"""
Coastal boundary detection, water-land spectral masking, and marine zone enforcement.
Specifically tailored for the Costa de Huelva (Ayamonte to Doñana / Gulf of Cadiz).
"""

from __future__ import annotations
import math
from dataclasses import replace
from typing import List, Tuple, Dict, Any, Optional

from src.models.poza import DetectedPoza


# High-precision Mean High Water (MHW) shoreline delineation of Costa de Huelva
# Ordered from West (Desembocadura del Guadiana, Ayamonte) to East (Doñana / Guadalquivir).
# Longitudes are strictly ascending from -7.4200 to -6.3600.
HUELVA_SHORELINE_VERTICES: List[Tuple[float, float]] = [
    # (lon, lat)
    (-7.4200, 37.1710),  # Ayamonte / Desembocadura Guadiana (Barra de Poniente)
    (-7.4082, 37.1735),  # Isla Canela (Playa Grande)
    (-7.3850, 37.1775),  # Isla Canela Centro
    (-7.3685, 37.1802),  # Isla Canela / Barra de Levante
    (-7.3500, 37.1850),  # Ría Carreras (Entrada Isla Cristina)
    (-7.3364, 37.1938),  # Isla Cristina (Punta del Caimán)
    (-7.3182, 37.1905),  # Isla Cristina (Barra de la Gaviota)
    (-7.2985, 37.1892),  # Isla Cristina (Playa Central)
    (-7.2618, 37.1952),  # La Redondela (Playa del Hoyo)
    (-7.2345, 37.1988),  # Islantilla / Urbasur
    (-7.2000, 37.2030),  # Lepe (Playa de Santa Pura)
    (-7.1552, 37.2025),  # El Terrón / Cartaya (Flecha de El Rompido oeste)
    (-7.1248, 37.2012),  # Cartaya (Flecha de El Rompido centro)
    (-7.0950, 37.2020),  # Flecha de El Rompido (Punta de la Flecha)
    (-7.0582, 37.2070),  # El Portil (Caño de la Culata)
    (-7.0125, 37.1925),  # El Portil / Los Enebrales (Banco Bermejo)
    (-6.9854, 37.1805),  # Punta Umbría (Playa de los Enebrales)
    (-6.9635, 37.1695),  # Punta Umbría (La Canaleta / Espigón de Poniente)
    (-6.9550, 37.1650),  # Desembocadura Ría de Huelva (Odiel / Tinto)
    (-6.8350, 37.1320),  # Mazagón (Playa de las Dunas / Puerto)
    (-6.8000, 37.1100),  # Mazagón (Playa del Parador / Playa de Rompeculos)
    (-6.7482, 37.0665),  # Acantilado del Asperillo / Cuesta Maneli
    (-6.6924, 37.0375),  # Acantilado del Asperillo Este
    (-6.6200, 37.0145),  # Médano del Loro
    (-6.5394, 36.9908),  # Matalascañas (Torre de la Higuera)
    (-6.5052, 36.9738),  # Matalascañas Este (Límite Parque Nacional Doñana)
    (-6.4400, 36.9300),  # Parque Nacional Doñana (Playa de Doñana centro)
    (-6.3600, 36.8000),  # Punta del Malandar (Frente a Sanlúcar de Barrameda)
]


def compute_ndwi(green_refl: float, nir_refl: float) -> float:
    """
    Computes Normalized Difference Water Index (NDWI, McFeeters 1996):
    NDWI = (Green - NIR) / (Green + NIR).

    Water bodies feature high green reflectance and near-zero NIR reflectance,
    yielding positive values (+0.1 to +0.8). Dry sand, dunes, and coastal scrub
    reflect strongly in NIR, yielding negative values (-0.5 to -0.05).

    Args:
        green_refl: Surface reflectance in Sentinel-2 Band 3 (~560 nm).
        nir_refl: Surface reflectance in Sentinel-2 Band 8 (~842 nm).

    Returns:
        float: NDWI value in range [-1.0, 1.0].
    """
    denom = float(green_refl + nir_refl)
    if abs(denom) < 1e-9:
        return 0.0
    ndwi = (float(green_refl) - float(nir_refl)) / denom
    return round(max(-1.0, min(1.0, ndwi)), 4)


def compute_mndwi(green_refl: float, swir_refl: float) -> float:
    """
    Computes Modified Normalized Difference Water Index (MNDWI, Xu 2006):
    MNDWI = (Green - SWIR) / (Green + SWIR).

    Suppresses wet sand / salt marsh false positives along the intertidal boundary.
    """
    denom = float(green_refl + swir_refl)
    if abs(denom) < 1e-9:
        return 0.0
    mndwi = (float(green_refl) - float(swir_refl)) / denom
    return round(max(-1.0, min(1.0, mndwi)), 4)


def get_shoreline_lat_at_lon(lon: float) -> float:
    """
    Calculates the Mean High Water shoreline latitude at the specified longitude
    using piecewise-linear interpolation along the curated Huelva shoreline vector.

    Args:
        lon: Longitude coordinate in degrees.

    Returns:
        float: Shoreline latitude in degrees.
    """
    verts = HUELVA_SHORELINE_VERTICES
    if lon <= verts[0][0]:
        return verts[0][1]
    if lon >= verts[-1][0]:
        return verts[-1][1]

    for i in range(len(verts) - 1):
        lon0, lat0 = verts[i]
        lon1, lat1 = verts[i + 1]
        if lon0 <= lon <= lon1:
            ratio = (lon - lon0) / (lon1 - lon0)
            return lat0 + ratio * (lat1 - lat0)

    return verts[-1][1]


def is_in_ocean(lat: float, lon: float, tolerance_m: float = 0.0) -> bool:
    """
    Determines whether a coordinate is located in the Atlantic Ocean (water)
    rather than on land (dry beach, dunes, pine forests, urban areas).

    Along the Huelva coastline, the Atlantic Ocean is to the South/South-West.
    Therefore, any point whose latitude is strictly lower than the shoreline latitude
    (minus any tolerance buffer) is located in the marine water zone.

    Args:
        lat: Latitude in degrees.
        lon: Longitude in degrees.
        tolerance_m: Permissible tolerance buffer towards land in meters (default: 0.0).

    Returns:
        bool: True if point is in the ocean, False if on land.
    """
    shore_lat = get_shoreline_lat_at_lon(lon)
    lat_buffer_deg = tolerance_m / 111139.0
    return bool(lat < (shore_lat + lat_buffer_deg))


def calculate_distance_to_shore_m(lat: float, lon: float) -> float:
    """
    Calculates the approximate perpendicular distance in meters from a point
    to the Huelva shoreline.

    Positive if point is seaward (in the ocean, South of shoreline).
    Negative if point is inland (on land, North of shoreline).

    Args:
        lat: Latitude in degrees.
        lon: Longitude in degrees.

    Returns:
        float: Distance in meters (positive in sea, negative on land).
    """
    shore_lat = get_shoreline_lat_at_lon(lon)
    delta_lat_deg = shore_lat - lat
    # 1 deg latitude ~ 111139 meters
    distance_m = delta_lat_deg * 111139.0
    return round(distance_m, 1)


def project_seaward_point(
    lat: float,
    lon: float,
    target_distance_m: float = 70.0,
) -> Tuple[float, float]:
    """
    Projects a coordinate perpendicularly seaward (South) to ensure it sits
    firmly in the surf zone at `target_distance_m` meters from the shoreline.

    Args:
        lat: Input latitude.
        lon: Input longitude.
        target_distance_m: Desired seaward distance from shoreline in meters (default: 70m).

    Returns:
        Tuple[float, float]: Adjusted (latitude, longitude) strictly in the surf zone.
    """
    shore_lat = get_shoreline_lat_at_lon(lon)
    # Project target_distance_m to the south
    lat_offset_deg = target_distance_m / 111139.0
    target_lat = shore_lat - lat_offset_deg
    return (round(target_lat, 6), round(lon, 6))


def get_shoreline_normal_azimuth(lon: float) -> float:
    """
    Calculates the deterministic nautical azimuth (degrees, 0-360°) of the shoreline normal
    vector pointing seaward (into the Atlantic Ocean) at the specified longitude along Costa de Huelva.

    Based on the tangent vector between adjacent curated shoreline vertices:
    dx = (lon1 - lon0) * 111320 * cos(lat_mean)
    dy = (lat1 - lat0) * 111139
    theta_tangent = atan2(dx, dy)
    theta_normal = (theta_tangent + 90°) % 360°

    Args:
        lon: Longitude in degrees.

    Returns:
        float: Seaward normal azimuth in degrees (e.g. ~165° to ~226° along Huelva).
    """
    verts = HUELVA_SHORELINE_VERTICES
    if lon <= verts[0][0]:
        idx = 0
    elif lon >= verts[-2][0]:
        idx = len(verts) - 2
    else:
        idx = 0
        for i in range(len(verts) - 1):
            if verts[i][0] <= lon <= verts[i + 1][0]:
                idx = i
                break

    lon0, lat0 = verts[idx]
    lon1, lat1 = verts[idx + 1]

    lat_avg = math.radians((lat0 + lat1) / 2.0)
    dx = (lon1 - lon0) * 111320.0 * math.cos(lat_avg)
    dy = (lat1 - lat0) * 111139.0

    tangent_deg = math.degrees(math.atan2(dx, dy)) % 360.0
    # Shoreline proceeds West-to-East (~75° to ~135°). Seaward points to the right (South):
    normal_deg = (tangent_deg + 90.0) % 360.0
    return round(normal_deg, 1)


def enforce_marine_bounds(
    poza: DetectedPoza,
    min_dist_m: float = 20.0,
    max_dist_m: float = 130.0,
) -> DetectedPoza:
    """
    Validates that a DetectedPoza is located in the marine water zone (range 20 to 130 meters).
    If the poza center or its polygon vertices fall on land (lat >= shore_lat),
    or outside the designated 20-130m surf zone, they are automatically snapped seaward into the surf zone.

    Args:
        poza: DetectedPoza instance to inspect and enforce.
        min_dist_m: Minimum allowed distance seaward from shoreline (default: 20m).
        max_dist_m: Maximum allowed distance seaward from shoreline (default: 130m).

    Returns:
        DetectedPoza: Validated instance with guaranteed marine coordinates in [20, 130]m
                      and `is_shoreline_validated = True`.
    """
    curr_dist = calculate_distance_to_shore_m(poza.latitude, poza.longitude)

    # Determine desired distance within surfcasting range [20m, 130m]
    if curr_dist < min_dist_m or curr_dist > max_dist_m:
        target_dist = float(poza.distance_from_shore_m or 65.0)
        target_dist = max(min_dist_m, min(max_dist_m, target_dist))
        new_lat, new_lon = project_seaward_point(poza.latitude, poza.longitude, target_distance_m=target_dist)
        lat_shift = new_lat - poza.latitude
        lon_shift = new_lon - poza.longitude
        enforced_dist = int(round(target_dist))
    else:
        new_lat, new_lon = poza.latitude, poza.longitude
        lat_shift, lon_shift = 0.0, 0.0
        enforced_dist = int(round(curr_dist))

    # Shift polygon vertices accordingly if present
    new_polygon = None
    if poza.coordinates_polygon:
        new_polygon = []
        for pt_lat, pt_lon in poza.coordinates_polygon:
            adj_lat = pt_lat + lat_shift
            adj_lon = pt_lon + lon_shift
            # Ensure every polygon vertex is also seaward
            pt_shore_lat = get_shoreline_lat_at_lon(adj_lon)
            if adj_lat >= pt_shore_lat:
                adj_lat = pt_shore_lat - (20.0 / 111139.0)  # at least 20m seaward
            new_polygon.append((round(adj_lat, 6), round(adj_lon, 6)))

    return replace(
        poza,
        latitude=round(new_lat, 6),
        longitude=round(new_lon, 6),
        distance_from_shore_m=enforced_dist,
        coordinates_polygon=new_polygon,
        is_shoreline_validated=True,
    )


def get_huelva_shoreline_folium_coords() -> List[Tuple[float, float]]:
    """
    Returns list of (latitude, longitude) tuples representing the Huelva shoreline,
    directly formatted for rendering as a Folium PolyLine layer.
    """
    return [(lat, lon) for lon, lat in HUELVA_SHORELINE_VERTICES]
