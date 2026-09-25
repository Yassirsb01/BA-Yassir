"""
pages/2_Experimente.py
========================
Analyse-Seite: Bewegungs-Animation der Carpathian-Baeren. Echte GPS-Route
und mehrere simulierte Baeren laufen auf derselben Zeitachse nebeneinander
(siehe sync_simulation.py), zusaetzlich einblendbar der Faecher der
Alternativ-Kandidaten pro Schritt.

Warum MEHRERE simulierte Baeren statt einem: Jeder Pfad ist nur eine
Zufallsziehung aus dem Modell. Ein einzelner Pfad neben der echten Route
wuerde als "das Modell sagt diesen Weg voraus" gelesen - mehrere
auseinanderlaufende Pfade zeigen den Moeglichkeitsraum unmittelbar.
Ueber den Seed ist jeder Lauf exakt reproduzierbar (wichtig fuer
Abbildungen in der Bachelorarbeit).

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
from geojson_table_helper import geojson_to_dataframe

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


@st.cache_data(show_spinner=False)
def _load_and_simulate(bear: str, date_str: str, seasons_key: tuple,
                       num_alt: int, n_real: int, seed: int) -> dict:
    """
    Laedt EINEN Tag und berechnet die Simulation dazu - gecacht.

    WARUM GECACHT (Fehlerbild "simulierte Pfade springen"): Streamlit fuehrt
    bei JEDER Interaktion das komplette Skript neu aus. Ohne Cache lief
    build_synced_geojson() dabei jedes Mal neu, das erzeugte HTML der
    Kartenkomponente aenderte sich, das iframe wurde neu aufgebaut - und die
    Animation begann von vorn. Mit Cache liefert ein Rerun bei unveraenderten
    Parametern exakt dasselbe Ergebnis, das iframe bleibt stehen.

    WICHTIG - alle Eingaben sind skalar: Der Tag wird INNERHALB der Funktion
    geladen, statt das GeoJSON als Argument hereinzureichen. Sonst muesste
    st.cache_data bei jedem Rerun ein Dict mit tausenden Features hashen.

    seasons_key ist ein Tupel (hashbar) und gehoert bewusst zum
    Cache-Schluessel: die Saisonauswahl bestimmt mit, welche Punkte der Tag
    ueberhaupt enthaelt.
    """
    from carpathian_bears import get_carpathian_geojson

    day = datetime.strptime(date_str, "%Y-%m-%d").date()
    start_dt = datetime.combine(day, datetime.min.time())
    end_dt = start_dt + timedelta(days=1)

    carpathian_data = get_carpathian_geojson(
        selected_bears=[bear],
        start_datetime=start_dt,
        end_datetime=end_dt,
        selected_seasons=list(seasons_key),
        map_type="Movement Paths",
        max_points_per_bear=50000,  # 1 Tag: keine Reduktion noetig
    )

    synced = sync.build_synced_geojson(
        carpathian_data.get("points", {}),
        num_alternatives=num_alt,
        n_realizations=n_real,
        seed=seed,
    )
    return {
        "carpathian": carpathian_data,
        "alternative": synced["alternative"],
        "simulated": synced["simulated"],
        "warnings": synced["warnings"],
    }


def _run_id(sim_geojson: dict) -> str:
    """
    Kurze Kennung der simulierten Pfade (Hash ueber alle Koordinaten).

    Dient der Fehlersuche und der Nachvollziehbarkeit: bleibt die Kennung
    ueber einen Rerun hinweg gleich, ist die Simulation unveraendert und die
    Animation wurde lediglich neu gestartet. Aendert sie sich, haben sich
    tatsaechlich die Daten geaendert. Fuer die Bachelorarbeit ausserdem
    praktisch, um einen Screenshot spaeter eindeutig zuzuordnen.
    """
    import hashlib
    coords = "".join(
        f"{f['geometry']['coordinates'][0]:.6f},{f['geometry']['coordinates'][1]:.6f};"
        for f in (sim_geojson or {}).get("features", [])
    )
    return hashlib.sha1(coords.encode()).hexdigest()[:8] if coords else "–"


st.title("Bewegungs-Animation: Echt vs. Simuliert")
st.caption(
    "Ein Bär, ein Tag – die echte GPS-Bewegung (blau) und mehrere simulierte Bären "
    "(orange) laufen auf derselben Zeitachse nebeneinander. Zusätzlich einblendbar: "
    "der Fächer der Alternativ-Kandidaten pro Schritt (grau). "
    "Datensatz: Carpathian Bears, GPS-Tracking Rumänien."
)

# Erklaerung bewusst auf ENGLISCH: die Arbeit wird vor der Abgabe auf
# Englisch umgestellt, und dieser Abschnitt ist der Teil, den Betreuer und
# andere Forschende zuerst lesen. Die uebrige Oberflaeche bleibt vorerst
# deutsch.
with st.expander("What am I looking at?  ·  About this experiment", expanded=False):
    st.markdown("""
**The dataset.** GPS collar data from brown bears (*Ursus arctos*) in the
Romanian Carpathians: 13 individuals and 59,997 fixes, recorded from
9 August 2011 to 31 July 2015. Fix intervals are about one hour — 80% fall
between 0.9 and 1.1 hours, 13% around two hours, the rest longer. One bear on
one day is loaded at a time, at full resolution.

**What the colours mean.**

| Colour | Meaning |
|---|---|
| **Blue** dot and trail | The bear's actual recorded GPS track, interpolated between fixes. |
| **Orange** dots and trails | Simulated bears, generated by the movement model. Several are shown at once; each is a separate run. |
| **Grey** fan (optional) | At every real step, all candidate moves the model considered at that moment. |

**What the animation shows.** Real and simulated bears advance along the
*same* timeline, starting from the *same* position. Both are driven by the
timestamps of the real GPS track, so any separation you see between them
accumulated within that time window. The "Abstand ø" readout gives the current
mean distance between the real bear and the simulated ones.

**What it does not show.** The orange paths are **not predictions** and not a
reconstruction of anything the bear actually did. Each is one random
realisation drawn from the model: change the seed and you get different paths
from the same starting point. This is why several are drawn at once — the
spread between them is the meaningful part, not any single line. A simulated
bear ending up far from the real one is not in itself a modelling failure.

**The question behind it.** Given step lengths and turning behaviour learned
from real bears, does the model produce movement that is *plausible* for this
landscape and this time of year? The comparison is distributional — how far
bears travel, how tortuous their paths are — not a point-by-point match.

**Reproducibility.** Every run is identified by the short hash shown above the
map. The same bear, day, season selection, seed and settings always reproduce
exactly the same paths.
""")

carpathian_data = None
alt_geojson = None
sim_geojson = None
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
        from carpathian_bears import (get_carpathian_geojson, get_carpathian_options,
                                       SEASON_HELP)

        bears, seasons, min_date, max_date = get_carpathian_options()

        if not bears:
            st.info("Keine Carpathian-Daten gefunden.")
        else:
            sel_bear = st.selectbox("Bär", bears, key="anim_bear")

            sel_seasons = st.multiselect(
                "Jahreszeit", seasons, default=seasons,
                help="Schränkt die auswählbaren Tage auf die gewählten Phasen ein.\n\n"
                     + SEASON_HELP,
            )
            st.caption(
                "Biologische Jahresphasen des Bären, keine Kalenderjahreszeiten – "
                "Erklärung über das (?)."
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
                    n_real = st.slider(
                        "Simulierte Bären (Realisierungen)", 0, 8, 3,
                        help="Jeder simulierte Bär ist EIN möglicher Modelllauf, keine "
                             "Vorhersage. Mehrere Läufe zeigen, wie weit das Modell bei "
                             "gleichem Start streuen kann. 0 blendet sie aus.",
                    )
                    anim_seed = st.number_input(
                        "Zufalls-Seed", min_value=0, max_value=999999, value=42,
                        help="Gleicher Seed = exakt derselbe Lauf. Seed ändern = neue "
                             "Realisierungen würfeln (wichtig, um zu sehen, dass ein "
                             "einzelner Pfad nichts beweist).",
                    )
                    submitted = st.form_submit_button("Laden", type="primary")

                if submitted:
                    # sel_seasons gehoert MIT in die Parameter: frueher wurde
                    # es live aus dem Multiselect gelesen, wodurch eine
                    # Aenderung der Saisonauswahl den bereits geladenen Tag
                    # still veraendert hat (andere Punktmenge -> andere
                    # Simulation, im Extremfall gar keine Punkte mehr).
                    st.session_state["anim_params"] = (
                        sel_bear, sel_date_str, tuple(sorted(sel_seasons)),
                        num_alt, int(n_real), int(anim_seed),
                    )

                # Aus einer aelteren Programmversion koennen noch Parameter
                # mit anderer Feldzahl in der Session liegen - die dann
                # einfach verwerfen statt mit einem ValueError abzustuerzen.
                if len(st.session_state.get("anim_params", ())) != 6:
                    st.session_state.pop("anim_params", None)

                if "anim_params" in st.session_state:
                    (loaded_bear, loaded_date_str, loaded_seasons,
                     loaded_num_alt, loaded_n_real, loaded_seed) = st.session_state["anim_params"]
                    selected_bear_label = f"BÄR {loaded_bear}"

                    with st.spinner(f"Lade {loaded_bear} am {loaded_date_str}..."):
                        try:
                            _res = _load_and_simulate(
                                loaded_bear, loaded_date_str, loaded_seasons,
                                loaded_num_alt, loaded_n_real, loaded_seed,
                            )
                            carpathian_data = _res["carpathian"]
                            alt_geojson = _res["alternative"]
                            sim_geojson = _res["simulated"]
                            sync_warnings = _res["warnings"]
                        except Exception as e:
                            st.error(f"Fehler bei der Simulations-Berechnung: {e}")

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
        # Lauf-Kennung: bleibt ueber Reruns hinweg gleich, solange sich die
        # Simulation nicht aendert. Aendert sie sich doch, ist das hier
        # sofort sichtbar (siehe _run_id).
        st.caption(
            f"Lauf-Kennung `{_run_id(sim_geojson)}` · Bär {loaded_bear} · {loaded_date_str} · "
            f"{loaded_n_real} Realisierungen · Seed {loaded_seed} · "
            f"{loaded_num_alt} Alternativen/Schritt"
        )

        anim.render_animation_map(
            carpathian=carpathian_data,
            alternatives=alt_geojson,
            simulated=sim_geojson,
            basemap="Satellit",
            bear_label=selected_bear_label,
            dataset_label="Carpathian Bears · GPS-Tracking (Rumänien)",
            source_label=source_label,
            height=900,
        )

        st.markdown("### Daten zur aktuellen Ansicht")
        _tabs = st.tabs(["Echte GPS-Punkte", "Simulierte Pfade", "Alternativ-Kandidaten"])
        with _tabs[0]:
            df_real = geojson_to_dataframe(carpathian_data.get("points"))
            st.caption(f"{len(df_real)} echte GPS-Punkte für {selected_bear_label}, {loaded_date_str}")
            st.dataframe(df_real, width="stretch")
        with _tabs[1]:
            df_sim = geojson_to_dataframe(sim_geojson)
            if df_sim.empty:
                st.info("Keine simulierten Pfade berechnet (Regler auf 0?).")
            else:
                st.caption(
                    f"{len(df_sim)} simulierte Positionen über {loaded_n_real} Realisierungen "
                    f"(Seed {loaded_seed}) – jede Realisierung ist ein möglicher Modelllauf, "
                    "keine Vorhersage."
                )
                st.dataframe(df_sim, width="stretch")
        with _tabs[2]:
            df_alt = geojson_to_dataframe(alt_geojson)
            if df_alt.empty:
                st.info("Keine Alternativ-Kandidaten berechnet.")
            else:
                st.caption(f"{len(df_alt)} Alternativ-Kandidaten (Fabians Modell)")
                st.dataframe(df_alt, width="stretch")