from DatabaseConnection import DatabaseConnection
from WildlifeLocations import WildlifeLocations
from BearLocations import BearLocations
from BearSpeeds import BearSpeeds
from datetime import datetime
from statistics import median
from geopy.distance import geodesic
from collections import defaultdict


class BearAttributes:
    def __init__(self):
        self.bear_speeds = {}

        self.dbcon = DatabaseConnection()
        self.wlc = WildlifeLocations(self.dbcon)
        self.blc = BearLocations(self.dbcon)
        self.bs = BearSpeeds(self.dbcon)

        self.source = "Carpathians"

    def get_gender_and_age_by_wildlife_id(self, wildlife_id):
        return self.wlc.get_gender_and_age_by_wildlife_id(wildlife_id, self.source)

    def get_hourly_bear_speeds_by_season(self, bear_id, season):
        entries = self.wlc.get_bear_by_id_and_season(bear_id, season, self.source)

        data_count = len(entries)
        if data_count == 0:
            return None

        gender, age = entries[0][6], entries[0][7]

        distances = [[] for _ in range(24)]

        for i in range(len(entries) - 1):
            _, _, _, time_start, lat_start, lon_start, _, _, _, _ = entries[i]
            _, _, _, time_end, lat_end, lon_end, _, _, _, _ = entries[i + 1]
            time_start = datetime.strptime(time_start, "%Y-%m-%d %H:%M:%S")
            time_end = datetime.strptime(time_end, "%Y-%m-%d %H:%M:%S")

            delta_sec = abs((time_end - time_start).total_seconds())
            if 3480 <= delta_sec <= 3720:
                distance = geodesic((lat_start, lon_start), (lat_end, lon_end)).kilometers
                time = time_start.hour
                distances[time].append(distance)

        speeds_median = [round(median(d), 3) if d else 0.0 for d in distances]
        speeds_max = [round(max(d), 3) if d else 0.0 for d in distances]
        speeds_min = [round(min(d), 3) if d else 0.0 for d in distances]

        return data_count, gender, age, speeds_median, speeds_max, speeds_min

    # def get_bear_speeds_by_season_and_time(self):
    #     # Highest Bear Id: 18
    #     seasons = ["spring", "summer", "autumn", "winter"]
    #     for season in seasons:
    #         self.bear_speeds[season] = []
    #         for i in range(19):
    #             result = self.get_hourly_bear_speeds_by_season(i, season)
    #             if result is not None:
    #                 print(i, *result)
    #                 self.bear_speeds[season].append((i, *result))

    def store_grouped_speeds_by_type(self):
        seasons = ["spring", "summer", "autumn", "winter"]

        grouped_speeds = defaultdict(list)

        for season in seasons:
            for bear_id in range(19):
                result = self.get_hourly_bear_speeds_by_season(bear_id, season)
                if result is None:
                    continue

                _, gender, age, speeds_median, speeds_max, speeds_min = result

                for hour in range(24):
                    distance = speeds_median[hour]
                    if distance > 0:
                        key = (gender, age, season, hour)
                        grouped_speeds[key].append(distance)

        for (gender, age, season, hour), values in grouped_speeds.items():
            v_min = round(min(values), 3)
            v_max = round(max(values), 3)
            v_median = round(median(values), 3)

            self.bs.insert(
                wildlife_type="bear",
                gender=gender,
                age=age,
                season=season,
                hour=hour,
                v_min=v_min,
                v_max=v_max,
                median=v_median,
                source=self.source
            )


if __name__ == "__main__":
    bear_attributes = BearAttributes()
    bear_attributes.store_grouped_speeds_by_type()



