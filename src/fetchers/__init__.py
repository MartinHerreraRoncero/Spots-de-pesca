"""
Data fetchers package for Open-Meteo, custom coordinates, and oceanographic buoys.
"""

from src.fetchers.open_meteo import (
    load_spots_from_json,
    load_marine_buoys_from_json,
    create_custom_spot_from_coords,
    fetch_raw_data_for_spot,
    get_spot_hourly_forecast,
    get_all_spots_snapshot,
    get_buoy_telemetry_snapshot,
)

__all__ = [
    "load_spots_from_json",
    "load_marine_buoys_from_json",
    "create_custom_spot_from_coords",
    "fetch_raw_data_for_spot",
    "get_spot_hourly_forecast",
    "get_all_spots_snapshot",
    "get_buoy_telemetry_snapshot",
]
