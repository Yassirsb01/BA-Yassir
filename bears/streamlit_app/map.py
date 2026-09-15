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
from geojson_table_helper import geojson_to_dataframe

st.set_page_config(page_title="Wildlife Movement Analysis System", layout="wide")

# ============================================================
# Kartenzustand aus der URL wiederherstellen (falls vorhanden).
# maplibre_component.py schreibt Center/Zoom/Basemap/sichtbare Layer bei
# jeder Interaktion in die Query-Parameter (window.parent.history.replaceState).
# Bei einem Rerun (z.B. Filter "Anwenden") sind sie hier schon in der URL und
# koennen ausgelesen werden -> Karte startet an der zuletzt gesehenen Stelle
# statt wieder bei der Default-Ansicht.
# ============================================================
def _restore_map_state():
    qp = st.query_params

    def _qf(key):
        v = qp.get(key)
        try:
            return float(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            return None

    lat, lng, zoom = _qf("m_lat"), _qf("m_lng"), _qf("m_zoom")
    center = (lat, lng) if (lat is not None and lng is not None) else None

    basemap = qp.get("m_style") or "Liberty"
    if basemap not in ml.BASEMAP_NAMES:
        basemap = "Liberty"

    layers_raw = qp.get("m_layers", "")
    # Bei allererstem Aufruf (kein Query-Param vorhanden) -> None zurueckgeben,
    # damit render_maplibre() auf die alte Default-Logik (Simulation an) faellt.
    initial_visible = set(layers_raw.split(",")) if layers_raw else None

    return center, zoom, basemap, initial_visible


_restored_center, _restored_zoom, _restored_basemap, _restored_visible = _restore_map_state()

# Layer, deren zugrunde liegende Daten sich in diesem Rerun geaendert haben
# (z.B. anderer Baer/Zeitraum gewaehlt) -> sollen automatisch angeflogen
# werden, auch wenn sie schon vorher sichtbar waren (siehe Carpathian-/
# Simulation-Bloecke weiter unten).
_refit_groups = set()


def _mark_refit_if_changed(session_key: str, new_signature, group_name: str):
    """Vergleicht die aktuelle Filter-Signatur mit der vom letzten Rerun.
    Bei Aenderung wird group_name zu _refit_groups hinzugefuegt, damit die
    Karte beim naechsten Laden dorthin navigiert statt an der alten Kamera-
    position (aus der URL-Persistenz) stehen zu bleiben."""
    old_signature = st.session_state.get(session_key)
    if old_signature != new_signature:
        _refit_groups.add(group_name)
    st.session_state[session_key] = new_signature

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

    # ------------------------------------------------------------
    # Neue Marker/Gebiete verarbeiten, die per Karten-Zeichenfunktion
    # (maplibre_component.py, saveDrawing()) als URL-Parameter ankommen.
    # Laeuft VOR dem Laden der Kartendaten, damit der neue Eintrag sofort
    # sichtbar ist, sobald die Seite (nach dem Speichern-Klick per echter
    # Navigation neu geladen) hier ankommt. Cache wird explizit geleert,
    # sonst wuerde die alte, gecachte JapanDeterrentSystem-Instanz weiter
    # die Daten von VOR dem Speichern zeigen.
    # ------------------------------------------------------------
    qp = st.query_params

    if "new_marker_lat" in qp and "new_marker_lng" in qp:
        try:
            lat = float(qp["new_marker_lat"])
            lng = float(qp["new_marker_lng"])
            from wildlife_db_mariadb import WildlifeDatabase
            db = WildlifeDatabase()
            new_id = db.get_next_marker_id()
            if db.save_marker(new_id, lat, lng):
                st.toast(f"Marker {new_id} gespeichert.", icon="✅")
                _get_japan_system.clear()
            else:
                st.error("Marker konnte nicht gespeichert werden (Datenbankverbindung/VPN prüfen).")
        except Exception as e:
            st.error(f"Fehler beim Speichern des Markers: {e}")
        finally:
            del st.query_params["new_marker_lat"]
            del st.query_params["new_marker_lng"]
            st.rerun()

    if "new_polygon_coords" in qp and "new_polygon_name" in qp:
        try:
            import json as _json
            coords = _json.loads(qp["new_polygon_coords"])
            name = qp["new_polygon_name"]
            from wildlife_db_mariadb import WildlifeDatabase
            db = WildlifeDatabase()
            new_id = db.get_next_polygon_id()
            polygon_id = f"poly-{new_id}"
            if db.save_polygon(polygon_id, name, coords):
                st.toast(f"Gebiet „{name}“ gespeichert.", icon="✅")
                _get_japan_system.clear()
            else:
                st.error("Gebiet konnte nicht gespeichert werden (Datenbankverbindung/VPN prüfen).")
        except Exception as e:
            st.error(f"Fehler beim Speichern des Gebiets: {e}")
        finally:
            del st.query_params["new_polygon_coords"]
            del st.query_params["new_polygon_name"]
            st.rerun()

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
        _mark_refit_if_changed(
            "cp_filter_sig",
            (tuple(sorted(sel_bears)), tuple(sorted(sel_seasons)), str(sd), str(ed), map_type, max_pts),
            "carpathian",
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
        _mark_refit_if_changed(
            "sim_filter_sig",
            (str(_sim_bear), _sim_season, _sim_num_alt),
            "simulation",
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
# WOLF/LUCHS (BfN) + BÄR-SICHTUNGEN (GBIF) - externe, oeffentliche APIs
# Kein VPN noetig (anders als die MariaDB-Systeme), aber eigener Haken in
# der Sidebar, falls jemand offline arbeitet oder die Anfragen bewusst
# vermeiden will.
# ============================================================
wolf_lynx_data = None
gbif_bears_data = None

with st.sidebar.expander("Externe Vergleichsdaten", expanded=False):
    load_external = st.checkbox(
        "Wolf/Luchs (BfN) + Bär-Sichtungen (GBIF) laden",
        value=True,
        help="Kostenfreie, oeffentliche Datenquellen. Wolf/Luchs vom "
             "Bundesamt fuer Naturschutz, Baer-Sichtungen von GBIF "
             "(Deutschland + Rumaenien).",
    )

if load_external:
    try:
        from import_bfn_wolf_lynx import get_wolf_lynx_geojson
        wolf_lynx_data = get_wolf_lynx_geojson()
    except Exception as e:
        st.sidebar.warning(f"Wolf/Luchs-Daten (BfN) nicht verfügbar: {e}")

    try:
        from import_gbif_bears import get_gbif_bears_geojson
        gbif_bears_data = get_gbif_bears_geojson()
    except Exception as e:
        st.sidebar.warning(f"Bär-Sichtungen (GBIF) nicht verfügbar: {e}")


# ============================================================
# Karte rendern (Startansicht leer; Auswahl + Zoom auf der Karte)
# ============================================================
ml.render_maplibre(
    japan=japan_data,
    carpathian=carpathian_data,
    simulation=simulation_data,
    wolf_lynx=wolf_lynx_data,
    gbif_bears=gbif_bears_data,
    basemap=_restored_basemap,       # zuletzt gewaehlter Stil, sonst "Liberty"
    center=_restored_center,          # zuletzt gesehene Kameraposition, sonst Default
    zoom=_restored_zoom,
    initial_visible=_restored_visible,  # zuletzt sichtbare Layer, sonst alte Default-Logik
    refit_on_load=_refit_groups,      # Layer mit geaenderten Filterdaten -> neu hinfliegen
    height=800,
)

st.caption(
    "Oben links auf der Karte die Layer an-/abhaken. Beim Anhaken zoomt die Karte "
    "automatisch auf die jeweiligen Daten. Welche Bären/Filter geladen werden, "
    "stellst du links in der Sidebar ein."
)

# ============================================================
# Datentabellen unter der Karte - dieselben Daten, die auch auf der Karte
# dargestellt werden (direkt aus denselben Variablen, keine zweite Abfrage),
# damit sich das Kartenbild anhand der Rohdaten nachvollziehen laesst.
# ============================================================
st.markdown("### Daten zur aktuellen Kartenansicht")

_table_tabs = st.tabs([
    "Japan-Geräte", "Japan Marker/Gebiete", "Carpathian GPS",
    "Simulation", "Wolf/Luchs", "GBIF Bär-Sichtungen",
])

with _table_tabs[0]:
    df = geojson_to_dataframe((japan_data or {}).get("deterrents"))
    st.caption(f"{len(df)} Abschreckungsgeräte" if not df.empty else "Keine Daten geladen.")
    if not df.empty:
        st.dataframe(df, width="stretch")

with _table_tabs[1]:
    df_m = geojson_to_dataframe((japan_data or {}).get("markers"))
    df_p = geojson_to_dataframe((japan_data or {}).get("polygons"))
    st.caption(f"{len(df_m)} Marker, {len(df_p)} Gebiete/Polygone")

    if not df_m.empty:
        st.markdown("**Marker**")
        st.dataframe(df_m, width="stretch")
        with st.expander("Marker löschen"):
            del_marker_id = st.selectbox("Zu löschender Marker", df_m["id"], key="del_marker_sel")
            confirm_marker = st.checkbox("Ja, wirklich löschen", key="confirm_del_marker")
            if st.button("Marker löschen", disabled=not confirm_marker, key="btn_del_marker"):
                from wildlife_db_mariadb import WildlifeDatabase
                if WildlifeDatabase().delete_marker(del_marker_id):
                    st.toast(f"Marker {del_marker_id} gelöscht.", icon="🗑️")
                    _get_japan_system.clear()
                    st.rerun()
                else:
                    st.error("Löschen fehlgeschlagen (Datenbankverbindung/VPN prüfen).")

    if not df_p.empty:
        st.markdown("**Gebiete**")
        st.dataframe(df_p, width="stretch")
        with st.expander("Gebiet löschen"):
            _poly_labels = {row["polygon_id"]: f"{row.get('name', '')} ({row['polygon_id']})" for _, row in df_p.iterrows()}
            del_poly_id = st.selectbox(
                "Zu löschendes Gebiet", options=list(_poly_labels.keys()),
                format_func=lambda k: _poly_labels[k], key="del_poly_sel",
            )
            confirm_poly = st.checkbox("Ja, wirklich löschen", key="confirm_del_poly")
            if st.button("Gebiet löschen", disabled=not confirm_poly, key="btn_del_poly"):
                from wildlife_db_mariadb import WildlifeDatabase
                if WildlifeDatabase().delete_polygon(del_poly_id):
                    st.toast(f"Gebiet {del_poly_id} gelöscht.", icon="🗑️")
                    _get_japan_system.clear()
                    st.rerun()
                else:
                    st.error("Löschen fehlgeschlagen (Datenbankverbindung/VPN prüfen).")

    if df_m.empty and df_p.empty:
        st.info("Keine Marker/Gebiete in der Datenbank.")

with _table_tabs[2]:
    df = geojson_to_dataframe((carpathian_data or {}).get("points"))
    st.caption(f"{len(df)} GPS-Punkte im aktuell gewählten Zeitraum/Filter" if not df.empty else "Keine Daten geladen.")
    if not df.empty:
        st.dataframe(df, width="stretch")

with _table_tabs[3]:
    df = geojson_to_dataframe((simulation_data or {}).get("points"))
    st.caption(f"{len(df)} simulierte Punkte (echt + Alternativen)" if not df.empty else "Keine Daten geladen.")
    if not df.empty:
        st.dataframe(df, width="stretch")

with _table_tabs[4]:
    df = geojson_to_dataframe(wolf_lynx_data)
    st.caption(f"{len(df)} Rasterzellen (Wolf + Luchs)" if not df.empty else "Keine Daten geladen (Haken bei „Externe Vergleichsdaten“ gesetzt?).")
    if not df.empty:
        st.dataframe(df, width="stretch")

with _table_tabs[5]:
    df = geojson_to_dataframe(gbif_bears_data)
    st.caption(f"{len(df)} Bär-Sichtungen (DE + RO)" if not df.empty else "Keine Daten geladen (Haken bei „Externe Vergleichsdaten“ gesetzt?).")
    if not df.empty:
        st.dataframe(df, width="stretch")

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