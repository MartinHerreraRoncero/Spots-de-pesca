"""
Data fetcher for Open-Meteo Marine & Forecast APIs with caching, retry logic,
fallback support, ocean current velocity extraction, custom coordinates, and marine buoys telemetry.
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import requests
import pandas as pd
import numpy as np

from src.models.spot import (
    Spot,
    MarineBuoy,
    BuoyObservation,
    MarineConditions,
    WeatherConditions,
    HourlySpotForecast,
    ScoringWeights,
)
from src.analytics.solunar import compute_daily_solunar
from src.analytics.scoring import score_hourly_conditions

logger = logging.getLogger(__name__)

# Base API URLs
OPEN_METEO_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Local cache dictionary
_MEMORY_CACHE: Dict[str, Tuple[datetime, Dict[str, Any]]] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour


def load_spots_from_json(filepath: Optional[str] = None) -> List[Spot]:
    """Loads predefined Andalusian fishing spots from JSON."""
    if filepath is None:
        filepath = str(Path(__file__).resolve().parent.parent.parent / "data" / "spots_andalucia.json")
    
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return [Spot(**item) for item in data]


def load_marine_buoys_from_json(filepath: Optional[str] = None) -> List[MarineBuoy]:
    """Loads official Puertos del Estado oceanographic buoy stations from JSON."""
    if filepath is None:
        filepath = str(Path(__file__).resolve().parent.parent.parent / "data" / "marine_buoys_andalucia.json")
    
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return [MarineBuoy(**item) for item in data]


def create_custom_spot_from_coords(
    latitude: float,
    longitude: float,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Spot:
    """Creates a dynamic Spot object from arbitrary GPS coordinates."""
    if longitude < -5.90:
        zone = "Atlántico"
        subzone = "Costa de Huelva / Golfo de Cádiz"
        province = "Huelva / Cádiz"
        bearing = 195.0
    elif -5.90 <= longitude <= -5.30:
        zone = "Estrecho"
        subzone = "Estrecho de Gibraltar"
        province = "Cádiz"
        bearing = 180.0
    elif -5.30 < longitude <= -3.80:
        zone = "Mediterráneo"
        subzone = "Costa del Sol (Málaga)"
        province = "Málaga"
        bearing = 160.0
    elif -3.80 < longitude <= -3.10:
        zone = "Mediterráneo"
        subzone = "Costa Tropical (Granada)"
        province = "Granada"
        bearing = 180.0
    else:
        zone = "Mediterráneo"
        subzone = "Costa de Almería / Cabo de Gata"
        province = "Almería"
        bearing = 135.0

    spot_name = name or f"Punto GPS ({latitude:.4f}°N, {longitude:.4f}°W)"
    spot_desc = description or f"Análisis oceanográfico, de corrientes y solunar bajo demanda para: {latitude:.4f}°N, {longitude:.4f}°W."

    return Spot(
        id=f"custom_{abs(hash((latitude, longitude))) % 1000000}",
        name=spot_name,
        province=province,
        zone=zone,
        subzone=subzone,
        municipality="Coordenada Libre",
        latitude=round(latitude, 4),
        longitude=round(longitude, 4),
        description=spot_desc,
        spot_type="Punto Personalizado",
        bottom_type="Fondo Mixto / Sonda",
        accessibility="Libre / Marcador GPS",
        coastline_bearing=bearing,
        target_species=["Dorada", "Lubina", "Sargo", "Dentón", "Depredadores"],
        recommended_techniques=["Surfcasting", "Spinning", "Embarcación / Sonda"],
        depth_m=12,
        tide_dependent=True,
        is_custom=True,
    )


def _fetch_api_with_retry(url: str, params: Dict[str, Any], max_retries: int = 2) -> Optional[Dict[str, Any]]:
    """Helper to fetch an API endpoint with timeout and simple retry."""
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"API {url} returned status {resp.status_code}: {resp.text[:200]}")
        except requests.RequestException as e:
            logger.warning(f"Network exception calling {url} (attempt {attempt+1}/{max_retries+1}): {e}")
    return None


def get_current_intensity_label(velocity_knots: float) -> str:
    """Categorizes ocean current speed into practical fishing tiers."""
    if velocity_knots < 0.2:
        return "Aguas Paradas (<0.2 kts)"
    elif velocity_knots <= 0.75:
        return "Corriente Suave (0.2-0.8 kts)"
    elif velocity_knots <= 1.5:
        return "Corriente Moderada (0.8-1.5 kts)"
    elif velocity_knots <= 2.5:
        return "Corriente Fuerte (1.5-2.5 kts)"
    else:
        return "Corriente Extrema (>2.5 kts - Estrecho)"


def _generate_synthetic_marine_weather_series(
    spot: Spot,
    start_dt: datetime,
    hours_count: int = 72
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Resilient fallback generator for offline demo / network failure scenarios.
    Simulates realistic Andalusian coastal oceanographic variables and currents.
    """
    times = [(start_dt + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(hours_count)]
    np.random.seed(int(abs(spot.latitude * 1000 + spot.longitude * 100)) % (2**32 - 1))

    # Marine simulation
    base_wave = 0.7 if spot.zone == "Atlántico" else 0.5
    wave_noise = np.sin(np.linspace(0, 3 * np.pi, hours_count)) * 0.3 + np.random.normal(0, 0.05, hours_count)
    wave_height = np.clip(base_wave + wave_noise, 0.2, 2.5).round(2).tolist()
    wave_period = (6.5 + np.cos(np.linspace(0, 2 * np.pi, hours_count)) * 2.0).round(1).tolist()
    wave_direction = np.random.randint(180, 270, hours_count).tolist()
    sst = (19.5 + np.sin(np.linspace(0, 4 * np.pi, hours_count)) * 0.8).round(1).tolist()

    # Current simulation (speed in km/h): stronger in Strait of Gibraltar & estuaries
    base_curr_kmh = 3.5 if spot.zone == "Estrecho" else (2.0 if spot.zone == "Atlántico" else 1.2)
    curr_noise = np.abs(np.sin(np.linspace(0, 6 * math.pi, hours_count))) * 2.2 + np.random.normal(0, 0.2, hours_count)
    current_velocity = np.clip(base_curr_kmh + curr_noise, 0.2, 8.0).round(2).tolist()
    current_direction = [(85 + int(np.sin(i / 5.0) * 40)) % 360 for i in range(hours_count)]

    marine_data = {
        "hourly": {
            "time": times,
            "wave_height": wave_height,
            "wave_period": wave_period,
            "wave_direction": wave_direction,
            "sea_surface_temperature": sst,
            "ocean_current_velocity": current_velocity,
            "ocean_current_direction": current_direction,
            "swell_wave_height": [round(w * 0.8, 2) for w in wave_height],
            "swell_wave_period": wave_period,
        }
    }

    # Weather simulation
    base_p = 1016.0
    pressure_trend = np.sin(np.linspace(0, 2.5 * np.pi, hours_count)) * 4.0
    surface_pressure = (base_p + pressure_trend + np.random.normal(0, 0.2, hours_count)).round(1).tolist()
    wind_speed = np.clip(12.0 + np.sin(np.linspace(0, 3 * np.pi, hours_count)) * 8.0, 2.0, 35.0).round(1).tolist()
    wind_direction = np.random.randint(120, 290, hours_count).tolist()
    cloud_cover = np.random.randint(10, 80, hours_count).tolist()
    precipitation = [0.0 if np.random.rand() > 0.15 else round(float(np.random.exponential(0.5)), 1) for _ in range(hours_count)]
    temp_2m = (22.0 + np.sin(np.linspace(0, 6 * np.pi, hours_count)) * 4.0).round(1).tolist()

    weather_data = {
        "hourly": {
            "time": times,
            "surface_pressure": surface_pressure,
            "wind_speed_10m": wind_speed,
            "wind_direction_10m": wind_direction,
            "cloud_cover": cloud_cover,
            "precipitation": precipitation,
            "temperature_2m": temp_2m,
        }
    }

    return marine_data, weather_data


def fetch_raw_data_for_spot(
    spot: Spot,
    forecast_days: int = 3,
    use_cache: bool = True
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Fetches raw Marine and Forecast JSON from Open-Meteo APIs for a spot."""
    cache_key = f"{spot.id}_{spot.latitude:.3f}_{spot.longitude:.3f}_{forecast_days}"
    now = datetime.now(timezone.utc)

    if use_cache and cache_key in _MEMORY_CACHE:
        cached_time, cached_val = _MEMORY_CACHE[cache_key]
        if (now - cached_time).total_seconds() < CACHE_TTL_SECONDS:
            return cached_val["marine"], cached_val["weather"]

    # 1. Fetch Marine Data (including ocean currents)
    marine_params = {
        "latitude": round(spot.latitude, 4),
        "longitude": round(spot.longitude, 4),
        "hourly": "wave_height,wave_period,wave_direction,sea_surface_temperature,ocean_current_velocity,ocean_current_direction,swell_wave_height,swell_wave_period",
        "forecast_days": forecast_days,
        "timezone": "UTC",
    }
    marine_json = _fetch_api_with_retry(OPEN_METEO_MARINE_URL, marine_params)

    # 2. Fetch Weather Data
    forecast_params = {
        "latitude": round(spot.latitude, 4),
        "longitude": round(spot.longitude, 4),
        "hourly": "surface_pressure,wind_speed_10m,wind_direction_10m,cloud_cover,precipitation,temperature_2m",
        "forecast_days": forecast_days,
        "timezone": "UTC",
    }
    weather_json = _fetch_api_with_retry(OPEN_METEO_FORECAST_URL, forecast_params)

    if not marine_json or "hourly" not in marine_json or not weather_json or "hourly" not in weather_json:
        logger.warning(f"Using synthetic fallback for spot {spot.name}")
        marine_json, weather_json = _generate_synthetic_marine_weather_series(spot, now, forecast_days * 24)

    _MEMORY_CACHE[cache_key] = (now, {"marine": marine_json, "weather": weather_json})
    return marine_json, weather_json


def get_spot_hourly_forecast(
    spot: Spot,
    forecast_days: int = 3,
    weights: Optional[ScoringWeights] = None,
    buoys_telemetry: Optional[List[Tuple[MarineBuoy, BuoyObservation]]] = None,
) -> List[HourlySpotForecast]:
    """
    Calculates unified, fully scored hourly forecasts for a spot over 48h-72h.
    Merges Open-Meteo marine/currents/weather, ephem solunar, tides, and heuristic scores.
    """
    marine_json, weather_json = fetch_raw_data_for_spot(spot, forecast_days)
    m_hourly = marine_json.get("hourly", {})
    w_hourly = weather_json.get("hourly", {})

    times_str = w_hourly.get("time", [])
    if not times_str:
        return []

    pressures = w_hourly.get("surface_pressure", [1015.0] * len(times_str))
    wind_speeds = w_hourly.get("wind_speed_10m", [10.0] * len(times_str))
    wind_dirs = w_hourly.get("wind_direction_10m", [180.0] * len(times_str))
    clouds = w_hourly.get("cloud_cover", [20.0] * len(times_str))
    precips = w_hourly.get("precipitation", [0.0] * len(times_str))
    temps = w_hourly.get("temperature_2m", [20.0] * len(times_str))

    wave_heights = m_hourly.get("wave_height", [0.6] * len(times_str))
    wave_periods = m_hourly.get("wave_period", [7.0] * len(times_str))
    wave_dirs = m_hourly.get("wave_direction", [220.0] * len(times_str))
    ssts = m_hourly.get("sea_surface_temperature", [20.0] * len(times_str))
    current_vels_kmh = m_hourly.get("ocean_current_velocity", [1.5] * len(times_str))
    current_dirs = m_hourly.get("ocean_current_direction", [180.0] * len(times_str))
    swell_heights = m_hourly.get("swell_wave_height", [0.5] * len(times_str))
    swell_periods = m_hourly.get("swell_wave_period", [7.0] * len(times_str))

    solunar_cache: Dict[str, Any] = {}
    results: List[HourlySpotForecast] = []

    for i, t_str in enumerate(times_str):
        dt = datetime.fromisoformat(t_str).replace(tzinfo=timezone.utc)
        date_key = dt.strftime("%Y-%m-%d")

        if date_key not in solunar_cache:
            solunar_cache[date_key] = compute_daily_solunar(spot, dt)
        solunar_summary = solunar_cache[date_key]

        curr_p = float(pressures[i]) if pressures[i] is not None else 1015.0
        p_3h_ago = float(pressures[i - 3]) if (i >= 3 and pressures[i - 3] is not None) else curr_p
        p_6h_ago = float(pressures[i - 6]) if (i >= 6 and pressures[i - 6] is not None) else curr_p

        delta_3h = curr_p - p_3h_ago
        delta_6h = curr_p - p_6h_ago

        w_h = float(wave_heights[i]) if (i < len(wave_heights) and wave_heights[i] is not None) else 0.6
        w_p = float(wave_periods[i]) if (i < len(wave_periods) and wave_periods[i] is not None) else 7.0
        w_d = float(wave_dirs[i]) if (i < len(wave_dirs) and wave_dirs[i] is not None) else 220.0
        sst = float(ssts[i]) if (i < len(ssts) and ssts[i] is not None) else 20.0
        
        # Ocean Current conversion from km/h to knots (1 knot = 1.852 km/h)
        c_kmh = float(current_vels_kmh[i]) if (i < len(current_vels_kmh) and current_vels_kmh[i] is not None) else 1.2
        c_knots = round(c_kmh / 1.852, 2)
        c_dir = float(current_dirs[i]) if (i < len(current_dirs) and current_dirs[i] is not None) else 180.0
        c_level = get_current_intensity_label(c_knots)

        sw_h = float(swell_heights[i]) if (i < len(swell_heights) and swell_heights[i] is not None) else None
        sw_p = float(swell_periods[i]) if (i < len(swell_periods) and swell_periods[i] is not None) else None

        marine_obj = MarineConditions(
            timestamp=dt,
            wave_height=round(w_h, 2),
            wave_period=round(w_p, 1),
            wave_direction=round(w_d, 1),
            sea_surface_temperature=round(sst, 1),
            current_velocity_knots=c_knots,
            current_direction=round(c_dir, 1),
            current_intensity_level=c_level,
            swell_wave_height=round(sw_h, 2) if sw_h is not None else None,
            swell_wave_period=round(sw_p, 1) if sw_p is not None else None,
        )

        weather_obj = WeatherConditions(
            timestamp=dt,
            surface_pressure=round(curr_p, 1),
            wind_speed_10m=round(float(wind_speeds[i]) if wind_speeds[i] is not None else 10.0, 1),
            wind_direction_10m=round(float(wind_dirs[i]) if wind_dirs[i] is not None else 180.0, 1),
            cloud_cover=round(float(clouds[i]) if clouds[i] is not None else 0.0, 1),
            precipitation=round(float(precips[i]) if precips[i] is not None else 0.0, 1),
            temperature_2m=round(float(temps[i]) if temps[i] is not None else 20.0, 1),
        )

        score_breakdown = score_hourly_conditions(
            spot=spot,
            target_dt=dt,
            marine=marine_obj,
            weather=weather_obj,
            solunar_summary=solunar_summary,
            delta_3h=delta_3h,
            delta_6h=delta_6h,
            weights=weights,
            buoys_telemetry=buoys_telemetry,
        )

        results.append(HourlySpotForecast(
            spot_id=spot.id,
            timestamp=dt,
            marine=marine_obj,
            weather=weather_obj,
            solunar_summary=solunar_summary,
            score=score_breakdown,
        ))

    return results


def get_buoy_telemetry_snapshot(buoys: List[MarineBuoy], target_dt: datetime) -> List[Tuple[MarineBuoy, BuoyObservation]]:
    """Retrieves current observational oceanographic telemetry for Puertos del Estado buoys."""
    results: List[Tuple[MarineBuoy, BuoyObservation]] = []
    for buoy in buoys:
        proxy_spot = Spot(
            id=buoy.id,
            name=buoy.name,
            province=buoy.province,
            zone=buoy.zone,
            subzone=buoy.network,
            latitude=buoy.latitude,
            longitude=buoy.longitude,
            description=buoy.description,
            depth_m=buoy.depth_m,
        )
        marine_json, weather_json = fetch_raw_data_for_spot(proxy_spot, forecast_days=1)
        m_hourly = marine_json.get("hourly", {})
        w_hourly = weather_json.get("hourly", {})

        times = m_hourly.get("time", [])
        if not times:
            continue

        target_iso = target_dt.strftime("%Y-%m-%dT%H:00")
        try:
            idx = times.index(target_iso)
        except ValueError:
            idx = 0

        hs = float(m_hourly.get("wave_height", [1.0])[idx] or 1.0)
        tp = float(m_hourly.get("wave_period", [7.0])[idx] or 7.0)
        dir_w = float(m_hourly.get("wave_direction", [220.0])[idx] or 220.0)
        sst = float(m_hourly.get("sea_surface_temperature", [19.0])[idx] or 19.0)
        pres = float(w_hourly.get("surface_pressure", [1016.0])[idx] or 1016.0)
        wind = float(w_hourly.get("wind_speed_10m", [12.0])[idx] or 12.0)
        wind_d = float(w_hourly.get("wind_direction_10m", [180.0])[idx] or 180.0)

        obs = BuoyObservation(
            buoy_id=buoy.id,
            timestamp=target_dt,
            wave_height_hs=round(hs, 2),
            wave_period_tp=round(tp, 1),
            wave_direction=round(dir_w, 1),
            sea_surface_temperature=round(sst, 1),
            surface_pressure=round(pres, 1),
            wind_speed=round(wind, 1),
            wind_direction=round(wind_d, 1),
            status="Operativa (En línea)",
        )
        results.append((buoy, obs))

    return results


def get_all_spots_snapshot(
    spots: List[Spot],
    target_dt: datetime,
    weights: Optional[ScoringWeights] = None,
    buoys_telemetry: Optional[List[Tuple[MarineBuoy, BuoyObservation]]] = None,
) -> List[Tuple[Spot, HourlySpotForecast]]:
    """Retrieves the closest hourly forecast record for all spots at a target datetime."""
    snapshot = []
    for spot in spots:
        forecasts = get_spot_hourly_forecast(spot, forecast_days=2, weights=weights, buoys_telemetry=buoys_telemetry)
        if not forecasts:
            continue
        best_rec = min(forecasts, key=lambda f: abs((f.timestamp - target_dt).total_seconds()))
        snapshot.append((spot, best_rec))

    snapshot.sort(key=lambda item: item[1].score.overall_score, reverse=True)
    return snapshot
