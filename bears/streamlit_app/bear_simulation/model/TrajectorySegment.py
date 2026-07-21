
class TrajectorySegment:
    """Represents a trajectory consisting of TrajectoryPoints.

    Contains a list of TrajectoryPoints with information identifying and characterizing the bear, that
    moved along the trajectory. Can be assigned with the local geometric median of the cluster the
    trajectory belongs to.

    Attributes:
        bear_id (int): ID given to the individual bear.
        gender (str): Gender of the bear (m/f).
        age (str): Age of the bear (adult/subadult).
        season (str): Season of the time range of the trajectory.
        segment (list[TrajectoryPoint]): Represents the trajectory.
        local_geometric_median (tuple[float, float]): local geometric median of the trajectory's cluster
    """
    def __init__(self, bear_id, gender, age, segment):
        """Initializes the TrajectorySegment.

                Args:
                    bear_id (int): ID given to the individual bear.
                    gender (str): Gender of the bear (m/f).
                    age (str): Age of the bear (adult/subadult).
                    segment(list[TrajectoryPoint]): Represents the trajectory.
        """
        self.bear_id = bear_id
        self.gender = gender
        self.age = age
        self.season = None
        self.segment = segment
        self.local_geometric_median = None