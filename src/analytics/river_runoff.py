"""
River runoff, estuary hydrological modeling, and freshwater plume analytics for Andalusian fishing spots.
Evaluates proximity to major river basins, salinity drop, and ecological impact on fish species.
"""

from __future__ import annotations
import json
import math
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from src.models.spot import Spot, WeatherConditions, RiverRunoffConditions

_RIVERS_CACHE: Optional[List[Dict[str, Any]]] = None


def load_rivers_catalog() -> List[Dict[str, Any]]:
    """Loads Andalusian river mouths catalog."""
    global _RIVERS_CACHE
    if _RIVERS_CACHE is None:
        path = Path(__file__).resolve().parent.parent.parent / "data" / "rivers_andalucia.json"
        with open(path, "r", encoding="utf-8") as f:
            _RIVERS_CACHE = json.load(f)
    return _RIVERS_CACHE


def compute_river_runoff_impact(
    spot: Spot,
    weather: WeatherConditions,
    precipitation_72h_mm: Optional[float] = None
) -> RiverRunoffConditions:
    """
    Computes proximity to closest river mouth, estuarine discharge,
    freshwater/sediment plume coverage, and salinity drop in PSU.
    """
    rivers = load_rivers_catalog()
    
    # 1. Find Closest River Mouth
    closest_river = None
    min_dist_km = 9999.0

    for r in rivers:
        dlat = (spot.latitude - r["mouth_latitude"]) * 111.0
        dlon = (spot.longitude - r["mouth_longitude"]) * 111.0 * math.cos(math.radians(spot.latitude))
        dist = math.sqrt(dlat**2 + dlon**2)
        if dist < min_dist_km:
            min_dist_km = dist
            closest_river = r

    if not closest_river:
        return RiverRunoffConditions(
            nearest_river_name="Sin desembocadura cercana",
            distance_to_mouth_km=99.0,
            basin_rain_72h_mm=0.0,
            plume_active=False,
            salinity_drop_psu=0.0,
            plume_impact_summary="Sin influencia fluvial relevante.",
        )

    # 2. Basin Rainfall & Discharge Dynamics
    # Estimate recent basin rainfall from local precipitation proxy
    rain_val = precipitation_72h_mm if precipitation_72h_mm is not None else (weather.precipitation * 6.0)
    basin_rain = max(0.0, min(120.0, rain_val + 2.0))

    # Base plume reach expanded by recent rain
    base_reach = closest_river.get("plume_reach_km", 8.0)
    rain_expansion_factor = 1.0 + min(1.8, (basin_rain / 30.0))
    effective_plume_reach = base_reach * rain_expansion_factor

    plume_active = (min_dist_km <= effective_plume_reach)

    # 3. Salinity Drop (PSU)
    # Seawater standard is ~37.0 PSU. In river plumes, salinity can drop by 2 to 18 PSU.
    if plume_active:
        proximity_ratio = 1.0 - (min_dist_km / effective_plume_reach)
        discharge_scale = min(2.5, closest_river.get("avg_discharge_m3s", 10.0) / 30.0)
        salinity_drop = round(proximity_ratio * (4.0 + (basin_rain / 8.0)) * discharge_scale, 1)
        salinity_drop = min(22.0, max(0.5, salinity_drop))
        
        if salinity_drop >= 8.0:
            impact_desc = f"🌊 Pluma fluvial intensa de {closest_river['name']}: choque osmótico, agua tomada rica en detritos. Muy favorable para lubina y corvina; perjudicial para calamar."
        else:
            impact_desc = f"🌊 Pluma activa de {closest_river['name']}: aporte moderado de nutrientes y agua dulce que oxigena y remueve el estuario."
    else:
        salinity_drop = 0.0
        impact_desc = f"Fuera de la pluma directa de {closest_river['name']} ({min_dist_km:.1f} km). Aguas con salinidad oceánica normal."

    return RiverRunoffConditions(
        nearest_river_name=closest_river["name"],
        distance_to_mouth_km=round(min_dist_km, 1),
        basin_rain_72h_mm=round(basin_rain, 1),
        plume_active=plume_active,
        salinity_drop_psu=salinity_drop,
        plume_impact_summary=impact_desc,
    )
