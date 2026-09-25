"""
pages/3_Japan_Experiment.py
=============================
Japan-Experiment (Version 2): EINE Kamera waehlen, N simulierte Baeren
starten dort GENAU an einem echten Foto-Ereignis (Ort + Zeit) und bewegen
sich animiert nach dem rumaenischen Modell (Geschwindigkeit, optionale
Gelaendegewichtung, Richtungstraegheit). Echte Fotozeiten AN DIESER KAMERA
werden zusaetzlich als rote Striche auf derselben Zeitleiste markiert -
direkter visueller Vergleich, keine Statistik-Kenntnis noetig, um die
Kernfrage des Protokolls zu verstehen ("kommen simulierte Baeren zu
aehnlichen Zeiten wie echte Sichtungen?").

Kein "Gesamt"-Zeitfenster (anders als bei Carpathian): die Simulation hat
kein natuerliches Ende, nur feste Fenster 15 Min bis 72 Std.

Die fruehere Monte-Carlo-Statistik (Δ, Bootstrap ueber ALLE Kameras/Laeufe,
siehe activity_overlap.py) bleibt bestehen, ruetscht aber zur VERTIEFENDEN
Analyse unten (eingeklappt) - die Animation oben ist jetzt die Hauptsache,
weil sie die Fragestellung direkt und ohne Vorwissen beantwortet.
"""

import streamlit as st
import pandas as pd
from datetime import datetime

import activity_overlap as ao
import japan_map_component as jm
from geojson_table_helper import geojson_to_dataframe
from japan_comparison import (
    load_japan_cameras, get_real_events_for_camera, simulate_multiple_bears_from_sighting,
    get_photo_counts_by_camera, DatabaseConnection, BearSpeeds, SIM_DB_PATH,
)
from wildlife_db_mariadb import WildlifeDatabase

st.set_page_config(page_title="Japan-Experiment", layout="wide")

st.title("Japan-Experiment: simulierte Bären vs. echte Kameras")
st.caption(
    "Eine Kamera wählen - mehrere simulierte Bären starten genau an einem echten "
    "Foto-Ereignis (Ort + Zeit) und bewegen sich nach dem rumänischen Modell. "
    "Rote Striche auf der Zeitleiste zeigen, wann an dieser Kamera tatsächlich fotografiert wurde."
)

# Erklaerung bewusst auf ENGLISCH - siehe gleichlautende Begruendung in
# pages/2_Experimente.py.
with st.expander("What am I looking at?  ·  About this experiment", expanded=False):
    st.markdown("""
**The idea.** Movement patterns learned from GPS-collared brown bears in the
Romanian Carpathians are transferred to a camera-trap landscape in Japan
(Fukushima region, Honshu), where no collar data exists. The question is
whether simulated bears show up near cameras at times comparable to when real
photographs were actually triggered.

**Two very different kinds of data.** The Romanian data is tied to the
*animal*: a collar reports where one known bear is, hour by hour. The Japanese
data is tied to the *place*: a camera reports that some bear passed a fixed
point at a given moment, with no identity and no track. The two cannot be
compared directly — only through the timing and location of encounters.

**What the colours mean.**

| Element | Meaning |
|---|---|
| **Coloured** dots and trails | Simulated bears. All start from the same real photo event — same place, same timestamp — and then move independently. |
| **Grey** dots | Camera locations. Click one for its device ID, coordinates and number of real photographs. |
| **Yellow** flash | A camera lights up when a simulated bear comes within the detection radius. |
| **Red** ticks on the timeline | Times at which a photograph was actually taken at the selected camera. |

**What the animation shows.** Whether simulated bears approach cameras during
the same hours of the day in which real photographs cluster.

In this dataset the triggers are strongly nocturnal: 47 of 50 usable
timestamps (94%) fall between 18:00 and 06:00. That concentration is itself an
observation, not a given. Asian black bears are generally described in the
literature as cathemeral — active during both day and night — so a near-absence
of daytime triggers is something the data shows rather than something the
species dictates. One plausible reading is avoidance of humans: these cameras
are placed at human–wildlife conflict sites, where daytime activity carries a
cost for the animal. With 50 timestamps the pattern is indicative, not
established.

**What it does not show.** Each coloured path is **one random realisation** of
the model, not a prediction of where a bear went. Re-running with a different
seed produces different paths. A single run proves nothing; the quantitative
answer comes from the statistical comparison further down the page, which pools
many runs across all cameras into an overlap coefficient with a confidence
interval.

**Known limitations.** The Japanese cameras lie in the range of the Asian black
bear (*Ursus thibetanus*), while the model was trained on European brown bears
(*Ursus arctos*) — a deliberate simplification, not an equivalence. The number
of real photo timestamps is small, so results are indicative rather than
conclusive. Terrain weighting, when enabled, uses OpenStreetMap land-use data
with hand-set preferences, not coefficients fitted to observed habitat use.
""")


@st.cache_data(ttl=3600, show_spinner=False)
def _load_cameras():
    return load_japan_cameras()


@st.cache_data(ttl=600, show_spinner=False)
def _check_db():
    return ao.check_db_reachable_bounded(WildlifeDatabase())


@st.cache_data(ttl=600, show_spinner=False)
def _get_real_events(device_id: str):
    db = WildlifeDatabase()
    return get_real_events_for_camera(db, device_id)


@st.cache_data(ttl=600, show_spinner=False)
def _get_photo_counts():
    """Fotozahlen aller Kameras fuer die anklickbaren Kartenpunkte -
    eine einzige Abfrage, gecacht (siehe get_photo_counts_by_camera)."""
    return get_photo_counts_by_camera(WildlifeDatabase())


@st.cache_data(ttl=3600, show_spinner=False)
def _simulate(device_id: str, lat: float, lng: float, start_time_iso: str,
              n_bears: int, hours: int, use_terrain: bool, seed: int):
    """
    Returns:
        (bears, terrain_warning) - terrain_warning ist "" im Normalfall bzw.
        der Grund, warum ohne Gelaendegewichtung gerechnet wurde.

    Die Gelaendegewichtung ist ein Komfortmerkmal: laesst sich der Cache
    nicht oeffnen (beschaedigte oder ueberschriebene terrain_cache.db),
    wird OHNE Gewichtung weitergerechnet statt die Seite abstuerzen zu
    lassen. Der Grund wird nach oben gereicht und dort angezeigt.
    """
    dbcon = DatabaseConnection(SIM_DB_PATH)
    bear_speeds = BearSpeeds(dbcon)
    terrain_cache = None
    terrain_warning = ""

    if use_terrain:
        try:
            from terrain_cache import TerrainCache
            terrain_cache = TerrainCache()
            if getattr(terrain_cache, "disabled", False):
                terrain_warning = terrain_cache.disabled_reason
                terrain_cache = None
        except Exception as e:
            terrain_warning = (
                f"Gelaende-Cache konnte nicht geoeffnet werden ({type(e).__name__}: {e}). "
                "Simulation laeuft ohne Gelaendegewichtung."
            )
            terrain_cache = None

    start_time = datetime.fromisoformat(start_time_iso)
    bears = simulate_multiple_bears_from_sighting(
        start_lat=lat, start_lng=lng, start_time=start_time,
        n_bears=n_bears, duration_hours=hours, bear_speeds=bear_speeds,
        seed=seed, terrain_cache=terrain_cache,
    )
    return bears, terrain_warning


DURATION_OPTIONS = [
    (0.25, "15 Min"), (0.5, "30 Min"), (1, "1 Std"),
    (4, "4 Std"), (24, "24 Std"), (72, "72 Std"),
]

cameras = _load_cameras()
db_ok = _check_db()

# ============================================================
# Sidebar
# ============================================================
with st.sidebar:
    st.header("Auswahl")

    if not db_ok:
        st.warning(
            "MariaDB nicht erreichbar (VPN aktiv?). Simulation funktioniert trotzdem "
            "(Kamerastandorte kommen aus einer lokalen Datei), aber ohne VPN gibt es "
            "keine echten Fotozeiten zum Vergleich."
        )

    if not cameras:
        st.error("Keine Kamerastandorte gefunden (2024Bear/ReadMe.csv im bear_simulation-Ordner?).")
    else:
        cam_labels = {c["device_id"]: f"Kamera {c['device_id']}" for c in cameras}
        selected_cam_id = st.selectbox(
            "Kamera", options=list(cam_labels.keys()), format_func=lambda k: cam_labels[k],
        )
        selected_camera = next(c for c in cameras if c["device_id"] == selected_cam_id)

        real_events = _get_real_events(selected_cam_id) if db_ok else []
        if db_ok:
            st.caption(f"{len(real_events)} echte Foto(s) an dieser Kamera bekannt.")

        with st.form("japan_exp_form"):
            if real_events:
                event_labels = [t.strftime("%d.%m.%Y %H:%M") for t in real_events]
                sel_event_idx = st.selectbox(
                    "Startzeitpunkt (echtes Foto-Ereignis)",
                    options=range(len(real_events)), format_func=lambda i: event_labels[i],
                    index=len(real_events) - 1,
                    help="Die Bären starten genau zu dieser echten Sichtung - Ort und Zeit.",
                )
                start_time = real_events[sel_event_idx]
            else:
                st.info(
                    "Keine echten Fotos an dieser Kamera bekannt (oder keine DB-Verbindung) - "
                    "Startzeit muss frei gewählt werden, kein Realitätsabgleich möglich."
                )
                start_date = st.date_input("Startdatum", value=datetime(2024, 6, 1).date())
                start_hour = st.slider("Startuhrzeit", 0, 23, 20)
                start_time = datetime.combine(start_date, datetime.min.time()).replace(hour=start_hour)

            n_bears = st.slider("Anzahl simulierter Bären", 1, 20, 6)

            dur_label = st.select_slider(
                "Zeitfenster", options=[label for _, label in DURATION_OPTIONS], value="24 Std",
                help="Kein 'Gesamt' möglich - die Simulation hat kein natürliches Ende.",
            )
            hours = next(v for v, label in DURATION_OPTIONS if label == dur_label)

            detection_radius_m = st.slider("Erfassungsradius der Kameras (m)", 50, 300, 100, step=25)

            use_terrain = st.checkbox(
                "Geländegewichtung (Wald bevorzugt)", value=False,
                help="Nutzt OpenStreetMap-Geländedaten, damit Bären eher durch Wald statt Dörfer "
                     "laufen. Braucht Internetzugriff auf Overpass - kann den ersten Lauf an einem "
                     "neuen Ort spürbar verlangsamen.",
            )
            seed = st.number_input("Zufalls-Seed", min_value=0, max_value=999999, value=42)

            submitted = st.form_submit_button("Simulieren", type="primary")

        if submitted:
            st.session_state["japan_exp2_params"] = (
                selected_cam_id, selected_camera["lat"], selected_camera["lng"],
                start_time.isoformat(), n_bears, int(hours), use_terrain, int(seed),
            )
            st.session_state["japan_exp2_real_events"] = real_events

    st.markdown("---")
    st.caption(
        "Rote Striche auf der Zeitleiste = echte Fotozeiten an der gewählten Kamera. "
        "Kameras auf der Karte leuchten auf, sobald ein simulierter Bär in Reichweite kommt."
    )

# ============================================================
# Hauptbereich: Animation
# ============================================================
if "japan_exp2_params" not in st.session_state:
    st.info("Links Kamera, Startzeitpunkt und Anzahl Bären wählen, dann **Simulieren** klicken.")
else:
    (cam_id, lat, lng, start_time_iso, n_bears, hours,
     use_terrain, seed) = st.session_state["japan_exp2_params"]
    real_events = st.session_state.get("japan_exp2_real_events", [])
    start_camera = {"device_id": cam_id, "lat": lat, "lng": lng}

    with st.spinner(f"Simuliere {n_bears} Bären ab Kamera {cam_id}..."):
        bears, terrain_warning = _simulate(
            cam_id, lat, lng, start_time_iso, n_bears, hours, use_terrain, seed
        )

    if terrain_warning:
        st.warning(terrain_warning)

    jm.render_japan_map(
        cameras=cameras, start_camera=start_camera, bears=bears,
        # None (nicht {}) bei fehlender DB - siehe render_japan_map():
        # {} hiesse "erreichbar, aber ueberall null Fotos".
        real_events=real_events, photo_counts=_get_photo_counts() if db_ok else None,
        height=850,
    )

    st.markdown("### Daten zur aktuellen Ansicht")
    _tabs = st.tabs(["Kamerastandorte", "Echte Fotozeiten (Startkamera)", "Simulierte Bärenpfade"])

    with _tabs[0]:
        df_cam = pd.DataFrame(cameras)
        st.caption(f"{len(df_cam)} Kamerastandorte aus 2024Bear/ReadMe.csv")
        st.dataframe(df_cam, width="stretch")

    with _tabs[1]:
        if real_events:
            df_events = pd.DataFrame({"zeitstempel": real_events})
            st.caption(f"{len(df_events)} echte Fotos an Kamera {cam_id}")
            st.dataframe(df_events, width="stretch")
        else:
            st.info("Keine echten Fotos bekannt (oder keine DB-Verbindung).")

    with _tabs[2]:
        rows = []
        for b in bears:
            for p in b["path"]:
                rows.append({
                    "bär": f"Bär {b['bear_index'] + 1}", "geschlecht": b["gender"],
                    "alter": b["age"], "saison": b["season"],
                    "zeit": p["time"], "lat": p["lat"], "lng": p["lng"],
                })
        df_bears = pd.DataFrame(rows)
        st.caption(f"{len(df_bears)} simulierte Positionen über {len(bears)} Bären")
        st.dataframe(df_bears, width="stretch")

    # ============================================================
    # Vertiefende Analyse (eingeklappt, sekundär - siehe Docstring)
    # ============================================================
    with st.expander("Vertiefende Analyse: statistischer Vergleich über alle Kameras"):
        st.caption(
            "Ergänzt die Animation oben um einen strengeren, aggregierten Vergleich: "
            "viele simulierte Läufe über ALLE Kameras hinweg, gegen alle echten Detektionen, "
            "als eine Kennzahl mit Unsicherheitsbereich (Δ, Bootstrap)."
        )
        n_runs = st.slider("Anzahl Simulationsläufe (für die Statistik)", 50, 500, 150, step=50)

        with st.spinner(f"Berechne Statistik über {n_runs} Läufe..."):
            stat_result = ao.compute_comparison(n_runs=n_runs, hours_per_run=48, seed=seed)

        if not stat_result["db_ok"]:
            st.info("MariaDB nicht erreichbar - kein statistischer Vergleich möglich.")
        elif stat_result["delta"] is None:
            st.warning("Zu wenig Daten für einen statistischen Vergleich.")
        else:
            col1, col2, col3 = st.columns(3)
            col1.metric("Überlappungskoeffizient Δ", f"{stat_result['delta']:.2f}")
            col2.metric("95%-Konfidenzintervall", f"[{stat_result['ci_low']:.2f}, {stat_result['ci_high']:.2f}]")
            col3.metric("Echte / simulierte Detektionen", f"{stat_result['n_real']} / {stat_result['n_sim']}")

            fig1 = ao.build_activity_overlap_figure(
                stat_result["grid"], stat_result["f_real"], stat_result["f_sim"], stat_result["delta"],
                stat_result["ci_low"], stat_result["ci_high"], stat_result["n_real"], stat_result["n_sim"],
            )
            st.pyplot(fig1, clear_figure=True)

            fig2 = ao.build_bootstrap_histogram_figure(
                stat_result["boot_deltas"], stat_result["delta"], stat_result["ci_low"], stat_result["ci_high"],
            )
            st.pyplot(fig2, clear_figure=True)