# Abbildungen für den Bericht

Acht Abbildungen als Vektor-PDF, Einbindung auf etwa 14 cm Breite
(`\includegraphics[width=14cm]{...}`). Beschriftungen auf Deutsch,
einheitliche Schriftart und Farbpalette, Information jeweils zusätzlich
über Schraffur, Linienart oder Form codiert, damit sie auch im
Schwarzweißdruck lesbar bleibt. Keine Überschrift im Bild — die
Bildunterschrift kommt aus LaTeX.

---

## Teil A — aus dem Repository

### `abb_a1_ausgangszustand.pdf`
**Abschnitt:** Ausgangszustand des Systems

Die drei Vorarbeiten nebeneinander, je mit Oberfläche, Kartenansicht und
Datenhaltung, durch gestrichelte Linien als getrennte Anwendungen
ausgewiesen.

**Quellen im Repository:**
- `docs/bearsimulation-master.zip` → `OverviewMap.py` (importiert `dash`,
  `folium`), `Visualization.py` (`dash`, `plotly`),
  `data/DatabaseConnection.py` (`sqlite3`), `data/database.db`,
  `Carpathian/1_bears_RO.csv`
- `docs/wildlife_pictures_extraction.zip` → `MicrosoftGraphApi.py`,
  `DBManager.py` (`mysql.connector`, Tabellen `wildlife_images` und
  `deterrent_devices`)
- `docs/lorenzBachelorarbeit.pdf`, Zusammenfassung: Streamlit, Folium,
  MariaDB, Pandas
- Tabellennamen gegen die laufende MariaDB geprüft (`SHOW TABLES`)

### `abb_a2_zielarchitektur.pdf`
**Abschnitt:** Kartenkomponente und Interaktionskonzept

Der heutige Aufbau in vier Schichten: Oberfläche, Kartendarstellung,
Fachlogik, Datenhaltung. Schraffiert ist, was unverändert aus der
Vorarbeit stammt; alles Übrige ist neu oder ersetzt. Gegenstück zu A1,
gleicher Stil.

**Quellen im Repository:**
- Seiten: `map.py`, `pages/2_Experiments.py`, `pages/3_Japan_Experiment.py`
- Kartenkomponenten (alle über `components.html` eingebettet):
  `maplibre_component.py`, `animation_component.py`,
  `japan_map_component.py`, `japan_deterrents.py`, `carpathian_bears.py`
- Fachlogik: `carpathian_bears.py`, `japan_comparison.py`,
  `sync_simulation.py`, `activity_overlap.py`, `terrain_cache.py`,
  `bear_simulation/` (Vorarbeit Bräu)
- Datenhaltung: `wildlife_db_mariadb.py`;
  `japan_comparison.SIM_DB_PATH` → `bear_simulation/data/database.db`;
  `terrain_cache.DEFAULT_CACHE_DB` → `bear_simulation/data/terrain_cache.db`;
  `import_bfn_wolf_lynx.py`, `import_gbif_bears.py`
- Tabellennamen aus `SHOW TABLES` der laufenden MariaDB

### `abb_a3_gps_verteilung.pdf`
**Abschnitt:** GPS-Trajektorien der Karpaten-Studie

Balken je Tier, nach Anzahl der Ortungen sortiert; Geschlecht über
Schraffur unterschieden. Zeigt Umfang und die deutliche Ungleichverteilung
(stärkstes Tier 20,5 %, schwächstes 1,7 %).

**Quelle im Repository:**
`data/animal_data/carpathian_bears/1_bears_RO.csv`, Werte selbst
ausgezählt (59 997 Ortungen, 13 Tiere, 9. August 2011 bis 31. Juli 2015).
Die Kennzahlen liegen als `_gps_kennzahlen.json` daneben.

> **Hinweis zur Datenquelle.** Die Anwendung liest primär die Tabelle
> `bears_tracking` der MariaDB und fällt nur ersatzweise auf die CSV
> zurück. Die Tabelle enthält **116 014 Zeilen, aber nur 59 997
> eindeutige Ortungen** (geprüft über `COUNT(DISTINCT bear_id, timestamp,
> lat, lng)`): jede Position liegt dort überwiegend doppelt vor. Die
> Abbildung nennt bewusst die entduplizierte Zahl. Die Dublettenbildung
> ist ein eigener Befund und gehört in das Kapitel zu den Problemen.

### `abb_a4_richtungswahl.pdf`
**Abschnitt:** Clusterbasierte Richtungswahl

Zwei Kreise nebeneinander: links das frühere 45°-Raster mit ±15° Streuung
und den dadurch gesperrten Bändern, rechts die heutige Fassung mit ±22,5°
und zusätzlichen Richtungen zu attraktiven Geländeflächen.

**Quellen im Repository:**
- heutiges Verfahren: `japan_comparison.choose_weighted_direction()`,
  Erzeugung der freien Kandidaten (`sector = 360 / n_free`, Streuung
  `±sector/2`), sowie `_terrain_clusters()` für die Flächenrichtungen
- frühere Fassung: `legacy_heading_selection()` in
  `tests/direction_distribution_test.py`, wortgleiche Kopie des Standes
  vor der Umstellung (`rng.uniform(-15, 15)`)

### `abb_a5_delta_ergebnis.pdf`
**Abschnitt:** Wissenschaftliche Einordnung des Delta-Ergebnisses

Der Überlappungskoeffizient auf einer Skala von 0 bis 1, mit dem
95-%-Bootstrap-Intervall als schraffiertem Band und der Datengrundlage
als Textblock.

**Quelle im Repository:**
`activity_overlap.py`; berichtetes Ergebnis aus `ANPASSUNGEN.md`,
Abschnitt 9 (Lauf vom 2. Oktober 2026): Δ = 0,615, Intervall
[0,528; 0,683], 50 reale Auslösungen gegenüber 1 958 virtuellen
Detektionen aus 300 Läufen à 48 h, Erfassungsradius 150 m, ohne
Geländegewichtung.

> **Nicht neu gerechnet.** Ein aktuelles Ergebnis lag dokumentiert vor,
> deshalb wurde der Lauf nicht wiederholt. Eine Wiederholung dauert rund
> 98 Sekunden und setzt eine erreichbare Datenbank voraus
> (`python activity_overlap.py`).
>
> **Kein Wert mit Geländegewichtung.** Der Lauf mit `use_terrain=True`
> ist derzeit nicht belastbar, weil die Geländegewichtung mitten im Lauf
> abgeschaltet wird, sobald die simulierten Bären das vorberechnete
> Gebiet verlassen (siehe `ANPASSUNGEN.md`, Abschnitt 9). Die Abbildung
> weist deshalb ausdrücklich „ohne Geländegewichtung" aus.

---

## Teil B — allgemeine Konzepte

Ohne Projektbezug, nach Lehrbuch gezeichnet.

### `abb_b1_vektor_raster.pdf`
**Abschnitt:** Vektor- und Rasterdaten

Dieselbe Szene zweimal: links als Punkt, Linie und Fläche mit
Stützpunkten, rechts als regelmäßiges Zellgitter. Macht den Unterschied
ohne Fließtext sichtbar.

### `abb_b2_kachelprinzip.pdf`
**Abschnitt:** Kacheln und Höhenmodelle

Links das Verhältnis der Zoomstufen zueinander (je Stufe vervierfacht
sich die Kachelzahl), rechts die Adressierung einer Kachel als z/x/y und
der sichtbare Ausschnitt, der nur die berührten Kacheln lädt.

### `abb_b3_quelle_ebene.pdf`
**Abschnitt:** MapLibre GL JS und Begründung der Technologiewahl

Eine Datenquelle versorgt mehrere Ebenen; die Darstellung wird über
Paint- und Layout-Eigenschaften im Style-Dokument festgelegt.

### `abb_a6_bildweg.pdf`
**Abschnitt:** Anbindung der Bildextraktion / Vereinheitlichung der Datenhaltung

Der Weg einer Aufnahme von der Kamera bis in die Karte, oben der
Ausgangszustand mit zwei getrennten Tabellen, unten der jetzige mit einer
gemeinsamen. Der gestrichelte Rahmen kennzeichnet die Bildextraktion als
eigenen Prozess.

**Quelle im Repository:** Tabellennamen, Spalten und Schlüssel aus
`SHOW CREATE TABLE` (`image_metadata`, `wildlife_images`,
`bears_images_unified`, `app_status`); Zeilenzahl 51 und die Aufteilung
14 E-Mail / 37 Dateisystem aus `SELECT source, image_type, COUNT(*) ...`;
Abfrageintervall 10 s aus `email_extractor/WildlifePictureExtractor.py`;
Zwischenspeicher 30 s aus `streamlit_app/new_images_checker.py`.

---

## Neu erzeugen

```
python bericht_abbildungen/_erzeugung_teil_a.py     # A1 bis A5
python bericht_abbildungen/_erzeugung_teil_b.py     # B1 bis B3
python bericht_abbildungen/_erzeugung_bildweg.py    # A6
```

Alle Skripte schreiben in das Verzeichnis aus der Umgebungsvariablen
`ABBDIR`, ersatzweise nach `bericht_abbildungen`. Mit gesetzter Variablen
`VORSCHAU=1` entsteht zusätzlich je eine PNG-Vorschau zum schnellen
Draufschauen. Teil A erwartet die Kennzahlen aus `GPSJSON`
(standardmäßig `_gps_kennzahlen.json`).
