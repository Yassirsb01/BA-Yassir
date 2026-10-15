"""
Sidebar and dashboard widgets reporting newly arrived images.
"""

import streamlit as st
from datetime import datetime
from new_images_checker import NewImagesChecker


@st.cache_data(ttl=30, show_spinner=False)
def database_reachable() -> bool:
    """
    Report whether the database answers, with a hard time limit.

    Without this check the widget would wait for the full
    connection_timeout of 15 seconds whenever the host is unreachable,
    which is the normal situation while the university VPN is down. The
    page runs again on every interaction, so that delay would apply to
    every click.

    The result is cached for 30 seconds, the same window the image queries
    use. After connecting the VPN the status therefore returns on its own
    within half a minute, or immediately via "Check now".
    """
    from wildlife_db_mariadb import WildlifeDatabase
    return WildlifeDatabase().is_reachable(timeout_sec=6.0)


def display_new_images_status(position="sidebar"):
    """
    Show the status of newly arrived images.

    Args:
        position: 'sidebar' or 'main', selecting where to render.
    """

    container = st.sidebar if position == "sidebar" else st

    if not database_reachable():
        with container:
            st.markdown("### New image status")
            st.info(
                "No connection to the database. Is the university VPN "
                "active? The map and all local data remain usable."
            )
            if st.button("Try again", key="retry_images"):
                database_reachable.clear()
                st.rerun()
        return

    checker = NewImagesChecker()

    # Read the time of the last check from the database, so it survives
    # a restart of the application
    last_check = checker.get_last_check_time()
    
    # If no check has ever been recorded, start from now
    if last_check is None:
        checker.update_last_check_time()
        last_check = datetime.now()
    
    # Time elapsed since the last check
    time_since_check = datetime.now() - last_check
    minutes_since_check = int(time_since_check.total_seconds() / 60)

    with container:
        st.markdown("### New image status")

        # Images of the last 24 hours (1440 minutes). The commented-out
        # line would instead cover only the span since the last check.
        # new_images = checker.get_new_images_since(minutes_ago=minutes_since_check)
        new_images = checker.get_new_images_since(minutes_ago=1440)
        
        if new_images:
            st.success(f"{len(new_images)} new image(s) found.")

            with st.expander("Show details", expanded=True):
                for img in new_images:
                    system = "E-mail" if img['source'] == 'email' else "File system"
                    
                    st.markdown(f"""
                    **{img['filename'][:30]}...**
                    - Device: {img['device_id']}
                    - Source: {system}
                    - Type: {img['image_type']}
                    - Time: {img['created_at']}
                    """)
                    st.divider()
        else:
            st.info("No new images yet")

        # Time of the last check
        if minutes_since_check == 0:
            time_text = "a few seconds ago"
        elif minutes_since_check == 1:
            time_text = "1 minute ago"
        else:
            time_text = f"{minutes_since_check} minutes ago"
        
        st.caption(f"Last checked: {time_text}")

        if st.button("Check now", key="refresh_images"):
            checker.update_last_check_time()
            st.rerun()


def display_compact_status():
    """
    Compact variant, a single line.
    """
    checker = NewImagesChecker()
    
    # Check the last 24 hours
    new_images = checker.get_new_images_since(minutes_ago=1440)
    
    if new_images:
        st.info(f"{len(new_images)} new images in the last 24 h")
    else:
        st.caption("No new images")


def display_detailed_dashboard():
    """
    Detailed dashboard variant for the main page.
    """
    checker = NewImagesChecker()
    
    st.markdown("## Image status dashboard")
    
    # Counts over several time windows
    col1, col2, col3 = st.columns(3)
    
    with col1:
        last_hour = checker.get_new_images_since(minutes_ago=60)
        st.metric(
            label="Last hour",
            value=len(last_hour),
            delta=len(last_hour) if last_hour else None
        )
    
    with col2:
        last_day = checker.get_new_images_since(minutes_ago=1440)
        st.metric(
            label="Last 24 hours",
            value=len(last_day)
        )
    
    with col3:
        last_week = checker.get_new_images_since(minutes_ago=10080)
        st.metric(
            label="Last week",
            value=len(last_week)
        )
    
    # Most recent images
    if last_day:
        st.markdown("### Most recent images (24 h)")
        
        for img in last_day[:5]:  # show at most five
            with st.container():
                col_info, col_time = st.columns([3, 1])
                
                with col_info:
                    source_icon = "E-mail" if img['source'] == 'email' else "File system"
                    st.markdown(f"**{img['filename']}** ({source_icon})")
                    st.caption(f"Device {img['device_id']} • {img['image_type']}")
                
                with col_time:
                    st.caption(f"{img['created_at']}")
                
                st.divider()
    else:
        st.info("No new images in the last 24 hours")