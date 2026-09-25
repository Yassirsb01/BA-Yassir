"""
bear_simulation/__init__.py
============================
Integrationsschicht zwischen map.py und Fabian Breus Bewegungsmodell.

Die Segmente werden direkt aus database.db aufgebaut, statt
StepSelectionModel/StepTrajectorySet zu importieren: deren Ladekette endet
in ClusterCalculator -> Hdbscan und braucht damit hdbscan/sklearn, deren
kompilierte Dateien auf dem Entwicklungsrechner von Windows Smart App
Control blockiert werden. Die Cluster-Analyse liefert ausschliesslich die
lokalen geometrischen Mediane, die von generate_alternative_steps() nie
gelesen werden - fuer diese Karte also verzichtbar. Segmentierungsregeln
und Schritt-Erzeugung sind unveraendert (siehe _build_segments_from_db()
und ANPASSUNGEN.md, Punkt 7).

Öffentliche API:
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

# Die Schritt-Erzeugung wird aus sync_simulation wiederverwendet statt ein
# drittes Mal implementiert. Der Import zeigt bewusst "nach oben" in die
# App - diese Datei ist ohnehin die App-Integrationsschicht (sie importiert
# auch streamlit) und keine wiederverwendbare Bibliothek.
try:
    from sync_simulation import _generate_alternative_steps as _gen_alt_steps
except Exception as _err:   # pragma: no cover - nur bei kaputter Installation
    _gen_alt_steps = None
    print(f"[bear_simulation] sync_simulation nicht ladbar: {_err}")

_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "database.db")

# Segmentierungsregeln - exakt die Werte aus Fabians StepTrajectorySet:
# Eine Luecke von mehr als 1,5 Stunden beendet ein Segment, danach wird
# zusaetzlich an Saisongrenzen getrennt (SeasonalTrajectoryProcessor).
_MAX_GAP = timedelta(hours=1.5)

# Segmente mit weniger Schritten werden verworfen (wie bisher in _load_model)
_MIN_STEPS = 5

# Konsistente Reihenfolge der Saisons (Frühling → Sommer → Herbst → Winter)
SEASON_ORDER = ["spring", "summer", "autumn", "winter"]


# ── Gecachtes Singleton ──────────────────────────────────────────────────────

class _SpeedTable:
    """
    Geschwindigkeitstabelle als reiner In-Memory-Dict.

    Grund (unveraendert aus der Vorversion): SQLite-Connections duerfen
    nicht thread-uebergreifend genutzt werden, Streamlit ruft die Karte
    aber aus wechselnden Threads auf. Deshalb wird bear_speeds EINMAL
    gelesen und danach nur noch aus dem Dict bedient.

    Die Methodensignatur entspricht exakt BearSpeeds, damit die Tabelle
    ohne Anpassung an _generate_alternative_steps uebergeben werden kann.
    """

    def __init__(self, rows):
        self._speeds = {(g, a, s, h, src): m for g, a, s, h, src, m in rows}

    def get_median_speed_for_type_and_time(self, gender, age, season, hour, source):
        return self._speeds.get((gender, age, season, hour, source))


def _build_segments_from_db(source: str = "Carpathians"):
    """
    Baut die Trajektorien-Segmente direkt aus database.db auf - ohne
    StepTrajectorySet und damit ohne die Kette
    SeasonalTrajectoryProcessor -> ClusterCalculator -> Hdbscan.

    WARUM NACHGEBAUT STATT IMPORTIERT (siehe ANPASSUNGEN.md, Punkt 7):
    StepTrajectorySet.build_segments() ruft am Ende assign_geometric_medians()
    auf, und NUR dieser letzte Schritt braucht die Cluster-Kette und damit
    die Pakete hdbscan/sklearn. Deren kompilierte Dateien werden auf dem
    Entwicklungsrechner von Windows Smart App Control blockiert
    ("DLL load failed while importing murmurhash"), wodurch der gesamte
    Import scheiterte. generate_alternative_steps() liest
    local_geometric_median aber an keiner Stelle - der teure Schritt ist
    fuer diese Karte schlicht ueberfluessig.

    Die Segmentierungsregeln sind identisch zu Fabians Original:
      1. nach bear_id gruppieren, nach Zeit sortieren
      2. neues Segment bei einer Zeitluecke > 1,5 Stunden
      3. zusaetzlich an Saisongrenzen trennen (BearSeasons)

    Returns:
        list[TrajectorySegment] mit gesetztem .season
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
            # Schritte = Punkte - 1; zu kurze Segmente sind fuer eine
            # Schritt-Simulation wertlos und wurden auch bisher verworfen.
            if len(current) - 1 >= _MIN_STEPS and current_season:
                seg = TrajectorySegment(bear_id=bear_id, gender=gender, age=age,
                                        segment=list(current))
                seg.season = current_season
                segments.append(seg)

        for ts, lat, lon, g, a in entries:
            gender, age = g, a
            season = bs.get_season(ts)
            gap = (last_time is not None and (ts - last_time) > _MAX_GAP)

            # Trennen bei Zeitluecke ODER Saisonwechsel
            if current and (gap or season != current_season):
                _flush()
                current = []

            if not current:
                current_season = season
            current.append(TrajectoryPoint(ts, lat, lon))
            last_time = ts

        _flush()

    return segments


@st.cache_resource(show_spinner="Lade Bear-Simulationsdaten …")
def _load_model():
    """
    Baut einmalig (gecacht) Segmente + Geschwindigkeitstabelle auf.

    Rueckgabe wie bisher: (speeds, index) mit
    index = {bear_id: {season: bestes_segment}}
    „Bestes Segment" = das mit den meisten GPS-Schritten fuer diese
    (Baer, Saison)-Kombination.

    Der erste Rueckgabewert war frueher das StepSelectionModel; da davon
    nur generate_alternative_steps() gebraucht wurde und diese Logik jetzt
    aus sync_simulation kommt, steht dort nun die Geschwindigkeitstabelle.
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

        # Bären ohne nutzbare Saison ausfiltern
        index = {bid: dict(seasons)
                 for bid, seasons in by_bear_season.items()
                 if seasons}

        return speeds, index

    except Exception as e:
        print(f"[bear_simulation] Segmentaufbau fehlgeschlagen: {e}")
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
        if result is not None and _gen_alt_steps is not None:
            speeds, index = result
            bear_seasons = index.get(str(bear_id), {})

            # Gewünschte Saison, Fallback: saison mit den meisten Schritten
            seg = bear_seasons.get(season)
            if seg is None and bear_seasons:
                seg = max(bear_seasons.values(), key=lambda s: len(s.segment))

            if seg is not None:
                # Dieselbe Schritt-Erzeugung wie in der Animations-Seite -
                # scale_to_interval=False, weil die Segmente hier bereits an
                # Luecken > 1,5 h getrennt sind und die Schritte damit
                # praktisch immer eine Stunde umfassen (Originalverhalten).
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
