from wildlife_db_mariadb import WildlifeDatabase

db = WildlifeDatabase()

create_table_sql = """
CREATE TABLE bears_images_unified (
    id INT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,
    filename VARCHAR(512) NOT NULL,
    image_bytes LONGBLOB NOT NULL,
    image_type VARCHAR(50) NOT NULL,
    source VARCHAR(50) NOT NULL,
    timestamp DATETIME,
    parsed_successfully BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_device_id (device_id),
    INDEX idx_image_type (image_type),
    INDEX idx_source (source),
    INDEX idx_timestamp (timestamp),
    INDEX idx_filename (device_id, filename),
    UNIQUE KEY unique_image (device_id, filename, source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

try:
    db.execute_update(create_table_sql)
    print("✅ Tabelle 'bears_images_unified' erfolgreich erstellt!")
except Exception as e:
    if "already exists" in str(e).lower():
        print("ℹ️ Tabelle existiert bereits")
    else:
        print(f"❌ Fehler: {e}")