from .Weiszfeld import Weiszfeld
from .util.Algorithm import Algorithm
from .GeoToolBox import GeoToolBox


class MedianCalculator:
    """Calculates geometric medians (weighted and unweighted) for geographic coordinates.

    Transforms coordinates from latitude/longitude to planar space (Web Mercator),
    applies a selected median algorithm (e.g., Weiszfeld), and converts the result back.

    Attributes:
        algorithm (Weiszfeld): The algorithm used to compute the median.
        geo (GeoToolBox): Utility for coordinate transformations.
    """
    def __init__(self, alg=Algorithm.WEISZFELD):
        """Initializes the MedianCalculator with the chosen algorithm.

        Args:
            alg (Algorithm, optional): The algorithm to use for median calculation.
                Defaults to Algorithm.WEISZFELD.
        """

        self.algorithm = None
        if alg == Algorithm.WEISZFELD:
            self.algorithm = Weiszfeld()
        self.geo = GeoToolBox()

    def transform(self, points):
        """Transforms geographic coordinates to planar X/Y coordinates.

        Args:
            points (list[tuple[float, float]]): List of (latitude, longitude) points.

        Returns:
            list[tuple[float, float]]: List of transformed (x, y) coordinates.
        """
        conv_points = []
        for point in points:
            lat, lon = point
            x, y = self.geo.latlon_to_xy(lat, lon)
            conv_points.append((x, y))
        return conv_points

    def transform_back(self, point):
        """Transforms a single planar X/Y point back to geographic coordinates.

        Args:
            point (tuple[float, float]): The (x, y) coordinate.

        Returns:
            tuple[float, float]: The corresponding (latitude, longitude).
        """
        x, y = point
        lat, lon = self.geo.xy_to_latlon(x, y)
        return lat, lon

    def get_unweighted_median(self, coords, eps=None):
        """Calculates the unweighted geometric median of geographic coordinates.

        Args:
            coords (list[tuple[float, float]]): List of (latitude, longitude) coordinates.
            eps (float, optional): Convergence tolerance for the algorithm. If None, default is used.

        Returns:
            tuple[float, float]: The estimated median point as (latitude, longitude).
        """
        points = self.transform(coords)

        if eps is None:
            median = self.algorithm.get_unweighted_median(points)
        else:
            median = self.algorithm.get_unweighted_median(points, eps)

        conv_median = self.transform_back(median)
        return conv_median

    def get_weighted_median(self, coords, weights, eps=None):
        """Calculates the weighted geometric median of geographic coordinates.

        Args:
            coords (list[tuple[float, float]]): List of (latitude, longitude) coordinates.
            weights (list[float]): List of weights corresponding to each coordinate.
            eps (float, optional): Convergence tolerance for the algorithm. If None, default is used.

        Returns:
            tuple[float, float]: The estimated median point as (latitude, longitude).
        """
        points = self.transform(coords)

        if eps is None:
            median = self.algorithm.get_weighted_median(points, weights)
        else:
            median = self.algorithm.get_weighted_median(points, weights, eps)

        conv_median = self.transform_back(median)
        return conv_median
