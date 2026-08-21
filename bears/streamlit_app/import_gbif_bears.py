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
            "occurrenceStatus": "PRESENT",  # nicht "ABSENT" (= gezielt gesucht, nicht gefunden -
                                             # sonst landen "kein Baer hier"-Eintraege auf der Karte)
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

    # Datensatztypen, die keine "wilde Baer wurde hier gesehen"-Aussage sind:
    # FOSSIL_SPECIMEN = fossile Knochenfunde (z.B. Museumsbestaende, teils
    #   Jahrhunderte/Jahrtausende alt), LIVING_SPECIMEN = Tiere in
    #   Gefangenschaft (Zoo/Gehege). Beides wuerde die Karte verfaelschen,
    #   wenn es wie eine aktuelle Wildsichtung dargestellt wird.
    _EXCLUDED_BASIS_OF_RECORD = {"FOSSIL_SPECIMEN", "LIVING_SPECIMEN"}

    for rec in records:
        lat = rec.get("decimalLatitude")
        lng = rec.get("decimalLongitude")
        if lat is None or lng is None:
            continue

        if rec.get("basisOfRecord") in _EXCLUDED_BASIS_OF_RECORD:
            continue

        # Defensiv zusaetzlich zum API-Parameter oben pruefen (falls diese
        # Funktion mal mit ungefilterten Rohdaten aufgerufen wird, oder GBIF
        # den Parameter in einem Sonderfall nicht greifen laesst).
        if rec.get("occurrenceStatus") == "ABSENT":
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

        # Fallback: manche Anbieter (z.B. ueber naturgucker/enjoynature.net
        # eingespeiste Datensaetze) nutzen statt der vollen Multimedia-
        # Extension nur das einfachere Darwin-Core-Feld 'associatedMedia'
        # (eine oder mehrere URLs, getrennt durch ' | ').
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
    n_total = len(combined["features"])
    n_with_image = sum(1 for f in combined["features"] if f["properties"].get("image_url"))
    print(f"\nGesamt (DE+RO): {n_total} Punkte, davon {n_with_image} mit Foto ({n_with_image/n_total*100:.0f}%)")

    with open("gbif_bears_test.geojson", "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False)
    print("Gespeichert als gbif_bears_test.geojson zur Kontrolle (z.B. auf geojson.io ansehen).")