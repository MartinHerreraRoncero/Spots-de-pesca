"""
Bathymetry and seabed topography analytics for Andalusian coastal fishing spots.
Evaluates depth gradients (slope %), seabed rugosity index, and structural hotspot potential.
"""

from __future__ import annotations
import math
from typing import Tuple
from src.models.spot import Spot, BathymetryProfile


def calculate_bathymetry_profile(spot: Spot) -> BathymetryProfile:
    """
    Computes seabed depth gradient, rugosity index, and structural morphology
    calibrated against Andalusian geomorphological and coastal bathymetry zones.
    """
    depth = spot.depth_m if spot.depth_m is not None else 8.0
    zone = spot.zone
    subzone = spot.subzone
    spot_type = spot.spot_type
    bottom_type = spot.bottom_type

    # 1. Base Gradient (%) and Drop-off Distance (m) by Coastal Subzone
    # In Granada/Costa Tropical and Estrecho, drop-offs are immediate (<40m from shore with >15% slope).
    # In Huelva and Doñana, continental shelf is very wide (<2% slope, drop-offs >250m).
    if "Granada" in subzone or "Tropical" in subzone:
        base_slope = 18.5
        drop_off_dist = 35.0
    elif "Estrecho" in subzone:
        base_slope = 22.0
        drop_off_dist = 25.0
    elif "Cabo de Gata" in subzone:
        base_slope = 14.0
        drop_off_dist = 45.0
    elif "Costa del Sol" in subzone:
        base_slope = 7.5
        drop_off_dist = 90.0
    elif "Cádiz" in subzone or "Cadiz" in subzone:
        base_slope = 4.8
        drop_off_dist = 130.0
    elif "Poniente" in subzone:
        base_slope = 6.0
        drop_off_dist = 110.0
    else:  # Huelva / Golfo de Cádiz exterior
        base_slope = 1.8
        drop_off_dist = 220.0

    # Spot Type Modifiers
    if spot_type in ["Roquedo / Acantilado", "Cala Mixta"]:
        slope = base_slope * 1.35
        drop_off_dist = max(15.0, drop_off_dist * 0.6)
    elif spot_type in ["Espigón / Estructura"]:
        slope = base_slope * 1.15
        drop_off_dist = max(20.0, drop_off_dist * 0.7)
    elif spot_type in ["Ría / Estuario", "Desembocadura"]:
        slope = base_slope * 0.85
        drop_off_dist = drop_off_dist * 1.1
    else:  # Playa / Arenal
        slope = base_slope * 0.9

    # 2. Rugosity Index (0.0 to 1.0)
    # Reflects structural crevices, bottom complexity, stones vs flat sand
    if "Roca laminar" in bottom_type or "Laja" in bottom_type:
        base_rugosity = 0.82
    elif "Posidonia" in bottom_type:
        base_rugosity = 0.68
    elif "Cascajo" in bottom_type:
        base_rugosity = 0.55
    elif "Fango / Mixto" in bottom_type:
        base_rugosity = 0.40
    else:  # Arena fina
        base_rugosity = 0.18

    if spot_type == "Roquedo / Acantilado":
        base_rugosity = min(0.98, base_rugosity + 0.12)
    elif spot_type == "Espigón / Estructura":
        base_rugosity = min(0.92, base_rugosity + 0.10)

    # 3. Structure Classification
    if slope >= 15.0 and depth >= 12.0:
        structure = "Cantil pronunciado (Caída abrupta)"
    elif base_rugosity >= 0.70 and depth < 10.0:
        structure = "Bajo rocoso somero (Rompientes de piedra)"
    elif spot_type in ["Desembocadura", "Ría / Estuario"]:
        structure = "Canalizo de marea (Fosa de corriente)"
    elif slope >= 4.0 and base_rugosity < 0.45:
        structure = "Barra de arena con escalón de rompiente"
    elif slope >= 5.0 and base_rugosity >= 0.50:
        structure = "Fondo mixto escalonado (Cascajo y roca)"
    else:
        structure = "Plataforma arenosa suave (Arenal uniforme)"

    # 4. Topographic Hotspot Score (0 - 100)
    # Higher for structural diversity (moderate/high slope + rugosity) where fish feed
    slope_score = min(100.0, (slope / 20.0) * 85.0 + 15.0)
    rugosity_score = base_rugosity * 100.0
    depth_suitability = min(100.0, (depth / 20.0) * 70.0 + 30.0)

    hotspot_score = round(0.40 * slope_score + 0.40 * rugosity_score + 0.20 * depth_suitability, 1)

    return BathymetryProfile(
        depth_m=round(depth, 1),
        depth_gradient_pct=round(slope, 1),
        rugosity_index=round(base_rugosity, 2),
        structure_type=structure,
        topographic_hotspot_score=hotspot_score,
        drop_off_distance_m=round(drop_off_dist, 0),
    )
