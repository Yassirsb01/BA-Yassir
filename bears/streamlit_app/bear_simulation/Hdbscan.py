import numpy as np
import hdbscan


class Hdbscan:
    """Wrapper class for the HDBSCAN clustering algorithm.

    Provides a class-based interface for clustering points using the HDBSCAN algorithm from the `hdbscan` library.

    Class Attributes:
        cluster_selection_epsilon (float): Default epsilon value for fine-tuning cluster selection.
        metric (str): Default distance metric to use for clustering (e.g., 'euclidean').
    """
    cluster_selection_epsilon = 0.0
    metric = "euclidean"

    def __init__(self):
        pass

    @classmethod
    def get_clusters(cls, points, min_cluster_size, min_samples, metric=None, cluster_selection_epsilon=None):
        """Clusters a set of points using the HDBSCAN algorithm.

        Args:
            points (list[tuple[float, float]]): List of 2D points to cluster.
            min_cluster_size (int): Minimum number of points required to form a cluster.
            min_samples (int): Number of neighboring points required to classify a point as a core point.
            metric (str, optional): Distance metric to use. Defaults to the class-level metric if not specified.
            cluster_selection_epsilon (float, optional): Epsilon threshold to fine-tune cluster selection.
                Defaults to the class-level value if not specified.

        Returns:
            numpy.ndarray: An array of cluster labels corresponding to the input points.
                Outliers are labeled with -1.
        """
        points = np.array(points)

        if cluster_selection_epsilon is None:
            cluster_selection_epsilon = cls.cluster_selection_epsilon
        if metric is None:
            metric = cls.metric

        clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size,
                                    min_samples=min_samples,
                                    metric=metric,
                                    cluster_selection_epsilon=cluster_selection_epsilon)

        return clusterer.fit_predict(points)
