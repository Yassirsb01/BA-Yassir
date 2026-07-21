import requests


class OpenStreetMapTerrain:
    """Retrieves terrain information from OpenStreetMap using the Overpass API.

    Sends spatial queries to the Overpass API to obtain tags such as land use, natural features,
    waterways, and more for a given location and radius.

    Class Attributes:
        OVERPASS_URL (str): The base URL of the Overpass API endpoint.
    """

    OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    def __init__(self):
        """Initializes the OpenStreetMapTerrain object."""
        pass

    def get_terrain_type(self, lat, lon, radius=200, query_elements=None):
        """Fetches terrain-related tags around a given geographic coordinate.

        Sends a query to the Overpass API to retrieve OSM tags such as land use, natural features,
        highways, waterways, and others within a given search radius.

        Args:
            lat (float): Latitude of the location.
            lon (float): Longitude of the location.
            radius (int, optional): Search radius in meters. Defaults to 200.
            query_elements (dict[str, list[str]], optional): Dictionary specifying the types of OSM elements
                (e.g., 'way', 'node') and their corresponding tags to search for. Uses default if not specified.

        Returns:
            dict[str, list[str] | None]: Dictionary of found terrain tags with lists of values or None if not found.

        Raises:
            Exception: If the Overpass API returns an error.
        """

        if query_elements is None:
            query_elements = {"way": ["landuse", "natural", "waterway", "water", "aerialway", "geological", "railway",
                                      "military", "highway", "place", "barrier", "leisure", "power"],
                              "node": ["landuse", "natural", "geological"]}

        query = "[out:json];\n("

        for element_type, tags in query_elements.items():
            for tag in tags:
                query += f"\n  {element_type}[\"{tag}\"](around:{radius},{lat},{lon});"

        query += "\n);\nout body geom;"

        response = requests.post(self.OVERPASS_URL, data={'data': query})
        if response.status_code != 200:
            raise Exception(f"Error: {response.status_code}: {response.text}")

        data = response.json()
        return self._parse_response(data, query_elements)

    def _parse_response(self, data, query_elements):
        """Parses the JSON response from the Overpass API.

        Extracts the requested tags and organizes them by tag name.

        Args:
            data (dict): The JSON data returned from the Overpass API.
            query_elements (dict[str, list[str]]): The original tag definitions used in the query.

        Returns:
            dict[str, list[str] | None]: Dictionary mapping tag names to lists of found values or None.
        """

        parsed_data = {tag: [] for element in query_elements.values() for tag in element}

        for element in data.get("elements", []):
            tags = element.get("tags", {})

            for tag in parsed_data.keys():
                if tag in tags:
                    parsed_data[tag].append(tags[tag])

        result = {tag: list(set(values)) if values else None for tag, values in parsed_data.items()}

        return result


if __name__ == "__main__":
    osm = OpenStreetMapTerrain()
    latitude = 49.007479
    longitude = 12.032298

    # latitude = 52.5200
    # longitude = 13.4050
    radius = 200

    result = osm.get_terrain_type(latitude, longitude, radius)
    print(f"Loaded Data for {latitude}, {longitude}: {result}")
