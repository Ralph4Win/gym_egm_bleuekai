# QGIS-Visualisierung – Standortanalyse Fitnesscenter Zürich

Dieser Ordner enthält ein PyQGIS-Automatisierungsskript, das alle Geodaten
des Projekts automatisch in QGIS lädt und korrekt stilisiert.

## Voraussetzungen

1. **QGIS 3.x** installiert (https://qgis.org)
2. **Jupyter Notebook vollständig durchgelaufen** (erzeugt die GeoJSON-Dateien in `data/processed/`)
   - Besonders wichtig: die Datei `data/processed/quartiere_scored.geojson` wird
     vom Notebook in Sektion 8 erzeugt und enthält den berechneten Standort-Score.

## Skript ausführen

1. QGIS öffnen
2. **Plugins → Python Console** (oder `Strg+Alt+P`)
3. Im Console-Fenster: **„Editor anzeigen"** klicken
4. **„Skript öffnen"** → `qgis/setup_qgis_project.py` wählen
5. **Grünen Pfeil** (▶) klicken – alle Layer werden automatisch geladen

## Was das Skript macht

Das Skript lädt und stilisiert automatisch:

| Layer | Stil |
|-------|------|
| Stadtgrenze Zürich | Transparente Fläche, dunkelblauer Rand |
| Statistische Quartiere | **Choropleth nach Standort-Score** (Rot–Gelb–Grün, 5 Klassen) |
| Isochronen (10 / 15 Min.) | Grün / Gelb, 35% Transparenz |
| ÖV-Haltestellen | Blaue Punkte |
| Fitnesscenter (OSM) | Rote Punkte mit weissem Rand |
| Geokodierte Adressen | Orange Sterne |

## Koordinatensystem

Alle Layer werden in **LV95 (EPSG:2056)** dargestellt – dem offiziellen
Schweizer Koordinatensystem. Das Projekt-CRS wird automatisch gesetzt.

## Drucklayout erstellen (für Präsentation)

Nach dem Skript-Ausführen:

1. **Projekt → Neues Drucklayout** → Name eingeben (z.B. „Standort-Score")
2. **Karte hinzufügen** (Werkzeug oben links) → Bereich auf dem Blatt aufziehen
3. **Massstabsbalken** hinzufügen: Layout → Massstabsbalken hinzufügen
4. **Nordpfeil** hinzufügen: Layout → Bild hinzufügen → OSM-Nordpfeil wählen
5. **Legende** hinzufügen: Layout → Legende hinzufügen
6. **Titel** hinzufügen: Layout → Beschriftung hinzufügen
7. **Exportieren**: Layout → Als Bild exportieren (PNG, 300 DPI)

## Empfohlene Basemap (QuickMapServices Plugin)

1. **Plugins → Plugins verwalten** → „QuickMapServices" installieren
2. **Web → QuickMapServices → Einstellungen → Mehr Services** aktivieren
3. Empfohlen: **CartoDB → Positron** (heller Hintergrund, professionell)

## Datenquellen (Koordinatenreferenz)

| Datei | Inhalt |
|-------|--------|
| `city_boundary.geojson` | Stadtgrenze Zürich (OSM) |
| `statistical_quarters.geojson` | 34 statistische Quartiere (Stadt Zürich OGD) |
| `quartiere_scored.geojson` | Quartiere mit berechnetem Standort-Score |
| `fitness_centers.geojson` | Fitnesscenter (OSM) |
| `oev_stops.geojson` | ÖV-Haltestellen (OSM) |
| `isochrones.geojson` | Isochronen 10/15 Min. (osmnx) |
| `geocoded_addresses.geojson` | Geokodierte Fitnesscenter-Adressen (Nominatim) |
