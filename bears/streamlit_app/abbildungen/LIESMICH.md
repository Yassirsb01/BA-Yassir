# Abbildungen zur Geländegewichtung

Sieben Bilder, die erklären, was an der Richtungswahl geändert wurde und was
dabei herauskam. Gedacht zum Zeigen und Besprechen, nicht als Bericht.

Die Abbildungen 1 bis 5 sind **Schemata** — vereinfachte Zeichnungen, die das
Prinzip zeigen. Die Abbildungen 6 und 7 stammen aus den **echten Daten** des
Projekts: echte Kamerastandorte, echter Rasterspeicher, echte simulierte Pfade.

---

## 01 — Richtungslücken

**Zeigt:** links die alte Richtungswahl (acht feste Richtungen, ±15° Streuung),
rechts die neue (±22,5°). Die roten Keile links sind Richtungen, die der Bär
grundsätzlich nicht laufen konnte.

**Der Satz dazu:** „Die Sektoren lagen 45 Grad auseinander, die Streuung deckte
aber nur 30 Grad ab. Ein Drittel aller Richtungen war dadurch unerreichbar —
an 3 840 Entscheidungen nachgemessen lag in diesen Bändern keine einzige."

**Wichtig:** Das ist das *kleinere* der beiden Probleme und mit einer Zahl
behoben (±15 → ±22,5). Nicht als Hauptleistung verkaufen.

---

## 02 — Analogie Sensormatte → Geländeraster

**Zeigt:** links das Problem aus dem Paper (wo steht der Fuß auf der Matte),
rechts dieselbe Rechnung auf dem Geländeraster. Unten die Zuordnungstabelle.

**Der Satz dazu:** „Die Geländezellen entsprechen Ihren Dreiecksfeldern, die
Geländebewertung dem Kapazitätswert, und ein zusammenhängendes Waldstück
entspricht einem Fuß. Dieselbe Formel liefert statt einer Rasterrichtung einen
stufenlosen Zielpunkt."

**Das wichtigste Bild.** Wenn nur eines gezeigt wird, dann dieses.

---

## 03 — Warum erst getrennt werden muss

**Zeigt:** in drei Schritten, warum der Trennschritt nötig ist — ohne ihn landet
der gemittelte Zielpunkt im Dorf zwischen den beiden Waldstücken.

**Der Satz dazu:** „Das ist Ihr Argument mit den zwei Füßen: ohne Trennung liegt
der Mittelwert zwischen ihnen, also dort, wo gar kein Fuß ist."

**Vorsicht:** Dieses Bild zeigt den *Idealfall*. Wie selten der Fall in unserem
Gebiet wirklich eintritt, zeigt erst Abbildung 6. Die beiden Bilder gehören
zusammen und sollten nacheinander gezeigt werden.

---

## 04 — Die vier Schritte

**Zeigt:** was bei jedem Schritt des Bären passiert — einsammeln, Schwelle
anlegen, trennen, Formel (1) anwenden.

**Der Satz dazu:** „Pro Schritt werden die Zellen im Suchbereich geholt, alles
unter der Schwelle 1,0 fällt weg, der Rest wird über die Nachbarschaft zu
Gebieten gruppiert, und je Gebiet entsteht ein gewichteter Mittelpunkt."

**Detail, falls gefragt:** Der Suchbereich ist bewusst als **Rechteck**
gezeichnet, nicht als Kreis — der Code fragt einen rechteckigen Ausschnitt ab
(`_terrain_clusters` → `get_cells_in_box`). Ecken liegen also etwas weiter weg
als 350 m.

---

## 05 — Wie ein einzelner Schritt zustande kommt

**Zeigt:** die acht freien Richtungen, die zusätzlichen Richtungen zu
Waldstücken, und woraus sich die Punktzahl eines Kandidaten zusammensetzt.

**Der Satz dazu:** „Die Clusterrichtungen ersetzen die freien Kandidaten nicht,
sie kommen dazu. Sonst könnte der Bär nur noch Wald ansteuern und würde ein
Waldstück nie wieder verlassen."

**Wichtig:** Der Kasten unten rechts. Es wird **gezogen**, nicht das Maximum
genommen — sonst wäre es kein Zufallsmodell mehr.

---

## 06 — Echte Kameras, echte Gebiete

**Echte Daten.** Links Kamera 002007, wo tatsächlich zwei getrennte Waldstücke
gefunden werden. Rechts Kamera 001000, wo gar nichts in Reichweite liegt.

**Der Satz dazu:** „Der Trennschritt — also genau der Beitrag, den Ihr Paper als
entscheidend beschreibt — greift bei uns nur bei 3,4 Prozent der Positionen. An
9 von 20 Kameras findet der Bär gar kein Gebiet, an 9 genau eines. Das ist kein
Umsetzungsfehler, sondern eine Eigenschaft der Landschaft."

**Dieses Bild selbst ansprechen, nicht abwarten.** Ein ehrliches Negativergebnis
wirkt deutlich besser, wenn es von einem selbst kommt. Rückendeckung gibt es
aus Abschnitt 4.3 seines neuen Papers, wo er dasselbe für seine eigene
kombinierte Methode berichtet.

---

## 07 — Ein Beispiellauf

**Echte Daten.** Derselbe Startpunkt, dieselben Zufallszahlen, 24 Stunden, einmal
mit der alten und einmal mit der neuen Richtungswahl.

**Der Satz dazu:** „Nur die Richtungswahl unterscheidet sich. Die Tagesstrecke
ist in beiden Läufen identisch, weil sie allein aus der Geschwindigkeitstabelle
folgt."

**Unbedingt dazusagen:** Das ist **ein einzelner, bewusst ausgewählter Lauf**
(20 % gegenüber 48 % Wald). Die belastbaren Zahlen sind die Mittelwerte über
160 Läufe: **34,5 % gegenüber 39,1 %**. Das steht auch im Bild, sollte aber
mündlich wiederholt werden — sonst entsteht der Eindruck, der Effekt sei
dreimal so groß wie er ist.

---

## Wenn nach den Zahlen gefragt wird

Alle Werte stammen aus `tests/direction_distribution_test.py`. Der Test läuft
ohne Netzwerk und ohne Datenbank, dauert knapp zwei Minuten und gibt die
Tabelle direkt aus:

```
python tests/direction_distribution_test.py
```

Die ausführliche Begründung jeder Entscheidung steht in `ANPASSUNGEN.md`,
Abschnitt 8.

---

## Abbildungen neu erzeugen

```
python abbildungen/_erzeugung_schemata.py       # 01 bis 05
python abbildungen/_erzeugung_echtdaten.py      # 06 und 07
```

Beide Skripte schreiben in das Verzeichnis, das in der Umgebungsvariablen
`FIGDIR` steht; ohne sie landen die Bilder in `abbildungen/`.

Die Skripte für 06 und 07 blockieren jeden Netzwerkzugriff und lesen
ausschließlich aus `bear_simulation/data/terrain_cache.db`. Sie müssen aus dem
Projektverzeichnis heraus gestartet werden.
