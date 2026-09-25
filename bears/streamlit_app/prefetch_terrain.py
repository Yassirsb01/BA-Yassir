"""
prefetch_terrain.py
=====================
Laedt die Gelaendedaten (OpenStreetMap) fuer das GESAMTE Gebiet der
japanischen Kameras EINMALIG herunter und rechnet sie lokal in das Raster
um, das terrain_cache.py ohnehin verwendet. Danach laeuft die
Gelaendegewichtung der Simulation komplett offline.

Warum: Bisher wurde bei JEDEM Simulationsschritt, fuer JEDE der 8
Kandidatenrichtungen, live bei der Overpass-API nachgefragt - bei mehreren
Baeren und Stunden also tausende Einzelanfragen. Mit einem unzuverlaessigen
Netz (OTH) fuehrte das zu minutenlangen Wartezeiten bzw. zum Abschalten der
Gewichtung. Jetzt: wenige grosse Abfragen einmalig, danach nur noch
lokales Nachschlagen in Millisekunden.

Nebenbei eine inhaltliche Verbesserung: Overpass' around-Filter misst den
Abstand zur UMRISSLINIE eines Gebiets. Mitten in einem grossen Waldstueck
(weit weg vom Waldrand) wurde der Wald deshalb bisher nicht erkannt. Hier
wird zusaetzlich geprueft, ob ein Rasterpunkt INNERHALB einer Flaeche liegt.

Aufruf (einmalig, dort wo Internet/Overpass funktioniert - z.B. zuhause
oder per Handy-Hotspot):

    python prefetch_terrain.py

Falls Python die Server nicht erreicht, aber der Browser schon:

    python prefetch_terrain.py --print-query      (Abfrage anzeigen)
    -> auf https://overpass-turbo.eu einfuegen, "Ausfuehren",
       dann "Export" -> "Rohdaten" (JSON) speichern, z.B. als gelaende.json
    python prefetch_terrain.py --from-file gelaende.json

Ergebnis landet in bear_simulation/data/terrain_cache.db - diese Datei
einfach mit auf den Labor-PC kopieren (oder ins Git-Repository legen).
"""

import argparse
import json
import math
import os
import shutil
import sqlite3
import sys
import time

import numpy as np
import requests

from terrain_cache import (
    TerrainCache, DEFAULT_CACHE_DB, DEFAULT_QUERY_ELEMENTS, GRID_SIZE_DEG,
    HEADERS, OVERPASS_URLS,
)

DEFAULT_RADIUS_M = 150      # muss zu query_radius_m in japan_comparison.choose_weighted_direction passen
DEFAULT_BUFFER_KM = 5.0     # Puffer um die Kameras (so weit koennen simulierte Baeren laufen)
DEFAULT_TILE_DEG = 0.08     # Kachelgroesse fuer den Download (~9 km) - kleinere Abfragen = weniger Timeouts
REQUEST_TIMEOUT_S = 240
M_PER_DEG_LAT = 111_320.0

RAW_DIR = os.path.join(os.path.dirname(DEFAULT_CACHE_DB), "terrain_prefetch_raw")


# =========================================================
# 1) Gebiet bestimmen
# =========================================================
def camera_bbox(buffer_km: float) -> tuple[float, float, float, float]:
    """(sued, west, nord, ost) um alle Kamerastandorte plus Puffer."""
    from japan_comparison import load_japan_cameras
    cams = load_japan_cameras()
    if not cams:
        raise RuntimeError("Keine Kamerastandorte gefunden (bear_simulation/2024Bear/ReadMe.csv?).")
    lats = [c["lat"] for c in cams]
    lons = [c["lng"] for c in cams]
    lat_mid = (min(lats) + max(lats)) / 2
    dlat = buffer_km * 1000 / M_PER_DEG_LAT
    dlon = buffer_km * 1000 / (M_PER_DEG_LAT * math.cos(math.radians(lat_mid)))
    return (min(lats) - dlat, min(lons) - dlon, max(lats) + dlat, max(lons) + dlon)


def build_query(bbox, timeout_s: int = 180) -> str:
    """Dieselben Tags wie terrain_cache.py (und Fabians OSM.py), aber per
    Bounding-Box statt around-Radius um einen einzelnen Punkt."""
    s, w, n, e = bbox
    q = f"[out:json][timeout:{timeout_s}];\n("
    for element_type, tags in DEFAULT_QUERY_ELEMENTS.items():
        for tag in tags:
            q += f'\n  {element_type}["{tag}"]({s:.6f},{w:.6f},{n:.6f},{e:.6f});'
    q += "\n);\nout body geom;"
    return q


# =========================================================
# 2) Download (gekachelt, mit Wiederaufnahme)
# =========================================================
def download_tiles(bbox, tile_deg: float, raw_dir: str = RAW_DIR) -> tuple[list[str], list[str]]:
    """
    Teilt das Gebiet in Kacheln und laedt jede einzeln. Bereits geladene
    Kacheln werden uebersprungen - bricht der Download ab, einfach erneut
    starten, es geht an der Stelle weiter.
    """
    os.makedirs(raw_dir, exist_ok=True)
    s, w, n, e = bbox
    lat_edges = list(np.arange(s, n, tile_deg)) + [n]
    lon_edges = list(np.arange(w, e, tile_deg)) + [e]
    tiles = [
        (i, j, (lat_edges[i], lon_edges[j], lat_edges[i + 1], lon_edges[j + 1]))
        for i in range(len(lat_edges) - 1) for j in range(len(lon_edges) - 1)
    ]

    done, failed = [], []
    for k, (i, j, tb) in enumerate(tiles, 1):
        path = os.path.join(raw_dir, f"tile_{i}_{j}.json")
        if os.path.exists(path):
            print(f"  Kachel {k}/{len(tiles)}: bereits vorhanden, uebersprungen")
            done.append(path)
            continue

        query = build_query(tb)
        ok = False
        for url in OVERPASS_URLS:
            try:
                print(f"  Kachel {k}/{len(tiles)}: lade von {url.split('/')[2]} ...", end=" ", flush=True)
                resp = requests.post(url, data={"data": query}, headers=HEADERS, timeout=REQUEST_TIMEOUT_S)
                if resp.status_code == 200:
                    data = resp.json()
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f)
                    print(f"ok ({len(data.get('elements', []))} Elemente)")
                    done.append(path)
                    ok = True
                    break
                print(f"HTTP {resp.status_code}")
            except Exception as ex:
                print(f"Fehler: {type(ex).__name__}")
            time.sleep(2)
        if not ok:
            failed.append(path)
        time.sleep(2)  # Overpass nicht ueberlasten
    return done, failed


def load_elements(paths: list[str]) -> list[dict]:
    """Liest alle Rohdateien und entfernt Duplikate (Elemente an Kachelgrenzen)."""
    seen, elements = set(), []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        for el in data.get("elements", []):
            key = (el.get("type"), el.get("id"))
            if key in seen:
                continue
            seen.add(key)
            elements.append(el)
    return elements


# =========================================================
# 3) Lokale Rasterung
# =========================================================
def _min_dist_to_segments(px, py, ax, ay, bx, by) -> np.ndarray:
    """Kleinster Abstand jedes Punktes (px,py) zu einer Polylinie (Segmente a->b), in Metern."""
    dx, dy = bx - ax, by - ay
    len2 = dx * dx + dy * dy
    len2 = np.where(len2 == 0, 1e-12, len2)
    out = np.empty(len(px))
    chunk = max(1, 2_000_000 // max(1, len(ax)))  # Speicher begrenzen
    for s in range(0, len(px), chunk):
        X = px[s:s + chunk, None]
        Y = py[s:s + chunk, None]
        t = np.clip(((X - ax) * dx + (Y - ay) * dy) / len2, 0.0, 1.0)
        qx, qy = ax + t * dx, ay + t * dy
        out[s:s + chunk] = np.sqrt((X - qx) ** 2 + (Y - qy) ** 2).min(axis=1)
    return out


def _points_in_polygon(px, py, vx, vy) -> np.ndarray:
    """Strahlverfahren (ray casting): liegt der Punkt innerhalb der geschlossenen Flaeche?"""
    x1, y1, x2, y2 = vx[:-1], vy[:-1], vx[1:], vy[1:]
    denom = np.where(y2 == y1, 1e-12, y2 - y1)
    out = np.empty(len(px), dtype=bool)
    chunk = max(1, 2_000_000 // max(1, len(x1)))
    for s in range(0, len(px), chunk):
        X = px[s:s + chunk, None]
        Y = py[s:s + chunk, None]
        crosses = ((y1 > Y) != (y2 > Y)) & (X < x1 + (Y - y1) * (x2 - x1) / denom)
        out[s:s + chunk] = (crosses.sum(axis=1) % 2) == 1
    return out


SQLITE_HEADER = b"SQLite format 3\x00"


def ensure_usable_db(db_path: str) -> None:
    """
    Prueft VOR dem Herunterladen/Rastern, ob die Ziel-Datenbank benutzbar ist.

    Grund: Ist die Datei beschaedigt, scheiterte der Lauf frueher erst ganz am
    Ende beim Schreiben - nach mehreren Minuten Rasterung, die damit umsonst
    war. Eine beschaedigte Datei wird hier nicht geloescht, sondern mit einem
    Zeitstempel zur Seite gelegt; die neue Datenbank wird frisch angelegt.
    """
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return
    try:
        with open(db_path, "rb") as f:
            header_ok = f.read(16) == SQLITE_HEADER
        if header_ok:
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA quick_check").fetchone()
            conn.close()
            return
    except Exception:
        header_ok = False

    backup = f"{db_path}.beschaedigt-{time.strftime('%Y%m%d-%H%M%S')}"
    os.rename(db_path, backup)
    print(f"[Hinweis] Die vorhandene Datei {os.path.basename(db_path)} ist keine gueltige "
          f"SQLite-Datenbank (beschaedigt).")
    print(f"          Sie wurde umbenannt in: {os.path.basename(backup)}")
    print(f"          Es wird eine neue Datenbank angelegt - die heruntergeladenen "
          f"Kacheln bleiben erhalten, es wird nichts neu geladen.\n")


def element_flags(el: dict) -> set:
    """
    Merkmale eines OSM-Elements als Flag-Menge.

    Speichert BEIDES: den reinen Wert ("residential") fuer Rueckwaerts-
    kompatibilitaet mit aelteren Caches, UND den tag-genauen Schluessel
    ("highway=residential" bzw. "landuse=residential"). Nur mit dem
    tag-genauen Schluessel laesst sich eine Wohnstrasse von einem
    Wohngebiet unterscheiden - ohne diese Trennung galten in der
    laendlichen Kameraregion 51 % aller Rasterzellen faelschlich als
    Siedlung, weil dort eine kleine Strasse verlaeuft.
    """
    tags = el.get("tags", {}) or {}
    flags = set()
    known = {t for tag_list in DEFAULT_QUERY_ELEMENTS.values() for t in tag_list}
    for tag, value in tags.items():
        if tag in known:
            flags.add(tag)
            flags.add(value)
            flags.add(f"{tag}={value}")
    return flags


def rasterize(elements: list[dict], bbox, grid_size_deg: float = GRID_SIZE_DEG,
              radius_m: int = DEFAULT_RADIUS_M) -> tuple[dict, tuple[int, int, int, int]]:
    """
    Fuer jeden Rasterpunkt (gleiches Raster wie TerrainCache._grid_key) werden
    die Gelaendemerkmale im Umkreis radius_m bestimmt - im selben Format
    (0/1-Flags) wie bei der bisherigen Live-Abfrage, damit die Bewertung in
    japan_comparison.TERRAIN_PREFERENCE unveraendert bleibt.
    """
    g = grid_size_deg
    s, w, n, e = bbox
    i_min, i_max = math.floor(s / g), math.ceil(n / g)
    j_min, j_max = math.floor(w / g), math.ceil(e / g)

    lat0, lon0 = (s + n) / 2, (w + e) / 2
    m_lon = M_PER_DEG_LAT * math.cos(math.radians(lat0))
    r_lat, r_lon = radius_m / M_PER_DEG_LAT, radius_m / m_lon

    cell_flags: dict[tuple[int, int], set] = {}
    n_used = 0

    for idx, el in enumerate(elements, 1):
        flags = element_flags(el)
        if not flags:
            continue

        if el.get("type") == "node" and "lat" in el:
            lats, lons = np.array([el["lat"]]), np.array([el["lon"]])
            closed = False
        elif el.get("type") == "way" and el.get("geometry"):
            geom = [p for p in el["geometry"] if p]
            lats = np.array([p["lat"] for p in geom])
            lons = np.array([p["lon"] for p in geom])
            closed = len(geom) >= 4 and lats[0] == lats[-1] and lons[0] == lons[-1]
        else:
            continue

        ci0 = max(i_min, math.floor((lats.min() - r_lat) / g))
        ci1 = min(i_max, math.ceil((lats.max() + r_lat) / g))
        cj0 = max(j_min, math.floor((lons.min() - r_lon) / g))
        cj1 = min(j_max, math.ceil((lons.max() + r_lon) / g))
        if ci0 > ci1 or cj0 > cj1:
            continue

        ii, jj = np.meshgrid(np.arange(ci0, ci1 + 1), np.arange(cj0, cj1 + 1), indexing="ij")
        ii, jj = ii.ravel(), jj.ravel()
        py = (ii * g - lat0) * M_PER_DEG_LAT
        px = (jj * g - lon0) * m_lon
        vy = (lats - lat0) * M_PER_DEG_LAT
        vx = (lons - lon0) * m_lon

        if len(vx) == 1:
            hit = np.hypot(px - vx[0], py - vy[0]) <= radius_m
        else:
            hit = _min_dist_to_segments(px, py, vx[:-1], vy[:-1], vx[1:], vy[1:]) <= radius_m
        if closed:
            hit |= _points_in_polygon(px, py, vx, vy)

        for k in np.nonzero(hit)[0]:
            cell_flags.setdefault((int(ii[k]), int(jj[k])), set()).update(flags)
        n_used += 1

        if idx % 2000 == 0:
            print(f"  ... {idx}/{len(elements)} Elemente verarbeitet")

    print(f"  {n_used} Gelaende-Elemente in {len(cell_flags)} Rasterzellen eingetragen")
    return cell_flags, (i_min, i_max, j_min, j_max)


# =========================================================
# 4) In die bestehende Cache-Datenbank schreiben
# =========================================================
def write_cache(cell_flags: dict, index_range, grid_size_deg: float, radius_m: int,
                db_path: str = DEFAULT_CACHE_DB) -> None:
    """
    Schreibt die Rasterzellen in die Cache-Datenbank - ATOMAR.

    Warum atomar: Die Cache-Datei ist schon zweimal unbrauchbar geworden.
    Geschrieben wird deshalb zuerst in eine Kopie neben der Zieldatei; erst
    wenn diese Kopie ein "PRAGMA quick_check" besteht, ersetzt os.replace()
    das Original in einem einzigen Schritt. Bricht der Vorgang vorher ab
    (Absturz, Virenscanner, Strom weg), bleibt die alte, funktionierende
    Datei unangetastet - man verliert hoechstens den neuen Lauf.

    Eine bereits defekte Zieldatei wird von ensure_usable_db() abgefangen,
    das main() vor dem Rastern aufruft - hier muss sie nicht noch einmal
    geprueft werden.
    """
    tmp_path = f"{db_path}.tmp-{os.getpid()}"
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    # Bestehende Eintraege uebernehmen, damit ein Teil-Lauf den Cache nicht leert
    if os.path.exists(db_path):
        shutil.copy2(db_path, tmp_path)

    try:
        _write_cache_into(cell_flags, index_range, grid_size_deg, radius_m, tmp_path)

        # Erst pruefen, dann ersetzen
        check = sqlite3.connect(tmp_path)
        ok = check.execute("PRAGMA quick_check").fetchone()[0]
        check.close()
        if ok != "ok":
            raise sqlite3.DatabaseError(f"Neu geschriebene Datei fehlerhaft: {ok}")

        os.replace(tmp_path, db_path)   # atomar, auch unter Windows
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _write_cache_into(cell_flags: dict, index_range, grid_size_deg: float, radius_m: int,
                      db_path: str) -> None:
    """Eigentliches Schreiben - immer in die temporaere Datei, siehe write_cache()."""
    TerrainCache(db_path=db_path, grid_size_deg=grid_size_deg)  # legt Tabellen an, falls noetig
    g = grid_size_deg
    now = time.time()
    # Schluessel exakt wie TerrainCache._grid_key: round(x/g)*g == int*g
    rows = [
        (int(i) * g, int(j) * g, radius_m, json.dumps({k: 1 for k in sorted(flags)}), now)
        for (i, j), flags in cell_flags.items()
    ]
    i_min, i_max, j_min, j_max = index_range
    conn = sqlite3.connect(db_path)
    conn.executemany(
        "INSERT OR REPLACE INTO terrain_cache (lat_key, lon_key, radius, features_json, cached_at) "
        "VALUES (?, ?, ?, ?, ?)", rows,
    )
    # Bei erneutem Lauf denselben Bereich nicht doppelt eintragen
    conn.execute(
        "DELETE FROM prefetch_regions WHERE min_lat_key=? AND min_lon_key=? AND max_lat_key=? "
        "AND max_lon_key=? AND radius=?",
        (i_min * g, j_min * g, i_max * g, j_max * g, radius_m),
    )
    conn.execute(
        "INSERT INTO prefetch_regions (min_lat_key, min_lon_key, max_lat_key, max_lon_key, radius, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (i_min * g, j_min * g, i_max * g, j_max * g, radius_m, now),
    )
    conn.commit()
    conn.close()
    n_cells = (i_max - i_min + 1) * (j_max - j_min + 1)
    print(f"  {len(rows)} Zellen mit Gelaendemerkmalen gespeichert "
          f"(Gebiet insgesamt {n_cells} Zellen, Rest = nachweislich ohne Merkmale)")


# =========================================================
# 5) Ablauf
# =========================================================
def main():
    ap = argparse.ArgumentParser(description="Gelaendedaten fuer die Japan-Simulation einmalig vorab laden.")
    ap.add_argument("--buffer-km", type=float, default=DEFAULT_BUFFER_KM)
    ap.add_argument("--tile-deg", type=float, default=DEFAULT_TILE_DEG)
    ap.add_argument("--radius", type=int, default=DEFAULT_RADIUS_M)
    ap.add_argument("--bbox", type=float, nargs=4, metavar=("SUED", "WEST", "NORD", "OST"),
                    help="Gebiet manuell angeben statt aus den Kamerastandorten")
    ap.add_argument("--print-query", action="store_true",
                    help="Nur die Abfrage fuer overpass-turbo.eu ausgeben")
    ap.add_argument("--from-file", nargs="+",
                    help="Vorher im Browser gespeicherte Overpass-JSON-Datei(en) verwenden")
    ap.add_argument("--db", default=DEFAULT_CACHE_DB)
    args = ap.parse_args()

    bbox = tuple(args.bbox) if args.bbox else camera_bbox(args.buffer_km)
    # etwas groesser laden als gerastert, damit Merkmale knapp ausserhalb
    # des Randes fuer die Randzellen trotzdem beruecksichtigt werden
    pad = args.radius / M_PER_DEG_LAT * 1.5
    load_bbox = (bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad)

    print(f"Gebiet: Sued {bbox[0]:.4f}, West {bbox[1]:.4f}, Nord {bbox[2]:.4f}, Ost {bbox[3]:.4f}")

    ensure_usable_db(args.db)  # frueh pruefen, damit keine Rechenzeit verloren geht

    if args.print_query:
        print("\nDiese Abfrage auf https://overpass-turbo.eu einfuegen, ausfuehren und "
              "ueber 'Export' -> 'Rohdaten' als JSON speichern:\n")
        print(build_query(load_bbox, timeout_s=300))
        return

    t0 = time.time()
    if args.from_file:
        paths = args.from_file
        print(f"\n[1/3] Verwende {len(paths)} lokale Datei(en)")
    else:
        print(f"\n[1/3] Lade Gelaendedaten (Kacheln a {args.tile_deg} Grad) ...")
        paths, failed = download_tiles(load_bbox, args.tile_deg)
        if failed:
            print(f"\n{len(failed)} Kachel(n) konnten nicht geladen werden. Einfach erneut starten "
                  f"(bereits geladene werden uebersprungen) oder den Browser-Weg nutzen "
                  f"(--print-query / --from-file). Es wird NICHTS gespeichert, damit keine "
                  f"Luecken als 'kein Gelaende' fehlinterpretiert werden.")
            sys.exit(1)

    elements = load_elements(paths)
    print(f"\n[2/3] Rastere {len(elements)} Elemente (Rasterweite ~150 m, Radius {args.radius} m) ...")
    cell_flags, idx_range = rasterize(elements, bbox, radius_m=args.radius)

    print(f"\n[3/3] Schreibe in {args.db} ...")
    write_cache(cell_flags, idx_range, GRID_SIZE_DEG, args.radius, db_path=args.db)

    print(f"\nFertig in {time.time() - t0:.0f} s. Die Simulation nutzt ab jetzt fuer dieses "
          f"Gebiet ausschliesslich lokale Daten - keine Internet-Anfragen mehr.")


if __name__ == "__main__":
    main()