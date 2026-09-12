"""
Satellite oceanographic analytics: thermal front detection (SST gradients)
and bio-optical water clarity / turbidity / Secchi depth estimation for Andalusian spots.
"""

from __future__ import annotations
import math
from typing import Optional, List, Tuple
from src.models.spot import Spot, MarineConditions, WeatherConditions, WaterClarityConditions, MarineBuoy, BuoyObservation


def compute_water_clarity_and_fronts(
    spot: Spot,
    marine: MarineConditions,
    weather: WeatherConditions,
    buoys_telemetry: Optional[List[Tuple[MarineBuoy, BuoyObservation]]] = None
) -> WaterClarityConditions:
    """
    Evaluates bio-optical water transparency (Secchi depth in meters, turbidity in NTU)
    and satellite sea surface temperature (SST) spatial thermal fronts.
    """
    wave_h = marine.wave_height
    wave_p = marine.wave_period
    wind_spd = weather.wind_speed_10m
    precip = weather.precipitation
    depth = spot.depth_m if spot.depth_m is not None else 8.0
    sst = marine.sea_surface_temperature

    # 1. Bio-optical Turbidity (NTU) Model
    # Resuspension is strong in shallow sandy bottoms with high wave energy
    # Bottom factor: sand/mud suspends much more easily than rock/deep shelves
    if "Fango" in spot.bottom_type:
        bottom_factor = 2.4
    elif "Arena" in spot.bottom_type:
        bottom_factor = 1.8
    elif "Cascajo" in spot.bottom_type:
        bottom_factor = 1.1
    elif "Posidonia" in spot.bottom_type:
        bottom_factor = 0.7  # Posidonia stabilizes sediment
    else:  # Roca / Roquedo
        bottom_factor = 0.5

    # Depth attenuation: shallow spots (<5m) stir up instantly; deep spots (>15m) stay clear
    depth_resuspension_damping = max(0.2, min(1.0, 6.0 / max(2.0, depth)))

    # Wave & Wind stirring energy
    wave_stirring = (wave_h ** 1.6) * (wave_p / 6.0) * 3.2
    wind_stirring = (wind_spd / 15.0) * 1.5
    rain_runoff_clouding = min(8.0, precip * 3.5)

    base_turbidity = 1.0  # Clean baseline open ocean
    turbidity_ntu = base_turbidity + (wave_stirring + wind_stirring) * bottom_factor * depth_resuspension_damping + rain_runoff_clouding
    turbidity_ntu = round(max(0.4, min(35.0, turbidity_ntu)), 1)

    # 2. Secchi Transparency Depth (meters)
    # Secchi depth is inversely proportional to turbidity & attenuation: Secchi ~ 14 / (NTU^0.75)
    secchi_m = round(max(0.4, min(14.0, 16.0 / (turbidity_ntu ** 0.65))), 1)

    # 3. Water Clarity Classification
    if turbidity_ntu >= 12.0 or secchi_m <= 1.2:
        clarity_class = "Agua Tomada (Chocolate)"
    elif turbidity_ntu >= 4.5 or secchi_m <= 2.8:
        clarity_class = "Agua Rizada / Nutrientes"
    elif turbidity_ntu >= 1.8 or secchi_m <= 6.5:
        clarity_class = "Agua Clara Turquesa"
    else:
        clarity_class = "Agua Azul Cristalina"

    # 4. Satellite SST Thermal Front Detection (Choque de masas de agua)
    # Compare spot SST with regional baseline or closest buoys
    sst_grad_c_km = 0.02  # standard baseline
    thermal_front = False
    convergence = False

    if buoys_telemetry:
        # Find SST variance against nearest buoy
        closest_b_diff = 0.0
        min_dist = 9999.0
        for b, obs in buoys_telemetry:
            dlat = (spot.latitude - b.latitude) * 111.0
            dlon = (spot.longitude - b.longitude) * 111.0 * math.cos(math.radians(spot.latitude))
            dist = math.sqrt(dlat**2 + dlon**2)
            if dist < min_dist:
                min_dist = dist
                closest_b_diff = abs(sst - obs.sea_surface_temperature)

        if min_dist > 0.1:
            sst_grad_c_km = round(closest_b_diff / min_dist, 3)

    # In Strait of Gibraltar or Alborán upwelling, thermal gradients frequently exceed 0.06 °C/km
    if spot.zone == "Estrecho" or sst_grad_c_km >= 0.05 or ("Granada" in spot.subzone and wind_spd > 15):
        thermal_front = True
        convergence = True
        if sst_grad_c_km < 0.06:
            sst_grad_c_km = 0.075

    return WaterClarityConditions(
        secchi_depth_m=secchi_m,
        turbidity_ntu=turbidity_ntu,
        clarity_class=clarity_class,
        thermal_front_detected=thermal_front,
        sst_gradient_c_km=round(sst_grad_c_km, 3),
        convergence_zone=convergence,
    )
