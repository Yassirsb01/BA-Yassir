"""
bear_simulation/__init__.py
============================
Integrationsschicht zwischen map.py und Fabian Breus StepSelectionModel.

Öffentliche API:
  get_simulation_options()
      -> (bear_ids: list[str],
          seasons_info: dict[bear_id, dict[season, step_count]])

  get_simulation_geojson(bear_id, season, num_alternatives)
      -> {"points": FeatureCollection, "paths": FeatureCollection}
"""

import os
from collections import defaultdict
import streamlit as st

try:
    from bear_simulation.model.StepSelectionModel import StepSelectionModel as _SSM
    _MODEL_AVAILABLE = True
except Exception as _err:
    _SSM = None
    _MODEL_AVAILABLE = False
    print(f"[bear_simulation] Import fehlgeschlagen: {_err}")

_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "database.db")

# Konsistente Reihenfolge der Saisons (Frühling → Sommer → Herbst → Winter)
SEASON_ORDER = ["spring", "summer", "autumn", "winter"]


# ── Gecachtes Singleton ──────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Lade Bear-Simulationsmodell …")
def _load_model():
    """
    Lädt StepSelectionModel einmalig.

    Baut einen zweistufigen Index: {bear_id: {season: bestes_segment}}
    „Bestes Segment" = das mit den meisten GPS-Schritten für diese
    (Bär, Saison)-Kombination. Segmente mit < 5 Schritten werden ignoriert.

    Ersetzt außerdem die SQLite-gebundene Speed-Abfrage durch einen
    In-Memory-Dict (thread-safety: SQLite-Connections dürfen nicht
    thread-übergreifend genutzt werden).
    """
    if not _MODEL_AVAILABLE:
        return None
    try:
        ssm = _SSM("Carpathians")

        # Speed-Daten einmalig in einen Dict laden → kein SQLite zur Laufzeit
        ssm.bs.db.cursor.execute(
            "SELECT gender, age, season, hour, source, median "
            "FROM bear_speeds WHERE wildlife_type='bear'"
        )
        _speeds = {
            (row[0], row[1], row[2], row[3], row[4]): row[5]
            for row in ssm.bs.db.cursor.fetchall()
        }
        ssm.bs.get_median_speed_for_type_and_time = (
            lambda gender, age, season, hour, source:
            _speeds.get((gender, age, season, hour, source))
        )

        # Index aufbauen: {bear_id: {season: bestes_segment}}
        by_bear_season: dict = defaultdict(dict)
        for seg in ssm.sts.trajectories:
            bid    = str(getattr(seg, "bear_id", ""))
            season = str(getattr(seg, "season",   ""))
            steps  = len(seg.segment) - 1
            if not bid or not season or steps < 5:
                continue
            existing = by_bear_season[bid].get(season)
            if existing is None or steps > len(existing.segment) - 1:
                by_bear_season[bid][season] = seg

        # Bären ohne nutzbare Saison ausfiltern
        index = {bid: dict(seasons)
                 for bid, seasons in by_bear_season.items()
                 if seasons}

        return ssm, index

    except Exception as e:
        print(f"[bear_simulation] Modellladen fehlgeschlagen: {e}")
        return None


# ── Öffentliche API ──────────────────────────────────────────────────────────

def get_simulation_options():
    """
    Gibt (bear_ids, seasons_info) zurück.

    bear_ids    – sortierte Liste nutzbarer Bären-IDs (str)
    seasons_info – dict {bear_id: {season: step_count}}
                   Zeigt genau wie viele echte Schritte pro (Bär, Saison) vorliegen.
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

    # Fallback: DB direkt (kein Saison-Info verfügbar)
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
    Gibt GeoJSON für die Hauptkarte zurück.
    {"points": FeatureCollection, "paths": FeatureCollection}

    Verwendet das beste Segment für (bear_id, season) — also die meisten
    verfügbaren echten Schritte für genau diese Saison.

    Echte Schritte  → color="#1565c0" (blau)
    Alternativen    → color="#ff9800" (orange)
    """
    _EMPTY = {
        "points": {"type": "FeatureCollection", "features": []},
        "paths":  {"type": "FeatureCollection", "features": []},
    }

    try:
        result = _load_model()
        if result is not None:
            ssm, index = result
            bear_seasons = index.get(str(bear_id), {})

            # Gewünschte Saison, Fallback: saison mit den meisten Schritten
            seg = bear_seasons.get(season)
            if seg is None and bear_seasons:
                seg = max(bear_seasons.values(), key=lambda s: len(s.segment))

            if seg is not None:
                alts = ssm.generate_alternative_steps(
                    seg, num_alternatives=num_alternatives
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
    """GPS-Rohdaten direkt aus database.db — wird genutzt wenn Modell nicht ladbar."""
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
