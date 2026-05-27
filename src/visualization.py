"""
visualization.py – Kartenerstellung und Visualisierungen
=========================================================
Alle Visualisierungsfunktionen für:
  - Statische Karten (Matplotlib + Contextily)
  - Interaktive Karten (Folium)
  - Statistische Plots (Moran Scatter, Balkendiagramme)
"""

import warnings
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from matplotlib.lines import Line2D
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster
import contextily as ctx
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import (
    CRS_LV95, CRS_WGS84, CRS_WEB,
    FIGSIZE_MAP, FIGSIZE_WIDE, FIGSIZE_SQUARE, DPI, ALPHA,
    COLOR_GYMS, COLOR_GYMS_LIGHT, COLOR_OEV, COLOR_CITY_EDGE,
    COLOR_ISO_10, COLOR_ISO_15, COLOR_POTENTIAL,
    CMAP_SCORE, CMAP_DENSITY,
    OUTPUT_MAPS, OUTPUT_FIGS,
)

warnings.filterwarnings("ignore")


def add_basemap(ax, crs=CRS_WEB):
    """Fügt Contextily-Basemap (OpenStreetMap) hinzu."""
    try:
        ctx.add_basemap(ax, crs=crs, source=ctx.providers.CartoDB.Positron, alpha=0.8)
    except Exception:
        try:
            ctx.add_basemap(ax, crs=crs, source=ctx.providers.OpenStreetMap.Mapnik, alpha=0.6)
        except Exception:
            pass  # Keine Basemap – kein Fehler


# Alias für Abwärtskompatibilität
_add_basemap = add_basemap


def add_north_arrow(ax, x=0.97, y=0.07, size=0.03):
    """Fügt einen einfachen Nordpfeil hinzu."""
    ax.annotate("N", xy=(x, y+size), xytext=(x, y),
                 xycoords="axes fraction", textcoords="axes fraction",
                 fontsize=10, fontweight="bold", ha="center",
                 arrowprops=dict(arrowstyle="->", lw=1.5))


# Alias für Abwärtskompatibilität
_north_arrow = add_north_arrow


# ─────────────────────────────────────────────────────────────────────────────
# 1. Stadtgrenze + Fitnesscenter
# ─────────────────────────────────────────────────────────────────────────────

def plot_city_with_gyms(city_gdf: gpd.GeoDataFrame,
                         gyms_gdf: gpd.GeoDataFrame,
                         oev_gdf: gpd.GeoDataFrame = None,
                         title: str = "Fitnesscenter in der Stadt Zürich",
                         save: bool = True) -> plt.Figure:
    """
    Karte 1: Stadtgrenze mit Fitnesscenter-Standorten und optionalen ÖV-Haltestellen.
    """
    fig, ax = plt.subplots(figsize=FIGSIZE_MAP)

    city_web = city_gdf.to_crs(CRS_WEB)
    gyms_web = gyms_gdf.to_crs(CRS_WEB)

    city_web.boundary.plot(ax=ax, color=COLOR_CITY_EDGE, linewidth=2, zorder=3)
    city_web.plot(ax=ax, color="#EBF2FA", alpha=0.5, zorder=2)

    if oev_gdf is not None and len(oev_gdf) > 0:
        oev_web = oev_gdf.to_crs(CRS_WEB)
        oev_web.plot(ax=ax, color=COLOR_OEV, markersize=3, alpha=0.4, zorder=4, label="ÖV-Haltestellen")

    gyms_web.plot(ax=ax, color=COLOR_GYMS, markersize=60, alpha=0.85, zorder=5,
                  edgecolor="white", linewidth=0.5, label="Fitnesscenter")

    add_basemap(ax, crs=CRS_WEB)
    add_north_arrow(ax)

    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLOR_GYMS,
               markersize=10, label=f"Fitnesscenter (n={len(gyms_gdf)})"),
    ]
    if oev_gdf is not None and len(oev_gdf) > 0:
        legend_elements.append(
            Line2D([0], [0], marker="o", color="w", markerfacecolor=COLOR_OEV,
                   markersize=6, alpha=0.7, label=f"ÖV-Haltestellen (n={len(oev_gdf)})")
        )
    ax.legend(handles=legend_elements, loc="lower left", fontsize=10, framealpha=0.9)

    ax.set_title(title, fontsize=15, fontweight="bold", pad=15)
    ax.set_axis_off()

    plt.tight_layout()
    if save:
        path = OUTPUT_MAPS / "01_fitnesscenter_zuerich.png"
        fig.savefig(path, dpi=DPI, bbox_inches="tight")
        print(f"  💾 Gespeichert: {path.name}")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 2. Choropleth-Karte (Bevölkerungsdichte / Score)
# ─────────────────────────────────────────────────────────────────────────────

def plot_choropleth(gdf: gpd.GeoDataFrame,
                    column: str,
                    title: str,
                    cmap: str = CMAP_DENSITY,
                    legend_label: str = "",
                    gyms_gdf: gpd.GeoDataFrame = None,
                    city_gdf: gpd.GeoDataFrame = None,
                    filename: str = "choropleth.png",
                    save: bool = True) -> plt.Figure:
    """
    Generische Choropleth-Karte für beliebige numerische Spalten.

    Parameters
    ----------
    city_gdf : gpd.GeoDataFrame, optional
        Stadtgrenze – wird genutzt um die Kartenausdehnung auf die Stadt
        zu beschränken (verhindert Anzeige des gesamten Kantons).
    """
    fig, ax = plt.subplots(figsize=FIGSIZE_MAP)
    gdf_web = gdf.to_crs(CRS_WEB)

    gdf_web.plot(
        column=column, ax=ax, cmap=cmap, alpha=ALPHA,
        legend=True,
        legend_kwds={
            "label": legend_label or column,
            "orientation": "horizontal",
            "pad": 0.02,
            "shrink": 0.6,
        },
        missing_kwds={"color": "#CCCCCC"},
        edgecolor="white", linewidth=0.5, zorder=3,
    )
    gdf_web.boundary.plot(ax=ax, color="#999999", linewidth=0.3, zorder=4)

    if gyms_gdf is not None and len(gyms_gdf) > 0:
        gyms_gdf.to_crs(CRS_WEB).plot(
            ax=ax, color=COLOR_GYMS, markersize=30,
            alpha=0.9, zorder=5, edgecolor="white", linewidth=0.4,
        )

    # Kartenausdehnung beschränken: city_gdf hat Priorität,
    # sonst werden die Bounds der Daten selbst verwendet (verhindert
    # Anzeige des gesamten Kantons, wenn Quartiere auf Stadt geclippt sind).
    if city_gdf is not None and len(city_gdf) > 0:
        extent_src = city_gdf.to_crs(CRS_WEB)
    else:
        extent_src = gdf_web  # Quartier-GDF selbst als Extent-Quelle
    minx, miny, maxx, maxy = extent_src.total_bounds
    pad_x = (maxx - minx) * 0.05
    pad_y = (maxy - miny) * 0.05
    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)

    add_basemap(ax, crs=CRS_WEB)
    add_north_arrow(ax)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    ax.set_axis_off()
    plt.tight_layout()

    if save:
        path = OUTPUT_MAPS / filename
        fig.savefig(path, dpi=DPI, bbox_inches="tight")
        print(f"  💾 Gespeichert: {path.name}")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 3. Isochronen-Karte
# ─────────────────────────────────────────────────────────────────────────────

def plot_isochrones(city_gdf: gpd.GeoDataFrame,
                    iso_gdf: gpd.GeoDataFrame,
                    gyms_gdf: gpd.GeoDataFrame,
                    minutes: list = None,
                    save: bool = True) -> plt.Figure:
    """
    Karte 3: Isochronen (Einzugsgebiete nach Gehzeit) aller Fitnesscenter.
    """
    if minutes is None:
        from config.settings import ISOCHRONE_WALK_MINS
        minutes = ISOCHRONE_WALK_MINS

    colors = {minutes[0]: COLOR_ISO_10, minutes[-1]: COLOR_ISO_15}
    if len(minutes) == 1:
        colors = {minutes[0]: COLOR_ISO_10}

    fig, ax = plt.subplots(figsize=FIGSIZE_MAP)

    city_web = city_gdf.to_crs(CRS_WEB)
    city_web.plot(ax=ax, color="#F5F5F5", alpha=0.6, zorder=1)
    city_web.boundary.plot(ax=ax, color=COLOR_CITY_EDGE, linewidth=2, zorder=4)

    if len(iso_gdf) > 0:
        iso_web = iso_gdf.to_crs(CRS_WEB)
        for mins in sorted(minutes, reverse=True):
            subset = iso_web[iso_web["walk_min"] == mins]
            if len(subset) > 0:
                subset.plot(ax=ax, color=colors.get(mins, "#AAAAAA"),
                            alpha=0.35, zorder=2)

    if len(gyms_gdf) > 0:
        gyms_gdf.to_crs(CRS_WEB).plot(
            ax=ax, color=COLOR_GYMS, markersize=50,
            alpha=0.9, zorder=5, edgecolor="white", linewidth=0.5,
        )

    add_basemap(ax, crs=CRS_WEB)
    add_north_arrow(ax)

    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLOR_GYMS,
               markersize=9, label="Fitnesscenter"),
    ]
    for mins, col in sorted(colors.items()):
        legend_elements.append(
            mpatches.Patch(facecolor=col, alpha=0.5,
                           label=f"{mins} Min. Einzugsgebiet (Fuss)")
        )
    ax.legend(handles=legend_elements, loc="lower left", fontsize=10, framealpha=0.9)

    ax.set_title("Einzugsgebietsanalyse: Fuss-Isochronen\nder Zürcher Fitnesscenter",
                 fontsize=14, fontweight="bold", pad=12)
    ax.set_axis_off()
    plt.tight_layout()

    if save:
        path = OUTPUT_MAPS / "03_isochronen.png"
        fig.savefig(path, dpi=DPI, bbox_inches="tight")
        print(f"  💾 Gespeichert: {path.name}")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 4. Standort-Score-Karte
# ─────────────────────────────────────────────────────────────────────────────

def plot_score_map(scored_gdf: gpd.GeoDataFrame,
                   gyms_gdf: gpd.GeoDataFrame,
                   top_n: int = 5,
                   save: bool = True) -> plt.Figure:
    """
    Karte 4: Standort-Score pro Quartier + Top-N Empfehlungen.
    """
    fig, ax = plt.subplots(figsize=FIGSIZE_MAP)
    gdf_web = scored_gdf.to_crs(CRS_WEB)

    gdf_web.plot(
        column="location_score", ax=ax, cmap=CMAP_SCORE,
        alpha=ALPHA, vmin=0, vmax=1,
        legend=True,
        legend_kwds={
            "label": "Standort-Score (0 = niedrig, 1 = hoch)",
            "orientation": "horizontal", "pad": 0.02, "shrink": 0.6,
        },
        edgecolor="white", linewidth=0.5, zorder=3,
    )
    gdf_web.boundary.plot(ax=ax, color="#AAAAAA", linewidth=0.4, zorder=4)

    # Bestehende Fitnesscenter
    if len(gyms_gdf) > 0:
        gyms_gdf.to_crs(CRS_WEB).plot(
            ax=ax, color=COLOR_GYMS, markersize=35,
            alpha=0.85, zorder=5, edgecolor="white", linewidth=0.4,
        )

    # Top-N Quartiere markieren
    top = scored_gdf.nlargest(top_n, "location_score")
    top_web = top.to_crs(CRS_WEB)
    top_web.boundary.plot(ax=ax, color="#1D3557", linewidth=2.5, zorder=6)

    for _, row in top_web.iterrows():
        centroid = row.geometry.centroid
        name = row.get("quartier_name", "?")
        ax.annotate(
            f"  {name}", xy=(centroid.x, centroid.y),
            xycoords="data", fontsize=7.5, fontweight="bold",
            color="#1D3557", zorder=7,
            bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7, ec="none"),
        )

    add_basemap(ax, crs=CRS_WEB)
    add_north_arrow(ax)

    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLOR_GYMS,
               markersize=9, label="Bestehende Fitnesscenter"),
        mpatches.Patch(facecolor="none", edgecolor="#1D3557", linewidth=2,
                       label=f"Top {top_n} Potenzialquartiere"),
    ]
    ax.legend(handles=legend_elements, loc="lower left", fontsize=10, framealpha=0.9)
    ax.set_title("Standort-Score-Modell\nPotenzial für neue Fitnesscenter in Zürich",
                 fontsize=14, fontweight="bold", pad=12)
    ax.set_axis_off()
    plt.tight_layout()

    if save:
        path = OUTPUT_MAPS / "04_standort_score.png"
        fig.savefig(path, dpi=DPI, bbox_inches="tight")
        print(f"  💾 Gespeichert: {path.name}")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 5. Moran Scatter Plot
# ─────────────────────────────────────────────────────────────────────────────

def plot_morans_scatter(moran_result: dict,
                         variable: str = "location_score",
                         save: bool = True) -> plt.Figure:
    """
    Moran-Streudiagramm (aus Vorlesung Kapitel 7: Spatial Autocorrelation).
    Zeigt die Beziehung zwischen einem Wert und dem räumlichen Lag seiner Nachbarn.
    """
    if not moran_result or "moran_obj" not in moran_result:
        print("  ⚠️  Moran-Ergebnis nicht verfügbar")
        return None

    mi   = moran_result["moran_obj"]
    w    = moran_result["weights"]
    gdf  = moran_result.get("gdf_with_lisa")

    y    = mi.y
    wy   = w.sparse.dot(y)   # Spatial Lag

    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_WIDE)

    # --- Moran Scatter ---
    ax = axes[0]
    yz = (y - y.mean()) / y.std()
    wyz = (wy - wy.mean()) / wy.std()

    ax.scatter(yz, wyz, color="#457B9D", alpha=0.7, edgecolor="white", s=60, zorder=3)
    ax.axhline(0, color="grey", lw=0.8, linestyle="--")
    ax.axvline(0, color="grey", lw=0.8, linestyle="--")

    # Regressionslinie
    m, b = np.polyfit(yz, wyz, 1)
    xline = np.linspace(yz.min(), yz.max(), 100)
    ax.plot(xline, m * xline + b, color="#E63946", lw=2, zorder=4)

    ax.set_xlabel("Standardisierter Score", fontsize=11)
    ax.set_ylabel("Räumlicher Lag (Ø Nachbarn)", fontsize=11)
    ax.set_title(
        f"Moran's I = {mi.I:.4f}\n(p = {mi.p_sim:.4f})",
        fontsize=12, fontweight="bold"
    )

    for quadrant, label, color in [
        ((1,  1), "HH (hot spot)",  "#E63946"),
        ((-1, 1), "LH (outlier)",   "#F4A261"),
        ((-1,-1), "LL (cold spot)", "#457B9D"),
        ((1, -1), "HL (outlier)",   "#2A9D8F"),
    ]:
        ax.text(quadrant[0]*0.7, quadrant[1]*0.7, label,
                ha="center", va="center", fontsize=8,
                color=color, alpha=0.6, fontweight="bold")
    ax.grid(True, alpha=0.3)

    # --- LISA Karte ---
    if gdf is not None:
        ax2 = axes[1]
        lisa_colors = {"HH": "#E63946", "LH": "#F4A261", "LL": "#457B9D", "HL": "#2A9D8F"}
        gdf_web = gdf.to_crs(CRS_WEB)

        # Nicht-signifikante Quartiere grau
        not_sig = gdf_web[~gdf_web["lisa_sig"]]
        not_sig.plot(ax=ax2, color="#CCCCCC", alpha=0.5, edgecolor="white", linewidth=0.3)

        # Signifikante LISA-Cluster
        for label, color in lisa_colors.items():
            subset = gdf_web[gdf_web["lisa_sig"] & (gdf_web["lisa_label"] == label)]
            if len(subset) > 0:
                subset.plot(ax=ax2, color=color, alpha=0.8,
                            edgecolor="white", linewidth=0.3, label=label)

        try:
            ctx.add_basemap(ax2, crs=CRS_WEB,
                            source=ctx.providers.CartoDB.Positron, alpha=0.6)
        except Exception:
            pass

        legend_patches = [
            mpatches.Patch(facecolor=c, label=l)
            for l, c in lisa_colors.items()
        ] + [mpatches.Patch(facecolor="#CCCCCC", label="nicht signifikant")]
        ax2.legend(handles=legend_patches, loc="lower left", fontsize=9, framealpha=0.9)
        ax2.set_title("LISA Cluster-Karte\n(signifikante lokale Autokorrelation)",
                      fontsize=12, fontweight="bold")
        ax2.set_axis_off()

    plt.suptitle("Räumliche Autokorrelation des Standort-Scores (Moran's I)",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()

    if save:
        path = OUTPUT_FIGS / "05_morans_i.png"
        fig.savefig(path, dpi=DPI, bbox_inches="tight")
        print(f"  💾 Gespeichert: {path.name}")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 6. Interaktive Folium-Karte
# ─────────────────────────────────────────────────────────────────────────────

def save_folium_map(city_gdf: gpd.GeoDataFrame,
                    gyms_gdf: gpd.GeoDataFrame,
                    scored_gdf: gpd.GeoDataFrame,
                    oev_gdf: gpd.GeoDataFrame = None,
                    iso_gdf: gpd.GeoDataFrame = None,
                    filename: str = "interactive_map.html") -> str:
    """
    Erstellt eine interaktive Folium-Karte mit:
      - Choropleth des Standort-Scores
      - Fitnesscenter (geclustert)
      - ÖV-Haltestellen (optional)
      - Isochronen (optional)
      - Layer-Steuerung
    """
    # Zentrum Zürich
    center = [47.3769, 8.5417]
    m = folium.Map(location=center, zoom_start=12, tiles="CartoDB positron")

    # ── Choropleth: Standort-Score ──
    scored_wgs = scored_gdf.to_crs(CRS_WGS84).copy()
    scored_wgs["location_score_pct"] = (scored_wgs["location_score"] * 100).round(1)
    # Stabilen numerischen Schluessel fuer Choropleth erzeugen
    scored_wgs = scored_wgs.reset_index(drop=True)
    scored_wgs["__q_id__"] = scored_wgs.index.astype(str)

    choropleth = folium.Choropleth(
        geo_data=scored_wgs.to_json(),
        name="Standort-Score",
        data=scored_wgs,
        columns=["__q_id__", "location_score"],
        key_on="feature.properties.__q_id__",
        fill_color="RdYlGn",
        fill_opacity=0.65,
        line_opacity=0.3,
        legend_name="Standort-Score (0 = niedrig, 1 = hoch)",
        nan_fill_color="#CCCCCC",
    )
    choropleth.add_to(m)

    # Tooltip auf Quartiere
    for _, row in scored_wgs.iterrows():
        name   = row.get("quartier_name", "Quartier")
        score  = row.get("location_score", 0)
        popden = row.get("pop_density", 0)
        gyms_c = row.get("gyms_count", 0)
        tooltip_html = (
            f"<b>{name}</b><br>"
            f"Score: {score:.3f}<br>"
            f"Bevölkerungsdichte: {popden:.0f} Einw./km²<br>"
            f"Fitnesscenter: {int(gyms_c)}"
        )
        folium.GeoJson(
            row.geometry.__geo_interface__,
            style_function=lambda x: {"fillOpacity": 0, "weight": 0},
            tooltip=folium.Tooltip(tooltip_html),
        ).add_to(m)

    # ── Isochronen ──
    if iso_gdf is not None and len(iso_gdf) > 0:
        iso_layer = folium.FeatureGroup(name="Isochronen (Gehzeit)", show=True)
        iso_colors = {10: "#2A9D8F", 15: "#E9C46A"}
        for _, row in iso_gdf.to_crs(CRS_WGS84).iterrows():
            mins = row.get("walk_min", 10)
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda x, c=iso_colors.get(mins, "#AAAAAA"): {
                    "fillColor": c, "fillOpacity": 0.2,
                    "color": c, "weight": 1,
                },
                tooltip=f"{mins} Min. Einzugsgebiet",
            ).add_to(iso_layer)
        iso_layer.add_to(m)

    # ── ÖV-Haltestellen ──
    if oev_gdf is not None and len(oev_gdf) > 0:
        oev_layer = folium.FeatureGroup(name="ÖV-Haltestellen", show=False)
        for _, row in oev_gdf.to_crs(CRS_WGS84).iterrows():
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=3, color=COLOR_OEV, fill=True,
                fill_opacity=0.6, weight=0.5,
                tooltip=str(row.get("oev_type", "OEV")),
            ).add_to(oev_layer)
        oev_layer.add_to(m)

    # Fitnesscenter (geclustert)
    gym_layer   = folium.FeatureGroup(name="Fitnesscenter", show=True)
    gym_cluster = MarkerCluster(name="Cluster").add_to(gym_layer)
    for _, row in gyms_gdf.to_crs(CRS_WGS84).iterrows():
        name = row.get("name", "Unbekannt")
        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            popup=folium.Popup(f"<b>{name}</b>", max_width=200),
            tooltip=name,
            icon=folium.Icon(color="red", icon="heart", prefix="fa"),
        ).add_to(gym_cluster)
    gym_layer.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    # Speichern
    out_path = OUTPUT_MAPS / "interactive_map.html"
    m.save(str(out_path))
    print(f"  Interaktive Karte gespeichert: {out_path}")
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# 8. Regressions-Diagnostik-Plot
# ─────────────────────────────────────────────────────────────────────────────

def plot_regression_diagnostics(reg_result: dict,
                                 quarters_gdf=None) -> "plt.Figure":
    """
    Visualisiert OLS- und Spatial-Lag-Regressionsergebnisse als 4-Panel-Grafik.

    Panel 1: Residuenkarte (Choropleth)
    Panel 2: Fitted vs. Actual (Streudiagramm)
    Panel 3: Residuenhistogramm + Shapiro-Wilk-Test
    Panel 4: Koeffizientenvergleich OLS vs. Spatial Lag

    Parameters
    ----------
    reg_result : dict
        Ausgabe von compute_spatial_regression()
    quarters_gdf : gpd.GeoDataFrame, optional
        GeoDataFrame mit Quartiersgrenzen (fuer Karte)
    """
    import warnings
    warnings.filterwarnings("ignore")

    if not reg_result:
        print("  Keine Regressionsergebnisse vorhanden.")
        return None

    try:
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
        import numpy as np
        from scipy import stats
        import geopandas as gpd
    except ImportError as e:
        print(f"  Import-Fehler: {e}")
        return None

    fig = plt.figure(figsize=(16, 12))
    gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.30)

    ols_resid  = np.array(reg_result.get("ols_residuals", []))
    ols_coef   = reg_result.get("ols_coef",  [])
    lag_coef   = reg_result.get("lag_coef",  [])
    ols_r2     = reg_result.get("ols_r2",    0.0)
    lag_r2     = reg_result.get("lag_r2",    0.0)
    lag_rho    = reg_result.get("lag_rho",   0.0)

    # ── Panel 1: Residuenkarte ────────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, 0])
    gdf_r = reg_result.get("gdf_result")
    if gdf_r is not None and "ols_residual" in gdf_r.columns:
        try:
            gdf_web = gdf_r.to_crs("EPSG:3857")
            vmax = max(abs(gdf_web["ols_residual"].min()),
                       abs(gdf_web["ols_residual"].max()))
            gdf_web.plot(column="ols_residual", ax=ax1, cmap="RdBu_r",
                         vmin=-vmax, vmax=vmax, alpha=0.8, legend=True,
                         legend_kwds={"label": "OLS-Residuum", "shrink": 0.7},
                         edgecolor="white", linewidth=0.3)
            try:
                import contextily as ctx
                ctx.add_basemap(ax1, crs="EPSG:3857", zoom=11, alpha=0.4,
                                source=ctx.providers.CartoDB.Positron)
            except Exception:
                pass
        except Exception:
            ax1.text(0.5, 0.5, "Karte nicht verfuegbar", ha="center",
                     va="center", transform=ax1.transAxes)
    else:
        ax1.text(0.5, 0.5, "Keine Geometrie", ha="center", va="center",
                 transform=ax1.transAxes)
    ax1.set_title("OLS-Residuen nach Quartier\n(Rot = unterschaetzt, Blau = ueberschaetzt)",
                  fontsize=11, fontweight="bold")
    ax1.set_axis_off()

    # ── Panel 2: Fitted vs. Actual ────────────────────────────────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    if gdf_r is not None and "y_actual" in gdf_r.columns and "y_fitted" in gdf_r.columns:
        y_act = gdf_r["y_actual"].values
        y_fit = gdf_r["y_fitted"].values
        ax2.scatter(y_act, y_fit, alpha=0.7, edgecolor="white",
                    linewidth=0.5, s=60, c=ols_resid,
                    cmap="RdBu_r", vmin=-abs(ols_resid).max(),
                    vmax=abs(ols_resid).max())
        lim = max(y_act.max(), y_fit.max()) * 1.05
        ax2.plot([0, lim], [0, lim], "k--", lw=1, label="Perfekte Vorhersage")
        ax2.set_xlabel("Tatsaechliche Werte (gyms/km2)", fontsize=10)
        ax2.set_ylabel("Vorhergesagte Werte (OLS)", fontsize=10)
        ax2.set_title(f"Fitted vs. Actual\nOLS R2 = {ols_r2:.3f}", fontsize=11, fontweight="bold")
        ax2.legend(fontsize=9)
        ax2.grid(True, alpha=0.3)
    else:
        ax2.text(0.5, 0.5, "Daten nicht verfuegbar", ha="center", va="center",
                 transform=ax2.transAxes)

    # ── Panel 3: Residuen-Histogramm + Normalverteilungstest ─────────────────
    ax3 = fig.add_subplot(gs[1, 0])
    if len(ols_resid) > 0:
        ax3.hist(ols_resid, bins=min(15, len(ols_resid) // 2),
                 color="#457B9D", edgecolor="white", alpha=0.8, density=True)
        # Normalverteilungskurve
        x_norm = np.linspace(ols_resid.min(), ols_resid.max(), 100)
        ax3.plot(x_norm, stats.norm.pdf(x_norm, ols_resid.mean(), ols_resid.std()),
                 "r-", lw=2, label="Normalverteilung")
        # Shapiro-Wilk
        try:
            stat_sw, p_sw = stats.shapiro(ols_resid)
            sw_text = f"Shapiro-Wilk: W={stat_sw:.3f}, p={p_sw:.3f}"
            sw_color = "red" if p_sw < 0.05 else "green"
            ax3.text(0.97, 0.95, sw_text, transform=ax3.transAxes,
                     ha="right", va="top", fontsize=9,
                     color=sw_color,
                     bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.8))
        except Exception:
            pass
        ax3.axvline(0, color="black", lw=1, ls="--")
        ax3.set_xlabel("OLS-Residuum", fontsize=10)
        ax3.set_ylabel("Dichte", fontsize=10)
        ax3.set_title("Residuenverteilung\n(Normalverteilungstest)", fontsize=11, fontweight="bold")
        ax3.legend(fontsize=9)
        ax3.grid(True, alpha=0.3)

    # ── Panel 4: Koeffizientenvergleich OLS vs. Spatial Lag ──────────────────
    ax4 = fig.add_subplot(gs[1, 1])
    coef_names = ["Konstante", "Bev.dichte", "OEV-Stops", "Kaufkraft"]
    if len(ols_coef) >= len(coef_names) and len(lag_coef) > len(coef_names):
        ols_vals = list(ols_coef[:len(coef_names)])
        lag_vals = list(lag_coef[:len(coef_names)])
        x = np.arange(len(coef_names))
        w = 0.35
        bars_ols = ax4.bar(x - w/2, ols_vals, w, label=f"OLS (R2={ols_r2:.3f})",
                           color="#457B9D", alpha=0.85, edgecolor="white")
        bars_lag = ax4.bar(x + w/2, lag_vals, w,
                           label=f"Spatial Lag (rho={lag_rho:+.3f}, R2={lag_r2:.3f})",
                           color="#E63946", alpha=0.85, edgecolor="white")
        ax4.axhline(0, color="black", lw=0.8)
        ax4.set_xticks(x)
        ax4.set_xticklabels(coef_names, fontsize=9)
        ax4.set_ylabel("Koeffizientenwert", fontsize=10)
        ax4.set_title("Koeffizientenvergleich\nOLS vs. Spatial Lag Model", fontsize=11, fontweight="bold")
        ax4.legend(fontsize=9)
        ax4.grid(True, alpha=0.3, axis="y")
    else:
        ax4.text(0.5, 0.5, "Koeffizienten nicht verfuegbar", ha="center",
                 va="center", transform=ax4.transAxes)

    plt.suptitle("Raeumliche Regression: Diagnostik-Uebersicht",
                 fontsize=14, fontweight="bold", y=1.01)

    try:
        fig.savefig(OUTPUT_FIGS / "06_spatial_regression.png",
                    dpi=DPI, bbox_inches="tight")
        print("  Gespeichert: 06_spatial_regression.png")
    except Exception as e:
        print(f"  Speichern fehlgeschlagen: {e}")

    return fig
