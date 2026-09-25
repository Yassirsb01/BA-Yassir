"""
test_richtungsverteilung.py
=============================
Prueft die cluster-basierte Richtungswahl (siehe japan_comparison,
Kommentarblock "Cluster-basierte Richtungswahl nach Geyer/Melzer/Duennweber").

Geprueft wird:
  1. Richtungsverteilung - die frueheren acht Luecken im 45-Grad-Raster
     muessen verschwunden sein.
  2. Vergleich alt/neu mit IDENTISCHEN Seeds: Tagesstrecke, Waldanteil,
     Siedlungsanteil, mittlere Gelaendebewertung.
  3. Laufzeit eines 24-h-Laufs.
  4. Wie viele Cluster typischerweise gefunden werden.
  5. Dass KEINE Netzwerkanfragen stattfinden.

Aufruf:  python test_richtungsverteilung.py
"""

import json
import math
import random
import statistics
import time

import japan_comparison as jc
from terrain_cache import TerrainCache

N_RUNS = 160
HOURS = 24
SEED_BASE = 1000


# =========================================================
# Netzwerksperre (Test 5)
# =========================================================
class NetzwerkBenutzt(AssertionError):
    pass


def netzwerk_sperren():
    """
    Macht jeden Socket-Verbindungsaufbau zum Fehler. Strenger als das
    Abfangen von requests: so faellt auch ein Zugriff auf, der an der
    Bibliothek vorbei geht.
    """
    import socket

    def _verboten(*a, **k):
        raise NetzwerkBenutzt("Es wurde eine Netzwerkverbindung versucht!")

    socket.socket.connect = _verboten
    socket.create_connection = _verboten


# =========================================================
# Hilfsfunktionen
# =========================================================
def sammle_richtungen(runs=N_RUNS, hours=HOURS):
    """Fuehrt Laeufe ab echten Kamerastandorten aus und protokolliert
    jede gewaehlte Richtung."""
    from data.DatabaseConnection import DatabaseConnection
    from data.BearSpeeds import BearSpeeds

    cams = jc.load_japan_cameras()
    bs = BearSpeeds(DatabaseConnection(jc.SIM_DB_PATH))
    tc = TerrainCache()

    richtungen = []
    original = jc.choose_weighted_direction

    def mitschnitt(*args, **kwargs):
        dest, direction = original(*args, **kwargs)
        richtungen.append(direction)
        return dest, direction

    jc.choose_weighted_direction = mitschnitt
    try:
        from datetime import datetime
        for i in range(runs):
            cam = cams[i % len(cams)]
            jc.simulate_free_path(
                start_lat=cam["lat"], start_lng=cam["lng"],
                start_time=datetime(2024, 6, 1, 20, 0),
                duration_hours=hours, gender="F", age="A", season="summer",
                bear_speeds=bs, seed=SEED_BASE + i, terrain_cache=tc,
            )
    finally:
        jc.choose_weighted_direction = original
    return richtungen


def luecken_pruefen(richtungen):
    """Zaehlt, wie viele Richtungen in die frueher unerreichbaren Bereiche
    fallen: das alte Raster erlaubte nur 45*i +/- 15 Grad."""
    in_luecke = 0
    for d in richtungen:
        rest = d % 45.0
        # erreichbar war nur [0,15] und [30,45] eines jeden 45-Grad-Sektors
        if 15.0 < rest < 30.0:
            in_luecke += 1
    return in_luecke


def histogramm(richtungen, bins=24):
    breite = 360.0 / bins
    h = [0] * bins
    for d in richtungen:
        h[min(bins - 1, int(d / breite))] += 1
    return h


def pfad_kennzahlen(path, tc):
    """Tagesstrecke, Wald-/Siedlungsanteil und mittlere Bewertung eines Pfads."""
    from geopy.distance import geodesic
    strecke = 0.0
    for a, b in zip(path, path[1:]):
        strecke += geodesic((a["lat"], a["lng"]), (b["lat"], b["lng"])).meters

    # Siedlung bewusst GETRENNT erfasst: "landuse=residential" ist ein
    # bebautes Wohngebiet, "highway=residential" nur eine Wohnstrasse. Die
    # frueher verwendete Oder-Verknuepfung beider Merkmale hat den
    # Siedlungsanteil massiv ueberzeichnet - in diesem Gebiet traegt fast
    # jede Zelle irgendeine Strasse (siehe ANPASSUNGEN.md, Punkt 5).
    wald = wohngebiet = wohnstrasse = 0
    scores = []
    for p in path:
        f = tc.get_features(p["lat"], p["lng"], radius=150)
        if f.get("landuse=forest") or f.get("natural=wood") or f.get("forest") or f.get("wood"):
            wald += 1
        if f.get("landuse=residential"):
            wohngebiet += 1
        if f.get("highway=residential"):
            wohnstrasse += 1
        scores.append(jc._score_terrain(f))
    n = max(1, len(path))
    # Netto-Verlagerung: Luftlinie Start -> Ende. Die Tagesstrecke (Summe
    # der Schrittlaengen) ist als Vergleichsmass ungeeignet, weil sie
    # allein aus der Geschwindigkeitstabelle folgt und von der
    # Richtungswahl gar nicht abhaengt - sie ist in allen Varianten exakt
    # gleich. Erst die Netto-Verlagerung zeigt, ob der Baer zielgerichtet
    # wandert oder umherirrt.
    netto = geodesic((path[0]["lat"], path[0]["lng"]),
                     (path[-1]["lat"], path[-1]["lng"])).meters if len(path) > 1 else 0.0
    return {
        "strecke_m": strecke,
        "netto_m": netto,
        "wald_pct": wald / n * 100,
        "wohngebiet_pct": wohngebiet / n * 100,
        "wohnstrasse_pct": wohnstrasse / n * 100,
        "bewertung": statistics.mean(scores) if scores else 0.0,
    }


def alte_richtungswahl(current, step_length_m, rng, terrain_cache=None,
                       prev_direction=None, persistence_weight=None,
                       num_candidates=8, query_radius_m=150,
                       terrain_perception_m=None, selection_beta=None,
                       terrain_samples=None):
    """
    WORTGETREUE Kopie der Richtungswahl VOR der Umstellung - acht feste
    Sektoren mit nur +/-15 Grad Streuung, Bewertung ausschliesslich am
    Wahrnehmungspunkt. Dient als ehrliche Vorher-Referenz im Vergleich;
    wird nur von diesem Test benutzt, nicht vom Produktivcode.
    """
    from GeoToolBox import GeoToolBox
    persistence_weight = jc.DEFAULT_PERSISTENCE_WEIGHT if persistence_weight is None else persistence_weight
    terrain_perception_m = jc.DEFAULT_TERRAIN_PERCEPTION_M if terrain_perception_m is None else terrain_perception_m
    selection_beta = jc.SELECTION_BETA if selection_beta is None else selection_beta

    candidates = []
    for i in range(num_candidates):
        base_angle = (360.0 / num_candidates) * i
        direction = (base_angle + rng.uniform(-15, 15)) % 360
        score = 0.0
        dest = GeoToolBox.destination_point(current, direction, step_length_m)
        if terrain_cache is not None:
            look_ahead = max(step_length_m, terrain_perception_m)
            pp = GeoToolBox.destination_point(current, direction, look_ahead)
            score += jc._score_terrain(terrain_cache.get_features(pp[0], pp[1], radius=query_radius_m))
        if prev_direction is not None:
            score += persistence_weight * math.cos(math.radians(
                jc._angular_diff_deg(direction, prev_direction)))
        candidates.append((dest, direction, score))
    scores = [c[2] for c in candidates]
    mx = max(scores)
    weights = [math.exp(selection_beta * (s - mx)) for s in scores]
    d, dirn, _ = rng.choices(candidates, weights=weights, k=1)[0]
    return d, dirn


def laeufe_kennzahlen(runs, hours, cluster_an):
    """Fuehrt Laeufe durch und mittelt die Kennzahlen. cluster_an=False
    schaltet die Cluster-Kandidaten ab (= altes Verhalten der Kandidaten-
    erzeugung, aber sonst identischer Code und identische Seeds)."""
    from data.DatabaseConnection import DatabaseConnection
    from data.BearSpeeds import BearSpeeds
    from datetime import datetime

    cams = jc.load_japan_cameras()
    bs = BearSpeeds(DatabaseConnection(jc.SIM_DB_PATH))
    tc = TerrainCache()

    alt = jc._terrain_clusters
    if not cluster_an:
        jc._terrain_clusters = lambda *a, **k: []

    ergebnisse = []
    t0 = time.time()
    try:
        for i in range(runs):
            cam = cams[i % len(cams)]
            path = jc.simulate_free_path(
                start_lat=cam["lat"], start_lng=cam["lng"],
                start_time=datetime(2024, 6, 1, 20, 0),
                duration_hours=hours, gender="F", age="A", season="summer",
                bear_speeds=bs, seed=SEED_BASE + i, terrain_cache=tc,
            )
            ergebnisse.append(pfad_kennzahlen(path, tc))
    finally:
        jc._terrain_clusters = alt
    dauer = time.time() - t0

    out = {k: statistics.mean(e[k] for e in ergebnisse)
           for k in ("strecke_m", "netto_m", "wald_pct", "wohngebiet_pct",
                     "wohnstrasse_pct", "bewertung")}
    out["sek_pro_lauf"] = dauer / max(1, runs)
    return out


# =========================================================
# Ablauf
# =========================================================
def main():
    netzwerk_sperren()
    print("Netzwerk gesperrt - jeder Verbindungsversuch wird zum Fehler.\n")

    tc = TerrainCache()
    print(f"Gelaende-Cache nutzbar: {not tc.disabled}, Prefetch-Regionen: {len(tc._regions)}\n")

    # ---- Test 4: Cluster-Anzahl ----------------------------------
    print("=" * 66)
    print("TEST 4: Wie viele Cluster werden gefunden?")
    print("=" * 66)
    cams = jc.load_japan_cameras()
    an_kameras = [len(jc._terrain_clusters((c["lat"], c["lng"]), tc)) for c in cams]
    print(f"  an den {len(cams)} Kamerastandorten: "
          f"median {statistics.median(an_kameras):.1f}, max {max(an_kameras)}, "
          f"ohne Cluster {sum(1 for x in an_kameras if x == 0)}")

    # entlang echter Simulationspfade (aussagekraeftiger als nur die Startpunkte)
    from data.DatabaseConnection import DatabaseConnection
    from data.BearSpeeds import BearSpeeds
    from datetime import datetime
    bs = BearSpeeds(DatabaseConnection(jc.SIM_DB_PATH))
    unterwegs = []
    for i in range(20):
        cam = cams[i % len(cams)]
        path = jc.simulate_free_path(
            start_lat=cam["lat"], start_lng=cam["lng"],
            start_time=datetime(2024, 6, 1, 20, 0), duration_hours=HOURS,
            gender="F", age="A", season="summer", bear_speeds=bs,
            seed=SEED_BASE + i, terrain_cache=tc,
        )
        for p in path:
            unterwegs.append(len(jc._terrain_clusters((p["lat"], p["lng"]), tc)))
    vert = {k: unterwegs.count(k) for k in sorted(set(unterwegs))}
    print(f"  entlang der Pfade ({len(unterwegs)} Positionen): median "
          f"{statistics.median(unterwegs):.1f}, mittel {statistics.mean(unterwegs):.2f}, max {max(unterwegs)}")
    print(f"  Verteilung (Cluster: Anzahl Positionen): {vert}")
    mehr_als_eins = sum(1 for x in unterwegs if x > 1) / len(unterwegs) * 100
    print(f"  Positionen mit MEHR als einem Cluster: {mehr_als_eins:.1f} %")

    # ---- Test 1: Richtungsverteilung ------------------------------
    print("\n" + "=" * 66)
    print(f"TEST 1: Richtungsverteilung ({N_RUNS} Laeufe a {HOURS} h)")
    print("=" * 66)
    t0 = time.time()
    richtungen = sammle_richtungen()
    print(f"  {len(richtungen)} Richtungsentscheidungen in {time.time()-t0:.1f}s")
    luecken = luecken_pruefen(richtungen)
    print(f"  in den frueher unerreichbaren Bereichen: {luecken} "
          f"({luecken/len(richtungen)*100:.1f} %) - erwartet werden rund 33 %")
    h = histogramm(richtungen, bins=24)
    erwartet = len(richtungen) / 24
    print(f"  Histogramm (24 Sektoren a 15 Grad), Erwartungswert je Sektor {erwartet:.0f}:")
    print(f"    {h}")
    print(f"    min {min(h)}, max {max(h)}, leere Sektoren: {sum(1 for x in h if x == 0)}")
    # Chi-Quadrat gegen Gleichverteilung (nur als Kennzahl, kein Test)
    chi = sum((x - erwartet) ** 2 / erwartet for x in h)
    print(f"    Chi-Quadrat gegen Gleichverteilung: {chi:.1f} (df=23)")

    # ---- Test 2 + 3: Vergleich und Laufzeit -----------------------
    print("\n" + "=" * 66)
    print("TEST 2+3: Vergleich ohne/mit Clustern, gleiche Seeds")
    print("=" * 66)
    # Variante A: der echte alte Code (8 Sektoren +/-15 Grad, 1 Stichprobe)
    neu = jc.choose_weighted_direction
    jc.choose_weighted_direction = alte_richtungswahl
    try:
        alt = laeufe_kennzahlen(60, HOURS, cluster_an=False)
    finally:
        jc.choose_weighted_direction = neu

    # Variante B: neuer Code, aber ohne Cluster-Kandidaten
    ohne = laeufe_kennzahlen(60, HOURS, cluster_an=False)
    # Variante C: neuer Code vollstaendig
    mit = laeufe_kennzahlen(60, HOURS, cluster_an=True)

    print(f"  {'Kennzahl':<24}{'ALT (45-Raster)':>17}{'neu ohne Cl.':>14}{'neu mit Cl.':>14}")
    print(f"  {'-'*69}")
    for key, label, fmt in [
        ("strecke_m", "Tagesstrecke (m)", "{:.0f}"),
        ("netto_m", "Netto-Verlagerung (m)", "{:.0f}"),
        ("wald_pct", "Waldanteil (%)", "{:.1f}"),
        ("wohngebiet_pct", "Wohngebiet (%)", "{:.1f}"),
        ("wohnstrasse_pct", "Wohnstrasse (%)", "{:.1f}"),
        ("bewertung", "mittlere Bewertung", "{:.2f}"),
        ("sek_pro_lauf", "Sek. je 24-h-Lauf", "{:.3f}"),
    ]:
        print(f"  {label:<24}{fmt.format(alt[key]):>17}{fmt.format(ohne[key]):>14}{fmt.format(mit[key]):>14}")
    faktor = mit["sek_pro_lauf"] / max(1e-9, alt["sek_pro_lauf"])
    print(f"\n  Laufzeit gegenueber ALT: {faktor:.2f}x")

    print("\n" + "=" * 66)
    print("TEST 5: keine Netzwerkanfragen - bis hierher keine Ausnahme "
          "ausgeloest.")
    print("=" * 66)


if __name__ == "__main__":
    main()
