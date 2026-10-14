"""
geojson_table_helper.py
=========================
Small reusable helper that converts a GeoJSON FeatureCollection into a flat
pandas table (properties plus lat/lng columns). Used by all three map pages
(main map, Experiments, Japan experiment) so that every map visualisation is
accompanied by a table of the underlying data. The table is built from the
same object that feeds the map, so it cannot diverge from what is displayed.
"""

import pandas as pd


def geojson_to_dataframe(fc: dict) -> pd.DataFrame:
    """
    Point features become one row with lat/lng columns taken directly from
    the geometry.

    LineString features become one row with start and end point plus the
    number of vertices; listing every coordinate would make the table row
    unreadable.

    Polygon and MultiPolygon features contribute only their geometry type,
    for the same reason.
    """
    if not fc or not fc.get("features"):
        return pd.DataFrame()

    rows = []
    for f in fc["features"]:
        props = dict(f.get("properties", {}))
        geom = f.get("geometry", {}) or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates")

        if gtype == "Point" and coords:
            props["lng"] = coords[0]
            props["lat"] = coords[1]
        elif gtype == "LineString" and coords:
            props["point_count"] = len(coords)
            if coords:
                props["start_lng"], props["start_lat"] = coords[0]
                props["end_lng"], props["end_lat"] = coords[-1]
        elif gtype in ("Polygon", "MultiPolygon"):
            props["geometry_type"] = gtype

        rows.append(props)

    return pd.DataFrame(rows)
