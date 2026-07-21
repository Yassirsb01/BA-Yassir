"""
Prueft, ob neue Bilder in der DB sind (seit letztem Check)
"""

from wildlife_db_mariadb import WildlifeDatabase
from datetime import datetime, timedelta
import streamlit as st

class NewImagesChecker:
    def __init__(self):
        self.db = WildlifeDatabase()
    
    def get_new_images_since(self, minutes_ago=60):
        """
        Holt neue Bilder aus den letzten X Minuten
        
        Args:
            minutes_ago: Wie viele Minuten zurueck pruefen (default: 60)
            
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
        
        results = self.db.execute_query(query, (cutoff_time,))
        return results if results else []
    
    def get_latest_image_time(self):
        """
        Holt den Zeitstempel des neuesten Bildes
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
    
    def get_last_check_time(self):
        """
        Holt die letzte Pruefzeit aus der DB
        
        Returns:
            datetime object oder None
        """
        query = """
            SELECT status_value 
            FROM app_status 
            WHERE status_key = 'last_image_check'
        """
        
        result = self.db.execute_scalar(query)
        
        if result:
            try:
                # Parse den gespeicherten Timestamp
                return datetime.fromisoformat(result)
            except:
                return None
        return None
    
    def update_last_check_time(self):
        """
        Speichert die aktuelle Zeit als letzte Pruefzeit in der DB
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