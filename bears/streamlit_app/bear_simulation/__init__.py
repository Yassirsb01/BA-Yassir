"""
bear_simulation/__init__.py
============================
Integration layer between map.py and the movement model of Fabian Breu.

Trajectory segments are built directly from database.db instead of
importing StepSelectionModel/StepTrajectorySet. Their loading chain ends
in ClusterCalculator -> Hdbscan and therefore requires hdbscan and
sklearn, whose compiled libraries are blocked by Windows Smart App Control
on the development machine. That cluster analysis only produces the local
geometric medians, which generate_alternative_steps() never reads, so it
is dispensable for this map. Segmentation rules and step generation are
unchanged; see _build_segments_from_db() and ANPASSUNGEN.md, item 7.

Public API:
  get_simulation_options()
      -> (bear_ids: list[str],
          seasons_info: dict[bear_id, dict[season, step_count]])

  get_simulation_geojson(bear_id, season, num_alternatives)
      -> {"points": FeatureCollection, "paths": FeatureCollection}
"""

import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta

import streamlit as st

from .data.BearSeasons import BearSeasons
from .model.TrajectoryPoint import TrajectoryPoint
from .model.TrajectorySegment import TrajectorySegment

# Step generation is reused from sync_simulation rather than implemented a
# third time. The import deliberately points "upwards" into the
# application: this file is the application integration layer, which also
# imports Streamlit, and not a reusable library.
try:
    from sync_simulation import _generate_alternative_steps as _gen_alt_steps
except Exception as _err:   # pragma: no cover - only on a broken installation
    _gen_alt_steps = None
    print(f"[bear_simulation] sync_simulation could not be loaded: {_err}")

_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "database.db")

# Segmentation rules, exactly the values used by StepTrajectorySet in the
# original model: a gap of more than 1.5 hours ends a segment, after which
# segments are additionally split at season boundaries.
_MAX_GAP = timedelta(hours=1.5)

# Segments with fewer steps than this are discarded
_MIN_STEPS = 5

# Consistent season order (spring, summer, autumn, winter)
SEASON_ORDER = ["spring", "summer", "autumn", "winter"]


# --- Cached singleton --------------------------------------------------

class _SpeedTable:
    """
    Speed table held purely as an in-memory dictionary.

    Rationale: SQLite connections must not be shared across threads, but
    Streamlit calls the map from changing threads. The bear_speeds table is
    therefore read ONCE and served from the dictionary afterwards.

    The method signature matches BearSpeeds exactly, so the table can be
    passed to _generate_alternative_steps without adaptation.
    """

    def __init__(self, rows):
        self._speeds = {(g, a, s, h, src): m for g, a, s, h, src, m in rows}

    def get_median_speed_for_type_and_time(self, gender, age, season, hour, source):
        return self._speeds.get((gender, age, season, hour, source))


def _build_segments_from_db(source: str = "Carpathians"):
    """
    Build the trajectory segments directly from database.db, without
    StepTrajectorySet and therefore without the chain
    SeasonalTrajectoryProcessor -> ClusterCalculator -> Hdbscan.

    Why this is reimplemented rather than imported (see ANPASSUNGEN.md,
    item 7): StepTrajectorySet.build_segments() ends by calling
    assign_geometric_medians(), and ONLY that last step needs the cluster
    chain and thus the hdbscan and sklearn packages. Their compiled
    libraries are blocked by Windows Smart App Control on the development
    machine ("DLL load failed while importing murmurhash"), which made the
    entire import fail. generate_alternative_steps() never reads
    local_geometric_median, so the expensive step is simply superfluous
    for this map.

    The segmentation rules are identical to the original:
      1. group by bear_id, sort by time
      2. start a new segment at a time gap of more than 1.5 hours
      3. additionally split at season boundaries (BearSeasons)

    Returns:
        list[TrajectorySegment] with .season set
    """
    if not os.path.exists(_DB):
        return []

    con = sqlite3.connect(_DB)
    try:
        rows = con.execute(
            "SELECT wildlife_id, time, latitude, longitude, gender, age "
            "FROM wildlife_locations WHERE source=? ORDER BY wildlife_id, time",
            (source,),
        ).fetchall()
    finally:
        con.close()

    grouped = defaultdict(list)
    for bear_id, t, lat, lon, gender, age in rows:
        try:
            ts = datetime.strptime(str(t), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        grouped[bear_id].append((ts, lat, lon, gender, age))

    bs = BearSeasons()
    segments = []

    for bear_id, entries in grouped.items():
        entries.sort(key=lambda e: e[0])

        current, last_time, current_season = [], None, None
        gender = age = None

        def _flush():
            # Steps = points - 1. Segments that are too short are
            # worthless for a step simulation and are discarded.
            if len(current) - 1 >= _MIN_STEPS and current_season:
                seg = TrajectorySegment(bear_id=bear_id, gender=gender, age=age,
                                        segment=list(current))
                seg.season = current_season
                segments.append(seg)

        for ts, lat, lon, g, a in entries:
            gender, age = g, a
            season = bs.get_season(ts)
            gap = (last_time is not None and (ts - last_time) > _MAX_GAP)

            # Split on a time gap OR a change of season
            if current and (gap or season != current_season):
                _flush()
                current = []

            if not current:
                current_season = season
            current.append(TrajectoryPoint(ts, lat, lon))
            last_time = ts

        _flush()

    return segments


@st.cache_resource(show_spinner="Loading bear simulation data ...")
def _load_model():
    """
    Build segments and the speed table once, cached.

    Returns (speeds, index) where index = {bear_id: {season: best_segment}}
    and "best segment" is the one with the most GPS steps for that
    (bear, season) combination.

    The first return value used to be the StepSelectionModel. Since only
    generate_alternative_steps() was needed from it and that logic now
    comes from sync_simulation, it holds the speed table instead.
    """
    try:
        segments = _build_segments_from_db("Carpathians")
        if not segments:
            return None

        con = sqlite3.connect(_DB)
        try:
            speed_rows = con.execute(
                "SELECT gender, age, season, hour, source, median "
                "FROM bear_speeds WHERE wildlife_type='bear'"
            ).fetchall()
        finally:
            con.close()
        speeds = _SpeedTable(speed_rows)

        # Index aufbauen: {bear_id: {season: bestes_segment}}
        by_bear_season: dict = defaultdict(dict)
        for seg in segments:
            bid    = str(getattr(seg, "bear_id", ""))
            season = str(getattr(seg, "season",   ""))
            steps  = len(seg.segment) - 1
            if not bid or not season or steps < _MIN_STEPS:
                continue
            existing = by_bear_season[bid].get(season)
            if existing is None or steps > len(existing.segment) - 1:
                by_bear_season[bid][season] = seg

        # Drop bears without a usable season
        index = {bid: dict(seasons)
                 for bid, seasons in by_bear_season.items()
                 if seasons}

        return speeds, index

    except Exception as e:
        print(f"[bear_simulation] Segmentaufbau fehlgeschlagen: {e}")
        return None


# --- Public API -------------------------------------------------------────────────

def get_simulation_options():
    """
    Return (bear_ids, seasons_info).

    bear_ids     - sorted list of usable bear IDs (str)
    seasons_info - dict {bear_id: {season: step_count}}, giving the exact
                   number of real steps per (bear, season) combination.
    """
    result = _load_model()
    if result is not None:
        _, index = result
        bear_ids = sorted(index.keys(), key=lambda x: (int(x) if x.isdigit() else x))
        seasons_info = {
            bid: {s: len(seg.segment) - 1
                  for s, seg in seasons.items()}
            for bid, seasons in index.items()
        }
        return bear_ids, seasons_info

    # Fallback: query the database directly; no season information available
    if not os.path.exists(_DB):
        return [], {}
    try:
        import sqlite3
        con = sqlite3.connect(_DB)
        rows = con.execute(
            "SELECT DISTINCT wildlife_id FROM wildlife_locations "
            "WHERE source='Carpathians' ORDER BY wildlife_id"
        ).fetchall()
        con.close()
        bear_ids = [str(r[0]) for r in rows]
        return bear_ids, {}
    except Exception as e:
        print(f"[bear_simulation] DB-Fehler: {e}")
        return [], {}


@st.cache_data(show_spinner=False)
def get_simulation_geojson(bear_id: str, season: str,
                           num_alternatives: int = 10) -> dict:
    """
    Return GeoJSON for the main map:
    {"points": FeatureCollection, "paths": FeatureCollection}

    Uses the best segment for (bear_id, season), that is, the one with the
    most real steps available for exactly that season.

    Real steps   -> color="#1565c0" (blue)
    Alternatives -> color="#ff9800" (orange)
    """
    _EMPTY = {
        "points": {"type": "FeatureCollection", "features": []},
        "paths":  {"type": "FeatureCollection", "features": []},
    }

    try:
        result = _load_model()
        if result is not None and _gen_alt_steps is not None:
            speeds, index = result
            bear_seasons = index.get(str(bear_id), {})

            # Requested season; fall back to the season with most steps
            seg = bear_seasons.get(season)
            if seg is None and bear_seasons:
                seg = max(bear_seasons.values(), key=lambda s: len(s.segment))

            if seg is not None:
                # Same step generation as on the animation page.
                # scale_to_interval=False because these segments are
                # already split at gaps longer than 1.5 h, so the steps
                # practically always span one hour (original behaviour).
                alts = _gen_alt_steps(
                    seg, speeds, num_alternatives=num_alternatives,
                    scale_to_interval=False,
                )
                geojson = _to_geojson(alts, str(bear_id))
                if geojson["points"]["features"]:
                    return geojson
    except Exception as e:
        print(f"[bear_simulation] Fehler: {e}")

    fb = _db_fallback(str(bear_id))
    return fb if fb["paths"]["features"] else _EMPTY


# ── Private Hilfsfunktionen ──────────────────────────────────────────────────

def _to_geojson(alternatives_per_step: list, bear_id: str) -> dict:
    """Konvertiert generate_alternative_steps()-Output nach GeoJSON."""
    pts, path_coords = [], []
    for step_idx, step in enumerate(alternatives_per_step):
        for alt in step:
            lat, lon = alt["end"]
            is_real = bool(alt.get("real", False))
            pts.append({
                "type": "Feature",
                "properties": {
                    "bear_id":  bear_id,
                    "type":     "real" if is_real else "alternative",
                    "color":    "#1565c0" if is_real else "#ff9800",
                    "step_idx": step_idx,
                    "angle":    round(float(alt.get("angle", 0)), 1),
                    "length_m": round(float(alt.get("length", 0)), 1),
                },
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
            })
            if is_real:
                path_coords.append([lon, lat])
    paths = []
    if len(path_coords) >= 2:
        paths.append({
            "type": "Feature",
            "properties": {"bear_id": bear_id, "color": "#1565c0", "type": "real_path"},
            "geometry": {"type": "LineString", "coordinates": path_coords},
        })
    return {
        "points": {"type": "FeatureCollection", "features": pts},
        "paths":  {"type": "FeatureCollection", "features": paths},
    }


def _db_fallback(bear_id: str) -> dict:
    """Raw GPS data straight from database.db, used when the model cannot be loaded."""
    empty = {
        "points": {"type": "FeatureCollection", "features": []},
        "paths":  {"type": "FeatureCollection", "features": []},
    }
    if not os.path.exists(_DB):
        return empty
    try:
        import sqlite3
        con = sqlite3.connect(_DB)
        rows = con.execute(
            "SELECT time, latitude, longitude FROM wildlife_locations "
            "WHERE wildlife_id=? AND source='Carpathians' ORDER BY time",
            (bear_id,)
        ).fetchall()
        con.close()
    except Exception as e:
        print(f"[bear_simulation] DB-Fallback-Fehler: {e}")
        return empty
    if not rows:
        return empty
    coords = [[float(lon), float(lat)] for _, lat, lon in rows]
    return {
        "points": {"type": "FeatureCollection", "features": [
            {"type": "Feature",
             "properties": {"bear_id": bear_id, "color": "#1565c0",
                            "type": "real", "timestamp": str(t)},
             "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]}}
            for t, lat, lon in rows[::15]
        ]},
        "paths": {"type": "FeatureCollection", "features": [
            {"type": "Feature",
             "properties": {"bear_id": bear_id, "color": "#1565c0", "type": "real_path"},
             "geometry": {"type": "LineString", "coordinates": coords}}
        ] if len(coords) >= 2 else []},
    }
