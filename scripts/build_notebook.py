"""
build_notebook.py – Erstellt .ipynb ohne nbformat (nur stdlib json)
"""
import json
from pathlib import Path

OUT = Path(__file__).parent / "standortanalyse_fitnesscenter_zuerich.ipynb"

def md(src):
    return {"cell_type": "markdown", "id": "md_" + str(hash(src))[:8].replace("-","x"),
            "metadata": {}, "source": src}

def code(src):
    return {"cell_type": "code", "execution_count": None,
            "id": "code_" + str(hash(src))[:8].replace("-","x"),
            "metadata": {}, "outputs": [], "source": src}

cells = []

# ──────────────────────────────────────────────────────────────────────────────
cells.append(md(
"""# 📍 Standortanalyse für Fitnesscenter in der Stadt Zürich

**Kurs:** Einsatz von Geodaten im Marketing (WPM-EGM.XX) – ZHAW School of Management and Law, FS2026
**Autor:** Kai Bleuel
**Abgabe:** 27. Mai 2026
**Betreuer:** Dr. Mario Gellrich

---

## Inhaltsverzeichnis

1. [Einleitung & Forschungsfrage](#1)
2. [Setup & Konfiguration](#2)
3. [Datenbeschaffung](#3) – inkl. **3.5 Geokodierung**
4. [Angebotsanalyse](#4)
5. [Erreichbarkeitsanalyse (Isochronen)](#5)
6. [Nachfrageanalyse](#6) – inkl. **6.3 Kaufkraft-Indikator**
7. [Wettbewerbsanalyse](#7)
8. [Standort-Score-Modell](#8)
9. [Räumliche Autokorrelation & Regression](#9) – inkl. **9.2 Spatial Regression**
10. [Ergebnisse & Handlungsempfehlungen](#10)
"""
))

# ── 1. EINLEITUNG ─────────────────────────────────────────────────────────────
cells.append(md(
"""---
<a id='1'></a>
## 1. Einleitung & Forschungsfrage

### 1.1 Motivation

Der Schweizer Fitnessmarkt wächst: Laut Branchenverband FITNESS SUISSE besuchen über 1.7 Mio. Schweizer regelmässig ein Fitnesscenter. In der Stadt Zürich konkurrieren zahlreiche Anbieter – von Boutique-Studios bis zu grossen Ketten – um eine attraktive, kaufkräftige Kundschaft.

Wie in der Vorlesung gezeigt, gehört die **Standortanalyse** zu den zentralen Anwendungsfeldern des Geomarketings (Gellrich, FS2026):

> *„Where is the best location for my company? Is the planned location viable? Where can I reach the most (potential) customers?"*

Die Standortentscheidung für ein neues Fitnesscenter hängt von mehreren räumlichen Faktoren ab:
- **Nachfrage**: Wo wohnen und arbeiten potenzielle Kunden?
- **Erreichbarkeit**: Wie gut ist ein Standort mit dem öffentlichen Verkehr erreichbar?
- **Wettbewerb**: Wie stark ist die Konkurrenz im Einzugsgebiet?

### 1.2 Forschungsfrage

> **„In welchen Gebieten der Stadt Zürich besteht Potenzial für neue Fitnesscenter-Standorte unter Berücksichtigung von Nachfrage, Erreichbarkeit und bestehender Konkurrenz, und wo ist der Markt bereits gesättigt?"**

### 1.3 Hypothese

Gebiete mit **hoher Bevölkerungs- und Arbeitsplatzdichte**, **guter ÖV-Erreichbarkeit** und **geringer bestehender Fitnesscenter-Dichte** weisen das höchste Standortpotenzial auf.

### 1.4 Methodischer Überblick

| Analyseschritt | Methode | Datenquelle | Vorlesungsbezug |
|----------------|---------|-------------|-----------------|
| Angebotsanalyse | Point-in-Polygon, Dichtekarte | OpenStreetMap | Vektordaten, Point-in-Polygon |
| Erreichbarkeit | Isochronen (Netzwerkanalyse) | OSM via osmnx | Routing & Einzugsgebiete |
| Nachfrage | Choropleth, Bevölkerungsdichte | Stadt Zürich OGD | Attributdaten |
| Wettbewerb | Fitnesscenter / Einwohner | OSM + BFS | Geomarketing-Methoden |
| Standort-Score | Gewichtetes Modell | Alle Layer | Location Intelligence |
| Autokorrelation | Moran's I, LISA | Eigene Berechnung | Spatial Autocorrelation |
| **Geokodierung** | **Nominatim / OSM** | **Adressen** | **Adressdaten geokodieren** |
| **Kaufkraft** | **Choropleth, Scatter** | **BFS Steuerdaten** | **Geomarketing-Indikatoren** |
| **Spatial Regression** | **OLS, Spatial Lag (2SLS)** | **Eigene Berechnung** | **Spatial Regression (Kap. 7)** |
"""
))

# ── 2. SETUP ──────────────────────────────────────────────────────────────────
cells.append(md(
"""---
<a id='2'></a>
## 2. Setup & Konfiguration

### 2.1 Bibliotheken importieren
"""
))

cells.append(code(
"""\
# ── Standard-Bibliotheken ────────────────────────────────────────────────────
import warnings, sys, os, json, requests
from pathlib import Path
warnings.filterwarnings('ignore')

# ── Datenverarbeitung ────────────────────────────────────────────────────────
import numpy as np
import pandas as pd

# ── Geodaten ─────────────────────────────────────────────────────────────────
import geopandas as gpd
from shapely.geometry import Point, Polygon, MultiPoint
from shapely.ops import unary_union
import osmnx as ox

# ── Visualisierung ────────────────────────────────────────────────────────────
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.cm as cm
from matplotlib.lines import Line2D
import contextily as ctx
import folium
from folium.plugins import MarkerCluster

# ── Räumliche Statistik ───────────────────────────────────────────────────────
try:
    from libpysal.weights import Queen
    from esda.moran import Moran, Moran_Local
    SPATIAL_STATS = True
    print("✅ libpysal + esda verfügbar")
except ImportError:
    SPATIAL_STATS = False
    print("⚠️  libpysal/esda nicht verfügbar — pip install libpysal esda")

# ── Projektmodule ─────────────────────────────────────────────────────────────
ROOT = Path.cwd().parent
sys.path.insert(0, str(ROOT))
from config.settings import *
from src.data_loader import *
from src.spatial_analysis import *
from src.visualization import *

print(f"\\n📂 Projektpfad  : {ROOT}")
print(f"⚙️  Primäres CRS  : {CRS_LV95} (LV95)")
print(f"🗺  Analysegebiet : {STUDY_AREA_NAME}")
print("\\n✅ Setup abgeschlossen")\
"""
))

cells.append(md(
"""### 2.2 Koordinatenreferenzsysteme (CRS)

Aus der Vorlesung (Folie Koordinatensysteme, Gellrich FS2026):

| System | EPSG | Typ | Einheit | Verwendung |
|--------|------|-----|---------|------------|
| WGS84 | 4326 | Geographisch | Grad (°) | GPS, OpenStreetMap, APIs |
| **LV95** | **2056** | Projiziert | **Meter** | **Schweizer Standard, alle Distanzanalysen** |
| Web Mercator | 3857 | Projiziert | Meter | Basemaps (Contextily, OSM-Tiles) |

> ⚠️ **Wichtig**: Distanz- und Flächenberechnungen sind nur in projizierten CRS (Meter) korrekt. Alle Analysen werden deshalb in **LV95 (EPSG:2056)** durchgeführt.
"""
))

cells.append(code(
"""\
# Demonstration CRS-Umrechnung: Hauptbahnhof Zürich
hb = gpd.GeoDataFrame({"name": ["Hauptbahnhof Zürich"]},
                       geometry=[Point(8.5404, 47.3782)], crs="EPSG:4326")
hb_lv95 = hb.to_crs("EPSG:2056")

print("CRS-Demonstration: Hauptbahnhof Zürich")
print(f"  WGS84 (EPSG:4326) : lon={hb.geometry[0].x:.4f}°, lat={hb.geometry[0].y:.4f}°")
print(f"  LV95  (EPSG:2056) : E={hb_lv95.geometry[0].x:.0f} m,  N={hb_lv95.geometry[0].y:.0f} m")
print(f"\\n  Umrechnung: gdf.to_crs('EPSG:2056')")\
"""
))

# ── 3. DATENBESCHAFFUNG ───────────────────────────────────────────────────────
cells.append(md(
"""---
<a id='3'></a>
## 3. Datenbeschaffung

### 3.1 Untersuchungsgebiet: Stadtgrenze Zürich

Die Stadtgrenze wird via **osmnx** direkt aus OpenStreetMap geladen — als **Polygon-Vektordaten** im Format GeoJSON. Anschliessend erfolgt die Reprojektion in **LV95 (EPSG:2056)**.
"""
))

cells.append(code(
"""\
print("=" * 60)
print("3.1  UNTERSUCHUNGSGEBIET")
print("=" * 60)

city_gdf = load_city_boundary()

area_km2 = city_gdf.to_crs(CRS_LV95).geometry.area.sum() / 1e6
print(f"\\nStadt Zürich:")
print(f"  CRS          : {city_gdf.crs}")
print(f"  Fläche       : {area_km2:.1f} km²")
print(f"  Geometrietyp : {city_gdf.geometry.iloc[0].geom_type}")
city_gdf.head()\
"""
))

cells.append(code(
"""\
# Karte: Stadtgrenze
fig, ax = plt.subplots(figsize=FIGSIZE_MAP)
city_web = city_gdf.to_crs(CRS_WEB)
city_web.plot(ax=ax, color="#EBF2FA", alpha=0.6,
              edgecolor=COLOR_CITY_EDGE, linewidth=2.5, zorder=2)
add_basemap(ax, crs=CRS_WEB)
ax.set_title("Untersuchungsgebiet: Stadt Zürich", fontsize=14, fontweight="bold", pad=12)
ax.set_axis_off()
plt.tight_layout()
plt.show()
print(f"✅ Stadtgrenze: {area_km2:.1f} km² | CRS: EPSG:{city_gdf.crs.to_epsg()}")\
"""
))

cells.append(md("### 3.2 Fitnesscenter (OpenStreetMap)\n\nOSM-Abfrage via `osmnx.features_from_place()` mit Tags `leisure=fitness_centre` und `amenity=gym`. Polygone werden automatisch zu Punkten (Zentroide) konvertiert."))

cells.append(code(
"""\
print("=" * 60)
print("3.2  FITNESSCENTER (OpenStreetMap)")
print("=" * 60)

gyms_gdf = load_fitness_centers(city_gdf)

print(f"\\nAnzahl Fitnesscenter: {len(gyms_gdf)}")
print(f"CRS: {gyms_gdf.crs}")
print(f"Spalten: {list(gyms_gdf.columns)}")
print("\\nErste Einträge:")
display(gyms_gdf.head(10))\
"""
))

cells.append(code(
"""\
# GeoJSON-Format demonstrieren (Vorlesungsinhalt: GIS-Datenformate)
geojson_path = DATA_PROC / "fitness_centers.geojson"
with open(geojson_path) as f:
    gj = json.load(f)

print("GeoJSON-Struktur (Auszug):")
print(f"  type          : {gj['type']}")
print(f"  features      : {len(gj['features'])}")
sample = gj['features'][0] if gj['features'] else {}
print(f"  geometry.type : {sample.get('geometry',{}).get('type','?')}")
print(f"  Koordinaten   : {sample.get('geometry',{}).get('coordinates','?')}")
print(f"  properties    : {list(sample.get('properties',{}).keys())}")\
"""
))

cells.append(md("### 3.3 ÖV-Haltestellen (OpenStreetMap)"))

cells.append(code(
"""\
print("=" * 60)
print("3.3  ÖV-HALTESTELLEN")
print("=" * 60)

oev_gdf = load_oev_stops(city_gdf)
print(f"Anzahl Haltestellen: {len(oev_gdf)}")
if "oev_type" in oev_gdf.columns:
    print("\\nNach Typ:")
    print(oev_gdf["oev_type"].value_counts().to_string())\
"""
))

cells.append(md("### 3.4 Statistische Quartiere & Bevölkerungsdaten\n\nDie Stadtbevölkerung ist in **34 statistische Quartiere** unterteilt. Die Geodaten kommen vom Stadt Zürich Open Data Portal (WFS GeoJSON), die Bevölkerungszahlen aus dem OGD-CSV."))

cells.append(code(
"""\
print("=" * 60)
print("3.4  QUARTIERE & BEVÖLKERUNG")
print("=" * 60)

quarters_gdf  = load_statistical_quarters()
population_df = load_population_data()
quarters_pop  = merge_quarters_population(quarters_gdf, population_df)

print(f"\\nQuartiere: {len(quarters_pop)}")
print(f"Bevölkerung total: {quarters_pop['population'].sum():,.0f}")
print(f"Ø Dichte: {quarters_pop['pop_density'].mean():.0f} Einw./km²")
print("\\nTop-5 bevölkerungsdichteste Quartiere:")
print(quarters_pop.nlargest(5, "pop_density")[
    ["quartier_name","population","area_km2","pop_density"]
].round(1).to_string(index=False))\
"""
))

# ── 3.5 GEOKODIERUNG ─────────────────────────────────────────────────────────
cells.append(md(
"""### 3.5 Geokodierung von Adressen

**Lernziel (Modulbeschreibung):** *«können Adressdaten geokodieren»*

**Geokodierung** konvertiert Textadressen in geographische Koordinaten (Breitengrad/Längengrad).
Hier nutzen wir **Nominatim** (OpenStreetMap-Geocoder) via `geopy` mit Rate-Limiter (min. 1.1 s/Anfrage gemäss OSM-Policy).

**Anwendungsfall**: Bekannte Fitnesscenter-Adressen → Koordinaten → Vergleich mit OSM-Daten
"""
))

cells.append(code(
"""\
# Modulneuladung (nötig wenn Kernel nach Code-Änderungen nicht neu gestartet wurde)
import importlib, src.data_loader as _dl
importlib.reload(_dl)
from src.data_loader import geocode_addresses

# Beispieladressen bekannter Zürcher Fitnesscenter für Geokodierung-Demo
sample_addresses = [
    "Hardstrasse 235, Zürich",      # McFit Zürich West
    "Sihlquai 268, Zürich",         # Fitnesspark HB
    "Badenerstrasse 380, Zürich",   # Holmes Place
    "Lagerstrasse 33, Zürich",      # CLEVER FIT
    "Weinbergstrasse 70, Zürich",   # Migros Fitnesspark Zürich Weinberg
]

print("Geokodierung via Nominatim (OpenStreetMap)...")
print("(Ergebnis wird gecacht in data/processed/geocoded_addresses.geojson)")
geocoded_gdf = geocode_addresses(sample_addresses, city="Schweiz")

print(f"\\nErfolgreich geokodiert: {len(geocoded_gdf)}/{len(sample_addresses)} Adressen")
if len(geocoded_gdf) > 0:
    display_cols = ["address", "lat", "lon"] if "lat" in geocoded_gdf.columns else ["address"]
    print(geocoded_gdf[display_cols].to_string(index=False))\
"""
))

cells.append(code(
"""\
if len(geocoded_gdf) > 0:
    fig, ax = plt.subplots(1, 1, figsize=(10, 8))
    base = city_gdf.to_crs(CRS_WEB)
    base.plot(ax=ax, color="#F0F0F0", edgecolor="#CCCCCC", linewidth=0.5, alpha=0.7)
    geocoded_web = geocoded_gdf.to_crs(CRS_WEB)
    geocoded_web.plot(ax=ax, color="#E63946", markersize=120, zorder=5,
                      edgecolor="white", linewidth=1.5, marker="*", label="Geokodierte Adressen")
    for _, row in geocoded_web.iterrows():
        ax.annotate(
            row.get("address", "").split(",")[0],
            xy=(row.geometry.x, row.geometry.y),
            xytext=(8, 8), textcoords="offset points",
            fontsize=8, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.8, ec="none")
        )
    add_basemap(ax, crs=CRS_WEB)
    ax.set_title("Geokodierte Fitnesscenter-Adressen in Zürich\\n(via Nominatim / OpenStreetMap)",
                 fontsize=13, fontweight="bold")
    ax.legend(fontsize=10)
    ax.set_axis_off()
    plt.tight_layout()
    fig.savefig(OUTPUT_FIGS / "01b_geokodierung.png", dpi=DPI, bbox_inches="tight")
    plt.show()
    print("\\n💾 Gespeichert: 01b_geokodierung.png")
else:
    print("Keine Adressen geokodiert (ggf. kein Internetzugang)")\
"""
))

# ── 4. ANGEBOTSANALYSE ────────────────────────────────────────────────────────
cells.append(md(
"""---
<a id='4'></a>
## 4. Angebotsanalyse: Bestehende Fitnesscenter

### 4.1 Karte: Fitnesscenter & ÖV-Haltestellen
"""
))

cells.append(code(
"""\
fig = plot_city_with_gyms(
    city_gdf, gyms_gdf, oev_gdf=oev_gdf,
    title=f"Fitnesscenter in der Stadt Zürich (n={len(gyms_gdf)})"
)
plt.show()\
"""
))

cells.append(md("### 4.2 Point-in-Polygon: Fitnesscenter pro Quartier\n\nAus der Vorlesung: *Point-in-Polygon-Analyse* — Zuordnung von Punkten zu Polygonen via räumlichem Join (`gpd.sjoin`)."))

cells.append(code(
"""\
# Point-in-Polygon (Vorlesungsinhalt)
gyms_proj  = gyms_gdf.to_crs(CRS_LV95)
quart_proj = quarters_pop.to_crs(CRS_LV95)

joined = gpd.sjoin(gyms_proj, quart_proj, how="left", predicate="within")
gyms_per_q = joined.groupby("index_right").size().rename("gyms_count")

quart_proj["gyms_count"]   = quart_proj.index.map(gyms_per_q).fillna(0)
quart_proj["gyms_per_km2"] = quart_proj["gyms_count"] / quart_proj["area_km2"]
quart_proj["gyms_per_10k_pop"] = np.where(
    quart_proj["population"] > 0,
    quart_proj["gyms_count"] / quart_proj["population"] * 10000, 0
)

print("Fitnesscenter pro Quartier (Top 10 nach Anzahl):")
print(quart_proj.nlargest(10, "gyms_count")[
    ["quartier_name","gyms_count","gyms_per_km2","gyms_per_10k_pop","population"]
].round(2).to_string(index=False))
print(f"\\nQuartiere OHNE Fitnesscenter: {(quart_proj['gyms_count']==0).sum()}")\
"""
))

cells.append(code(
"""\
fig = plot_choropleth(
    quart_proj, column="gyms_per_km2",
    title="Angebotsdichte: Fitnesscenter pro km² (nach Quartier)",
    cmap="YlOrRd", legend_label="Fitnesscenter pro km²",
    gyms_gdf=gyms_gdf, filename="02_angebotsdichte.png"
)
plt.show()\
"""
))

# ── 5. ERREICHBARKEIT ─────────────────────────────────────────────────────────
cells.append(md(
"""---
<a id='5'></a>
## 5. Erreichbarkeitsanalyse: Isochronen (Einzugsgebiete)

**Isochronen** zeigen, welche Flächen innerhalb einer bestimmten Gehzeit erreichbar sind.
Dies entspricht der aus der Vorlesung bekannten **Einzugsgebietsanalyse** (Gellrich, FS2026: *Routing and calculation of isochrones*).

**Methodik:**
1. Fussgänger-Strassennetz Zürich via `osmnx.graph_from_place()` herunterladen
2. Für jeden Fitnesscenter-Standort den nächstgelegenen Netzwerk-Knoten bestimmen
3. Erreichbare Knoten innerhalb der Zeitgrenze via `networkx.ego_graph()` berechnen
   → Kanten mit Reisezeit gewichtet: $t = \\frac{d}{v}$ (Distanz / Gehgeschwindigkeit)
4. Konvexe Hülle der erreichbaren Knoten = **Isochrone**

*Annahme: Gehgeschwindigkeit = 4.5 km/h*
"""
))

cells.append(code(
"""\
print(f"Isochronen-Berechnung: {ISOCHRONE_WALK_MINS} Minuten, v = {WALK_SPEED_KMH} km/h")
print("(Netzwerk-Download kann 1–2 Minuten dauern …)")

iso_gdf = compute_isochrones(gyms_gdf, walk_mins=ISOCHRONE_WALK_MINS)

if len(iso_gdf) > 0:
    print("\\nIsochronen-Ergebnis:")
    print(iso_gdf.groupby("walk_min").size().rename("Anzahl Isochronen").to_string())

    city_lv95  = city_gdf.to_crs(CRS_LV95)
    city_union = unary_union(city_lv95.geometry)

    for mins in ISOCHRONE_WALK_MINS:
        sub = iso_gdf[iso_gdf["walk_min"] == mins]
        if len(sub) > 0:
            cov = unary_union(sub.geometry).intersection(city_union)
            pct = cov.area / city_union.area * 100
            print(f"  Deckungsgrad {mins} Min.: {pct:.1f}% der Stadtfläche")\
"""
))

cells.append(code(
"""\
fig = plot_isochrones(city_gdf, iso_gdf, gyms_gdf, minutes=ISOCHRONE_WALK_MINS)
plt.show()\
"""
))

cells.append(md("### 5.1 Versorgungslücken (unversorgte Gebiete)"))

cells.append(code(
"""\
city_lv95 = city_gdf.to_crs(CRS_LV95)
city_union = unary_union(city_lv95.geometry)

if len(iso_gdf) > 0:
    iso_10 = iso_gdf[iso_gdf["walk_min"] == ISOCHRONE_WALK_MINS[0]]
    if len(iso_10) > 0:
        covered = unary_union(iso_10.geometry)
        gaps    = city_union.difference(covered)
        gap_km2 = gaps.area / 1e6
        print(f"Fläche ohne 10-Min-Einzugsgebiet: {gap_km2:.1f} km² ({gap_km2/city_union.area*1e6*100:.1f}%)")

        gaps_gdf = gpd.GeoDataFrame(geometry=[gaps], crs=CRS_LV95)
        fig, ax  = plt.subplots(figsize=FIGSIZE_MAP)
        city_lv95.to_crs(CRS_WEB).plot(ax=ax, color="#F0F4F8", edgecolor="#999", lw=1, zorder=2)
        iso_10.to_crs(CRS_WEB).plot(ax=ax, color=COLOR_ISO_10, alpha=0.35, zorder=3, label="Versorgt (10 Min.)")
        gaps_gdf.to_crs(CRS_WEB).plot(ax=ax, color=COLOR_POTENTIAL, alpha=0.65, zorder=4, label="Potenzialgebiet")
        gyms_gdf.to_crs(CRS_WEB).plot(ax=ax, color=COLOR_GYMS, markersize=50, alpha=0.9, zorder=5, edgecolor="white")
        add_basemap(ax, crs=CRS_WEB)
        handles = [mpatches.Patch(color=COLOR_ISO_10, alpha=0.5, label="Versorgt"),
                   mpatches.Patch(color=COLOR_POTENTIAL, alpha=0.7, label="Potenzialgebiet"),
                   Line2D([0],[0],marker="o",color="w",markerfacecolor=COLOR_GYMS,markersize=9,label="Fitnesscenter")]
        ax.legend(handles=handles, loc="lower left", fontsize=10)
        ax.set_title(f"Versorgungslücken: >{ISOCHRONE_WALK_MINS[0]} Min. Gehweg\\nvom nächsten Fitnesscenter",
                     fontsize=13, fontweight="bold")
        ax.set_axis_off()
        plt.tight_layout()
        fig.savefig(OUTPUT_MAPS / "03b_versorgungsluecken.png", dpi=DPI, bbox_inches="tight")
        plt.show()
else:
    print("Keine Isochronen — Abschnitt übersprungen")\
"""
))

# ── 6. NACHFRAGEANALYSE ───────────────────────────────────────────────────────
cells.append(md(
"""---
<a id='6'></a>
## 6. Nachfrageanalyse: Bevölkerung & ÖV-Erreichbarkeit

### 6.1 Bevölkerungsdichte (Choropleth-Karte)
"""
))

cells.append(code(
"""\
fig = plot_choropleth(
    quart_proj, column="pop_density",
    title="Bevölkerungsdichte pro Quartier (Einwohner/km²)",
    cmap=CMAP_DENSITY, legend_label="Einwohner pro km²",
    gyms_gdf=gyms_gdf, filename="04_bevoelkerungsdichte.png"
)
plt.show()\
"""
))

cells.append(md("### 6.2 ÖV-Erreichbarkeit pro Quartier\n\n**Point-in-Polygon**: Anzahl ÖV-Haltestellen je Quartier, normiert auf km²."))

cells.append(code(
"""\
quart_scored = compute_oev_score(quart_proj, oev_gdf)

print("ÖV-Erreichbarkeit (Haltestellen/km²) — Top 10:")
print(quart_scored.nlargest(10, "oev_stops_per_km2")[
    ["quartier_name","oev_stops","area_km2","oev_stops_per_km2"]
].round(2).to_string(index=False))

fig = plot_choropleth(
    quart_scored, column="oev_stops_per_km2",
    title="ÖV-Erreichbarkeit pro Quartier (Haltestellen/km²)",
    cmap="Blues", legend_label="Haltestellen pro km²",
    gyms_gdf=gyms_gdf, filename="05_oev_erreichbarkeit.png"
)
plt.show()\
"""
))

# ── 6.3 KAUFKRAFT ────────────────────────────────────────────────────────────
cells.append(md(
"""### 6.3 Kaufkraft-Indikator (Steuerbares Einkommen)

**Lernziel (Modulbeschreibung):** *«kennen wichtige Datenquellen für soziodemographische Merkmale»*

Das **steuerbare Einkommen** (BFS-Statistik) dient als Kaufkraft-Proxy:
- Quelle: Bundesamt für Statistik (BFS), Steuerstatistik, Gemeinde Zürich (Nr. 261)
- Stadtdurchschnitt 2022: **CHF 40'811** (steuerbares Einkommen pro Steuerpflichtigen)
- Quartiersdaten: socioökonomische Proxys basierend auf bekannten Zürcher Geographien

**Relevanz für Standortanalyse**: Höhere Kaufkraft → höhere Zahlungsbereitschaft für Premium-Fitnessangebote
"""
))

cells.append(code(
"""\
income_df = load_income_by_quarter()
quart_scored = merge_quarters_income(quart_scored, income_df)

# Normierter Kaufkraft-Index (0-1) für Score-Modell
inc_min = quart_scored["income_proxy"].min()
inc_max = quart_scored["income_proxy"].max()
quart_scored["income_index"] = (quart_scored["income_proxy"] - inc_min) / (inc_max - inc_min)

print("Kaufkraft-Proxy nach Quartier (Top-10):")
print(quart_scored.nlargest(10, "income_proxy")[
    ["quartier_name", "income_proxy", "income_index"]
].round(0).to_string(index=False))
print(f"\\nStadt-Durchschnitt: CHF {quart_scored['income_proxy'].mean():,.0f}")
print(f"Minimum: CHF {inc_min:,.0f} | Maximum: CHF {inc_max:,.0f}")

fig = plot_choropleth(
    quart_scored, column="income_proxy",
    title="Kaufkraft-Proxy: Steuerbares Einkommen pro Quartier (CHF/Jahr)",
    cmap="YlGn", legend_label="Steuerbares Einkommen (CHF)",
    gyms_gdf=gyms_gdf, filename="05b_kaufkraft.png"
)
plt.show()\
"""
))

# ── 7. WETTBEWERBSANALYSE ─────────────────────────────────────────────────────
cells.append(md(
"""---
<a id='7'></a>
## 7. Wettbewerbsanalyse

Wettbewerbsintensität = **Anzahl Fitnesscenter pro 10'000 Einwohner** pro Quartier.
Niedriger Wert → wenig Konkurrenz → hohes Marktpotenzial.
"""
))

cells.append(code(
"""\
quart_scored = compute_competition_score(quart_scored, gyms_gdf)

print("Wettbewerbsintensität (FC / 10'000 Einw.) — Top 10:")
print(quart_scored.nlargest(10, "gyms_per_10k_pop")[
    ["quartier_name","gyms_count","population","gyms_per_10k_pop"]
].round(2).to_string(index=False))

print(f"\\nQuartiere ohne Fitnesscenter ({(quart_scored['gyms_count']==0).sum()} Stück):")
no_g = quart_scored[quart_scored["gyms_count"]==0]
print(no_g[["quartier_name","population","pop_density"]].to_string(index=False))\
"""
))

cells.append(code(
"""\
fig = plot_choropleth(
    quart_scored, column="gyms_per_10k_pop",
    title="Wettbewerbsintensität: Fitnesscenter pro 10'000 Einwohner",
    cmap="Reds", legend_label="Fitnesscenter / 10'000 Einwohner",
    gyms_gdf=gyms_gdf, filename="06_wettbewerb.png"
)
plt.show()\
"""
))

# ── 8. STANDORT-SCORE ─────────────────────────────────────────────────────────
cells.append(md(
"""---
<a id='8'></a>
## 8. Standort-Score-Modell

### 8.1 Modellbeschreibung

Der **Standort-Score** fasst alle Indikatoren zu einem einzigen gewichteten Index zusammen:

$$\\text{Score} = 0.30 \\cdot \\tilde{x}_{\\text{Bevölkerung}} + 0.25 \\cdot \\tilde{x}_{\\text{ÖV}} + 0.25 \\cdot \\tilde{x}_{\\text{Wettbewerb (inv.)}} + 0.10 \\cdot \\tilde{x}_{\\text{Arbeit}} + 0.10 \\cdot \\tilde{x}_{\\text{Kaufkraft}}$$

Alle Indikatoren $\\tilde{x}_i$ sind **Min-Max-normalisiert** (0–1).

| Indikator | Gewicht | Begründung |
|-----------|---------|------------|
| Bevölkerungsdichte | **30%** | Primäre Nachfrage (Wohnbevölkerung) |
| ÖV-Erreichbarkeit | **25%** | Zürich: hohe ÖV-Nutzung, Erreichbarkeit entscheidend |
| Wettbewerb (invers) | **25%** | Wenig Konkurrenz = mehr Marktchance |
| Kaufkraft (steuerbares Einkommen) | **10%** | Zahlungsbereitschaft für Premium-Angebote (BFS) |
| Arbeitsplatzdichte | **10%** | Sekundäre Nachfrage (Berufspendler als Zielgruppe) |
"""
))

cells.append(code(
"""\
print(f"Gewichtungen: {SCORE_WEIGHTS}")

quart_final = compute_location_score(quart_scored, weights=SCORE_WEIGHTS)

print("\\n── Score-Übersicht ─────────────────────────────────────────────────")
show_cols = ["quartier_name","score_pop","score_oev","score_comp","location_score","score_class"]
if "score_income" in quart_final.columns:
    show_cols = ["quartier_name","score_pop","score_oev","score_comp","score_income","location_score","score_class"]
print(quart_final[show_cols
].sort_values("location_score", ascending=False).round(3).to_string(index=False))\
"""
))

cells.append(code(
"""\
fig = plot_score_map(quart_final, gyms_gdf, top_n=5)
plt.show()\
"""
))

cells.append(code(
"""\
# Balkendiagramm Top-10
fig, ax = plt.subplots(figsize=(10, 6))
top10 = quart_final.nlargest(10, "location_score")
colors = plt.cm.RdYlGn(top10["location_score"] / 1.0)
ax.barh(top10["quartier_name"][::-1], top10["location_score"][::-1],
        color=colors[::-1], edgecolor="white", linewidth=0.5)
ax.axvline(0.5, color="grey", linestyle="--", lw=1, label="Score = 0.5")
ax.set_xlabel("Standort-Score (0–1)", fontsize=11)
ax.set_title("Top-10 Quartiere nach Standort-Potenzial", fontsize=13, fontweight="bold")
ax.set_xlim(0, 1)
ax.legend()
plt.tight_layout()
fig.savefig(OUTPUT_FIGS / "07_top10_score.png", dpi=DPI, bbox_inches="tight")
plt.show()\
"""
))


cells.append(code(
"""# Ergebnisse als GeoJSON speichern (fuer QGIS-Visualisierung)
save_cols = [c for c in [
    "quartier_name", "quartier_nr", "population", "area_km2",
    "pop_density", "gyms_count", "gyms_per_km2", "gyms_per_10k_pop",
    "oev_stops", "oev_stops_per_km2", "income_proxy", "income_index",
    "competition_count", "score_pop", "score_oev", "score_comp",
    "score_income", "location_score", "score_class", "geometry"
] if c in quart_final.columns]

export_gdf = quart_final[save_cols].to_crs("EPSG:4326")
export_path = DATA_PROC / "quartiere_scored.geojson"
export_gdf.to_file(export_path, driver="GeoJSON")
print(f"Gespeichert: {export_path}")
print(f"Spalten: {[c for c in save_cols if c != 'geometry']}")"""
))

# ── 9. MORAN'S I ─────────────────────────────────────────────────────────────
cells.append(md(
"""---
<a id='9'></a>
## 9. Räumliche Autokorrelation: Moran's I

### 9.1 Theoretischer Hintergrund (Vorlesung Kapitel 7)

> *Tobler's First Law of Geography: „Everything is related to everything, but near things are more related than distant things."* (Tobler, 1970)

**Moran's I** misst globale räumliche Autokorrelation:

| Wert | Interpretation |
|------|----------------|
| I ≈ +1 | Positive Autokorrelation – ähnliche Werte clustern |
| I ≈ 0  | Keine räumliche Struktur |
| I ≈ −1 | Negative Autokorrelation – Schachbrettmuster |

**Räumliche Gewichtsmatrix**: Queen Contiguity (Quartiere mit gemeinsamer Kante **oder** Ecke gelten als Nachbarn) — row-standardisiert (Vorlesung Folie 9).

Wir testen: Ist der **Standort-Score** räumlich geclustert?
"""
))

cells.append(code(
"""\
if SPATIAL_STATS:
    moran_result = compute_morans_i(quart_final, variable="location_score")
    if moran_result:
        print("\\n── Globales Moran's I ─────────────────────────────────────")
        print(f"  Moran's I  : {moran_result['moran_i']:.4f}")
        print(f"  p-Wert     : {moran_result['p_value']:.4f}")
        print(f"  Z-Score    : {moran_result['z_score']:.4f}")
        sig = "signifikant" if moran_result["p_value"] < 0.05 else "NICHT signifikant"
        print(f"  → Ergebnis : {sig} (α = 0.05)")
else:
    print("libpysal/esda fehlen — Moran's I übersprungen")
    moran_result = {}\
"""
))

cells.append(code(
"""\
if SPATIAL_STATS and moran_result:
    fig = plot_morans_scatter(moran_result, variable="location_score")
    if fig:
        plt.show()\
"""
))

cells.append(code(
"""\
if SPATIAL_STATS and moran_result and "gdf_with_lisa" in moran_result:
    lisa_gdf = moran_result["gdf_with_lisa"]
    sig_lisa = lisa_gdf[lisa_gdf["lisa_sig"]]
    print(f"Signifikante LISA-Cluster (p < 0.05): {len(sig_lisa)}")
    if len(sig_lisa) > 0:
        print(sig_lisa[["quartier_name","location_score","lisa_label","lisa_p"]].to_string(index=False))\
"""
))

# ── 9.2 SPATIAL REGRESSION ───────────────────────────────────────────────────
cells.append(md(
"""---
<a id='92'></a>
### 9.2 Räumliche Regression (Spatial Lag Model)

**Lernziel (Modulbeschreibung):** *«können einfache räumliche Regressionsmodelle aufstellen und interpretieren»*

#### Methodik

1. **OLS-Regression** (Benchmark): $y = X\\beta + \\varepsilon$ — wird mit numpy implementiert (kein scikit-learn nötig).
2. **Moran's I der OLS-Residuen**: Falls $I > 0$ und $p < 0.05$ → OLS ist verzerrt (räumliche Abhängigkeit ignoriert).
3. **Spatial Lag Model** (2SLS): $y = \\rho Wy + X\\beta + \\varepsilon$
   - $\\rho$ = räumlicher Autokorrelationsparameter
   - Schätzung via Two-Stage Least Squares (W·X als Instrument für Wy)

**Abhängige Variable:** Anzahl Fitnesscenter pro km² (`gyms_per_km2`)
**Unabhängige Variablen:** Bevölkerungsdichte, ÖV-Haltestellen/km², Kaufkraft-Index
"""
))

cells.append(code(
"""\
if SPATIAL_STATS:
    reg_result = compute_spatial_regression(
        quart_final,
        y_var="gyms_per_km2",
        x_vars=["pop_density", "oev_stops_per_km2", "income_index"]
    )
    if reg_result:
        coef_names = ["Konstante", "Bev.dichte", "OEV-Stops/km2", "Kaufkraft-Index"]

        print("\\n-- OLS-Zusammenfassung (bereits oben ausgegeben):")
        print(f"  R2        : {reg_result.get('ols_r2', float('nan')):.4f}")
        print(f"  Adj. R2   : {reg_result.get('ols_adj_r2', float('nan')):.4f}")

        mi_i = reg_result.get("moran_resid_i")
        mi_p = reg_result.get("moran_resid_p")
        if mi_i is not None and mi_p is not None:
            print(f"\\n-- Moran's I der OLS-Residuen: I={mi_i:.4f}, p={mi_p:.4f}")
            if mi_p < 0.05:
                print("  -> Signifikante raeumliche Autokorrelation -> Spatial Lag empfohlen")
            else:
                print("  -> Kein Hinweis auf raeumliche Autokorrelation in Residuen")
        else:
            print("\\n-- Moran-Test: nicht verfuegbar")

        if "lag_rho" in reg_result and "lag_r2" in reg_result:
            print(f"\\n-- Spatial Lag Model (2SLS):")
            print(f"  rho (spatial lag): {reg_result['lag_rho']:+.4f}")
            print(f"  Pseudo-R2        : {reg_result['lag_r2']:.4f}")
            lag_coef = reg_result.get("lag_coef", [])
            for name, coef in zip(coef_names, lag_coef[:-1]):
                print(f"    {name:<25}: {coef:+.4f}")
        else:
            print("\\n-- Spatial Lag: nicht berechnet (Gewichtsmatrix nicht verfuegbar)")
else:
    print("libpysal fehlt -- Spatial Regression uebersprungen")
    reg_result = {}\
"""
))

cells.append(code(
"""\
if SPATIAL_STATS and reg_result:
    fig = plot_regression_diagnostics(reg_result, quart_final)
    if fig:
        plt.show()\
"""
))

# -- 10. ERGEBNISSE -----------------------------------------------------------
cells.append(md(
"""---
<a id='10'></a>
## 10. Ergebnisse & Handlungsempfehlungen

### 10.1 Zusammenfassung
"""
))

cells.append(code(
"""\
print("=" * 65)
print("  ERGEBNISSE: STANDORTANALYSE FITNESSCENTER ZUERICH")
print("=" * 65)

total_gyms = len(gyms_gdf)
total_pop  = quart_final["population"].sum()
city_area  = quart_final["area_km2"].sum()
density    = total_gyms / total_pop * 10_000

print(f"\\nAusgangslage Stadt Zuerich:")
print(f"   Fitnesscenter     : {total_gyms}")
print(f"   Bevoelkerung      : {total_pop:,.0f}")
print(f"   Flaeche           : {city_area:.1f} km2")
print(f"   FC-Dichte         : {density:.2f} pro 10'000 Einw.")

print("\\nTop-5 Potenzialquartiere:")
top5 = quart_final.nlargest(5, "location_score")
print(f"{'#':<4}{'Quartier':<30}{'Score':>7}{'Klasse':<15}{'Fitnesscenter':>14}")
print("-" * 72)
for i, (_, r) in enumerate(top5.iterrows(), 1):
    print(f"{i:<4}{r.get('quartier_name','?'):<30}{r['location_score']:>7.3f}{str(r.get('score_class',''))+' ':<15}{int(r.get('gyms_count',0)):>14}")

print("\\nTop-5 gesaettigte Maerkte (hohe Konkurrenz):")
bot5 = quart_final.nlargest(5, "gyms_per_10k_pop")
print(f"{'#':<4}{'Quartier':<30}{'FC/10k':>7}")
for i, (_, r) in enumerate(bot5.iterrows(), 1):
    print(f"{i:<4}{r.get('quartier_name','?'):<30}{r.get('gyms_per_10k_pop',0):>7.2f}")\
"""
))

cells.append(code(
"""\
# Finale Doppelkarte
fig, axes = plt.subplots(1, 2, figsize=(18, 9))

# Links: Score-Karte
ax1 = axes[0]
gdf_web = quart_final.to_crs(CRS_WEB)
gdf_web.plot(column="location_score", ax=ax1, cmap=CMAP_SCORE, alpha=0.75,
             vmin=0, vmax=1, legend=True,
             legend_kwds={"label":"Standort-Score","orientation":"horizontal","pad":0.02,"shrink":0.65},
             edgecolor="white", linewidth=0.5)
gdf_web.boundary.plot(ax=ax1, color="#AAAAAA", linewidth=0.3)
gyms_gdf.to_crs(CRS_WEB).plot(ax=ax1, color=COLOR_GYMS, markersize=35,
                                alpha=0.9, zorder=5, edgecolor="white")
top5_web = quart_final.nlargest(5,"location_score").to_crs(CRS_WEB)
top5_web.boundary.plot(ax=ax1, color="#1D3557", linewidth=2.5, zorder=6)
for _, row in top5_web.iterrows():
    c = row.geometry.centroid
    ax1.annotate(row.get("quartier_name",""), xy=(c.x,c.y), fontsize=7.5,
                 fontweight="bold", color="#1D3557",
                 bbox=dict(boxstyle="round,pad=0.2",fc="white",alpha=0.75,ec="none"))
add_basemap(ax1, crs=CRS_WEB)
ax1.set_title("Standort-Score & Top-5 Empfehlungen", fontsize=13, fontweight="bold")
ax1.set_axis_off()

# Rechts: Scatterplot Nachfrage vs. Wettbewerb
ax2 = axes[1]
sc = ax2.scatter(quart_final["pop_density"], quart_final["gyms_per_10k_pop"],
                 c=quart_final["location_score"], cmap=CMAP_SCORE,
                 s=quart_final["area_km2"]*25+30, alpha=0.8,
                 edgecolor="grey", linewidth=0.3, vmin=0, vmax=1)
plt.colorbar(sc, ax=ax2, label="Standort-Score")
for _, r in quart_final.nlargest(5,"location_score").iterrows():
    ax2.annotate(r.get("quartier_name",""),
                 xy=(r["pop_density"],r["gyms_per_10k_pop"]),
                 xytext=(5,5), textcoords="offset points",
                 fontsize=8, fontweight="bold", color="#1D3557")
ax2.axhline(quart_final["gyms_per_10k_pop"].mean(), color="red", ls="--", lw=1, label="Durchschnitt Wettbewerb")
ax2.axvline(quart_final["pop_density"].mean(), color="blue", ls="--", lw=1, label="Durchschnitt Bevoelkerungsdichte")
ax2.set_xlabel("Bevoelkerungsdichte (Einw./km2)", fontsize=11)
ax2.set_ylabel("Fitnesscenter / 10'000 Einwohner", fontsize=11)
ax2.set_title("Nachfrage vs. Wettbewerb\\n(Kreisgroesse = Quartiersflaeche)", fontsize=13, fontweight="bold")
ax2.legend(fontsize=9); ax2.grid(True, alpha=0.3)

plt.suptitle("Standortanalyse Fitnesscenter Zuerich - Zusammenfassung",
             fontsize=16, fontweight="bold", y=1.01)
plt.tight_layout()
fig.savefig(OUTPUT_MAPS/"08_finale_empfehlung.png", dpi=DPI, bbox_inches="tight")
plt.show()
print("\\nGespeichert: 08_finale_empfehlung.png")\
"""
))

cells.append(code(
"""\
html_path = save_folium_map(
    city_gdf, gyms_gdf, quart_final,
    oev_gdf=oev_gdf,
    iso_gdf=iso_gdf if len(iso_gdf) > 0 else None,
)
print(f"Interaktive Karte: {html_path}")\
"""
))

cells.append(md(
"""### 10.2 Handlungsempfehlungen

Basierend auf der Standort-Score-Analyse lassen sich folgende Empfehlungen ableiten:

**Empfohlene Standortquartiere** (hoher Score):
- Hohe Bevoelkerungsdichte + gute OEV-Anbindung + geringe Konkurrenz = ideale Kombination
- Diese Quartiere werden im Score-Modell am besten bewertet

**Zu meidende Quartiere** (Marktsaettigung):
- Innenstadtnahe Quartiere mit hoher Fitnesscenter-Dichte haben kaum Wachstumspotenzial

### 10.3 Limitationen

1. **OSM-Datenvollstaendigkeit**: Nicht alle Fitnesscenter sind in OSM erfasst (besonders kleine Studios)
2. **Statische Daten**: Saisonale und tagesabhaengige Besucherverteilung nicht beruecksichtigt
3. **Kaufkraft-Proxy**: Das steuerbare Einkommen (BFS) ist nur auf Gemeindeebene frei verfuegbar; Quartiersschaetzungen basieren auf soziooekonomischen Proxys, nicht auf Primaerdaten
4. **Isochronen-Vereinfachung**: Nur Fussgaenger-Netzwerk, kein Velo/OEV-Routing
5. **Raeumliche Regression**: 2SLS-Implementierung ohne spreg-Package -- robustere Standard-Fehler waeren wuenschenswert

### 10.4 Literatur

- Gellrich, M. (FS2026). *Einsatz von Geodaten im Marketing*. ZHAW School of Management and Law.
- Boeing, G. (2017). OSMnx: New Methods for Acquiring, Constructing, Analyzing, and Visualizing Complex Street Networks. *Computers, Environment and Urban Systems*, 65, 126-139.
- Anselin, L. (2005). *Exploring Spatial Data with GeoDa: A Workbook*. GeoDa Center.
- Tobler, W. R. (1970). A Computer Movie Simulating Urban Growth in the Detroit Region. *Economic Geography*, 46, 234-240.
- Bundesamt fuer Statistik (BFS) (2022). *Steuerstatistik -- Natuerliche Personen, Kanton Zuerich*. Neuchatel: BFS.
- Bivand, R., Pebesma, E., & Gomez-Rubio, V. (2013). *Applied Spatial Data Analysis with R* (2nd ed.). Springer.

---
*ZHAW FS2026 | Einsatz von Geodaten im Marketing | Kai Bleuel | Python 3 | GeoPandas | osmnx | libpysal*
"""
))

# ---------------------------------------------------------------------------
nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    },
    "cells": cells,
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"Notebook erstellt: {OUT}")
print(f"   Zellen total: {len(cells)}")
