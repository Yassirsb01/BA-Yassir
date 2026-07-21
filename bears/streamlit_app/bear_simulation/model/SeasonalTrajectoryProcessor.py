from ..ClusterCalculator import ClusterCalculator
from ..MedianCalculator import MedianCalculator
from ..data.BearSeasons import BearSeasons
from ..data.ClusterMap import ClusterMap
from .TrajectorySegment import TrajectorySegment


class SeasonalTrajectoryProcessor:
    """Helper class for StepTrajectorySet.

    Splits Trajectories by season and assigns the local geometric medians of the clusters they belong to.

    Attributes:
        trajectories (list[TrajectorySegment]): The trajectories to be processed.
        bs (BearSeasons): Provides the season corresponding to a given timestamp.
        cm (ClusterMap): Computes clusters from bear sightings and their medians.
    """
    def __init__(self):
        """Initializes a new SeasonalTrajectoryProcessor object."""

        self.trajectories = None
        self.cc = ClusterCalculator()
        self.mc = MedianCalculator()
        self.bs = BearSeasons()
        self.cm = ClusterMap("Carpathians", 30, 10)

    def split_segments_by_season(self):
        """Splits trajectories by season."""
        new_segments = []

        for segment in self.trajectories:
            current_season = None
            current_points = []

            for tp in segment.segment:
                season = self.bs.get_season(tp.time)

                if current_season is None:
                    current_season = season

                if season != current_season:
                    if current_points:
                        new_segment = TrajectorySegment(
                            bear_id=segment.bear_id,
                            gender=segment.gender,
                            age=segment.age,
                            segment=current_points
                        )
                        new_segment.season = current_season
                        new_segments.append(new_segment)

                    current_points = []
                    current_season = season

                current_points.append(tp)

            if current_points:
                new_segment = TrajectorySegment(
                    bear_id=segment.bear_id,
                    gender=segment.gender,
                    age=segment.age,
                    segment=current_points
                )
                new_segment.season = current_season
                new_segments.append(new_segment)

        self.trajectories = new_segments

    def assign_geometric_medians(self):
        """Assigns local geometric medians to each trajectory segment based on its cluster."""
        for trajectory_segment in self.trajectories:
            trajectory_segment.local_geometric_median = self.cm.get_median_for_segment(trajectory_segment)
