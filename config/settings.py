"""
settings.py – Zentrale Projektkonfiguration
============================================
Alle globalen Parameter, Pfade und Konstanten für das
Geomarketing-Projekt "Standortanalyse Fitnesscenter Zürich".

Kurs  : Einsatz von Geodaten im Marketing (WPM-EGM), ZHAW FS2026
Autor : Kai Bleuel
"""

from pathlib import Path

# ── Projektpfade ───────────────────────────────────────────────────────────────
ROOT_DIR     = Path(__file__).resolve().parent.parent
DATA_RAW     = ROOT_DIR / "data" / "raw"
DATA_PROC    = ROOT_DIR / "data" / "processed"
OUTPUT_MAPS  = ROOT_DIR / "outputs" / "maps"
OUTPUT_FIGS  = ROOT_DIR / "outputs" / "figures"
DOCS_DIR     = ROOT_DIR / "docs"

# Sicherstellen, dass alle Verzeichnisse existieren
for _p in [DATA_RAW, DATA_PROC, OUTPUT_MAPS, OUTPUT_FIGS, DOCS_DIR]:
    _p.mkdir(parents=True, exist_ok=True)

# ── Koordinatenreferenzsysteme (CRS) ──────────────────────────────────────────
# Alle im Unterricht behandelten CRS-Codes (Folie Koordinatensysteme)
CRS_WGS84 = "EPSG:4326"   # Geographisch, GPS (lon/lat) – WGS84
CRS_LV95  = "EPSG:2056"   # Schweizer Landeskoordinaten (Meter) – CH1903+/LV95
CRS_WEB   = "EPSG:3857"   # Web Mercator (für Basemaps / Contextily)
CRS_LV03  = "EPSG:21781"  # Altes CH-System LV03 (Referenz)

# Primäres CRS für alle Analysen: LV95 (Meter, für Distanzberechnungen korrekt)
CRS_ANALYSIS = CRS_LV95

# ── Untersuchungsgebiet ────────────────────────────────────────────────────────
STUDY_AREA_QUERY = "Zürich, Switzerland"   # OSMnx Geocoding Query
STUDY_AREA_NAME  = "Stadt Zürich"

# ── Datenquellen (URLs) ────────────────────────────────────────────────────────
# Stadt Zürich Open Data (OGD) – Statistische Quartiere (WFS GeoJSON)
URL_QUARTIERE_WFS = (
    "https://www.ogd.stadt-zuerich.ch/wfs/geoportal/Statistische_Quartiere"
    "?service=WFS&version=1.1.0&request=GetFeature"
    "&outputFormat=GeoJSON&typename=adm_statistische_quartiere_v"
)

# Stadt Zürich – Bevölkerung nach Statistischem Quartier (OGD CSV)
URL_BEVOELKERUNG_CSV = (
    "https://data.stadt-zuerich.ch/dataset/"
    "bev_bestand_jahr_quartier_od3240/download/BEV390OD3240.csv"
)

# GeoAdmin – Schweizer Gemeindegrenzen (WFS)
URL_GEMEINDEN_GEOADMIN = (
    "https://api3.geo.admin.ch/rest/services/api/MapServer/"
    "ch.swisstopo.swissboundaries3d-gemeinde-flaeche.fill/query"
)

# ── OSM-Tags für Datenbeschaffung ──────────────────────────────────────────────
OSM_TAGS_FITNESSCENTER = {
    "leisure": "fitness_centre",
}
OSM_TAGS_GYM = {
    "amenity": "gym",
}
OSM_TAGS_OEV = {
    "public_transport": "stop_position",
}

# ── Analysenparameter ──────────────────────────────────────────────────────────
# Isochronen: Gehzeit in Minuten (aus Vorlesung: Einzugsgebietsanalyse)
ISOCHRONE_WALK_MINS  = [10, 15]        # Fussgänger-Isochronen
WALK_SPEED_KMH       = 4.5             # Durchschnittliche Gehgeschwindigkeit
NETWORK_TYPE_WALK    = "walk"          # osmnx Netzwerktyp

# Standort-Score Gewichtungen (Annahmen dokumentiert in Notebook Kapitel 6)
SCORE_WEIGHTS = {
    "pop_density"  : 0.30,   # Nachfrage: Einwohner/km²
    "job_density"  : 0.10,   # Nachfrage: Arbeitsplätze/km²
    "oev_access"   : 0.25,   # Erreichbarkeit: ÖV-Haltestellen/km²
    "competition"  : 0.25,   # Wettbewerb: invers (weniger Konkurrenz = höherer Score)
    "income"       : 0.10,   # Kaufkraft: Steuerbares Einkommen (BFS-Proxy)
}

# Buffer-Radius für Konkurrenzanalyse (Meter, LV95)
COMPETITION_RADIUS_M = 800   # ~10 Min. Fussweg

# ── Visualisierungsparameter ───────────────────────────────────────────────────
FIGSIZE_MAP    = (12, 10)
FIGSIZE_WIDE   = (16, 8)
FIGSIZE_SQUARE = (10, 10)
DPI            = 150
ALPHA          = 0.75

# Farben (konsistentes Farbschema)
COLOR_GYMS       = "#E63946"    # Rot – bestehende Fitnesscenter
COLOR_GYMS_LIGHT = "#FF9999"
COLOR_OEV        = "#457B9D"    # Blau – ÖV-Haltestellen
COLOR_CITY_EDGE  = "#1D3557"    # Dunkelblau – Stadtgrenze
COLOR_ISO_10     = "#2A9D8F"    # Grün – 10-Min-Isochrone
COLOR_ISO_15     = "#E9C46A"    # Gelb – 15-Min-Isochrone
COLOR_POTENTIAL  = "#F4A261"    # Orange – Potenzialgebiete
CMAP_SCORE       = "RdYlGn"     # Colormap für Score (Rot=niedrig, Grün=hoch)
CMAP_DENSITY     = "YlOrRd"     # Colormap für Dichte
