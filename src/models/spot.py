"""
Data models and typed structures for the Andalusian Marine Fishing App,
including spots, ocean currents, tides, wind relative aspect, species scoring,
solunar ephemeris, oceanographic buoys, bathymetric profile, water clarity, and river runoff.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Spot(BaseModel):
    """Represents a geographic fishing spot along the Andalusian coastline."""
    id: str
    name: str
    province: str
    zone: str  # "Atlántico", "Mediterráneo", "Estrecho"
    subzone: str  # e.g., "Costa de Huelva", "Costa de la Luz Gaditana", "Costa del Sol", etc.
    municipality: Optional[str] = None
    latitude: float
    longitude: float
    description: str
    spot_type: str = "Playa / Arenal"  # "Playa / Arenal", "Espigón / Estructura", "Ría / Estuario", "Roquedo / Acantilado", "Cala Mixta", "Desembocadura"
    bottom_type: str = "Arena fina"  # "Arena fina", "Cascajo y grava", "Roca laminar / Laja", "Fango / Mixto", "Posidonia y arena"
    accessibility: str = "Fácil / A pie"  # "Fácil / A pie", "Caminata media", "Acceso técnico / Escarpado", "Embarcación / Kayak"
    coastline_bearing: float = 180.0  # Direction (degrees 0-360) facing the sea normal to the coast
    target_species: List[str] = Field(default_factory=list)
    recommended_techniques: List[str] = Field(default_factory=list)
    depth_m: Optional[float] = None
    tide_dependent: bool = True
    is_custom: bool = False

    @property
    def coordinates(self) -> tuple[float, float]:
        return (self.latitude, self.longitude)


class MarineBuoy(BaseModel):
    """Represents an official oceanographic buoy station from Puertos del Estado / REDEXT / REDCOS."""
    id: str
    name: str
    code: str
    network: str  # "REDEXT (Red Exterior)" | "REDCOS (Red Costera)"
    operator: str
    province: str
    zone: str
    latitude: float
    longitude: float
    depth_m: float
    buoy_type: str
    sensors: List[str] = Field(default_factory=list)
    description: str


@dataclass
class BuoyObservation:
    """Current observational reading / telemetry from a marine buoy."""
    buoy_id: str
    timestamp: datetime
    wave_height_hs: float  # meters
    wave_period_tp: float  # seconds
    wave_direction: float  # degrees
    sea_surface_temperature: float  # Celsius
    surface_pressure: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None
    status: str = "Operativa (En línea)"


@dataclass
class TideState:
    """Astronomical and hydraulic tidal state for a spot and time."""
    coefficient: int  # Spanish standard 20 to 120
    state_name: str  # "Llenante (Subiendo)", "Vaciante (Bajando)", "Repunte de Pleamar", "Repunte de Bajamar"
    is_slack_water: bool  # True if within ±45 min of high/low tide
    next_high_tide: Optional[datetime] = None
    next_low_tide: Optional[datetime] = None
    minutes_to_high_tide: Optional[int] = None
    minutes_to_low_tide: Optional[int] = None
    tide_height_est_m: float = 1.5


@dataclass
class WindRelativeAspect:
    """Wind direction and impact relative to the specific coastline orientation."""
    relative_angle: float  # -180 to +180
    wind_type: str  # "Onshore", "Offshore", "Cross-shore"
    is_onshore: bool
    is_offshore: bool
    is_cross_shore: bool
    upwelling_risk: bool
    effect_summary: str


@dataclass
class SpeciesScores:
    """Specialized heuristic scores for targeted fish species & techniques (each 0 - 100)."""
    dorada_score: float  # Sparus aurata (Surfcasting en arenales y canales de marea)
    lubina_score: float  # Dicentrarchus labrax (Spinning en rompiente y espuma)
    sargo_score: float  # Diplodus sargus (Rockfishing en roquedos batidos)
    calamar_score: float  # Loligo vulgaris (Eging nocturno en aguas claras y calmas)
    denton_score: float  # Dentex dentex (Shore Jigging y pesca profunda en cantiles)
    corvina_score: float  # Argyrosomus regius (Grandes corrientes de marea viva en Golfo de Cádiz)


@dataclass
class BathymetryProfile:
    """Submarine bathymetric gradient and seabed rugosity profile."""
    depth_m: float  # Current spot depth
    depth_gradient_pct: float  # Slope % (e.g. 1.5% gentle beach to 25% steep drop-off)
    rugosity_index: float  # 0.0 (flat sand) to 1.0 (rocky labyrinths, ledges)
    structure_type: str  # "Cantil pronunciado", "Bajo rocoso somero", "Barra de arena con escalón", "Canalizo de marea", "Plataforma arenosa"
    topographic_hotspot_score: float  # Structural hotspot quality (0 - 100)
    drop_off_distance_m: float = 80.0  # Distance to significant drop-off from shore


@dataclass
class WaterClarityConditions:
    """Bio-optical water clarity, turbidity, and satellite SST thermal front detection."""
    secchi_depth_m: float  # Visibility depth in meters (0.5m to 12.0m)
    turbidity_ntu: float  # Turbidity in NTU (0.5 clean to 20+ chocolate)
    clarity_class: str  # "Agua Tomada (Chocolate)", "Agua Rizada / Nutrientes", "Agua Clara Turquesa", "Agua Azul Cristalina"
    thermal_front_detected: bool  # True if sea surface temperature gradient exceeds threshold
    sst_gradient_c_km: float  # °C / km gradient
    convergence_zone: bool  # True if plankton/nutrient convergence expected


@dataclass
class RiverRunoffConditions:
    """Hydrological river discharge, basin rain, and freshwater plume impact."""
    nearest_river_name: str  # e.g. "Río Guadalquivir", "Río Guadiana", "Río Guadalfeo"
    distance_to_mouth_km: float  # Distance to river mouth
    basin_rain_72h_mm: float  # Estimated recent accumulated rainfall in river basin
    plume_active: bool  # True if freshwater & silt plume influences this spot
    salinity_drop_psu: float  # Estimated salinity reduction (0 to 15+ PSU)
    plume_impact_summary: str


@dataclass
class SolunarWindow:
    """Represents a specific solunar major or minor activity window."""
    name: str
    window_type: str  # "MAJOR" | "MINOR"
    peak_time: datetime
    start_time: datetime
    end_time: datetime
    quality_bonus: float
    description: str


@dataclass
class SolunarDaySummary:
    """Astronomical and solunar details for a spot on a given day."""
    date: datetime
    moon_phase_name: str
    moon_illumination: float
    moon_age_days: float
    is_spring_tide: bool
    sunrise: Optional[datetime]
    sunset: Optional[datetime]
    dawn_twilight: Optional[datetime]
    dusk_twilight: Optional[datetime]
    moonrise: Optional[datetime]
    moonset: Optional[datetime]
    moon_zenith: Optional[datetime]
    moon_nadir: Optional[datetime]
    windows: List[SolunarWindow] = field(default_factory=list)


@dataclass
class MarineConditions:
    """Oceanographic metrics from Open-Meteo Marine API, including physical currents."""
    timestamp: datetime
    wave_height: float  # meters
    wave_period: float  # seconds
    wave_direction: float  # degrees
    sea_surface_temperature: float  # Celsius
    current_velocity_knots: float = 0.5  # Knots (1 knot = 1.852 km/h)
    current_direction: float = 180.0  # Direction (degrees) where current is flowing towards
    current_intensity_level: str = "Corriente Suave"  # "Aguas Paradas", "Corriente Suave", "Corriente Moderada", "Corriente Fuerte", "Corriente Extrema"
    swell_wave_height: Optional[float] = None
    swell_wave_period: Optional[float] = None
    calibrated_wave_height: Optional[float] = None


@dataclass
class WeatherConditions:
    """Meteorological metrics from Open-Meteo Forecast API."""
    timestamp: datetime
    surface_pressure: float
    wind_speed_10m: float
    wind_direction_10m: float
    cloud_cover: float
    precipitation: float
    temperature_2m: float


@dataclass
class ScoreBreakdown:
    """Comprehensive scoring breakdown with multi-species, currents, tides, wind aspect, bathymetry, clarity, and runoff."""
    overall_score: float  # 0 - 100
    rating_tier: str
    rating_color: str
    
    # Sub-scores
    pressure_score: float
    pressure_delta_3h: float
    pressure_delta_6h: float
    
    solunar_score: float
    solunar_window_active: Optional[str]
    is_crepuscular_overlap: bool
    
    marine_score: float
    wind_score: float
    moon_phase_score: float
    
    # Advanced Scientific Extensions
    tide_state: TideState
    wind_aspect: WindRelativeAspect
    species_scores: SpeciesScores
    buoy_calibration_applied: bool = False
    calibrating_buoy_name: Optional[str] = None
    
    # New Scientific Modules
    bathymetry: Optional[BathymetryProfile] = None
    water_clarity: Optional[WaterClarityConditions] = None
    river_runoff: Optional[RiverRunoffConditions] = None
    
    tactical_tips: List[str] = field(default_factory=list)


@dataclass
class HourlySpotForecast:
    """Unified hourly record with all observations, ocean currents, solunar, tides, and scores."""
    spot_id: str
    timestamp: datetime
    marine: MarineConditions
    weather: WeatherConditions
    solunar_summary: SolunarDaySummary
    score: ScoreBreakdown


@dataclass
class ScoringWeights:
    """User-adjustable weighting coefficients for the heuristic scoring engine."""
    weight_pressure: float = 0.25
    weight_solunar: float = 0.30
    weight_marine: float = 0.20
    weight_wind: float = 0.15
    weight_moon_phase: float = 0.10

    def normalized(self) -> ScoringWeights:
        total = (self.weight_pressure + self.weight_solunar +
                 self.weight_marine + self.weight_wind + self.weight_moon_phase)
        if total <= 0:
            return ScoringWeights()
        return ScoringWeights(
            weight_pressure=self.weight_pressure / total,
            weight_solunar=self.weight_solunar / total,
            weight_marine=self.weight_marine / total,
            weight_wind=self.weight_wind / total,
            weight_moon_phase=self.weight_moon_phase / total,
        )
