# Anpassungen an Fabian Bräus Bewegungssimulation

Dokumentiert alle Abweichungen vom Originalcode aus `bear_simulation/`
(Bachelorarbeit Fabian Bräu). Grundlage: Prof. Dünnweber hat im Meeting am
21.08.2026 ausdrücklich erlaubt, Fabians Code anzupassen statt ihn 1:1 zu
übernehmen — Ziel ist die Umsetzung seiner Anforderungen, nicht die
originalgetreue Wiederverwendung.

**Fabians Originaldateien sind unverändert.** Angefasst wurden nur eigene
Dateien: `sync_simulation.py`, `japan_comparison.py` und
`bear_simulation/__init__.py`. Letztere liegt zwar in seinem Ordner, ist
aber die selbst geschriebene Integrationsschicht zu `map.py` (sie
importiert Streamlit) und nicht Teil seiner Arbeit. Alle drei
implementieren seine Logik neu bzw. erweitern sie.

---

## 1. `StepSelectionModel` wird nicht importiert, sondern nachgebaut

**Wo:** `sync_simulation._generate_alternative_steps()`

**Original:** `model/StepSelectionModel.py`, Methode `generate_alternative_steps()`

**Grund:** Der Konstruktor `StepSelectionModel.__init__()` zieht über
`StepTrajectorySet` → `SeasonalTrajectoryProcessor` → `ClusterCalculator` →
`Hdbscan` eine vollständige Cluster-Analyse-Kette mit und benötigt dafür das
Paket `hdbscan`. Für die reine Schritt-Generierung werden davon nur
`BearSpeeds` und `GeoToolBox` gebraucht. Die fehlende `hdbscan`-Abhängigkeit
ist vermutlich auch der Grund, warum die Simulation vorher im Fallback-Modus
lief.

**Auswirkung auf die Ergebnisse:** keine — die Schritt-Erzeugung ist Zeile für
Zeile identisch.

---

## 2. Schrittlänge wird an das tatsächliche GPS-Intervall angepasst

**Wo:** `sync_simulation._generate_alternative_steps(scale_to_interval=True)`

**Original:** `step_length_m = median_speed_kmh * 1000`

**Problem:** `median_speed_kmh * 1000` ist die Strecke **einer Stunde**. Die
Carpathian-GPS-Fixes liegen aber nicht durchgängig eine Stunde auseinander
(gemessen an `data/animal_data/carpathian_bears/1_bears_RO.csv`, 13 Bären,
59 997 Punkte):

| Intervall | Anteil |
|---|---|
| ~1 h | 79,7 % |
| ~2 h | 12,9 % |
| > 2,1 h | 6,9 % |

Bei einer Zweistundenlücke waren die Alternativen damit nur halb so lang wie
der echte Schritt. Der Fächer war dort systematisch zu klein, und eine daraus
gebaute Trajektorie blieb zwangsläufig hinter dem echten Bären zurück.

**Neu:** Die Schrittlänge wird mit der tatsächlich verstrichenen Zeit
skaliert. `scale_to_interval=False` stellt das Originalverhalten wieder her.

**Auswirkung:** Der Fächer ist bei Schritten > 1 h größer als vorher. Das ist
eine Korrektur, keine Verhaltensänderung im Modell.

---

## 3. Reproduzierbarer Zufall

**Wo:** `sync_simulation._generate_alternative_steps(rng=...)`,
`build_synced_geojson(seed=...)`

**Original:** globales `random`-Modul, also bei jedem Aufruf ein anderes
Ergebnis.

**Grund:** Ohne festen Seed lässt sich eine Abbildung in der Bachelorarbeit
nicht reproduzieren. `seed=None` erhält das alte Verhalten.

**Auswirkung:** keine inhaltliche — nur Reproduzierbarkeit.

---

## 4. NEU: Durchgehende simulierte Trajektorien ("Realisierungen")

**Wo:** `sync_simulation._build_simulated_realizations()`

**Im Original nicht vorhanden.** Fabians Modell erzeugt pro echtem Schritt
eine Menge von Kandidaten — das ist der Möglichkeitsraum *eines* Schritts,
aber kein Pfad. Die Protokoll-Anforderung ("Bewegungen echter **und**
simulierter Bären") braucht einen zweiten Bären, der mitläuft.

**Vorgehen:** Der simulierte Bär startet auf dem echten Startpunkt. Für jeden
echten Schritt wird aus den Kandidaten dieses Schritts einer gezogen; dessen
Richtung und Länge werden auf die **aktuelle simulierte** Position angewandt
(nicht auf die echte — sonst entstünde wieder nur ein Fächer). Die Zeitstempel
werden unverändert von der echten Route übernommen, dadurch laufen beide
Animationen zwangsläufig synchron.

**Der echte Schritt bleibt Teil der Kandidatenmenge.** In einer
Step-Selection-Funktion ist er der „genutzte" unter den „verfügbaren"
Schritten; ihn auszuschließen würde die Simulation künstlich von der Realität
wegdrücken.

**Standardmäßig mehrere Realisierungen** (3): Eine einzelne Linie neben der
echten Route wird unweigerlich als Vorhersage gelesen. Mehrere
auseinanderlaufende Linien zeigen den Zufallscharakter unmittelbar.

---

## 5. NEU: Empirisch kalibrierte Richtungstreue

**Wo:** `sync_simulation.EMPIRICAL_TURN_PERSISTENCE`,
`_mean_cos_for_step_length()`, `_kappa_from_mean_cos()`

**Problem:** Die Kandidatenrichtungen sind gleichverteilt
(`angle_offset = random.uniform(0, 360)`). Zieht man daraus ebenfalls
gleichverteilt, hat der entstehende Pfad keinerlei Bezug zum Drehverhalten
echter Bären.

**Erster, verworfener Ansatz:** ein fester Trägheitsparameter wie im
Japan-Teil (`japan_comparison.DEFAULT_PERSISTENCE_WEIGHT = 2.5`).

**Messung an den echten Daten** (13 Bären, alle Paare aufeinanderfolgender
1-h-Schritte, n = 46 161), Mittelwert von cos(Drehwinkel) nach Schrittlänge:

| Schrittlänge | n | mittleres cos | Median-Drehwinkel |
|---|---|---|---|
| < 25 m | 24 058 | **−0,202** | 114° |
| 25–50 m | 5 876 | −0,122 | 106° |
| 50–100 m | 4 545 | +0,106 | 75° |
| 100–200 m | 4 529 | +0,251 | 62° |
| 200–500 m | 4 634 | +0,414 | 47° |
| > 500 m | 2 519 | **+0,588** | 36° |

Über alle Schritte gemittelt ergibt sich cos = −0,012, also scheinbar völlig
richtungsloses Umherlaufen. Das ist aber eine Mischung aus zwei
**gegensätzlichen** Zuständen: kleinräumiges Fressen/Ruhen (kurze Schritte,
ausgeprägtes Hin-und-Her) und zielgerichtetes Wandern (lange Schritte,
deutlich geradeaus). Ein einzelner fester Parameter kann beides nicht
abbilden.

**Lösung:** Die Kandidaten werden mit `exp(κ · cos(Drehwinkel))` gewichtet —
eine diskrete von-Mises-Verteilung der Drehwinkel, dem Standardmodell der
Bewegungsökologie. κ wird pro Schritt aus der gemessenen Richtungstreue bei
dieser Schrittlänge abgeleitet (Umkehrung von A(κ) = I₁(κ)/I₀(κ) nach der
Näherung von Fisher 1993, Abschn. 4.5.5). Kein frei gewählter Parameter — der
Wert steht in den Daten.

**Validierung** an 40 zufälligen Bär-Tagen mit je ≥ 10 GPS-Punkten, Netto-
Verlagerung pro Tag (Median über alle Tage):

| Variante | Netto-Verlagerung | Abweichung |
|---|---|---|
| **Echte Bären** | **885 m** | — |
| `off` (gleichverteilt) | 697 m | −21 % |
| `fixed` (κ = 2,5, fest) | 1 373 m | +55 % |
| `empirical` (kalibriert) | **858 m** | **−3 %** |

Alle drei Varianten bleiben über `persistence_mode` verfügbar, damit der
Vergleich in der Arbeit reproduzierbar ist.

**Einschränkung:** Der Median aller Schritte liegt bei 22,7 m. In dieser
Größenordnung liegt auch die GPS-Ungenauigkeit. Ein Teil des gemessenen
Hin-und-Her bei kurzen Schritten dürfte daher Messrauschen und nicht
Verhalten sein — die negativen Werte sind eher eine Obergrenze der
Tortuosität.

**Offene Frage für die Arbeit:** Der Japan-Teil verwendet einen festen
Trägheitswert von 2,5. Die hier gemessenen Daten stützen diesen Wert für
kurze Schritte nicht. Da in Japan keine echte Route als Anker existiert, ist
dort ein höherer Wert praktisch nötig (sonst erreicht der simulierte Bär nie
eine zweite Kamera) — das ist aber eine Modellierungsentscheidung und keine
empirische Ableitung und sollte in der Arbeit als Limitation genannt werden.

---

## 6. Schritte ohne Geschwindigkeitsdaten

**Wo:** `sync_simulation._build_simulated_realizations()`

Fehlt für eine Stunde/Demografie ein Eintrag in `bear_speeds`, erzeugt
Fabians Code für diesen Schritt keine Kandidaten. Die Realisierung hält dann
die Position und setzt trotzdem einen Punkt auf den nächsten Zeitstempel,
damit die Zeitachse lückenlos zur echten Route passt. Die Anzahl solcher
Schritte wird als Warnung ausgegeben — sonst sähe ein Stillstand wie ein
Verhaltensbefund aus.

---

## 7. Segmentaufbau ohne StepTrajectorySet (Simulations-Layer der Hauptkarte)

**Wo:** `bear_simulation/__init__.py`, `_build_segments_from_db()`

**Original:** `model/StepTrajectorySet.py`, `build_segments()`

**Problem:** `bear_simulation/__init__.py` importierte `StepSelectionModel`.
Dessen Konstruktor zieht die Kette `StepTrajectorySet` →
`SeasonalTrajectoryProcessor` → `ClusterCalculator` → `Hdbscan` mit und
braucht damit `hdbscan` und `sklearn`. Deren kompilierte Dateien werden auf
dem Entwicklungsrechner von Windows Smart App Control blockiert:

```
ImportError: DLL load failed while importing murmurhash:
Eine Anwendungssteuerungsrichtlinie hat diese Datei blockiert.
```

Der Import scheiterte, `get_simulation_options()` fiel auf den DB-Zweig
zurück — und der liefert `bear_ids, {}`, also **leere** `seasons_info`.
In `map.py` wird daraus `_sim_season = None`, womit der Guard
`if sim_bear_ids and _sim_bear is not None and _sim_season is not None`
fehlschlägt: `get_simulation_geojson()` wurde nie aufgerufen und der Layer
blieb leer.

**Warum ein Nachbau vertretbar ist:** `build_segments()` besteht aus drei
Schritten. Nur der letzte, `assign_geometric_medians()`, braucht die
Cluster-Kette — und er setzt ausschließlich `local_geometric_median`, ein
Attribut, das `generate_alternative_steps()` an keiner Stelle liest. Für
diese Karte ist die Cluster-Analyse also nicht nur blockiert, sondern
ohnehin überflüssig (und langsam).

**Übernommene Regeln, unverändert:**
1. nach `bear_id` gruppieren, nach Zeit sortieren
2. neues Segment bei einer Zeitlücke > 1,5 Stunden
3. zusätzlich an Saisongrenzen trennen (`BearSeasons`)
4. Segmente mit < 5 Schritten verwerfen

**Nicht übernommen:** `assign_geometric_medians()` (siehe oben).

**Ergebnis:** 9 Bären, 30 (Bär, Saison)-Kombinationen mit echten
Schrittzahlen. `get_simulation_options()` und `get_simulation_geojson()`
haben Signatur und Rückgabeformat behalten, `map.py` ist unverändert.

**Einschränkung:** Ein direkter Ausgabevergleich mit dem Originalpfad war
nicht möglich, weil `hdbscan` auf diesem Rechner nicht ladbar ist. Die
Gleichwertigkeit stützt sich auf den Vergleich des Quelltexts.

**Nebenbei:** `StepSelectionModel` lud die Geschwindigkeiten über eine
offene SQLite-Verbindung; ersetzt durch `_SpeedTable`, einen reinen
In-Memory-Dict (SQLite-Verbindungen sind nicht thread-sicher, Streamlit
ruft die Karte aus wechselnden Threads auf). Dieses Verhalten war in der
Vorversion bereits so und wurde beibehalten.

---

## 8. Richtungswahl nach Geyer/Melzer/Dünnweber (Formel (1))

**Wo:** `japan_comparison._terrain_clusters()`, `_habitat_score()`,
`choose_weighted_direction()`; `terrain_cache.get_cells_in_box()`

**Grundlage:** J. Geyer, M. Melzer, J. Dünnweber, A. Sarkar, *Human Step
Movement Imitation for Training Privacy-Aware Intelligent Environments*, IEEE,
Abschnitt III-B und Formel (1):

    P = Σ(wᵢ · pᵢ) / Σwᵢ

Im Paper ist P die Fußposition auf einer Sensormatte, pᵢ der Schwerpunkt eines
aktivierten Dreiecksfelds und wᵢ dessen Kapazitätswert. Der Kern: statt sich
für *ein* Rasterfeld zu entscheiden, wird eine **kontinuierliche** Position aus
allen aktivierten Feldern berechnet, die zu den stärker aktivierten hin
tendiert. Vorgeschaltet ist eine Trennung in einzelne Füße — ohne sie läge der
Mittelwert zweier Füße zwischen ihnen, also dort, wo gar kein Fuß ist.

### Das behobene Problem

Die bisherige Richtungswahl prüfte acht feste Richtungen im 45°-Raster mit
±15° Streuung. Jeder Sektor deckte damit nur 30 seiner 45 Grad ab: **ein
Drittel aller Richtungen war grundsätzlich unerreichbar**. An 3 840
Entscheidungen nachgemessen — in den Lücken lag keine einzige.

### Was übernommen wurde und was nicht

**Übernommen:** Formel (1) selbst und die Reihenfolge *erst trennen, dann
gewichtet mitteln*.

**Nicht übernommen — wichtig für die Arbeit:** Das Trennverfahren des Papers
ist **nicht** ein Clustering der aktivierten Rasterfelder. Mean Shift läuft
dort auf **Pixel-Embeddings in einem gelernten 16-dimensionalen Raum** (U-Net
mit discriminative loss, 200 Epochen, 25 918 Trainingsbeispiele); die räumliche
Trennung der Füße ist das Ergebnis, nicht der Mechanismus. Ein solches
Embedding existiert hier nicht und wäre für ein regelmäßiges Geländeraster auch
unnötig — benachbarte Zellen sind bereits im Raum benachbart, eine
Zusammenhangskomponenten-Suche (Flutfüllung, 8er-Nachbarschaft) trennt die
Gebiete direkt. **Das ist ein Analogon zum Ziel des Schritts, nicht zu seiner
Methode**, und sollte in der Arbeit so formuliert werden.

**Vorzeichen der Gewichte:** Im Paper sind wᵢ Kapazitätswerte, also
nichtnegativ. Geländebewertungen sind vorzeichenbehaftet (Wald +3, Autobahn
−4). Ein Schwerpunkt mit negativen Gewichten ist nicht sinnvoll: der Nenner
kann gegen null gehen und das Ergebnis beliebig weit wegspringen. Deshalb gehen
nur Zellen oberhalb der Attraktivitätsschwelle ein, mit Gewicht
(Bewertung − Schwelle + 0,5).

### Zusätzliche Korrektur: Habitat getrennt von Störung

`_score_terrain()` summiert alle Merkmale einer Zelle, auch die negativen. Eine
Waldzelle mit einem Waldweg kommt so auf 3,0 − 1,5 = 1,5. Gemessen am
Kameragebiet tragen 11,5 % der Zellen einen Wald-Tag, aber nur 6,1 % erreichen
in der Summenbewertung noch 1,0 — die Wälder werden von Wegen zerschnitten und
zerfallen in Ein-Zellen-Cluster. Für die Frage „wo liegt ein zusammenhängendes
Waldstück" ist das die falsche Größe; ein Weg macht aus Wald keinen Nicht-Wald.
Deshalb `_habitat_score()`: nur die positiven Terme. Die Strafterme wirken
weiterhin dort, wo sie hingehören — in der Bewertung des Schrittziels.

### Zwei Ergänzungen, die sich erst aus den Messungen ergaben

**Stichproben entlang des Wegs** statt nur am Endpunkt: Eine Cluster-Richtung
zeigt auf den Schwerpunkt eines Waldstücks, das hinter einem Dorf liegen kann.
Bei reiner Endpunktbewertung sah der Weg attraktiv aus und der Bär lief mitten
durch die Ortschaft. Drei Stichproben senkten den Wohnstraßenanteil von 40,7
auf 38,1 %.

**Anziehung proportional zur Clustermasse** (`CLUSTER_ATTRACTION`,
tanh-gedeckelt): Ohne diesen Term war die Übertragung *wirkungslos*. Eine
Cluster-Richtung war dann nur ein weiterer Kandidat, der wie die freien
bewertet wurde — die eigentliche Information aus Formel (1), „in dieser
Richtung liegt eine große Masse attraktiven Geländes", ging verloren. Gemessen
(60 Läufe je Stufe):

| Anziehung | Wald % | mittl. Bewertung |
|---|---|---|
| 0 (wirkungslos) | 30,2 | −0,41 |
| 1 | 34,7 | −0,36 |
| 2 | 34,9 | −0,37 |
| **4 (gewählt)** | **39,1** | **−0,27** |
| 8 | 43,2 | −0,44 |

Bei 8 kippt die Bewertung wieder, weil der Bär Wald um jeden Preis ansteuert
und dafür schlechtes Gelände durchquert. 4 liegt nahe am Optimum.

### Messergebnisse (60 Läufe à 24 h, identische Seeds, echte Kamerastandorte)

| Kennzahl | ALT (45°-Raster) | neu, ohne Cluster | neu, mit Clustern |
|---|---|---|---|
| Tagesstrecke | 1 988 m | 1 988 m | 1 988 m |
| Netto-Verlagerung | 884 m | 976 m | 909 m |
| Waldanteil | 34,5 % | 31,9 % | **39,1 %** |
| Wohngebiet (`landuse=residential`) | 0,0 % | 0,0 % | 0,0 % |
| Wohnstraße (`highway=residential`) | 40,7 % | 38,1 % | 42,7 % |
| mittlere Geländebewertung | −0,33 | −0,37 | **−0,27** |
| Laufzeit je 24-h-Lauf | 0,068 s | 0,149 s | 0,219 s |

Laufzeit rund **3× langsamer**, absolut aber unkritisch (gut 0,2 s je Lauf).

**Zwei Korrekturen an bisher berichteten Zahlen:**

1. Die **Tagesstrecke ist als Vergleichsmaß ungeeignet.** Sie ist die Summe der
   Schrittlängen, die allein aus der Geschwindigkeitstabelle folgen — von der
   Richtungswahl hängt sie überhaupt nicht ab und ist in allen Varianten exakt
   gleich. Aussagekräftig ist nur die Netto-Verlagerung.
2. Der bisher berichtete „Siedlungsanteil" von rund 30 % ist **vollständig
   `highway=residential`**, also Wohnstraßen. Echtes Wohnbauland
   (`landuse=residential`) wird in **keiner** Variante betreten (0,0 %). Die
   Oder-Verknüpfung beider Merkmale hat den Wert massiv überzeichnet.

### Wirksamkeit des Trennschritts — der wichtigste Vorbehalt

Entlang der simulierten Pfade (500 Positionen) wurden gefunden:

| Cluster in Reichweite | Positionen |
|---|---|
| 0 | 246 (49 %) |
| 1 | 237 (47 %) |
| 2 | 17 (3 %) |

**Nur 3,4 % der Positionen haben mehr als einen Cluster.** Der Trennschritt —
also genau der Beitrag, den das Paper als entscheidend beschreibt — wird in
diesem Gebiet fast nie wirksam. Der gemessene Gewinn stammt praktisch
vollständig aus der kontinuierlichen Zielrichtung nach Formel (1) und aus dem
Massenbonus, nicht aus der Trennung mehrerer Gebiete. Das ist kein Fehler der
Umsetzung, sondern eine Eigenschaft der Landschaft: um die Kameras herum liegt
meist entweder gar kein oder genau ein zusammenhängendes Waldstück in
Reichweite. In einer stärker zergliederten Landschaft wäre eine andere
Bewertung zu erwarten — das gehört als Einschränkung in die Arbeit.

### Richtungsverteilung nach der Umstellung

3 840 Entscheidungen aus 160 Läufen à 24 h: **31,9 %** liegen in den früher
unerreichbaren Bändern (bei Gleichverteilung wären es 33 %), **kein** leerer
Sektor unter 24 Sektoren à 15°. Die Verteilung ist nicht gleichförmig
(χ² = 163 bei df = 23) — das ist erwartet und erwünscht, weil Geländeanziehung
und Richtungsträgheit gezielt bestimmte Richtungen bevorzugen. Beseitigt ist
das *systematische* Loch, nicht die inhaltliche Bevorzugung.

### Randbedingungen

- **Kein scikit-learn**, kein Mean Shift: Flutfüllung in reinem Python.
- **Keine Netzwerkzugriffe.** Im Test wird `socket.socket.connect` durch eine
  Ausnahme ersetzt; alle Läufe gehen ausschließlich gegen den lokalen
  Rasterspeicher (`terrain_cache.db`, 20 075 Zellen).
- Ohne Geländedaten (`terrain_cache=None`) bleibt die Kandidatenerzeugung
  stratifiziert wie bisher, nur mit **±22,5° statt ±15°** — damit stoßen die
  Sektoren lückenlos aneinander.
- **Rückfall ohne Cluster:** Findet sich kein attraktives Gebiet (bei 49 % der
  Positionen der Fall), bleiben schlicht die acht freien Kandidaten übrig. Das
  entspricht dem bisherigen Verhalten und braucht keinen Sonderfall.

### Nicht geändert

Die Richtungsträgheit im Japan-Teil bleibt beim festen Wert 2,5
(`DEFAULT_PERSISTENCE_WEIGHT`) und nutzt **nicht** das empirisch kalibrierte
von-Mises-κ aus `sync_simulation` (siehe Punkt 5). Das ist Absicht: um den
Effekt der neuen Richtungswahl sauber zu messen, darf sich nur eine Sache
ändern. Die Umstellung bleibt als offener Punkt bestehen.

Reproduzierbar mit `python test_richtungsverteilung.py`.
