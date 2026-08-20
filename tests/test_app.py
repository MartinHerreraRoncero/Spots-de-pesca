"""
Unit and integration tests for Andalusian Marine Fishing App with advanced scientific modules:
tides, wind aspect, buoy bias correction, and multi-species scoring.
"""

import unittest
from datetime import datetime, timezone, timedelta
import pandas as pd

from src.models.spot import Spot, MarineBuoy, ScoringWeights, MarineConditions, WeatherConditions
from src.fetchers.open_meteo import (
    load_spots_from_json,
    load_marine_buoys_from_json,
    create_custom_spot_from_coords,
    get_spot_hourly_forecast,
    get_buoy_telemetry_snapshot,
)
from src.analytics.solunar import compute_daily_solunar, evaluate_solunar_for_hour
from src.analytics.tides import calculate_tide_coefficient, compute_spot_tide_state
from src.analytics.scoring import (
    calculate_wind_relative_aspect,
    apply_buoy_bias_correction,
    calculate_species_scores,
    calculate_pressure_score,
    calculate_marine_score,
    score_hourly_conditions,
)
from src.visualization.map_view import (
    create_andalucia_fishing_map,
    get_score_color,
    calculate_optimal_viewport,
    get_display_score_for_mode,
)
from src.visualization.charts import (
    create_pressure_and_score_chart,
    create_marine_and_wind_chart,
    create_score_radar_chart,
    create_species_comparison_chart,
    create_top_spots_bar_chart,
)


class TestAndaluciaFishingAppScientific(unittest.TestCase):

    def setUp(self):
        self.spots = load_spots_from_json()
        self.buoys = load_marine_buoys_from_json()
        self.test_spot = self.spots[0]  # Isla Canela / Ayamonte
        self.now_utc = datetime(2026, 8, 20, 18, 0, 0, tzinfo=timezone.utc)

    def test_tides_and_coefficient_calculations(self):
        """Tests calculation of tide coefficients (20-120) and semidiurnal tide states."""
        # Spring tide (New moon day 0)
        coef_spring = calculate_tide_coefficient(0.5, 5.0)
        self.assertGreaterEqual(coef_spring, 85)

        # Neap tide (Quarter moon day 7.5)
        coef_neap = calculate_tide_coefficient(7.5, 50.0)
        self.assertLessEqual(coef_neap, 50)

        # Spot Tide State
        solunar = compute_daily_solunar(self.test_spot, self.now_utc)
        tide_state = compute_spot_tide_state(self.test_spot, self.now_utc, solunar)
        self.assertGreaterEqual(tide_state.coefficient, 20)
        self.assertLessEqual(tide_state.coefficient, 120)
        self.assertIsNotNone(tide_state.state_name)
        self.assertIsNotNone(tide_state.next_high_tide)
        self.assertIsNotNone(tide_state.next_low_tide)

    def test_wind_relative_aspect(self):
        """Tests wind direction relative to coastline bearing (Onshore/Offshore/Upwelling)."""
        # Huelva coast faces ~195° (South-Southwest)
        # 1. Wind from 195° (South-Southwest) is blowing straight onto shore -> ONSHORE
        aspect_onshore = calculate_wind_relative_aspect(195.0, 195.0, 15.0, "Atlántico")
        self.assertTrue(aspect_onshore.is_onshore)
        self.assertFalse(aspect_onshore.is_offshore)

        # 2. Wind from 15° (North-Northeast) is blowing from land out to sea -> OFFSHORE
        aspect_offshore = calculate_wind_relative_aspect(15.0, 195.0, 15.0, "Atlántico")
        self.assertTrue(aspect_offshore.is_offshore)
        self.assertFalse(aspect_offshore.is_onshore)

        # 3. Upwelling risk in Mediterranean with strong offshore wind
        aspect_upwelling = calculate_wind_relative_aspect(335.0, 155.0, 22.0, "Mediterráneo")
        self.assertTrue(aspect_upwelling.upwelling_risk)

    def test_buoy_bias_correction(self):
        """Tests in-situ wave calibration with nearest Puertos del Estado buoys."""
        telemetry = get_buoy_telemetry_snapshot(self.buoys, self.now_utc)
        marine_orig = MarineConditions(
            timestamp=self.now_utc,
            wave_height=0.7,
            wave_period=6.0,
            wave_direction=220,
            sea_surface_temperature=20.0
        )
        calibrated_h, applied, buoy_name = apply_buoy_bias_correction(self.test_spot, marine_orig, telemetry)
        self.assertTrue(applied)
        self.assertIsNotNone(buoy_name)
        self.assertGreater(calibrated_h, 0.0)

    def test_multi_species_scoring_differentiation(self):
        """Validates that heavy surf conditions score higher for Lubina than for Calamar."""
        solunar = compute_daily_solunar(self.test_spot, self.now_utc)
        tide_state = compute_spot_tide_state(self.test_spot, self.now_utc, solunar)
        wind_aspect = calculate_wind_relative_aspect(195.0, self.test_spot.coastline_bearing, 14.0, self.test_spot.zone)

        # Heavy surf condition: 1.5m waves, -1.0 hPa pressure drop
        marine_heavy = MarineConditions(
            timestamp=self.now_utc, wave_height=1.5, wave_period=8.5, wave_direction=220, sea_surface_temperature=19.0
        )
        weather_stormy = WeatherConditions(
            timestamp=self.now_utc, surface_pressure=1012.0, wind_speed_10m=16.0, wind_direction_10m=200.0,
            cloud_cover=60, precipitation=0.5, temperature_2m=21.0
        )

        spec_heavy = calculate_species_scores(
            self.test_spot, weather_stormy, marine_heavy, solunar, 70.0, tide_state, wind_aspect, 85.0, -1.2
        )
        # Lubina should score significantly higher than Calamar in 1.5m surf!
        self.assertGreater(spec_heavy.lubina_score, spec_heavy.calamar_score)

        # Calm flat sea: 0.2m waves, 5 km/h wind
        marine_calm = MarineConditions(
            timestamp=self.now_utc, wave_height=0.2, wave_period=5.0, wave_direction=220, sea_surface_temperature=21.0
        )
        weather_calm = WeatherConditions(
            timestamp=self.now_utc, surface_pressure=1018.0, wind_speed_10m=6.0, wind_direction_10m=180.0,
            cloud_cover=10, precipitation=0.0, temperature_2m=22.0
        )
        spec_calm = calculate_species_scores(
            self.test_spot, weather_calm, marine_calm, solunar, 60.0, tide_state, wind_aspect, 75.0, 0.0
        )
        # Calamar should score higher than Lubina in flat glass water!
        self.assertGreater(spec_calm.calamar_score, spec_calm.lubina_score)

    def test_ocean_currents_physics_and_impact(self):
        """Tests physical ocean currents velocity in knots and biological scoring impact."""
        forecasts = get_spot_hourly_forecast(self.test_spot, forecast_days=1)
        self.assertGreater(len(forecasts), 0)
        f0 = forecasts[0]
        
        # Verify current metrics
        self.assertGreaterEqual(f0.marine.current_velocity_knots, 0.0)
        self.assertGreaterEqual(f0.marine.current_direction, 0.0)
        self.assertLessEqual(f0.marine.current_direction, 360.0)
        self.assertIsNotNone(f0.marine.current_intensity_level)

        # Verify species differentiation on fast currents (1.8 kts):
        # Corvina should score high with 1.8 kts current, Calamar should be penalized
        solunar = compute_daily_solunar(self.test_spot, self.now_utc)
        tide_state = compute_spot_tide_state(self.test_spot, self.now_utc, solunar)
        wind_aspect = calculate_wind_relative_aspect(195.0, 195.0, 10.0, "Atlántico")
        
        marine_fast_current = MarineConditions(
            timestamp=self.now_utc, wave_height=0.7, wave_period=6.5, wave_direction=220,
            sea_surface_temperature=20.0, current_velocity_knots=1.8, current_direction=85.0
        )
        weather_std = WeatherConditions(
            timestamp=self.now_utc, surface_pressure=1015.0, wind_speed_10m=10.0,
            wind_direction_10m=195.0, cloud_cover=20, precipitation=0.0, temperature_2m=21.0
        )
        spec_scores = calculate_species_scores(
            self.test_spot, weather_std, marine_fast_current, solunar, 70.0, tide_state, wind_aspect, 80.0, 0.0
        )
        self.assertGreater(spec_scores.corvina_score, spec_scores.calamar_score)

    def test_full_pipeline_multi_species_map_and_charts(self):
        """Tests full pipeline forecast retrieval and multi-species charts."""
        forecasts = get_spot_hourly_forecast(self.test_spot, forecast_days=2)
        self.assertGreaterEqual(len(forecasts), 40)
        f0 = forecasts[0]

        # Verify species scores exist in breakdown
        self.assertIsNotNone(f0.score.species_scores.dorada_score)
        self.assertIsNotNone(f0.score.species_scores.lubina_score)
        self.assertIsNotNone(f0.score.tide_state)
        self.assertIsNotNone(f0.score.wind_aspect)

        # Test species chart
        fig_spec = create_species_comparison_chart(f0.score.species_scores)
        self.assertIsNotNone(fig_spec)

        # Test multi-species map rendering
        telemetry = get_buoy_telemetry_snapshot(self.buoys, self.now_utc)
        m = create_andalucia_fishing_map(
            spots_data=[(self.test_spot, f0)],
            selected_spot_id=self.test_spot.id,
            buoys_data=telemetry,
            score_mode="DORADA",
        )
        self.assertIsNotNone(m)


if __name__ == "__main__":
    unittest.main()
