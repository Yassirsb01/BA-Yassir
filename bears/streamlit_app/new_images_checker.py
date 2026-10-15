"""
Checks the database for images that arrived since the last check.
"""

from wildlife_db_mariadb import WildlifeDatabase
from datetime import datetime, timedelta
import streamlit as st

class NewImagesChecker:
    def __init__(self):
        self.db = WildlifeDatabase()

    # ttl=30: hits the database at most every 30 s, no matter how often
    # Streamlit reruns in between, for example on every filter change in
    # another form. The leading underscore in "_self" tells Streamlit not
    # to hash the instance, so the cache key is (minutes_ago) alone.
    @st.cache_data(ttl=30, show_spinner=False)
    def get_new_images_since(_self, minutes_ago=60):
        """
        Return images that arrived within the last X minutes.

        Args:
            minutes_ago: how many minutes to look back (default: 60)
            
        Returns:
            List von Bildern mit Details
        """
        cutoff_time = datetime.now() - timedelta(minutes=minutes_ago)
        
        query = """
            SELECT 
                filename,
                device_id,
                source,
                timestamp,
                created_at,
                image_type
            FROM bears_images_unified
            WHERE created_at >= %s
            ORDER BY created_at DESC
        """
        
        results = _self.db.execute_query(query, (cutoff_time,))
        return results if results else []
    
    def get_latest_image_time(self):
        """
        Return the timestamp of the most recent image.
        """
        query = """
            SELECT MAX(created_at) as latest
            FROM bears_images_unified
        """
        result = self.db.execute_scalar(query)
        return result
    
    def get_images_count_by_source(self, minutes_ago=60):
        """
        Zaehlt neue Bilder gruppiert nach Quelle
        """
        cutoff_time = datetime.now() - timedelta(minutes=minutes_ago)
        
        query = """
            SELECT 
                source,
                COUNT(*) as count
            FROM bears_images_unified
            WHERE created_at >= %s
            GROUP BY source
        """
        
        results = self.db.execute_query(query, (cutoff_time,))
        return {row['source']: row['count'] for row in results} if results else {}
    
    @st.cache_data(ttl=30, show_spinner=False)
    def get_last_check_time(_self):
        """
        Read the time of the last check from the database.
        
        Returns:
            datetime object, or None if no check has been recorded yet
        """
        query = """
            SELECT status_value 
            FROM app_status 
            WHERE status_key = 'last_image_check'
        """
        
        result = _self.db.execute_scalar(query)
        
        if result:
            try:
                # Parse den gespeicherten Timestamp
                return datetime.fromisoformat(result)
            except:
                return None
        return None
    
    def update_last_check_time(self):
        """
        Store the current time as the time of the last check.
        """
        current_time = datetime.now().isoformat()
        
        query = """
            INSERT INTO app_status (status_key, status_value) 
            VALUES ('last_image_check', %s)
            ON DUPLICATE KEY UPDATE 
                status_value = %s,
                updated_at = NOW()
        """
        
        self.db.execute_update(query, (current_time, current_time))

        # Clear the cache: without this, "Check now" would keep showing
        # the previous cached state for up to 30 s instead of the new one.
        NewImagesChecker.get_last_check_time.clear()
        NewImagesChecker.get_new_images_since.clear()