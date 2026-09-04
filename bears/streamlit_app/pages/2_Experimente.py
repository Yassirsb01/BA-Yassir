"""
pages/2_Experimente.py
========================
Analyse-Seite: Bewegungs-Animation der Carpathian-Baeren (echte GPS-Route
+ zugehoerige Alternativ-Kandidaten aus Fabians Modell, garantiert
synchron - siehe sync_simulation.py).

Zielgruppe sind Forschende, die nachvollziehen wollen, wie sich ein
konkreter Baer an einem konkreten Tag im Gelaende bewegt hat und wie
plausibel die simulierten Alternativen dazu sind. Deshalb:
  - Filter nach Bär, Jahreszeit und Tag (nur Tage MIT Daten waehlbar)
  - Datenherkunft wird explizit angezeigt (MariaDB vs. CSV-Fallback)
  - Satellitenbild + optionales 3D-Gelaende fuer raeumlichen Kontext

Performance-Prinzip: server-seitig immer nur EIN Tag laden (dafuer in
voller Aufloesung, ohne Downsampling) - nicht die komplette
Mehrjahres-Historie.
"""

import streamlit as st
from datetime import datetime, timedelta

import animation_component as anim
import sync_simulation as sync

st.set_page_config(page_title="Bewegungs-Animation", layout="wide")


# ============================================================
# Datenherkunft ermitteln (fuer die Anzeige auf der Karte)
# ============================================================
@st.cache_data(ttl=300, show_spinner=False)
def _get_data_source_label() -> str:
    """
    Prueft einmalig (gecacht), ob die MariaDB erreichbar ist. Wichtig fuer
    die Nachvollziehbarkeit: Forschende sollen sehen, ob sie Live-Daten aus
    der Projektdatenbank oder den lokalen CSV-Fallback vor sich haben.
    """
    try:
        from wildlife_db_mariadb import WildlifeDatabase
        db = WildlifeDatabase()
        conn = db._get_connection()
        conn.close()
        host = db.db_config.get("host", "?")
        database = db.db_config.get("database", "?")
        return f"MariaDB · {database}@{host}"
    except Exception:
        return "Lokaler CSV-Fallback (keine DB-Verbindung)"


st.title("Bewegungs-Animation: Echt vs. Simuliert")
st.caption(
    "Ein Bär, ein Tag – echte GPS-Bewegung (blau) und die dazu passenden "
    "Alternativ-Kandidaten aus Fabians Modell (orange, als Fächer pro Schritt), "
    "garantiert synchron. Datensatz: Carpathian Bears, GPS-Tracking Rumänien."
)

carpathian_data = None
alt_geojson = None
sync_warnings = []
selected_bear_label = ""

source_label = _get_data_source_label()

# ============================================================
# Sidebar: Bär -> Jahreszeit -> Tag (nur Tage MIT Daten)
# ============================================================
with st.sidebar:
    st.header("Auswahl")
    st.caption(f"Datenquelle: {source_label}")

    try:
        from carpathian_bears import get_carpathian_geojson, get_carpathian_options

        bears, seasons, min_date, max_date = get_carpathian_options()

        if not bears:
            st.info("Keine Carpathian-Daten gefunden.")
        else:
            sel_bear = st.selectbox("Bär", bears, key="anim_bear")

            sel_seasons = st.multiselect(
                "Jahreszeit", seasons, default=seasons,
                help="Schränkt die auswählbaren Tage auf die gewählten Saisons ein "
                     "(z.B. nur Hyperphagie-Phase betrachten).",
            )
            if not sel_seasons:
                sel_seasons = seasons  # leere Auswahl = keine Einschränkung

            # Welche Tage hat dieser Bär in diesen Saisons ueberhaupt Daten?
            # Gecacht, damit die Abfrage nicht bei jeder Interaktion laeuft.
            @st.cache_data(ttl=3600, show_spinner=False)
            def _get_available_dates(bear, seasons_tuple, min_d, max_d):
                fc = get_carpathian_geojson(
                    selected_bears=[bear],
                    start_datetime=datetime.combine(min_d, datetime.min.time()),
                    end_datetime=datetime.combine(max_d, datetime.max.time()),
                    selected_seasons=list(seasons_tuple),
                    map_type="Movement Paths",
                    max_points_per_bear=200000,
                )
                dates = set()
                for f in fc.get("points", {}).get("features", []):
                    ts = f.get("properties", {}).get("timestamp")
                    if ts:
                        dates.add(str(ts)[:10])
                return sorted(dates)

            with st.spinner(f"Prüfe verfügbare Tage für {sel_bear}..."):
                available_dates = _get_available_dates(
                    sel_bear, tuple(sorted(sel_seasons)), min_date, max_date
                )

            if not available_dates:
                st.warning(
                    f"Keine GPS-Daten für {sel_bear} in den gewählten Jahreszeiten. "
                    "Andere Saison oder anderen Bären wählen."
                )
            else:
                with st.form("anim_form"):
                    sel_date_str = st.selectbox(
                        "Tag", available_dates,
                        help=f"{len(available_dates)} Tage mit echten GPS-Daten.",
                    )
                    num_alt = st.slider(
                        "Alternativen pro Schritt", 3, 20, 10,
                        help="Wie viele Kandidatenrichtungen das Modell pro echtem "
                             "GPS-Schritt erzeugt (Fächer auf der Karte).",
                    )
                    submitted = st.form_submit_button("Laden", type="primary")

                if submitted:
                    st.session_state["anim_params"] = (sel_bear, sel_date_str, num_alt)

                if "anim_params" in st.session_state:
                    loaded_bear, loaded_date_str, loaded_num_alt = st.session_state["anim_params"]
                    loaded_date = datetime.strptime(loaded_date_str, "%Y-%m-%d").date()
                    start_dt = datetime.combine(loaded_date, datetime.min.time())
                    end_dt = start_dt + timedelta(days=1)
                    selected_bear_label = f"BÄR {loaded_bear}"

                    with st.spinner(f"Lade {loaded_bear} am {loaded_date_str}..."):
                        carpathian_data = get_carpathian_geojson(
                            selected_bears=[loaded_bear],
                            start_datetime=start_dt,
                            end_datetime=end_dt,
                            selected_seasons=sel_seasons,
                            map_type="Movement Paths",
                            max_points_per_bear=50000,  # 1 Tag: keine Reduktion noetig
                        )

                    with st.spinner("Berechne Alternativ-Kandidaten (Fabians Modell)..."):
                        try:
                            synced = sync.build_synced_geojson(
                                carpathian_data.get("points", {}),
                                num_alternatives=loaded_num_alt,
                            )
                            alt_geojson = synced["alternative"]
                            sync_warnings = synced["warnings"]
                        except Exception as e:
                            st.error(f"Fehler bei der Alternativen-Berechnung: {e}")

    except Exception as e:
        st.error(f"Fehler beim Laden der Daten: {e}")

    for w in sync_warnings:
        st.warning(w)

    st.markdown("---")
    st.caption(
        "Hinweis: Der Gesamtpfad ist beim Start bewusst ausgeblendet, damit die "
        "Bewegung erst beim Abspielen entsteht. Auf der Karte einblendbar."
    )

# ============================================================
# Animations-Karte
# ============================================================
if carpathian_data is None:
    st.info("Links Bär, Jahreszeit und Tag auswählen und auf **Laden** klicken.")
else:
    n_pts = len(carpathian_data.get("points", {}).get("features", []))
    if n_pts == 0:
        st.warning("Für diesen Tag wurden keine GPS-Punkte geladen. Anderen Tag wählen.")
    else:
        anim.render_animation_map(
            carpathian=carpathian_data,
            alternatives=alt_geojson,
            basemap="Satellit",
            bear_label=selected_bear_label,
            dataset_label="Carpathian Bears · GPS-Tracking (Rumänien)",
            source_label=source_label,
            height=900,
        )