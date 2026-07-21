from ..data.DatabaseConnection import DatabaseConnection
from ..data.BearSpeeds import BearSpeeds
from .StepTrajectorySet import StepTrajectorySet
from ..GeoToolBox import GeoToolBox
import random
from geopy.distance import geodesic
import os


class StepSelectionModel:
    def __init__(self, source):
        self.db_path = os.path.join(os.path.dirname(__file__), "..", "data", "database.db")
        self.source = source
        self.sts = StepTrajectorySet("Carpathians")
        self.results = []
        dbcon = DatabaseConnection(self.db_path)
        self.bs = BearSpeeds(dbcon)

    def get_median_speed(self, gender, age, season, hour):
        speed = self.bs.get_median_speed_for_type_and_time(gender, age, season, hour, self.source)
        return speed

    def generate_alternative_steps(self, segment, num_alternatives=10, perception_distance=200):
        alternatives_per_step = []

        for i in range(len(segment.segment) - 1):
            start = segment.segment[i]
            end = segment.segment[i + 1]

            hour = start.time.hour
            gender = segment.gender
            age = segment.age
            season = segment.season

            median_speed_kmh = self.get_median_speed(gender, age, season, hour)
            if median_speed_kmh is None:
                continue

            step_length_m = median_speed_kmh * 1000

            start_point = (start.lat, start.lon)
            end_point = (end.lat, end.lon)
            real_direction = GeoToolBox.calculate_direction(start_point, end_point)

            alt_steps = []
            for _ in range(num_alternatives):
                angle_offset = random.uniform(0, 360)
                alt_direction = (real_direction + angle_offset) % 360
                alt_endpoint = GeoToolBox.destination_point(start_point, alt_direction, step_length_m)
                perception_point = GeoToolBox.destination_point(start_point, alt_direction, perception_distance)

                alt_steps.append({
                    "start": start_point,
                    "end": alt_endpoint,
                    "perception_point": perception_point,
                    "angle": alt_direction,
                    "length": step_length_m,
                    "real": False
                })

            perception_real = GeoToolBox.destination_point(start_point, real_direction, perception_distance)
            alt_steps.append({
                "start": start_point,
                "end": (end.lat, end.lon),
                "perception_point": perception_real,
                "angle": real_direction,
                "length": geodesic(start_point, (end.lat, end.lon)).meters,
                "real": True
            })

            alternatives_per_step.append(alt_steps)

        return alternatives_per_step


if __name__ == "__main__":
    ssm = StepSelectionModel("Carpathians")
    segment = ssm.sts.trajectories[0]
    alternatives = ssm.generate_alternative_steps(segment)
    for alternative in alternatives:
        print(alternative)






