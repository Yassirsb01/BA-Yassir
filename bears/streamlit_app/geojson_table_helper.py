"""
geojson_table_helper.py
=========================
Kleine, wiederverwendbare Hilfsfunktion: wandelt eine GeoJSON-
FeatureCollection in eine flache pandas-Tabelle um (properties + lat/lng-
Spalten). Wird auf allen drei Karten-Seiten genutzt (Hauptkarte,
Experimente, Japan-Experiment), damit unter jeder Kartenvisualisierung
eine Tabelle der zugrundeliegenden Daten steht - zum Nachvollziehen, was
tatsaechlich auf der Karte zu sehen ist, direkt aus derselben Quelle wie
die Kartendarstellung (keine zweite, potenziell abweichende Abfrage).
"""

import pandas as pd


def geojson_to_dataframe(fc: dict) -> pd.DataFrame:
    """
    Point-Features -> eine Zeile mit lat/lng-Spalten direkt aus der Geometrie.
    LineString-Features -> eine Zeile mit Start-/Endpunkt + Anzahl Stuetzpunkte
    (einzelne Koordinaten waeren in einer Tabellenzeile unlesbar).
    Polygon/MultiPolygon -> nur der Geometrietyp, aus demselben Grund.
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
            props["anzahl_punkte"] = len(coords)
            if coords:
                props["start_lng"], props["start_lat"] = coords[0]
                props["end_lng"], props["end_lat"] = coords[-1]
        elif gtype in ("Polygon", "MultiPolygon"):
            props["geometrie_typ"] = gtype

        rows.append(props)

    return pd.DataFrame(rows)
