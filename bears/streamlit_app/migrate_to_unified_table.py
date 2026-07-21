"""
migrate_to_unified_table.py

Safe Migration: Alle Bilder → bears_images_unified
- Dateisystem → neue Tabelle
- Anthony's wildlife_images → neue Tabelle
- Alte Tabellen bleiben unberührt!
"""

import os
import mysql.connector
from datetime import datetime
import re

class SafeImageMigrator:
    def __init__(self):
        self.db = mysql.connector.connect(
            host="172.20.39.9",
            port=3306,
            user="ursus",
            password="thibetanus",
            database="ursus"
        )
        self.cursor = self.db.cursor(dictionary=True)
        
    def migrate_all(self):
        """Haupt-Migration: Alle Quellen"""
        
        print("="*70)
        print("🚀 SAFE MIGRATION: Alle Bilder → bears_images_unified")
        print("="*70)
        print()
        
        # Step 1: Migriere aus Dateisystem
        print("📁 SCHRITT 1: Dateisystem → DB")
        print("-"*70)
        fs_stats = self.migrate_from_filesystem()
        print()
        
        # Step 2: Migriere aus Anthony's Tabelle
        print("📧 SCHRITT 2: Anthony's wildlife_images → Unified")
        print("-"*70)
        anthony_stats = self.migrate_from_anthony_table()
        print()
        
        # Summary
        print("="*70)
        print("✅ MIGRATION ABGESCHLOSSEN!")
        print("="*70)
        print(f"Dateisystem:  {fs_stats['migrated']:4d} migrated, {fs_stats['skipped']:4d} skipped, {fs_stats['errors']:4d} errors")
        print(f"Anthony's DB: {anthony_stats['migrated']:4d} migrated, {anthony_stats['skipped']:4d} skipped, {anthony_stats['errors']:4d} errors")
        print("-"*70)
        total_migrated = fs_stats['migrated'] + anthony_stats['migrated']
        print(f"TOTAL:        {total_migrated} neue Bilder in bears_images_unified")
        print("="*70)
        
        return {
            'filesystem': fs_stats,
            'anthony': anthony_stats,
            'total': total_migrated
        }
    
    def migrate_from_filesystem(self, base_folder="data/bear_pictures"):
        """Migration 1: Dateisystem → unified"""
        
        stats = {'migrated': 0, 'skipped': 0, 'errors': 0}
        
        if not os.path.isdir(base_folder):
            print(f"⚠️ Ordner nicht gefunden: {base_folder}")
            return stats
        
        device_dirs = os.listdir(base_folder)
        print(f"📊 Gefunden: {len(device_dirs)} Device-Ordner")
        
        for device_dir in device_dirs:
            device_path = os.path.join(base_folder, device_dir)
            
            if not os.path.isdir(device_path):
                continue
            
            device_id = self._clean_device_id(device_dir)
            print(f"\n📷 Device: {device_id}")
            
            # Device-Ordner
            device_subfolder = os.path.join(device_path, "device")
            if os.path.isdir(device_subfolder):
                result = self._process_image_folder(
                    device_subfolder, device_id, "device", "filesystem"
                )
                stats['migrated'] += result['migrated']
                stats['skipped'] += result['skipped']
                stats['errors'] += result['errors']
                print(f"   device: {result['migrated']} migrated, {result['skipped']} skipped")
            
            # Trail-Ordner
            trail_subfolder = os.path.join(device_path, "trail_processed")
            if os.path.isdir(trail_subfolder):
                result = self._process_image_folder(
                    trail_subfolder, device_id, "trail", "filesystem"
                )
                stats['migrated'] += result['migrated']
                stats['skipped'] += result['skipped']
                stats['errors'] += result['errors']
                print(f"   trail:  {result['migrated']} migrated, {result['skipped']} skipped")
        
        return stats
    
    def migrate_from_anthony_table(self):
        """Migration 2: Anthony's wildlife_images → unified"""
        
        stats = {'migrated': 0, 'skipped': 0, 'errors': 0}
        
        # Prüfe ob Anthony's Tabelle existiert
        self.cursor.execute("SHOW TABLES LIKE 'wildlife_images'")
        if not self.cursor.fetchone():
            print("ℹ️ Anthony's 'wildlife_images' Tabelle existiert nicht (wird übersprungen)")
            return stats
        
        # Hole alle Bilder aus Anthony's Tabelle
        query = "SELECT * FROM wildlife_images"
        self.cursor.execute(query)
        anthony_images = self.cursor.fetchall()
        
        print(f"📊 Gefunden: {len(anthony_images)} Bilder in Anthony's Tabelle")
        
        for img_dict in anthony_images:
            try:
                # Insert in unified table
                insert_query = """
                    INSERT IGNORE INTO bears_images_unified 
                    (device_id, filename, image_bytes, image_type, source, 
                     timestamp, parsed_successfully)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                
                # image_bytes oder image_metadata (beide Namen möglich)
                image_data = img_dict.get('image_bytes') or img_dict.get('image_metadata')
                
                self.cursor.execute(insert_query, (
                    img_dict.get('device_id'),
                    img_dict.get('filename'),
                    image_data,
                    img_dict.get('image_type', 'trail'),
                    'email',  # Anthony's Bilder kommen per E-Mail
                    img_dict.get('timestamp'),
                    img_dict.get('parsed_successfully', True)
                ))
                
                if self.cursor.rowcount > 0:
                    stats['migrated'] += 1
                    if stats['migrated'] % 10 == 0:
                        print(f"   ✅ {stats['migrated']} Bilder migriert...")
                else:
                    stats['skipped'] += 1
                
            except Exception as e:
                print(f"   ❌ Fehler bei {img_dict.get('filename')}: {e}")
                stats['errors'] += 1
        
        self.db.commit()
        return stats
    
    def _process_image_folder(self, folder_path, device_id, image_type, source):
        """Verarbeitet alle Bilder in einem Ordner"""
        
        result = {'migrated': 0, 'skipped': 0, 'errors': 0}
        
        for img_file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, img_file)
            
            if not img_file.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            
            if not os.path.isfile(file_path):
                continue
            
            # Lese Bild
            try:
                with open(file_path, 'rb') as f:
                    image_bytes = f.read()
            except Exception as e:
                result['errors'] += 1
                continue
            
            # Timestamp extrahieren
            timestamp = self._extract_timestamp(img_file, image_type)
            
            # Parsed successfully?
            parsed = "unsuccessful_parsing" not in img_file
            
            # In DB speichern (IGNORE bei Duplikaten)
            try:
                query = """
                    INSERT IGNORE INTO bears_images_unified 
                    (device_id, filename, image_bytes, image_type, source, 
                     timestamp, parsed_successfully)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                
                self.cursor.execute(query, (
                    device_id, img_file, image_bytes, image_type, 
                    source, timestamp, parsed
                ))
                
                if self.cursor.rowcount > 0:
                    result['migrated'] += 1
                else:
                    result['skipped'] += 1
                
            except Exception as e:
                result['errors'] += 1
        
        self.db.commit()
        return result
    
    def _clean_device_id(self, device_dir):
        """Bereinigt Device ID"""
        device_id = str(device_dir).strip()
        if '.' in device_id:
            try:
                id_float = float(device_id)
                if id_float == int(id_float):
                    device_id = str(int(id_float))
            except ValueError:
                pass
        return device_id
    
    def _extract_timestamp(self, filename, image_type):
        """Extrahiert Timestamp aus Dateinamen"""
        try:
            if image_type == "trail":
                if "unsuccessful_parsing" in filename:
                    return None
                
                base_name = os.path.splitext(filename)[0]
                parts = base_name.split('.')
                
                if len(parts) >= 4 and all(p.isdigit() for p in parts[-4:]):
                    date_part = ".".join(parts[-4:])
                    dt_obj = datetime.strptime(date_part, "%Y.%m.%d.%H%M")
                    return dt_obj
                    
            elif image_type == "device":
                parts = filename.split('_')
                if len(parts) >= 3:
                    date_str = parts[2]
                    date_cleaned = "".join(filter(lambda c: c.isdigit() or c == '.', date_str))
                    dt_obj = datetime.strptime(date_cleaned, "%Y.%m.%d.%H%M")
                    return dt_obj
        except:
            pass
        
        return None
    
    def verify_migration(self):
        """Prüft die Migration"""
        print("\n" + "="*70)
        print("🔍 VERIFIKATION")
        print("="*70)
        
        # Count in unified table
        self.cursor.execute("SELECT COUNT(*) as count FROM bears_images_unified")
        unified_count = self.cursor.fetchone()['count']
        
        # Count by source
        self.cursor.execute("""
            SELECT source, COUNT(*) as count 
            FROM bears_images_unified 
            GROUP BY source
        """)
        by_source = self.cursor.fetchall()
        
        # Count by type
        self.cursor.execute("""
            SELECT image_type, COUNT(*) as count 
            FROM bears_images_unified 
            GROUP BY image_type
        """)
        by_type = self.cursor.fetchall()
        
        print(f"\n📊 Gesamt in bears_images_unified: {unified_count}")
        print("\n📁 Nach Quelle:")
        for row in by_source:
            print(f"   {row['source']:12s}: {row['count']:6d}")
        
        print("\n🏷️  Nach Typ:")
        for row in by_type:
            print(f"   {row['image_type']:12s}: {row['count']:6d}")
        
        print("="*70)
    
    def close(self):
        """Schließt DB-Verbindung"""
        if self.cursor:
            self.cursor.close()
        if self.db:
            self.db.close()


if __name__ == "__main__":
    migrator = SafeImageMigrator()
    
    try:
        # Migration durchführen
        stats = migrator.migrate_all()
        
        # Verifikation
        migrator.verify_migration()
        
    except KeyboardInterrupt:
        print("\n⚠️ Migration unterbrochen")
    except Exception as e:
        print(f"\n❌ Fehler: {e}")
        import traceback
        traceback.print_exc()
    finally:
        migrator.close()
        print("\n✅ Fertig!")