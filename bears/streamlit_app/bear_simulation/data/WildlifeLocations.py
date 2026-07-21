

class WildlifeLocations:
    def __init__(self, db_connection):
        self.db = db_connection
        self.create_table()

    def create_table(self):
        self.db.cursor.execute("""
        CREATE TABLE IF NOT EXISTS wildlife_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wildlife_type VARCHAR(255) NOT NULL,
            wildlife_id INTEGER,
            time DATETIME NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            gender CHAR(1),
            age CHAR(1),
            source VARCHAR(255)
        )
        """)

        self.db.commit()

    def insert(self, wildlife_type, wildlife_id, time, latitude, longitude, gender, age, source=None):
        time_str = time.strftime('%Y-%m-%d %H:%M:%S')
        self.db.cursor.execute("""
        INSERT INTO wildlife_locations (wildlife_type, wildlife_id, time, latitude, longitude, gender, age, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (wildlife_type, wildlife_id, time_str, latitude, longitude, gender, age, source))
        self.db.commit()

    def get_all(self):
        self.db.cursor.execute("SELECT * FROM wildlife_locations")
        return self.db.cursor.fetchall()

    def get_by_source(self, source):
        self.db.cursor.execute("""
        SELECT * FROM wildlife_locations WHERE source = ?
        """, (source,))
        return self.db.cursor.fetchall()

    def get_by_date(self, date):
        self.db.cursor.execute("""
                SELECT * FROM wildlife_locations WHERE DATE(time) = ?
                """, (date,))
        return self.db.cursor.fetchall()

    def get_by_source_and_wildlife_id(self, source, wildlife_id, limit):
        self.db.cursor.execute("""
        SELECT * FROM wildlife_locations WHERE source = ? AND wildlife_id = ? ORDER BY time LIMIT ?
        """, (source, wildlife_id, limit))
        return self.db.cursor.fetchall()

    def get_by_source_and_date(self, source, date):
        self.db.cursor.execute("""
                SELECT * FROM wildlife_locations WHERE source = ? AND DATE(time) = ? ORDER BY time
                """, (source, date))
        return self.db.cursor.fetchall()

    # def get_by_source_and_hour(self, source, hour):
    #     hour_str = f"{hour:02d}"
    #     self.db.cursor.execute("""
    #                     SELECT * FROM wildlife_locations WHERE source = ? AND strftime('%H', time) = ? ORDER BY time
    #                     """, (source, hour_str))
    #     return self.db.cursor.fetchall()

    def get_by_source_and_hour(self, source, hour):
        hour_str = f"{hour:02d}"
        self.db.cursor.execute("""
            SELECT 
                WL1.wildlife_id,
                WL1.latitude  AS lat_begin,
                WL1.longitude AS lon_begin,
                WL2.latitude  AS lat_end,
                WL2.longitude AS lon_end,
                WL1.time AS time_begin,
                WL2.time AS time_end,
                B1.season
            FROM wildlife_locations AS WL1
            JOIN wildlife_locations AS WL2
              ON WL1.wildlife_id = WL2.wildlife_id
             AND WL1.source      = WL2.source
             AND julianday(WL2.time) - julianday(WL1.time) BETWEEN 0.0403 AND 0.0430
            JOIN bear_locations AS B1
              ON B1.wildlife_id = WL1.wildlife_id
             AND B1.source      = WL1.source
             AND B1.time        = DATE(WL1.time)
            JOIN bear_locations AS B2
              ON B2.wildlife_id = WL2.wildlife_id
             AND B2.source      = WL2.source
             AND B2.time        = DATE(WL2.time)
            WHERE WL1.source = ?
              AND strftime('%H', WL1.time) = ?
              AND B1.season = B2.season
            ORDER BY WL1.wildlife_id, WL1.time
        """, (source, hour_str))

        return self.db.cursor.fetchall()

    def get_with_season_by_source(self, source):
        self.db.cursor.execute("""
                            SELECT 
                                WL.*,
                                BL.season
                            FROM wildlife_locations AS WL
                            JOIN bear_locations AS BL
                            ON BL.wildlife_id = WL.wildlife_id
                            AND BL.source      = WL.source
                            AND BL.time        = DATE(WL.time)
                            WHERE WL.source = ?
                        """, (source,))

        return self.db.cursor.fetchall()

    def get_bear_by_id_and_season(self, bear_id, season, source):
        self.db.cursor.execute("""
                    SELECT 
                        WL.*,
                        BL.season
                    FROM wildlife_locations AS WL
                    JOIN bear_locations AS BL
                      ON BL.wildlife_id = WL.wildlife_id
                     AND BL.source      = WL.source
                     AND BL.time        = DATE(WL.time)
                    WHERE WL.wildlife_id = ?
                      AND BL.season = ?
                      AND WL.source = ?
                    ORDER BY WL.time
                """, (bear_id, season, source))

        return self.db.cursor.fetchall()

    def get_gender_and_age_by_wildlife_id(self, wildlife_id, source):
        self.db.cursor.execute("""
                SELECT gender, COUNT(*) AS count
                FROM wildlife_locations
                WHERE wildlife_id = ?
                AND source = ?
                GROUP BY gender
                ORDER BY count DESC
                LIMIT 1
                """, (wildlife_id, source))
        gender = self.db.cursor.fetchone()[0]
        self.db.cursor.execute("""
                SELECT age, COUNT(*) AS count
                FROM wildlife_locations
                WHERE wildlife_id = ?
                AND source = ?
                GROUP BY age
                ORDER BY count DESC
                LIMIT 1
                """, (wildlife_id, source))
        age = self.db.cursor.fetchone()[0]

        return gender, age

    def delete_by_id(self, entry_id):
        self.db.cursor.execute("DELETE FROM wildlife_locations WHERE id = ?", (entry_id,))
        self.db.commit()

    def delete_all(self):
        self.db.cursor.execute("DELETE FROM wildlife_locations")
        self.db.commit()


if __name__ == "__main__":
    from data.DatabaseConnection import DatabaseConnection

    dbc = DatabaseConnection()
    wlc = WildlifeLocations(dbc)

    print(len(wlc.get_all()))
    for entry in wlc.get_by_source_and_wildlife_id("Carpathians", 2, 30):
        print(entry)



