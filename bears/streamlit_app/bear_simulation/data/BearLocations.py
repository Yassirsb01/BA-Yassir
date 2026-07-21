from datetime import datetime

class BearLocations:
    def __init__(self, db_connection):
        self.db = db_connection
        self.create_table()

    def create_table(self):
        self.db.cursor.execute("""
        CREATE TABLE IF NOT EXISTS bear_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wildlife_type VARCHAR(255) NOT NULL,
            wildlife_id INTEGER,
            time DATE NOT NULL,
            season VARCHAR(255),
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            distance REAL NOT NULL,
            altitude INTEGER NOT NULL,
            source VARCHAR(255)
        )
        """)

        self.db.commit()

    def insert(self, wildlife_type, wildlife_id, time, season, latitude, longitude,
               distance, altitude, source=None):
        time_str = time.strftime('%Y-%m-%d')
        self.db.cursor.execute("""
        INSERT INTO bear_locations (wildlife_type, wildlife_id, time, season, latitude, longitude, distance,
        altitude, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (wildlife_type, wildlife_id, time_str, season, latitude, longitude, distance, altitude, source))
        self.db.commit()

    def get_all(self):
        self.db.cursor.execute("SELECT * FROM bear_locations")
        return self.db.cursor.fetchall()

    def delete_by_id(self, entry_id):
        self.db.cursor.execute("DELETE FROM bear_locations WHERE id = ?", (entry_id,))
        self.db.commit()

    def delete_all(self):
        self.db.cursor.execute("DELETE FROM bear_locations")
        self.db.commit()

    def get_by_date(self, date):
        self.db.cursor.execute("""
                SELECT * FROM bear_locations WHERE time = ?
                """, (date,))
        return self.db.cursor.fetchall()

    def get_by_season(self, season):
        self.db.cursor.execute("""
                SELECT * FROM bear_locations WHERE season = ? ORDER BY time
                """, (season,))
        return self.db.cursor.fetchall()


if __name__ == "__main__":
    from data.DatabaseConnection import DatabaseConnection

    dbc = DatabaseConnection()
    blc = BearLocations(dbc)

    entries = []
    for entry in blc.get_all():
        _, _, _, date_str, season, lat, lon, _, _, _ = entry
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if date.year == 2013:
            entries.append((date, season, lat, lon))

    print(len(entries))
    for entry in entries:
        print(entry)
