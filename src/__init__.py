"""
src – Hilfsfunktionen für Standortanalyse Fitnesscenter Zürich
ZHAW FS2026 | Einsatz von Geodaten im Marketing
"""
from .data_loader import (
    load_city_boundary,
    load_fitness_centers,
    load_oev_stops,
    load_statistical_quarters,
    load_population_data,
    merge_quarters_population,
    geocode_addresses,
    load_income_by_quarter,
    merge_quarters_income,
)
from .spatial_analysis import (
    compute_isochrones,
    compute_oev_score,
    compute_competition_score,
    compute_location_score,
    compute_morans_i,
    compute_spatial_regression,
)
from .visualization import (
    # Öffentliche Hilfsfunktionen (direkt im Notebook nutzbar)
    add_basemap,
    add_north_arrow,
    # Plotfunktionen
    plot_city_with_gyms,
    plot_choropleth,
    plot_isochrones,
    plot_score_map,
    plot_morans_scatter,
    save_folium_map,
    plot_regression_diagnostics,
)

__all__ = [
    # data_loader
    "load_city_boundary", "load_fitness_centers", "load_oev_stops",
    "load_statistical_quarters", "load_population_data", "merge_quarters_population",
    "geocode_addresses", "load_income_by_quarter", "merge_quarters_income",
    # spatial_analysis
    "compute_isochrones", "compute_oev_score", "compute_competition_score",
    "compute_location_score", "compute_morans_i", "compute_spatial_regression",
    # visualization – Hilfsfunktionen
    "add_basemap", "add_north_arrow",
    # visualization – Plots
    "plot_city_with_gyms", "plot_choropleth", "plot_isochrones",
    "plot_score_map", "plot_morans_scatter", "save_folium_map",
    "plot_regression_diagnostics",
]
