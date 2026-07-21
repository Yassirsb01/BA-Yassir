import os
import csv
from datetime import datetime
from pyproj import Transformer
from data.DatabaseConnection import DatabaseConnection
from data.BearLocations import BearLocations


class CsvReader3:
    def __init__(self):
        self.base_path = "../Carpathian"
        self.transformer = Transformer.from_crs("EPSG:3844", "EPSG:4326", always_xy=True)

    def get_timestamp(self, timestamp):
        time = datetime.strptime(timestamp, "%m/%d/%Y")
        return time

    def laea_to_latlon(self, x, y):
        lon, lat = self.transformer.transform(x, y)

        return lat, lon

    def get_bear_sightings(self):
        entries = []
        counter = 0
        csv_file = os.path.join(self.base_path, "7_dist_bears_RO.csv")
        with open(csv_file, newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile, delimiter=",")
            for line in reader:
                if counter == 0:
                    counter = counter + 1
                    continue

                lat, lon = self.laea_to_latlon(line[1], line[2])
                formatted_lat = f"{lat:.6f}"
                formatted_lon = f"{lon:.6f}"
                animal_id_str = line[6].strip()
                animal_id = int(animal_id_str.replace("Bear", ""))

                season_nr = line[5]
                if season_nr == "II":
                    season = "spring"
                elif season_nr == "III":
                    season = "summer"
                elif season_nr == "IV":
                    season = "autumn"
                else:
                    season = "winter"

                timestamp = self.get_timestamp(line[3])
                distance_m = line[4]
                altitude_m = line[7]
                animal_type = "bear"
                source = "Carpathians"

                entries.append((animal_type, animal_id, timestamp, season, formatted_lat, formatted_lon,
                                distance_m, altitude_m, source))
        return entries

if __name__ == "__main__":
    csvr = CsvReader3()
    db_name = "../data/database.db"
    dbcon = DatabaseConnection(db_name=db_name)
    blc = BearLocations(dbcon)
    entries = csvr.get_bear_sightings()
    for entry in entries:
        animal_type, animal_id, timestamp, season, lat, lon, distance, altitude, src = entry
        blc.insert(animal_type, animal_id, timestamp, season, lat, lon, distance, altitude, src)
