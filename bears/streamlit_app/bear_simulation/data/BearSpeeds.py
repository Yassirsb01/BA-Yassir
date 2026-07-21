

class BearSpeeds:
    def __init__(self, db_connection):
        self.db = db_connection
        self.create_table()

    def create_table(self):
        self.db.cursor.execute("""
        CREATE TABLE IF NOT EXISTS bear_speeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wildlife_type VARCHAR(255) NOT NULL,
            gender CHAR(1) NOT NULL,
            age CHAR(1) NOT NULL,
            season VARCHAR(255) NOT NULL,
            hour INTEGER NOT NULL,
            v_min REAL NOT NULL,
            v_max REAL NOT NULL,
            median REAL NOT NULL,
            source VARCHAR(255)
        )
        """)

        self.db.commit()

    def insert(self, wildlife_type, gender, age, season, hour, v_min, v_max, median, source=None):
        self.db.cursor.execute("""
        INSERT INTO bear_speeds (wildlife_type, gender, age, season, hour, v_min, v_max, median,
        source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (wildlife_type, gender, age, season, hour, v_min, v_max, median, source))
        self.db.commit()

    def get_all(self):
        self.db.cursor.execute("SELECT * FROM bear_speeds")
        return self.db.cursor.fetchall()

    def get_median_speed_for_type_and_time(self, gender, age, season, hour, source):
        self.db.cursor.execute("""
                            SELECT median
                            FROM bear_speeds
                            WHERE wildlife_type = ?
                            AND gender = ?
                            AND age = ?
                            AND season = ?
                            AND hour = ?
                            AND source = ?
                        """, ("bear", gender, age, season, hour, source))
        result = self.db.cursor.fetchone()
        return result[0] if result else None

    def delete_by_id(self, entry_id):
        self.db.cursor.execute("DELETE FROM bear_speeds WHERE id = ?", (entry_id,))
        self.db.commit()

    def delete_all(self):
        self.db.cursor.execute("DELETE FROM bear_speeds")
        self.db.commit()


if __name__ == "__main__":
    from data.DatabaseConnection import DatabaseConnection

    dbc = DatabaseConnection()
    bs = BearSpeeds(dbc)

    print(len(bs.get_all()))
    for entry in bs.get_all():
        print(entry)

