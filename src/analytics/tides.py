"""
Astronomical and hydraulic tidal analytics for Andalusian coastal spots.
Computes tidal coefficients (20-120), high/low tide timings, and slack water slack periods.
"""

from __future__ import annotations
import math
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional

from src.models.spot import Spot, TideState, SolunarDaySummary


def calculate_tide_coefficient(moon_age_days: float, moon_illumination: float) -> int:
    """
    Calculates the Spanish maritime tide coefficient (20 - 120 scale).
    - Springs (Mareas Vivas / Sicigias): 90 - 118 (New & Full Moon).
    - Neaps (Mareas Muertas / Cuadraturas): 25 - 45 (First & Third Quarter).
    """
    # Angle in synodic cycle (0 at new moon, pi at full moon, 2pi at next new moon)
    cycle_rad = 2.0 * math.pi * ((moon_age_days % 29.53) / 29.53)
    
    # Base coefficient oscillates with 2*cycle_rad (semimonthly cycle)
    # Cosine is +1 at new moon and full moon, -1 at quarters
    cos_val = math.cos(2.0 * cycle_rad)
    
    # Map [-1, 1] to [32, 108] with slight illumination weighting
    coef = 70.0 + (38.0 * cos_val) + (4.0 * (moon_illumination / 100.0 - 0.5))
    return int(max(20, min(120, round(coef))))


def compute_spot_tide_state(
    spot: Spot,
    target_dt: datetime,
    solunar_summary: SolunarDaySummary
) -> TideState:
    """
    Computes tidal phase, high/low water timing, and minutes to slack for a spot and hour.
    """
    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=timezone.utc)

    # 1. Tidal coefficient
    coef = calculate_tide_coefficient(solunar_summary.moon_age_days, solunar_summary.moon_illumination)

    # 2. Reference High Tide (Lunitidal interval for southern Spain)
    # In the Gulf of Cádiz, high tide occurs ~3h00m after moon transit (Cenit).
    # In the Mediterranean, micro-tidal high water occurs ~3h30m after transit.
    lunitidal_delay_hours = 3.0 if spot.zone == "Atlántico" else 3.5
    
    # Base transit time for the day
    ref_transit = solunar_summary.moon_zenith or (solunar_summary.date + timedelta(hours=13))
    
    # M2 tidal period is ~12.4206 hours (12 hours 25 minutes)
    m2_period_h = 12.4206
    
    # Primary high tide of the day
    primary_high_1 = ref_transit + timedelta(hours=lunitidal_delay_hours)
    
    # High tides for a 48h window around target_dt
    high_tides = [
        primary_high_1 - timedelta(hours=m2_period_h),
        primary_high_1,
        primary_high_1 + timedelta(hours=m2_period_h),
        primary_high_1 + timedelta(hours=2 * m2_period_h),
    ]

    # Low tides occur ~6h 12m after each high tide
    low_tides = [ht + timedelta(hours=m2_period_h / 2.0) for ht in high_tides]

    # Find future next high and low tides relative to target_dt
    future_highs = [ht for ht in high_tides if ht >= target_dt]
    future_lows = [lt for lt in low_tides if lt >= target_dt]

    next_high = min(future_highs) if future_highs else primary_high_1 + timedelta(hours=m2_period_h)
    next_low = min(future_lows) if future_lows else primary_high_1 + timedelta(hours=m2_period_h / 2.0)

    # Calculate time differences in minutes to closest high and low tides (can be in past or future)
    min_dist_high = min(abs((target_dt - ht).total_seconds()) / 60.0 for ht in high_tides)
    min_dist_low = min(abs((target_dt - lt).total_seconds()) / 60.0 for lt in low_tides)

    min_to_next_high = int((next_high - target_dt).total_seconds() / 60.0)
    min_to_next_low = int((next_low - target_dt).total_seconds() / 60.0)

    # 3. Determine state
    is_slack = False
    if min_dist_high <= 45:
        state_name = "Repunte de Pleamar (Punto Alto)"
        is_slack = True
    elif min_dist_low <= 45:
        state_name = "Repunte de Bajamar (Punto Bajo)"
        is_slack = True
    elif min_to_next_high < min_to_next_low:
        state_name = "Llenante (Marea Subiendo / Entrada de Agua)"
    else:
        state_name = "Vaciante (Marea Bajando / Salida de Agua)"

    # 4. Estimated water level (m above datum)
    # Golfo de Cádiz max range ~3.5m, Med ~0.6m
    max_range = 3.2 if spot.zone == "Atlántico" else 0.6
    effective_range = max_range * (coef / 100.0)
    
    # Cosine tidal curve
    time_from_high_min = (target_dt - next_high).total_seconds() / 60.0
    phase_rad = (time_from_high_min / (m2_period_h * 60.0)) * 2.0 * math.pi
    est_height = 0.5 + (effective_range / 2.0) * (1.0 + math.cos(phase_rad))

    return TideState(
        coefficient=coef,
        state_name=state_name,
        is_slack_water=is_slack,
        next_high_tide=next_high,
        next_low_tide=next_low,
        minutes_to_high_tide=min_to_next_high,
        minutes_to_low_tide=min_to_next_low,
        tide_height_est_m=round(est_height, 2),
    )
