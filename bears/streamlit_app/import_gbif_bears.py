"""
import_gbif_bears.py
=====================
Importiert echte Braunbaer-Sichtungsdaten (Ursus arctos) aus der GBIF
Occurrence API - weltweite, kostenfreie Biodiversitaetsdatenbank.

Quelle: https://api.gbif.org/v1/occurrence/search (stabile, oeffentliche
        REST-API, kein API-Key noetig, JSON-Antworten)

Nutzen fuer dieses Projekt:
  - Deutschland: seltene einzelne "Problembaeren" (keine feste Population,
    daher erwartbar sehr wenige/keine Datensaetze)
  - Rumaenien: zusaetzliche, unabhaengige Meldedaten als Vergleich/Ergaenzung
    zu den eigenen Carpathian-GPS-Trackingdaten

Verifiziert per Live-Abruf (05.08.2026): Endpoint + Antwortstruktur (Felder
wie decimalLatitude/decimalLongitude/scientificName/eventDate/gbifID/country)
sind uebereinstimmend mit der offiziellen GBIF-API-Dokumentation. Die genaue
Trefferzahl fuer Ursus arctos in DE/RO konnte im Sandbox-Test nicht gefiltert
abgerufen werden (Netzwerk-Einschraenkung) - bitte beim ersten echten Lauf
kurz pruefen, wie viele Datensaetze tatsaechlich zurueckkommen.
"""

import json
import requests
import streamlit as st

GBIF_OCCURRENCE_URL = "https://api.gbif.org/v1/occurrence/search"

# ISO-3166 Alpha-2 Laendercodes, wie von GBIF erwartet
COUNTRIES = {
    "DE": "#5b3a29",  # Deutschland - braun, passend zu anderen Baeren-Layern
    "RO": "#c77b2e",  # Rumaenien - etwas heller, um von DE zu unterscheiden
}


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)  # 1x taeglich reicht
def fetch_gbif_bear_occurrences(country: str, limit: int = 300, timeout: int = 30) -> list[dict]:
    """
    Holt Ursus-arctos-Sichtungen fuer ein Land von GBIF (mit Paginierung).

    Args:
        country: ISO-3166 Alpha-2 Code, z.B. "DE" oder "RO"
        limit: max. Datensaetze insgesamt (GBIF liefert max. 300 pro Request)

    Returns:
        Liste von GBIF-Occurrence-Dicts (rohe API-Records, noch kein GeoJSON)
    """
    all_records = []
    page_size = 300  # GBIF-Maximum pro Request
    offset = 0

    while len(all_records) < limit:
        params = {
            "scientificName": "Ursus arctos",
            "country": country,
            "hasCoordinate": "true",
            "hasGeospatialIssue": "false",  # keine als fehlerhaft markierten Koordinaten
            "limit": min(page_size, limit - len(all_records)),
            "offset": offset,
        }
        try:
            resp = requests.get(GBIF_OCCURRENCE_URL, params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[GBIF] Fehler beim Abruf ({country}, offset={offset}): {e}")
            break

        results = data.get("results", [])
        all_records.extend(results)

        if data.get("endOfRecords", True) or not results:
            break
        offset += page_size

    return all_records


def _records_to_geojson(records: list[dict], country: str) -> dict:
    """Wandelt rohe GBIF-Records in eine GeoJSON FeatureCollection um."""
    features = []
    color = COUNTRIES.get(country, "#5b3a29")

    for rec in records:
        lat = rec.get("decimalLatitude")
        lng = rec.get("decimalLongitude")
        if lat is None or lng is None:
            continue

        gbif_id = rec.get("gbifID") or rec.get("key")

        # GBIF liefert Bild-URLs direkt im 'media'-Feld mit (keine
        # zusaetzliche Anfrage noetig). Erstes Foto (type=StillImage) nehmen,
        # falls vorhanden - fuer eine Bild-Vorschau direkt im Kartenpopup.
        image_url = ""
        for m in rec.get("media", []):
            if m.get("type") == "StillImage" and m.get("identifier"):
                image_url = m["identifier"]
                break

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
    Kombinierter Layer ueber mehrere Laender - passt so direkt ins bestehende
    GROUPS-Muster in maplibre_component.py (ein Source, ein Layer).
    """
    all_features = []
    for country in countries:
        records = fetch_gbif_bear_occurrences(country, limit=limit_per_country)
        fc = _records_to_geojson(records, country)
        all_features.extend(fc["features"])
    return {"type": "FeatureCollection", "features": all_features}


if __name__ == "__main__":
    for cc in ("DE", "RO"):
        print(f"\nHole Ursus-arctos-Daten fuer {cc}...")
        records = fetch_gbif_bear_occurrences(cc, limit=300)
        print(f"  -> {len(records)} Datensaetze mit Koordinaten erhalten")

        if records:
            print("  Erster Datensatz (zur Kontrolle):")
            sample = {k: records[0].get(k) for k in
                      ["scientificName", "country", "eventDate", "decimalLatitude",
                       "decimalLongitude", "basisOfRecord", "institutionCode"]}
            print("  " + json.dumps(sample, indent=2, ensure_ascii=False))

    combined = get_gbif_bears_geojson()
    print(f"\nGesamt (DE+RO): {len(combined['features'])} Punkte")

    with open("gbif_bears_test.geojson", "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False)
    print("Gespeichert als gbif_bears_test.geojson zur Kontrolle (z.B. auf geojson.io ansehen).")