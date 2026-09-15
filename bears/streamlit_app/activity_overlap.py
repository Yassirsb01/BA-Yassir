"""
activity_overlap.py
=====================
Vergleicht das TAGESRHYTHMUS-Muster echter japanischer Kamera-Ausloesungen
mit dem eines simulierten Baeren (Fabians Bewegungsmodell, uebertragen auf
die japanische Kamera-Landschaft) - als EINE Kennzahl: den Ueberlappungs-
koeffizienten Delta (0 = keine Uebereinstimmung, 1 = identisch).

Warum gepoolt statt pro Kamera: Ein Test der echten Daten
(check_japan_data.py) zeigte nur 36-52 Zeitstempel, verteilt auf 8-20
Kameras - zu duenn fuer eine Verteilung PRO Kamera. Gepoolt ueber alle
Kameras ist die Stichprobe groesser genug fuer eine (weiterhin vorsichtig
zu interpretierende) Kerndichteschaetzung.

Methodik (siehe Recherche-Ergebnis, Konzept A + B kombiniert):
  - Echte Detektionen: Uhrzeiten aus bears_images_unified, OHNE die
    Platzhalter-Geraete-IDs (199999, 999999 - vermutlich fehlgeschlagene
    ID-Erkennung beim E-Mail-Import).
  - Simulierte Detektionen: Viele Monte-Carlo-Laeufe (nicht nur einer wie
    in japan_comparison.py) - fuer jeden Lauf ein virtueller Baer ab einem
    zufaelligen Kamerastandort, zufaelligem Geschlecht/Alter/Saison (um
    ueber unbekannte Demografie zu mitteln), der sich nach Fabians Modell
    bewegt. Jedes Mal, wenn er einer Kamera nahe genug kommt (Radius
    DETECTION_RADIUS_M), zaehlt das als "virtuelle Ausloesung" mit der
    jeweiligen Uhrzeit.
  - Beide Uhrzeit-Verteilungen werden per Kreis-Dichteschaetzung (wrapped
    Gaussian KDE - 23 Uhr und 0 Uhr liegen damit korrekt nah beieinander,
    nicht an gegenueberliegenden Enden einer Linie) geglaettet und ueber
    den Ueberlappungskoeffizienten Delta = Integral(min(f1,f2)) verglichen -
    das Standardmass aus der Kamerafallen-Literatur (Ridout & Linkie 2009),
    hier vereinfacht ohne die R-spezifische 'overlap'-Paket-Implementierung
    (von-Mises-Kern) nachgebaut, aber nach demselben Prinzip.
  - Unsicherheit: Bootstrap (Ziehen mit Zurueglegen aus beiden Stichproben,
    Delta neu berechnen, 1000x) - liefert ein 95%-Konfidenzintervall statt
    einer einzelnen, unbegruendet praezise wirkenden Zahl.
"""

import os
import sys
from datetime import datetime, timedelta

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# Wiederverwendung der bereits gebauten und getesteten Bausteine aus
# japan_comparison.py (Kamera-Liste laden, Pfad simulieren, DB-Check) -
# keine Dopplung von Logik.
from japan_comparison import (  # noqa: E402
    load_japan_cameras, simulate_free_path,
    DatabaseConnection, BearSpeeds, SIM_DB_PATH,
    VALID_GENDERS, VALID_AGES, VALID_SEASONS,
)
from geopy.distance import geodesic  # noqa: E402
from wildlife_db_mariadb import WildlifeDatabase  # noqa: E402

import threading  # noqa: E402


def check_db_reachable_bounded(db: "WildlifeDatabase", timeout_sec: float = 6.0) -> bool:
    """
    Wie check_db_reachable() in japan_comparison.py, aber mit einer HARTEN
    Zeitgrenze ueber einen Hintergrund-Thread (funktioniert plattform-
    unabhaengig, auch unter Windows - anders als z.B. signal.alarm()).

    Grund: mysql.connector hat in WildlifeDatabase keinen expliziten
    connection_timeout gesetzt. Falls ein Netzwerk Pakete still verwirft
    statt die Verbindung aktiv abzulehnen, kann der Verbindungsversuch
    sonst sehr lange (ggf. mehrere Minuten) haengen bleiben, bevor ueberhaupt
    eine Fehlermeldung kommt - fuer ein interaktives Analyseskript inakzeptabel.
    """
    result = {"ok": False}

    def _try_connect():
        try:
            conn = db._get_connection()
            conn.close()
            result["ok"] = True
        except Exception:
            result["ok"] = False

    t = threading.Thread(target=_try_connect, daemon=True)
    t.start()
    t.join(timeout_sec)
    if t.is_alive():
        # Verbindungsversuch haengt noch nach Ablauf der Frist - als nicht
        # erreichbar werten. Der Thread ist ein Daemon und haengt hoechstens
        # im Hintergrund weiter, blockiert das Skript aber nicht mehr.
        return False
    return result["ok"]

# Geraete-IDs, die beim Datencheck als Platzhalter/Fehlwerte aufgefallen
# sind (kein Muster wie die echten 6-stelligen IDs) - siehe check_japan_data.py.
PLACEHOLDER_DEVICE_IDS = {"199999", "999999"}

DETECTION_RADIUS_M = 150  # Wahrnehmungsradius einer Kamera, wie bei japan_comparison.py


# =========================================================
# 1) Echte Detektionszeiten aus der Datenbank
# =========================================================
def get_real_detection_hours(db: "WildlifeDatabase", exclude_ids=PLACEHOLDER_DEVICE_IDS):
    """
    Liest alle Zeitstempel aus bears_images_unified (Dateisystem + E-Mail
    zusammen - vollstaendiger als nur image_metadata) und wandelt sie in
    Dezimalstunden um (z.B. 19:30 Uhr -> 19.5).

    Returns:
        (hours: list[float], n_excluded: int)
    """
    rows = db.execute_query(
        "SELECT device_id, timestamp FROM bears_images_unified WHERE timestamp IS NOT NULL"
    )
    hours = []
    n_excluded = 0
    for r in rows or []:
        device_id = str(r.get("device_id"))
        if device_id in exclude_ids:
            n_excluded += 1
            continue
        ts = r.get("timestamp")
        try:
            dt = ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts))
        except (ValueError, TypeError):
            continue
        hours.append(dt.hour + dt.minute / 60.0)
    return hours, n_excluded


# =========================================================
# 2) Monte-Carlo-Simulation: virtuelle Kamera-Ausloesungen
# =========================================================
def run_monte_carlo_virtual_detections(
    n_runs: int = 300,
    hours_per_run: int = 48,
    detection_radius_m: float = DETECTION_RADIUS_M,
    seed: int = 42,
    terrain_cache=None,
    capture_run: bool = False,
) -> tuple[list[float], dict | None]:
    """
    Simuliert n_runs unabhaengige Baerenpfade (je hours_per_run Stunden lang)
    ab zufaelligen Kamerastandorten, mit zufaelligem Geschlecht/Alter/Saison
    (um ueber unbekannte Demografie der japanischen Population zu mitteln -
    wir wissen nicht, welches Tier welche Kamera ausgeloest hat). Jede
    Annaeherung <= detection_radius_m an IRGENDEINE Kamera zaehlt als
    virtuelle Ausloesung; deren Uhrzeit wird gesammelt.

    Der Startpunkt selbst (= eine Kamera per Definition) wird NICHT
    mitgezaehlt, sonst waere jeder Lauf trivial "sofort erkannt".

    Args:
        capture_run: Falls True, wird zusaetzlich EIN kompletter Lauf (Pfad +
            Detektions-Ereignisse) zurueckgegeben - fuer eine Animation in der
            Oberflaeche. Es ist bewusst NICHT der Lauf mit den meisten
            Treffern (das waere Rosinenpickerei fuer eine huebschere Demo),
            sondern schlicht der ERSTE Lauf mit mindestens einer Detektion
            (unter den ersten 15 Laeufen durchsucht, damit die Animation nicht
            zufaellig einen komplett leeren Lauf erwischt und wie ein Fehler
            aussieht) - klar als "ein zufaelliger Lauf, kein Best-Case" in
            der Oberflaeche zu kennzeichnen.

    Returns:
        (virtual_hours, captured_run) - captured_run ist None, falls
        capture_run=False oder kein Lauf unter den ersten 15 Treffer hatte.
        captured_run ist sonst ein Dict:
          {"path": [...], "detections": [{"time": datetime, "lat", "lng",
           "camera_id"}], "start_camera": {...}}
    """
    cameras = load_japan_cameras()
    if not cameras:
        raise RuntimeError("Keine Japan-Kamerastandorte gefunden (2024Bear/ReadMe.csv fehlt?).")

    dbcon = DatabaseConnection(SIM_DB_PATH)
    bear_speeds = BearSpeeds(dbcon)
    rng = np.random.default_rng(seed)

    virtual_hours: list[float] = []
    captured_run: dict | None = None
    capture_search_budget = 15  # nur die ersten N Laeufe als Kandidat pruefen, siehe Docstring

    for run_idx in range(n_runs):
        start_cam = cameras[rng.integers(0, len(cameras))]
        gender = VALID_GENDERS[rng.integers(0, len(VALID_GENDERS))]
        age = VALID_AGES[rng.integers(0, len(VALID_AGES))]
        season = VALID_SEASONS[rng.integers(0, len(VALID_SEASONS))]
        start_hour = int(rng.integers(0, 24))  # gleichverteilter Start ueber den Tag, keine Verzerrung
        start_time = datetime(2024, 1, 1, start_hour, 0, 0)

        path = simulate_free_path(
            start_lat=start_cam["lat"], start_lng=start_cam["lng"],
            start_time=start_time, duration_hours=hours_per_run,
            gender=gender, age=age, season=season,
            bear_speeds=bear_speeds, seed=int(rng.integers(0, 10_000_000)),
            terrain_cache=terrain_cache,
        )

        run_detections = []  # nur fuer diesen Lauf, falls er als "captured" in Frage kommt
        for point in path[1:]:  # [0] ist der Startpunkt = eine Kamera -> ausschliessen
            pos = (point["lat"], point["lng"])
            for cam in cameras:
                if geodesic(pos, (cam["lat"], cam["lng"])).meters <= detection_radius_m:
                    t = point["time"]
                    virtual_hours.append(t.hour + t.minute / 60.0)
                    run_detections.append({
                        "time": t, "lat": point["lat"], "lng": point["lng"],
                        "camera_id": cam.get("device_id"),
                        "camera_lat": cam["lat"], "camera_lng": cam["lng"],
                    })
                    break  # eine Ausloesung pro Zeitschritt reicht, nicht pro Kamera doppelt zaehlen

        if capture_run and captured_run is None and run_idx < capture_search_budget:
            if run_detections:
                captured_run = {"path": path, "detections": run_detections, "start_camera": start_cam}
            elif run_idx == capture_search_budget - 1:
                # Kein einziger der ersten 15 Laeufe hatte eine Detektion -
                # dann lieber den letzten davon (leer) zeigen als gar keinen,
                # transparent als "kein Treffer in diesem Beispiel" kennzeichenbar.
                captured_run = {"path": path, "detections": [], "start_camera": start_cam}

    return virtual_hours, captured_run


# =========================================================
# 3) Kreis-Dichteschaetzung + Ueberlappungskoeffizient
# =========================================================
def circular_kde(hours, grid: np.ndarray, bandwidth: float = 1.5) -> np.ndarray:
    """
    Wrapped-Gaussian-KDE auf dem 24h-Kreis: Die Daten werden zusaetzlich um
    -24h und +24h gespiegelt eingerechnet, damit z.B. 23:30 und 00:30 Uhr
    korrekt als nah beieinander liegend behandelt werden (nicht als
    entgegengesetzte Enden einer Linie). bandwidth in Stunden.
    """
    hours = np.asarray(hours, dtype=float)
    if len(hours) == 0:
        return np.zeros_like(grid)
    extended = np.concatenate([hours - 24, hours, hours + 24])
    diffs = grid[:, None] - extended[None, :]
    weights = np.exp(-0.5 * (diffs / bandwidth) ** 2)
    density = weights.sum(axis=1) / (len(hours) * bandwidth * np.sqrt(2 * np.pi))
    return density


def overlap_coefficient(f1: np.ndarray, f2: np.ndarray, dx: float) -> float:
    """Delta = Integral(min(f1,f2)) - Standardmass fuer Verteilungsueberlappung
    (Ridout & Linkie 2009), hier numerisch ueber ein Gitter approximiert."""
    return float(np.sum(np.minimum(f1, f2)) * dx)


def bootstrap_delta_ci(
    real_hours, sim_hours, grid: np.ndarray, bandwidth: float,
    n_boot: int = 1000, seed: int = 42, return_samples: bool = False,
):
    """Bootstrap-Konfidenzintervall fuer Delta (2.5%, Median, 97.5%).

    return_samples=True liefert zusaetzlich alle n_boot Delta-Werte zurueck
    (fuer ein Histogramm in der Oberflaeche) - Standardfall (False) bleibt
    unveraendert zum bisherigen Verhalten."""
    rng = np.random.default_rng(seed)
    real_hours = np.asarray(real_hours, dtype=float)
    sim_hours = np.asarray(sim_hours, dtype=float)
    dx = grid[1] - grid[0]

    deltas = np.empty(n_boot)
    for i in range(n_boot):
        r = rng.choice(real_hours, size=len(real_hours), replace=True)
        s = rng.choice(sim_hours, size=len(sim_hours), replace=True)
        f1 = circular_kde(r, grid, bandwidth)
        f2 = circular_kde(s, grid, bandwidth)
        f1 = f1 / max(f1.sum() * dx, 1e-12)
        f2 = f2 / max(f2.sum() * dx, 1e-12)
        deltas[i] = overlap_coefficient(f1, f2, dx)

    lo, med, hi = np.percentile(deltas, [2.5, 50, 97.5])
    if return_samples:
        return float(lo), float(med), float(hi), deltas
    return float(lo), float(med), float(hi)


# =========================================================
# 4) Diagramme (von Skript UND Streamlit-Seite gemeinsam genutzt -
#    eine einzige Implementierung, damit beide niemals auseinanderlaufen)
# =========================================================
def build_activity_overlap_figure(grid, f_real, f_sim, delta, ci_low, ci_high, n_real, n_sim):
    """Erzeugt die Vergleichs-Abbildung als matplotlib-Figure (wird NICHT
    gespeichert - das macht der Aufrufer, je nach Kontext unterschiedlich:
    Skript -> Datei, Streamlit-Seite -> st.pyplot())."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.axvspan(18, 24, color="black", alpha=0.05, label="Nacht (18–06 Uhr)")
    ax.axvspan(0, 6, color="black", alpha=0.05)
    ax.plot(grid, f_real, color="#1d6fb8", lw=2.2, label=f"Echte Detektionen (Japan, n={n_real})")
    ax.plot(grid, f_sim, color="#e8830c", lw=2.2, label=f"Simulierter Bär (Carpathian-Modell, n={n_sim})")
    ax.fill_between(grid, np.minimum(f_real, f_sim), color="#6b6b6b", alpha=0.35,
                     label=f"Überlappung (Δ={delta:.2f})")
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 2))
    ax.set_xlabel("Uhrzeit")
    ax.set_ylabel("Aktivitätsdichte")
    ax.set_title(f"Tagesrhythmus-Vergleich: Δ = {delta:.2f}  (95%-Bootstrap-KI [{ci_low:.2f}, {ci_high:.2f}])")
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()
    return fig


def build_bootstrap_histogram_figure(deltas: np.ndarray, delta_point: float, ci_low: float, ci_high: float):
    """Histogramm der Bootstrap-Delta-Werte mit Punktschaetzung + Konfidenzband."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.hist(deltas, bins=40, color="#8fb8dd", edgecolor="white")
    ax.axvline(delta_point, color="black", lw=2.2, label=f"Δ aus den Originaldaten = {delta_point:.2f}")
    ax.axvline(ci_low, color="#c0392b", lw=1.8, ls="--", label=f"95%-Grenzen: [{ci_low:.2f}, {ci_high:.2f}]")
    ax.axvline(ci_high, color="#c0392b", lw=1.8, ls="--")
    ax.axvspan(ci_low, ci_high, color="#c0392b", alpha=0.08)
    ax.set_xlabel("Δ-Wert einer einzelnen Wiederholung")
    ax.set_ylabel(f"Anzahl der {len(deltas)} Wiederholungen")
    ax.set_title("Bootstrap: wie stark streut Δ bei leicht anderer Stichprobe?")
    ax.legend(fontsize=9)
    fig.tight_layout()
    return fig


def plot_activity_overlap(grid, f_real, f_sim, delta, ci_low, ci_high,
                           n_real, n_sim, out_path="activity_overlap.png"):
    """Duenner Wrapper um build_activity_overlap_figure() fuer den
    Kommandozeilen-Gebrauch (speichert zusaetzlich als Datei)."""
    import matplotlib.pyplot as plt
    fig = build_activity_overlap_figure(grid, f_real, f_sim, delta, ci_low, ci_high, n_real, n_sim)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


# =========================================================
# 5) Gesamtablauf
# =========================================================
def run_full_analysis(
    n_runs: int = 300,
    hours_per_run: int = 48,
    detection_radius_m: float = DETECTION_RADIUS_M,
    bandwidth: float = 1.5,
    n_boot: int = 1000,
    use_terrain: bool = False,
    seed: int = 42,
    out_path: str = "activity_overlap.png",
) -> dict | None:
    print("=" * 70)
    print("Tagesrhythmus-Vergleich: echte Japan-Detektionen vs. simulierter Bär")
    print("=" * 70)

    print(f"Starte Monte-Carlo-Simulation: {n_runs} Läufe × {hours_per_run}h "
          f"(Erfassungsradius {detection_radius_m}m)...")
    result = compute_comparison(
        n_runs=n_runs, hours_per_run=hours_per_run, detection_radius_m=detection_radius_m,
        bandwidth=bandwidth, n_boot=n_boot, use_terrain=use_terrain, seed=seed,
    )

    if not result["db_ok"]:
        print("[Hinweis] MariaDB nicht erreichbar (VPN aktiv?) - "
              "es wird nur die simulierte Seite berechnet, kein Vergleich möglich.")
    else:
        print(f"Echte Detektionen: {result['n_real']} "
              f"({result['n_excluded']} Platzhalter-Geräte-IDs ausgeschlossen)")
        if result["n_real"] < 20:
            print("[Hinweis] Kleine Stichprobe (<20) - Ergebnis nur explorativ interpretierbar, "
                  "siehe Bootstrap-Konfidenzintervall unten.")

    print(f"Virtuelle Detektionen (simuliert): {result['n_sim']}")
    if not result["n_sim"]:
        print("Keine virtuellen Detektionen erzeugt - Radius vergrößern oder mehr Läufe/Stunden.")
        return None
    if not result["n_real"]:
        print("\nKein Vergleich möglich ohne echte Daten (siehe Hinweis oben).")
        return result

    print(f"\nÜberlappungskoeffizient Δ = {result['delta']:.3f}")
    print(f"95%-Bootstrap-Konfidenzintervall: [{result['ci_low']:.3f}, {result['ci_high']:.3f}]")

    saved_to = plot_activity_overlap(
        result["grid"], result["f_real"], result["f_sim"], result["delta"],
        result["ci_low"], result["ci_high"],
        n_real=result["n_real"], n_sim=result["n_sim"], out_path=out_path,
    )
    print(f"\nDiagramm gespeichert: {saved_to}")
    result["plot_path"] = saved_to
    return result


def compute_comparison(
    n_runs: int = 300,
    hours_per_run: int = 48,
    detection_radius_m: float = DETECTION_RADIUS_M,
    bandwidth: float = 1.5,
    n_boot: int = 1000,
    use_terrain: bool = False,
    seed: int = 42,
    capture_run: bool = False,
) -> dict:
    """
    Einziger Ort, an dem die komplette Berechnung passiert - vom Konsolen-
    Skript (run_full_analysis) UND von der Streamlit-Seite gleichermassen
    genutzt, damit es niemals zwei Implementierungen gibt, die im Ergebnis
    auseinanderlaufen koennten.

    Wirft KEINE Exception bei fehlender DB-Verbindung - meldet das ueber
    result["db_ok"] = False, result["delta"] = None, laesst aber die
    Simulation trotzdem laufen (z.B. fuer die Kartenanimation allein).
    """
    db = WildlifeDatabase()
    db_ok = check_db_reachable_bounded(db)
    real_hours, n_excluded = ([], 0)
    if db_ok:
        real_hours, n_excluded = get_real_detection_hours(db)

    terrain_cache = None
    if use_terrain:
        from terrain_cache import TerrainCache
        terrain_cache = TerrainCache()

    sim_hours, captured_run = run_monte_carlo_virtual_detections(
        n_runs=n_runs, hours_per_run=hours_per_run,
        detection_radius_m=detection_radius_m, seed=seed,
        terrain_cache=terrain_cache, capture_run=capture_run,
    )

    result = {
        "db_ok": db_ok, "n_real": len(real_hours), "n_excluded": n_excluded,
        "n_sim": len(sim_hours), "sim_hours": sim_hours, "real_hours": real_hours,
        "captured_run": captured_run,
        "delta": None, "ci_low": None, "ci_high": None,
        "grid": None, "f_real": None, "f_sim": None, "boot_deltas": None,
    }

    if not sim_hours or not real_hours:
        return result

    grid = np.linspace(0, 24, 481)
    dx = grid[1] - grid[0]
    f_real = circular_kde(real_hours, grid, bandwidth)
    f_sim = circular_kde(sim_hours, grid, bandwidth)
    f_real = f_real / max(f_real.sum() * dx, 1e-12)
    f_sim = f_sim / max(f_sim.sum() * dx, 1e-12)
    delta = overlap_coefficient(f_real, f_sim, dx)
    ci_low, ci_med, ci_high, boot_deltas = bootstrap_delta_ci(
        real_hours, sim_hours, grid, bandwidth, n_boot=n_boot, seed=seed, return_samples=True,
    )

    result.update({
        "delta": delta, "ci_low": ci_low, "ci_high": ci_high,
        "grid": grid, "f_real": f_real, "f_sim": f_sim, "boot_deltas": boot_deltas,
    })
    return result


if __name__ == "__main__":
    run_full_analysis()