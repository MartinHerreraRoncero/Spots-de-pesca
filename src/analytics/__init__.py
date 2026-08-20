"""
Analytics package: solunar calculations, tides, wind aspect, and marine multi-species scoring.
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
from src.analytics.scoring import (
    calculate_wind_relative_aspect,
    apply_buoy_bias_correction,
    calculate_pressure_score,
    calculate_marine_score,
    calculate_wind_score,
    calculate_species_scores,
    score_hourly_conditions,
)

__all__ = [
    "get_moon_phase_info",
    "compute_daily_solunar",
    "evaluate_solunar_for_hour",
    "calculate_tide_coefficient",
    "compute_spot_tide_state",
    "calculate_wind_relative_aspect",
    "apply_buoy_bias_correction",
    "calculate_pressure_score",
    "calculate_marine_score",
    "calculate_wind_score",
    "calculate_species_scores",
    "score_hourly_conditions",
]
