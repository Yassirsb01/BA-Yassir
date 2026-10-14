# Screenshots der laufenden Anwendung

Aufgenommen aus der tatsächlich laufenden Streamlit-Anwendung mit
bestehender MariaDB-Verbindung. Auflösung 3200 x 2200 Pixel
(1600 x 1100 CSS-Pixel bei doppelter Pixeldichte), also auch im Druck
scharf.

| Datei | Zeigt | Passt zu Kapitel |
|---|---|---|
| `01_hauptkarte_satellit.png` | Hauptkarte mit Satellitengrundkarte, Ebenenschalter mit Objektzählern, Simulationsebene aktiv | 4.1, 4.7 |
| `02_alle_ebenen.png` | Alle fünf Ebenen gleichzeitig: Japan, Karpaten, Simulation, Wolf/Luchs (BfN), Bärensichtungen (GBIF) | 4.2, 4.3 |
| `03_3d_gelaende.png` | 3D-Geländedarstellung mit echten GPS-Punkten (cyan) und simulierten Pfaden (rot) | 4.1 |
| `04_ebene_japan.png` | Kamerastandorte und Abschreckungsgeräte in Japan auf der Hauptkarte | 4.2 |
| `05_animation_karpaten.png` | Animationsseite: echter Pfad gegen simulierte Bären, Bedienfeld mit Realisierungen und Zufallszahl | 4.4 |
| `06_japan_experiment.png` | Japan-Experiment: 6 simulierte Bären ab einem echten Fotoereignis, Kamera 003000 mit 11 realen Aufnahmen, Zeitleiste und Auslöseprotokoll | 4.5 |
| `07_japan_gelaendegewichtung.png` | Dieselbe Seite mit eingeschalteter Geländegewichtung | 4.5.2, 4.5.3 |

## Offener Punkt

In `05_animation_karpaten.png` sind die Bewegungspfade noch **nicht**
sichtbar: die Animation steht auf dem Startzeitpunkt, deshalb ist nur
der blaue Startpunkt zu sehen. Für die Arbeit sollte das Bild durch eine
Aufnahme ersetzt werden, bei der die Animation durchgelaufen ist und die
Spuren gezeichnet sind.

## Neu aufnehmen

Die Anwendung starten und im Browser aufrufen:

```
python -m streamlit run map.py --server.port 8512
```

Hinweis: Wird die Anwendung aus einer Umgebung ohne Netzwerkfreigabe
gestartet, meldet sie „MariaDB not reachable", obwohl der VPN steht. Die
Screenshots oben sind mit funktionierender Verbindung entstanden.
