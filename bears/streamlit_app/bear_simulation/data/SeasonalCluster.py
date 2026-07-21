
class SeasonalCluster:
    def __init__(self, year, season, cluster_id, points):
        self.year = year
        self.season = season
        self.cluster_id = cluster_id
        self.points = points
        self.median = None