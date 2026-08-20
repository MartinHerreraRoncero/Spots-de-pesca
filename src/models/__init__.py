"""
Model definitions for spots, marine buoys, tides, wind aspect, species scores, solunar, and oceanography.
"""

from src.models.spot import (
    Spot,
    MarineBuoy,
    BuoyObservation,
    TideState,
    WindRelativeAspect,
    SpeciesScores,
    SolunarWindow,
    SolunarDaySummary,
    MarineConditions,
    WeatherConditions,
    ScoreBreakdown,
    HourlySpotForecast,
    ScoringWeights,
)

__all__ = [
    "Spot",
    "MarineBuoy",
    "BuoyObservation",
    "TideState",
    "WindRelativeAspect",
    "SpeciesScores",
    "SolunarWindow",
    "SolunarDaySummary",
    "MarineConditions",
    "WeatherConditions",
    "ScoreBreakdown",
    "HourlySpotForecast",
    "ScoringWeights",
]
