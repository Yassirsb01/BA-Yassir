from .DatabaseConnection import DatabaseConnection
from .WildlifeLocations import WildlifeLocations
from .BearSeasons import BearSeasons
from ..ClusterCalculator import ClusterCalculator
from ..MedianCalculator import MedianCalculator
from datetime import datetime
from .SeasonalCluster import SeasonalCluster
from geopy.distance import geodesic
import os
from ..GeoToolBox import GeoToolBox


class ClusterMap:
    def __init__(self, source, min_cluster_size, min_samples):
        self.db_path = os.path.join(os.path.dirname(__file__), "..", "data", "database.db")
        self.data = self.get_data(source)
        self.bs = BearSeasons()
        self.seasons = {"spring", "summer", "autumn", "winter"}
        self.clusters = None
        self.build_clusters(min_cluster_size, min_samples)

    def get_data(self, source):
        dbcon = DatabaseConnection(self.db_path)
        wlc = WildlifeLocations(dbcon)
        entries = wlc.get_by_source(source)
        return entries

    def get_time(self, entry):
        return datetime.strptime(entry[3], "%Y-%m-%d %H:%M:%S")

    def get_timespan(self):
        times = [self.get_time(entry) for entry in self.data]

        starting_year = min(times).year
        ending_year = max(times).year

        return starting_year, ending_year

    def group_data_by_season(self):
        seasonal_data = []
        start, end = self.get_timespan()
        for year in range(start, end + 1):
            for season in self.seasons:
                current_seasonal_data = []
                for entry in self.data:
                    current_time = self.get_time(entry)
                    current_season = self.bs.get_season(current_time)
                    if current_time.year == year:
                        if season == current_season:
                            current_seasonal_data.append(entry)
                seasonal_data.append({"year": year,
                                      "season": season,
                                      "data": current_seasonal_data})
        return seasonal_data

    def build_clusters(self, min_cluster_size, min_samples):
        self.clusters = []
        cc = ClusterCalculator()
        mc = MedianCalculator()

        seasonal_data = self.group_data_by_season()

        for group in seasonal_data:
            year = group["year"]
            season = group["season"]
            entries = group["data"]

            if not entries:
                continue

            coords = [(entry[4], entry[5]) for entry in entries]

            clustered = cc.get_clusters(
                coords,
                min_cluster_size=min_cluster_size,
                min_samples=min_samples
            )

            clusters_dict = {}
            for lat, lon, cluster_id in clustered:
                if cluster_id == -1:
                    continue
                if cluster_id not in clusters_dict:
                    clusters_dict[cluster_id] = []
                clusters_dict[cluster_id].append((lat, lon))

            for cluster_id, points in clusters_dict.items():
                sc = SeasonalCluster(
                    year=year,
                    season=season,
                    cluster_id=cluster_id,
                    points=points
                )
                sc.median = mc.get_unweighted_median(points)
                self.clusters.append(sc)

    # def get_median_for_segment(self, segment):
    #     if not segment.segment:
    #         return None
    #
    #     year = segment.segment[0].time.year
    #     season = self.bs.get_season(segment.segment[0].time)
    #     points = [(tp.lat, tp.lon) for tp in segment.segment]
    #
    #     matching_clusters = [
    #         cluster for cluster in self.clusters
    #         if cluster.year == year and cluster.season == season
    #     ]
    #
    #     cluster_hits = {}
    #     for cluster in matching_clusters:
    #         match_count = sum(
    #             1 for point in points
    #             if any(geodesic(point, cluster_point).meters <= 10 for cluster_point in cluster.points)
    #         )
    #         if match_count > 0:
    #             cluster_hits[cluster] = match_count
    #
    #     if cluster_hits:
    #         best_cluster = max(cluster_hits, key=cluster_hits.get)
    #         return best_cluster.median
    #
    #     return None

    def get_median_for_segment(self, segment):
        if not segment.segment:
            return None

        season = segment.season
        year = segment.segment[0].time.year

        latitudes = [tp.lat for tp in segment.segment]
        longitudes = [tp.lon for tp in segment.segment]
        center_lat = sum(latitudes) / len(latitudes)
        center_lon = sum(longitudes) / len(longitudes)

        candidates = [
            cluster for cluster in self.clusters
            if cluster.season == season and cluster.year == year
        ]

        for cluster in candidates:
            lats = [p[0] for p in cluster.points]
            lons = [p[1] for p in cluster.points]
            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)

            if (min_lat <= center_lat <= max_lat and
                    min_lon <= center_lon <= max_lon):
                return cluster.median

        if candidates:
            closest = min(
                candidates,
                key=lambda c: GeoToolBox.get_euclidean_distance(c.median, (center_lat, center_lon))
            )
            return closest.median

        return None









