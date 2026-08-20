"""
Solunar and astronomical analytics using ephem for Andalusian coastal spots.
"""

from __future__ import annotations
import math
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
import ephem

from src.models.spot import Spot, SolunarWindow, SolunarDaySummary


def get_moon_phase_info(ephem_date: ephem.Date) -> Tuple[str, float, float, bool]:
    """
    Returns (phase_name, illumination_pct [0-100], moon_age_days [0-29.53], is_spring_tide).
    """
    moon = ephem.Moon()
    moon.compute(ephem_date)
    illumination = float(moon.phase)  # 0 to 100

    # Calculate moon age from previous new moon
    try:
        prev_new = ephem.previous_new_moon(ephem_date)
        moon_age = float(ephem_date - prev_new)
    except Exception:
        moon_age = (illumination / 100.0) * 29.53

    # Categorize phase
    # Synodic month ~29.53 days
    cycle_pct = (moon_age % 29.53) / 29.53
    if cycle_pct < 0.03 or cycle_pct > 0.97:
        phase_name = "Luna Nueva (Mareas Vivas)"
    elif cycle_pct < 0.22:
        phase_name = "Luna Creciente"
    elif cycle_pct < 0.28:
        phase_name = "Cuarto Creciente (Mareas Muertas)"
    elif cycle_pct < 0.47:
        phase_name = "Gibosa Creciente"
    elif cycle_pct < 0.53:
        phase_name = "Luna Llena (Mareas Vivas)"
    elif cycle_pct < 0.72:
        phase_name = "Gibosa Menguante"
    elif cycle_pct < 0.78:
        phase_name = "Cuarto Menguante (Mareas Muertas)"
    else:
        phase_name = "Luna Menguante"

    # Spring tides (Mareas Vivas) occur around New Moon & Full Moon (approx ±3 days or illumination <= 10% / >= 90%)
    is_spring_tide = (moon_age <= 3.5 or moon_age >= 26.0 or (11.5 <= moon_age <= 18.0))

    return phase_name, illumination, moon_age, is_spring_tide


def _ephem_date_to_utc_datetime(ed: ephem.Date) -> datetime:
    """Converts ephem.Date to timezone-aware UTC datetime."""
    dt = ed.datetime()
    return dt.replace(tzinfo=timezone.utc)


def compute_daily_solunar(spot: Spot, target_date: datetime) -> SolunarDaySummary:
    """
    Computes all solar and lunar celestial timings and solunar windows for a given spot and date.
    """
    # Normalize to midnight UTC for the given day
    day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
    ephem_day = ephem.Date(day_start)

    obs = ephem.Observer()
    obs.lat = str(spot.latitude)
    obs.lon = str(spot.longitude)
    obs.elevation = spot.depth_m or 0.0
    obs.date = ephem_day

    sun = ephem.Sun()
    moon = ephem.Moon()

    # Moon phase
    phase_name, illumination, moon_age, is_spring_tide = get_moon_phase_info(ephem_day)

    # Solar timings
    sunrise = None
    sunset = None
    dawn_twilight = None
    dusk_twilight = None

    try:
        obs.horizon = '0'  # standard horizon
        obs.date = ephem_day
        sunrise = _ephem_date_to_utc_datetime(obs.next_rising(sun))
        sunset = _ephem_date_to_utc_datetime(obs.next_setting(sun))

        # Civil twilight (-6 degrees below horizon)
        obs.horizon = '-6'
        obs.date = ephem_day
        dawn_twilight = _ephem_date_to_utc_datetime(obs.next_rising(sun))
        dusk_twilight = _ephem_date_to_utc_datetime(obs.next_setting(sun))
    except Exception:
        # Fallback approximation for southern Spain (~36.5 N)
        sunrise = day_start + timedelta(hours=6, minutes=45)
        sunset = day_start + timedelta(hours=20, minutes=30)
        dawn_twilight = sunrise - timedelta(minutes=30)
        dusk_twilight = sunset + timedelta(minutes=30)

    # Reset horizon for moon timings
    obs.horizon = '0'
    obs.date = ephem_day

    moonrise = None
    moonset = None
    moon_zenith = None
    moon_nadir = None

    try:
        moonrise = _ephem_date_to_utc_datetime(obs.next_rising(moon))
    except Exception:
        pass

    try:
        moonset = _ephem_date_to_utc_datetime(obs.next_setting(moon))
    except Exception:
        pass

    try:
        moon_zenith = _ephem_date_to_utc_datetime(obs.next_transit(moon))
    except Exception:
        pass

    try:
        moon_nadir = _ephem_date_to_utc_datetime(obs.next_antitransit(moon))
    except Exception:
        pass

    # Build Solunar Windows
    windows: List[SolunarWindow] = []

    # Major Windows: Moon Zenith & Moon Nadir (±1 hour)
    if moon_zenith:
        windows.append(SolunarWindow(
            name="Periodo Mayor 1 (Cenit Lunar)",
            window_type="MAJOR",
            peak_time=moon_zenith,
            start_time=moon_zenith - timedelta(minutes=60),
            end_time=moon_zenith + timedelta(minutes=60),
            quality_bonus=35.0,
            description="La luna se encuentra directamente sobre la vertical del spot. Pico máximo de actividad biológica marina."
        ))

    if moon_nadir:
        windows.append(SolunarWindow(
            name="Periodo Mayor 2 (Nadir / Antitránsito)",
            window_type="MAJOR",
            peak_time=moon_nadir,
            start_time=moon_nadir - timedelta(minutes=60),
            end_time=moon_nadir + timedelta(minutes=60),
            quality_bonus=30.0,
            description="La luna se encuentra en el punto opuesto bajo nuestros pies. Fuerte estímulo trófico."
        ))

    # Minor Windows: Moonrise & Moonset (±45 minutes)
    if moonrise:
        windows.append(SolunarWindow(
            name="Periodo Menor 1 (Orto Lunar)",
            window_type="MINOR",
            peak_time=moonrise,
            start_time=moonrise - timedelta(minutes=45),
            end_time=moonrise + timedelta(minutes=45),
            quality_bonus=20.0,
            description="Salida de la luna en el horizonte. Actividad media de bancos de peces."
        ))

    if moonset:
        windows.append(SolunarWindow(
            name="Periodo Menor 2 (Ocaso Lunar)",
            window_type="MINOR",
            peak_time=moonset,
            start_time=moonset - timedelta(minutes=45),
            end_time=moonset + timedelta(minutes=45),
            quality_bonus=20.0,
            description="Puesta de la luna. Ventana complementaria de forrajeo costero."
        ))

    return SolunarDaySummary(
        date=day_start,
        moon_phase_name=phase_name,
        moon_illumination=illumination,
        moon_age_days=moon_age,
        is_spring_tide=is_spring_tide,
        sunrise=sunrise,
        sunset=sunset,
        dawn_twilight=dawn_twilight,
        dusk_twilight=dusk_twilight,
        moonrise=moonrise,
        moonset=moonset,
        moon_zenith=moon_zenith,
        moon_nadir=moon_nadir,
        windows=windows,
    )


def evaluate_solunar_for_hour(
    solunar_summary: SolunarDaySummary,
    hour_dt: datetime
) -> Tuple[float, Optional[str], bool]:
    """
    Evaluates solunar activity score (0 - 100) for a given specific hourly timestamp.
    Returns (solunar_score, active_window_name, is_crepuscular_overlap).
    """
    # Ensure timezone awareness
    if hour_dt.tzinfo is None:
        hour_dt = hour_dt.replace(tzinfo=timezone.utc)

    # 1. Base score from lunar phase and spring tides (30 - 55 baseline)
    if solunar_summary.is_spring_tide:
        base_score = 45.0 + 10.0 * (1.0 - abs(solunar_summary.moon_illumination - 50.0) / 50.0)
    else:
        base_score = 30.0 + 10.0 * (solunar_summary.moon_illumination / 100.0)

    # 2. Check overlap with Solunar Windows
    window_bonus = 0.0
    active_window_name = None

    for w in solunar_summary.windows:
        # Distance in minutes to peak
        time_diff_min = abs((hour_dt - w.peak_time).total_seconds()) / 60.0
        
        # Check if inside window or within 90 min proximity
        if w.window_type == "MAJOR" and time_diff_min <= 90:
            # Gaussian bell curve decay
            intensity = math.exp(-0.5 * ((time_diff_min / 45.0) ** 2))
            bonus = w.quality_bonus * intensity
            if bonus > window_bonus:
                window_bonus = bonus
                active_window_name = w.name
        elif w.window_type == "MINOR" and time_diff_min <= 70:
            intensity = math.exp(-0.5 * ((time_diff_min / 35.0) ** 2))
            bonus = w.quality_bonus * intensity
            if bonus > window_bonus:
                window_bonus = bonus
                active_window_name = w.name

    # 3. Check Solar Crepuscular overlap (Dawn/Dusk ± 45 mins)
    is_crepuscular = False
    solar_bonus = 0.0

    if solunar_summary.sunrise:
        sun_diff = abs((hour_dt - solunar_summary.sunrise).total_seconds()) / 60.0
        if sun_diff <= 60:
            is_crepuscular = True
            solar_bonus = max(solar_bonus, 20.0 * math.exp(-0.5 * (sun_diff / 30.0) ** 2))

    if solunar_summary.sunset:
        sun_diff = abs((hour_dt - solunar_summary.sunset).total_seconds()) / 60.0
        if sun_diff <= 60:
            is_crepuscular = True
            solar_bonus = max(solar_bonus, 20.0 * math.exp(-0.5 * (sun_diff / 30.0) ** 2))

    # Golden Window multiplier: Solunar + Twilight synergy
    synergy_bonus = 0.0
    is_crepuscular_overlap = False
    if window_bonus > 15.0 and is_crepuscular:
        synergy_bonus = 20.0
        is_crepuscular_overlap = True

    total_solunar_score = min(100.0, base_score + window_bonus + solar_bonus + synergy_bonus)
    return round(total_solunar_score, 1), active_window_name, is_crepuscular_overlap
