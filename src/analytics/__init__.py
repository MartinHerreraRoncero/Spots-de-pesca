"""
Analytics package: solunar calculations, tides, wind aspect, bathymetry,
water clarity, river plumes, and marine multi-species scoring.
"""

from src.analytics.solunar import (
    get_moon_phase_info,
    compute_daily_solunar,
    evaluate_solunar_for_hour,
)
from src.analytics.tides import (
    calculate_tide_coefficient,
    compute_spot_tide_state,
)
from src.analytics.bathymetry import (
    calculate_bathymetry_profile,
)
from src.analytics.satellite_ocean import (
    compute_water_clarity_and_fronts,
)
from src.analytics.river_runoff import (
    load_rivers_catalog,
    compute_river_runoff_impact,
)
from src.analytics.scoring import (
    calculate_wind_relative_aspect,
    apply_buoy_bias_correction,
    calculate_pressure_score,
    calculate_marine_score,
    calculate_wind_score,
    calculate_species_scores,
    score_hourly_conditions,
)
from src.analytics.poza_detection import (
    load_pozas_from_json,
    compute_stumpf_sdb_ratio,
    evaluate_poza_fishability,
    filter_pozas,
    sync_pozas_with_satellite_pass,
    contrast_multi_temporal_pozas,
)
from src.analytics.coastline import (
    compute_ndwi,
    compute_mndwi,
    get_shoreline_lat_at_lon,
    is_in_ocean,
    calculate_distance_to_shore_m,
    project_seaward_point,
    enforce_marine_bounds,
    get_huelva_shoreline_folium_coords,
    HUELVA_SHORELINE_VERTICES,
)

__all__ = [
    "get_moon_phase_info",
    "compute_daily_solunar",
    "evaluate_solunar_for_hour",
    "calculate_tide_coefficient",
    "compute_spot_tide_state",
    "calculate_bathymetry_profile",
    "compute_water_clarity_and_fronts",
    "load_rivers_catalog",
    "compute_river_runoff_impact",
    "calculate_wind_relative_aspect",
    "apply_buoy_bias_correction",
    "calculate_pressure_score",
    "calculate_marine_score",
    "calculate_wind_score",
    "calculate_species_scores",
    "score_hourly_conditions",
    "load_pozas_from_json",
    "compute_stumpf_sdb_ratio",
    "evaluate_poza_fishability",
    "filter_pozas",
    "sync_pozas_with_satellite_pass",
    "contrast_multi_temporal_pozas",
    "compute_ndwi",
    "compute_mndwi",
    "get_shoreline_lat_at_lon",
    "is_in_ocean",
    "calculate_distance_to_shore_m",
    "project_seaward_point",
    "enforce_marine_bounds",
    "get_huelva_shoreline_folium_coords",
    "HUELVA_SHORELINE_VERTICES",
]

