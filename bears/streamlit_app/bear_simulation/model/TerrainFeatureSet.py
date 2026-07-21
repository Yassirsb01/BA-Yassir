from OSM import OpenStreetMapTerrain


class TerrainFeatureSet:
    """Generates and holds environment feature list for geographic points.

       Creates a list of predefined terrain features, relevant for bears, determining
       their presence for a given geographic point and radius around it using the
       Overpass API by OpenStreetMap.

    Attributes:
        latitude (float): Latitude of the geographic point.
        longitude (float): Longitude of the geographic point.
        radius (int): Radius around the geographic point.
        osm (OpenStreetMapTerrain): Class for contacting the Overpass API.
        features (dict): Features and their presence marked by flags.
    """
    def __init__(self, coords, radius):
        """Initializes the TerrainFeatureSet and creates the feature list.

                Args:
                    coords (tuple[float, float]): Coordinates of the geographic point.
                    radius (int): Radius around the geographic point.
        """
        self.latitude = coords[0]
        self.longitude = coords[1]
        self.radius = radius
        self.osm = OpenStreetMapTerrain()

        feature_list = [
            # Aerialways (Tag: Aerialway)
            "aerialway",
            # Barriers (Tag: Barrier)
            "barrier",
            # Railways (Tag: Railway)
            "railway",
            # Roads and Paths (Tag: Highway)
            "motorway", "primary", "secondary", "tertiary",
            "footway", "path", "track", "steps",
            # Agriculture and Forestry (Tag: Landuse)
            "farmland", "animal_keeping", "forest", "meadow",
            "orchard", "vineyard",
            # Protected Wildlife Areas (Tag: Leisure)
            "nature_reserve",
            # Human Populated Areas (Tag: Landuse)
            "residential", "commercial", "industrial",
            # Human Populated Areas (Tag: Place)
            "city", "suburb", "town", "village",
            # Human Populated Areas (Tag: Military)
            "military",
            # Infrastructure (Tag: Power)
            "power",
            # Natural Areas or Objects (Tag: Natural)
            "wood", "scrub", "grassland", "tree", "tree_row",
            "wetland", "rock", "bare_rock", "stone", "hill",
            "cliff", "cave_entrance",
            # Bodies of Water (Tag: Water, Waterway)
            "river", "canal", "lake", "pond", "wastewater",
            # Bodies of Water (Tag: Waterway)
            "stream"
        ]

        self.features = {name: 0 for name in feature_list}
        self.query_features(self.latitude, self.longitude, self.radius)

    def query_features(self, latitude, longitude, radius):
        """Queries terrain features for a geographic point using the Overpass API.

        Args:
            latitude (float): Latitude of the geographic point.
            longitude (float): Longitude of the geographic point.
            radius (int): Radius around the geographic point.
        """
        result = self.osm.get_terrain_type(latitude, longitude, radius)
        for tag, values in result.items():
            if values is not None:
                for value in values:
                    if value in self.features:
                        self.features[value] = 1
                if tag in self.features:
                    self.features[tag] = 1


if __name__ == "__main__":
    tfs = TerrainFeatureSet((49.007457, 12.032305), 200)

    for key, value in tfs.features.items():
        print(f"{key}: {value}")
