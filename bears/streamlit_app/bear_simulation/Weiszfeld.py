import numpy as np
from scipy.spatial.distance import cdist, euclidean

class Weiszfeld:
    """Provides methods to compute the (weighted) geometric median of a set of points using the Weiszfeld algorithm.

    Class Attributes:
        eps (float): Default tolerance for convergence.
    """
    eps = 1e-6

    def __init__(self):
        pass

    @classmethod
    def get_unweighted_median(cls, points, eps=None):
        """Computes the geometric (L1) median of a set of unweighted points using the Weiszfeld algorithm.

        Args:
            points (list[tuple[float, float]]): A list of 2D points.
            eps (float, optional): Tolerance for convergence. Defaults to class-level value.

        Returns:
            numpy.ndarray: The estimated geometric median as a 1D array [x, y].
        """

        if eps is None:
            eps = cls.eps

        points = np.array(points)

        def l1_median(X, eps=1e-6):
            y = np.mean(X, 0)  # the geometric mean is a fare start
            while True:
                while np.any(cdist(X, [y]) == 0):  # Euclidean distances, let's move away to avoid any null
                    y += 0.1 * np.ones(len(y))
                # set of weights that are the inverse of the distances from current estimate to the observations
                W = 1 / cdist(X, [y])  # element-wise
                # new estimate is the weighted average of the observations
                y1 = np.sum(W * X, 0) / np.sum(W)  # sum along axis 0
                if euclidean(y, y1) < eps:
                    return y1
                y = y1

        return l1_median(points, eps=eps)

    @classmethod
    def get_weighted_median(cls, points, weights, eps=None):
        """Computes the weighted geometric (L1) median of a set of points using the Weiszfeld algorithm.

        Args:
            points (list[tuple[float, float]]): A list of 2D points.
            weights (list[float]): Corresponding weights for each point.
            eps (float, optional): Tolerance for convergence. Defaults to class-level value.

        Returns:
            numpy.ndarray: The estimated weighted geometric median as a 1D array [x, y].
        """

        if eps is None:
            eps = cls.eps

        points = np.array(points)
        weights = np.array(weights)

        def weighted_l1_median(X, WX, eps=1e-6):
            y = np.average(X, axis=0, weights=WX)
            while True:
                while np.any(cdist(X, [y]) == 0):
                    y += 0.1 * np.ones(len(y))
                W = np.expand_dims(WX, axis=1) / cdist(X, [y])  # element-wise operation
                y1 = np.sum(W * X, 0) / np.sum(W)
                if euclidean(y, y1) < eps:
                    return y1
                y = y1

        return weighted_l1_median(points, weights, eps)
