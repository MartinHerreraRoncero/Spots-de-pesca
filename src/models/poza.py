"""
Data models for coastal holes/depressions (pozas) and Sentinel-2 satellite pass metadata.
Specifically tailored for the Andalusian Atlantic coast (e.g. Huelva, Gulf of Cadiz).
"""

from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Tuple, Literal, Dict, Any
from enum import Enum


class DetectionMethod(str, Enum):
    """Detection methodology used to identify the coastal depression/poza."""
    SDB_STUMPF = "SDB_STUMPF"         # Satellite Derived Bathymetry using Stumpf ratio (Blue/Green log ratio)
    BREAKER_GAP = "BREAKER_GAP"       # Wave breaker line discontinuity analysis
    PNOA_ORTHO = "PNOA_ORTHO"         # High-resolution PNOA aerial orthophotography verification


@dataclass
class DetectedPoza:
    """
    Represents a detected coastal hole, trough, or depression (poza/canal)
    formed by wave breaking and littoral drift dynamics.
    """
    id: str
    name: str
    beach_name: str
    latitude: float
    longitude: float
    detection_method: str  # Literal/enum: "SDB_STUMPF", "BREAKER_GAP", "PNOA_ORTHO"
    distance_from_shore_m: int
    width_m: int
    length_m: int
    relative_depth_m: float
    confidence_score: float  # 0.0 to 100.0
    target_species: List[str]
    optimal_tide_stage: str
    satellite_pass_date: str
    coordinates_polygon: Optional[List[Tuple[float, float]]] = None
    persistence_score: float = 90.0
    temporal_passes_count: int = 1
    observation_dates: List[str] = field(default_factory=list)
    drift_offset_m: float = 0.0
    morphodynamic_stability: str = "Foso Estable Confirmado"
    is_shoreline_validated: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to standard dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DetectedPoza:
        """Create a DetectedPoza instance from a dictionary."""
        coords = data.get("coordinates_polygon")
        if coords is not None:
            coords = [(float(pt[0]), float(pt[1])) for pt in coords]

        obs_dates = data.get("observation_dates")
        if obs_dates is None:
            sat_date = str(data.get("satellite_pass_date", ""))
            obs_dates = [sat_date] if sat_date else []

        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            beach_name=str(data["beach_name"]),
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            detection_method=str(data["detection_method"]),
            distance_from_shore_m=int(data["distance_from_shore_m"]),
            width_m=int(data["width_m"]),
            length_m=int(data["length_m"]),
            relative_depth_m=float(data["relative_depth_m"]),
            confidence_score=float(data["confidence_score"]),
            target_species=list(data.get("target_species", [])),
            optimal_tide_stage=str(data.get("optimal_tide_stage", "")),
            satellite_pass_date=str(data.get("satellite_pass_date", "")),
            coordinates_polygon=coords,
            persistence_score=float(data.get("persistence_score", 90.0)),
            temporal_passes_count=int(data.get("temporal_passes_count", 1)),
            observation_dates=list(obs_dates),
            drift_offset_m=float(data.get("drift_offset_m", 0.0)),
            morphodynamic_stability=str(data.get("morphodynamic_stability", "Foso Estable Confirmado")),
            is_shoreline_validated=bool(data.get("is_shoreline_validated", True)),
        )


@dataclass
class SentinelPassMetadata:
    """
    Metadata capturing Sentinel-2 MSI L2A satellite pass information
    for the target coastal AOI (Huelva / Costa de la Luz).
    """
    scene_id: str
    datetime: str
    cloud_cover_pct: float
    sun_elevation: float
    tile_id: str
    visual_url: Optional[str]
    b02_blue_url: Optional[str]
    b03_green_url: Optional[str]
    b04_red_url: Optional[str]
    b08_nir_url: Optional[str]
    cached_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to standard dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SentinelPassMetadata:
        """Create a SentinelPassMetadata instance from a dictionary."""
        return cls(
            scene_id=str(data["scene_id"]),
            datetime=str(data["datetime"]),
            cloud_cover_pct=float(data["cloud_cover_pct"]),
            sun_elevation=float(data["sun_elevation"]),
            tile_id=str(data["tile_id"]),
            visual_url=data.get("visual_url"),
            b02_blue_url=data.get("b02_blue_url"),
            b03_green_url=data.get("b03_green_url"),
            b04_red_url=data.get("b04_red_url"),
            b08_nir_url=data.get("b08_nir_url"),
            cached_at=str(data.get("cached_at", "")),
        )
