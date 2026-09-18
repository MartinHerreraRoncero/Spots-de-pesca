"""
Unit and integration tests for Andalusian Marine Fishing App with advanced scientific modules:
tides, wind aspect, buoy bias correction, multi-species scoring,
bathymetry gradients, satellite water clarity, and river runoff plumes.
"""

import unittest
from datetime import datetime, timezone, timedelta
import pandas as pd

from src.models.spot import (
    Spot,
    MarineBuoy,
    ScoringWeights,
    MarineConditions,
    WeatherConditions,
    BathymetryProfile,
    WaterClarityConditions,
    RiverRunoffConditions,
)
from src.fetchers.open_meteo import (
    load_spots_from_json,
    load_marine_buoys_from_json,
    create_custom_spot_from_coords,
    get_spot_hourly_forecast,
    get_buoy_telemetry_snapshot,
)
from src.analytics.solunar import compute_daily_solunar, evaluate_solunar_for_hour
from src.analytics.tides import calculate_tide_coefficient, compute_spot_tide_state
from src.analytics.bathymetry import calculate_bathymetry_profile
from src.analytics.satellite_ocean import compute_water_clarity_and_fronts
from src.analytics.river_runoff import load_rivers_catalog, compute_river_runoff_impact
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
    render_poza_popup_html,
)
from src.analytics.poza_detection import load_pozas_from_json, evaluate_poza_fishability
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
        self.rivers = load_rivers_catalog()
        self.test_spot = self.spots[0]  # Isla Canela / Ayamonte
        self.now_utc = datetime(2026, 8, 20, 18, 0, 0, tzinfo=timezone.utc)

    def test_tides_and_coefficient_calculations(self):
        """Tests calculation of tide coefficients (20-120) and semidiurnal tide states."""
        coef_spring = calculate_tide_coefficient(0.5, 5.0)
        self.assertGreaterEqual(coef_spring, 85)

        coef_neap = calculate_tide_coefficient(7.5, 50.0)
        self.assertLessEqual(coef_neap, 50)

        solunar = compute_daily_solunar(self.test_spot, self.now_utc)
        tide_state = compute_spot_tide_state(self.test_spot, self.now_utc, solunar)
        self.assertGreaterEqual(tide_state.coefficient, 20)
        self.assertLessEqual(tide_state.coefficient, 120)
        self.assertIsNotNone(tide_state.state_name)
        self.assertIsNotNone(tide_state.next_high_tide)
        self.assertIsNotNone(tide_state.next_low_tide)

    def test_wind_relative_aspect(self):
        """Tests wind direction relative to coastline bearing (Onshore/Offshore/Upwelling)."""
        aspect_onshore = calculate_wind_relative_aspect(195.0, 195.0, 15.0, "Atlántico")
        self.assertTrue(aspect_onshore.is_onshore)
        self.assertFalse(aspect_onshore.is_offshore)

        aspect_offshore = calculate_wind_relative_aspect(15.0, 195.0, 15.0, "Atlántico")
        self.assertTrue(aspect_offshore.is_offshore)
        self.assertFalse(aspect_offshore.is_onshore)

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

    def test_bathymetry_gradients_and_rugosity(self):
        """Tests bathymetric slope and rugosity calculation across different coastal morphotypes."""
        # Find a cliff/rocky spot in Granada / Costa Tropical
        granada_spots = [s for s in self.spots if "Granada" in s.subzone or "Tropical" in s.subzone]
        granada_cliff = granada_spots[0] if granada_spots else self.test_spot
        bathy_cliff = calculate_bathymetry_profile(granada_cliff)
        
        # Steep drop-off checks
        self.assertGreaterEqual(bathy_cliff.depth_gradient_pct, 8.0)
        self.assertGreater(bathy_cliff.topographic_hotspot_score, 0.0)
        self.assertLessEqual(bathy_cliff.topographic_hotspot_score, 100.0)

        # Shallow beach in Huelva
        bathy_beach = calculate_bathymetry_profile(self.test_spot)
        self.assertLessEqual(bathy_beach.depth_gradient_pct, 5.0)
        self.assertLessEqual(bathy_beach.rugosity_index, 0.50)

    def test_satellite_water_clarity_and_thermal_fronts(self):
        """Tests bio-optical turbidity, Secchi depth, and thermal front detection."""
        # Stormy stirring wave conditions
        marine_stormy = MarineConditions(
            timestamp=self.now_utc, wave_height=2.2, wave_period=9.0, wave_direction=220, sea_surface_temperature=19.5
        )
        weather_rainy = WeatherConditions(
            timestamp=self.now_utc, surface_pressure=1008.0, wind_speed_10m=25.0, wind_direction_10m=200.0,
            cloud_cover=90, precipitation=4.5, temperature_2m=18.0
        )
        clarity_turbid = compute_water_clarity_and_fronts(self.test_spot, marine_stormy, weather_rainy)
        self.assertGreater(clarity_turbid.turbidity_ntu, 10.0)
        self.assertLessEqual(clarity_turbid.secchi_depth_m, 2.5)
        self.assertIn("Tomada", clarity_turbid.clarity_class)

        # Calm crystal clear conditions in deep water
        spot_deep = Spot(
            id="deep_test", name="Deep Spot", province="Málaga", zone="Mediterráneo", subzone="Costa del Sol",
            latitude=36.4, longitude=-4.6, description="Deep spot", spot_type="Roquedo / Acantilado",
            bottom_type="Roca laminar", depth_m=25.0
        )
        marine_calm = MarineConditions(
            timestamp=self.now_utc, wave_height=0.2, wave_period=5.0, wave_direction=180, sea_surface_temperature=21.0
        )
        weather_calm = WeatherConditions(
            timestamp=self.now_utc, surface_pressure=1018.0, wind_speed_10m=5.0, wind_direction_10m=180.0,
            cloud_cover=0, precipitation=0.0, temperature_2m=24.0
        )
        clarity_clean = compute_water_clarity_and_fronts(spot_deep, marine_calm, weather_calm)
        self.assertLess(clarity_clean.turbidity_ntu, 3.0)
        self.assertGreater(clarity_clean.secchi_depth_m, 5.0)

    def test_river_runoff_plume_and_salinity(self):
        """Tests estuarine runoff and plume detection for spots near major rivers."""
        # Spot near Guadalquivir (Sanlúcar / Doñana)
        sanlucar_spot = Spot(
            id="sanlucar_test", name="Bajo de Guía", province="Cádiz", zone="Atlántico",
            subzone="Bahía y Costa de Cádiz", latitude=36.7900, longitude=-6.3600,
            description="Desembocadura del Guadalquivir", spot_type="Desembocadura",
            bottom_type="Fango / Mixto", depth_m=5.0
        )
        weather_rain = WeatherConditions(
            timestamp=self.now_utc, surface_pressure=1012.0, wind_speed_10m=12.0, wind_direction_10m=220.0,
            cloud_cover=50, precipitation=1.5, temperature_2m=20.0
        )
        runoff_sanlucar = compute_river_runoff_impact(sanlucar_spot, weather_rain, precipitation_72h_mm=25.0)
        self.assertTrue(runoff_sanlucar.plume_active)
        self.assertGreater(runoff_sanlucar.salinity_drop_psu, 3.0)
        self.assertIn("Guadalquivir", runoff_sanlucar.nearest_river_name)

        # Species impact in river plume: Lubina and Corvina thrive, Calamar heavily penalized
        solunar = compute_daily_solunar(sanlucar_spot, self.now_utc)
        tide = compute_spot_tide_state(sanlucar_spot, self.now_utc, solunar)
        wind_asp = calculate_wind_relative_aspect(220.0, 230.0, 12.0, "Atlántico")
        marine_std = MarineConditions(
            timestamp=self.now_utc, wave_height=0.8, wave_period=6.5, wave_direction=220,
            sea_surface_temperature=20.0, current_velocity_knots=1.5, current_direction=240.0
        )
        spec = calculate_species_scores(
            sanlucar_spot, weather_rain, marine_std, solunar, 70.0, tide, wind_asp, 80.0, -0.5,
            river_runoff=runoff_sanlucar
        )
        self.assertGreater(spec.lubina_score, spec.calamar_score + 25.0)
        self.assertGreater(spec.corvina_score, spec.calamar_score + 25.0)

    def test_ocean_currents_physics_and_impact(self):
        """Tests physical ocean currents velocity in knots and biological scoring impact."""
        forecasts = get_spot_hourly_forecast(self.test_spot, forecast_days=1)
        self.assertGreater(len(forecasts), 0)
        f0 = forecasts[0]
        
        self.assertGreaterEqual(f0.marine.current_velocity_knots, 0.0)
        self.assertGreaterEqual(f0.marine.current_direction, 0.0)
        self.assertLessEqual(f0.marine.current_direction, 360.0)
        self.assertIsNotNone(f0.marine.current_intensity_level)

    def test_full_pipeline_multi_species_map_and_charts(self):
        """Tests full pipeline forecast retrieval with bathymetry, clarity, runoff, and map rendering."""
        forecasts = get_spot_hourly_forecast(self.test_spot, forecast_days=2)
        self.assertGreaterEqual(len(forecasts), 40)
        f0 = forecasts[0]

        # Verify species scores and new scientific fields exist in breakdown
        self.assertIsNotNone(f0.score.species_scores.dorada_score)
        self.assertIsNotNone(f0.score.species_scores.lubina_score)
        self.assertIsNotNone(f0.score.tide_state)
        self.assertIsNotNone(f0.score.wind_aspect)
        self.assertIsNotNone(f0.score.bathymetry)
        self.assertIsNotNone(f0.score.water_clarity)
        self.assertIsNotNone(f0.score.river_runoff)

        # Test species chart
        fig_spec = create_species_comparison_chart(f0.score.species_scores)
        self.assertIsNotNone(fig_spec)

        # Test map rendering with rivers and buoys
        telemetry = get_buoy_telemetry_snapshot(self.buoys, self.now_utc)
        m = create_andalucia_fishing_map(
            spots_data=[(self.test_spot, f0)],
            selected_spot_id=self.test_spot.id,
            buoys_data=telemetry,
            rivers_data=self.rivers,
            score_mode="DORADA",
        )
        self.assertIsNotNone(m)

    def test_map_rendering_with_satellite_pozas(self):
        """Tests map generation with PNOA WMS layer, Esri World Imagery, and satellite poza layers."""
        pozas = load_pozas_from_json()
        self.assertGreater(len(pozas), 0)

        f0 = get_spot_hourly_forecast(self.test_spot, forecast_days=1)[0]
        telemetry = get_buoy_telemetry_snapshot(self.buoys, self.now_utc)

        m = create_andalucia_fishing_map(
            spots_data=[(self.test_spot, f0)],
            selected_spot_id=self.test_spot.id,
            subzone_filter="Costa de Huelva",
            buoys_data=telemetry,
            rivers_data=self.rivers,
            score_mode="DORADA",
            pozas_data=pozas,
            show_pozas=True,
            current_tide_name="Bajamar",
            current_tide_coeff=82.0,
            current_wave_h=0.7,
            current_knots=1.1,
        )
        self.assertIsNotNone(m)
        rendered_html = m.get_root().render()
        self.assertIn("PNOA", rendered_html)
        self.assertIn("Esri World Imagery", rendered_html)
        self.assertIn("Pozas y Canales Detectados", rendered_html)

    def test_render_poza_popup_html(self):
        """Tests rendering of rich HTML popup card for coastal poza markers."""
        pozas = load_pozas_from_json()
        poza = pozas[0]
        eval_res = evaluate_poza_fishability(
            poza=poza,
            tide_state_name=poza.optimal_tide_stage,
            tide_coeff=80.0,
            wave_height_m=0.8,
            current_speed_knots=1.0,
        )
        html = render_poza_popup_html(poza, eval_res)
        self.assertIn(poza.name, html)
        self.assertIn(poza.beach_name, html)
        self.assertIn(str(poza.distance_from_shore_m), html)
        self.assertIn(str(poza.relative_depth_m), html)
        self.assertIn(str(poza.width_m), html)
        self.assertIn(str(poza.length_m), html)
        self.assertIn(poza.satellite_pass_date, html)
        self.assertIn(f"{eval_res['fishability_score']:.0f}", html)
        self.assertIn(str(eval_res["recommended_lead_g"]), html)
        for sp in poza.target_species[:2]:
            self.assertIn(sp, html)

    def test_app_py_syntax(self):
        """Verifies app.py compiles cleanly without SyntaxErrors."""
        import py_compile
        py_compile.compile("app.py", doraise=True)


if __name__ == "__main__":
    unittest.main()
