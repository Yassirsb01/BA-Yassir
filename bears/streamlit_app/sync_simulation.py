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

Zwei Ausgabeformen der Simulation (beide gleichzeitig nutzbar):

  1. FÄCHER ("alternative"): an jedem echten Schritt alle N Kandidaten,
     die das Modell dort erzeugt hat. Zeigt den Möglichkeitsraum EINES
     Schritts, ergibt aber keinen Pfad.

  2. REALISIERUNGEN ("simulated", neu): durchgehende Pfade, die entstehen,
     wenn man Schritt für Schritt einen Kandidaten zieht und ihn auf die
     jeweils aktuelle simulierte Position anwendet. Erst damit gibt es
     einen zweiten Bären, der neben dem echten mitlaufen kann - die
     eigentliche Protokoll-Anforderung ("Bewegungen echter UND simulierter
     Bären"). Jede Realisierung ist EIN möglicher Modelllauf, KEINE
     Vorhersage; Details und Begründung in _build_simulated_realizations().

Abweichungen von Fabians Originalcode sind in ANPASSUNGEN.md gesammelt.

Wichtiger Hinweis zur Saison: Carpathian nutzt biologische Saisonlabel
("Forest fruits", "Hyperphagia", ...), Fabians Geschwindigkeitstabelle
(bear_speeds) braucht Kalender-Saisons ("spring"/"summer"/"autumn"/
"winter"). Die Saison wird deshalb NICHT aus den Carpathian-Properties
übernommen, sondern direkt aus dem Datum abgeleitet - mit Fabians eigener
BearSeasons-Klasse (gleicher Code, den auch StepTrajectorySet nutzt).
"""

import math
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

# --- Parameter der simulierten Trajektorie (siehe Modul-Docstring, Punkt 2) ---

# Empirisch gemessene Richtungstreue der ECHTEN Carpathian-Baeren.
#
# Gemessen an 1_bears_RO.csv (13 Baeren, 59997 Punkte) ueber alle Paare
# aufeinanderfolgender 1-Stunden-Schritte (n = 46161): der Drehwinkel
# zwischen zwei Schritten, aufgeschluesselt nach Schrittlaenge. Angegeben
# ist der Mittelwert von cos(Drehwinkel) - 0 bedeutet richtungslos,
# +1 schnurgerade, negative Werte ein Hin-und-Her.
#
#   Schrittlaenge      n      mittleres cos    Median-Drehwinkel
#      < 25 m       24058        -0.202            114 Grad
#     25 -  50 m     5876        -0.122            106 Grad
#     50 - 100 m     4545        +0.106             75 Grad
#    100 - 200 m     4529        +0.251             62 Grad
#    200 - 500 m     4634        +0.414             47 Grad
#      > 500 m       2519        +0.588             36 Grad
#
# WARUM DAS WICHTIG IST: Ueber alle Schritte gemittelt ergibt sich
# cos = -0.012, also scheinbar voellig richtungsloses Umherlaufen. Das ist
# aber eine Mischung aus zwei GEGENSAETZLICHEN Zustaenden - der Baer frisst
# bzw. ruht kleinraeumig (kurze Schritte, ausgepraegtes Hin-und-Her) oder
# er wandert zielgerichtet (lange Schritte, deutlich geradeaus). Ein
# einzelner, fester Traegheitsparameter kann beides nicht abbilden: zu
# klein gewaehlt zittert der simulierte Baer auch beim Wandern auf der
# Stelle, zu gross gewaehlt marschiert er auch beim Fressen schnurgerade
# davon. Die Kandidatenauswahl wird deshalb pro Schritt anhand der fuer
# diesen Schritt erwarteten Laenge gewichtet.
#
# Hinweis fuer die Bewertung: Bei sehr kurzen Schritten (Median aller
# Schritte 22,7 m) liegt die GPS-Ungenauigkeit in derselben
# Groessenordnung wie der Schritt selbst. Ein Teil des gemessenen
# Hin-und-Her duerfte daher Messrauschen und nicht Verhalten sein - die
# negativen Werte sind also eher eine Obergrenze der Tortuositaet.
EMPIRICAL_TURN_PERSISTENCE = [
    (15.0, -0.202), (35.0, -0.122), (70.0, 0.106),
    (140.0, 0.251), (320.0, 0.414), (800.0, 0.588),
]

# Fester Traegheitswert fuer persistence_mode="fixed" - derselbe Wert wie
# DEFAULT_PERSISTENCE_WEIGHT in japan_comparison.py. Dort ist er noetig,
# weil ohne echte Route gar kein Bezugspunkt existiert; hier dient er nur
# noch dem Vergleich (siehe ANPASSUNGEN.md).
DEFAULT_PERSISTENCE_WEIGHT = 2.5

# Wie viele unabhaengige Realisierungen standardmaessig erzeugt werden.
# Bewusst > 1: eine einzelne Linie wuerde wie eine Vorhersage aussehen,
# mehrere auseinanderlaufende Linien zeigen sofort, dass es sich um
# Zufallsziehungen aus demselben Modell handelt.
DEFAULT_REALIZATIONS = 3


def _generate_alternative_steps(segment, bear_speeds, num_alternatives=10, perception_distance=200,
                                rng=None, scale_to_interval=True):
    """
    Direkte Neuimplementierung von StepSelectionModel.generate_alternative_steps()
    (identische Logik, siehe model/StepSelectionModel.py) - bewusst OHNE den Import
    von StepSelectionModel selbst, weil dessen __init__ ueber StepTrajectorySet ->
    SeasonalTrajectoryProcessor -> ClusterCalculator -> Hdbscan eine schwere,
    fuer diesen Anwendungsfall unnoetige Cluster-Analyse-Kette mitzieht (und das
    'hdbscan'-Paket braucht, das hier evtl. nicht installiert ist - vermutlich der
    Grund, warum die Simulation bisher im Fallback-Modus lief). Fuer die eigentliche
    Schritt-Generierung wird nur BearSpeeds + GeoToolBox gebraucht, siehe unten.

    Zwei Abweichungen vom Original (beide bewusst, siehe ANPASSUNGEN.md):

    rng: eigener Zufallsgenerator statt des globalen random-Moduls. Nur so
        ist ein Lauf reproduzierbar - noetig, damit ein Screenshot in der
        Bachelorarbeit spaeter exakt wiederherstellbar ist.

    scale_to_interval: Die Schrittlaenge des Originals ist
        median_speed_kmh * 1000, also die Strecke einer STUNDE. Die
        Carpathian-GPS-Fixes liegen aber nur zu rund 80 % eine Stunde
        auseinander, zu 13 % zwei Stunden und zu 7 % noch weiter (gemessen
        an 1_bears_RO.csv, 59997 Punkte). Bei einer Zweistundenluecke waren
        die Alternativen damit nur halb so lang wie der echte Schritt - der
        Faecher war dort systematisch zu klein und eine daraus gebaute
        Trajektorie blieb zwangslaeufig hinter dem echten Baeren zurueck.
        Mit scale_to_interval=True wird die Laenge mit der tatsaechlich
        verstrichenen Zeit skaliert. scale_to_interval=False stellt das
        urspruengliche Verhalten wieder her.
    """
    rng = rng or random
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

        # Dauer DIESES Schritts in Stunden (siehe scale_to_interval oben)
        dt_hours = (end.time - start.time).total_seconds() / 3600.0
        factor = dt_hours if (scale_to_interval and dt_hours > 0) else 1.0

        step_length_m = median_speed_kmh * 1000 * factor
        start_point = (start.lat, start.lon)
        end_point = (end.lat, end.lon)
        real_direction = GeoToolBox.calculate_direction(start_point, end_point)

        alt_steps = []
        for _ in range(num_alternatives):
            angle_offset = rng.uniform(0, 360)
            alt_direction = (real_direction + angle_offset) % 360
            alt_endpoint = GeoToolBox.destination_point(start_point, alt_direction, step_length_m)
            perception_point = GeoToolBox.destination_point(start_point, alt_direction, perception_distance)
            alt_steps.append({
                "start": start_point, "end": alt_endpoint, "perception_point": perception_point,
                "angle": alt_direction, "length": step_length_m, "real": False,
                "dt_hours": dt_hours,
            })

        perception_real = GeoToolBox.destination_point(start_point, real_direction, perception_distance)
        alt_steps.append({
            "start": start_point, "end": end_point, "perception_point": perception_real,
            "angle": real_direction, "length": geodesic(start_point, end_point).meters, "real": True,
            "dt_hours": dt_hours,
        })

        alternatives_per_step.append(alt_steps)

    return alternatives_per_step


def _angular_diff_deg(a: float, b: float) -> float:
    """Kleinster Winkel zwischen zwei Richtungen (0-180 Grad)."""
    d = abs(a - b) % 360
    return d if d <= 180 else 360 - d


def _mean_cos_for_step_length(step_length_m: float) -> float:
    """
    Erwartete Richtungstreue (mittleres cos des Drehwinkels) fuer einen
    Schritt dieser Laenge - lineare Interpolation zwischen den gemessenen
    Stuetzstellen in EMPIRICAL_TURN_PERSISTENCE, auf logarithmischer
    Laengenachse (die Stuetzstellen sind ungefaehr logarithmisch verteilt).
    Ausserhalb des gemessenen Bereichs wird der Randwert gehalten, statt zu
    extrapolieren.
    """
    pts = EMPIRICAL_TURN_PERSISTENCE
    if step_length_m <= pts[0][0]:
        return pts[0][1]
    if step_length_m >= pts[-1][0]:
        return pts[-1][1]
    x = math.log(max(step_length_m, 1e-6))
    for (l0, c0), (l1, c1) in zip(pts, pts[1:]):
        if l0 <= step_length_m <= l1:
            f = (x - math.log(l0)) / (math.log(l1) - math.log(l0))
            return c0 + (c1 - c0) * f
    return pts[-1][1]


def _kappa_from_mean_cos(rho: float) -> float:
    """
    Rechnet eine gewuenschte mittlere Richtungstreue rho in die
    Konzentration kappa einer von-Mises-Verteilung um.

    Hintergrund: Werden gleichverteilte Kandidatenrichtungen mit
    exp(kappa * cos(Drehwinkel)) gewichtet, ist das genau eine diskrete
    Naeherung der von-Mises-Verteilung - dem Standardmodell fuer
    Drehwinkel in der Bewegungsoekologie. Deren mittlere resultierende
    Laenge ist A(kappa) = I1(kappa)/I0(kappa); gesucht ist also die
    Umkehrung A^-1(rho). Verwendet wird die gaengige Naeherung nach
    Fisher (1993, "Statistical Analysis of Circular Data", Abschn. 4.5.5).

    Negative rho (kurze Schritte, Hin-und-Her) ergeben negative kappa -
    dann liegt das Gewichtsmaximum bei 180 Grad, also bei der Kehrtwende.
    Das ist genau das gemessene Verhalten und kein Sonderfall.
    """
    s = 1.0 if rho >= 0 else -1.0
    r = min(abs(rho), 0.99)
    if r < 0.53:
        k = 2 * r + r ** 3 + 5 * r ** 5 / 6
    elif r < 0.85:
        k = -0.4 + 1.39 * r + 0.43 / (1 - r)
    else:
        k = 1 / (r ** 3 - 4 * r ** 2 + 3 * r)
    return s * k


def _build_simulated_realizations(
    traj_points,
    alternatives_per_step,
    n_realizations: int = DEFAULT_REALIZATIONS,
    rng=None,
    persistence_mode: str = "empirical",
    persistence_weight: float = DEFAULT_PERSISTENCE_WEIGHT,
) -> list[list[dict]]:
    """
    Baut aus den Schritt-Kandidaten zusammenhaengende simulierte Pfade.

    WAS DAS IST - und was es NICHT ist:
    Jeder erzeugte Pfad ist EINE moegliche Realisierung des Bewegungsmodells,
    KEINE Vorhersage und keine Rekonstruktion dessen, was der Baer "eigentlich"
    getan hat. Bei erneutem Ziehen kommt ein anderer Pfad heraus. Genau
    deshalb werden standardmaessig MEHRERE Realisierungen erzeugt: eine
    einzelne Linie neben der echten Route wuerde unweigerlich als "das
    Modell sagt diesen Weg voraus" gelesen, mehrere auseinanderlaufende
    Linien zeigen den Zufallscharakter unmittelbar.

    Vorgehen pro Realisierung: Der simulierte Baer startet auf dem echten
    Startpunkt. Fuer jeden echten Schritt wird aus den Kandidaten DIESES
    Schritts einer gezogen; dessen Richtung und Laenge werden auf die
    AKTUELLE simulierte Position angewandt (nicht auf die echte - sonst
    entstuende kein durchgehender Pfad, sondern wieder nur ein Faecher).
    Die Zeitstempel werden unveraendert von der echten Route uebernommen,
    dadurch laufen beide Animationen zwangslaeufig synchron.

    Warum die Ziehung GEWICHTET erfolgt: Die Kandidatenrichtungen sind
    gleichverteilt (siehe _generate_alternative_steps: angle_offset ist
    uniform ueber 0-360 Grad). Eine ebenfalls gleichverteilte Ziehung
    ergaebe einen Pfad ohne jede Beziehung zum Drehverhalten echter
    Baeren. Stattdessen werden die Kandidaten mit exp(kappa * cos(Drehwinkel))
    gewichtet - eine diskrete von-Mises-Verteilung der Drehwinkel, dem
    Standardmodell der Bewegungsoekologie.

    persistence_mode steuert, woher kappa kommt:

      "empirical" (Standard): kappa wird pro Schritt aus der gemessenen
          Richtungstreue ECHTER Carpathian-Baeren bei DIESER Schrittlaenge
          abgeleitet (EMPIRICAL_TURN_PERSISTENCE + _kappa_from_mean_cos).
          Kurze Schritte werden dadurch tortuos wie beim Fressen, lange
          Schritte gerichtet wie beim Wandern. Kein frei gewaehlter
          Parameter - der Wert steht in den Daten.

      "fixed": ein einziger Traegheitswert fuer alle Schritte
          (persistence_weight), wie im Japan-Teil. Nur fuer den Vergleich
          gedacht; ueberzeichnet kurze Schritte deutlich.

      "off": gleichverteilte Ziehung, also unkorrelierter Random Walk.
          Entspricht dem urspruenglichen Verhalten ohne jede Gewichtung.

    Der echte Schritt bleibt bewusst Teil der Kandidatenmenge: In einer
    Step-Selection-Funktion ist er der "genutzte" unter den "verfuegbaren"
    Schritten. Ihn auszuschliessen wuerde die Simulation kuenstlich von der
    Realitaet wegdruecken.

    Returns:
        Liste von Realisierungen; jede ist eine Liste von
        {"time": datetime, "lat": float, "lng": float, "step_index": int}.
    """
    rng = rng or random
    if len(traj_points) < 2 or not alternatives_per_step:
        return []

    realizations = []
    for _ in range(max(1, n_realizations)):
        current = (traj_points[0].lat, traj_points[0].lon)
        prev_direction = None
        path = [{
            "time": traj_points[0].time, "lat": current[0], "lng": current[1], "step_index": 0,
        }]

        for step_idx, candidates in enumerate(alternatives_per_step):
            next_time = traj_points[step_idx + 1].time

            if not candidates:
                # Keine Geschwindigkeitsdaten fuer diese Stunde: Position
                # halten statt zu raten. Der Punkt wird trotzdem gesetzt,
                # damit die Zeitachse luckenlos zur echten Route passt.
                path.append({
                    "time": next_time, "lat": current[0], "lng": current[1],
                    "step_index": step_idx + 1,
                })
                continue

            if prev_direction is None or persistence_mode == "off":
                # Erster Schritt: es gibt noch keine vorherige Richtung,
                # auf die sich eine Drehung beziehen koennte.
                weights = [1.0] * len(candidates)
            else:
                if persistence_mode == "empirical":
                    # Erwartete Schrittlaenge dieses Schritts (die Kandidaten
                    # eines Schritts haben bis auf den echten dieselbe Laenge).
                    lengths = [c["length"] for c in candidates if not c.get("real")]
                    step_len = lengths[0] if lengths else candidates[0]["length"]
                    kappa = _kappa_from_mean_cos(_mean_cos_for_step_length(step_len))
                else:  # "fixed"
                    kappa = persistence_weight

                scores = [
                    kappa * math.cos(math.radians(
                        _angular_diff_deg(c["angle"], prev_direction)
                    ))
                    for c in candidates
                ]
                # Abzug des Maximums nur zur Zahlenstabilitaet - aendert die
                # relativen Wahrscheinlichkeiten nicht.
                max_score = max(scores)
                weights = [math.exp(s - max_score) for s in scores]

            chosen = rng.choices(candidates, weights=weights, k=1)[0]
            current = GeoToolBox.destination_point(current, chosen["angle"], chosen["length"])
            prev_direction = chosen["angle"]

            path.append({
                "time": next_time, "lat": current[0], "lng": current[1],
                "step_index": step_idx + 1,
            })

        realizations.append(path)

    return realizations


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
    n_realizations: int = DEFAULT_REALIZATIONS,
    seed: int | None = None,
    scale_to_interval: bool = True,
    persistence_mode: str = "empirical",
) -> dict:
    """
    Args:
        carpathian_points_geojson: das GeoJSON "points"-Objekt, das
            get_carpathian_geojson() für EINEN Bären an EINEM Tag liefert
            (properties: bear_id, timestamp, sex, age, ...).
        num_alternatives: wie viele Alternativ-Kandidaten pro echtem Schritt.
        perception_distance: siehe StepSelectionModel (Wahrnehmungsradius in m).
        n_realizations: wie viele durchgehende simulierte Pfade erzeugt
            werden (siehe _build_simulated_realizations). 0 schaltet sie ab.
        seed: fester Zufalls-Seed fuer reproduzierbare Laeufe. None = wie
            bisher zufaellig bei jedem Aufruf.
        scale_to_interval: Schrittlaenge an die tatsaechliche Dauer des
            GPS-Schritts anpassen (siehe _generate_alternative_steps).
        persistence_mode: "empirical" | "fixed" | "off" - wie die
            Drehwinkel der simulierten Pfade gewichtet werden, siehe
            _build_simulated_realizations().

    Returns:
        {
          "real": GeoJSON FeatureCollection (== die echten Punkte, nur
                  nochmal durch Fabians Modell bestaetigt/durchgereicht),
          "alternative": GeoJSON FeatureCollection, jede Alternative mit
                  properties.timestamp EXAKT auf den Start-Zeitpunkt ihres
                  zugehoerigen echten Schritts gesetzt (kein synthetischer,
                  unabhaengiger Zeitstrahl mehr noetig),
          "simulated": GeoJSON FeatureCollection der durchgehenden
                  simulierten Pfade - Punkte mit properties.realization
                  (0..n-1) und properties.timestamp, identisch zu den
                  Zeitstempeln der echten Route. Jede Realisierung ist EIN
                  moeglicher Modelllauf, keine Vorhersage.
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
            "simulated": {"type": "FeatureCollection", "features": []},
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

    # Ein gemeinsamer Zufallsgenerator fuer Faecher UND Realisierungen:
    # mit gesetztem Seed ist damit der komplette Lauf reproduzierbar.
    rng = random.Random(seed) if seed is not None else random

    dbcon = DatabaseConnection(_SIM_DB_PATH)
    bear_speeds = BearSpeeds(dbcon)
    alternatives_per_step = _generate_alternative_steps(
        segment, bear_speeds, num_alternatives=num_alternatives, perception_distance=perception_distance,
        rng=rng, scale_to_interval=scale_to_interval,
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

    # ------------------------------------------------------------------
    # Durchgehende simulierte Pfade (mitlaufender Baer, siehe Protokoll:
    # "Bewegungen echter UND simulierter Baeren")
    # ------------------------------------------------------------------
    sim_features = []
    if n_realizations > 0:
        realizations = _build_simulated_realizations(
            traj_points, alternatives_per_step, n_realizations=n_realizations, rng=rng,
            persistence_mode=persistence_mode,
        )
        n_stalled = 0
        for r_idx, path in enumerate(realizations):
            for p in path:
                sim_features.append({
                    "type": "Feature",
                    "properties": {
                        "type": "simulated",
                        "realization": r_idx,
                        "timestamp": p["time"].strftime("%Y-%m-%d %H:%M:%S"),
                        "step_index": p["step_index"],
                        "bear_id": bear_id,
                    },
                    "geometry": {"type": "Point", "coordinates": [p["lng"], p["lat"]]},
                })
        # Schritte ohne Geschwindigkeitsdaten: dort bleibt der simulierte
        # Baer stehen (siehe _build_simulated_realizations) - das soll der
        # Nutzer wissen, sonst wirkt eine Pause wie ein Verhaltensbefund.
        n_stalled = sum(1 for alt in alternatives_per_step if not alt)
        if n_stalled:
            warnings.append(
                f"Fuer {n_stalled} von {len(alternatives_per_step)} Schritten fehlen "
                "Geschwindigkeitsdaten - die simulierten Baeren bleiben dort stehen."
            )

    return {
        "real": {"type": "FeatureCollection", "features": real_features},
        "alternative": {"type": "FeatureCollection", "features": alt_features},
        "simulated": {"type": "FeatureCollection", "features": sim_features},
        "warnings": warnings,
    }
