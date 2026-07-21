from ..data.DatabaseConnection import DatabaseConnection
from ..data.WildlifeLocations import WildlifeLocations
from collections import defaultdict
from datetime import timedelta
from .TrajectorySegment import TrajectorySegment
from .TrajectoryPoint import TrajectoryPoint
from .SeasonalTrajectoryProcessor import SeasonalTrajectoryProcessor
from datetime import datetime
import os


class StepTrajectorySet:
    """Generates and holds season-specific trajectories with geometric medians.

    Fetches sightings data out of the database and creates trajectories out of them, that
    each belong to only one season, and assigns geometric medians to them.

    Attributes:
        db_path (str): Path to the SQLite database file.
        trajectories (list[TrajectorySegment]): List of trajectories to be generated.
        src (str): Source of the sightings to be fetched from the database.
        stp (SeasonalTrajectoryProcessor): Helper class for further trajectory processing.
    """
    def __init__(self, src):
        """Initializes the StepTrajectorySet and builds trajectories from database sightings.

                Args:
                    src (str): Source identifier for the sightings' data.
        """
        self.db_path = os.path.join(os.path.dirname(__file__), "..", "data", "database.db")
        self.trajectories = []
        self.src = src
        self.stp = SeasonalTrajectoryProcessor()
        self.build_segments()

    def extract_data(self):
        """Extracts and returns sightings data from the database.

        Returns:
            list[dict]: A list of dictionaries containing bear-specific sightings information.
        """
        dbcon = DatabaseConnection(db_name=self.db_path)
        wlc = WildlifeLocations(dbcon)
        entries = wlc.get_by_source(self.src)
        data = []
        for entry in entries:
            _, _, bear_id, time, lat, lon, gender, age, _ = entry
            d = {"bear_id": bear_id,
                 "time": datetime.strptime(time, "%Y-%m-%d %H:%M:%S"),
                 "lat": lat,
                 "lon": lon,
                 "gender": gender,
                 "age": age}
            data.append(d)
        return data

    def build_segments(self):
        """Builds a list of trajectories out of the fetched data."""
        data = self.extract_data()
        grouped = defaultdict(list)

        for entry in data:
            grouped[entry["bear_id"]].append(entry)

        for bear_id, points in grouped.items():
            points.sort(key=lambda x: x["time"])
            current_segment = []
            last_time = None

            for entry in points:
                tp = TrajectoryPoint(entry["time"], entry["lat"], entry["lon"])

                if last_time is not None:
                    delta = entry["time"] - last_time
                    if delta > timedelta(hours=1.5):
                        if current_segment:
                            segment = TrajectorySegment(
                                bear_id=bear_id,
                                gender=entry["gender"],
                                age=entry["age"],
                                segment=current_segment
                            )
                            self.trajectories.append(segment)
                            current_segment = []

                current_segment.append(tp)
                last_time = entry["time"]

            if current_segment:
                segment = TrajectorySegment(
                    bear_id=bear_id,
                    gender=entry["gender"],
                    age=entry["age"],
                    segment=current_segment
                )
                self.trajectories.append(segment)
        self.split_segments_by_season()
        self.assign_geometric_medians()

    def split_segments_by_season(self):
        """Splits the trajectories by season using the SeasonalTrajectoryProcessor class."""
        self.stp.trajectories = self.trajectories
        self.stp.split_segments_by_season()
        self.trajectories = self.stp.trajectories

    def assign_geometric_medians(self):
        """Assigns trajectory-specific local geometric medians using the SeasonalTrajectoryProcessor class."""
        self.stp.trajectories = self.trajectories
        self.stp.assign_geometric_medians()
        self.trajectories = self.stp.trajectories


if __name__ == "__main__":
    sts = StepTrajectorySet("Carpathians")
    # for trajectory in sts.trajectories:
    #     print(trajectory)

    segment = sts.trajectories[0]
    points = segment.segment
    print(segment.bear_id, segment.gender, segment.age, segment.season, segment.local_geometric_median)
    for point in points:
        print(point.lat, point.lon, point.time)


