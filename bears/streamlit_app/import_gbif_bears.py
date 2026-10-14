"""
import_gbif_bears.py
=====================
Imports brown bear sighting records (Ursus arctos) from the GBIF
Occurrence API, a free global biodiversity database.

Source: https://api.gbif.org/v1/occurrence/search (stable public REST API,
        no API key required, JSON responses)

Purpose in this project:
  - Germany: the occasional individual bear. There is no resident
    population, so very few records are expected.
  - Romania: additional, independent reports as a comparison and
    supplement to the project's own Carpathian GPS tracking data.

Verified against the live service: the endpoint and the response structure
(fields such as decimalLatitude, decimalLongitude, scientificName,
eventDate, gbifID and country) match the official GBIF API
documentation.
"""

import json
import requests
import streamlit as st

GBIF_OCCURRENCE_URL = "https://api.gbif.org/v1/occurrence/search"

# ISO-3166 Alpha-2 Laendercodes, wie von GBIF erwartet
COUNTRIES = {
    "DE": "#5b3a29",  # Germany - brown, matching the other bear layers
    "RO": "#c77b2e",  # Rumaenien - etwas heller, um von DE zu unterscheiden
}


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)  # 1x taeglich reicht
def fetch_gbif_bear_occurrences(country: str, limit: int = 300, timeout: int = 30) -> list[dict]:
    """
    Fetch Ursus arctos sightings for one country from GBIF, with paging.

    Args:
        country: ISO 3166 alpha-2 code, for example "DE" or "RO"
        limit: maximum number of records in total (GBIF returns at most
            300 per request)

    Returns:
        A list of GBIF occurrence dicts (raw API records, not yet GeoJSON)
    """
    all_records = []
    page_size = 300  # GBIF maximum per request
    offset = 0

    while len(all_records) < limit:
        params = {
            "scientificName": "Ursus arctos",
            "country": country,
            "hasCoordinate": "true",
            "hasGeospatialIssue": "false",  # exclude coordinates flagged as faulty
            # "PRESENT" only: "ABSENT" records mean the species was
            # searched for and not found, which would otherwise place
            # "no bear here" entries on the map.
            "occurrenceStatus": "PRESENT",
            "limit": min(page_size, limit - len(all_records)),
            "offset": offset,
        }
        try:
            resp = requests.get(GBIF_OCCURRENCE_URL, params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[GBIF] Request failed ({country}, offset={offset}): {e}")
            break

        results = data.get("results", [])
        all_records.extend(results)

        if data.get("endOfRecords", True) or not results:
            break
        offset += page_size

    return all_records


def _records_to_geojson(records: list[dict], country: str) -> dict:
    """Convert raw GBIF records into a GeoJSON FeatureCollection."""
    features = []
    color = COUNTRIES.get(country, "#5b3a29")

    # Record types that do not state "a wild bear was seen here":
    # FOSSIL_SPECIMEN covers fossil bone finds, for example museum
    # holdings that can be centuries or millennia old, and
    # LIVING_SPECIMEN covers animals in captivity such as zoos. Showing
    # either as a current wild sighting would misrepresent the map.
    _EXCLUDED_BASIS_OF_RECORD = {"FOSSIL_SPECIMEN", "LIVING_SPECIMEN"}

    for rec in records:
        lat = rec.get("decimalLatitude")
        lng = rec.get("decimalLongitude")
        if lat is None or lng is None:
            continue

        if rec.get("basisOfRecord") in _EXCLUDED_BASIS_OF_RECORD:
            continue

        # Checked again here in addition to the API parameter above, in
        # case this function is called with unfiltered raw records or GBIF
        # does not honour the parameter in some edge case.
        if rec.get("occurrenceStatus") == "ABSENT":
            continue

        gbif_id = rec.get("gbifID") or rec.get("key")

        # GBIF returns image URLs directly in the 'media' field, so no
        # extra request is needed. The first photo (type=StillImage) is
        # used for a thumbnail inside the map popup.
        image_url = ""
        for m in rec.get("media", []):
            if m.get("type") == "StillImage" and m.get("identifier"):
                image_url = m["identifier"]
                break

        # Fallback: some providers, for example records fed in through
        # naturgucker/enjoynature.net, use the simpler Darwin Core field
        # 'associatedMedia' instead of the full multimedia extension. It
        # holds one or more URLs separated by ' | '.
        if not image_url:
            associated = rec.get("associatedMedia", "")
            if associated:
                first_url = associated.split("|")[0].strip()
                if first_url.lower().startswith(("http://", "https://")):
                    image_url = first_url

        features.append({
            "type": "Feature",
            "properties": {
                "source": "gbif",
                "country": country,
                "color": color,
                "scientific_name": rec.get("scientificName", ""),
                "event_date": rec.get("eventDate", ""),
                "basis_of_record": rec.get("basisOfRecord", ""),
                "individual_count": rec.get("individualCount"),
                "recorded_by": rec.get("recordedBy", ""),
                "institution": rec.get("institutionCode", ""),
                "gbif_id": gbif_id,
                "gbif_url": f"https://www.gbif.org/occurrence/{gbif_id}" if gbif_id else "",
                "image_url": image_url,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [float(lng), float(lat)],
            },
        })

    return {"type": "FeatureCollection", "features": features}


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def get_gbif_bears_geojson(countries: tuple[str, ...] = ("DE", "RO"), limit_per_country: int = 300) -> dict:
    """
    Combined layer across several countries, which fits the existing
    GROUPS pattern in maplibre_component.py directly: one source, one
    layer.
    """
    all_features = []
    for country in countries:
        records = fetch_gbif_bear_occurrences(country, limit=limit_per_country)
        fc = _records_to_geojson(records, country)
        all_features.extend(fc["features"])
    return {"type": "FeatureCollection", "features": all_features}


if __name__ == "__main__":
    for cc in ("DE", "RO"):
        print(f"\nFetching Ursus arctos records for {cc}...")
        records = fetch_gbif_bear_occurrences(cc, limit=300)
        print(f"  -> {len(records)} records with coordinates received")

        if records:
            print("  First record (for inspection):")
            sample = {k: records[0].get(k) for k in
                      ["scientificName", "country", "eventDate", "decimalLatitude",
                       "decimalLongitude", "basisOfRecord", "institutionCode"]}
            print("  " + json.dumps(sample, indent=2, ensure_ascii=False))

    combined = get_gbif_bears_geojson()
    n_total = len(combined["features"])
    n_with_image = sum(1 for f in combined["features"] if f["properties"].get("image_url"))
    print(f"\nTotal (DE and RO): {n_total} points, {n_with_image} with a photo ({n_with_image/n_total*100:.0f}%)")

    with open("gbif_bears_test.geojson", "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False)
    print("Written to gbif_bears_test.geojson for inspection, for example on geojson.io.")