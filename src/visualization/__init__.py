"""
Visualization package for Folium maps and Plotly charts.
"""

from src.visualization.map_view import (
    create_andalucia_fishing_map,
    get_score_color,
    get_spot_type_icon,
    get_display_score_for_mode,
    render_spot_popup_html,
)
from src.visualization.charts import (
    create_pressure_and_score_chart,
    create_marine_and_wind_chart,
    create_score_radar_chart,
    create_species_comparison_chart,
    create_top_spots_bar_chart,
)

__all__ = [
    "create_andalucia_fishing_map",
    "get_score_color",
    "get_spot_type_icon",
    "get_display_score_for_mode",
    "render_spot_popup_html",
    "create_pressure_and_score_chart",
    "create_marine_and_wind_chart",
    "create_score_radar_chart",
    "create_species_comparison_chart",
    "create_top_spots_bar_chart",
]
