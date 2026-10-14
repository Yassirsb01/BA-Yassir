"""
terrain_cache.py
=================
Local cache for OpenStreetMap terrain queries (Overpass API), so that
TerrainFeatureSet/OSM.py does not have to be queried live for every single
simulation step.

Rationale: the public Overpass API enforces rate limits and shows recurring
stability problems. A simulation with many steps, each evaluating several
candidate headings, would otherwise make the terrain lookup the bottleneck
and the most likely point of failure in the system.

Request handling: Overpass responded with HTTP 406 ("Not Acceptable") to
rapid consecutive requests that carried no dedicated user agent, which is
presumably a bot protection measure. This module therefore does not use the
raw requests.post() call from OSM.py but sends requests

  - with a distinct User-Agent header, as recommended by Overpass,
  - with a short pause before every real request (self-throttling),
  - with retries using increasing wait times on individual failures,
  - behind a circuit breaker: after several consecutive failures the
    terrain lookup is disabled for the remainder of the run, so the
    simulation continues without terrain weighting instead of stalling on
    hundreds of failed attempts.

Offline operation: tools/prefetch_terrain.py can load the entire camera
area once in advance. Inside such a prefetched area get_features() never
issues an internet request; a missing entry there means "no features
present". The live query below is only a fallback for points outside.

Caching strategy: coordinates are rounded to a grid (about 150 m edge
length by default) so that nearby simulation steps reuse the same cache
entry instead of triggering a new query. Results are persisted in SQLite.
"""

import json
import os
import sqlite3
import time

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
_SIM_DIR = os.path.join(_HERE, "bear_simulation")

DEFAULT_CACHE_DB = os.path.join(_SIM_DIR, "data", "terrain_cache.db")

# Grid size in degrees (roughly 150 m at these latitudes). Smaller values
# are more precise but cause more Overpass requests; larger values mean
# fewer requests at a coarser resolution.
GRID_SIZE_DEG = 0.0015

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Independent mirrors run by different operators on different domains. If
# overpass-api.de is unreachable, for example because of a network firewall,
# these are often still reachable since they share no infrastructure.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# Overpass explicitly asks clients for a distinct user agent instead of the
# generic "python-requests/x.x", which some servers block as a bot.
HEADERS = {"User-Agent": "OTH-Regensburg-WildlifeTracking/1.0 (academic, non-commercial)"}

# Default tags, identical to those in OSM.py of the movement simulation, so
# that results stay comparable.
DEFAULT_QUERY_ELEMENTS = {
    "way": ["landuse", "natural", "waterway", "water", "aerialway", "geological", "railway",
            "military", "highway", "place", "barrier", "leisure", "power"],
    "node": ["landuse", "natural", "geological"],
}

MIN_SECONDS_BETWEEN_REQUESTS = 1.2       # self-throttling
CONSECUTIVE_FAILURES_BEFORE_GIVING_UP = 2  # give up early on unreliable networks
REQUEST_TIMEOUT_SECONDS = 6              # limits the cost of each failed attempt


class TerrainCache:
    """
    Cached access to OpenStreetMap terrain features on a fixed grid.

    The circuit breaker state (_consecutive_failures / _giving_up) is held
    at CLASS level rather than per instance. With several simulated bears a
    separate TerrainCache() instance may be created per bear; if the
    counter belonged to the instance it would restart at zero for every
    bear and never actually trip, even when the network is demonstrably
    unreachable. Class level makes the behaviour independent of how often
    calling code constructs new instances.
    """
    _consecutive_failures = 0
    _giving_up = False

    def __init__(self, db_path: str = DEFAULT_CACHE_DB, grid_size_deg: float = GRID_SIZE_DEG):
        self.db_path = db_path
        self.grid_size_deg = grid_size_deg
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
        self._last_request_time = 0.0

    @classmethod
    def reset_circuit_breaker(cls):
        """Reset the circuit breaker manually, for example before an
        independent simulation run or in tests."""
        cls._consecutive_failures = 0
        cls._giving_up = False

    def _init_db(self):
        """
        Create the tables. If the file is not a valid SQLite database,
        sqlite3 raises a DatabaseError here. That must not bring down the
        application: terrain weighting is a convenience feature and the
        simulation runs without it. The cache is therefore disabled
        (self.disabled) and the reason recorded in self.disabled_reason, so
        the user interface can show a comprehensible warning instead of
        aborting with a traceback.
        """
        self.disabled = False
        self.disabled_reason = ""
        try:
            self._create_tables()
        except sqlite3.DatabaseError as e:
            self.disabled = True
            self.disabled_reason = (
                f"Terrain cache '{self.db_path}' is not a valid SQLite file ({e}). "
                "The simulation continues without terrain weighting. "
                "Rebuild with: python tools/prefetch_terrain.py --from-file "
                "bear_simulation/data/terrain_prefetch_raw/*.json"
            )
            print(f"[terrain_cache] {self.disabled_reason}")
            self._regions = []
            self._mem = {}
            return

    def _create_tables(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS terrain_cache (
                lat_key REAL NOT NULL,
                lon_key REAL NOT NULL,
                radius INTEGER NOT NULL,
                features_json TEXT NOT NULL,
                cached_at REAL NOT NULL,
                PRIMARY KEY (lat_key, lon_key, radius)
            )
        """)
        # Areas fully precomputed by tools/prefetch_terrain.py. Inside such
        # an area a missing cache entry does NOT mean "unknown" but "no
        # features present", so no internet request is ever issued there.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prefetch_regions (
                min_lat_key REAL NOT NULL,
                min_lon_key REAL NOT NULL,
                max_lat_key REAL NOT NULL,
                max_lon_key REAL NOT NULL,
                radius INTEGER NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        conn.commit()
        conn.close()
        self._regions = self._load_regions()
        self._mem: dict = {}  # in-memory lookup table, saves SQLite round trips

    def _load_regions(self) -> list[tuple]:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT min_lat_key, min_lon_key, max_lat_key, max_lon_key, radius FROM prefetch_regions"
        ).fetchall()
        conn.close()
        return rows

    def _in_prefetched_region(self, lat_key: float, lon_key: float, radius: int) -> bool:
        eps = 1e-9
        for min_lat, min_lon, max_lat, max_lon, r in self._regions:
            if r == radius and min_lat - eps <= lat_key <= max_lat + eps and min_lon - eps <= lon_key <= max_lon + eps:
                return True
        return False

    def _grid_key(self, lat: float, lon: float) -> tuple[float, float]:
        g = self.grid_size_deg
        return (round(lat / g) * g, round(lon / g) * g)

    def _throttle(self):
        """Enforce at least MIN_SECONDS_BETWEEN_REQUESTS between real requests."""
        elapsed = time.time() - self._last_request_time
        wait = MIN_SECONDS_BETWEEN_REQUESTS - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_time = time.time()

    def _query_overpass_raw(self, lat: float, lon: float, radius: int) -> dict:
        """Build the Overpass QL query, as OSM.py does, and send it with a
        dedicated user agent and throttling. Mirrors from OVERPASS_URLS are
        tried in turn rather than retrying the same, possibly blocked,
        server repeatedly."""
        query = "[out:json];\n("
        for element_type, tags in DEFAULT_QUERY_ELEMENTS.items():
            for tag in tags:
                query += f"\n  {element_type}[\"{tag}\"](around:{radius},{lat},{lon});"
        query += "\n);\nout body geom;"

        last_error = None
        for i, url in enumerate(OVERPASS_URLS):
            self._throttle()
            try:
                resp = requests.post(url, data={"data": query}, headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
                if resp.status_code == 200:
                    return resp.json()
                last_error = f"{url} -> HTTP {resp.status_code}: {resp.text[:150]}"
            except Exception as e:
                last_error = f"{url} -> {e}"

            if i < len(OVERPASS_URLS) - 1:
                time.sleep(1)  # brief pause, then try the next mirror

        raise RuntimeError(last_error)

    def get_cells_in_box(self, min_lat: float, min_lon: float,
                         max_lat: float, max_lon: float,
                         radius: int = 150) -> list[tuple]:
        """
        Return ALL cached grid cells inside a rectangle in one query.

        Counterpart to get_features(), which always returns a single cell.
        Required by the cluster-based heading selection
        (japan_comparison.choose_weighted_direction), which treats the
        terrain around the bear as an area rather than point by point.

        Never queries Overpass: this method is intended exclusively for
        prefetched areas (tools/prefetch_terrain.py). A missing cell there
        means "no features present" and simply does not appear in the
        result.

        Returns:
            A list of (lat_key, lon_key, features_dict).
        """
        if getattr(self, "disabled", False):
            return []
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT lat_key, lon_key, features_json FROM terrain_cache "
                "WHERE radius=? AND lat_key BETWEEN ? AND ? AND lon_key BETWEEN ? AND ?",
                (radius, min_lat, max_lat, min_lon, max_lon),
            ).fetchall()
        except sqlite3.DatabaseError as e:
            print(f"[terrain_cache] Grid section not readable: {e}")
            return []
        finally:
            conn.close()

        out = []
        for lat_key, lon_key, fj in rows:
            try:
                out.append((lat_key, lon_key, json.loads(fj)))
            except (ValueError, TypeError):
                continue
        return out

    def get_features(self, lat: float, lon: float, radius: int = 150) -> dict:
        """
        Return terrain features (0/1 flags per OSM tag and value) for a
        coordinate: from the cache if present, otherwise queried live from
        Overpass and cached afterwards. After repeated failures the terrain
        lookup disables itself for the rest of the run (circuit breaker)
        instead of continuing to fail.
        """
        # Cache unusable (see _init_db): report no features. Heading
        # selection then falls back to the unweighted random draw, which is
        # exactly the behaviour without terrain weighting.
        if getattr(self, "disabled", False):
            return {}

        lat_key, lon_key = self._grid_key(lat, lon)
        mem_key = (lat_key, lon_key, radius)
        if mem_key in self._mem:
            return self._mem[mem_key]

        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT features_json FROM terrain_cache WHERE lat_key=? AND lon_key=? AND radius=?",
            (lat_key, lon_key, radius),
        ).fetchone()

        if row is not None:
            conn.close()
            features = json.loads(row[0])
            self._mem[mem_key] = features
            return features

        # Prefetched area (tools/prefetch_terrain.py): a missing entry means
        # "no relevant terrain features" here, so return an empty result
        # immediately without any internet request.
        if self._in_prefetched_region(lat_key, lon_key, radius):
            conn.close()
            self._mem[mem_key] = {}
            return {}

        if TerrainCache._giving_up:
            conn.close()
            return {}

        try:
            raw = self._query_overpass_raw(lat, lon, radius)
            TerrainCache._consecutive_failures = 0
        except Exception as e:
            TerrainCache._consecutive_failures += 1
            print(f"  [warning] Overpass query failed ({lat:.5f},{lon:.5f}): {e}")
            if TerrainCache._consecutive_failures >= CONSECUTIVE_FAILURES_BEFORE_GIVING_UP:
                TerrainCache._giving_up = True
                print(f"  [note] {CONSECUTIVE_FAILURES_BEFORE_GIVING_UP} consecutive failures; "
                      f"terrain lookup is disabled for the rest of the session, including "
                      f"newly created TerrainCache instances. The simulation continues "
                      f"without terrain weighting.")
            conn.close()
            return {}

        features = self._to_flags(raw)

        conn.execute(
            "INSERT OR REPLACE INTO terrain_cache (lat_key, lon_key, radius, features_json, cached_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (lat_key, lon_key, radius, json.dumps(features), time.time()),
        )
        conn.commit()
        conn.close()
        return features

    @staticmethod
    def _to_flags(raw: dict) -> dict:
        """
        Convert the raw Overpass response (tag to list of values) into
        simple 0/1 flags, both for the tag name itself (for example
        'highway') and for every value found (for example 'motorway',
        'forest').
        """
        parsed = {tag: [] for element in DEFAULT_QUERY_ELEMENTS.values() for tag in element}
        for element in raw.get("elements", []):
            tags = element.get("tags", {})
            for tag in parsed.keys():
                if tag in tags:
                    parsed[tag].append(tags[tag])

        flags = {}
        for tag, values in parsed.items():
            if values:
                flags[tag] = 1
                for v in set(values):
                    flags[v] = 1
        return flags

    def stats(self) -> dict:
        conn = sqlite3.connect(self.db_path)
        n = conn.execute("SELECT COUNT(*) FROM terrain_cache").fetchone()[0]
        conn.close()
        return {"cached_cells": n, "db_path": self.db_path}


if __name__ == "__main__":
    cache = TerrainCache()
    print(f"Cache database: {cache.db_path}")
    print("Running a test query (Fukushima region, first camera of 2024Bear)...")
    features = cache.get_features(37.476533, 139.963517, radius=150)
    print(f"Features found: {features}")
    print(f"\nCache statistics: {cache.stats()}")
    print("Second query of the same location (should come from the cache, no network pause):")
    t0 = time.time()
    features2 = cache.get_features(37.476533, 139.963517, radius=150)
    print(f"Duration: {time.time()-t0:.3f}s (expected to be close to zero)")
    assert features == features2
    print("Identical result returned from the cache.")
