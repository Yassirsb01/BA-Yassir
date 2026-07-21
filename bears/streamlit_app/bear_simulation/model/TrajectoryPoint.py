
class TrajectoryPoint:
    """Represents a point of a trajectory and holds its characteristics.

    Attributes:
        time (datetime): Time of the sighting at the location.
        lat (float): Latitude of the sightings' location.
        lon(float): Longitude of the sightings' location.
    """
    def __init__(self, time, lat, lon):
        """Initializes the TrajectoryPoint.

                Args:
                    time (datetime): Time of the sighting at the location.
                    lat (float): Latitude of the location.
                    lon (float): Longitude of the location.
        """
        self.time = time
        self.lat = lat
        self.lon = lon
