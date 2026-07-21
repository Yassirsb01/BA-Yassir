import os
import csv
from datetime import datetime
from pyproj import Transformer
from data.DatabaseConnection import DatabaseConnection
from data.WildlifeLocations import WildlifeLocations

class CsvReader2:
    def __init__(self):
        self.base_path = "../Carpathian"
        self.transformer = Transformer.from_crs("EPSG:3844", "EPSG:4326", always_xy=True)

    def get_timestamp(self, timestamp):
        time = datetime.strptime(timestamp, "%m/%d/%Y %H:%M")
        return time

    def laea_to_latlon(self, x, y):
        lon, lat = self.transformer.transform(x, y)

        return lat, lon

    def get_bear_sightings(self):
        entries = []
        counter = 0
        csv_file = os.path.join(self.base_path, "1_bears_RO.csv")
        with open(csv_file, newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile, delimiter=",")
            for line in reader:
                if counter == 0:
                    counter = counter + 1
                    continue

                lat, lon = self.laea_to_latlon(line[1], line[2])
                formatted_lat = f"{lat:.6f}"
                formatted_lon = f"{lon:.6f}"
                animal_id_str = line[3].strip()
                animal_id = int(animal_id_str.replace("Bear", ""))
                animal_type = "bear"
                timestamp = self.get_timestamp(line[4])
                gender = line[7].strip()
                age = line[8].strip()
                source = "Carpathians"
                entries.append((animal_type, animal_id, timestamp, formatted_lat, formatted_lon,
                                gender, age, source))
        return entries


if __name__ == "__main__":
    csvr = CsvReader2()
    db_name = "../data/database.db"
    dbcon = DatabaseConnection(db_name=db_name)
    wlc = WildlifeLocations(dbcon)
    entries = csvr.get_bear_sightings()
    for entry in entries:
        wildlife_type, wildlife_id, timestamp, lat, lon, gender, age, src = entry
        wlc.insert(wildlife_type, wildlife_id, timestamp, lat, lon, gender, age, src)



