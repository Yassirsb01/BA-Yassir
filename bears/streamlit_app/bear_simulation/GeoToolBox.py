import utm
from pyproj import Transformer
from geographiclib.geodesic import Geodesic
from geopy.distance import geodesic
from geopy.point import Point
import math


class GeoToolBox:
    """A collection of geographic utility functions for coordinate conversion and distance calculation.

    This class provides static-like methods for transforming between coordinate systems,
    computing geodesic distances and directions, and converting between latitude/longitude,
    UTM, and projected coordinates (EPSG:3857).

    All methods are class methods and can be used without instantiating the class.

    Class Attributes:
        latlon_xy_transformer (Transformer): Transforms coordinates from WGS84 (EPSG:4326) to Web Mercator (EPSG:3857).
        xy_latlon_transformer (Transformer): Transforms coordinates from Web Mercator (EPSG:3857) to WGS84 (EPSG:4326).
    """
    latlon_xy_transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    xy_latlon_transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    def __init__(self):
        pass

    @classmethod
    def latlon_to_utm(cls, latitude, longitude):
        """Converts latitude and longitude to UTM coordinates.

        Args:
            latitude (float): Latitude in decimal degrees.
            longitude (float): Longitude in decimal degrees.

        Returns:
            tuple[float, float, str]: Easting, northing, and UTM zone as a string (e.g., "33T").
        """
        easting, northing, zone_number, zone_letter = utm.from_latlon(latitude, longitude)
        return easting, northing, f"{zone_number}{zone_letter}"

    @classmethod
    def utm_to_latlon(cls, easting, northing, zone):
        """Converts UTM coordinates to latitude and longitude.

        Args:
            easting (float): UTM easting.
            northing (float): UTM northing.
            zone (str): UTM zone (e.g., "33T").

        Returns:
            tuple[float, float]: Latitude and longitude in decimal degrees.
        """
        zone_number = int(zone[:-1])
        zone_letter = zone[-1]
        latitude, longitude = utm.to_latlon(easting, northing, zone_number, zone_letter)
        return latitude, longitude

    @classmethod
    def latlon_to_xy(cls, latitude, longitude):
        """Projects latitude and longitude to Web Mercator (EPSG:3857) coordinates.

        Args:
            latitude (float): Latitude in decimal degrees.
            longitude (float): Longitude in decimal degrees.

        Returns:
            tuple[float, float]: X and Y coordinates in meters.
        """
        x, y = cls.latlon_xy_transformer.transform(longitude, latitude)
        return x, y

    @classmethod
    def xy_to_latlon(cls, x, y):
        """Converts Web Mercator (EPSG:3857) coordinates back to latitude and longitude.

        Args:
            x (float): X coordinate in meters.
            y (float): Y coordinate in meters.

        Returns:
            tuple[float, float]: Latitude and longitude in decimal degrees.
        """
        longitude, latitude = cls.xy_latlon_transformer.transform(x, y)
        return latitude, longitude

    @classmethod
    def calculate_direction(cls, start, end):
        """Calculates the azimuth (bearing) from the start point to the end point.

        Args:
            start (tuple[float, float]): Start point as (latitude, longitude).
            end (tuple[float, float]): End point as (latitude, longitude).

        Returns:
            float: Azimuth in degrees from North (0–360).
        """
        result = Geodesic.WGS84.Inverse(start[0], start[1], end[0], end[1])
        return result['azi1'] % 360

    @classmethod
    def destination_point(cls, start, direction_deg, distance_m):
        """Computes the destination point given a start point, bearing, and distance.

        Args:
            start (tuple[float, float]): Starting point as (latitude, longitude).
            direction_deg (float): Bearing in degrees from North.
            distance_m (float): Distance to travel in meters.

        Returns:
            tuple[float, float]: Destination point as (latitude, longitude).
        """
        origin = Point(start[0], start[1])
        destination = geodesic(meters=distance_m).destination(origin, direction_deg)
        return destination.latitude, destination.longitude

    @classmethod
    def get_euclidean_distance(cls, start, end):
        """Calculates Euclidean (straight-line) distance between two points.

        Args:
            start (tuple[float, float]): First point as (x, y).
            end (tuple[float, float]): Second point as (x, y).

        Returns:
            float: Euclidean distance.
        """
        return math.sqrt((start[0] - end[0]) ** 2 + (start[1] - end[1]) ** 2)




