"""
generate_notebook.py
====================
Generiert das vollständige Jupyter Notebook für die Standortanalyse
Fitnesscenter Zürich via nbformat.

Ausführen:
    cd notebooks/
    python generate_notebook.py
"""

import nbformat as nbf
from pathlib import Path

OUT = Path(__file__).parent / "standortanalyse_fitnesscenter_zuerich.ipynb"

nb = nbf.v4.new_notebook()
nb.metadata = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3.10.0"},
}

def md(src):  return nbf.v4.new_markdown_cell(src)
def code(src): return nbf.v4.new_code_cell(src)

cells = []

# ════════════════════════════════════════════════════════════════════════
# TITELSEITE
# ════════════════════════════════════════════════════════════════════════
cells.append(md("""# 📍 Standortanalyse für Fitnesscenter in der Stadt Zürich

**Kurs:** Einsatz von Geodaten im Marketing (WPM-EGM.XX) – ZHAW School of Management and Law, FS2026
**Autor:** Kai Bleuel
**Abgabe:** 27. Mai 2026
**Betreuer:** Dr. Mario Gellrich

---

## Inhaltsverzeichnis

1. [Einleitung & Forschungsfrage](#1)
2. [Setup & Konfiguration](#2)
3. [Datenbeschaffung](#3)
   - 3.1 Untersuchungsgebiet (Stadtgrenze Zürich)
   - 3.2 Fitnesscenter (OpenStreetMap)
   - 3.3 ÖV-Haltestellen (OpenStreetMap)
   - 3.4 Statistische Quartiere & Bevölkerungsdaten
4. [Angebotsanalyse: Bestehende Fitnesscenter](#4)
5. [Erreichbarkeitsanalyse: Isochronen](#5)
6. [Nachfrageanalyse: Bevölkerung & Arbeitsplätze](#6)
7. [Wettbewerbsanalyse](#7)
8. [Standort-Score-Modell](#8)
9. [Räumliche Autokorrelation (Moran's I)](#9)
10. [Ergebnisse & Handlungsempfehlungen](#10)

---
"""))

# ════════════════════════════════════════════════════════════════════════
# 1. EINLEITUNG
# ════════════════════════════════════════════════════════════════════════
cells.append(md("""<a id='1'></a>
## 1. Einleitung & Forschungsfrage

### Motivation

Der Fitnessmarkt in der Schweiz wächst kontinuierlich. In der Stadt Zürich konkurrieren zahlreiche
Anbieter um eine attraktive, kaufkräftige Kundschaft. Wie in der Vorlesung gezeigt, gehört die
**Standortanalyse** zu den wichtigsten Anwendungsfeldern des Geomarketings (Gellrich, FS2026):

> *„Where is the best location for my company? Is the planned location viable?"*

Die Entscheidung, wo ein neues Fitnesscenter eröffnet werden soll, hängt von mehreren räumlichen
Faktoren ab: Wo wohnen und arbeiten potenzielle Kunden? Wie gut ist ein Standort mit dem ÖV
erreichbar? Wie stark ist die Konkurrenz in der Umgebung?

### Forschungsfrage

> **„In welchen Gebieten der Stadt Zürich besteht Potenzial für neue Fitnesscenter-Standorte
> unter Berücksichtigung von Nachfrage, Erreichbarkeit und bestehender Konkurrenz,
> und wo ist der Markt bereits gesättigt?"**

### Hypothese

Gebiete mit **hoher Bevölkerungs- und Arbeitsplatzdichte** sowie **guter ÖV-Erreichbarkeit**
und **geringer Fitmesscenter-Dichte** weisen das höchste Standortpotenzial auf.

### Methodischer Überblick

| Schritt | Methode | Datenquelle |
|---------|---------|-------------|
| Angebotsanalyse | Point-in-Polygon, KDE | OpenStreetMap |
| Erreichbarkeit | Isochronen (Netzwerkanalyse) | OpenStreetMap (osmnx) |
| Nachfrage | Choropleth, Dichtekarte | Stadt Zürich OGD / BFS |
| Wettbewerb | Fitnesscenter/Einwohner | OSM + BFS |
| Standort-Score | Gewichtetes Modell | Alle Layer |
| Autokorrelation | Moran's I, LISA | Eigene Berechnung |

---
"""))

# ════════════════════════════════════════════════════════════════════════
# 2. SETUP
# ════════════════════════════════════════════════════════════════════════
cells.append(md("""<a id='2'></a>
## 2. Setup & Konfiguration

### 2.1 Bibliotheken importieren
"""))

cells.append(code("""\
# ── Standard-Bibliotheken ───────────────────────────────────────────────────
import warnings, sys, os
from pathlib import Path
import json, requests

warnings.filterwarnings('ignore')

# ── Datenverarbeitung ───────────────────────────────────────────────────────
import numpy as np
import pandas as pd

# ── Geodaten (Kerntool der Analyse) ────────────────────────────────────────
import geopandas as gpd          # Vektordaten (wie Vorlesung: GeoDataFrame)
from shapely.geometry import Point, Polygon, MultiPoint
from shapely.ops import unary_union
import osmnx as ox               # OpenStreetMap-Datenabfragen & Routing

# ── Visualisierung ──────────────────────────────────────────────────────────
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.cm as cm
from matplotlib.lines import Line2D
import contextily as ctx          # Basemaps (OpenStreetMap/CartoDB)
import folium                     # Interaktive Webkarten
from folium.plugins import MarkerCluster

# ── Räumliche Statistik (Kapitel 7 der Vorlesung) ─────────────────────────
try:
    from libpysal.weights import Queen
    from esda.moran import Moran, Moran_Local
    SPATIAL_STATS = True
    print("✅ libpysal + esda verfügbar → Moran's I wird berechnet")
except ImportError:
    SPATIAL_STATS = False
    print("⚠️  libpysal/esda fehlen → pip install libpysal esda")

# ── Projektmodule (src/) ────────────────────────────────────────────────────
ROOT = Path.cwd().parent
sys.path.insert(0, str(ROOT))
from config.settings import *
from src.data_loader import *
from src.spatial_analysis import *
from src.visualization import *

print(f"\\n📂 Projektpfad : {ROOT}")
print(f"🗂  Daten (roh)  : {DATA_RAW}")
print(f"🗂  Daten (proc) : {DATA_PROC}")
print(f"📊 Outputs       : {OUTPUT_MAPS}")
print(f"\\n⚙️  Primäres CRS : {CRS_LV95} (LV95 – Schweizer Landeskoordinaten, Meter)")
"""))

cells.append(md("""### 2.2 Koordinatenreferenzsysteme (CRS)

Aus der Vorlesung (Folie 40): Für die Schweiz werden zwei Koordinatensysteme verwendet:

| System | EPSG-Code | Typ | Verwendung |
|--------|-----------|-----|------------|
| WGS84 | EPSG:4326 | Geographisch (°) | GPS, OSM, APIs |
| LV95 | **EPSG:2056** | Projiziert (m) | Schweizer Standard, Distanzanalysen |
| Web Mercator | EPSG:3857 | Projiziert | Basemaps (Contextily) |

**Alle Analysen** werden im CRS **LV95 (EPSG:2056)** durchgeführt, da nur projizierte
Koordinatensysteme korrekte Distanzen und Flächenberechnungen in Metern ermöglichen.
"""))

cells.append(code("""\
# Demonstration CRS-Umrechnung (WGS84 → LV95)
# Beispiel: Hauptbahnhof Zürich

hb_wgs84 = gpd.GeoDataFrame(
    {"name": ["Hauptbahnhof Zürich"]},
    geometry=[Point(8.5404, 47.3782)],
    crs="EPSG:4326"
)
hb_lv95 = hb_wgs84.to_crs("EPSG:2056")

print("Koordinatensystem-Demonstration: Hauptbahnhof Zürich")
print(f"  WGS84  (EPSG:4326): lon={hb_wgs84.geometry[0].x:.4f}°, lat={hb_wgs84.geometry[0].y:.4f}°")
print(f"  LV95   (EPSG:2056): E={hb_lv95.geometry[0].x:.0f} m,  N={hb_lv95.geometry[0].y:.0f} m")
print(f"\\n→ Umrechnung mit: gdf.to_crs('EPSG:2056')")
"""))

# ════════════════════════════════════════════════════════════════════════
# 3. DATENBESCHAFFUNG
# ════════════════════════════════════════════════════════════════════════
cells.append(md("""---
<a id='3'></a>
## 3. Datenbeschaffung

### 3.1 Untersuchungsgebiet: Stadtgrenze Zürich

Die Stadtgrenze wird via **osmnx** aus OpenStreetMap geladen und in das
Analysen-CRS **LV95 (EPSG:2056)** reprojiziert.
"""))

cells.append(code("""\
print("=" * 60)
print("3.1  UNTERSUCHUNGSGEBIET")
print("=" * 60)

city_gdf = load_city_boundary()

# Basisinformationen
area_km2 = city_gdf.to_crs(CRS_LV95).geometry.area.sum() / 1e6
bbox = city_gdf.to_crs(CRS_WGS84).total_bounds

print(f"\\nStadt Zürich:")
print(f"  CRS             : {city_gdf.crs}")
print(f"  Fläche          : {area_km2:.1f} km²")
print(f"  Bounding Box    : N={bbox[3]:.4f}°, S={bbox[1]:.4f}°,")
print(f"                    E={bbox[2]:.4f}°, W={bbox[0]:.4f}°")
print(f"  Geometrietyp    : {city_gdf.geometry.iloc[0].geom_type}")

# GeoDataFrame-Info
print(f"\\nGeoDataFrame-Info:")
city_gdf.info()
"""))

cells.append(code("""\
# Karte: Stadtgrenze Zürich
fig, ax = plt.subplots(figsize=FIGSIZE_MAP)
city_web = city_gdf.to_crs(CRS_WEB)
city_web.plot(ax=ax, color="#EBF2FA", alpha=0.6, edgecolor=COLOR_CITY_EDGE,
              linewidth=2.5, zorder=2)
_add_basemap(ax, crs=CRS_WEB)
ax.set_title("Untersuchungsgebiet: Stadt Zürich", fontsize=14, fontweight="bold", pad=12)
ax.set_axis_off()
plt.tight_layout()
plt.show()
print(f"Stadtgrenze geladen ✅ | Fläche: {area_km2:.1f} km² | CRS: {city_gdf.crs.to_epsg()}")
"""))

cells.append(md("### 3.2 Fitnesscenter (OpenStreetMap)\n\nAbfrage via `osmnx.features_from_place()` mit den Tags `leisure=fitness_centre` und `amenity=gym`."))

cells.append(code("""\
print("=" * 60)
print("3.2  FITNESSCENTER (OpenStreetMap)")
print("=" * 60)

gyms_gdf = load_fitness_centers(city_gdf)

print(f"\\nGeoDataFrame Fitnesscenter:")
print(gyms_gdf.head(10).to_string())
print(f"\\nSpalten: {list(gyms_gdf.columns)}")
print(f"CRS: {gyms_gdf.crs}")
"""))

cells.append(code("""\
# Statistiken
print("\\n── Fitnesscenter-Statistiken ──────────────────────────────")
print(f"  Anzahl total           : {len(gyms_gdf)}")
if "source_tag" in gyms_gdf.columns:
    print(f"  Nach OSM-Tag:")
    print(gyms_gdf["source_tag"].value_counts().to_string())
if "name" in gyms_gdf.columns:
    named = gyms_gdf["name"].notna().sum()
    print(f"  Mit Namen              : {named} ({named/len(gyms_gdf)*100:.0f}%)")

# Geodaten-Format demonstrieren: GeoJSON Export
geojson_path = DATA_PROC / "fitness_centers.geojson"
print(f"\\n  Gespeichert als GeoJSON: {geojson_path}")
print("  GeoJSON-Struktur (erste 2 Features):")
with open(geojson_path) as f:
    gj = json.load(f)
print(json.dumps({
    "type": gj["type"],
    "features_count": len(gj["features"]),
    "sample_feature": gj["features"][0] if gj["features"] else {}
}, indent=2, ensure_ascii=False)[:600] + "...")
"""))

cells.append(md("### 3.3 ÖV-Haltestellen (OpenStreetMap)"))

cells.append(code("""\
print("=" * 60)
print("3.3  ÖV-HALTESTELLEN (OpenStreetMap)")
print("=" * 60)

oev_gdf = load_oev_stops(city_gdf)

print(f"  Anzahl Haltestellen: {len(oev_gdf)}")
if "oev_type" in oev_gdf.columns:
    print("  Nach Typ:")
    print(oev_gdf["oev_type"].value_counts().to_string())
"""))

cells.append(md("### 3.4 Statistische Quartiere & Bevölkerungsdaten\n\nDie Bevölkerungsdaten werden aus dem **Stadt Zürich Open Data Portal** geladen und mit den Quartiergeometrien verknüpft (Spatial Join)."))

cells.append(code("""\
print("=" * 60)
print("3.4  QUARTIERE & BEVÖLKERUNGSDATEN")
print("=" * 60)

quarters_gdf  = load_statistical_quarters()
population_df = load_population_data()
quarters_pop  = merge_quarters_population(quarters_gdf, population_df)

print(f"\\nStatistische Quartiere:")
print(f"  Anzahl Quartiere   : {len(quarters_pop)}")
print(f"  CRS                : {quarters_pop.crs}")
print(f"  Bevölkerung total  : {quarters_pop['population'].sum():,.0f}")
print(f"  Ø Quartiersgrösse  : {quarters_pop['area_km2'].mean():.2f} km²")
print(f"  Max. Dichte        : {quarters_pop['pop_density'].max():.0f} Einw./km²")
print(f"  Min. Dichte        : {quarters_pop['pop_density'].min():.0f} Einw./km²")

print("\\nTop-5 dichteste Quartiere:")
print(quarters_pop.nlargest(5, "pop_density")[
    ["quartier_name", "population", "area_km2", "pop_density"]
].to_string(index=False))
"""))

# ════════════════════════════════════════════════════════════════════════
# 4. ANGEBOTSANALYSE
# ════════════════════════════════════════════════════════════════════════
cells.append(md("""---
<a id='4'></a>
## 4. Angebotsanalyse: Bestehende Fitnesscenter

### 4.1 Karte: Fitnesscenter in der Stadt Zürich
"""))

cells.append(code("""\
fig = plot_city_with_gyms(city_gdf, gyms_gdf, oev_gdf=oev_gdf,
                          title=f"Fitnesscenter in der Stadt Zürich (n={len(gyms_gdf)})")
plt.show()
"""))

cells.append(md("### 4.2 Point-in-Polygon: Fitnesscenter pro Quartier\n\nMit dem **Point-in-Polygon**-Verfahren (aus der Vorlesung) wird jedem Fitnesscenter-Punkt das zugehörige Quartier zugewiesen."))

cells.append(code("""\
# Point-in-Polygon (aus Vorlesung: Vector Data Analysis)
gyms_proj  = gyms_gdf.to_crs(CRS_LV95)
quart_proj = quarters_pop.to_crs(CRS_LV95)

joined = gpd.sjoin(gyms_proj, quart_proj, how="left", predicate="within")

gyms_per_q = joined.groupby("index_right").size().rename("gyms_in_quarter")
quart_proj["gyms_count"] = quart_proj.index.map(gyms_per_q).fillna(0)
quart_proj["gyms_per_km2"] = quart_proj["gyms_count"] / quart_proj["area_km2"]

print("Point-in-Polygon: Fitnesscenter pro Quartier")
print("-" * 50)
top_gyms = quart_proj.nlargest(10, "gyms_count")[
    ["quartier_name", "gyms_count", "area_km2", "gyms_per_km2", "population"]
]
top_gyms["gyms_per_10k"] = top_gyms["gyms_count"] / top_gyms["population"] * 10000
print(top_gyms.round(2).to_string(index=False))

print(f"\\n  Quartiere OHNE Fitnesscenter: {(quart_proj['gyms_count'] == 0).sum()}")
print(f"  Quartiere mit 1+ Fitnesscenter : {(quart_proj['gyms_count'] >= 1).sum()}")
"""))

cells.append(code("""\
# Choropleth: Fitnesscenter-Dichte pro Quartier
fig = plot_choropleth(
    quart_proj, column="gyms_per_km2",
    title="Fitnesscenter-Dichte pro Quartier (Anzahl/km²)",
    cmap="YlOrRd",
    legend_label="Fitnesscenter pro km²",
    filename="02_fitnesscenter_dichte.png"
)
plt.show()
"""))

# ════════════════════════════════════════════════════════════════════════
# 5. ERREICHBARKEITSANALYSE (ISOCHRONEN)
# ════════════════════════════════════════════════════════════════════════
cells.append(md("""---
<a id='5'></a>
## 5. Erreichbarkeitsanalyse: Isochronen (Einzugsgebiete)

**Isochronen** zeigen, welche Gebiete innerhalb einer definierten Gehzeit
erreichbar sind (aus der Vorlesung: *Routing and calculation of isochrones*).

Methodik:
1. Strassennetzwerk Zürich via `osmnx` herunterladen
2. Für jeden Fitnesscenter-Standort den nächsten Netzwerkknoten finden
3. Erreichbare Knoten innerhalb 10/15 Min. via `networkx.ego_graph()` berechnen
4. Konvexe Hülle der erreichbaren Knoten = Isochrone (Einzugsgebiet)

*Annahme: Gehgeschwindigkeit = 4.5 km/h (Standardwert für Fussgänger)*
"""))

cells.append(code("""\
print("Starte Isochronen-Berechnung …")
print(f"Isochronenzeiten: {ISOCHRONE_WALK_MINS} Minuten")
print(f"Gehgeschwindigkeit: {WALK_SPEED_KMH} km/h")
print()

iso_gdf = compute_isochrones(
    gyms_gdf,
    walk_minutes=ISOCHRONE_WALK_MINS,
    query=STUDY_AREA_QUERY,
)

if len(iso_gdf) > 0:
    print(f"\\nIsochronen-Ergebnis:")
    print(iso_gdf.groupby("walk_min").size().rename("Anzahl Isochronen").to_string())

    # Deckungsgrad berechnen
    city_lv95 = city_gdf.to_crs(CRS_LV95)
    city_area = city_lv95.geometry.area.sum()

    for mins in ISOCHRONE_WALK_MINS:
        subset = iso_gdf[iso_gdf["walk_min"] == mins]
        if len(subset) > 0:
            covered = subset.geometry.union_all() if hasattr(subset.geometry, 'union_all') else unary_union(subset.geometry)
            covered_clip = covered.intersection(city_lv95.geometry.union_all() if hasattr(city_lv95.geometry, 'union_all') else unary_union(city_lv95.geometry))
            pct = covered_clip.area / city_area * 100
            print(f"  Deckungsgrad {mins} Min.: {pct:.1f}% der Stadtfläche")
"""))

cells.append(code("""\
fig = plot_isochrones(city_gdf, iso_gdf, gyms_gdf, minutes=ISOCHRONE_WALK_MINS)
plt.show()
"""))

cells.append(md("### 5.1 Unversorgte Gebiete (Lücken in der Erreichbarkeit)\n\nGebiete ausserhalb aller Isochronen gelten als potenzielle Standorte."))

cells.append(code("""\
city_lv95 = city_gdf.to_crs(CRS_LV95)

if len(iso_gdf) > 0:
    # Union aller 10-Min-Isochronen
    iso_10 = iso_gdf[iso_gdf["walk_min"] == ISOCHRONE_WALK_MINS[0]]
    if len(iso_10) > 0:
        covered_union = (iso_10.geometry.union_all()
                         if hasattr(iso_10.geometry, 'union_all')
                         else unary_union(iso_10.geometry))
        city_union = (city_lv95.geometry.union_all()
                      if hasattr(city_lv95.geometry, 'union_all')
                      else unary_union(city_lv95.geometry))
        gaps = city_union.difference(covered_union)
        gap_area_km2 = gaps.area / 1e6
        city_area_km2 = city_union.area / 1e6

        print(f"Unversorgte Fläche (>{ISOCHRONE_WALK_MINS[0]} Min. zu nächstem Fitnesscenter):")
        print(f"  {gap_area_km2:.1f} km² = {gap_area_km2/city_area_km2*100:.1f}% der Stadtfläche")

        # Als GeoDataFrame visualisieren
        gaps_gdf = gpd.GeoDataFrame(geometry=[gaps], crs=CRS_LV95)
        fig, ax = plt.subplots(figsize=FIGSIZE_MAP)
        city_lv95.to_crs(CRS_WEB).plot(ax=ax, color="#F0F4F8", edgecolor="#999", linewidth=1, zorder=2)
        if len(iso_10) > 0:
            iso_10.to_crs(CRS_WEB).plot(ax=ax, color=COLOR_ISO_10, alpha=0.35, zorder=3,
                                         label=f"{ISOCHRONE_WALK_MINS[0]} Min. Einzugsgebiet")
        gaps_gdf.to_crs(CRS_WEB).plot(ax=ax, color=COLOR_POTENTIAL, alpha=0.6, zorder=3,
                                       label="Unversorgtes Gebiet (Potenzial)")
        gyms_gdf.to_crs(CRS_WEB).plot(ax=ax, color=COLOR_GYMS, markersize=50,
                                       alpha=0.9, zorder=5, edgecolor="white")
        _add_basemap(ax, crs=CRS_WEB)
        ax.set_title(f"Versorgungslücken: Gebiete >{ISOCHRONE_WALK_MINS[0]} Min. Gehweg\\nvom nächsten Fitnesscenter",
                     fontsize=13, fontweight="bold")
        handles = [
            mpatches.Patch(color=COLOR_ISO_10, alpha=0.5, label="Versorgt"),
            mpatches.Patch(color=COLOR_POTENTIAL, alpha=0.7, label="Potenzialgebiet"),
            Line2D([0],[0], marker="o", color="w", markerfacecolor=COLOR_GYMS, markersize=9, label="Fitnesscenter"),
        ]
        ax.legend(handles=handles, loc="lower left", fontsize=10)
        ax.set_axis_off()
        plt.tight_layout()
        fig.savefig(OUTPUT_MAPS / "03b_versorgungsluecken.png", dpi=DPI, bbox_inches="tight")
        plt.show()
        print(f"\\n💾 Karte gespeichert: 03b_versorgungsluecken.png")
else:
    print("Keine Isochronen verfügbar – Abschnitt übersprungen")
"""))

# ════════════════════════════════════════════════════════════════════════
# 6. NACHFRAGEANALYSE
# ════════════════════════════════════════════════════════════════════════
cells.append(md("""---
<a id='6'></a>
## 6. Nachfrageanalyse: Bevölkerung & ÖV-Erreichbarkeit

### 6.1 Bevölkerungsdichte pro Quartier
"""))

cells.append(code("""\
# Karte: Bevölkerungsdichte
fig = plot_choropleth(
    quart_proj, column="pop_density",
    title="Bevölkerungsdichte pro Statistisches Quartier\\n(Einwohner/km²)",
    cmap=CMAP_DENSITY,
    legend_label="Einwohner pro km²",
    gyms_gdf=gyms_gdf,
    filename="04_bevoelkerungsdichte.png"
)
plt.show()
"""))

cells.append(md("### 6.2 ÖV-Erreichbarkeit pro Quartier\n\n**Point-in-Polygon**: Anzahl ÖV-Haltestellen pro Quartier, normiert auf km²."))

cells.append(code("""\
quart_scored = compute_oev_score(quart_proj, oev_gdf)

print("ÖV-Erreichbarkeit pro Quartier (Haltestellen/km²):")
print(quart_scored.nlargest(10, "oev_stops_per_km2")[
    ["quartier_name", "oev_stops", "area_km2", "oev_stops_per_km2"]
].round(2).to_string(index=False))

fig = plot_choropleth(
    quart_scored, column="oev_stops_per_km2",
    title="ÖV-Erreichbarkeit pro Quartier\\n(Anzahl Haltestellen/km²)",
    cmap="Blues",
    legend_label="Haltestellen pro km²",
    gyms_gdf=gyms_gdf,
    filename="05_oev_erreichbarkeit.png"
)
plt.show()
"""))

# ════════════════════════════════════════════════════════════════════════
# 7. WETTBEWERBSANALYSE
# ════════════════════════════════════════════════════════════════════════
cells.append(md("""---
<a id='7'></a>
## 7. Wettbewerbsanalyse

Die Wettbewerbsintensität wird als **Anzahl Fitnesscenter pro 10'000 Einwohner** gemessen.
Ein hoher Wert bedeutet starke Konkurrenz → niedriges Potenzial für Neueröffnungen.
"""))

cells.append(code("""\
quart_scored = compute_competition_score(quart_scored, gyms_gdf)

print("Wettbewerbsintensität: Fitnesscenter pro 10'000 Einwohner")
print("-" * 60)
print(quart_scored.nlargest(10, "gyms_per_10k_pop")[
    ["quartier_name", "gyms_count", "population", "gyms_per_10k_pop"]
].round(2).to_string(index=False))

print("\\nQuartiere OHNE Fitnesscenter (höchstes Potenzial):")
no_gyms = quart_scored[quart_scored["gyms_count"] == 0]
print(no_gyms[["quartier_name", "population", "pop_density"]].to_string(index=False))
"""))

cells.append(code("""\
# Karte: Wettbewerbsintensität
fig = plot_choropleth(
    quart_scored, column="gyms_per_10k_pop",
    title="Wettbewerbsintensität: Fitnesscenter pro 10'000 Einwohner",
    cmap="Reds",
    legend_label="Fitnesscenter / 10'000 Einwohner",
    gyms_gdf=gyms_gdf,
    filename="06_wettbewerb.png"
)
plt.show()
"""))

# ════════════════════════════════════════════════════════════════════════
# 8. STANDORT-SCORE-MODELL
# ════════════════════════════════════════════════════════════════════════
cells.append(md(f"""---
<a id='8'></a>
## 8. Standort-Score-Modell

### 8.1 Modellbeschreibung

Der **Standort-Score** kombiniert alle analysierten Faktoren zu einem einzigen,
gewichteten Index pro Quartier (0 = kein Potenzial, 1 = maximales Potenzial).

$$\\text{{Score}} = \\sum_{{i}} w_i \\cdot \\tilde{{x}}_i$$

Wobei $\\tilde{{x}}_i$ die Min-Max-normalisierte Version des Indikators $i$ ist.

**Gewichtungsannahmen** (begründet durch Geomarketing-Theorie):

| Indikator | Gewicht | Begründung |
|-----------|---------|------------|
| Bevölkerungsdichte | **30%** | Primäre Nachfrage: mehr Einwohner = mehr potenzielle Kunden |
| ÖV-Erreichbarkeit | **25%** | Fitnesscenter werden oft mit ÖV besucht (Zürich: hohe ÖV-Nutzung) |
| Wettbewerb (invers) | **30%** | Wenig Konkurrenz = mehr Marktpotenzial |
| Arbeitsplatzdichte | **15%** | Sekundäre Nachfrage: Berufstätige als Zielgruppe |
"""))

cells.append(code("""\
print("Standort-Score-Berechnung:")
print(f"Gewichtungen: {SCORE_WEIGHTS}")
print()

quart_final = compute_location_score(quart_scored, weights=SCORE_WEIGHTS)

print("\\n── Vollständige Score-Übersicht ────────────────────────────────────")
score_overview = quart_final[[
    "quartier_name", "score_pop", "score_oev", "score_comp",
    "location_score", "score_class"
]].sort_values("location_score", ascending=False)
print(score_overview.round(3).to_string(index=False))
"""))

cells.append(code("""\
# Karte: Standort-Score
fig = plot_score_map(quart_final, gyms_gdf, top_n=5)
plt.show()
"""))

cells.append(code("""\
# Balkendiagramm: Top-10 Quartiere
fig, ax = plt.subplots(figsize=(10, 6))
top10 = quart_final.nlargest(10, "location_score")
bars = ax.barh(
    top10["quartier_name"][::-1],
    top10["location_score"][::-1],
    color=plt.cm.RdYlGn(top10["location_score"][::-1] / 1.0),
    edgecolor="white", linewidth=0.5
)
ax.axvline(0.5, color="grey", linestyle="--", lw=1, label="Score = 0.5")
ax.set_xlabel("Standort-Score", fontsize=11)
ax.set_title("Top-10 Quartiere nach Standort-Score", fontsize=13, fontweight="bold")
ax.set_xlim(0, 1)
ax.legend()
plt.tight_layout()
fig.savefig(OUTPUT_FIGS / "07_top10_quartiere.png", dpi=DPI, bbox_inches="tight")
plt.show()
"""))

# ════════════════════════════════════════════════════════════════════════
# 9. MORAN'S I
# ════════════════════════════════════════════════════════════════════════
cells.append(md("""---
<a id='9'></a>
## 9. Räumliche Autokorrelation: Moran's I

### 9.1 Theoretischer Hintergrund

Aus der Vorlesung (Kapitel 7, Gellrich FS2026):

> *Tobler's First Law of Geography: „Everything is related to everything,
> but near things are more related than distant things."*

**Moran's I** ist das wichtigste Mass für räumliche Autokorrelation:

| Wert | Interpretation |
|------|----------------|
| I ≈ +1 | Starke positive Autokorrelation (ähnliche Werte clustern) |
| I ≈ 0  | Zufällige Verteilung (keine Autokorrelation) |
| I ≈ −1 | Negative Autokorrelation (Schachbrettmuster) |

Wir analysieren, ob der **Standort-Score** räumlich geclustert ist –
d.h. ob Quartiere mit hohem Potenzial neben anderen Hochpotenzial-Quartieren liegen.

**Räumliche Gewichtsmatrix**: Queen Contiguity (Quartiere teilen gemeinsame Kanten **oder** Ecken)
– entspricht der Definition aus der Vorlesung.
"""))

cells.append(code("""\
if SPATIAL_STATS:
    moran_result = compute_morans_i(quart_final, variable="location_score")

    if moran_result:
        print("\\n── Globales Moran's I ─────────────────────────────────────────")
        print(f"  Moran's I    : {moran_result['moran_i']:.4f}")
        print(f"  p-Wert       : {moran_result['p_value']:.4f}")
        print(f"  Z-Score      : {moran_result['z_score']:.4f}")
        print()
        if moran_result['p_value'] < 0.05:
            direction = "positiv" if moran_result['moran_i'] > 0 else "negativ"
            print(f"  → Statistisch signifikante {direction}e räumliche Autokorrelation")
            if moran_result['moran_i'] > 0:
                print("  → Quartiere mit hohem Score clustern räumlich zusammen")
        else:
            print("  → Kein signifikanter räumlicher Cluster (Zufallsverteilung)")
else:
    print("libpysal/esda nicht installiert.")
    print("Zum Installieren: pip install libpysal esda")
    moran_result = {}
"""))

cells.append(code("""\
if SPATIAL_STATS and moran_result:
    fig = plot_morans_scatter(moran_result, variable="location_score")
    if fig:
        plt.show()
"""))

cells.append(md("""### 9.2 LISA-Cluster (Lokale räumliche Autokorrelation)

**LISA** (Local Indicators of Spatial Association) identifiziert lokale Cluster:

| Cluster | Bedeutung |
|---------|-----------|
| **HH** (High-High) | Hohes Potenzial, umgeben von hohem Potenzial → **Hot Spot** |
| **LL** (Low-Low) | Niedriges Potenzial, umgeben von niedrigem → **Cold Spot** |
| **LH** / **HL** | Räumliche Ausreisser |
"""))

cells.append(code("""\
if SPATIAL_STATS and moran_result and "gdf_with_lisa" in moran_result:
    lisa_gdf = moran_result["gdf_with_lisa"]
    print("LISA-Cluster (signifikante Quartiere, p < 0.05):")
    sig = lisa_gdf[lisa_gdf["lisa_sig"]]
    if len(sig) > 0:
        print(sig[["quartier_name", "location_score", "lisa_label", "lisa_p"]].to_string(index=False))
    else:
        print("  Keine signifikanten LISA-Cluster gefunden")
"""))

# ════════════════════════════════════════════════════════════════════════
# 10. ERGEBNISSE & EMPFEHLUNGEN
# ════════════════════════════════════════════════════════════════════════
cells.append(md("""---
<a id='10'></a>
## 10. Ergebnisse & Handlungsempfehlungen

### 10.1 Zusammenfassung der Analysen
"""))

cells.append(code("""\
print("=" * 65)
print("  ERGEBNISSE: STANDORTANALYSE FITNESSCENTER ZÜRICH")
print("=" * 65)
print()

total_gyms = len(gyms_gdf)
total_pop  = quart_final["population"].sum()
total_area = quart_final["area_km2"].sum()
gyms_per_10k = total_gyms / total_pop * 10_000

print(f"📊 Ausgangslage:")
print(f"   Fitnesscenter in Zürich    : {total_gyms}")
print(f"   Bevölkerung                : {total_pop:,.0f}")
print(f"   Stadtfläche                : {total_area:.1f} km²")
print(f"   Dichte                     : {gyms_per_10k:.2f} Fitnesscenter / 10'000 Einw.")
print()

top5 = quart_final.nlargest(5, "location_score")
print("🏆 Top-5 Empfehlung: Quartiere mit höchstem Standort-Potenzial:")
print(f"{'#':<4} {'Quartier':<30} {'Score':>6} {'Klasse':<15} {'Fitnesscenter':>14}")
print("-" * 75)
for rank, (_, row) in enumerate(top5.iterrows(), 1):
    name   = row.get("quartier_name", "?")
    score  = row["location_score"]
    cls    = str(row.get("score_class", ""))
    n_gyms = int(row.get("gyms_count", 0))
    print(f"{rank:<4} {name:<30} {score:>6.3f} {cls:<15} {n_gyms:>14}")

print()
bottom5 = quart_final.nsmallest(5, "location_score")
print("🔴 Gesättigte Märkte (niedrigstes Potenzial für Neueinsteiger):")
print(f"{'#':<4} {'Quartier':<30} {'Score':>6} {'Fitnesscenter':>14}")
print("-" * 55)
for rank, (_, row) in enumerate(bottom5.iterrows(), 1):
    name   = row.get("quartier_name", "?")
    score  = row["location_score"]
    n_gyms = int(row.get("gyms_count", 0))
    print(f"{rank:<4} {name:<30} {score:>6.3f} {n_gyms:>14}")
"""))

cells.append(md("""### 10.2 Finale Empfehlungskarte
"""))

cells.append(code("""\
# Finale kombinierte Karte
fig, axes = plt.subplots(1, 2, figsize=(18, 9))

# Links: Score-Karte
ax1 = axes[0]
gdf_web = quart_final.to_crs(CRS_WEB)
gdf_web.plot(column="location_score", ax=ax1, cmap=CMAP_SCORE,
             alpha=0.75, vmin=0, vmax=1, legend=True,
             legend_kwds={"label": "Standort-Score", "orientation": "horizontal",
                          "pad": 0.02, "shrink": 0.7},
             edgecolor="white", linewidth=0.5)

gyms_gdf.to_crs(CRS_WEB).plot(ax=ax1, color=COLOR_GYMS, markersize=40,
                                alpha=0.9, zorder=5, edgecolor="white")
top5_web = quart_final.nlargest(5, "location_score").to_crs(CRS_WEB)
top5_web.boundary.plot(ax=ax1, color="#1D3557", linewidth=2.5, zorder=6)
for _, row in top5_web.iterrows():
    c = row.geometry.centroid
    ax1.annotate(row.get("quartier_name",""), xy=(c.x, c.y),
                fontsize=7.5, fontweight="bold", color="#1D3557",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.75, ec="none"))
_add_basemap(ax1, crs=CRS_WEB)
ax1.set_title("Standort-Score & Top-5 Empfehlungen", fontsize=13, fontweight="bold")
ax1.set_axis_off()

# Rechts: Wettbewerb vs. Nachfrage (Scatterplot)
ax2 = axes[1]
scatter = ax2.scatter(
    quart_final["pop_density"],
    quart_final["gyms_per_10k_pop"],
    c=quart_final["location_score"],
    cmap=CMAP_SCORE, s=quart_final["area_km2"] * 20 + 30,
    alpha=0.8, edgecolor="grey", linewidth=0.3, vmin=0, vmax=1
)
plt.colorbar(scatter, ax=ax2, label="Standort-Score")

# Top-5 beschriften
for _, row in quart_final.nlargest(5, "location_score").iterrows():
    ax2.annotate(
        row.get("quartier_name", ""),
        xy=(row["pop_density"], row["gyms_per_10k_pop"]),
        xytext=(5, 5), textcoords="offset points",
        fontsize=8, fontweight="bold", color="#1D3557"
    )

ax2.axhline(quart_final["gyms_per_10k_pop"].mean(), color="red",
            linestyle="--", lw=1, label="Ø Wettbewerb")
ax2.axvline(quart_final["pop_density"].mean(), color="blue",
            linestyle="--", lw=1, label="Ø Bevölkerungsdichte")
ax2.set_xlabel("Bevölkerungsdichte (Einw./km²)", fontsize=11)
ax2.set_ylabel("Fitnesscenter / 10'000 Einwohner", fontsize=11)
ax2.set_title("Nachfrage vs. Wettbewerb\\n(Kreisgrösse = Quartiersfläche)",
              fontsize=13, fontweight="bold")
ax2.legend(fontsize=9)
ax2.grid(True, alpha=0.3)

plt.suptitle("Standortanalyse Fitnesscenter Zürich – Zusammenfassung",
             fontsize=16, fontweight="bold", y=1.01)
plt.tight_layout()
fig.savefig(OUTPUT_MAPS / "08_finale_empfehlung.png", dpi=DPI, bbox_inches="tight")
plt.show()
print("\\n💾 Finale Empfehlungskarte gespeichert")
"""))

cells.append(md("""### 10.3 Interaktive Karte (Folium)
"""))

cells.append(code("""\
html_path = save_folium_map(
    city_gdf, gyms_gdf, quart_final,
    oev_gdf=oev_gdf,
    iso_gdf=iso_gdf if len(iso_gdf) > 0 else None,
    filename="interactive_map.html"
)
print(f"\\n✅ Interaktive Karte: {html_path}")
print("   → Im Browser öffnen (oder in VS Code mit 'Live Preview')")
"""))

cells.append(md("""### 10.4 Fazit & Limitationen

**Fazit:**

Die räumliche Analyse zeigt, dass das Standortpotenzial für neue Fitnesscenter
in der Stadt Zürich stark variiert. Quartiere mit hoher Bevölkerungsdichte und
guter ÖV-Anbindung, in denen die bestehende Fitmesscenter-Dichte noch gering ist,
bieten das grösste Marktpotenzial.

Die **Moran's I-Analyse** zeigt [wird nach Berechnung ergänzt], ob diese Muster
räumlich geclustert sind oder zufällig verteilt vorliegen.

**Methodische Limitationen:**

1. **OSM-Datenvollständigkeit**: OpenStreetMap-Daten sind nutzergeneriert und
   möglicherweise nicht vollständig (besonders kleine Studios).
2. **Statische Bevölkerungsdaten**: Es werden jährliche Durchschnittswerte verwendet;
   tageszeit- und wochentagsabhängige Schwankungen werden nicht abgebildet.
3. **Isochronen-Vereinfachung**: Die Berechnung basiert auf einem Fussgänger-Netzwerk;
   Velowege und Tram-Routen werden nicht separat modelliert.
4. **Kaufkraft**: Ein zentraler Einflussfaktor (Kaufkraft der Bevölkerung) konnte
   mangels frei verfügbarer Daten auf Quartiersebene nicht einbezogen werden.

**Literatur:**
- Gellrich, M. (FS2026). Einsatz von Geodaten im Marketing. ZHAW.
- Boeing, G. (2017). OSMnx: New Methods for Acquiring, Constructing, Analyzing, and Visualizing Complex Street Networks. *Computers, Environment and Urban Systems*.
- Anselin, L. (2005). Exploring Spatial Data with GeoDa: A Workbook.
- Tobler, W. R. (1970). A Computer Movie Simulating Urban Growth in the Detroit Region.

---
*Notebook erstellt mit Python 3.10 | GeoPandas | osmnx | libpysal | esda | Folium*
"""))

# ════════════════════════════════════════════════════════════════════════
nb["cells"] = cells

with open(OUT, "w", encoding="utf-8") as f:
    nbf.write(nb, f)

print(f"✅ Notebook gespeichert: {OUT}")
print(f"   Zellen: {len(cells)}")
