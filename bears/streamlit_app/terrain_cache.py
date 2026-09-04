"""
terrain_cache.py
=================
Lokaler Cache fuer OpenStreetMap-Gelaendeabfragen (Overpass API), damit
TerrainFeatureSet/OSM.py nicht bei jedem einzelnen Simulationsschritt live
abgefragt werden muss.

Warum das noetig ist (siehe Recherche-Ergebnis zur Maplibre/Simulation-
Optimierung): Die oeffentliche Overpass-API hat nachweislich Rate-Limits
und wiederkehrende Stabilitaetsprobleme. Bei einer Simulation mit vielen
Schritten (und pro Schritt mehreren Kandidatenrichtungen) waere das sonst
der Flaschenhals bzw. Absturzpunkt des Systems.

Wichtig (Update nach echtem Testlauf 25.08.2026): Overpass hat bei
schnellen, direkt aufeinanderfolgenden Anfragen ohne eigenen User-Agent
mit HTTP 406 ("Not Acceptable") geantwortet - vermutlich eine
Bot-/Abuse-Schutzmassnahme des Servers. Dieses Modul schickt daher NICHT
mehr ueber OSM.py's rohen requests.post(), sondern:
  - mit einem eindeutigen User-Agent-Header (von Overpass empfohlen)
  - mit einer kleinen Pause vor jeder echten Anfrage (Selbst-Drosselung)
  - mit Wiederholungsversuchen (steigende Wartezeit) bei einzelnen Fehlern
  - mit einem "Circuit Breaker": nach mehreren Fehlern IN FOLGE wird die
    Terrain-Abfrage fuer den Rest des Laufs automatisch abgeschaltet
    (Simulation laeuft dann einfach ohne Gelaende-Gewichtung weiter,
    statt sich an hunderten Fehlversuchen aufzuhaengen)

Funktionsweise (Cache): Koordinaten werden auf ein Raster gerundet
(Standard ca. 150m Kantenlaenge), damit nahegelegene Simulationsschritte
denselben Cache-Eintrag wiederverwenden statt jedes Mal neu abzufragen.
Ergebnisse landen dauerhaft in SQLite.
"""

import json
import os
import sqlite3
import time

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
_SIM_DIR = os.path.join(_HERE, "bear_simulation")

DEFAULT_CACHE_DB = os.path.join(_SIM_DIR, "data", "terrain_cache.db")

# Rasterweite in Grad (~150m in Mitteleuropa/Japan). Kleiner = praeziser,
# aber mehr Overpass-Anfragen; groesser = weniger Anfragen, groebere Aufloesung.
GRID_SIZE_DEG = 0.0015

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Unabhaengige Spiegelserver (andere Betreiber, andere Domains). Falls
# overpass-api.de bei dir blockiert/nicht erreichbar ist (z.B. durch eine
# Netzwerk-Firewall), sind diese trotzdem oft erreichbar, weil sie
# technisch nichts miteinander zu tun haben.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# Overpass bittet Nutzer explizit um einen eindeutigen User-Agent statt des
# generischen "python-requests/x.x" (das manche Server als Bot blocken).
HEADERS = {"User-Agent": "OTH-Regensburg-WildlifeTracking/1.0 (Bachelorarbeit, nicht-kommerziell)"}

# Standard-Tags, dieselben wie in Fabians OSM.py, damit die Ergebnisse
# vergleichbar bleiben.
DEFAULT_QUERY_ELEMENTS = {
    "way": ["landuse", "natural", "waterway", "water", "aerialway", "geological", "railway",
            "military", "highway", "place", "barrier", "leisure", "power"],
    "node": ["landuse", "natural", "geological"],
}

MIN_SECONDS_BETWEEN_REQUESTS = 1.2  # Selbst-Drosselung
CONSECUTIVE_FAILURES_BEFORE_GIVING_UP = 3


class TerrainCache:
    def __init__(self, db_path: str = DEFAULT_CACHE_DB, grid_size_deg: float = GRID_SIZE_DEG):
        self.db_path = db_path
        self.grid_size_deg = grid_size_deg
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
        self._last_request_time = 0.0
        self._consecutive_failures = 0
        self._giving_up = False  # Circuit Breaker: True = keine echten Anfragen mehr in diesem Lauf

    def _init_db(self):
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
        conn.commit()
        conn.close()

    def _grid_key(self, lat: float, lon: float) -> tuple[float, float]:
        g = self.grid_size_deg
        return (round(lat / g) * g, round(lon / g) * g)

    def _throttle(self):
        """Sorgt fuer mind. MIN_SECONDS_BETWEEN_REQUESTS Pause zwischen echten Anfragen."""
        elapsed = time.time() - self._last_request_time
        wait = MIN_SECONDS_BETWEEN_REQUESTS - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_time = time.time()

    def _query_overpass_raw(self, lat: float, lon: float, radius: int) -> dict:
        """Baut die Overpass-QL-Anfrage (wie OSM.py) und schickt sie mit
        eigenem User-Agent + Drosselung ab - probiert dabei nacheinander
        alle unabhaengigen Spiegelserver aus OVERPASS_URLS durch, statt
        denselben (evtl. blockierten) Server mehrfach zu wiederholen."""
        query = "[out:json];\n("
        for element_type, tags in DEFAULT_QUERY_ELEMENTS.items():
            for tag in tags:
                query += f"\n  {element_type}[\"{tag}\"](around:{radius},{lat},{lon});"
        query += "\n);\nout body geom;"

        last_error = None
        for i, url in enumerate(OVERPASS_URLS):
            self._throttle()
            try:
                resp = requests.post(url, data={"data": query}, headers=HEADERS, timeout=8)
                if resp.status_code == 200:
                    return resp.json()
                last_error = f"{url} -> HTTP {resp.status_code}: {resp.text[:150]}"
            except Exception as e:
                last_error = f"{url} -> {e}"

            if i < len(OVERPASS_URLS) - 1:
                time.sleep(1)  # kurze Pause, dann direkt naechsten Spiegel probieren

        raise RuntimeError(last_error)

    def get_features(self, lat: float, lon: float, radius: int = 150) -> dict:
        """
        Liefert Terrain-Features (0/1-Flags pro OSM-Tag/-Wert) fuer eine
        Koordinate - aus dem Cache, falls vorhanden, sonst live von Overpass
        abgefragt (und danach gecacht). Bei wiederholten Fehlern schaltet
        sich die Terrain-Abfrage fuer den Rest des Laufs automatisch ab
        (Circuit Breaker) statt endlos weiter zu scheitern.
        """
        lat_key, lon_key = self._grid_key(lat, lon)

        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT features_json FROM terrain_cache WHERE lat_key=? AND lon_key=? AND radius=?",
            (lat_key, lon_key, radius),
        ).fetchone()

        if row is not None:
            conn.close()
            return json.loads(row[0])

        if self._giving_up:
            conn.close()
            return {}

        try:
            raw = self._query_overpass_raw(lat, lon, radius)
            self._consecutive_failures = 0
        except Exception as e:
            self._consecutive_failures += 1
            print(f"  [Warnung] Overpass-Abfrage fehlgeschlagen ({lat:.5f},{lon:.5f}): {e}")
            if self._consecutive_failures >= CONSECUTIVE_FAILURES_BEFORE_GIVING_UP:
                self._giving_up = True
                print(f"  [Hinweis] {CONSECUTIVE_FAILURES_BEFORE_GIVING_UP} Fehler in Folge - "
                      f"Terrain-Abfrage wird fuer den Rest dieses Laufs deaktiviert "
                      f"(Simulation laeuft ohne Gelaende-Gewichtung weiter).")
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
        Wandelt die rohe Overpass-Antwort (Tag -> Werteliste) in einfache
        0/1-Flags um - sowohl fuer den Tag-Namen selbst (z.B. 'highway')
        als auch fuer jeden gefundenen Wert (z.B. 'motorway', 'forest').
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
    print(f"Cache-Datenbank: {cache.db_path}")
    print("Teste Abfrage (Fukushima-Region, Startkamera aus 2024Bear)...")
    features = cache.get_features(37.476533, 139.963517, radius=150)
    print(f"Gefundene Features: {features}")
    print(f"\nCache-Statistik: {cache.stats()}")
    print("Zweite Abfrage derselben Stelle (sollte aus Cache kommen, keine Netzwerk-Pause):")
    t0 = time.time()
    features2 = cache.get_features(37.476533, 139.963517, radius=150)
    print(f"Dauer: {time.time()-t0:.3f}s (sollte nahe 0 sein)")
    assert features == features2
    print("OK - identisches Ergebnis aus dem Cache.")