import os
import csv
from datetime import datetime
from data.DatabaseConnection import DatabaseConnection
from data.WildlifeLocations import WildlifeLocations


class CsvReader:
    def __init__(self):
        self.base_path = "../2024Bear"

    def get_time_stamps(self, folder):
        timestamps = []
        folder = "00" + folder.split(".")[0]
        files = os.path.join(os.path.join(self.base_path, folder), "device")
        elements = os.listdir(files)
        for element in elements:
            timestamps.append(element.split("_")[2])
        return timestamps

    def get_bear_sightings(self):
        entries = []
        counter = 0
        csv_file = os.path.join(self.base_path, "ReadMe.csv")
        with open(csv_file, newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile, delimiter=",")
            for line in reader:
                if counter == 0:
                    counter = counter + 1
                    continue
                timestamps = self.get_time_stamps(line[1])
                for timestamp in timestamps:
                    time = datetime.strptime(timestamp, "%Y.%m.%d.%H%M")
                    lat_dmm = line[4]
                    lon_dmm = line[5]
                    lat_dd = line[6]
                    lon_dd = line[7]
                    entries.append((time, lat_dmm, lon_dmm, lat_dd, lon_dd))

        return entries


if __name__ == "__main__":
    csvr = CsvReader()
    db_name = "../data/database.db"
    dbcon = DatabaseConnection(db_name=db_name)
    wlc = WildlifeLocations(dbcon)
    entries = csvr.get_bear_sightings()
    print(len(entries))
    for entry in entries:
        animal_type = "bear"
        animal_id = None
        timestamp, _, _, lat, lon = entry
        gender = None
        age = None
        source = "Hiroshi Saito"
        print(animal_type, timestamp, lat, lon, source)
        wlc.insert(animal_type, animal_id, timestamp, lat, lon, gender, age, source)
