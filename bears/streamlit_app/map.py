"""
map.py
======
Hauptanwendung: EINE gemeinsame Karte fuer alle drei Systeme.

Aufbau:
  - Sidebar oben: Status-Widget (neue Bilder)
  - Sidebar: Kartenstil + Filter pro System (Carpathian, Japan-Bilder, Simulation)
  - Hauptbereich: EINE MapLibre-Karte. Die AUSWAHL der Layer passiert direkt
    AUF DER KARTE (oben links). Beim Start sieht man nur die Karte ohne Daten.
    Haken setzen -> Layer erscheint und die Karte zoomt automatisch darauf.

Wichtig (IT-Hinweis):
  Die Daten aller Systeme werden im Hintergrund vorbereitet (gecacht) und in die
  Karte eingebettet. Die Checkboxen auf der Karte blenden sie nur ein/aus + zoomen.
  So funktioniert die Auswahl ganz auf der Karte, ohne dass die Seite neu laedt.
"""

import streamlit as st
from datetime import datetime

from status_widget import display_new_images_status
import maplibre_component as ml

st.set_page_config(page_title="Wildlife Movement Analysis System", layout="wide")

# ============================================================
# Sidebar: Status-Widget + Kartenstil
# ============================================================
with st.sidebar:
    try:
        display_new_images_status(position="sidebar")
    except Exception as e:
        st.error(f"Status-Widget nicht verfügbar (DB-Verbindung?): {e}")
    st.markdown("---")

st.sidebar.caption("Layer und Kartenstil wählst du direkt auf der Karte (oben links).")
st.sidebar.markdown("---")

st.title("Wildlife Movement Analysis System")

# Daten-Container fuer jedes System (werden vorgeladen)
japan_data = None
carpathian_data = None
simulation_data = None


# ============================================================
# JAPAN  (immer vorgeladen - leichtgewichtig)
# ============================================================
try:
    from japan_deterrents import JapanDeterrentSystem

    @st.cache_resource
    def _get_japan_system():
        return JapanDeterrentSystem()

    jp = _get_japan_system()
    japan_data = {
        "deterrents": jp._df_to_geojson_points(jp.deterrent_data, kind="deterrent"),
        "markers": jp._df_to_geojson_points(jp.existing_markers, kind="marker"),
        "polygons": jp._polygons_to_geojson(jp.existing_polygons),
    }

    # Japan-Bilder/Geraete-Browser (eigene Sidebar-Logik der Klasse)
    jp.display_device_images_in_sidebar()
    st.sidebar.markdown("---")

except Exception as e:
    st.error(f"Fehler beim Laden des Japan-Systems: {e}")


# ============================================================
# CARPATHIAN  (Filter als Form -> laedt nur bei "Anwenden" neu)
# ============================================================
try:
    from carpathian_bears import get_carpathian_geojson, get_carpathian_options

    bears, seasons, min_date, max_date = get_carpathian_options()

    with st.sidebar.expander("Carpathian: Filter", expanded=False):
        if not bears:
            st.info("Keine Carpathian-Daten gefunden.")
            sel_bears, sel_seasons = [], []
            sd, ed = min_date, max_date
            map_type, max_pts = "Movement Paths", 3000
        else:
            with st.form("cp_form"):
                select_all = st.checkbox("Alle Bären", value=False)
                bears_choice = st.multiselect(
                    "Bären", bears, default=bears[: min(2, len(bears))]
                )
                sel_seasons = st.multiselect("Saison", seasons, default=seasons)
                date_range = st.date_input(
                    "Zeitraum", value=(min_date, max_date),
                    min_value=min_date, max_value=max_date,
                )
                map_type = st.selectbox("Darstellung", ["Movement Paths", "Daily Positions"], index=0)
                max_pts = st.slider("Max. Punkte/Bär", 300, 20000, 3000, 100)
                st.form_submit_button("Anwenden", type="primary")

            sel_bears = bears if select_all else bears_choice
            if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
                sd, ed = date_range
            else:
                sd, ed = min_date, max_date

    start_dt = datetime.combine(sd, datetime.min.time())
    end_dt = datetime.combine(ed, datetime.max.time())

    if sel_bears:
        with st.spinner("Bereite Carpathian-Daten vor..."):
            carpathian_data = get_carpathian_geojson(
                selected_bears=sel_bears,
                start_datetime=start_dt,
                end_datetime=end_dt,
                selected_seasons=sel_seasons,
                map_type=map_type,
                max_points_per_bear=max_pts,
            )

except Exception as e:
    st.error(f"Fehler beim Laden der Carpathian-Daten: {e}")


# ============================================================
# SIMULATION  (Fabian Breus StepSelectionModel - vollstaendige Integration)
# Wird immer vorgeladen (Default: erster Baer, 10 Alternativen)
# -> Checkbox auf der Karte ist von Anfang an verfuegbar
# ============================================================
try:
    from bear_simulation import get_simulation_geojson, get_simulation_options, SEASON_ORDER

    sim_bear_ids, sim_seasons_info = get_simulation_options()

    with st.sidebar.expander("Bear Simulation: Filter", expanded=False):
        if not sim_bear_ids:
            st.warning(
                "bear_simulation/data/database.db nicht gefunden. "
                "Bitte Inhalt von bearsimulation-master in bear_simulation/ kopieren."
            )
            _sim_bear   = None
            _sim_season = None
            _sim_num_alt = 10
        else:
            # ── welcher Bär ist gerade "committed" (nach letztem Anwenden)? ──
            _committed_bear = st.session_state.get(
                "sim_committed_bear", str(sim_bear_ids[0])
            )
            # Saisons für den committed Bären (vor dem Submit)
            _avail_seasons = sim_seasons_info.get(_committed_bear, {})
            # Sortiert nach definierer Reihenfolge, fehlende ans Ende
            _sorted_seasons = sorted(
                _avail_seasons.keys(),
                key=lambda s: SEASON_ORDER.index(s) if s in SEASON_ORDER else 99,
            )
            # Lesbare Labels: "Autumn", "Summer", ...
            _season_labels = [s.capitalize() for s in _sorted_seasons]

            with st.form("sim_form"):
                _sim_bear = st.selectbox(
                    "Bär auswählen",
                    sim_bear_ids,
                    index=sim_bear_ids.index(_committed_bear)
                          if _committed_bear in sim_bear_ids else 0,
                    key="sim_bear_sel",
                    help="Nur Bären mit mindestens 5 GPS-Schritten werden angezeigt",
                )
                if _season_labels:
                    _sim_season_label = st.selectbox(
                        "Saison",
                        _season_labels,
                        help="Jede Option zeigt die exakte Anzahl echter GPS-Schritte "
                             "für diesen Bären in dieser Saison",
                    )
                    # Saison-Schlüssel aus Label extrahieren (z. B. "Autumn" → "autumn")
                    _sim_season = _sim_season_label.lower()
                else:
                    st.info("Keine Saisondaten für diesen Bären verfügbar.")
                    _sim_season_label = None
                    _sim_season = None

                _sim_num_alt = st.slider(
                    "Alternativen pro Schritt",
                    min_value=3, max_value=20, value=10,
                    help="Anzahl simulierter Alternativpositionen pro echtem GPS-Schritt",
                )
                submitted = st.form_submit_button("Anwenden", type="primary")
                if submitted:
                    st.session_state["sim_committed_bear"] = str(_sim_bear)

    # Immer laden → Simulation-Checkbox auf der Karte sofort verfügbar
    if sim_bear_ids and _sim_bear is not None and _sim_season is not None:
        with st.spinner("Lade Simulationsdaten..."):
            simulation_data = get_simulation_geojson(
                bear_id=str(_sim_bear),
                season=_sim_season,
                num_alternatives=_sim_num_alt,
            )
        # Status-Caption
        feats  = simulation_data.get("points", {}).get("features", [])
        n_real = sum(1 for f in feats if f["properties"].get("type") == "real")
        n_alt  = sum(1 for f in feats if f["properties"].get("type") == "alternative")
        if n_alt > 0:
            _season_disp = _sim_season.capitalize()
            _total = n_real + n_alt
            st.sidebar.caption(
                f"🐻 Bär {_sim_bear} · {_season_disp}: "
                f"{n_real} echte Schritte × {_sim_num_alt} Alternativen "
                f"= {_total} Punkte gesamt"
            )
        else:
            st.sidebar.caption(
                f"🐻 Bär {_sim_bear}: {n_real} GPS-Punkte (Fallback-Modus)"
            )

except ImportError:
    pass
except Exception as e:
    st.error(f"Fehler beim Laden der Simulation: {e}")


# ============================================================
# Karte rendern (Startansicht leer; Auswahl + Zoom auf der Karte)
# ============================================================
ml.render_maplibre(
    japan=japan_data,
    carpathian=carpathian_data,
    simulation=simulation_data,
    basemap="Liberty",   # Start-Stil; Wechsel passiert auf der Karte
    center=None,
    zoom=None,
    height=800,
)

st.caption(
    "Oben links auf der Karte die Layer an-/abhaken. Beim Anhaken zoomt die Karte "
    "automatisch auf die jeweiligen Daten. Welche Bären/Filter geladen werden, "
    "stellst du links in der Sidebar ein."
)

# ============================================================
# Footer
# ============================================================
st.markdown(
    """
---
### Über diese Anwendung

Integriertes System für:
1. **Japan Bear Deterrent System** – Abschreckungsgeräte und Kamerabilder in Japan
2. **Carpathian Bears Movement** – Bewegungsmuster von Braunbären in den Karpaten
3. **Bear Movement Simulation** – ML-basierte Vorhersage von Bärenbewegungen

Entwickelt für Wildtierforschung und -management.
"""
)