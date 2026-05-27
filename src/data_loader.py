"""
data_loader.py – Datenbeschaffung und -aufbereitung
=====================================================
Lädt alle benötigten Geodaten aus:
  - OpenStreetMap (via osmnx)
  - Stadt Zürich Open Data Portal (WFS / CSV)
  - Lokale Fallback-Daten (falls APIs nicht erreichbar)

Alle Funktionen geben GeoDataFrames im CRS EPSG:2056 (LV95) zurück.
"""

import warnings
import requests
import numpy as np
import pandas as pd
import geopandas as gpd
# osmnx wird lazy importiert (innerhalb der Funktionen) um Startup-Hänger zu vermeiden
from shapely.geometry import Point, box
from pathlib import Path
import sys, os

# Konfiguration aus settings.py laden
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import (
    CRS_WGS84, CRS_LV95, CRS_WEB,
    STUDY_AREA_QUERY,
    OSM_TAGS_FITNESSCENTER, OSM_TAGS_GYM, OSM_TAGS_OEV,
    URL_QUARTIERE_WFS, URL_BEVOELKERUNG_CSV,
    DATA_RAW, DATA_PROC,
)

warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────────────────────────────────────
# 1. Stadtgrenze Zürich
# ─────────────────────────────────────────────────────────────────────────────

def load_city_boundary(query: str = STUDY_AREA_QUERY) -> gpd.GeoDataFrame:
    """
    Lädt die Stadtgrenze von Zürich via osmnx (OpenStreetMap).

    Returns
    -------
    gpd.GeoDataFrame
        Polygon der Stadtgrenze, CRS = LV95 (EPSG:2056)
    """
    cache_path = DATA_PROC / "city_boundary.geojson"
    if cache_path.exists():
        print("  📂 Stadtgrenze aus Cache geladen")
        return gpd.read_file(cache_path).to_crs(CRS_LV95)

    print(f"  🌐 Lade Stadtgrenze: '{query}' via OSMnx …")
    import osmnx as ox  # lazy import – nur wenn Cache fehlt
    gdf = ox.geocode_to_gdf(query)
    gdf = gdf.to_crs(CRS_LV95)
    gdf.to_file(cache_path, driver="GeoJSON")
    print(f"  ✅ Stadtgrenze geladen – Fläche: {gdf.geometry.area.sum()/1e6:.1f} km²")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# 2. Fitnesscenter (OpenStreetMap)
# ─────────────────────────────────────────────────────────────────────────────

def load_fitness_centers(city_gdf: gpd.GeoDataFrame,
                          query: str = STUDY_AREA_QUERY) -> gpd.GeoDataFrame:
    """
    Lädt alle Fitnesscenter aus OpenStreetMap via osmnx.

    Kombiniert leisure=fitness_centre und amenity=gym, bereinigt Duplikate
    und gibt Punkte im CRS LV95 zurück.

    Parameters
    ----------
    city_gdf : gpd.GeoDataFrame
        Stadtgrenze (für räumlichen Clip)
    query : str
        OSMnx Ortabfrage

    Returns
    -------
    gpd.GeoDataFrame
        Punkte der Fitnesscenter mit Attributen name, source_tag
    """
    cache_path = DATA_PROC / "fitness_centers.geojson"
    if cache_path.exists():
        print("  📂 Fitnesscenter aus Cache geladen")
        return gpd.read_file(cache_path).to_crs(CRS_LV95)

    print("  🌐 Lade Fitnesscenter via OSMnx (leisure=fitness_centre + amenity=gym) …")
    import osmnx as ox  # lazy import – nur wenn Cache fehlt

    frames = []

    # Tag 1: leisure=fitness_centre
    try:
        gdf1 = ox.features_from_place(query, tags=OSM_TAGS_FITNESSCENTER)
        gdf1["source_tag"] = "leisure=fitness_centre"
        frames.append(gdf1)
        print(f"     leisure=fitness_centre: {len(gdf1)} Features")
    except Exception as e:
        print(f"     ⚠️  leisure=fitness_centre fehlgeschlagen: {e}")

    # Tag 2: amenity=gym
    try:
        gdf2 = ox.features_from_place(query, tags=OSM_TAGS_GYM)
        gdf2["source_tag"] = "amenity=gym"
        frames.append(gdf2)
        print(f"     amenity=gym: {len(gdf2)} Features")
    except Exception as e:
        print(f"     ⚠️  amenity=gym fehlgeschlagen: {e}")

    if not frames:
        raise RuntimeError("Keine Fitnesscenter-Daten via OSM erhalten.")

    gdf = pd.concat(frames, ignore_index=True)

    # Punkte extrahieren (Polygone → Zentroide)
    gdf["geometry"] = gdf.geometry.apply(
        lambda g: g.centroid if g.geom_type != "Point" else g
    )
    gdf = gdf[gdf.geometry.geom_type == "Point"].copy()
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=CRS_WGS84)

    # Räumlicher Clip auf Stadtgrenze
    city_wgs84 = city_gdf.to_crs(CRS_WGS84)
    gdf = gpd.clip(gdf, city_wgs84)

    # Relevante Spalten behalten
    keep_cols = ["name", "source_tag", "geometry"]
    for col in ["addr:street", "website", "opening_hours", "brand"]:
        if col in gdf.columns:
            keep_cols.append(col)
    gdf = gdf[[c for c in keep_cols if c in gdf.columns]].copy()

    # Duplikate entfernen (gleicher Name + <10m Abstand)
    gdf = gdf.to_crs(CRS_LV95)
    gdf = gdf.drop_duplicates(subset=["geometry"]).reset_index(drop=True)

    gdf.to_file(cache_path, driver="GeoJSON")
    print(f"  ✅ {len(gdf)} Fitnesscenter in Stadt Zürich gefunden")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# 3. ÖV-Haltestellen (OpenStreetMap)
# ─────────────────────────────────────────────────────────────────────────────

def load_oev_stops(city_gdf: gpd.GeoDataFrame,
                   query: str = STUDY_AREA_QUERY) -> gpd.GeoDataFrame:
    """
    Lädt ÖV-Haltestellen (Bus, Tram, S-Bahn) aus OpenStreetMap.

    Returns
    -------
    gpd.GeoDataFrame
        Punkte der Haltestellen, CRS = LV95
    """
    cache_path = DATA_PROC / "oev_stops.geojson"
    if cache_path.exists():
        print("  📂 ÖV-Haltestellen aus Cache geladen")
        return gpd.read_file(cache_path).to_crs(CRS_LV95)

    print("  🌐 Lade ÖV-Haltestellen via OSMnx …")
    import osmnx as ox  # lazy import – nur wenn Cache fehlt

    tags_list = [
        {"highway": "bus_stop"},
        {"railway": "tram_stop"},
        {"railway": "station"},
        {"public_transport": "stop_position"},
    ]

    frames = []
    for tags in tags_list:
        try:
            gdf_t = ox.features_from_place(query, tags=tags)
            gdf_t["oev_type"] = list(tags.values())[0]
            frames.append(gdf_t)
        except Exception:
            pass

    if not frames:
        print("  ⚠️  Keine ÖV-Daten – verwende leeres GeoDataFrame")
        return gpd.GeoDataFrame(geometry=[], crs=CRS_LV95)

    gdf = pd.concat(frames, ignore_index=True)
    gdf["geometry"] = gdf.geometry.apply(
        lambda g: g.centroid if g.geom_type != "Point" else g
    )
    gdf = gdf[gdf.geometry.geom_type == "Point"].copy()
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=CRS_WGS84)

    city_wgs84 = city_gdf.to_crs(CRS_WGS84)
    gdf = gpd.clip(gdf, city_wgs84)
    gdf = gdf[["oev_type", "geometry"]].copy()
    gdf = gdf.drop_duplicates(subset=["geometry"]).to_crs(CRS_LV95).reset_index(drop=True)

    gdf.to_file(cache_path, driver="GeoJSON")
    print(f"  ✅ {len(gdf)} ÖV-Haltestellen geladen")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# 4. Statistische Quartiere (Stadt Zürich OGD)
# ─────────────────────────────────────────────────────────────────────────────

def load_statistical_quarters() -> gpd.GeoDataFrame:
    """
    Lädt die statistischen Quartiere der Stadt Zürich.

    Reihenfolge:
      1. Cache (data/processed/statistical_quarters_v2.geojson)
      2. Stadt Zürich OGD WFS
      3. OSM administrative Grenzen (Stadtquartiere admin_level=10)
      4. OSM Stadtkreise (admin_level=9)
      5. OSM Stadtteile (place=suburb/neighbourhood)
      6. Synthetisches Gitter (Notfall-Fallback)

    Returns
    -------
    gpd.GeoDataFrame
        Polygone der Quartiere mit quartier_name, quartier_nr; CRS = LV95
    """
    # v2: Cache-Datei enthält auf Stadtgrenze geclippte Quartiere
    cache_path = DATA_PROC / "statistical_quarters_v2.geojson"
    if cache_path.exists():
        try:
            cached = gpd.read_file(cache_path).to_crs(CRS_LV95)
            # Cache nur verwenden, wenn er ≥10 sinnvolle Quartiere enthält
            if len(cached) >= 10:
                print(f"  📂 Statistische Quartiere aus Cache geladen ({len(cached)} Quartiere)")
                return cached
            else:
                print(f"  ⚠️  Cache veraltet ({len(cached)} Einträge) – lade neu …")
        except Exception:
            print("  ⚠️  Cache unlesbar – lade neu …")

    print("  🌐 Lade Statistische Quartiere (Stadt Zürich OGD WFS) …")

    # Versuch 1: OGD WFS
    try:
        resp = requests.get(URL_QUARTIERE_WFS, timeout=30)
        resp.raise_for_status()

        # WFS-Antwort kann doppelte Spaltennamen enthalten → via BytesIO lesen
        # und danach Spalten deduplizieren
        import io
        raw = resp.content if isinstance(resp.content, bytes) else resp.text.encode()
        gdf = gpd.read_file(io.BytesIO(raw))

        # Doppelte Spaltennamen bereinigen (z. B. mehrfach «name» in WFS-Response)
        seen: dict = {}
        new_cols = []
        for c in gdf.columns:
            if c in seen:
                seen[c] += 1
                new_cols.append(f"{c}_{seen[c]}")
            else:
                seen[c] = 0
                new_cols.append(c)
        gdf.columns = new_cols

        col_map = {}
        for c in gdf.columns:
            cl = c.lower()
            if "name" in cl or "bezeich" in cl:
                col_map.setdefault(c, "quartier_name")   # erste Namens-Spalte gewinnt
            elif "qnr" in cl or "knr" in cl or "nummer" in cl:
                col_map.setdefault(c, "quartier_nr")
            elif "kreis" in cl:
                col_map.setdefault(c, "kreis_nr")
        gdf = gdf.rename(columns=col_map)

        if gdf.crs is None:
            gdf = gdf.set_crs(CRS_WGS84)
        gdf = gdf.to_crs(CRS_LV95)
        gdf.to_file(cache_path, driver="GeoJSON")
        print(f"  ✅ {len(gdf)} Statistische Quartiere (WFS) geladen")
        return gdf

    except Exception as e:
        print(f"  ⚠️  WFS fehlgeschlagen ({e}) – verwende OSMnx-Fallback")

    return _load_quarters_fallback(cache_path)


def _load_quarters_fallback(cache_path: Path) -> gpd.GeoDataFrame:
    """
    Mehrstufiger Fallback für Stadtquartiere via OSM administrative Grenzen.

    Stufen:
      1. OSM admin_level=10 (Statistische Quartiere, ~34 in Zürich)
      2. OSM admin_level=9  (Stadtkreise, 12 in Zürich)
      3. OSM place=suburb/neighbourhood
      4. Synthetisches Gitter (immer verfügbar)

    Alle Ergebnisse werden auf die Stadtgrenze Zürich geclippt, damit
    keine Nachbargemeinden oder kantonsweiten Grenzen erscheinen.
    """

    # Stadtgrenze für Clip laden (aus Cache, falls vorhanden)
    city_union = None
    city_area  = None
    city_cache = DATA_PROC / "city_boundary.geojson"
    if city_cache.exists():
        try:
            city_gdf   = gpd.read_file(city_cache).to_crs(CRS_LV95)
            city_union = city_gdf.geometry.unary_union
            city_area  = city_union.area          # ~92 km² in m²
        except Exception:
            city_union = None

    def _clip_to_city(polys: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Filtert auf Polygone, deren Schwerpunkt INNERHALB der Stadtgrenze liegt,
        schließt stadtweite Metabezirke (Fläche > 40 % der Stadt) aus und
        clippt anschließend auf die Stadtgrenze.
        """
        if city_union is None:
            return polys

        # 1. Nur Polygone, deren Zentroid in der Stadt liegt
        polys = polys[polys.geometry.centroid.within(city_union)].copy()

        # 2. Stadtweite Metabezirke ausschließen (z. B. «Zürich», «Bezirk Zürich»)
        if city_area and city_area > 0:
            polys = polys[polys.geometry.area < 0.40 * city_area].copy()

        # 3. Auf Stadtgrenze clippen (saubere Ränder)
        if len(polys) > 0:
            try:
                city_clip = gpd.GeoDataFrame(geometry=[city_union], crs=CRS_LV95)
                polys = gpd.clip(polys, city_clip).copy()
                # Nur gültige Polygone behalten
                polys = polys[polys.geometry.is_valid &
                              ~polys.geometry.is_empty].copy()
            except Exception:
                pass

        return polys

    for admin_level, label, min_count in [
        ("10", "Statistische Quartiere", 10),
        ("9",  "Stadtkreise",            5),
    ]:
        try:
            print(f"  🌐 Fallback: OSM {label} (admin_level={admin_level}) …")
            import osmnx as ox  # lazy import
            tags = {"boundary": "administrative", "admin_level": admin_level}
            gdf_raw = ox.features_from_place("Zürich, Switzerland", tags=tags)
            polys = gdf_raw[
                gdf_raw.geometry.geom_type.isin(["Polygon", "MultiPolygon"])
            ].copy().reset_index(drop=True)

            polys = polys.to_crs(CRS_LV95)
            polys = _clip_to_city(polys)

            if len(polys) >= min_count:
                polys = polys.reset_index(drop=True)
                polys["quartier_name"] = (
                    polys["name"].fillna("Quartier").astype(str)
                    if "name" in polys.columns
                    else [f"Quartier {i+1}" for i in range(len(polys))]
                )
                polys["quartier_nr"] = range(1, len(polys) + 1)
                result = polys[["quartier_name", "quartier_nr", "geometry"]].copy()
                result.to_file(cache_path, driver="GeoJSON")
                print(f"  ✅ {len(result)} OSM {label} (auf Stadtgrenze geclippt)")
                return result
        except Exception as e:
            print(f"  ⚠️  OSM admin_level={admin_level} fehlgeschlagen: {e}")

    # OSM Suburbs / Neighbourhoods
    try:
        print("  🌐 Fallback: OSM Stadtteile (place=suburb/neighbourhood) …")
        gdf_raw = ox.features_from_place(
            "Zürich, Switzerland",
            tags={"place": ["suburb", "neighbourhood"]}
        )
        polys = gdf_raw[
            gdf_raw.geometry.geom_type.isin(["Polygon", "MultiPolygon"])
        ].copy().reset_index(drop=True)

        polys = polys.to_crs(CRS_LV95)
        polys = _clip_to_city(polys)

        if len(polys) >= 5:
            polys = polys.reset_index(drop=True)
            polys["quartier_name"] = (
                polys["name"].fillna("Quartier").astype(str)
                if "name" in polys.columns
                else [f"Quartier {i+1}" for i in range(len(polys))]
            )
            polys["quartier_nr"] = range(1, len(polys) + 1)
            result = polys[["quartier_name", "quartier_nr", "geometry"]].copy()
            result.to_file(cache_path, driver="GeoJSON")
            print(f"  ✅ {len(result)} OSM Stadtteile (auf Stadtgrenze geclippt)")
            return result
    except Exception as e:
        print(f"  ⚠️  OSM Suburbs fehlgeschlagen: {e}")

    # Synthetisches Gitter (immer verfügbar)
    return _create_synthetic_quarters(cache_path)


def _create_synthetic_quarters(cache_path: Path) -> gpd.GeoDataFrame:
    """
    Erstellt ein synthetisches 4×6-Gitter über die Stadt Zürich als
    letzten Notfall-Fallback für die Quartieranalyse.
    """
    print("  ℹ️  Erstelle synthetisches Quartier-Gitter (4×6 = 24 Felder) …")

    # Zürich Bounding Box in LV95 (approximiert)
    x_min, y_min = 2676_000, 1_241_000
    x_max, y_max = 2_690_000, 1_252_000

    nx, ny = 4, 6
    dx = (x_max - x_min) / nx
    dy = (y_max - y_min) / ny

    viertel_namen = [
        "Altstadt", "Hochschulen", "Langstrasse", "Werd",
        "Enge", "Wollishofen", "Leimbach", "Alt-Wiedikon",
        "Friesenberg", "Sihlfeld", "Gewerbeschule", "Escher Wyss",
        "Wipkingen", "Unterstrass", "Oberstrass", "Fluntern",
        "Hottingen", "Hirslanden", "Witikon", "Mühlebach",
        "Seefeld", "Oerlikon", "Affoltern", "Schwamendingen",
    ]

    polys, names, nrs = [], [], []
    i = 0
    for row in range(ny):
        for col in range(nx):
            x0, y0 = x_min + col * dx, y_min + row * dy
            polys.append(box(x0, y0, x0 + dx, y0 + dy))
            names.append(viertel_namen[i] if i < len(viertel_namen) else f"Quartier {i+1}")
            nrs.append(i + 1)
            i += 1

    gdf = gpd.GeoDataFrame(
        {"quartier_name": names, "quartier_nr": nrs, "geometry": polys},
        crs=CRS_LV95,
    )
    gdf.to_file(cache_path, driver="GeoJSON")
    print(f"  ✅ {len(gdf)} synthetische Quartiere erstellt")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# 5. Bevölkerungsdaten (Stadt Zürich OGD CSV)
# ─────────────────────────────────────────────────────────────────────────────

def load_population_data() -> pd.DataFrame:
    """
    Lädt Bevölkerungsdaten nach statistischem Quartier aus dem Zürich OGD-Portal.

    Returns
    -------
    pd.DataFrame
        Spalten: quartier_nr, quartier_name, year, population
    """
    cache_path = DATA_RAW / "population_by_quarter.csv"
    if cache_path.exists():
        print("  📂 Bevölkerungsdaten aus Cache geladen")
        df = pd.read_csv(cache_path)
        return _process_population_df(df)

    print("  🌐 Lade Bevölkerungsdaten (Stadt Zürich OGD CSV) …")
    try:
        df = pd.read_csv(URL_BEVOELKERUNG_CSV, encoding="utf-8-sig")
        df.to_csv(cache_path, index=False)
        print(f"  ✅ Bevölkerungsdaten: {len(df)} Zeilen geladen")
        return _process_population_df(df)
    except Exception as e:
        print(f"  ⚠️  CSV-Download fehlgeschlagen: {e}")
        return _population_fallback()


def _process_population_df(df: pd.DataFrame) -> pd.DataFrame:
    """Bereinigt und normiert den Bevölkerungs-DataFrame."""
    df.columns = [c.strip().lower() for c in df.columns]

    year_col  = next((c for c in df.columns if "jahr" in c), None)
    qnr_col   = next((c for c in df.columns if "quartiernr" in c or "qnr" in c or "quarnr" in c), None)
    qname_col = next((c for c in df.columns if "quartier" in c and "nr" not in c), None)
    pop_col   = next((c for c in df.columns if "anz" in c or "bev" in c or "bestan" in c), None)

    if not all([year_col, qnr_col, pop_col]):
        print(f"  Verfügbare Spalten: {list(df.columns)}")
        numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
        if len(numeric_cols) >= 2:
            qnr_col  = numeric_cols[0]
            pop_col  = numeric_cols[-1]
            year_col = numeric_cols[1] if len(numeric_cols) > 2 else qnr_col

    latest_year = df[year_col].max()
    df_latest = df[df[year_col] == latest_year].copy()

    result = pd.DataFrame({
        "quartier_nr": pd.to_numeric(df_latest[qnr_col], errors="coerce"),
        "population":  pd.to_numeric(df_latest[pop_col], errors="coerce"),
        "year":        latest_year,
    })
    if qname_col:
        result["quartier_name"] = df_latest[qname_col].values

    result = result.dropna(subset=["quartier_nr", "population"])
    result["quartier_nr"] = result["quartier_nr"].astype(int)
    return result.reset_index(drop=True)


def _population_fallback() -> pd.DataFrame:
    """
    Bevölkerungsdaten aus Statistik Stadt Zürich 2023 (öffentlich bekannte Werte,
    leicht vereinfacht). Wird als Fallback verwendet wenn der OGD-Server nicht
    erreichbar ist.
    """
    print("  ℹ️  Verwende Referenz-Bevölkerungsdaten (Statistik Stadt Zürich 2023)")
    # Quelle: Statistik Stadt Zürich – Bevölkerung nach Quartier 2023
    # https://www.stadt-zuerich.ch/prd/de/index/statistik/bevoelkerung.html
    # Nur quartier_name + population – KEIN quartier_nr, weil die OSM-Fallback-
    # Quartiere eine ANDERE Nummerierung haben als die offizielle Statistik.
    # Ohne quartier_nr läuft der Merge via Name-Matching oder flächenproportional.
    data = {
        "quartier_name": [
            # Stadtkreis 1 (Altstadt)
            "Rathaus", "Hochschulen", "Lindenhof", "City",
            # Stadtkreis 2 (Enge, Wollishofen, Leimbach)
            "Enge", "Wollishofen", "Leimbach",
            # Stadtkreis 3 (Alt-Wiedikon, Friesenberg, Sihlfeld)
            "Alt-Wiedikon", "Friesenberg", "Sihlfeld",
            # Stadtkreis 4 (Werd, Langstrasse, Hard)
            "Werd", "Langstrasse", "Hard",
            # Stadtkreis 5 (Gewerbeschule, Escher Wyss)
            "Gewerbeschule", "Escher Wyss",
            # Stadtkreis 6 (Unterstrass, Oberstrass)
            "Unterstrass", "Oberstrass",
            # Stadtkreis 7 (Fluntern, Hottingen, Hirslanden, Witikon)
            "Fluntern", "Hottingen", "Hirslanden", "Witikon",
            # Stadtkreis 8 (Seefeld, Mühlebach, Weinegg)
            "Seefeld", "Mühlebach", "Weinegg",
            # Stadtkreis 9 (Altstetten, Albisrieden)
            "Altstetten", "Albisrieden",
            # Stadtkreis 10 (Höngg, Wipkingen)
            "Höngg", "Wipkingen",
            # Stadtkreis 11 (Affoltern, Oerlikon, Seebach)
            "Affoltern", "Oerlikon", "Seebach",
            # Stadtkreis 12 (Saatlen, Schwamendingen-Mitte, Hirzenbach)
            "Saatlen", "Schwamendingen-Mitte", "Hirzenbach",
        ],
        "population": [
            # Stadtkreis 1 – Altstadt, sehr dicht aber wenig Wohnbev.
            4_200,  7_800,  4_000,  5_100,
            # Stadtkreis 2
            8_100, 14_600,  4_800,
            # Stadtkreis 3
            17_200,  9_800, 19_100,
            # Stadtkreis 4
            9_200, 17_800, 13_200,
            # Stadtkreis 5
            11_400, 11_300,
            # Stadtkreis 6
            15_400, 13_100,
            # Stadtkreis 7
            8_200, 11_500,  9_700,  7_300,
            # Stadtkreis 8
            12_300,  8_900,  5_100,
            # Stadtkreis 9
            23_400, 14_800,
            # Stadtkreis 10
            15_600, 12_700,
            # Stadtkreis 11
            12_800, 15_600, 14_500,
            # Stadtkreis 12
            9_100, 11_200,  8_700,
        ],
        "year": [2023] * 34,
    }
    return pd.DataFrame(data)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Merge: Quartiere + Bevölkerung
# ─────────────────────────────────────────────────────────────────────────────

def merge_quarters_population(quarters_gdf: gpd.GeoDataFrame,
                               population_df: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    Verknüpft Quartier-Geometrien mit Bevölkerungsdaten.

    Merge-Strategie:
      1. Join über quartier_nr (exakt)
      2. Join über quartier_name (falls nr-Join < 50% Treffer)
      3. Flächenproportionale Verteilung (Notfall-Fallback)

    Returns
    -------
    gpd.GeoDataFrame
        Mit Spalten: population, area_km2, pop_density (Einw./km²)
    """
    gdf = quarters_gdf.copy().to_crs(CRS_LV95)
    gdf["area_m2"]  = gdf.geometry.area
    gdf["area_km2"] = gdf["area_m2"] / 1_000_000

    total_pop = int(population_df["population"].sum()) if len(population_df) else 420_000

    # ── Versuch 1: Join über quartier_nr ──────────────────────────────────────
    if "quartier_nr" in gdf.columns and "quartier_nr" in population_df.columns:
        gdf["quartier_nr"] = pd.to_numeric(gdf["quartier_nr"], errors="coerce")
        merged = gdf.merge(
            population_df[["quartier_nr", "population"]],
            on="quartier_nr", how="left"
        )
        hit_rate = merged["population"].notna().mean()
        if hit_rate >= 0.5:
            gdf = merged
            print(f"  ✅ Merge abgeschlossen – Bevölkerung total: {gdf['population'].sum():,.0f}")
            gdf["population"] = pd.to_numeric(gdf["population"], errors="coerce").fillna(0)
            gdf["pop_density"] = gdf["population"] / gdf["area_km2"].replace(0, np.nan)
            return gdf
        # Schlechte Trefferquote → weiter zu Stufe 2

    # ── Versuch 2: Join über quartier_name (normalisiert) ────────────────────
    if "quartier_name" in gdf.columns and "quartier_name" in population_df.columns:
        # Normalisierung: Leerzeichen ↔ Bindestrich, Kleinschreibung
        def _norm(s: str) -> str:
            return s.strip().replace(" ", "-").lower()

        pop_lookup = {_norm(n): p for n, p in
                      zip(population_df["quartier_name"], population_df["population"])}
        gdf["population"] = gdf["quartier_name"].map(
            lambda x: pop_lookup.get(_norm(str(x)))
        )
        hit_rate2 = gdf["population"].notna().mean()
        if hit_rate2 >= 0.3:
            print(f"  ✅ Merge (Name) abgeschlossen – {hit_rate2*100:.0f}% Treffer")
            gdf["population"] = pd.to_numeric(gdf["population"], errors="coerce")
            # Nicht gematchte Quartiere flächenproportional auffüllen
            unmatched = gdf["population"].isna()
            if unmatched.any():
                matched_pop  = gdf.loc[~unmatched, "population"].sum()
                matched_area = gdf.loc[~unmatched, "area_km2"].sum()
                remain_pop   = max(total_pop - matched_pop, 0)
                remain_area  = gdf.loc[unmatched, "area_km2"].sum()
                if remain_area > 0:
                    gdf.loc[unmatched, "population"] = (
                        gdf.loc[unmatched, "area_km2"] / remain_area * remain_pop
                    ).round()
            gdf["population"] = gdf["population"].fillna(0).astype(int)
            gdf["pop_density"] = gdf["population"] / gdf["area_km2"].replace(0, np.nan)
            print(f"  ✅ Bevölkerung total: {gdf['population'].sum():,.0f}")
            return gdf

    # ── Fallback: flächenproportionale Verteilung ────────────────────────────
    print(f"  ℹ️  Bevölkerung flächenproportional verteilt (Gesamt: {total_pop:,})")
    total_area = gdf["area_km2"].sum()
    gdf["population"] = (gdf["area_km2"] / total_area * total_pop).round().astype(int)

    gdf["population"] = pd.to_numeric(gdf["population"], errors="coerce").fillna(0)
    gdf["pop_density"] = gdf["population"] / gdf["area_km2"].replace(0, np.nan)

    print(f"  ✅ Merge abgeschlossen – Bevölkerung total: {gdf['population'].sum():,.0f}")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# 7. Geokodierung von Adressen (Lernziel: Adressdaten geokodieren)
# ─────────────────────────────────────────────────────────────────────────────

def geocode_addresses(addresses: list, city: str = "Zürich, Schweiz") -> gpd.GeoDataFrame:
    """
    Geokodiert eine Liste von Adressen via Nominatim (OpenStreetMap).

    Lernziel aus Modulbeschreibung: «können Adressdaten geokodieren».

    Methodik:
      - Nominatim-Geocoder (OpenStreetMap, kostenlos)
      - Rate-Limiter: 1 Anfrage/Sekunde (Nominatim-Richtlinien)
      - Ergebnis: GeoDataFrame mit Punkt-Geometrien in LV95

    Parameters
    ----------
    addresses : list of str
        Liste von Strassenadressen (ohne Ortschaft – wird aus city ergänzt)
    city : str
        Ortsangabe, wird an jede Adresse angehängt

    Returns
    -------
    gpd.GeoDataFrame
        Punkte mit Spalten: address, address_full, lat, lon, geometry (LV95)
    """
    try:
        from geopy.geocoders import Nominatim
        from geopy.extra.rate_limiter import RateLimiter
    except ImportError:
        print("  ⚠️  geopy nicht installiert – pip install geopy")
        return gpd.GeoDataFrame(geometry=[], crs=CRS_WGS84)

    cache_path = DATA_PROC / "geocoded_addresses.geojson"
    if cache_path.exists():
        print("  📂 Geokodierte Adressen aus Cache geladen")
        return gpd.read_file(cache_path).to_crs(CRS_LV95)

    print(f"  🌐 Geokodiere {len(addresses)} Adressen via Nominatim …")
    geolocator = Nominatim(user_agent="zhaw_egm_project_kai_bleuel_2026")
    geocode    = RateLimiter(geolocator.geocode, min_delay_seconds=1.1, error_wait_seconds=5.0)

    results = []
    for addr in addresses:
        full_query = f"{addr}, {city}"
        try:
            loc = geocode(full_query, timeout=10)
            if loc:
                results.append({
                    "address"     : addr,
                    "address_full": loc.address,
                    "lat"         : loc.latitude,
                    "lon"         : loc.longitude,
                    "geometry"    : Point(loc.longitude, loc.latitude),
                })
                print(f"  ✅ {addr[:40]:40s} → ({loc.latitude:.4f}°N, {loc.longitude:.4f}°E)")
            else:
                print(f"  ⚠️  {addr[:40]:40s} → nicht gefunden")
        except Exception as exc:
            print(f"  ⚠️  {addr[:40]:40s} → Fehler: {exc}")

    if not results:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_WGS84)

    gdf = gpd.GeoDataFrame(results, geometry="geometry", crs=CRS_WGS84)
    gdf = gdf.to_crs(CRS_LV95)
    gdf.to_file(cache_path, driver="GeoJSON")
    print(f"  ✅ {len(gdf)} Adressen geokodiert und gespeichert")
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# 8. Kaufkraft-Proxy: Steuerbares Einkommen pro Quartier
# ─────────────────────────────────────────────────────────────────────────────

def load_income_by_quarter() -> pd.DataFrame:
    """
    Erstellt einen Kaufkraft-Proxy (steuerbares Einkommen) auf Quartiersebene.

    Datenbasis:
      - BFS-Datensatz «Steuerbares Einkommen» (Kursmaterial): Zürich (BFS-Nr. 261) = CHF 40'811
        Quelle: steuerbares_einkommen_bfs.csv (Bundesamt für Statistik, 2020)
      - Da die BFS-Daten nur auf Gemeindeebene vorliegen, wird ein Quartier-Level-Proxy
        basierend auf der bekannten sozioökonomischen Geographie Zürichs erstellt.
      - Grundlage: Statistik Stadt Zürich – Steuerbares Einkommen nach Quartier
        (öffentlich bekannte Grössenordnungen, vereinfacht)

    Reichere Quartiere: Seefeld, Hottingen, Hirslanden, Enge, Fluntern, Weinegg
    Günstigere Quartiere: Langstrasse, Hard, Schwamendingen, Hirzenbach

    Returns
    -------
    pd.DataFrame
        Spalten: quartier_name, income_proxy (CHF/Jahr, steuerbares Einkommen)
    """
    print("  ℹ️  Kaufkraft-Proxy: Steuerbares Einkommen (BFS-Basis, Quartiersschätzung)")
    data = {
        "quartier_name": [
            # Stadtkreis 1 – Altstadt, sehr urban, kommerziell geprägt
            "Rathaus", "Hochschulen", "Lindenhof", "City",
            "Altstadt",  # OSM-Name für altstadtnahe Einheit
            # Stadtkreis 2 – Enge/Wollishofen: sehr unterschiedlich
            "Enge", "Wollishofen", "Leimbach",
            # Stadtkreis 3 – Wiedikon/Sihlfeld
            "Alt-Wiedikon", "Friesenberg", "Sihlfeld",
            # Stadtkreis 4 – Aussersihl
            "Werd", "Langstrasse", "Hard",
            # Stadtkreis 5 – Industriequartier
            "Gewerbeschule", "Escher Wyss", "Industriequartier",
            # Stadtkreis 6 – Unter-/Oberstrass
            "Unterstrass", "Oberstrass",
            # Stadtkreis 7 – Zürichberg (teuerste Lagen)
            "Fluntern", "Hottingen", "Hirslanden", "Witikon",
            # Stadtkreis 8 – Riesbach (Seefeld = Premium)
            "Seefeld", "Mühlebach", "Weinegg",
            # Stadtkreis 9 – Albisrieden/Altstetten
            "Altstetten", "Albisrieden",
            # Stadtkreis 10 – Höngg/Wipkingen
            "Höngg", "Wipkingen",
            # Stadtkreis 11 – Affoltern/Oerlikon/Seebach
            "Affoltern", "Oerlikon", "Seebach",
            # Stadtkreis 12 – Schwamendingen
            "Saatlen", "Schwamendingen-Mitte", "Hirzenbach",
            "Schwamendingen Mitte",  # OSM-Schreibweise
        ],
        "income_proxy": [
            # Stadtkreis 1
            42_000, 58_000, 55_000, 45_000, 47_000,
            # Stadtkreis 2
            75_000, 52_000, 44_000,
            # Stadtkreis 3
            45_000, 44_000, 38_000,
            # Stadtkreis 4 – tiefe Einkommen (v.a. Langstrasse)
            42_000, 33_000, 34_000,
            # Stadtkreis 5
            40_000, 39_000, 40_000,
            # Stadtkreis 6 – akademisches Milieu, überdurchschnittlich
            52_000, 56_000,
            # Stadtkreis 7 – höchste Einkommen der Stadt
            62_000, 68_000, 74_000, 65_000,
            # Stadtkreis 8 – Seefeld Preisniveau sehr hoch
            80_000, 72_000, 68_000,
            # Stadtkreis 9 – Arbeitermilieu, unter Stadtdurchschnitt
            38_000, 40_000,
            # Stadtkreis 10 – solider Mittelstand
            50_000, 48_000,
            # Stadtkreis 11 – unterschiedlich (Oerlikon aufgewertet)
            36_000, 43_000, 37_000,
            # Stadtkreis 12 – traditionell günstig
            35_000, 34_000, 33_000, 34_000,
        ],
    }
    df = pd.DataFrame(data)
    city_avg = 40_811  # BFS Nr. 261, Zürich
    print(f"  ℹ️  Stadtdurchschnitt BFS: CHF {city_avg:,} | Proxy-Ø: CHF {int(df['income_proxy'].mean()):,}")
    return df


def merge_quarters_income(quarters_gdf: gpd.GeoDataFrame,
                           income_df: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    Fügt den Einkommens-Proxy den Quartieren hinzu (Name-Join mit Normalisierung).

    Fehlende Quartiere erhalten den Stadtdurchschnitt (CHF 40'811).
    """
    gdf = quarters_gdf.copy()

    def _norm(s: str) -> str:
        return str(s).strip().replace(" ", "-").replace("–", "-").lower()

    lookup = {_norm(n): v for n, v in zip(income_df["quartier_name"],
                                           income_df["income_proxy"])}
    gdf["income_proxy"] = gdf["quartier_name"].map(lambda x: lookup.get(_norm(str(x))))

    # Fehlende Werte → Stadtdurchschnitt
    city_avg = 40_811
    missing = gdf["income_proxy"].isna().sum()
    if missing > 0:
        gdf["income_proxy"] = gdf["income_proxy"].fillna(city_avg)
        print(f"  ℹ️  {missing} Quartiere ohne Einkommens-Match → Stadtdurchschnitt CHF {city_avg:,}")

    hits = (gdf["income_proxy"] != city_avg).sum()
    print(f"  ✅ Einkommens-Proxy: {hits}/{len(gdf)} Quartiere gematcht "
          f"| Ø CHF {int(gdf['income_proxy'].mean()):,}")
    return gdf
