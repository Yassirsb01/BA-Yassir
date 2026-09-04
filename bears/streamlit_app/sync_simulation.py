"""
sync_simulation.py
====================
Erzeugt echte + simulierte Bärenbewegung GARANTIERT synchron für denselben
Bären, denselben Tag - im Gegensatz zum vorherigen Ansatz (getrennte
Bär-/Zeitraum-Auswahl für Carpathian vs. Simulation), der zwei potenziell
völlig unzusammenhängende Datensätze nebeneinander gezeigt hat.

Wie: Nutzt Fabians StepSelectionModel DIREKT (nicht den bisherigen,
undurchsichtigen bear_simulation-Wrapper) und füttert es mit genau den
echten GPS-Punkten, die auch für den gewählten Tag in der Karte angezeigt
werden. Jede Alternative wird mit dem Zeitstempel ihres zugehörigen echten
Schritts verknüpft - Animation von echt und simuliert läuft dadurch immer
exakt im selben Zeitfenster, Schritt für Schritt.

Laut Prof. Dünnweber (Meeting 21.08.2026) ausdrücklich erlaubt: Fabians
Code darf angepasst werden, muss nicht 1:1 übernommen werden - Ziel ist
die Umsetzung seiner Anforderungen (echte + simulierte Bewegung
nebeneinander zur "Realitätsprüfung der KI-Simulation").

Wichtiger Hinweis zur Saison: Carpathian nutzt biologische Saisonlabel
("Forest fruits", "Hyperphagia", ...), Fabians Geschwindigkeitstabelle
(bear_speeds) braucht Kalender-Saisons ("spring"/"summer"/"autumn"/
"winter"). Die Saison wird deshalb NICHT aus den Carpathian-Properties
übernommen, sondern direkt aus dem Datum abgeleitet - mit Fabians eigener
BearSeasons-Klasse (gleicher Code, den auch StepTrajectorySet nutzt).
"""

import os
import sys
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
_SIM_DIR = os.path.join(_HERE, "bear_simulation")
for _p in (_SIM_DIR, os.path.join(_SIM_DIR, "model"), os.path.join(_SIM_DIR, "data"), os.path.join(_SIM_DIR, "util")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from TrajectoryPoint import TrajectoryPoint        # noqa: E402
from TrajectorySegment import TrajectorySegment    # noqa: E402
from DatabaseConnection import DatabaseConnection  # noqa: E402
from BearSpeeds import BearSpeeds                  # noqa: E402
from BearSeasons import BearSeasons                # noqa: E402
from GeoToolBox import GeoToolBox                  # noqa: E402
import random                                      # noqa: E402
from geopy.distance import geodesic                # noqa: E402

SIM_SOURCE = "Carpathians"
_SIM_DB_PATH = os.path.join(_SIM_DIR, "data", "database.db")


def _generate_alternative_steps(segment, bear_speeds, num_alternatives=10, perception_distance=200):
    """
    Direkte Neuimplementierung von StepSelectionModel.generate_alternative_steps()
    (identische Logik, siehe model/StepSelectionModel.py) - bewusst OHNE den Import
    von StepSelectionModel selbst, weil dessen __init__ ueber StepTrajectorySet ->
    SeasonalTrajectoryProcessor -> ClusterCalculator -> Hdbscan eine schwere,
    fuer diesen Anwendungsfall unnoetige Cluster-Analyse-Kette mitzieht (und das
    'hdbscan'-Paket braucht, das hier evtl. nicht installiert ist - vermutlich der
    Grund, warum die Simulation bisher im Fallback-Modus lief). Fuer die eigentliche
    Schritt-Generierung wird nur BearSpeeds + GeoToolBox gebraucht, siehe unten.
    """
    alternatives_per_step = []

    for i in range(len(segment.segment) - 1):
        start = segment.segment[i]
        end = segment.segment[i + 1]

        hour = start.time.hour
        median_speed_kmh = bear_speeds.get_median_speed_for_type_and_time(
            segment.gender, segment.age, segment.season, hour, SIM_SOURCE
        )
        if median_speed_kmh is None:
            alternatives_per_step.append([])
            continue

        step_length_m = median_speed_kmh * 1000
        start_point = (start.lat, start.lon)
        end_point = (end.lat, end.lon)
        real_direction = GeoToolBox.calculate_direction(start_point, end_point)

        alt_steps = []
        for _ in range(num_alternatives):
            angle_offset = random.uniform(0, 360)
            alt_direction = (real_direction + angle_offset) % 360
            alt_endpoint = GeoToolBox.destination_point(start_point, alt_direction, step_length_m)
            perception_point = GeoToolBox.destination_point(start_point, alt_direction, perception_distance)
            alt_steps.append({
                "start": start_point, "end": alt_endpoint, "perception_point": perception_point,
                "angle": alt_direction, "length": step_length_m, "real": False,
            })

        perception_real = GeoToolBox.destination_point(start_point, real_direction, perception_distance)
        alt_steps.append({
            "start": start_point, "end": end_point, "perception_point": perception_real,
            "angle": real_direction, "length": geodesic(start_point, end_point).meters, "real": True,
        })

        alternatives_per_step.append(alt_steps)

    return alternatives_per_step


def _normalize_gender(raw) -> str:
    """Carpathian-Rohwerte (z.B. 'male'/'Female'/'M') -> 'M'/'F', wie es
    bear_speeds in der DB erwartet."""
    s = str(raw).strip().lower()
    return "M" if s.startswith("m") else "F"


def _normalize_age(raw) -> str:
    """Carpathian-Rohwerte -> 'J' (juvenil/subadult) oder 'A' (adult)."""
    s = str(raw).strip().lower()
    if "sub" in s or "juv" in s or s in ("j", "young", "yearling"):
        return "J"
    return "A"


def build_synced_geojson(
    carpathian_points_geojson: dict,
    num_alternatives: int = 10,
    perception_distance: int = 200,
) -> dict:
    """
    Args:
        carpathian_points_geojson: das GeoJSON "points"-Objekt, das
            get_carpathian_geojson() für EINEN Bären an EINEM Tag liefert
            (properties: bear_id, timestamp, sex, age, ...).
        num_alternatives: wie viele Alternativ-Kandidaten pro echtem Schritt.
        perception_distance: siehe StepSelectionModel (Wahrnehmungsradius in m).

    Returns:
        {
          "real": GeoJSON FeatureCollection (== die echten Punkte, nur
                  nochmal durch Fabians Modell bestaetigt/durchgereicht),
          "alternative": GeoJSON FeatureCollection, jede Alternative mit
                  properties.timestamp EXAKT auf den Start-Zeitpunkt ihres
                  zugehoerigen echten Schritts gesetzt (kein synthetischer,
                  unabhaengiger Zeitstrahl mehr noetig),
          "warnings": Liste evtl. Auffaelligkeiten (z.B. zu wenige Punkte,
                  fehlende Geschwindigkeitsdaten fuer bestimmte Stunden).
        }

    Bei < 2 echten Punkten (kein Schritt moeglich) werden leere
    FeatureCollections zurueckgegeben statt eines Fehlers.
    """
    features = carpathian_points_geojson.get("features", [])
    warnings = []

    if len(features) < 2:
        warnings.append(f"Nur {len(features)} echte(r) Punkt(e) an diesem Tag - "
                         f"mindestens 2 fuer einen Schritt noetig.")
        return {
            "real": {"type": "FeatureCollection", "features": []},
            "alternative": {"type": "FeatureCollection", "features": []},
            "warnings": warnings,
        }

    def _ts_key(f):
        return f["properties"].get("timestamp", "")

    sorted_features = sorted(features, key=_ts_key)

    traj_points = []
    for f in sorted_features:
        props = f["properties"]
        ts_raw = props.get("timestamp")
        try:
            t = datetime.strptime(str(ts_raw), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # Fallback fuer ggf. abweichendes Format (z.B. mit Millisekunden/ISO-T)
            t = datetime.fromisoformat(str(ts_raw).replace("Z", ""))
        lng, lat = f["geometry"]["coordinates"]
        traj_points.append(TrajectoryPoint(t, lat, lng))

    first_props = sorted_features[0]["properties"]
    gender = _normalize_gender(first_props.get("sex", "F"))
    age = _normalize_age(first_props.get("age", "A"))
    bear_id = first_props.get("bear_id")

    segment = TrajectorySegment(bear_id=bear_id, gender=gender, age=age, segment=traj_points)
    # Kalender-Saison direkt aus dem Datum (Fabians eigene Logik) - NICHT
    # das biologische Carpathian-Saisonlabel, das nicht zu bear_speeds passt.
    segment.season = BearSeasons().get_season(traj_points[0].time)

    dbcon = DatabaseConnection(_SIM_DB_PATH)
    bear_speeds = BearSpeeds(dbcon)
    alternatives_per_step = _generate_alternative_steps(
        segment, bear_speeds, num_alternatives=num_alternatives, perception_distance=perception_distance,
    )

    if not alternatives_per_step:
        warnings.append(
            "Keine Alternativen erzeugt - vermutlich fehlen Geschwindigkeitsdaten "
            f"(bear_speeds) fuer Saison '{segment.season}', Geschlecht '{gender}', Alter '{age}'."
        )

    real_features = []
    alt_features = []

    for step_idx, alt_steps in enumerate(alternatives_per_step):
        step_time = traj_points[step_idx].time  # Start-Zeitpunkt DIESES Schritts
        for alt in alt_steps:
            lat, lng = alt["end"]
            feat = {
                "type": "Feature",
                "properties": {
                    "type": "real" if alt["real"] else "alternative",
                    "timestamp": step_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "step_index": step_idx,
                    "bear_id": bear_id,
                },
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
            }
            (real_features if alt["real"] else alt_features).append(feat)

    return {
        "real": {"type": "FeatureCollection", "features": real_features},
        "alternative": {"type": "FeatureCollection", "features": alt_features},
        "warnings": warnings,
    }
