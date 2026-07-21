from .Hdbscan import Hdbscan
from .util.Algorithm import Algorithm
from .GeoToolBox import GeoToolBox


class ClusterCalculator:
    """Creates clusters out of geographic points using a specified algorithm.

    Assigns every point from a given set of points to a cluster identified by a number.
    May also identify outliers not being part of a cluster.
    Can be extended with alternative clustering algorithms.

    Attributes:
        algorithm (Hdbscan | None): A class implementing the clustering algorithm (Hdbscan).
        geo (GeoToolBox): Helper class with a set of methods for processing geographic coordinates.
    """

    def __init__(self, alg=Algorithm.HDBSCAN):
        """Initializes the ClusterCalculator.

                Args:
                    alg (Algorithm): clustering algorithm to be applied.
        """
        self.algorithm = None
        if alg == Algorithm.HDBSCAN:
            self.algorithm = Hdbscan()
        self.geo = GeoToolBox()

    def transform(self, points):
        """Prepares a set of points for a clustering algorithm applied to them.

        Transforms the geographic coordinates (lat, lon) of the points into geometric coordinates
        (x, y), so that common clustering algorithms can work with them.

        Args:
            points (List[Tuple[float, float]]): The list of points to be transformed.

        Returns:
            List[Tuple[float, float]: The list of transformed points.
        """
        conv_points = []
        for point in points:
            lat, lon = point
            x, y = self.geo.latlon_to_xy(lat, lon)
            conv_points.append((x, y))
        return conv_points

    def get_clusters(self,
                     coords,
                     min_cluster_size,
                     min_samples,
                     metric=None,
                     cluster_selection_epsilon=None):

        """Determines cluster affiliations for a set of points.

        Attaches a cluster identifier to each point of the set of points.
        Outliers, not being part of any cluster, will be assigned with a negative identifier.

        Args:
            coords (List[Tuple[float, float]]): The list of points to be transformed.
            min_cluster_size (int): The minimum number of points required to form a valid cluster.
            min_samples (int): The number of neighboring points required for a point to be considered a core point.
            metric (str, optional): The distance metric to use. For geographic data, 'haversine' is common.
                Defaults to 'euclidean' if not specified.
            cluster_selection_epsilon (float, optional): A tolerance parameter influencing how fine-grained the cluster
                selection should be. Lower values result in fewer, larger clusters.

        Returns:
            List[Tuple[float, float, int]]: The list of points with cluster identifiers.
        """

        points = self.transform(coords)

        clusters = self.algorithm.get_clusters(points,
                                               min_cluster_size,
                                               min_samples,
                                               metric=None,
                                               cluster_selection_epsilon=None)
        result = []
        for i in range(len(coords)):
            lat, lon = coords[i]
            cluster = clusters[i]
            result.append((lat, lon, cluster))
        return result


if __name__ == "__main__":
    from data.DatabaseConnection import DatabaseConnection
    from data.WildlifeLocations import WildlifeLocations
    from GeoToolBox import GeoToolBox
    import matplotlib.pyplot as plt
    import numpy as np

    geo = GeoToolBox()
    db_conn = DatabaseConnection()
    db = WildlifeLocations(db_conn)
    cc = ClusterCalculator()

    locations = db.get_all()

    points = []

    for location in locations:
        _, _, _, lat, lon, _, _ = location
        lat_utm, lon_utm, _ = geo.latlon_to_utm(lat, lon)
        points.append((lat_utm, lon_utm))

    clusters = cc.get_clusters(points, min_cluster_size=2, min_samples=1)

    points = np.array(points)
    clusters = np.array(clusters)

    print(clusters)

    plt.figure(figsize=(10, 8))

    unique_clusters = np.unique(clusters)
    for cluster_id in unique_clusters:
        mask = clusters == cluster_id

        if cluster_id == -1:
            plt.scatter(points[mask, 0], points[mask, 1], color='gray', label='Outliers')
        else:
            plt.scatter(points[mask, 0], points[mask, 1], label=f'Cluster {cluster_id}')

    plt.xlabel("Easting")
    plt.ylabel("Northing")
    plt.axis('equal')
    plt.title("HDBSCAN Cluster Visualization")
    plt.legend()
    plt.show()
