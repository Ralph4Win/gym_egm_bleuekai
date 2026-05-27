"""
setup_qgis_project.py
=====================
PyQGIS-Skript fuer die Standortanalyse Fitnesscenter Zuerich.

Ausfuehren in QGIS:
    1. QGIS oeffnen
    2. Plugins -> Python Console (Strg+Alt+P)
    3. Auf "Editor anzeigen" klicken
    4. Dieses Skript laden oder den Inhalt einfuegen
    5. "Skript ausfuehren" (gruener Pfeil)

Voraussetzung:
    Das Jupyter Notebook muss zuerst vollstaendig ausgefuehrt worden sein
    (erzeugt die GeoJSON-Dateien in data/processed/).

ZHAW FS2026 | Einsatz von Geodaten im Marketing | Kai Bleuel
"""

import os
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsCoordinateReferenceSystem,
    QgsFillSymbol, QgsLineSymbol, QgsMarkerSymbol,
    QgsGraduatedSymbolRenderer, QgsRendererRange,
    QgsCategorizedSymbolRenderer, QgsRendererCategory,
    QgsClassificationQuantile, QgsGradientColorRamp,
    QgsLayoutItemMap, QgsLayoutItemScaleBar, QgsLayoutItemLegend,
    QgsLayoutItemLabel, QgsPrintLayout, QgsLayoutSize,
    QgsLayoutPoint, QgsUnitTypes, QgsLayoutExporter,
)
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtCore import QRectF

# ── Pfade ─────────────────────────────────────────────────────────────────────
# Pfad zum EGD-Projektordner (Elternordner von qgis/)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR  = os.path.join(BASE_DIR, "data",    "processed")
OUT_DIR   = os.path.join(BASE_DIR, "outputs", "maps")
QGIS_DIR  = os.path.join(BASE_DIR, "qgis")

def p(filename):
    """Erstellt den vollstaendigen Pfad zu einer Datendatei."""
    return os.path.join(DATA_DIR, filename)

print(f"EGD Projektpfad : {BASE_DIR}")
print(f"Datenpfad       : {DATA_DIR}")
print()

# ── Projekt-CRS: LV95 (EPSG:2056) ────────────────────────────────────────────
project = QgsProject.instance()
crs = QgsCoordinateReferenceSystem("EPSG:2056")
project.setCrs(crs)
print(f"Projekt-CRS gesetzt: {crs.authid()} ({crs.description()})")

# ── Hilfsfunktion: Layer laden ────────────────────────────────────────────────
def load_vector(filename, name, crs_epsg="EPSG:2056"):
    """Laed eine GeoJSON-Datei als Vektorlayer und fuegt sie dem Projekt hinzu."""
    path = p(filename)
    if not os.path.exists(path):
        print(f"  FEHLER: Datei nicht gefunden – {path}")
        print(f"  Hinweis: Zuerst das Jupyter Notebook ausfuehren!")
        return None
    layer = QgsVectorLayer(path, name, "ogr")
    if not layer.isValid():
        print(f"  FEHLER: Layer ungueltig – {name}")
        return None
    project.addMapLayer(layer)
    print(f"  OK: {name} ({layer.featureCount()} Features, {layer.geometryType()})")
    return layer

# ── Alle Gruppen-Layer entfernen (sauberer Start) ─────────────────────────────
for layer in list(project.mapLayers().values()):
    project.removeMapLayer(layer)

# ═══════════════════════════════════════════════════════════════════════════════
# LAYER LADEN
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Layer laden ---")

# Reihenfolge: von unten nach oben (letzter = zuoberst im Layer-Panel = wird zuletzt gerendert)
# Ziel-Reihenfolge (unten → oben):
#   Stadtgrenze → Quartiere (Choropleth) → Isochronen → OEV-Stops → Fitnesscenter → Geokodiert
city    = load_vector("city_boundary.geojson",   "Stadtgrenze Zuerich")
quarters_scored = load_vector("quartiere_scored.geojson", "Quartiere (Score)")
quarters_basic  = None
if quarters_scored is None:
    quarters_basic = load_vector("statistical_quarters.geojson", "Statistische Quartiere")
iso     = load_vector("isochrones.geojson",       "Isochronen (Gehzeit)")   # unter OEV-Stops
oev     = load_vector("oev_stops.geojson",        "OEV-Haltestellen")       # ueber Isochronen
gyms    = load_vector("fitness_centers.geojson",  "Fitnesscenter")
geocoded = load_vector("geocoded_addresses.geojson", "Geokodierte Adressen")

# ═══════════════════════════════════════════════════════════════════════════════
# LAYER STILISIERUNG
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Stilisierung ---")

# ── 1. Stadtgrenze ────────────────────────────────────────────────────────────
if city:
    sym = QgsFillSymbol.createSimple({
        "color"        : "255,255,255,0",   # Transparent
        "outline_color": "#1D3557",
        "outline_width": "1.5",
        "outline_style": "solid",
    })
    city.setRenderer(city.renderer().__class__(sym))
    city.triggerRepaint()
    print("  Stadtgrenze: transparent mit dunkelblauem Rand")

# ── 2. Quartiere: Choropleth nach Standort-Score ─────────────────────────────
if quarters_scored:
    field = "location_score"
    fields = [f.name() for f in quarters_scored.fields()]
    if field not in fields:
        field = "pop_density" if "pop_density" in fields else fields[0]
        print(f"  Hinweis: 'location_score' nicht gefunden, verwende '{field}'")

    # Farbreihe: Rot (tief) -> Gelb -> Gruen (hoch) = RdYlGn
    color_ramp = QgsGradientColorRamp(
        QColor("#D73027"),   # Rot (niedrig)
        QColor("#1A9850"),   # Gruen (hoch)
        False,
        [
            QgsGradientStop(0.25, QColor("#FC8D59")),
            QgsGradientStop(0.50, QColor("#FFFFBF")),
            QgsGradientStop(0.75, QColor("#91CF60")),
        ]
    )

    # 5 Klassen (Quantile)
    renderer = QgsGraduatedSymbolRenderer(field)
    renderer.setClassificationMethod(QgsClassificationQuantile())
    renderer.updateColorRamp(color_ramp)
    renderer.updateClasses(quarters_scored, 5)

    # Umrandung der Quartiere
    for range_ in renderer.ranges():
        sym = range_.symbol().clone()
        sym.symbolLayer(0).setStrokeColor(QColor("white"))
        sym.symbolLayer(0).setStrokeWidth(0.3)
        sym.setOpacity(0.70)   # 70% Deckkraft: Basemap leicht sichtbar
        range_.setSymbol(sym)

    quarters_scored.setRenderer(renderer)
    quarters_scored.triggerRepaint()
    print(f"  Quartiere: Choropleth '{field}' (5 Quantilklassen, RdYlGn)")

# ── 3. Isochronen ─────────────────────────────────────────────────────────────
if iso:
    cats = []
    iso_styles = {
        10: ("#2A9D8F", "10 Min. Gehzeit"),
        15: ("#E9C46A", "15 Min. Gehzeit"),
    }
    for val, (color, label) in iso_styles.items():
        sym = QgsFillSymbol.createSimple({
            "color"        : color,
            "outline_style": "no",
        })
        sym.setOpacity(0.20)   # 20% Deckkraft: sichtbar aber stoert Choropleth nicht
        cats.append(QgsRendererCategory(val, sym, label))

    iso.setRenderer(QgsCategorizedSymbolRenderer("walk_min", cats))
    iso.triggerRepaint()
    print("  Isochronen: 10 Min. (Gruen, 20%), 15 Min. (Gelb, 20%)")

# ── 4. OEV-Haltestellen ───────────────────────────────────────────────────────
if oev:
    sym = QgsMarkerSymbol.createSimple({
        "name"         : "circle",
        "color"        : "#1565C0",   # kraeftiges Dunkelblau
        "size"         : "1.8",       # groesser (war 1.8)
        "outline_color": "white",
        "outline_width": "0.3",
    })
    sym.setOpacity(0.85)
    oev.renderer().setSymbol(sym)
    oev.triggerRepaint()
    print("  OEV-Haltestellen: blaue Punkte (2.8 px, weisser Rand)")

# ── 5. Fitnesscenter ──────────────────────────────────────────────────────────
if gyms:
    sym = QgsMarkerSymbol.createSimple({
        "name"          : "circle",
        "color"         : "#E63946",
        "size"          : "4.0",
        "outline_color" : "white",
        "outline_width" : "0.5",
    })
    gyms.renderer().setSymbol(sym)
    gyms.triggerRepaint()
    print("  Fitnesscenter: rote Punkte (4 px, weisser Rand)")

# ── 6. Geokodierte Adressen ───────────────────────────────────────────────────
if geocoded:
    sym = QgsMarkerSymbol.createSimple({
        "name"          : "star",
        "color"         : "#FF6B35",
        "size"          : "5.0",
        "outline_color" : "#1D3557",
        "outline_width" : "0.5",
    })
    geocoded.renderer().setSymbol(sym)
    geocoded.triggerRepaint()
    print("  Geokodierte Adressen: orange Sterne (5 px)")

# ── Kartenleinwand zoomen ─────────────────────────────────────────────────────
if city:
    iface.mapCanvas().setExtent(city.extent())
    iface.mapCanvas().refresh()

print("\n--- Abgeschlossen ---")
print("Layer koennen jetzt in QGIS inspiziert und layoutet werden.")
print()
print("=" * 60)
print("TIPPS FUER VERSCHIEDENE KARTEN-LAYOUTS:")
print("=" * 60)
print()
print("Karte 1 – Standort-Score (empfohlen fuer Ergebnis-Slide):")
print("  AN : Stadtgrenze, Quartiere (Score), Fitnesscenter")
print("  AUS: Isochronen, OEV-Haltestellen, Geokodierte Adressen")
print()
print("Karte 2 – Erreichbarkeit (oeffentlicher Verkehr):")
print("  AN : Stadtgrenze, Quartiere (Score), Isochronen, OEV-Haltestellen")
print("  AUS: Fitnesscenter, Geokodierte Adressen")
print()
print("Karte 3 – Wettbewerb (Fitnesscenter-Verteilung):")
print("  AN : Stadtgrenze, Quartiere (Score), Fitnesscenter")
print("  AUS: Isochronen, OEV-Haltestellen, Geokodierte Adressen")
print()
print("Fuer Drucklayout:")
print("  Projekt -> Neues Drucklayout -> Titel eingeben")
print("  'Karte hinzufuegen' -> aufziehen -> Massstab, Nordpfeil, Legende")
