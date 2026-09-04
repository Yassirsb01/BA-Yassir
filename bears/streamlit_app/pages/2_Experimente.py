"""
pages/2_Experimente.py
========================
Eigene Seite fuer Bewegungs-Animation: echte GPS-Route + zugehoerige
Alternativ-Kandidaten aus Fabians Modell - GARANTIERT derselbe Baer,
derselbe Tag (siehe sync_simulation.py).

Wichtig, nach Ruecksprache mit Prof. Duennweber (Meeting 21.08.2026):
Ziel ist "echte und simulierte Bewegung nebeneinander, zur
Realitaetspruefung der KI-Simulation" - das erfordert EINE gemeinsame
Bären-/Tages-Auswahl, nicht zwei unabhaengige (wie in der ersten Version
dieser Seite, die zwei potenziell unzusammenhaengende Datensaetze
nebeneinander zeigte).

Performance-Prinzip: server-seitig immer nur EIN Tag laden (voll
aufgeloest), nicht die komplette Mehrjahres-Historie - siehe
animation_component.py fuer die Details zur eigenen, schlanken Karte.
"""

import streamlit as st
from datetime import datetime, timedelta

import animation_component as anim
import sync_simulation as sync

st.set_page_config(page_title="Bewegungs-Animation", layout="wide")

st.title("Bewegungs-Animation: Echt vs. Simuliert")
st.caption(
    "Ein Bär, ein Tag - echte GPS-Bewegung (blau) und die dazu passenden "
    "Alternativ-Kandidaten aus Fabians Modell (orange, als Fächer pro Schritt) "
    "garantiert synchron. Eigene Seite, getrennt von der Haupt-Karte."
)

carpathian_data = None
alt_geojson = None
sync_warnings = []

# ============================================================
# Sidebar: EINE gemeinsame Auswahl fuer Bär + Tag
# ============================================================
with st.sidebar:
    st.header("Bär & Tag auswählen")
    try:
        from carpathian_bears import get_carpathian_geojson, get_carpathian_options

        bears, seasons, min_date, max_date = get_carpathian_options()

        if bears:
            sel_bear = st.selectbox("Bär", bears, key="anim_bear")

            # Leichtgewichtiger, gecachter Lookup: welche Tage hat dieser
            # Bär überhaupt Daten? Kein Rumprobieren mehr nötig.
            @st.cache_data(ttl=3600, show_spinner=False)
            def _get_available_dates(bear, seasons_tuple, min_d, max_d):
                start_dt = datetime.combine(min_d, datetime.min.time())
                end_dt = datetime.combine(max_d, datetime.max.time())
                fc = get_carpathian_geojson(
                    selected_bears=[bear], start_datetime=start_dt, end_datetime=end_dt,
                    selected_seasons=list(seasons_tuple), map_type="Movement Paths",
                    max_points_per_bear=200000,
                )
                dates = set()
                for f in fc.get("points", {}).get("features", []):
                    ts = f.get("properties", {}).get("timestamp")
                    if ts:
                        dates.add(str(ts)[:10])
                return sorted(dates)

            with st.spinner(f"Prüfe verfügbare Tage für {sel_bear}..."):
                available_dates = _get_available_dates(sel_bear, tuple(seasons), min_date, max_date)

            if not available_dates:
                st.warning(f"Keine GPS-Daten für {sel_bear} gefunden.")
            else:
                with st.form("anim_form"):
                    sel_date_str = st.selectbox(
                        "Tag", available_dates,
                        help=f"{len(available_dates)} Tage mit echten GPS-Daten für {sel_bear}.",
                    )
                    num_alt = st.slider(
                        "Alternativen pro Schritt", 3, 20, 10,
                        help="Wie viele Kandidatenrichtungen das Modell pro echtem Schritt zeigt.",
                    )
                    submitted = st.form_submit_button("Laden", type="primary")

                if submitted:
                    st.session_state["anim_params"] = (sel_bear, sel_date_str, num_alt)

                if "anim_params" in st.session_state:
                    loaded_bear, loaded_date_str, loaded_num_alt = st.session_state["anim_params"]
                    loaded_date = datetime.strptime(loaded_date_str, "%Y-%m-%d").date()
                    start_dt = datetime.combine(loaded_date, datetime.min.time())
                    end_dt = start_dt + timedelta(days=1)

                    with st.spinner(f"Lade {loaded_bear} am {loaded_date_str}..."):
                        carpathian_data = get_carpathian_geojson(
                            selected_bears=[loaded_bear],
                            start_datetime=start_dt,
                            end_datetime=end_dt,
                            selected_seasons=seasons,
                            map_type="Movement Paths",
                            max_points_per_bear=50000,  # 1 Tag ist server-seitig schon klein genug
                        )

                    with st.spinner("Berechne Alternativ-Kandidaten (Fabians Modell)..."):
                        try:
                            synced = sync.build_synced_geojson(
                                carpathian_data.get("points", {}), num_alternatives=loaded_num_alt,
                            )
                            alt_geojson = synced["alternative"]
                            sync_warnings = synced["warnings"]
                        except Exception as e:
                            st.error(f"Fehler bei der Alternativen-Berechnung: {e}")
        else:
            st.info("Keine Carpathian-Daten gefunden.")
    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {e}")

    for w in sync_warnings:
        st.warning(w)

# ============================================================
# Animations-Karte
# ============================================================
if carpathian_data is None:
    st.info("Links einen Bären und einen Tag auswählen und auf **Laden** klicken.")
else:
    anim.render_animation_map(
        carpathian=carpathian_data,
        alternatives=alt_geojson,
        height=750,
    )
    st.caption(
        "Play/Pause, Einzelschritt vor/zurück, Tempo und Zeitfenster oben rechts auf der Karte. "
        "Der orangene Fächer zeigt die Alternativ-Kandidaten am jeweils aktuellen echten Schritt "
        "(kein eigener Pfad - jede Alternative ist eine von mehreren Optionen an genau diesem Punkt)."
    )