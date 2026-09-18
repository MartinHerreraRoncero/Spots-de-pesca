"""
Model definitions for spots, marine buoys, tides, wind aspect, species scores,
solunar, bathymetry, water clarity, and river runoff.
"""

from src.models.spot import (
    Spot,
    MarineBuoy,
    BuoyObservation,
    TideState,
    WindRelativeAspect,
    SpeciesScores,
    BathymetryProfile,
    WaterClarityConditions,
    RiverRunoffConditions,
    SolunarWindow,
    SolunarDaySummary,
    MarineConditions,
    WeatherConditions,
    ScoreBreakdown,
    HourlySpotForecast,
    ScoringWeights,
)

from src.models.poza import (
    DetectedPoza,
    SentinelPassMetadata,
    DetectionMethod,
)

__all__ = [
    "Spot",
    "MarineBuoy",
    "BuoyObservation",
    "TideState",
    "WindRelativeAspect",
    "SpeciesScores",
    "BathymetryProfile",
    "WaterClarityConditions",
    "RiverRunoffConditions",
    "SolunarWindow",
    "SolunarDaySummary",
    "MarineConditions",
    "WeatherConditions",
    "ScoreBreakdown",
    "HourlySpotForecast",
    "ScoringWeights",
    "DetectedPoza",
    "SentinelPassMetadata",
    "DetectionMethod",
]
