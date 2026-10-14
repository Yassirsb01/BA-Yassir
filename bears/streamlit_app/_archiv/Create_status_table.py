"""
Erstellt die app_status Tabelle fuer Status-Tracking
"""

from wildlife_db_mariadb import WildlifeDatabase
from datetime import datetime

def create_status_table():
    """Erstellt die app_status Tabelle"""
    
    db = WildlifeDatabase()
    
    print("Erstelle app_status Tabelle...")
    
    # Erstelle Tabelle
    create_query = """
        CREATE TABLE IF NOT EXISTS app_status (
            id INT AUTO_INCREMENT PRIMARY KEY,
            status_key VARCHAR(255) UNIQUE NOT NULL,
            status_value TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """
    
    db.execute_update(create_query)
    print("Tabelle erstellt (oder existiert bereits).")
    
    # Initialer Eintrag
    print("Fuege initialen Eintrag hinzu...")
    
    init_query = """
        INSERT INTO app_status (status_key, status_value) 
        VALUES ('last_image_check', %s)
        ON DUPLICATE KEY UPDATE status_value = status_value
    """
    
    current_time = datetime.now().isoformat()
    db.execute_update(init_query, (current_time,))
    
    print("Fertig!")
    
    # Verifiziere
    verify_query = "SELECT * FROM app_status WHERE status_key = 'last_image_check'"
    result = db.execute_query(verify_query)
    
    if result:
        print(f"\nVerifizierung:")
        print(f"  Status Key: {result[0]['status_key']}")
        print(f"  Status Value: {result[0]['status_value']}")
        print(f"  Updated At: {result[0]['updated_at']}")
    else:
        print("\nWarnung: Eintrag nicht gefunden!")

if __name__ == "__main__":
    create_status_table()