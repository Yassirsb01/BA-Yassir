"""
Status-Widget fuer neue Bilder
"""

import streamlit as st
from datetime import datetime, timedelta
from new_images_checker import NewImagesChecker

def display_new_images_status(position="sidebar"):
    """
    Zeigt Status neuer Bilder an
    
    Args:
        position: 'sidebar' oder 'main' (wo anzeigen?)
    """
    
    checker = NewImagesChecker()
    
    # Hole letzte Pruefzeit aus DB (persistent!)
    last_check = checker.get_last_check_time()
    
    # Falls noch nie geprueft, setze auf jetzt
    if last_check is None:
        checker.update_last_check_time()
        last_check = datetime.now()
    
    # Berechne, wie lange der letzte Check her ist
    time_since_check = datetime.now() - last_check
    minutes_since_check = int(time_since_check.total_seconds() / 60)
    
    # Container waehlen
    container = st.sidebar if position == "sidebar" else st
    
    with container:
        st.markdown("### Neue Bilder Status")
        
        # Pruefe neue Bilder seit letztem Check
        # new_images = checker.get_new_images_since(minutes_ago=minutes_since_check)
        new_images = checker.get_new_images_since(minutes_ago=1440)  # Letzte 24 Stunden=1440min
        
        if new_images:
            # NEUE BILDER GEFUNDEN!
            st.success(f"{len(new_images)} neue(s) Bild(er) gefunden!")
            
            # Zeige Details in Expander
            with st.expander("Details anzeigen", expanded=True):
                for img in new_images:
                    system = "E-Mail" if img['source'] == 'email' else "Dateisystem"
                    
                    st.markdown(f"""
                    **{img['filename'][:30]}...**
                    - Device: {img['device_id']}
                    - Quelle: {system}
                    - Typ: {img['image_type']}
                    - Zeit: {img['created_at']}
                    """)
                    st.divider()
        else:
            # Keine neuen Bilder
            st.info("Noch keine neuen Bilder")
        
        # Zeige letzten Check-Zeitpunkt
        if minutes_since_check == 0:
            time_text = "vor wenigen Sekunden"
        elif minutes_since_check == 1:
            time_text = "vor 1 Minute"
        else:
            time_text = f"vor {minutes_since_check} Minuten"
        
        st.caption(f"Zuletzt geprueft: {time_text}")
        
        # Refresh-Button
        if st.button("Jetzt pruefen", key="refresh_images"):
            checker.update_last_check_time()  # Speichere in DB!
            st.rerun()


def display_compact_status():
    """
    Kompakte Version - nur eine Zeile
    """
    checker = NewImagesChecker()
    
    # Pruefe letzte 24 Stunden
    new_images = checker.get_new_images_since(minutes_ago=1440)
    
    if new_images:
        st.info(f"{len(new_images)} neue Bilder in den letzten 24h")
    else:
        st.caption("Keine neuen Bilder")


def display_detailed_dashboard():
    """
    Ausfuehrliche Dashboard-Version (fuer Hauptseite)
    """
    checker = NewImagesChecker()
    
    st.markdown("## Bilder-Status Dashboard")
    
    # Statistiken fuer verschiedene Zeitraeume
    col1, col2, col3 = st.columns(3)
    
    with col1:
        last_hour = checker.get_new_images_since(minutes_ago=60)
        st.metric(
            label="Letzte Stunde",
            value=len(last_hour),
            delta=len(last_hour) if last_hour else None
        )
    
    with col2:
        last_day = checker.get_new_images_since(minutes_ago=1440)
        st.metric(
            label="Letzte 24 Stunden",
            value=len(last_day)
        )
    
    with col3:
        last_week = checker.get_new_images_since(minutes_ago=10080)
        st.metric(
            label="Letzte Woche",
            value=len(last_week)
        )
    
    # Zeige neueste Bilder
    if last_day:
        st.markdown("### Neueste Bilder (24h)")
        
        for img in last_day[:5]:  # Max 5 zeigen
            with st.container():
                col_info, col_time = st.columns([3, 1])
                
                with col_info:
                    source_icon = "E-Mail" if img['source'] == 'email' else "Dateisystem"
                    st.markdown(f"**{img['filename']}** ({source_icon})")
                    st.caption(f"Device {img['device_id']} • {img['image_type']}")
                
                with col_time:
                    st.caption(f"{img['created_at']}")
                
                st.divider()
    else:
        st.info("Keine neuen Bilder in den letzten 24 Stunden")