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
# Gelaende-Bewertung, getrennt nach OSM-Tag UND Wert ("tag=wert").
#
# Warum tag-genau (Update 23.09.2026, nach Auswertung des echten
# vorab geladenen Gelaendes der Kameraregion): Die frueheren, rein
# wertbasierten Flags konnten zwei voellig verschiedene Dinge nicht
# unterscheiden - "landuse=residential" (Wohngebiet) und
# "highway=residential" (Wohnstrasse). In der laendlichen Kameraregion
# fuehrte das dazu, dass 51 % aller Rasterzellen als Siedlung galten,
# obwohl dort meist nur eine kleine Strasse durch Feld oder Wald laeuft.
# Ausserdem vergab die alte Tabelle pauschal "highway": -3 fuer JEDE
# Strasse - also auch fuer Waldwege und Fusspfade. Da 94 % der Zellen
# irgendeine Strasse enthalten, war praktisch das gesamte Gebiet negativ
# bewertet (Mittelwert -4,83; selbst Waldzellen lagen bei -2,09) und der
# Wald hob sich kaum noch ab.
TERRAIN_PREFERENCE_QUALIFIED = {
    # Deckung / bevorzugter Lebensraum
    "landuse=forest": 3.0, "natural=wood": 3.0, "leisure=nature_reserve": 3.0,
    "natural=scrub": 2.0, "natural=grassland": 1.0, "natural=wetland": 1.0,
    "landuse=meadow": 1.0, "natural=tree_row": 0.5, "landuse=orchard": 0.5,
    # Offenland: wenig Deckung, aber Nahrung -> nur leicht negativ
    "landuse=farmland": -0.5, "landuse=vineyard": 0.0,
    # Menschliche Nutzung (Flaechen)
    "landuse=residential": -3.0, "landuse=commercial": -3.0,
    "landuse=industrial": -3.0, "landuse=military": -4.0,
    "place=city": -3.0, "place=town": -3.0, "place=village": -2.0, "place=suburb": -2.0,
    # Strassen nach Klasse statt pauschal
    "highway=motorway": -4.0, "highway=trunk": -3.5, "highway=primary": -3.0,
    "highway=secondary": -2.0, "highway=tertiary": -1.0, "highway=residential": -1.5,
    "highway=unclassified": -0.5, "highway=service": -0.5,
    "highway=track": 0.0, "highway=path": 0.0, "highway=footway": 0.0,
    "railway=rail": -2.0,
}

# Rueckfall fuer aeltere Cache-Datenbanken ohne tag-genaue Schluessel:
# dieselbe Logik, so gut es ohne Tag-Kontext geht. "highway" pauschal ist
# hier bewusst NICHT mehr enthalten (siehe oben); "residential" ist
# mehrdeutig und daher nur schwach negativ gewichtet.
TERRAIN_PREFERENCE = {
    "forest": 3.0, "wood": 3.0, "nature_reserve": 3.0, "scrub": 2.0,
    "grassland": 1.0, "wetland": 1.0, "meadow": 1.0, "tree_row": 0.5,
    "farmland": -0.5,
    "motorway": -4.0, "trunk": -3.5, "primary": -3.0, "secondary": -2.0,
    "tertiary": -1.0, "unclassified": -0.5, "service": -0.5,
    "residential": -1.5, "commercial": -3.0, "industrial": -3.0, "military": -4.0,
    "city": -3.0, "town": -3.0, "village": -2.0, "suburb": -2.0, "railway": -2.0,
}

# Wie stark Bewertungsunterschiede die Richtungswahl beeinflussen.
# Auswahlwahrscheinlichkeit ~ exp(beta * Bewertung) - dieselbe
# exponentielle Form wie in Step-Selection-Funktionen ueblich. Vorher
# wurde linear gewichtet, wodurch der Unterschied zwischen Wald und
# Siedlung nur etwa Faktor 2-3 ausmachte und Baeren sichtbar in Doerfer
# hineinliefen. Mit beta=0.6 entspricht ein Bewertungsunterschied von 6
# Punkten (Wald vs. Wohngebiet) etwa Faktor 400. Empirisch am echten
# Gelaende der Kameraregion getestet (0.6 / 1.0 / 1.5): 1.0 senkt den
# Siedlungsanteil deutlich, ohne die Wahl faktisch deterministisch zu
# machen - was den Zufallscharakter des Modells zerstoeren wuerde.
SELECTION_BETA = 1.0

# Wie weit der Baer bei der Richtungswahl "vorausschaut" (Meter). Fabians
# StepSelectionModel nutzt denselben Wert als perception_distance.
# Noetig, weil die Schrittweiten (Median ~45 m/h) deutlich kleiner sind
# als die Rasterweite des Gelaendes (150 m): ohne Vorausschau landen alle
# Kandidatenrichtungen in derselben Rasterzelle, bekommen dieselbe
# Bewertung - und die Wahl waere wieder rein zufaellig.
DEFAULT_TERRAIN_PERCEPTION_M = 200

# Wie stark ein Schritt bevorzugt in etwa dieselbe Richtung wie der
# vorherige geht (= "Richtungstraegheit", korrelierter Random Walk). Auf
# derselben Groessenordnung wie TERRAIN_PREFERENCE gehalten, damit sich
# beide Signale sinnvoll die Waage halten koennen.
DEFAULT_PERSISTENCE_WEIGHT = 2.5


def _score_terrain(features: dict) -> float:
    """
    Bewertet ein Gelaende-Feature-Dict. Enthaelt es tag-genaue Schluessel
    ("landuse=forest"), wird die genauere Tabelle genutzt; aeltere Caches
    ohne Tag-Kontext fallen automatisch auf die wertbasierte Tabelle zurueck.
    """
    if any("=" in k for k in features):
        return sum(w for key, w in TERRAIN_PREFERENCE_QUALIFIED.items() if features.get(key))
    return sum(w for key, w in TERRAIN_PREFERENCE.items() if features.get(key))


def _angular_diff_deg(a: float, b: float) -> float:
    """Kleinster Winkel zwischen zwei Richtungen (0-180 Grad)."""
    d = abs(a - b) % 360
    return d if d <= 180 else 360 - d


# --- Cluster-basierte Richtungswahl nach Geyer/Melzer/Duennweber ---------
#
# Grundlage: J. Geyer, M. Melzer, J. Duennweber, A. Sarkar, "Human Step
# Movement Imitation for Training Privacy-Aware Intelligent Environments",
# IEEE, Abschnitt III-B und Formel (1):
#
#     P = SUMME(w_i * p_i) / SUMME(w_i)
#
# Im Paper ist P die Fussposition auf einer Sensormatte, p_i der Schwerpunkt
# eines aktivierten Dreiecksfelds und w_i dessen Kapazitaetswert. Der
# entscheidende Gedanke: Statt sich fuer EIN Rasterfeld zu entscheiden, wird
# eine kontinuierliche Position aus allen aktivierten Feldern berechnet, die
# zu den staerker aktivierten hin tendiert. Dem vorgeschaltet ist eine
# Trennung in einzelne Fuesse - ohne sie laege der Mittelwert zweier Fuesse
# zwischen ihnen, also dort, wo gar kein Fuss ist.
#
# WAS HIER UEBERTRAGEN WIRD und was nicht:
#   - Uebernommen ist Formel (1) selbst und die Reihenfolge "erst trennen,
#     dann gewichtet mitteln".
#   - NICHT uebernommen ist das Trennverfahren des Papers. Dort clustert
#     Mean Shift keine Rasterfelder, sondern Pixel-Embeddings in einem
#     gelernten 16-dimensionalen Raum (U-Net mit discriminative loss). Ein
#     solches Embedding gibt es hier nicht und waere fuer ein regelmaessiges
#     Gelaenderaster auch unnoetig: benachbarte Zellen sind schon im Raum
#     benachbart, eine Zusammenhangskomponenten-Suche (Flutfuellung) trennt
#     die Gebiete direkt. Das ist ein Analogon zum ZIEL des Schritts, nicht
#     zu seiner Methode.
#   - Die Gewichte w_i sind im Paper Kapazitaetswerte, also nichtnegativ.
#     Gelaendebewertungen sind dagegen vorzeichenbehaftet (Wald +3,
#     Autobahn -4). Ein Schwerpunkt mit negativen Gewichten ist nicht
#     sinnvoll: die Summe im Nenner kann gegen null gehen und das Ergebnis
#     beliebig weit wegspringen. Deshalb gehen nur ATTRAKTIVE Zellen in die
#     Mittelung ein, und ihr Gewicht ist die um die Attraktivitaetsschwelle
#     verschobene Bewertung (siehe _terrain_clusters).

# Ab welcher Bewertung eine Rasterzelle als attraktiv gilt. 1.0 laesst
# Wald (3.0), Naturschutzgebiet (3.0) und Gebuesch (2.0) zu, schliesst aber
# reine Wiesen/Feuchtgebiete (1.0) knapp ein und Ackerland (-0.5) aus.
TERRAIN_ATTRACTIVE_MIN = 1.0

# Umkreis, in dem das Gelaende als Flaeche betrachtet wird. 350 m entspricht
# bei 167 m Rasterweite gut 4 Zellen Kantenlaenge in jede Richtung - weit
# genug, um ein benachbartes Waldstueck zu erfassen, klein genug, damit die
# Richtung noch etwas mit dem naechsten Schritt zu tun hat.
CLUSTER_SEARCH_RADIUS_M = 350

# Wie viele frei gewuerfelte Richtungen zusaetzlich zu den Cluster-Richtungen
# angeboten werden. Ohne sie koennte der Baer ausschliesslich Cluster
# ansteuern - bei typisch 2-3 Clustern waere das Modell nahezu
# deterministisch und der Baer kaeme aus einem Waldstueck nie wieder heraus.
# Diese Kandidaten sind KONTINUIERLICH gleichverteilt (kein 45-Grad-Raster),
# damit keine unerreichbaren Richtungen entstehen.
NUM_FREE_CANDIDATES = 8

# Wie stark die blosse EXISTENZ eines attraktiven Gebiets in Reichweite die
# Richtungswahl anzieht - zusaetzlich zur Bewertung des Wegs dorthin.
#
# Ohne diesen Term waere die Uebertragung wirkungslos: Eine Cluster-Richtung
# ist dann nur ein weiterer Kandidat, der genau wie die freien bewertet wird
# (Gelaende auf den ersten ~200 m plus Richtungstraegheit). Die eigentliche
# Information aus Formel (1) - "in DIESER Richtung liegt eine grosse Masse
# attraktiven Gelaendes" - ginge dabei verloren. Im Paper ist die
# Aktivierungsmasse genau das Signal, das die Position zieht.
#
# Der Bonus waechst mit der Clustermasse, ist aber durch tanh gedeckelt:
# ein doppelt so grosser Wald soll anziehender sein, aber nicht beliebig,
# sonst wird die Wahl deterministisch.
CLUSTER_ATTRACTION = 4.0
CLUSTER_MASS_SCALE = 10.0


def _habitat_score(features: dict) -> float:
    """
    Bewertet eine Rasterzelle NUR nach Deckung/Lebensraum - Strassen,
    Siedlungen und Bahnlinien bleiben aussen vor.

    Warum getrennt von _score_terrain(): Dort werden alle Merkmale einer
    Zelle aufsummiert, also auch die negativen. Eine Waldzelle mit einem
    Waldweg darin kommt so auf 3.0 - 1.5 = 1.5, eine mit einer
    Gemeindestrasse sogar auf 1.5. Gemessen am echten Kameragebiet tragen
    11,5 % der Zellen einen Wald-Tag, aber nur 6,1 % erreichen in der
    Summenbewertung noch 1.0 - die Waelder werden von Wegen regelrecht
    zerschnitten und zerfallen in lauter Ein-Zellen-Cluster.

    Fuer die Frage "wo liegt ein zusammenhaengendes Waldstueck" ist das die
    falsche Groesse: ein Weg macht aus Wald keinen Nicht-Wald. Die
    Strafterme wirken weiterhin dort, wo sie hingehoeren - in der Bewertung
    des einzelnen Schrittziels (_score_terrain am Wahrnehmungspunkt).
    """
    if any("=" in k for k in features):
        table = TERRAIN_PREFERENCE_QUALIFIED
    else:
        table = TERRAIN_PREFERENCE
    return sum(w for key, w in table.items() if w > 0 and features.get(key))


def _terrain_clusters(
    current: tuple[float, float],
    terrain_cache: "TerrainCache",
    search_radius_m: float = CLUSTER_SEARCH_RADIUS_M,
    query_radius_m: int = 150,
    attractive_min: float = TERRAIN_ATTRACTIVE_MIN,
) -> list[dict]:
    """
    Sucht attraktive Gelaendegebiete im Umkreis und gibt pro Gebiet EINEN
    kontinuierlichen Zielpunkt zurueck (Formel (1) des Papers).

    Ablauf:
      1. Alle gecachten Rasterzellen im Umkreis holen (eine einzige
         SQLite-Abfrage, kein Netzwerkzugriff).
      2. Jede Zelle mit der bestehenden Tabelle bewerten (_score_terrain)
         und alle Zellen unterhalb der Attraktivitaetsschwelle verwerfen.
      3. Uebrige Zellen per Flutfuellung ueber die 8er-Nachbarschaft zu
         zusammenhaengenden Gebieten gruppieren - das ist der Schritt, der
         im Paper die Fuesse trennt. Ohne ihn laege der Schwerpunkt eines
         Waldes im Norden und eines im Sueden genau dazwischen, also
         womoeglich mitten im Dorf.
      4. Pro Gebiet den gewichteten Schwerpunkt nach Formel (1) bilden.
         Gewicht einer Zelle = Bewertung minus Schwelle, plus einen kleinen
         Sockel, damit auch eine Zelle genau auf der Schwelle noch zaehlt.
         Dadurch sind alle Gewichte positiv (siehe Kommentar oben).

    Returns:
        Liste von {"center": (lat, lon), "weight_sum": float, "n_cells": int},
        absteigend nach weight_sum. Leer, wenn nichts Attraktives in
        Reichweite liegt.
    """
    lat, lon = current
    # Umkreis in Gradmass: Laengengrade werden zum Pol hin enger.
    dlat = search_radius_m / 111_320.0
    dlon = search_radius_m / (111_320.0 * max(0.2, math.cos(math.radians(lat))))

    cells = terrain_cache.get_cells_in_box(
        lat - dlat, lon - dlon, lat + dlat, lon + dlon, radius=query_radius_m
    )
    if not cells:
        return []

    g = getattr(terrain_cache, "grid_size_deg", 0.0015)

    # Auf ganzzahlige Rasterindizes abbilden - erst dadurch ist
    # "benachbart" ohne Fliesskomma-Vergleich pruefbar.
    scored: dict[tuple[int, int], tuple[float, float, float]] = {}
    for lat_key, lon_key, features in cells:
        s = _habitat_score(features)
        if s < attractive_min:
            continue
        i, j = int(round(lat_key / g)), int(round(lon_key / g))
        scored[(i, j)] = (s, lat_key, lon_key)

    if not scored:
        return []

    # Flutfuellung ueber die 8er-Nachbarschaft (Zusammenhangskomponenten).
    # Bewusst iterativ mit einem Stapel statt rekursiv: bei grossen
    # zusammenhaengenden Waldflaechen waere die Rekursionstiefe sonst ein
    # Problem.
    neighbours = [(di, dj) for di in (-1, 0, 1) for dj in (-1, 0, 1) if (di, dj) != (0, 0)]
    seen: set[tuple[int, int]] = set()
    clusters = []

    for start in scored:
        if start in seen:
            continue
        stack, members = [start], []
        seen.add(start)
        while stack:
            cur = stack.pop()
            members.append(cur)
            ci, cj = cur
            for di, dj in neighbours:
                nb = (ci + di, cj + dj)
                if nb in scored and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)

        # Formel (1): P = SUMME(w_i * p_i) / SUMME(w_i)
        # Sockel 0.5, damit eine Zelle exakt auf der Schwelle nicht mit
        # Gewicht 0 herausfaellt.
        w_sum = 0.0
        lat_acc = lon_acc = 0.0
        for m in members:
            s, clat, clon = scored[m]
            w = (s - attractive_min) + 0.5
            w_sum += w
            lat_acc += w * clat
            lon_acc += w * clon
        if w_sum <= 0:
            continue
        clusters.append({
            "center": (lat_acc / w_sum, lon_acc / w_sum),
            "weight_sum": w_sum,
            "n_cells": len(members),
        })

    clusters.sort(key=lambda c: c["weight_sum"], reverse=True)
    return clusters


def choose_weighted_direction(
    current: tuple[float, float],
    step_length_m: float,
    rng: random.Random,
    terrain_cache: "TerrainCache | None" = None,
    prev_direction: float | None = None,
    persistence_weight: float = DEFAULT_PERSISTENCE_WEIGHT,
    num_candidates: int = 8,
    query_radius_m: int = 150,
    terrain_perception_m: float = DEFAULT_TERRAIN_PERCEPTION_M,
    selection_beta: float = SELECTION_BETA,
    terrain_samples: int = 3,
    cluster_attraction: float = CLUSTER_ATTRACTION,
) -> tuple[tuple[float, float], float]:
    """
    Waehlt die naechste Richtung gewichtet-zufaellig aus einer Kandidatenmenge.

    Die Kandidaten entstehen aus zwei Quellen:
      - Zielrichtungen zu attraktiven Gelaendegebieten, ermittelt nach dem
        Verfahren aus Geyer/Melzer/Duennweber (Formel (1), siehe
        _terrain_clusters und den Kommentarblock darueber). Nur wenn ein
        terrain_cache uebergeben wurde.
      - Kontinuierlich gleichverteilte Zufallsrichtungen, damit das Modell
        stochastisch bleibt und keine Richtung unerreichbar ist.

    Bewertet werden die Kandidaten danach nach ZWEI ggf. kombinierten
    Signalen:

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
    # -----------------------------------------------------------------
    # 1) Richtungen zu attraktiven Gelaendegebieten (Formel (1), s.o.)
    # -----------------------------------------------------------------
    # Je Kandidat (Richtung, Zusatzbonus). Nur Cluster-Richtungen bekommen
    # einen Bonus, freie Richtungen nicht.
    directions: list[tuple[float, float]] = []
    if terrain_cache is not None:
        for cl in _terrain_clusters(current, terrain_cache,
                                    query_radius_m=query_radius_m):
            d = GeoToolBox.calculate_direction(current, cl["center"])
            bonus = cluster_attraction * math.tanh(cl["weight_sum"] / CLUSTER_MASS_SCALE)
            directions.append((d % 360, bonus))

    # -----------------------------------------------------------------
    # 2) Frei gewuerfelte Richtungen, KONTINUIERLICH gleichverteilt.
    #
    # Fruehere Fassung: acht feste Richtungen im 45-Grad-Raster mit nur
    # +/-15 Grad Streuung. Damit deckte jeder Sektor nur 30 seiner 45 Grad
    # ab - die Bereiche dazwischen (z.B. 16-29 Grad) waren grundsaetzlich
    # unerreichbar, ein Drittel aller Richtungen.
    #
    # Jetzt +/-22.5 Grad: die Sektoren stossen luekenlos aneinander und
    # decken den vollen Kreis ab. Die Stratifizierung (genau ein Kandidat
    # je Sektor) bleibt bewusst erhalten - sie verteilt die Kandidaten
    # gleichmaessiger ueber den Kreis, als es reines Wuerfeln taete, bei
    # dem sich pro Schritt zufaellig mehrere Kandidaten in derselben
    # Himmelsrichtung haeufen koennen.
    #
    # Diese Kandidaten bleiben auch MIT Gelaendedaten erhalten: sonst
    # koennte der Baer nur noch Cluster ansteuern und kaeme aus einem
    # Waldstueck nicht mehr heraus.
    # -----------------------------------------------------------------
    n_free = num_candidates if terrain_cache is None else NUM_FREE_CANDIDATES
    sector = 360.0 / n_free
    for i in range(n_free):
        directions.append(((sector * i + rng.uniform(-sector / 2, sector / 2)) % 360, 0.0))

    candidates = []
    for direction, cluster_bonus in directions:
        score = cluster_bonus
        dest = GeoToolBox.destination_point(current, direction, step_length_m)
        if terrain_cache is not None:
            # Gelaende NICHT nur am Schrittende bewerten, sondern entlang
            # des Wegs bis zu einem Wahrnehmungspunkt weiter voraus: die
            # Schritte sind oft kuerzer als die Rasterweite (167 m), sonst
            # landen alle Kandidaten in derselben Zelle und die Bewertung
            # waere identisch.
            #
            # Mehrere Stichproben statt nur des Endpunkts (Messung siehe
            # ANPASSUNGEN.md, Punkt 8): Eine Cluster-Richtung zeigt auf den
            # Schwerpunkt eines Waldstuecks, das durchaus HINTER einem Dorf
            # liegen kann. Wird nur der Endpunkt bewertet, sieht der Weg
            # attraktiv aus und der Baer laeuft mitten durch die Ortschaft.
            # Mit Stichproben auf dem Weg schlaegt die Siedlung zu Buche.
            look_ahead = max(step_length_m, terrain_perception_m)
            samples = []
            for k in range(1, terrain_samples + 1):
                d_k = look_ahead * k / terrain_samples
                pt = GeoToolBox.destination_point(current, direction, d_k)
                samples.append(_score_terrain(
                    terrain_cache.get_features(pt[0], pt[1], radius=query_radius_m)
                ))
            score += sum(samples) / len(samples)

        if prev_direction is not None:
            angle_diff = _angular_diff_deg(direction, prev_direction)
            # cos(0)=1 (gleiche Richtung, voller Bonus) ... cos(180)=-1 (Kehrtwende, voller Abzug)
            score += persistence_weight * math.cos(math.radians(angle_diff))

        candidates.append((dest, direction, score))

    # Exponentielle Gewichtung (wie in Step-Selection-Funktionen ueblich):
    # Wahrscheinlichkeit ~ exp(beta * Bewertung). Die vorherige lineare
    # Verschiebung machte den Unterschied zwischen Wald und Siedlung nur
    # etwa Faktor 2-3 gross - zu wenig, um ein Hineinlaufen in Ortschaften
    # zu verhindern. Abzug des Maximums dient nur der Zahlenstabilitaet
    # (aendert die relativen Wahrscheinlichkeiten nicht).
    scores = [c[2] for c in candidates]
    max_score = max(scores)
    weights = [math.exp(selection_beta * (sc - max_score)) for sc in scores]

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
    terrain_perception_m: float = DEFAULT_TERRAIN_PERCEPTION_M,
    selection_beta: float = SELECTION_BETA,
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
                terrain_perception_m=terrain_perception_m,
                selection_beta=selection_beta,
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


def get_photo_counts_by_camera(db: "WildlifeDatabase") -> "dict[str, int] | None":
    """
    Anzahl echter Fotos je Kamera - EINE Abfrage fuer alle Geraete.

    Wird fuer die anklickbaren Kamerapunkte gebraucht. Bewusst nicht ueber
    wiederholte get_real_events_for_camera()-Aufrufe geloest: das waeren 20
    Einzelabfragen pro Seitenaufruf.

    Die IDs werden mit derselben Normalisierung wie die Kamera-CSV
    behandelt (_normalize_device_id), sonst passen "3002.0" aus der CSV und
    "003002" aus der DB nicht zusammen. Platzhalter-Geraete (fehlgeschlagene
    ID-Erkennung beim E-Mail-Import) bleiben aussen vor.

    Returns:
        {device_id: anzahl}, oder None, wenn die Abfrage fehlgeschlagen ist.

        None und {} sind BEWUSST verschieden: {} heisst "abgefragt, aber an
        keiner Kamera Fotos", None heisst "nicht abfragbar". Kameras, an
        denen nie fotografiert wurde, tauchen wegen GROUP BY gar nicht erst
        im Ergebnis auf - der Aufrufer darf einen fehlenden Schluessel also
        als 0 werten, sobald das Ergebnis nicht None ist. Wuerde hier im
        Fehlerfall {} zurueckgegeben, meldete die Karte faelschlich
        "keine Fotos" statt "unbekannt".
    """
    try:
        rows = db.execute_query(
            "SELECT device_id, COUNT(*) AS n FROM bears_images_unified "
            "WHERE device_id IS NOT NULL GROUP BY device_id"
        )
    except Exception as e:
        print(f"[japan_comparison] Fotozahlen nicht abrufbar: {e}")
        return None
    if rows is None:
        # execute_query() wirft Fehler weiter und liefert sonst immer eine
        # Liste - diese Pruefung ist reine Absicherung, damit ein kuenftiges
        # None nicht stillschweigend als "keine Fotos" durchgereicht wird.
        return None

    counts: dict[str, int] = {}
    for r in rows or []:
        did = _normalize_device_id(r.get("device_id"))
        if did in PLACEHOLDER_DEVICE_IDS:
            continue
        counts[did] = counts.get(did, 0) + int(r.get("n") or 0)
    return counts


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