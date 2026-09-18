"""
Coastal oceanography, bathymetric Stumpf ratio calculations, and poza fishability algorithms.
Specialized for coastal depressions, breaker line discontinuities, and troughs along the Huelva coast.
"""

from __future__ import annotations
import json
import logging
import math
from dataclasses import replace
from pathlib import Path
from typing import List, Optional, Dict, Any

from src.models.poza import DetectedPoza, SentinelPassMetadata, DetectionMethod

logger = logging.getLogger(__name__)

# Default location of the Huelva coastal pozas database
_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_POZAS_FILE = _WORKSPACE_ROOT / "data" / "pozas_huelva.json"


def load_pozas_from_json(filepath: Optional[Path] = None) -> List[DetectedPoza]:
    """
    Loads curated detected coastal pozas and channels from JSON database.

    Args:
        filepath: Optional Path to the JSON file. Defaults to data/pozas_huelva.json.

    Returns:
        List[DetectedPoza]: List of validated DetectedPoza instances.
    """
    target_path = Path(filepath) if filepath is not None else DEFAULT_POZAS_FILE

    if not target_path.is_file():
        logger.warning(f"Pozas database file not found at {target_path}")
        return []

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        if not isinstance(raw_data, list):
            logger.error(f"Expected list of pozas in {target_path}, got {type(raw_data).__name__}")
            return []

        pozas: List[DetectedPoza] = []
        for idx, item in enumerate(raw_data):
            try:
                pozas.append(DetectedPoza.from_dict(item))
            except Exception as item_err:
                logger.warning(f"Error parsing poza entry at index {idx}: {item_err}")

        logger.info(f"Loaded {len(pozas)} coastal pozas from {target_path}")
        return pozas

    except Exception as e:
        logger.error(f"Failed to read pozas JSON from {target_path}: {e}")
        return []


def compute_stumpf_sdb_ratio(
    b02_refl: float,
    b03_refl: float,
    m1: float = 12.5,
    m0: float = 2.0,
) -> float:
    """
    Computes Satellite Derived Bathymetry (SDB) depth using the Stumpf et al. (2003) log-ratio algorithm:
    Depth Z = m1 * (ln(n * R_blue) / ln(n * R_green)) - m0.

    Band 2 (Blue, ~490 nm) and Band 3 (Green, ~560 nm) are evaluated. Blue light penetrates deeper
    in clear coastal waters, while green light attenuates faster.

    Args:
        b02_refl: Blue band reflectance (0.0 to 1.0) or scaled digital numbers (DN > 1).
        b03_refl: Green band reflectance (0.0 to 1.0) or scaled digital numbers (DN > 1).
        m1: Tuned linear regression scale factor (default: 12.5 for Huelva sandy littoral waters).
        m0: Tuned regression offset factor (default: 2.0 m).

    Returns:
        float: Estimated bathymetric water depth in meters (>= 0.0), rounded to 2 decimal places.
    """
    # Guard against non-positive reflectances
    val_b02 = max(1e-5, float(b02_refl))
    val_b03 = max(1e-5, float(b03_refl))

    # Determine scaling constant n so that n * reflectance > 1.0, ensuring positive natural logs
    # Typical surface reflectance is 0.01 - 0.35; multiplying by 1000 yields 10 - 350
    n_b02 = val_b02 * 1000.0 if val_b02 <= 1.0 else val_b02
    n_b03 = val_b03 * 1000.0 if val_b03 <= 1.0 else val_b03

    # Ensure strictly > 1.0 to prevent log <= 0 or division by zero
    n_b02 = max(1.0001, n_b02)
    n_b03 = max(1.0001, n_b03)

    log_blue = math.log(n_b02)
    log_green = math.log(n_b03)

    if abs(log_green) < 1e-9:
        ratio = 1.0
    else:
        ratio = log_blue / log_green

    depth = m1 * ratio - m0
    return round(max(0.0, depth), 2)


def evaluate_poza_fishability(
    poza: DetectedPoza,
    tide_state_name: Optional[str] = "Pleamar",
    tide_coeff: Optional[float] = 75.0,
    wave_height_m: Optional[float] = 0.8,
    current_speed_knots: Optional[float] = 1.0,
) -> Dict[str, Any]:
    """
    Evaluates current tactical fishability of a coastal poza/channel based on real-time
    tide state, coefficient, breaker height, and littoral current speed.

    Args:
        poza: The DetectedPoza instance.
        tide_state_name: Current tide stage name (e.g. "Media marea subiendo", "Bajamar", "Pleamar").
        tide_coeff: Astronomical tide coefficient (typically 30 to 115).
        wave_height_m: Significant wave breaker height in meters.
        current_speed_knots: Littoral/channel current speed in knots.

    Returns:
        Dict[str, Any]: Assessment containing:
            - 'fishability_score': float (0 to 100)
            - 'activity_summary': str (tactical assessment)
            - 'recommended_lead_g': int (110 to 150g)
            - 'recommended_baits': List[str] (tailored bait selection)
            - 'is_optimal_now': bool
    """
    # 1. Tide Alignment Factor (0 to 35 points)
    tide_curr = str(tide_state_name or "Pleamar").strip().lower()
    tide_opt = str(poza.optimal_tide_stage or "").strip().lower()

    tide_score = 15.0  # Base score for active tide movement

    # Check key tide stage keywords
    keywords_subiendo = ["subiendo", "llenante", "creciente", "reflujo"]
    keywords_bajamar = ["bajamar", "baja", "repunte de bajamar", "últimas 2h de bajamar", "vaciante"]
    keywords_pleamar = ["pleamar", "alta", "plea"]

    opt_is_subiendo = any(k in tide_opt for k in keywords_subiendo)
    opt_is_bajamar = any(k in tide_opt for k in keywords_bajamar)
    opt_is_pleamar = any(k in tide_opt for k in keywords_pleamar)

    curr_is_subiendo = any(k in tide_curr for k in keywords_subiendo)
    curr_is_bajamar = any(k in tide_curr for k in keywords_bajamar)
    curr_is_pleamar = any(k in tide_curr for k in keywords_pleamar)

    if tide_curr == tide_opt or (curr_is_subiendo and opt_is_subiendo) or (curr_is_bajamar and opt_is_bajamar) or (curr_is_pleamar and opt_is_pleamar):
        tide_score = 35.0
    elif (opt_is_subiendo and curr_is_bajamar) or (opt_is_bajamar and curr_is_subiendo):
        # Transición marea viva/muerta o repunte
        tide_score = 22.0
    elif opt_is_pleamar and curr_is_subiendo:
        tide_score = 28.0
    elif opt_is_bajamar and "vaciante" in tide_curr:
        tide_score = 30.0
    else:
        tide_score = 18.0

    # 2. Tide Coefficient Factor (0 to 25 points)
    # Andalusian Atlantic surfcasting benefits from vigorous tidal currents (65 - 95 coeff)
    # which scour channels and transport worms/crabs, without being unmanageably violent (>105).
    try:
        coeff = float(tide_coeff if tide_coeff is not None else 75.0)
    except (TypeError, ValueError):
        coeff = 75.0

    if 70.0 <= coeff <= 95.0:
        coeff_score = 25.0
    elif 55.0 <= coeff < 70.0 or 95.0 < coeff <= 105.0:
        coeff_score = 20.0
    elif 40.0 <= coeff < 55.0:
        coeff_score = 14.0
    elif coeff > 105.0:
        coeff_score = 12.0  # Extreme rip currents
    else:
        coeff_score = 8.0   # Dead neap (aguas muertas)

    # 3. Wave Breaker Energy Factor (0 to 25 points)
    # 0.4 - 1.2m is ideal for holding and feeding inside troughs behind the sandbars
    try:
        wave_h = max(0.0, float(wave_height_m if wave_height_m is not None else 0.8))
    except (TypeError, ValueError):
        wave_h = 0.8

    if 0.5 <= wave_h <= 1.3:
        wave_score = 25.0
    elif 0.3 <= wave_h < 0.5:
        wave_score = 20.0  # Good for herrera / calm night surfcasting
    elif 1.3 < wave_h <= 1.8:
        wave_score = 18.0  # Good for robalo/lubina in breakers, but harder lead hold
    elif 1.8 < wave_h <= 2.3:
        wave_score = 10.0  # Strong surf, heavy weed risk
    elif wave_h > 2.3:
        wave_score = 2.0   # Dangerous or unfishable from the beach
    else:
        wave_score = 14.0  # Flat calm (<0.3m), water too clear in daytime

    # 4. Littoral Current Speed Factor (0 to 15 points)
    try:
        current_kn = max(0.0, float(current_speed_knots if current_speed_knots is not None else 1.0))
    except (TypeError, ValueError):
        current_kn = 1.0

    if 0.4 <= current_kn <= 1.6:
        current_score = 15.0
    elif 0.1 <= current_kn < 0.4:
        current_score = 12.0
    elif 1.6 < current_kn <= 2.4:
        current_score = 10.0
    elif 2.4 < current_kn <= 3.2:
        current_score = 5.0
    else:
        current_score = 1.0  # > 3.2 knots creates severe line drag and rolling sinkers

    # Base score summation (0 to 100)
    raw_score = tide_score + coeff_score + wave_score + current_score

    # Minor structural bonus (+2 points for deep well-defined pozas > 2.0m depth)
    if poza.relative_depth_m is not None and poza.relative_depth_m >= 2.0:
        raw_score += 2.0
    if poza.confidence_score is not None and poza.confidence_score >= 95.0:
        raw_score += 1.0

    # Penalties for extreme sea states
    if wave_h > 2.4:
        raw_score = min(raw_score, 25.0)
    if current_kn > 3.5:
        raw_score = min(raw_score, 30.0)

    fishability_score = round(max(0.0, min(100.0, raw_score)), 1)

    # 5. Lead Weight Recommendation (110g to 150g)
    # Adjusted dynamically based on current velocity and wave energy
    if current_kn >= 2.5 or wave_h >= 2.0:
        recommended_lead_g = 150
    elif current_kn >= 1.8 or wave_h >= 1.4:
        recommended_lead_g = 140
    elif current_kn >= 1.2 or wave_h >= 1.0:
        recommended_lead_g = 130
    elif current_kn >= 0.7 or wave_h >= 0.6:
        recommended_lead_g = 120
    else:
        recommended_lead_g = 110

    # 6. Tailored Bait Recommendation
    target_sp = [s.lower() for s in poza.target_species]
    baits: List[str] = []

    has_dorada = any("dorada" in s for s in target_sp)
    has_herrera = any("herrera" in s for s in target_sp)
    has_robalo = any("robalo" in s or "lubina" in s or "baila" in s for s in target_sp)
    has_corvina = any("corvina" in s for s in target_sp)
    has_lenguado = any("lenguado" in s for s in target_sp)

    if has_dorada:
        baits.append("Tita de palangre")
        baits.append("Navaja viva con cáscara")
    if has_herrera or has_lenguado:
        baits.append("Gusana de playa / Catalana")
        baits.append("Lombriz de arena")
    if has_robalo or has_corvina:
        baits.append("Choco fresco de Huelva")
        if "Sardinilla fresca" not in baits:
            baits.append("Sardinilla fresca")

    # Ensure unique and fallback if empty
    seen = set()
    deduped_baits = []
    for b in baits:
        if b not in seen:
            seen.add(b)
            deduped_baits.append(b)

    if not deduped_baits:
        deduped_baits = ["Tita de palangre", "Navaja viva con cáscara", "Gusana de playa / Catalana", "Choco fresco de Huelva"]

    recommended_baits = deduped_baits[:4]

    # 7. Activity Summary and Tactical Assessment
    is_optimal_now = bool(fishability_score >= 70.0 and wave_h <= 2.2 and current_kn <= 3.0)

    if is_optimal_now:
        activity_summary = (
            f"Condición óptima ({fishability_score}/100): Poza {poza.name} en fase idónea ({poza.optimal_tide_stage}). "
            f"Foso de +{poza.relative_depth_m}m concentrando moluscos y anélidos con corriente lateral de {current_kn:.1f} nd. "
            f"Lance recomendado a {poza.distance_from_shore_m}m empleando plomo de {recommended_lead_g}g."
        )
    elif wave_h > 2.2:
        activity_summary = (
            f"Condición difícil ({fishability_score}/100): Oleaje excesivo ({wave_h:.1f}m) desbordando la barra arenosa "
            f"y generando fuerte mar de fondo. Riesgo de deriva constante a {poza.distance_from_shore_m}m."
        )
    elif current_kn > 3.0:
        activity_summary = (
            f"Corriente severa ({current_kn:.1f} nd): Fuerte arrastre de línea en la poza. Requiere plomo de agarre {recommended_lead_g}g "
            f"y revisión constante de algas."
        )
    else:
        activity_summary = (
            f"Actividad moderada ({fishability_score}/100): La poza se encuentra en {tide_state_name or 'marea intermedia'}, "
            f"fuera de su ventana pico ({poza.optimal_tide_stage}). Posibles capturas selectivas a media distancia."
        )

    return {
        "fishability_score": fishability_score,
        "activity_summary": activity_summary,
        "recommended_lead_g": recommended_lead_g,
        "recommended_baits": recommended_baits,
        "is_optimal_now": is_optimal_now,
    }


def filter_pozas(
    pozas: List[DetectedPoza],
    beach: Optional[str] = None,
    method: Optional[str] = None,
    max_distance: Optional[int] = None,
) -> List[DetectedPoza]:
    """
    Filters detected pozas by beach name, detection methodology, and maximum casting distance.

    Args:
        pozas: Input list of DetectedPoza.
        beach: Optional beach name or substring (case-insensitive).
        method: Optional detection method ("SDB_STUMPF", "BREAKER_GAP", "PNOA_ORTHO").
        max_distance: Optional maximum distance from shore in meters.

    Returns:
        List[DetectedPoza]: Filtered list of pozas.
    """
    filtered: List[DetectedPoza] = []

    for poza in pozas:
        # Filter by beach
        if beach:
            query = beach.strip().lower()
            if query not in poza.beach_name.lower() and query not in poza.name.lower():
                continue

        # Filter by method
        if method:
            if poza.detection_method.strip().upper() != method.strip().upper():
                continue

        # Filter by max distance from shore
        if max_distance is not None:
            if poza.distance_from_shore_m > max_distance:
                continue

        filtered.append(poza)

    return filtered


def sync_pozas_with_satellite_pass(
    pozas: List[DetectedPoza],
    sentinel_meta: SentinelPassMetadata,
) -> List[DetectedPoza]:
    """
    Synchronizes coastal pozas with latest Sentinel-2 MSI satellite pass metadata.
    Updates detection pass dates and dynamically adjusts confidence scores based on
    atmospheric transparency (cloud cover %) and solar zenith angle.

    Args:
        pozas: List of DetectedPoza to synchronize.
        sentinel_meta: Latest Sentinel-2 pass metadata for the coastal tile.

    Returns:
        List[DetectedPoza]: Updated list of DetectedPoza instances.
    """
    # Extract date string (YYYY-MM-DD) from ISO datetime
    pass_date = sentinel_meta.datetime.split("T")[0] if "T" in sentinel_meta.datetime else sentinel_meta.datetime[:10]

    # Atmospheric quality modifier:
    # Clear sky (< 5% cloud) and high sun (> 45 deg) boosts SDB confidence
    cloud_pct = sentinel_meta.cloud_cover_pct
    sun_elev = sentinel_meta.sun_elevation

    conf_delta = 0.0
    if cloud_pct < 5.0 and sun_elev >= 45.0:
        conf_delta = 1.5
    elif cloud_pct < 10.0:
        conf_delta = 0.5
    elif cloud_pct > 20.0:
        conf_delta = -3.0

    synced_pozas: List[DetectedPoza] = []
    for p in pozas:
        new_conf = p.confidence_score
        # Only Stumpf SDB and Breaker Gap are dynamically affected by satellite pass clarity
        if p.detection_method in [DetectionMethod.SDB_STUMPF.value, DetectionMethod.BREAKER_GAP.value]:
            new_conf = round(max(50.0, min(99.0, p.confidence_score + conf_delta)), 1)

        synced_pozas.append(
            replace(
                p,
                satellite_pass_date=pass_date,
                confidence_score=new_conf,
            )
        )

    return synced_pozas
