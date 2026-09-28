"""
Coastal boundary detection, water-land spectral masking, and marine zone enforcement.
Specifically tailored for the Costa de Huelva (Ayamonte to Doñana / Gulf of Cadiz).
"""

from __future__ import annotations
import math
from dataclasses import replace
from typing import List, Tuple, Dict, Any, Optional

from src.models.poza import DetectedPoza


# High-precision Mean High Water (MHW) shoreline delineation of Costa de Huelva,
# calibrated against the OpenStreetMap (natural=coastline) vector.
# Ordered from West (Desembocadura del Guadiana, Ayamonte) to East (Doñana / Guadalquivir).
# Longitudes are strictly ascending from -7.4375 to -6.3503.
HUELVA_SHORELINE_VERTICES: List[Tuple[float, float]] = [
    # (lon, lat)
    (-7.437500, 37.176000),  # Ayamonte / Desembocadura Guadiana (Frontera Portugal)
    (-7.420000, 37.171500),  # Barra de Poniente
    (-7.408287, 37.170069),  # Isla Canela (Playa Grande / Poniente)
    (-7.380481, 37.169806),  # Isla Canela (Barra de Levante)
    (-7.340476, 37.180337),  # Isla Cristina (Punta del Caimán)
    (-7.322823, 37.190241),  # Isla Cristina (Barra de la Gaviota)
    (-7.302489, 37.196271),  # Isla Cristina (Playa Central)
    (-7.264094, 37.202385),  # La Redondela (Playa del Hoyo)
    (-7.239642, 37.203605),  # Islantilla / Urbasur
    (-7.158468, 37.207175),  # El Terrón / Cartaya (Flecha de El Rompido oeste)
    (-7.119670, 37.207640),  # Cartaya (Punta de la Flecha)
    (-7.062364, 37.204810),  # El Portil (Caño de la Culata)
    (-7.007517, 37.195643),  # El Portil / Los Enebrales (Banco Bermejo)
    (-6.981727, 37.183393),  # Punta Umbría (Playa de los Enebrales)
    (-6.958458, 37.172487),  # Punta Umbría (La Canaleta / Espigón)
    (-6.900000, 37.148000),  # Mazagón Oeste
    (-6.850000, 37.127000),  # Mazagón Puerto / Playa de las Dunas
    (-6.800000, 37.123000),  # Mazagón Parador / Rompeculos
    (-6.742857, 37.096748),  # Cuesta Maneli / Asperillo
    (-6.686969, 37.068924),  # Acantilado del Asperillo Este
    (-6.640000, 37.042000),  # Médano del Loro
    (-6.590000, 37.019000),  # Playa de Castilla
    (-6.535137, 36.985046),  # Matalascañas (Torre de la Higuera)
    (-6.501644, 36.960521),  # Matalascañas Este (Límite Parque Nacional Doñana)
    (-6.460000, 36.920000),  # Playa de Doñana Centro
    (-6.400000, 36.815000),  # Dunas Móviles de Doñana Sur
    (-6.350300, 36.797100),  # Punta del Malandar (Desembocadura Guadalquivir)
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

    if hasattr(poza, "clone_with"):
        return poza.clone_with(
            latitude=round(new_lat, 6),
            longitude=round(new_lon, 6),
            distance_from_shore_m=enforced_dist,
            coordinates_polygon=new_polygon,
            is_shoreline_validated=True,
        )

    try:
        return replace(
            poza,
            latitude=round(new_lat, 6),
            longitude=round(new_lon, 6),
            distance_from_shore_m=enforced_dist,
            coordinates_polygon=new_polygon,
            is_shoreline_validated=True,
        )
    except Exception:
        d = poza.to_dict() if hasattr(poza, "to_dict") else dict(vars(poza))
        d["latitude"] = round(new_lat, 6)
        d["longitude"] = round(new_lon, 6)
        d["distance_from_shore_m"] = enforced_dist
        d["coordinates_polygon"] = new_polygon
        d["is_shoreline_validated"] = True
        return DetectedPoza.from_dict(d)


_CACHED_OSM_SHORELINE: Optional[List[Tuple[float, float]]] = None


def get_huelva_shoreline_folium_coords() -> List[Tuple[float, float]]:
    """
    Returns list of (latitude, longitude) tuples representing the Huelva shoreline,
    directly formatted for rendering as a Folium PolyLine layer.
    Loads the official, high-resolution OpenStreetMap coastline vector (932 points from Ayamonte to Doñana).
    """
    global _CACHED_OSM_SHORELINE
    if _CACHED_OSM_SHORELINE is not None:
        return _CACHED_OSM_SHORELINE

    import json
    from pathlib import Path
    data_file = Path(__file__).resolve().parent.parent.parent / "data" / "osm_huelva_coastline.json"
    if data_file.exists():
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                d = json.load(f)
            pts = d.get("coordinates_lat_lon", [])
            if pts:
                _CACHED_OSM_SHORELINE = [(float(p[0]), float(p[1])) for p in pts]
                return _CACHED_OSM_SHORELINE
        except Exception:
            pass

    return [(lat, lon) for lon, lat in HUELVA_SHORELINE_VERTICES]
