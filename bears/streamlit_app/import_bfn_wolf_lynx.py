"""
import_bfn_wolf_lynx.py
========================
Imports wolf and lynx occurrence data (occupied 10 x 10 km grid cells)
from the German Federal Agency for Nature Conservation (BfN) as a GeoJSON
layer.

Source: geodienste.bfn.de (INSPIRE download service, free to use)
        https://geodienste.bfn.de/ogc/wfs/INSPIRE_SD_DE_Luchs_Wolf_distribution
Data basis: monitoring data of the federal states (wolf 2023/24, lynx
            2019/20), compiled by the BfN.

Verified through GetCapabilities:
  - TypeNames: SD:Vorkommen_-_carnis_lupus__Wolf_
               SD:Vorkommen_-_lynx_lynx__Luchs_
  - The service supports outputFormat "GEOJSON", so no GML parsing and no
    geopandas or GDAL are required, only requests and json.

Context: Germany has no resident bear population. Wolf and lynx are the
large carnivores that are systematically monitored here, so this layer
adds a different species to the map rather than another bear dataset.
"""

import json
import requests
import streamlit as st

WFS_BASE_URL = "https://geodienste.bfn.de/ogc/wfs/INSPIRE_SD_DE_Luchs_Wolf_distribution"

TYPE_NAMES = {
    "wolf": "SD:Vorkommen_-_carnis_lupus__Wolf_",
    "luchs": "SD:Vorkommen_-_lynx_lynx__Luchs_",
}

# Farben passend zum bestehenden Schema in maplibre_component.py
SPECIES_COLOR = {
    "wolf": "#5b3a29",   # braun
    "luchs": "#8c8c8c",  # grey
}

# Bounding box of Germany, taken from the GetCapabilities response of the
# service. Used as a reference to detect and repair a swapped axis order
# automatically (see _fix_coordinate_order below).
GERMANY_LAT_RANGE = (46.5, 55.5)
GERMANY_LNG_RANGE = (5.5, 15.5)


def _fix_coordinate_order(coords):
    """
    Some WFS services, including this one as confirmed by testing, return
    coordinates in the order [latitude, longitude] (the ISO axis order of
    EPSG:4326) even with outputFormat=GEOJSON, instead of the GeoJSON
    standard [longitude, latitude] (RFC 7946). Without correction the
    polygons end up on the wrong side of the world, for example in the
    Gulf of Aden instead of Germany.

    This function walks a GeoJSON 'coordinates' array recursively, which
    works equally for Point, LineString, Polygon and MultiPolygon, and
    swaps a coordinate pair only when the values unambiguously match the
    bounding box of Germany. That stays safe if a future service update
    starts returning the correct order by itself.
    """
    if not coords:
        return coords

    # A single coordinate pair [a, b]?
    if isinstance(coords[0], (int, float)):
        a, b = coords[0], coords[1]
        a_is_lng = GERMANY_LNG_RANGE[0] <= a <= GERMANY_LNG_RANGE[1]
        b_is_lat = GERMANY_LAT_RANGE[0] <= b <= GERMANY_LAT_RANGE[1]
        if a_is_lng and b_is_lat:
            return coords  # schon korrekt [lng, lat] -> nichts tun

        a_is_lat = GERMANY_LAT_RANGE[0] <= a <= GERMANY_LAT_RANGE[1]
        b_is_lng = GERMANY_LNG_RANGE[0] <= b <= GERMANY_LNG_RANGE[1]
        if a_is_lat and b_is_lng:
            return [b, a]  # vertauscht -> korrigieren

        return coords  # ambiguous or outside Germany, so leave untouched

    return [_fix_coordinate_order(c) for c in coords]


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)  # once a day is enough; the data changes yearly
def fetch_bfn_species_geojson(species: str, timeout: int = 30) -> dict:
    """
    Fetch occurrence data (grid cells) for 'wolf' or 'luchs' as GeoJSON.

    Returns:
        A GeoJSON FeatureCollection. On error an empty FeatureCollection is
        returned, so the layer simply stays empty instead of crashing the
        application.
    """
    if species not in TYPE_NAMES:
        raise ValueError(f"Unknown species '{species}'. Allowed: {list(TYPE_NAMES)}")

    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": TYPE_NAMES[species],
        "OUTPUTFORMAT": "GEOJSON",
        # CRS:84 is explicitly defined by the OGC as always being
        # longitude, latitude, unlike EPSG:4326, whose ISO axis order is
        # latitude, longitude. That mismatch is the root of the problem.
        "SRSNAME": "CRS:84",
    }

    try:
        resp = requests.get(WFS_BASE_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[BfN WFS] Request failed ({species}): {e}")
        return {"type": "FeatureCollection", "features": []}

    # Embed the colour and a uniform "species" field into the properties,
    # so the map can colour the features through ['get','color'] exactly as
    # it does for the Carpathian and simulation layers, with no client-side
    # special cases. The axis order is additionally corrected defensively
    # (see above): CRS:84 should already fix it, but the check costs
    # nothing and catches a service that behaves differently.
    features = data.get("features", [])
    for f in features:
        props = f.setdefault("properties", {})
        props["species"] = species
        props["color"] = SPECIES_COLOR[species]

        geom = f.get("geometry")
        if geom and "coordinates" in geom:
            geom["coordinates"] = _fix_coordinate_order(geom["coordinates"])

    return {"type": "FeatureCollection", "features": features}


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def get_wolf_lynx_geojson() -> dict:
    """
    Combined layer with wolf and lynx in a single FeatureCollection, which
    fits the existing GROUPS pattern in maplibre_component.py directly: one
    source, one layer, colour taken from the properties.
    """
    wolf = fetch_bfn_species_geojson("wolf")
    luchs = fetch_bfn_species_geojson("luchs")
    return {
        "type": "FeatureCollection",
        "features": wolf["features"] + luchs["features"],
    }


if __name__ == "__main__":
    # Standalone check outside Streamlit. st.cache_data also works without
    # a running Streamlit app, behaving like a plain function call without
    # the spinner UI.
    print("Fetching wolf data...")
    wolf_fc = fetch_bfn_species_geojson("wolf")

    n = len(wolf_fc.get("features", []))
    print(f"Wolf grid cells received: {n}")

    if n > 0:
        print("\nFirst feature (to check the actual property names):")
        print(json.dumps(wolf_fc["features"][0], indent=2, ensure_ascii=False)[:1500])

    with open("bfn_wolf_test.geojson", "w", encoding="utf-8") as f:
        json.dump(wolf_fc, f, ensure_ascii=False)
    print("\nWritten to bfn_wolf_test.geojson for inspection, for example on geojson.io.")