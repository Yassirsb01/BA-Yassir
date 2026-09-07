"""
check_japan_data.py
=====================
Prueft, wie viele Kamerabilder MIT Zeitstempel tatsaechlich vorliegen -
und zwar in BEIDEN Bildtabellen:

  - image_metadata        (aeltere Tabelle, nur Dateisystem-Indexierung)
  - bears_images_unified  (vereinheitlichte Tabelle: Dateisystem + E-Mail,
                           angelegt mit create_unified_table.py und befuellt
                           mit migrate_to_unified_table.py)

Hintergrund: Fuer den Vergleich der Ausloesezeiten (echte Bilder vs.
simulierter Baer) brauchen wir genug Zeitstempel, um eine Tagesrhythmus-
Verteilung zu schaetzen. Ein erster Lauf gegen image_metadata fand nur 36
Zeitstempel - moeglicherweise liegen in der unified-Tabelle deutlich mehr.

Braucht die OTH-VPN-Verbindung.
Aufruf:  python check_japan_data.py
"""

import sys
from collections import Counter
from datetime import datetime

from wildlife_db_mariadb import WildlifeDatabase

MIN_FOR_DISTRIBUTION = 20  # Faustregel: ab hier wird eine Tagesrhythmus-Schaetzung sinnvoll


def table_exists(db, name: str) -> bool:
    try:
        return bool(db.execute_query(f"SHOW TABLES LIKE '{name}'"))
    except Exception:
        return False


def analyse_table(db, table: str, device_col: str = "device_id"):
    print("\n" + "=" * 68)
    print(f"Tabelle: {table}")
    print("=" * 68)

    if not table_exists(db, table):
        print("  -> existiert nicht in dieser Datenbank.")
        return None

    rows = db.execute_query(f"""
        SELECT {device_col} AS device_id,
               COUNT(*) AS gesamt,
               SUM(CASE WHEN timestamp IS NOT NULL THEN 1 ELSE 0 END) AS mit_zeit
        FROM {table}
        GROUP BY {device_col}
        ORDER BY mit_zeit DESC
    """)

    if not rows:
        print("  -> Tabelle ist leer.")
        return None

    print(f"\n{'Geraet':<14}{'Bilder ges.':>13}{'davon m. Zeit':>15}")
    print("-" * 68)
    total_all = total_time = 0
    for r in rows:
        gesamt = int(r.get("gesamt") or 0)
        mit_zeit = int(r.get("mit_zeit") or 0)
        total_all += gesamt
        total_time += mit_zeit
        print(f"{str(r.get('device_id')):<14}{gesamt:>13}{mit_zeit:>15}")
    print("-" * 68)
    print(f"{'SUMME':<14}{total_all:>13}{total_time:>15}")

    usable = [r for r in rows if int(r.get("mit_zeit") or 0) >= MIN_FOR_DISTRIBUTION]
    print(f"\nKameras mit >= {MIN_FOR_DISTRIBUTION} Zeitstempeln: {len(usable)} von {len(rows)}")

    # Nach Quelle aufschluesseln (nur unified-Tabelle hat diese Spalte):
    # zeigt, ob die E-Mail-Anbindung zusaetzliche Bilder beigesteuert hat.
    try:
        by_source = db.execute_query(f"""
            SELECT source, COUNT(*) AS n,
                   SUM(CASE WHEN timestamp IS NOT NULL THEN 1 ELSE 0 END) AS mit_zeit
            FROM {table} GROUP BY source
        """)
        if by_source:
            print("\nNach Quelle:")
            for r in by_source:
                print(f"  {str(r.get('source')):<14}{int(r.get('n') or 0):>7} Bilder, "
                      f"{int(r.get('mit_zeit') or 0):>5} mit Zeitstempel")
    except Exception:
        pass  # Spalte 'source' gibt es nur in bears_images_unified

    return _hour_histogram(db, table)


def _hour_histogram(db, table: str):
    imgs = db.execute_query(f"SELECT timestamp FROM {table} WHERE timestamp IS NOT NULL")
    hours = Counter()
    for row in imgs or []:
        ts = row.get("timestamp")
        if not ts:
            continue
        try:
            dt = ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts))
            hours[dt.hour] += 1
        except (ValueError, TypeError):
            continue

    if not hours:
        print("\nKeine auswertbaren Zeitstempel.")
        return None

    n = sum(hours.values())
    print(f"\nVerteilung ueber die Tagesstunden (n={n}):")
    peak = max(hours.values())
    for h in range(24):
        c = hours.get(h, 0)
        bar = "#" * int(round(c / peak * 45)) if peak else ""
        print(f"  {h:02d}:00  {c:>6}  {bar}")

    night = sum(c for h, c in hours.items() if h >= 18 or h <= 5)
    print(f"\n  Nachts (18-05 Uhr): {night} von {n}  ({night/n*100:.0f} %)")
    return hours


def main():
    db = WildlifeDatabase()
    try:
        conn = db._get_connection()
        conn.close()
    except Exception as e:
        print("FEHLER: Keine Verbindung zur Datenbank.")
        print(f"  Details: {e}")
        print("\n  -> Ist die OTH-VPN-Verbindung aktiv?")
        sys.exit(1)

    analyse_table(db, "image_metadata")
    analyse_table(db, "bears_images_unified")

    print("\n" + "=" * 68)
    print("Hinweis: Massgeblich ist die Tabelle mit den MEISTEN Zeitstempeln.")
    print("=" * 68)


if __name__ == "__main__":
    main()