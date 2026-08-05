"""
import_bfn_wolf_lynx.py
========================
Importiert echte Wolf-/Luchs-Vorkommensdaten (besetzte 10x10km Rasterzellen)
vom Bundesamt fuer Naturschutz (BfN) als GeoJSON-Layer.

Quelle: geodienste.bfn.de (INSPIRE-Downloaddienst, kostenfrei nutzbar)
        https://geodienste.bfn.de/ogc/wfs/INSPIRE_SD_DE_Luchs_Wolf_distribution
Datenbasis: Monitoringdaten der Bundeslaender (Wolf 2023/24, Luchs 2019/20),
            zusammengestellt vom BfN.

Verifiziert per GetCapabilities (05.08.2026):
  - TypeNames: SD:Vorkommen_-_carnis_lupus__Wolf_
               SD:Vorkommen_-_lynx_lynx__Luchs_
  - outputFormat "GEOJSON" wird vom Dienst unterstuetzt -> kein GML-Parsing,
    kein geopandas/GDAL noetig, nur requests + json.

Wichtig: Deutschland hat keine feste Baerenpopulation. Wolf und Luchs sind
die tatsaechlich systematisch ueberwachten Grossraubtiere hierzulande. Dieser
Layer bringt also eine neue Tierart ins Kartenportal (nicht "Baer"), passend
zu Prof. Duennwebers urspruenglichem Hinweis auf die DBBW.
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
    "luchs": "#8c8c8c",  # grau
}

# Echte Bounding Box aus der GetCapabilities-Antwort des Dienstes (Deutschland).
# Dient als Referenz, um eine vertauschte Achsenreihenfolge automatisch zu
# erkennen und zu reparieren (siehe _fix_coordinate_order unten).
GERMANY_LAT_RANGE = (46.5, 55.5)
GERMANY_LNG_RANGE = (5.5, 15.5)


def _fix_coordinate_order(coords):
    """
    Manche WFS-Dienste (so auch dieser hier, per Test bestaetigt) liefern
    Koordinaten trotz outputFormat=GEOJSON in der Reihenfolge [Breite, Laenge]
    (EPSG:4326-Achsenreihenfolge nach ISO-Norm), statt im GeoJSON-Standard
    [Laenge, Breite] (RFC 7946). Ohne Korrektur landen die Polygone am
    falschen Ende der Welt (z.B. Golf von Aden statt Deutschland).

    Diese Funktion laeuft rekursiv durch ein GeoJSON-'coordinates'-Array
    (funktioniert fuer Point/LineString/Polygon/MultiPolygon gleichermassen)
    und vertauscht pro Koordinatenpaar nur dann, wenn die Werte eindeutig
    zur Deutschland-Bounding-Box passen -> sicher, auch falls ein zukuenftiger
    Dienst-Update die Reihenfolge von sich aus schon korrekt liefert.
    """
    if not coords:
        return coords

    # Einzelnes Koordinatenpaar [a, b]?
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

        return coords  # unklar/ausserhalb Deutschlands -> nicht anfassen

    return [_fix_coordinate_order(c) for c in coords]


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)  # 1x taeglich reicht, Daten aendern sich jaehrlich
def fetch_bfn_species_geojson(species: str, timeout: int = 30) -> dict:
    """
    Holt Vorkommensdaten (Rasterzellen) fuer 'wolf' oder 'luchs' direkt als GeoJSON.

    Returns:
        GeoJSON FeatureCollection. Bei Fehlern: leere FeatureCollection
        (Layer bleibt dann einfach leer, statt die App abstuerzen zu lassen).
    """
    if species not in TYPE_NAMES:
        raise ValueError(f"Unbekannte Art '{species}'. Erlaubt: {list(TYPE_NAMES)}")

    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": TYPE_NAMES[species],
        "OUTPUTFORMAT": "GEOJSON",
        # CRS:84 ist von OGC explizit als "immer Laenge,Breite" definiert -
        # anders als EPSG:4326, das nach ISO-Achsenreihenfolge eigentlich
        # Breite,Laenge waere (der eigentliche Grund fuer den Bug).
        "SRSNAME": "CRS:84",
    }

    try:
        resp = requests.get(WFS_BASE_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[BfN WFS] Fehler beim Abruf ({species}): {e}")
        return {"type": "FeatureCollection", "features": []}

    # Farbe + einheitliches "species"-Feld in die properties einbetten,
    # damit die Karte (wie bei Carpathian/Simulation) per ['get','color']
    # faerben kann, ohne clientseitige Sonderfaelle.
    # Zusaetzlich: Achsenreihenfolge defensiv korrigieren (siehe oben) - auch
    # wenn CRS:84 den Fehler beheben sollte, schadet die Sicherheitspruefung
    # nicht und faengt es ab, falls der Dienst sich anders verhaelt.
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
    Kombinierter Layer: Wolf + Luchs in einer FeatureCollection.
    So passt es 1:1 in das bestehende GROUPS-Muster in maplibre_component.py
    (ein Source, ein Layer, Farbe kommt aus den properties).
    """
    wolf = fetch_bfn_species_geojson("wolf")
    luchs = fetch_bfn_species_geojson("luchs")
    return {
        "type": "FeatureCollection",
        "features": wolf["features"] + luchs["features"],
    }


if __name__ == "__main__":
    # Standalone-Test ausserhalb von Streamlit. st.cache_data funktioniert
    # auch ohne laufende Streamlit-App als normaler Funktionsaufruf (nur
    # ohne die Streamlit-typische Spinner-UI).
    print("Hole Wolf-Daten...")
    wolf_fc = fetch_bfn_species_geojson("wolf")

    n = len(wolf_fc.get("features", []))
    print(f"Wolf-Rasterzellen erhalten: {n}")

    if n > 0:
        print("\nErstes Feature (zur Kontrolle der echten Property-Namen):")
        print(json.dumps(wolf_fc["features"][0], indent=2, ensure_ascii=False)[:1500])

    with open("bfn_wolf_test.geojson", "w", encoding="utf-8") as f:
        json.dump(wolf_fc, f, ensure_ascii=False)
    print("\nGespeichert als bfn_wolf_test.geojson zur Kontrolle (z.B. auf geojson.io ansehen).")