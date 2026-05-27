"""
spatial_analysis.py - Raeumliche Analysen fuer Standortanalyse Fitnesscenter Zuerich
ZHAW FS2026 | Einsatz von Geodaten im Marketing
Autor: Kai Bleuel

Hinweis: osmnx/networkx werden lazy importiert (innerhalb von Funktionen),
um langsamen Startup des Notebooks zu vermeiden.
"""

import warnings
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, MultiPoint
from shapely.ops import unary_union
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import (
    CRS_WGS84, CRS_LV95, STUDY_AREA_QUERY,
    ISOCHRONE_WALK_MINS, WALK_SPEED_KMH, NETWORK_TYPE_WALK,
    COMPETITION_RADIUS_M, SCORE_WEIGHTS, DATA_PROC,
)

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# 1. Isochronen
# ---------------------------------------------------------------------------

def compute_isochrones(
    centers_gdf,
    walk_mins=None,
    walk_speed_kmh=None,
    network_type=None,
    cache_dir=None,
):
    """Berechne Fussweg-Isochronen fuer eine Liste von Standorten.

    Verwendet osmnx-Strassennetz. Falls ein gecachtes Netzwerk vorhanden ist,
    wird es geladen; andernfalls von OSM heruntergeladen und gespeichert.

    Parameters
    ----------
    centers_gdf : GeoDataFrame
        Punkte im CRS_WGS84 (lon/lat).
    walk_mins : list[int], optional
        Gehzeiten in Minuten. Standard: ISOCHRONE_WALK_MINS aus settings.
    walk_speed_kmh : float, optional
        Gehgeschwindigkeit km/h. Standard: WALK_SPEED_KMH.
    network_type : str, optional
        osmnx Netzwerktyp. Standard: NETWORK_TYPE_WALK.
    cache_dir : Path, optional
        Pfad fuer gecachtes Netzwerk. Standard: DATA_PROC.

    Returns
    -------
    GeoDataFrame
        Isochronen-Polygone mit Spalten walk_min und center_idx.
    """
    # Lazy imports - nur beim ersten Aufruf wenn Cache fehlt
    import osmnx as ox
    import networkx as nx

    if walk_mins is None:
        walk_mins = ISOCHRONE_WALK_MINS
    if walk_speed_kmh is None:
        walk_speed_kmh = WALK_SPEED_KMH
    if network_type is None:
        network_type = NETWORK_TYPE_WALK
    if cache_dir is None:
        cache_dir = DATA_PROC

    cache_dir = Path(cache_dir)
    cache_path = cache_dir / "zuerich_walk_network.graphml"

    print(f"  Lade Strassennetz (walk, {walk_mins} min) ...")
    if cache_path.exists():
        print("  Strassennetz aus Cache geladen")
        G = ox.load_graphml(cache_path)
    else:
        print("  Lade Strassennetz von OSM (1-3 min) ...")
        G = ox.graph_from_place(STUDY_AREA_QUERY, network_type=network_type)
        ox.save_graphml(G, cache_path)
        print(f"  Gespeichert: {cache_path.name}")

    # Gehgeschwindigkeit in m/min
    meters_per_min = walk_speed_kmh * 1000 / 60
    for _, _, _, data in G.edges(data=True, keys=True):
        data["travel_time"] = data.get("length", 0) / meters_per_min

    # WGS84 sicherstellen
    gdf = centers_gdf.copy()
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(CRS_WGS84)

    polygons = []
    n_total = len(gdf)
    for i, (idx, row) in enumerate(gdf.iterrows(), 1):
        if i % 5 == 0 or i == n_total:
            print(f"  Isochronen: {i}/{n_total} Standorte ...")
        lon = row.geometry.x
        lat = row.geometry.y
        try:
            center_node = ox.nearest_nodes(G, lon, lat)
        except Exception:
            continue
        for minutes in walk_mins:
            subgraph = nx.ego_graph(G, center_node, radius=minutes,
                                    distance="travel_time")
            node_points = [
                Point(data["x"], data["y"])
                for _, data in subgraph.nodes(data=True)
            ]
            if len(node_points) < 3:
                continue
            poly = MultiPoint(node_points).convex_hull
            polygons.append({
                "geometry": poly,
                "walk_min": minutes,
                "center_idx": idx,
            })

    if not polygons:
        print("  Keine Isochronen berechnet")
        return gpd.GeoDataFrame(
            columns=["geometry", "walk_min", "center_idx"],
            crs=CRS_WGS84,
        )

    iso_gdf = gpd.GeoDataFrame(polygons, crs=CRS_WGS84)
    print(f"  {len(iso_gdf)} Isochronen berechnet")
    return iso_gdf


# ---------------------------------------------------------------------------
# 2. OEV-Score
# ---------------------------------------------------------------------------

def compute_oev_score(quarters_gdf, oev_gdf):
    """Berechne OEV-Haltestellen-Dichte pro Quartier (Haltestellen/km2).

    Parameters
    ----------
    quarters_gdf : GeoDataFrame
        Statistische Quartiere.
    oev_gdf : GeoDataFrame
        OEV-Haltestellen als Punkte.

    Returns
    -------
    GeoDataFrame
        Eingabe-GDF mit neuen Spalten:
        - oev_stops : Anzahl Haltestellen im Quartier
        - oev_stops_per_km2 : Haltestellen-Dichte
    """
    q = quarters_gdf.copy()
    if q.crs is None:
        q = q.set_crs(CRS_LV95)
    q = q.to_crs(CRS_LV95)

    o = oev_gdf.copy()
    if o.crs is None:
        o = o.set_crs(CRS_WGS84)
    o = o.to_crs(CRS_LV95)

    # Nur Punkte behalten
    o = o[o.geometry.geom_type == "Point"].copy()

    joined = gpd.sjoin(o, q, how="left", predicate="within")
    counts = joined.groupby("index_right").size().rename("oev_stops")
    q = q.join(counts)
    q["oev_stops"] = q["oev_stops"].fillna(0)

    # area_km2 hinzufuegen falls nicht vorhanden
    if "area_km2" not in q.columns:
        q["area_km2"] = q.geometry.area / 1e6

    q["oev_stops_per_km2"] = q["oev_stops"] / q["area_km2"].replace(0, np.nan)
    q["oev_stops_per_km2"] = q["oev_stops_per_km2"].fillna(0)
    return q


# ---------------------------------------------------------------------------
# 3. Konkurrenz-Score
# ---------------------------------------------------------------------------

def compute_competition_score(quarters_gdf, gyms_gdf, radius_m=None):
    """Berechne Konkurrenz-Score: Anzahl Fitnesscenter im Radius pro Quartier.

    Berechnet zusaetzlich gyms_count (Point-in-Polygon) und
    gyms_per_10k_pop falls population-Spalte vorhanden.

    Parameters
    ----------
    quarters_gdf : GeoDataFrame
        Statistische Quartiere (gyms_count, population sollten vorhanden sein).
    gyms_gdf : GeoDataFrame
        Fitnesscenter als Punkte.
    radius_m : float, optional
        Suchradius in Metern. Standard: COMPETITION_RADIUS_M.

    Returns
    -------
    GeoDataFrame
        Eingabe-GDF mit neuer Spalte competition_count (Radius-basiert).
    """
    if radius_m is None:
        radius_m = COMPETITION_RADIUS_M

    q = quarters_gdf.copy()
    if q.crs is None:
        q = q.set_crs(CRS_LV95)
    q = q.to_crs(CRS_LV95)

    g = gyms_gdf.copy()
    if g.crs is None:
        g = g.set_crs(CRS_WGS84)
    g = g.to_crs(CRS_LV95)
    g = g[g.geometry.geom_type == "Point"].copy()

    # Zentroid jedes Quartiers fuer Radius-Suche
    q_centroids = q.copy()
    q_centroids["geometry"] = q.geometry.centroid

    competition_counts = []
    for idx, row in q_centroids.iterrows():
        buf = row.geometry.buffer(radius_m)
        n = g[g.geometry.within(buf)].shape[0]
        competition_counts.append(n)

    q["competition_count"] = competition_counts

    # Falls gyms_count noch nicht vorhanden: Point-in-Polygon berechnen
    if "gyms_count" not in q.columns:
        joined = gpd.sjoin(g, q, how="left", predicate="within")
        gyms_cnt = joined.groupby("index_right").size().rename("gyms_count")
        q = q.join(gyms_cnt)
        q["gyms_count"] = q["gyms_count"].fillna(0)

    # gyms_per_10k_pop berechnen
    if "population" in q.columns:
        q["gyms_per_10k_pop"] = np.where(
            q["population"] > 0,
            q["gyms_count"] / q["population"] * 10_000,
            0,
        )
    else:
        q["gyms_per_10k_pop"] = 0.0

    return q


# ---------------------------------------------------------------------------
# 4. Standort-Score
# ---------------------------------------------------------------------------

def compute_location_score(quarters_gdf, weights=None):
    """Berechne gewichteten Standort-Score fuer jedes Quartier.

    Normiert alle Teil-Scores auf [0,1] (Min-Max) und kombiniert sie
    gemaess SCORE_WEIGHTS (oder weights).

    Erwartete Eingabespalten:
    - pop_density       : Einwohner/km2
    - job_density       : Arbeitsplaetze/km2 (optional)
    - oev_stops_per_km2 : OEV-Dichte
    - competition_count : Anzahl Konkurrenten (Radius-basiert)
    - income_index      : Kaufkraft-Index [0,1] (optional)

    Returns
    -------
    GeoDataFrame
        Eingabe-GDF mit neuen Spalten score_*, location_score, score_class.
    """
    if weights is None:
        weights = SCORE_WEIGHTS

    gdf = quarters_gdf.copy()

    def minmax(series):
        mn, mx = series.min(), series.max()
        if mx == mn:
            return pd.Series(0.5, index=series.index)
        return (series - mn) / (mx - mn)

    # Bevoelkerungsdichte
    if "pop_density" in gdf.columns:
        gdf["score_pop"] = minmax(gdf["pop_density"])
    else:
        gdf["score_pop"] = pd.Series(0.5, index=gdf.index)

    # Arbeitsplatzdichte
    if "job_density" in gdf.columns:
        gdf["score_jobs"] = minmax(gdf["job_density"])
    else:
        gdf["score_jobs"] = pd.Series(0.0, index=gdf.index)

    # OEV-Score
    if "oev_stops_per_km2" in gdf.columns:
        gdf["score_oev"] = minmax(gdf["oev_stops_per_km2"])
    else:
        gdf["score_oev"] = pd.Series(0.5, index=gdf.index)

    # Konkurrenz (invers: weniger Konkurrenz = hoeherer Score)
    comp_col = "competition_count" if "competition_count" in gdf.columns else None
    if comp_col:
        gdf["score_comp"] = 1.0 - minmax(gdf[comp_col])
    else:
        gdf["score_comp"] = pd.Series(0.5, index=gdf.index)

    # Kaufkraft-Indikator
    if "income_index" in gdf.columns:
        gdf["score_income"] = gdf["income_index"].fillna(0.5)
    elif "income_proxy" in gdf.columns:
        gdf["score_income"] = minmax(gdf["income_proxy"])
    else:
        gdf["score_income"] = pd.Series(0.5, index=gdf.index)

    # Gewichteter Gesamtscore
    gdf["location_score"] = (
        weights.get("pop_density", 0.30) * gdf["score_pop"]  +
        weights.get("job_density", 0.10) * gdf["score_jobs"] +
        weights.get("oev_access",  0.25) * gdf["score_oev"]  +
        weights.get("competition", 0.25) * gdf["score_comp"] +
        weights.get("income",      0.10) * gdf["score_income"]
    )

    # Score-Klasse (fuer Tabellen und Legenden)
    gdf["score_class"] = pd.cut(
        gdf["location_score"],
        bins=[0.0, 0.35, 0.50, 0.65, 1.01],
        labels=["Gering", "Mittel", "Hoch", "Sehr hoch"],
        right=True,
        include_lowest=True,
    ).astype(str)

    return gdf


# ---------------------------------------------------------------------------
# 5. Moran's I
# ---------------------------------------------------------------------------

def compute_morans_i(gdf, variable, weight_type="queen"):
    """Berechne globalen Moran's I und LISA fuer eine Variable.

    Parameters
    ----------
    gdf : GeoDataFrame
    variable : str
        Spaltenname der zu analysierenden Variable.
    weight_type : str
        queen (Standard) oder rook.

    Returns
    -------
    dict mit Schluesseln:
        moran_i, p_value, z_score, expected_i,
        weights, moran_obj, lisa_obj,
        gdf_result, gdf_with_lisa (beide identisch)
    """
    from libpysal.weights import Queen, Rook
    from esda.moran import Moran, Moran_Local

    gdf_c = gdf.copy()
    if gdf_c.crs is None:
        gdf_c = gdf_c.set_crs(CRS_LV95)
    gdf_c = gdf_c.to_crs(CRS_LV95)

    # Fehlende Werte auffuellen
    gdf_c[variable] = pd.to_numeric(gdf_c[variable], errors="coerce")
    gdf_c[variable] = gdf_c[variable].fillna(gdf_c[variable].median())

    # Gewichtsmatrix
    if weight_type == "rook":
        w = Rook.from_dataframe(gdf_c, silence_warnings=True)
    else:
        w = Queen.from_dataframe(gdf_c, silence_warnings=True)
    w.transform = "r"   # Zeilenstandardisierung

    # Globaler Moran's I
    mi = Moran(gdf_c[variable], w)

    # Lokaler Moran's I (LISA)
    lisa = Moran_Local(gdf_c[variable], w, seed=42)

    # LISA-Spalten
    cluster_labels = {1: "HH", 2: "LH", 3: "LL", 4: "HL"}
    gdf_c["local_moran_i"]  = lisa.Is
    gdf_c["local_moran_p"]  = lisa.p_sim
    gdf_c["moran_cluster"]  = lisa.q          # 1=HH, 2=LH, 3=LL, 4=HL
    gdf_c["lisa_sig"]       = lisa.p_sim < 0.05
    gdf_c["lisa_p"]         = lisa.p_sim
    gdf_c["lisa_label"]     = [cluster_labels.get(int(q), "NS") for q in lisa.q]

    return {
        "moran_i":      mi.I,
        "p_value":      mi.p_sim,
        "z_score":      mi.z_sim,
        "expected_i":   mi.EI,
        "weights":      w,          # Benoetigt von plot_morans_scatter
        "moran_obj":    mi,
        "lisa_obj":     lisa,
        "gdf_result":   gdf_c,      # Hauptschluessel
        "gdf_with_lisa": gdf_c,     # Alias fuer Rueckwaertskompatibilitaet
    }


# ---------------------------------------------------------------------------
# 6. Spatial Regression
# ---------------------------------------------------------------------------

def compute_spatial_regression(gdf, y_var="gyms_per_km2", x_vars=None):
    """OLS-Regression + Moran-Diagnostik + Spatial-Lag-Modell (2SLS).

    Parameters
    ----------
    gdf : GeoDataFrame
        Quartierdaten mit y_var und x_vars als Spalten.
    y_var : str
        Abhaengige Variable (Standard: gyms_per_km2).
    x_vars : list[str], optional
        Unabhaengige Variablen. Standard:
        [pop_density, oev_stops_per_km2, income_index]

    Returns
    -------
    dict
        ols_coef, ols_pvals, ols_r2, ols_adj_r2, ols_residuals,
        moran_resid_i, moran_resid_p,
        lag_coef, lag_rho, lag_r2,
        feature_names, gdf_result
    """
    from scipy import stats
    from libpysal.weights import Queen
    from esda.moran import Moran

    if x_vars is None:
        x_vars = ["pop_density", "oev_stops_per_km2", "income_index"]

    # Daten vorbereiten
    gdf_r = gdf.copy()
    if gdf_r.crs is None:
        gdf_r = gdf_r.set_crs(CRS_LV95)
    gdf_r = gdf_r.to_crs(CRS_LV95)

    # Zielvariable erstellen falls noetig
    if y_var not in gdf_r.columns:
        if "gyms_count" in gdf_r.columns and "area_km2" in gdf_r.columns:
            gdf_r[y_var] = gdf_r["gyms_count"] / gdf_r["area_km2"].replace(0, np.nan)
        else:
            gdf_r[y_var] = 0.0

    # Fehlende Werte auffuellen
    for col in [y_var] + x_vars:
        if col in gdf_r.columns:
            gdf_r[col] = pd.to_numeric(gdf_r[col], errors="coerce")
            gdf_r[col] = gdf_r[col].fillna(gdf_r[col].median())
        else:
            gdf_r[col] = 0.0

    # Gueltige x_vars
    valid_x = [c for c in x_vars if c in gdf_r.columns]
    if not valid_x:
        valid_x = [x_vars[0]] if x_vars else ["pop_density"]

    feature_names = ["intercept"] + valid_x

    y = gdf_r[y_var].values.astype(float)
    X_raw = gdf_r[valid_x].values.astype(float)
    if X_raw.ndim == 1:
        X_raw = X_raw.reshape(-1, 1)
    X = np.column_stack([np.ones(len(y)), X_raw])

    n, k = X.shape

    # ────────────────────────────────────────────────────────────── OLS ──────
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    y_hat = X @ beta
    resid = y - y_hat

    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2     = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    r2_adj = 1.0 - (1.0 - r2) * (n - 1) / max(n - k, 1)

    # t-Tests
    mse      = ss_res / max(n - k, 1)
    var_beta = mse * XtX_inv
    se_beta  = np.sqrt(np.abs(np.diag(var_beta)))
    t_vals   = beta / np.where(se_beta > 0, se_beta, np.nan)
    p_vals   = 2.0 * (1.0 - stats.t.cdf(np.abs(t_vals), df=max(n - k, 1)))

    print(f"\n  OLS Regression: y = {y_var}")
    print(f"  {'Variable':<30} {'Coef':>10} {'p-val':>10}")
    print("  " + "-" * 52)
    for name, coef, pv in zip(feature_names, beta, p_vals):
        sig = "**" if pv < 0.01 else ("*" if pv < 0.05 else "")
        print(f"  {name:<30} {coef:>10.4f} {pv:>10.4f} {sig}")
    print(f"  R2 = {r2:.4f}, adj. R2 = {r2_adj:.4f}")

    # Ergebnisse in GDF speichern
    gdf_r["y_actual"]      = y
    gdf_r["y_fitted"]      = y_hat
    gdf_r["ols_residual"]  = resid
    gdf_r["ols_residuals"] = resid

    # ────────────────────────────────────────────── Moran's I (Residuen) ─────
    try:
        w = Queen.from_dataframe(gdf_r, silence_warnings=True)
        w.transform = "r"
        mi_resid = Moran(resid, w)
        moran_i  = float(mi_resid.I)
        moran_p  = float(mi_resid.p_sim)
        print(f"\n  Moran's I (Residuen): I = {moran_i:.4f}, p = {moran_p:.4f}")
    except Exception as e:
        w       = None
        moran_i = float("nan")
        moran_p = float("nan")
        print(f"  Moran's I: nicht berechnet ({e})")

    # ──────────────────────────────────────── Spatial-Lag-Modell (2SLS) ─────
    lag_results = {}
    lag_rho     = float("nan")
    coef_iv     = np.full(k + 1, float("nan"))
    r2_iv       = float("nan")

    if w is not None:
        try:
            W_full = np.array(w.full()[0], dtype=float)
            Wy     = W_full @ y

            # Instrumente: [X, W*X_raw]
            WX = W_full @ X_raw
            Z  = np.column_stack([X, WX])

            # Erste Stufe: Wy ~ Z
            Wy_hat = Z @ (np.linalg.pinv(Z.T @ Z) @ Z.T @ Wy)

            # Zweite Stufe: y ~ [X, Wy_hat]
            X_iv   = np.column_stack([X, Wy_hat])
            coef_iv = np.linalg.pinv(X_iv.T @ X_iv) @ X_iv.T @ y
            lag_rho = float(coef_iv[-1])

            y_hat_iv = X_iv @ coef_iv
            ss_res_iv = float(((y - y_hat_iv) ** 2).sum())
            r2_iv = 1.0 - ss_res_iv / ss_tot if ss_tot > 0 else 0.0

            gdf_r["lag_fitted"] = y_hat_iv
            print(f"  Spatial Lag (2SLS): rho = {lag_rho:+.4f}, R2 = {r2_iv:.4f}")

            lag_results = {
                "lag_feature_names": feature_names + ["W_y"],
                "lag_y_hat": y_hat_iv,
            }
        except Exception as e:
            lag_results = {"lag_error": str(e)}
            print(f"  Spatial Lag: Fehler – {e}")

    return {
        "ols_coef":       beta,
        "ols_pvals":      p_vals,
        "ols_r2":         r2,
        "ols_adj_r2":     r2_adj,
        "ols_residuals":  resid,
        "moran_resid_i":  moran_i,
        "moran_resid_p":  moran_p,
        "lag_coef":       coef_iv,
        "lag_rho":        lag_rho,
        "lag_r2":         r2_iv,
        "feature_names":  feature_names,
        "gdf_result":     gdf_r,
        **lag_results,
    }
