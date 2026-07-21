class WildlifeSightingsView:
    def __init__(self, db_connection):
        self.db = db_connection
        self.create_view()

    def create_view(self):
        self.db.cursor.execute("DROP VIEW IF EXISTS wildlife_sightings")
        self.db.cursor.execute("""
            CREATE VIEW IF NOT EXISTS wildlife_sightings AS
            SELECT 
                id,
                wildlife_type,
                time,
                strftime('%Y', time) AS year,
                strftime('%m', time) AS month,
                strftime('%d', time) AS day,
                strftime('%H', time) AS hour,
                CASE 
                    WHEN strftime('%m', time) IN ('12', '01', '02') THEN 'winter'
                    WHEN strftime('%m', time) IN ('03', '04', '05') THEN 'spring'
                    WHEN strftime('%m', time) IN ('06', '07', '08') THEN 'summer'
                    ELSE 'autumn'
                END AS season,
                latitude,
                longitude,
                source
            FROM wildlife_locations
        """)
        self.db.commit()

    def get_all(self):
        self.db.cursor.execute("SELECT * FROM wildlife_sightings")
        return self.db.cursor.fetchall()

    def get_by_season(self, season):
        self.db.cursor.execute("SELECT * FROM wildlife_sightings WHERE season = ?", (season,))
        return self.db.cursor.fetchall()

    def get_by_year(self, year):
        self.db.cursor.execute("SELECT * FROM wildlife_sightings WHERE year = ?", (str(year),))
        return self.db.cursor.fetchall()

    def get_stats_by_season(self):
        self.db.cursor.execute("""
            SELECT season, COUNT(*) as count
            FROM wildlife_sightings
            GROUP BY season
        """)
        return self.db.cursor.fetchall()

    def get_recent(self, limit=10):
        self.db.cursor.execute("""
            SELECT * FROM wildlife_sightings
            ORDER BY time DESC
            LIMIT ?
        """, (limit,))
        return self.db.cursor.fetchall()


if __name__ == "__main__":
    from data.DatabaseConnection import DatabaseConnection

    dbcon = DatabaseConnection()
    wlsv = WildlifeSightingsView(dbcon)

    for entry in wlsv.get_all():
        print(entry)