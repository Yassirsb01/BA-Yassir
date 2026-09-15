"""
japan_comparison.py
=====================
Vergleichsexperiment (Basisversion, siehe Meeting mit Prof. Duennweber
21.08.2026): Simuliert einen Baerenpfad ab einem echten japanischen
Kamerastandort mit Fabians Bewegungsmodell (empirische Schrittlaengen aus
den rumaenischen Carpathian-Daten) und prueft, ob der simulierte Pfad
zeitlich/raeumlich zu echten Fotoausloesungen an anderen japanischen
Kameras passt.

WICHTIGE EINSCHRAENKUNGEN (bewusst, siehe Recherche-Ergebnis):
  - Artunterschied: Die Japan-Kameras (Fukushima-Region, Honshu) liegen im
    Verbreitungsgebiet des Asiatischen Schwarzbaeren (Ursus thibetanus),
    die Carpathian-Trainingsdaten stammen vom Europaeischen Braunbaeren
    (Ursus arctos). Bewusste methodische Vereinfachung, keine 1:1-Uebertragung.
  - Basisversion OHNE Gelaende-Gewichtung: reiner (unkorrelierter) Random
    Walk mit empirischer, stundenabhaengiger Schrittlaenge - keine
    Praeferenz fuer Wald/gegen Strassen o.ae. Das ist der naechste
    Ausbauschritt (TerrainFeatureSet anschliessen, siehe Punkt 2/3).
  - Nur EIN simulierter Lauf pro Aufruf (Zufallskomponente!). Fuer eine
    belastbare Aussage braeuchte es viele Wiederholungen (Monte-Carlo-Stil),
    nicht nur einen einzelnen Pfad - hier bewusst einfach gehalten als
    erster Plausibilitaets-Check, keine strenge Validierung.

Datenquellen:
  - Kamerastandorte: bear_simulation/bearsimulation-master/2024Bear/ReadMe.csv
    (echte GPS-Koordinaten der japanischen Geraete)
  - Geschwindigkeitsmodell: bear_simulation/bearsimulation-master/data/database.db
    (Tabelle bear_speeds, Quelle "Carpathians")
  - Echte Foto-Zeitstempel: MariaDB (image_metadata-Tabelle) ueber die
    bestehende WildlifeDatabase-Klasse - braucht OTH-VPN wie die anderen
    MariaDB-Systeme.
"""

import csv
import math
import os
import random
import sys
from datetime import datetime, timedelta

# Pfade zu Fabians Original-Code (bear_simulation/bearsimulation-master/...)
_BASE = os.path.join(os.path.dirname(__file__), "bear_simulation")
for _p in (_BASE, os.path.join(_BASE, "model"), os.path.join(_BASE, "data"), os.path.join(_BASE, "util")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from data.DatabaseConnection import DatabaseConnection  # noqa: E402
from data.BearSpeeds import BearSpeeds                   # noqa: E402
from GeoToolBox import GeoToolBox                         # noqa: E402
from geopy.distance import geodesic                       # noqa: E402

from wildlife_db_mariadb import WildlifeDatabase           # noqa: E402
from terrain_cache import TerrainCache                      # noqa: E402

CAMERAS_CSV = os.path.join(_BASE, "2024Bear", "ReadMe.csv")
SIM_DB_PATH = os.path.join(_BASE, "data", "database.db")

# Echte Werte aus database.db (bear_speeds), NICHT geraten:
VALID_GENDERS = ("M", "F")
VALID_AGES = ("J", "A")   # Juvenil / Adult
VALID_SEASONS = ("spring", "summer", "autumn", "winter")
SIM_SOURCE = "Carpathians"


def _normalize_device_id(raw_id: str) -> str:
    """
    Gleiche Normalisierung wie format_device_id() in japan_deterrents.py:
    Geraete-IDs werden im Rest des Projekts als 6-stellige Zahl mit
    fuehrenden Nullen gespeichert (z.B. "3002.0" aus der CSV -> "003002" in
    der DB, passend zu Ordnernamen wie 003002/ im ZIP). Ohne diese
    Normalisierung findet die DB-Abfrage nie einen Treffer.
    """
    raw_id = str(raw_id).strip()
    try:
        as_float = float(raw_id)
        if as_float == int(as_float):
            return f"{int(as_float):06d}"
    except ValueError:
        pass
    if raw_id.isdigit() and len(raw_id) < 6:
        return raw_id.zfill(6)
    return raw_id


def load_japan_cameras(csv_path: str = CAMERAS_CSV) -> list[dict]:
    """Laedt die echten Kamera-/Geraetestandorte aus 2024Bear/ReadMe.csv."""
    cameras = []
    if not os.path.exists(csv_path):
        print(f"[Warnung] Kamera-CSV nicht gefunden: {csv_path}")
        return cameras

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lat = float(row["DD-Latitude"])
                lng = float(row["DD-Longitude"])
            except (KeyError, ValueError, TypeError):
                continue
            raw_device_id = (row.get("Directory name") or "").strip()
            if not raw_device_id:
                continue
            device_id = _normalize_device_id(raw_device_id)
            cameras.append({"device_id": device_id, "lat": lat, "lng": lng})
    return cameras


# Praeferenzgewichte fuer die Gelaende-gewichtete Richtungswahl.
# Positiv = bevorzugt, negativ = gemieden, fehlend = neutral (0).
# Bewusst grob/einfach gehalten (keine echte iSSF mit gefitteten
# Koeffizienten, siehe Recherche-Ergebnis zu amt/iSSF) - eine einfache,
# nachvollziehbare Annaeherung als naechster Ausbauschritt nach der
# reinen Zufallsrichtung.
TERRAIN_PREFERENCE = {
    "forest": 3, "wood": 3, "scrub": 2, "grassland": 1, "nature_reserve": 3,
    "wetland": 1, "meadow": 1, "tree": 1, "tree_row": 1,
    "highway": -3, "motorway": -4, "primary": -3, "secondary": -2, "tertiary": -1,
    "residential": -3, "commercial": -3, "industrial": -3, "military": -4,
    "railway": -2, "city": -3, "town": -3, "village": -2, "suburb": -2,
}

# Wie stark ein Schritt bevorzugt in etwa dieselbe Richtung wie der
# vorherige geht (= "Richtungstraegheit", korrelierter Random Walk). Auf
# derselben Groessenordnung wie TERRAIN_PREFERENCE gehalten, damit sich
# beide Signale sinnvoll die Waage halten koennen.
DEFAULT_PERSISTENCE_WEIGHT = 2.5


def _score_terrain(features: dict) -> float:
    """Bewertet ein Gelaende-Feature-Dict anhand von TERRAIN_PREFERENCE."""
    return sum(weight for key, weight in TERRAIN_PREFERENCE.items() if features.get(key))


def _angular_diff_deg(a: float, b: float) -> float:
    """Kleinster Winkel zwischen zwei Richtungen (0-180 Grad)."""
    d = abs(a - b) % 360
    return d if d <= 180 else 360 - d


def choose_weighted_direction(
    current: tuple[float, float],
    step_length_m: float,
    rng: random.Random,
    terrain_cache: "TerrainCache | None" = None,
    prev_direction: float | None = None,
    persistence_weight: float = DEFAULT_PERSISTENCE_WEIGHT,
    num_candidates: int = 8,
    query_radius_m: int = 150,
) -> tuple[tuple[float, float], float]:
    """
    Waehlt die naechste Richtung gewichtet nach ZWEI ggf. kombinierten Signalen
    (statt komplett zufaellig):

      1. Gelaende-Praeferenz (siehe TERRAIN_PREFERENCE) - falls terrain_cache
         angegeben ist. Macht den Pfad landschaftlich plausibler (Wald statt
         Strasse/Siedlung).
      2. Richtungstraegheit (correlated random walk) - falls prev_direction
         angegeben ist. Kandidaten nah an der vorherigen Richtung werden
         bevorzugt, echte Kehrtwenden abgewertet. Macht den Pfad zu einer
         erkennbaren Wanderbewegung statt eines Zitterns auf der Stelle
         (genau das Problem, das bei reinem Wuerfeln jeden Schritt neu
         auftrat - der Baer "hing" oft nahe seines Startpunkts fest).

    Beide Signale sind unabhaengig optional und werden additiv kombiniert,
    falls beide vorhanden sind. Die Auswahl bleibt danach weiterhin
    gewichtet-zufaellig (kein striktes Maximum) - sonst waere es kein Random
    Walk mehr, sondern ein deterministischer Pfad.

    Returns:
        (destination, chosen_direction_deg) - die Richtung wird
        zurueckgegeben, damit der naechste Aufruf sie als prev_direction
        nutzen kann.
    """
    candidates = []
    for i in range(num_candidates):
        base_angle = (360.0 / num_candidates) * i
        direction = (base_angle + rng.uniform(-15, 15)) % 360

        score = 0.0
        if terrain_cache is not None:
            dest = GeoToolBox.destination_point(current, direction, step_length_m)
            features = terrain_cache.get_features(dest[0], dest[1], radius=query_radius_m)
            score += _score_terrain(features)
        else:
            dest = GeoToolBox.destination_point(current, direction, step_length_m)

        if prev_direction is not None:
            angle_diff = _angular_diff_deg(direction, prev_direction)
            # cos(0)=1 (gleiche Richtung, voller Bonus) ... cos(180)=-1 (Kehrtwende, voller Abzug)
            score += persistence_weight * math.cos(math.radians(angle_diff))

        candidates.append((dest, direction, score))

    scores = [c[2] for c in candidates]
    shifted = [s - min(scores) + 0.5 for s in scores]  # alle positiv, keiner exakt 0
    total = sum(shifted)
    weights = [s / total for s in shifted]

    chosen_dest, chosen_direction, _ = rng.choices(candidates, weights=weights, k=1)[0]
    return chosen_dest, chosen_direction


def simulate_free_path(
    start_lat: float,
    start_lng: float,
    start_time: datetime,
    duration_hours: int,
    gender: str,
    age: str,
    season: str,
    bear_speeds: "BearSpeeds",
    source: str = SIM_SOURCE,
    seed: int | None = None,
    terrain_cache: "TerrainCache | None" = None,
    use_directional_persistence: bool = True,
    persistence_weight: float = DEFAULT_PERSISTENCE_WEIGHT,
) -> list[dict]:
    """
    Simuliert einen Pfad ab einem freien Startpunkt, Stunde fuer Stunde.

    Nutzt bewusst dieselbe Konvention wie Fabians generate_alternative_steps():
    der Wert aus bear_speeds ist bereits die typische Schrittweite in km
    fuer diese Stunde/Saison/Alter/Geschlecht (kein zusaetzliches *Zeit).

    Args:
        terrain_cache: Falls angegeben, wird bei jedem Schritt die Richtung
            zusaetzlich gelaende-gewichtet gewaehlt (Wald bevorzugt) - macht
            die Basisversion realistischer, braucht aber (gecachte)
            Overpass-Abfragen.
        use_directional_persistence: Ob die Richtung von Schritt zu Schritt
            traege bleibt (korrelierter Random Walk) statt jedes Mal komplett
            neu zu wuerfeln. Standardmaessig an, weil eine rein zufaellige
            Neuwahl jeden Schritt dazu fuehrt, dass der simulierte Baer
            effektiv auf der Stelle "zittert" statt sich glaubwuerdig
            fortzubewegen.

    Returns:
        Liste von {"time": datetime, "lat": float, "lng": float}
    """
    if gender not in VALID_GENDERS or age not in VALID_AGES or season not in VALID_SEASONS:
        raise ValueError(
            f"Ungueltige Kombination gender={gender!r} age={age!r} season={season!r}. "
            f"Erlaubt: gender in {VALID_GENDERS}, age in {VALID_AGES}, season in {VALID_SEASONS}"
        )

    rng = random.Random(seed)

    path = [{"time": start_time, "lat": start_lat, "lng": start_lng}]
    current = (start_lat, start_lng)
    current_time = start_time
    prev_direction: float | None = None  # noch keine Vorgeschichte beim ersten Schritt

    for _ in range(int(duration_hours)):
        hour = current_time.hour
        median_speed_kmh = bear_speeds.get_median_speed_for_type_and_time(
            gender, age, season, hour, source
        )
        current_time += timedelta(hours=1)

        if median_speed_kmh is None:
            # Keine Daten fuer diese Stunde -> Position haelt (kein Schritt),
            # Zeit laeuft trotzdem weiter. Richtung bleibt fuer den naechsten
            # tatsaechlichen Schritt erhalten (kein Bruch der Traegheit).
            path.append({"time": current_time, "lat": current[0], "lng": current[1]})
            continue

        step_length_m = median_speed_kmh * 1000

        if terrain_cache is not None or use_directional_persistence:
            current, prev_direction = choose_weighted_direction(
                current, step_length_m, rng,
                terrain_cache=terrain_cache,
                prev_direction=prev_direction if use_directional_persistence else None,
                persistence_weight=persistence_weight,
            )
        else:
            direction_deg = rng.uniform(0, 360)  # komplett zufaellig (alte Basisversion)
            current = GeoToolBox.destination_point(current, direction_deg, step_length_m)
            prev_direction = direction_deg

        path.append({"time": current_time, "lat": current[0], "lng": current[1]})

    return path


# Bekannte Platzhalter-Geraete-IDs (fehlgeschlagene Erkennung beim
# E-Mail-Import) - siehe check_japan_data.py / activity_overlap.py.
PLACEHOLDER_DEVICE_IDS = {"199999", "999999"}


def get_real_events_for_camera(db: "WildlifeDatabase", device_id: str) -> list[datetime]:
    """
    Volle Zeitstempel (nicht nur Stunden) aller echten Fotos AN EINER
    BESTIMMTEN Kamera - aus bears_images_unified (Dateisystem + E-Mail
    zusammen, vollstaendiger als die aeltere image_metadata-Tabelle).

    Wird gebraucht, um (a) einen echten Startzeitpunkt fuer die Simulation
    auszuwaehlen und (b) echte Ausloesezeiten zum Vergleich auf der
    Animations-Zeitleiste einzuzeichnen.
    """
    if device_id in PLACEHOLDER_DEVICE_IDS:
        return []
    rows = db.execute_query(
        "SELECT timestamp FROM bears_images_unified WHERE device_id = %s AND timestamp IS NOT NULL",
        [device_id],
    )
    events = []
    for r in rows or []:
        ts = r.get("timestamp")
        try:
            dt = ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts))
            events.append(dt)
        except (ValueError, TypeError):
            continue
    return sorted(events)


def simulate_multiple_bears_from_sighting(
    start_lat: float,
    start_lng: float,
    start_time: datetime,
    n_bears: int,
    duration_hours: int,
    bear_speeds: "BearSpeeds",
    seed: int = 42,
    terrain_cache: "TerrainCache | None" = None,
    use_directional_persistence: bool = True,
) -> list[dict]:
    """
    Simuliert N unabhaengige Baeren, die alle an DERSELBEN echten Foto-
    Position und -Uhrzeit "starten" (so, als waere das der Moment einer
    echten Sichtung) - jeder mit zufaelligem Geschlecht/Alter/Saison, um
    ueber die unbekannte Demografie zu mitteln, und jeder mit eigenem Zufalls-
    Seed, damit sich die Pfade sichtbar unterscheiden.

    Returns:
        Liste von {"bear_index": int, "gender", "age", "season", "path": [...]}
    """
    rng = random.Random(seed)
    bears = []
    for i in range(n_bears):
        gender = VALID_GENDERS[rng.randrange(len(VALID_GENDERS))]
        age = VALID_AGES[rng.randrange(len(VALID_AGES))]
        season = VALID_SEASONS[rng.randrange(len(VALID_SEASONS))]
        bear_seed = rng.randrange(10_000_000)

        path = simulate_free_path(
            start_lat=start_lat, start_lng=start_lng, start_time=start_time,
            duration_hours=duration_hours, gender=gender, age=age, season=season,
            bear_speeds=bear_speeds, seed=bear_seed, terrain_cache=terrain_cache,
            use_directional_persistence=use_directional_persistence,
        )
        bears.append({"bear_index": i, "gender": gender, "age": age, "season": season, "path": path})
    return bears


def check_db_reachable(db: "WildlifeDatabase") -> bool:
    """
    Explizite, einmalige Verbindungspruefung. Noetig, weil WildlifeDatabase
    Verbindungsfehler bereits intern abfaengt (druckt nur eine Fehlermeldung,
    wirft aber keine Exception) - ein try/except um get_images() wuerde den
    Fehler also NICHT erkennen.
    """
    try:
        conn = db._get_connection()
        conn.close()
        return True
    except Exception:
        return False
def get_real_photo_hours(db: "WildlifeDatabase", device_id: str) -> list[int]:
    """
    Holt die Uhrzeiten (0-23), zu denen an einer echten Kamera tatsaechlich
    Fotos ausgeloest wurden (MariaDB, ueber die bestehende get_images-Methode).

    Vorausgesetzt wird, dass die DB-Erreichbarkeit bereits vorab per
    check_db_reachable() geprueft wurde - diese Funktion geht also von einer
    stehenden Verbindung aus und liefert bei genuinem Fehlen von Fotos
    einfach eine leere Liste (nicht mehr zu verwechseln mit "DB down").
    """
    images = db.get_images(device_id=device_id, limit=10000)
    records = images.to_dict("records") if hasattr(images, "to_dict") else (images or [])

    hours = []
    for img in records:
        ts = img.get("timestamp")
        if not ts:
            continue
        try:
            dt = ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts))
            hours.append(dt.hour)
        except (ValueError, TypeError):
            continue
    return hours


def compare_to_real_cameras(
    simulated_path: list[dict],
    cameras: list[dict],
    db: "WildlifeDatabase",
    db_reachable: bool,
    proximity_m: float = 200,
    hour_tolerance: int = 2,
) -> list[dict]:
    """
    Prueft fuer jeden simulierten Wegpunkt, ob eine echte Kamera in der Naehe
    liegt (< proximity_m) UND ob zu einer aehnlichen Uhrzeit (+/- hour_tolerance)
    tatsaechlich Fotos an dieser Kamera ausgeloest wurden.

    db_reachable muss vorab per check_db_reachable() geprueft worden sein -
    wenn False, wird gar nicht erst versucht zu queryen (sonst haengt sich
    das Skript ggf. an mehreren Timeouts auf).
    """
    hits = []
    photo_hours_cache: dict[str, list[int]] = {}

    for point in simulated_path:
        sim_point = (point["lat"], point["lng"])
        for cam in cameras:
            dist_m = geodesic(sim_point, (cam["lat"], cam["lng"])).meters
            if dist_m > proximity_m:
                continue

            device_id = cam["device_id"]
            real_hours: list[int] = []
            if db_reachable:
                if device_id not in photo_hours_cache:
                    photo_hours_cache[device_id] = get_real_photo_hours(db, device_id)
                real_hours = photo_hours_cache[device_id]

            sim_hour = point["time"].hour
            time_match = db_reachable and any(
                min(abs(sim_hour - h), 24 - abs(sim_hour - h)) <= hour_tolerance
                for h in real_hours
            )

            hits.append({
                "sim_time": point["time"],
                "sim_lat": point["lat"],
                "sim_lng": point["lng"],
                "device_id": device_id,
                "distance_m": round(dist_m, 1),
                "time_match": time_match,
                "query_ok": db_reachable,
                "real_photo_hours_at_camera": sorted(set(real_hours)),
            })

    return hits


def run_experiment(
    gender: str = "F",
    age: str = "A",
    season: str = "summer",
    duration_hours: int = 24,
    start_time: datetime | None = None,
    start_camera_index: int = 0,
    proximity_m: float = 200,
    hour_tolerance: int = 2,
    seed: int | None = 42,
    use_terrain: bool = False,
) -> dict:
    """
    Kompletter Durchlauf: laden -> simulieren -> abgleichen -> Ergebnis.

    use_terrain=True: Richtung wird gelaende-gewichtet gewaehlt (siehe
    choose_weighted_direction), braucht Internetzugang beim ersten
    Mal pro Rasterfeld (danach lokal gecacht in terrain_cache.db).
    use_terrain=False (Standard): reine Zufallsrichtung, keine Overpass-
    Abfragen noetig - schneller, aber die "blinde" Basisversion.
    """
    cameras = load_japan_cameras()
    if not cameras:
        return {"error": "Keine Japan-Kamerastandorte gefunden (2024Bear/ReadMe.csv fehlt?)."}

    start_camera_index = max(0, min(start_camera_index, len(cameras) - 1))
    start_cam = cameras[start_camera_index]

    dbcon = DatabaseConnection(SIM_DB_PATH)
    bear_speeds = BearSpeeds(dbcon)

    if start_time is None:
        start_time = datetime(2024, 6, 1, 6, 0, 0)

    terrain_cache = TerrainCache() if use_terrain else None

    path = simulate_free_path(
        start_lat=start_cam["lat"], start_lng=start_cam["lng"],
        start_time=start_time, duration_hours=duration_hours,
        gender=gender, age=age, season=season,
        bear_speeds=bear_speeds, seed=seed,
        terrain_cache=terrain_cache,
    )

    result = {
        "start_camera": start_cam,
        "path": path,
        "hits": [],
        "db_available": False,
    }

    try:
        db = WildlifeDatabase()
        db_reachable = check_db_reachable(db)
        result["db_available"] = db_reachable
        if not db_reachable:
            print("  [Hinweis] MariaDB nicht erreichbar (VPN aktiv?) - "
                  "Zeit-Abgleich wird uebersprungen, simulierter Pfad bleibt aber gueltig.")
        result["hits"] = compare_to_real_cameras(
            path, cameras, db, db_reachable=db_reachable,
            proximity_m=proximity_m, hour_tolerance=hour_tolerance,
        )
    except Exception as e:
        result["db_error"] = str(e)

    return result


if __name__ == "__main__":
    use_terrain = "--terrain" in sys.argv

    print("=" * 70)
    if use_terrain:
        print("Japan-Vergleichsexperiment (mit Gelaende-Gewichtung, lokal gecacht)")
    else:
        print("Japan-Vergleichsexperiment (Basisversion, ohne Gelaende-Gewichtung)")
    print("=" * 70)

    res = run_experiment(use_terrain=use_terrain)

    if "error" in res:
        print(res["error"])
        sys.exit(1)

    cam = res["start_camera"]
    print(f"\nStartpunkt: Kamera {cam['device_id']} bei {cam['lat']:.5f}, {cam['lng']:.5f}")
    print(f"Simulierter Pfad: {len(res['path'])} Punkte")
    print(f"  Erster Punkt:  {res['path'][0]}")
    print(f"  Letzter Punkt: {res['path'][-1]}")

    if not res["db_available"]:
        print(f"\n[Hinweis] DB-Abgleich nicht moeglich (VPN aktiv?): "
              f"{res.get('db_error', 'Verbindung fehlgeschlagen')}")
        print("Der simulierte Pfad selbst wurde trotzdem erfolgreich erzeugt.")
        print(f"\n{len(res['hits'])} raeumliche Annaeherung(en) an Kameras gefunden "
              f"(< 200m, ohne Zeit-Abgleich):")
        for h in res["hits"]:
            print(f"  {h['sim_time']} -> Kamera {h['device_id']} ({h['distance_m']}m entfernt)")
    else:
        hits = res["hits"]
        print(f"\n{len(hits)} Annaeherung(en) an japanische Kameras gefunden (< 200m):")
        for h in hits:
            match_str = "JA" if h["time_match"] else "nein"
            print(f"  {h['sim_time']} -> Kamera {h['device_id']} "
                  f"({h['distance_m']}m entfernt) | Zeit passt zu echten Fotos: {match_str} "
                  f"(echte Foto-Stunden dort: {h['real_photo_hours_at_camera']})")
        if not hits:
            print("  Keine Annaeherungen - Kameras liegen vermutlich zu weit auseinander "
                  "fuer einen 24h-Radius. Laengere Simulationsdauer oder anderen "
                  "Startpunkt probieren.")