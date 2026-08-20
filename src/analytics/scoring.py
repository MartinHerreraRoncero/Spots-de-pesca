"""
Heuristic Marine Biology, Solunar, Tides & Multi-Species Scoring Engine for Andalusia.
Integrates barometric pressure dynamics, tidal hydraulic state, wind-coastline aspect,
oceanographic buoy bias correction, and species-specific scoring models.
"""

from __future__ import annotations
import math
from datetime import datetime
from typing import List, Tuple, Optional, Dict

from src.models.spot import (
    Spot,
    MarineConditions,
    WeatherConditions,
    SolunarDaySummary,
    TideState,
    WindRelativeAspect,
    SpeciesScores,
    ScoreBreakdown,
    ScoringWeights,
    MarineBuoy,
    BuoyObservation,
)
from src.analytics.solunar import evaluate_solunar_for_hour
from src.analytics.tides import compute_spot_tide_state


def calculate_wind_relative_aspect(
    wind_direction: float,
    coastline_bearing: float,
    wind_speed: float,
    zone: str = "Atlántico"
) -> WindRelativeAspect:
    """
    Computes wind angle relative to coastline orientation and detects Onshore / Offshore / Upwelling effects.
    - coastline_bearing: The direction (0-360°) pointing directly outwards from the coast to sea.
    - wind_direction: The direction the wind is COMING FROM.
    """
    # Vector of wind moving towards = (wind_direction + 180) % 360
    # Difference between wind arrival and coastline normal
    diff = (wind_direction - coastline_bearing + 180.0) % 360.0 - 180.0
    abs_diff = abs(diff)

    is_onshore = (abs_diff <= 50.0)
    is_offshore = (abs_diff >= 130.0)
    is_cross_shore = (not is_onshore and not is_offshore)

    # Upwelling risk in the Mediterranean (Costa del Sol / Tropical) when strong offshore/westerly wind blows
    upwelling_risk = (zone in ["Mediterráneo", "Estrecho"] and is_offshore and wind_speed >= 18.0)

    if is_onshore:
        wind_type = "Onshore (De cara / Mar a tierra)"
        effect = "🌊 Viento de cara: empuja nutrientes a la rompiente, oxigena la orilla y genera rizado propicio."
    elif is_offshore:
        wind_type = "Offshore (De espalda / Tierra a mar)"
        if upwelling_risk:
            effect = "❄️ Viento de espalda fuerte (Riesgo Upwelling): aplana el mar pero puede enfriar aguas costeras."
        else:
            effect = "🏹 Viento de espalda: mar plano, permite lances a gran distancia con plomos ligeros."
    else:
        wind_type = "Cross-shore (Lateral / De costado)"
        effect = "💨 Viento lateral: provoca derivas del bajo de línea y acumulación de algas en las puntas."

    return WindRelativeAspect(
        relative_angle=round(diff, 1),
        wind_type=wind_type,
        is_onshore=is_onshore,
        is_offshore=is_offshore,
        is_cross_shore=is_cross_shore,
        upwelling_risk=upwelling_risk,
        effect_summary=effect,
    )


def apply_buoy_bias_correction(
    spot: Spot,
    marine: MarineConditions,
    buoys_telemetry: Optional[List[Tuple[MarineBuoy, BuoyObservation]]] = None
) -> Tuple[float, bool, Optional[str]]:
    """
    Applies spatial Inverse Distance Weighting (IDW) bias correction to model wave height
    based on real in-situ Puertos del Estado buoy telemetry within 90 km.
    """
    if not buoys_telemetry:
        return marine.wave_height, False, None

    # Find closest buoy
    closest_buoy = None
    min_dist_km = 9999.0
    closest_obs = None

    for b, obs in buoys_telemetry:
        # Haversine approximation for short distances in Andalusia
        dlat = (spot.latitude - b.latitude) * 111.0
        dlon = (spot.longitude - b.longitude) * 111.0 * math.cos(math.radians(spot.latitude))
        dist_km = math.sqrt(dlat**2 + dlon**2)
        if dist_km < min_dist_km:
            min_dist_km = dist_km
            closest_buoy = b
            closest_obs = obs

    # Apply calibration if within 90km radius
    if closest_buoy and min_dist_km <= 90.0 and closest_obs:
        # Scale factor between buoy real observation and model
        weight = max(0.0, 1.0 - (min_dist_km / 90.0)) * 0.45  # Blending weight up to 45%
        calibrated_h = (1.0 - weight) * marine.wave_height + weight * closest_obs.wave_height_hs
        return round(calibrated_h, 2), True, closest_buoy.name

    return marine.wave_height, False, None


def calculate_pressure_score(
    current_pressure: float,
    delta_3h: float,
    delta_6h: float
) -> Tuple[float, List[str]]:
    """Evaluates barometric pressure and lag delta based on fish swim bladder physiology."""
    tips = []
    diff = abs(current_pressure - 1015.0)
    if diff <= 4.0:
        base_p = 85.0
    elif diff <= 8.0:
        base_p = 70.0
    elif diff <= 14.0:
        base_p = 50.0
    else:
        base_p = 30.0

    trend_modifier = 0.0
    if -1.8 <= delta_3h <= -0.4:
        trend_modifier = +15.0
        tips.append("📉 Descenso barométrico suave: alta actividad alimenticia pre-frente.")
    elif -0.4 < delta_3h <= 0.5:
        trend_modifier = +5.0
        tips.append("⚖️ Presión atmosférica muy estable: actividad trófica regular.")
    elif delta_3h < -2.5:
        trend_modifier = -30.0
        tips.append("⚠️ Caída brusca de presión: mar alterado y peces replegados a zonas profundas.")
    elif delta_3h > 2.0:
        trend_modifier = -15.0
        tips.append("📈 Subida rápida de presión: peces inactivos adaptándose al cambio barométrico.")

    if current_pressure > 1026.0:
        trend_modifier -= 15.0
        tips.append("☀️ Anticiclón fuerte: aguas paradas y peces recelosos.")
    elif current_pressure < 1002.0:
        trend_modifier -= 25.0
        tips.append("⛈️ Borrasca profunda: condiciones adversas para pesca de orilla.")

    final_score = max(5.0, min(100.0, base_p + trend_modifier))
    return round(final_score, 1), tips


def calculate_marine_score(marine: MarineConditions, spot: Spot) -> Tuple[float, List[str]]:
    """Evaluates wave height and period suitability for coastal shore fishing."""
    tips = []
    h = marine.wave_height
    if 0.4 <= h <= 1.1:
        wave_score = 95.0
        tips.append(f"🌊 Oleaje óptimo ({h:.1f}m): espuma y oxigenación ideales en rompientes.")
    elif 0.25 <= h < 0.4:
        wave_score = 75.0
        tips.append(f"🌊 Mar en calma ({h:.1f}m): usar bajos finos y lances lejanos.")
    elif 1.1 < h <= 1.6:
        wave_score = 75.0
        tips.append(f"🌊 Mar picada/fuerte ({h:.1f}m): excelente para lubinas y sargos en espuma.")
    elif h < 0.25:
        wave_score = 50.0
        tips.append(f"🌊 Mar como un plato ({h:.1f}m): aguas excesivamente claras.")
    elif 1.6 < h <= 2.2:
        wave_score = 45.0
        tips.append(f"⚠️ Mar de fondo notable ({h:.1f}m): buscar zonas abrigadas o calas protegidas.")
    else:
        wave_score = 20.0
        tips.append(f"🛑 Temporal marítimo ({h:.1f}m): peligro en roquedos y playas abiertas.")

    p = marine.wave_period
    period_bonus = 0.0
    if p >= 8.0:
        period_bonus = +10.0
    elif p >= 6.5:
        period_bonus = +5.0
    elif p < 4.5:
        period_bonus = -15.0
        tips.append("💨 Mar de viento corto y revuelto (periodo < 5s).")

    final_marine = max(5.0, min(100.0, wave_score + period_bonus))
    return round(final_marine, 1), tips


def calculate_wind_score(weather: WeatherConditions, wind_aspect: WindRelativeAspect) -> Tuple[float, List[str]]:
    """Evaluates coastal wind speed and direction impact."""
    tips = []
    w = weather.wind_speed_10m

    if 8.0 <= w <= 18.0:
        score = 95.0
    elif 4.0 <= w < 8.0:
        score = 80.0
    elif 18.0 < w <= 26.0:
        score = 65.0
    elif w < 4.0:
        score = 60.0
    elif 26.0 < w <= 35.0:
        score = 40.0
        tips.append(f"⚠️ Viento muy fuerte ({w:.1f} km/h): dificulta el lance.")
    else:
        score = 15.0
        tips.append(f"🛑 Vendaval ({w:.1f} km/h): lance imposible.")

    # Aspect modifier
    if wind_aspect.is_onshore and 8.0 <= w <= 20.0:
        score = min(100.0, score + 5.0)
    elif wind_aspect.upwelling_risk:
        score = max(20.0, score - 15.0)

    tips.append(wind_aspect.effect_summary)
    return round(score, 1), tips


def calculate_species_scores(
    spot: Spot,
    weather: WeatherConditions,
    marine: MarineConditions,
    solunar_summary: SolunarDaySummary,
    solunar_score: float,
    tide_state: TideState,
    wind_aspect: WindRelativeAspect,
    pressure_score: float,
    delta_3h: float,
) -> SpeciesScores:
    """
    Computes calibrated species-specific scores based on precise marine biology criteria.
    """
    h = marine.wave_height
    p = marine.wave_period
    w = weather.wind_speed_10m
    coef = tide_state.coefficient
    is_spring = solunar_summary.is_spring_tide

    # 1. DORADA & HERRERA (Surfcasting en Arenales / Canales)
    # Prefers: 0.4-0.9m waves, rising tide (llenante), high tide coefficient, gentle currents (0.25-0.75 kts)
    c_kts = marine.current_velocity_knots
    d_score = 50.0
    if 0.35 <= h <= 0.85:
        d_score += 15.0
    elif h > 1.4:
        d_score -= 20.0
    if "Llenante" in tide_state.state_name or "Pleamar" in tide_state.state_name:
        d_score += 15.0
    if coef >= 70:
        d_score += 10.0
    if 0.25 <= c_kts <= 0.85:
        d_score += 10.0  # Gentle current disperses scent trail
    elif c_kts > 1.8:
        d_score -= 15.0  # Excessive current drags weights
    if spot.spot_type in ["Playa / Arenal", "Desembocadura"]:
        d_score += 10.0
    if wind_aspect.is_onshore:
        d_score += 5.0
    dorada_final = max(10.0, min(100.0, d_score * 0.5 + pressure_score * 0.25 + solunar_score * 0.25))

    # 2. LUBINA & ROBALO (Spinning en Rompiente / Espuma)
    # Prefers: 1.1-1.9m waves with heavy foam, moving current (0.6-1.8 kts), pre-frontal pressure drops
    l_score = 45.0
    if 1.1 <= h <= 1.8:
        l_score += 25.0
    elif 0.8 <= h < 1.1:
        l_score += 12.0
    elif h < 0.4:
        l_score -= 20.0  # Clear flat water is bad for daytime seabass
    if 0.6 <= c_kts <= 1.8:
        l_score += 12.0  # Current stirs up baitfish near points & headlands
    if delta_3h <= -0.5:
        l_score += 15.0
    if solunar_score >= 65.0:
        l_score += 10.0
    if spot.spot_type in ["Espigón / Estructura", "Desembocadura", "Ría / Estuario", "Roquedo / Acantilado"]:
        l_score += 10.0
    lubina_final = max(10.0, min(100.0, l_score * 0.6 + pressure_score * 0.2 + solunar_score * 0.2))

    # 3. SARGO (Rockfishing en Roquedos y Espuma)
    # Prefers: Breaking waves on rocky ledges (0.8 - 1.5m), moderate current, long wave period
    s_score = 50.0
    if 0.8 <= h <= 1.6:
        s_score += 25.0
    elif h < 0.35:
        s_score -= 15.0
    if 0.4 <= c_kts <= 1.5:
        s_score += 10.0
    if p >= 7.5:
        s_score += 10.0
    if spot.spot_type in ["Roquedo / Acantilado", "Cala Mixta", "Espigón / Estructura"]:
        s_score += 15.0
    sargo_final = max(10.0, min(100.0, s_score * 0.5 + solunar_score * 0.3 + pressure_score * 0.2))

    # 4. CALAMAR & SEPIA (Eging en Aguas Claras)
    # Prefers: Calm sea (h < 0.4m), zero/weak current (<0.4 kts), light wind (<10 km/h), high tide
    c_score = 50.0
    if h <= 0.35:
        c_score += 25.0
    elif h <= 0.6:
        c_score += 5.0
    else:
        c_score -= 30.0  # Rough water ruins squid fishing
    if c_kts <= 0.4:
        c_score += 15.0  # Low current allows jigs to sink naturally
    elif c_kts > 0.8:
        c_score -= 20.0  # Strong current sweeps jigs away
    if w <= 10.0:
        c_score += 15.0
    elif w > 20.0:
        c_score -= 20.0
    if tide_state.is_slack_water or "Pleamar" in tide_state.state_name:
        c_score += 10.0
    calamar_final = max(10.0, min(100.0, c_score * 0.55 + solunar_score * 0.3 + pressure_score * 0.15))

    # 5. DENTÓN & SERVIOLA (Shore Jigging y Pesca Profunda)
    # Prefers: Deep waters (>15m), strong current (0.8-2.2 kts), clean groundswell
    dent_score = 45.0
    if (spot.depth_m or 10) >= 15:
        dent_score += 20.0
    if 0.8 <= c_kts <= 2.2:
        dent_score += 15.0  # Pelagic predators actively hunt in strong currents
    if p >= 7.5:
        dent_score += 10.0
    if 0.5 <= h <= 1.3:
        dent_score += 10.0
    if solunar_score >= 70.0:
        dent_score += 15.0
    denton_final = max(10.0, min(100.0, dent_score * 0.5 + solunar_score * 0.35 + pressure_score * 0.15))

    # 6. CORVINA (Grandes Corrientes de Marea en Golfo de Cádiz)
    # Prefers: Gulf of Cadiz/Huelva, huge currents (1.0-2.5 kts), spring tides (coef > 80), estuaries
    corv_score = 45.0
    if spot.zone == "Atlántico":
        corv_score += 15.0
    if coef >= 80:
        corv_score += 15.0
    if 1.0 <= c_kts <= 2.6:
        corv_score += 20.0  # Huge corvinas feed aggressively in fast tidal currents
    if spot.spot_type in ["Desembocadura", "Espigón / Estructura", "Playa / Arenal"]:
        corv_score += 10.0
    if 0.5 <= h <= 1.2:
        corv_score += 10.0
    corvina_final = max(10.0, min(100.0, corv_score * 0.5 + solunar_score * 0.3 + pressure_score * 0.2))

    return SpeciesScores(
        dorada_score=round(dorada_final, 1),
        lubina_score=round(lubina_final, 1),
        sargo_score=round(sargo_final, 1),
        calamar_score=round(calamar_final, 1),
        denton_score=round(denton_final, 1),
        corvina_score=round(corvina_final, 1),
    )


def score_hourly_conditions(
    spot: Spot,
    target_dt: datetime,
    marine: MarineConditions,
    weather: WeatherConditions,
    solunar_summary: SolunarDaySummary,
    delta_3h: float,
    delta_6h: float,
    weights: Optional[ScoringWeights] = None,
    buoys_telemetry: Optional[List[Tuple[MarineBuoy, BuoyObservation]]] = None,
) -> ScoreBreakdown:
    """
    Core heuristic scoring function: aggregates physics, tides, wind aspect,
    buoy calibration, and species-specific models into unified ratings.
    """
    if weights is None:
        weights = ScoringWeights()
    w = weights.normalized()

    # 1. Apply Buoy Bias Correction to wave height
    calibrated_wave_h, buoy_applied, buoy_name = apply_buoy_bias_correction(spot, marine, buoys_telemetry)
    marine.calibrated_wave_height = calibrated_wave_h

    # 2. Sub-scores
    p_score, p_tips = calculate_pressure_score(weather.surface_pressure, delta_3h, delta_6h)
    m_score, m_tips = calculate_marine_score(marine, spot)
    
    # 3. Wind Relative Aspect
    wind_aspect = calculate_wind_relative_aspect(
        weather.wind_direction_10m,
        spot.coastline_bearing,
        weather.wind_speed_10m,
        spot.zone
    )
    wind_score, w_tips = calculate_wind_score(weather, wind_aspect)
    
    # 4. Solunar & Lunar Phase
    solunar_score, active_window, is_crepuscular = evaluate_solunar_for_hour(solunar_summary, target_dt)
    lunar_score = 90.0 if solunar_summary.is_spring_tide else 65.0

    # 5. Tides State
    tide_state = compute_spot_tide_state(spot, target_dt, solunar_summary)

    # 6. Global Multi-Species Weighted Sum
    overall = (
        w.weight_pressure * p_score +
        w.weight_solunar * solunar_score +
        w.weight_marine * m_score +
        w.weight_wind * wind_score +
        w.weight_moon_phase * lunar_score
    )
    overall = max(0.0, min(100.0, overall))

    # 7. Species-specific scoring models
    species_scores = calculate_species_scores(
        spot, weather, marine, solunar_summary, solunar_score, tide_state, wind_aspect, p_score, delta_3h
    )

    # Rating classification
    if overall >= 75.0:
        tier = "Excelente"
        color = "#10b981"
    elif overall >= 60.0:
        tier = "Muy Bueno"
        color = "#84cc16"
    elif overall >= 45.0:
        tier = "Favorable"
        color = "#f59e0b"
    else:
        tier = "Desfavorable"
        color = "#ef4444"

    # Tactical tips
    all_tips = []
    if active_window:
        all_tips.append(f"⭐ Coincidencia con {active_window}.")
    if is_crepuscular:
        all_tips.append("🌅 Ventana Crepuscular Dorada: solapamiento solunar con amanecer/atardecer.")
    if buoy_applied:
        all_tips.append(f"📡 Oleaje calibrado in-situ con {buoy_name} ({marine.calibrated_wave_height}m).")
    
    all_tips.append(f"🌊 Marea: {tide_state.state_name} (Coef. {tide_state.coefficient}).")
    all_tips.append(f"🧭 Corriente: {marine.current_velocity_knots} kts ({marine.current_direction:.0f}°) • {marine.current_intensity_level}.")
    all_tips.extend(p_tips)
    all_tips.extend(m_tips)
    all_tips.extend(w_tips)

    return ScoreBreakdown(
        overall_score=round(overall, 1),
        rating_tier=tier,
        rating_color=color,
        pressure_score=p_score,
        pressure_delta_3h=round(delta_3h, 2),
        pressure_delta_6h=round(delta_6h, 2),
        solunar_score=solunar_score,
        solunar_window_active=active_window,
        is_crepuscular_overlap=is_crepuscular,
        marine_score=m_score,
        wind_score=wind_score,
        moon_phase_score=lunar_score,
        tide_state=tide_state,
        wind_aspect=wind_aspect,
        species_scores=species_scores,
        buoy_calibration_applied=buoy_applied,
        calibrating_buoy_name=buoy_name,
        tactical_tips=all_tips[:4],
    )
