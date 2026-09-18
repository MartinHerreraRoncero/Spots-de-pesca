"""
Unit tests for coastal poza detection, bathymetric Stumpf ratio calculations,
and surfcasting fishability algorithms along the Huelva coast.
"""

import unittest
from pathlib import Path
import tempfile
import json

from src.models.poza import DetectedPoza, SentinelPassMetadata, DetectionMethod
from src.analytics.poza_detection import (
    load_pozas_from_json,
    compute_stumpf_sdb_ratio,
    evaluate_poza_fishability,
    filter_pozas,
    sync_pozas_with_satellite_pass,
)


class TestPozaAnalytics(unittest.TestCase):
    """Test suite for poza detection, SDB bathymetry, and fishability analytics."""

    def setUp(self):
        """Load default Huelva pozas database for testing."""
        self.pozas = load_pozas_from_json()

    def test_load_pozas_from_json(self):
        """Verify loading the curated pozas_huelva.json database."""
        self.assertIsInstance(self.pozas, list)
        # Check minimum requirement: at least 12-16 structures
        self.assertGreaterEqual(len(self.pozas), 16)

        valid_methods = {"SDB_STUMPF", "BREAKER_GAP", "PNOA_ORTHO"}

        # Track key geographical zones
        found_zones = {
            "isla_canela": False,
            "isla_cristina": False,
            "redondela_islantilla": False,
            "cartaya_rompido": False,
            "portil": False,
            "punta_umbria": False,
            "mazagon": False,
            "matalascanas": False,
        }

        for poza in self.pozas:
            self.assertIsInstance(poza, DetectedPoza)
            self.assertTrue(poza.id.startswith("poza_"))
            self.assertTrue(len(poza.name) > 5)
            self.assertTrue(len(poza.beach_name) > 3)

            # Geographic bounds for Huelva coast (approx 36.9 to 37.3 lat, -7.5 to -6.4 lon)
            self.assertGreaterEqual(poza.latitude, 36.90)
            self.assertLessEqual(poza.latitude, 37.30)
            self.assertGreaterEqual(poza.longitude, -7.45)
            self.assertLessEqual(poza.longitude, -6.45)

            # Surfcasting casting distance (35 to 140 m)
            self.assertGreaterEqual(poza.distance_from_shore_m, 35)
            self.assertLessEqual(poza.distance_from_shore_m, 140)

            # Morphology dimensions
            self.assertGreaterEqual(poza.width_m, 20)
            self.assertLessEqual(poza.width_m, 60)
            self.assertGreaterEqual(poza.length_m, 50)
            self.assertLessEqual(poza.length_m, 150)

            # Relative depression depth (+0.8 to +2.8 m)
            self.assertGreaterEqual(poza.relative_depth_m, 0.8)
            self.assertLessEqual(poza.relative_depth_m, 2.8)

            # Confidence score (80.0 to 98.0)
            self.assertGreaterEqual(poza.confidence_score, 80.0)
            self.assertLessEqual(poza.confidence_score, 98.0)

            # Method validation
            self.assertIn(poza.detection_method, valid_methods)

            # Target species and tide stage
            self.assertGreaterEqual(len(poza.target_species), 3)
            self.assertTrue(len(poza.optimal_tide_stage) > 5)

            # Polygon outline check
            if poza.coordinates_polygon is not None:
                self.assertGreaterEqual(len(poza.coordinates_polygon), 3)
                for pt in poza.coordinates_polygon:
                    self.assertEqual(len(pt), 2)
                    self.assertIsInstance(pt[0], float)
                    self.assertIsInstance(pt[1], float)

            # Check coverage
            beach_lower = poza.beach_name.lower()
            name_lower = poza.name.lower()
            if "canela" in beach_lower or "canela" in name_lower or "guadiana" in name_lower:
                found_zones["isla_canela"] = True
            if "cristina" in beach_lower or "caimán" in name_lower or "gaviota" in name_lower:
                found_zones["isla_cristina"] = True
            if "redondela" in beach_lower or "islantilla" in beach_lower or "hoyo" in name_lower:
                found_zones["redondela_islantilla"] = True
            if "cartaya" in beach_lower or "rompido" in beach_lower or "flecha" in name_lower:
                found_zones["cartaya_rompido"] = True
            if "portil" in beach_lower or "culata" in name_lower:
                found_zones["portil"] = True
            if "punta umbría" in beach_lower or "canaleta" in name_lower:
                found_zones["punta_umbria"] = True
            if "mazagón" in beach_lower or "maneli" in name_lower or "asperillo" in name_lower:
                found_zones["mazagon"] = True
            if "matalascañas" in beach_lower or "higuera" in name_lower or "doñana" in name_lower:
                found_zones["matalascanas"] = True

        # Ensure all requested areas along Huelva coast are represented
        for zone_key, covered in found_zones.items():
            self.assertTrue(covered, f"Expected coverage for zone: {zone_key}")

    def test_load_pozas_nonexistent_file(self):
        """Verify graceful handling when JSON file is missing or invalid."""
        missing_path = Path("data/non_existent_pozas_catalog_123.json")
        result = load_pozas_from_json(missing_path)
        self.assertEqual(result, [])

    def test_compute_stumpf_sdb_ratio_accuracy(self):
        """Verify Stumpf Satellite Derived Bathymetry calculation."""
        # Standard BOA reflectances: Blue=0.08, Green=0.05
        # With n=1000: ln(80)/ln(50) = 4.3820268 / 3.912023 = 1.12014
        # m1=12.5, m0=2.0 -> 12.5 * 1.12014 - 2.0 = 12.00 m
        depth = compute_stumpf_sdb_ratio(0.08, 0.05, m1=12.5, m0=2.0)
        self.assertAlmostEqual(depth, 12.00, places=1)

        # Equal reflectances -> ratio = 1.0 -> depth = 12.5 * 1.0 - 2.0 = 10.5 m
        depth_equal = compute_stumpf_sdb_ratio(0.05, 0.05, m1=12.5, m0=2.0)
        self.assertAlmostEqual(depth_equal, 10.50, places=1)

        # Custom m1 and m0 parameters
        depth_custom = compute_stumpf_sdb_ratio(0.08, 0.05, m1=10.0, m0=1.0)
        expected_custom = round(10.0 * 1.12014 - 1.0, 2)
        self.assertAlmostEqual(depth_custom, expected_custom, places=1)

    def test_compute_stumpf_sdb_ratio_scaled_dn(self):
        """Verify calculation is invariant to scaled digital numbers (DN) vs fractional reflectance."""
        # 0.08 and 0.05 scaled to DN values 80 and 50
        depth_dn = compute_stumpf_sdb_ratio(80.0, 50.0, m1=12.5, m0=2.0)
        depth_frac = compute_stumpf_sdb_ratio(0.08, 0.05, m1=12.5, m0=2.0)
        self.assertEqual(depth_dn, depth_frac)

    def test_compute_stumpf_sdb_ratio_edge_cases(self):
        """Verify robustness against non-positive and very small reflectances."""
        # Zero and negative reflectances should be protected
        depth_zero = compute_stumpf_sdb_ratio(0.0, 0.05)
        self.assertIsInstance(depth_zero, float)
        self.assertGreaterEqual(depth_zero, 0.0)

        depth_neg = compute_stumpf_sdb_ratio(-0.02, -0.05)
        self.assertIsInstance(depth_neg, float)
        self.assertGreaterEqual(depth_neg, 0.0)

    def test_evaluate_poza_fishability_optimal(self):
        """Verify fishability evaluation under optimal surfcasting conditions."""
        sample_poza = self.pozas[0]  # Isla Canela Guadiana
        result = evaluate_poza_fishability(
            poza=sample_poza,
            tide_state_name=sample_poza.optimal_tide_stage,
            tide_coeff=82.0,
            wave_height_m=0.9,
            current_speed_knots=1.1,
        )

        self.assertIn("fishability_score", result)
        self.assertIn("activity_summary", result)
        self.assertIn("recommended_lead_g", result)
        self.assertIn("recommended_baits", result)
        self.assertIn("is_optimal_now", result)

        self.assertGreaterEqual(result["fishability_score"], 70.0)
        self.assertTrue(result["is_optimal_now"])
        self.assertIn(result["recommended_lead_g"], [110, 120, 130, 140, 150])
        self.assertGreater(len(result["recommended_baits"]), 0)
        self.assertIn("Corvina", sample_poza.target_species)
        # High score summary
        self.assertIn("Condición óptima", result["activity_summary"])

    def test_evaluate_poza_fishability_adverse(self):
        """Verify fishability drops during rough sea states and violent currents."""
        sample_poza = self.pozas[0]
        result = evaluate_poza_fishability(
            poza=sample_poza,
            tide_state_name="Pleamar",  # Opposing tide
            tide_coeff=35.0,            # Dead neap
            wave_height_m=2.8,          # Heavy surf
            current_speed_knots=3.8,    # Violent rip current
        )

        self.assertLess(result["fishability_score"], 50.0)
        self.assertFalse(result["is_optimal_now"])
        # Should recommend maximum holding sinker for severe conditions
        self.assertEqual(result["recommended_lead_g"], 150)
        self.assertTrue("Condición difícil" in result["activity_summary"] or "Corriente severa" in result["activity_summary"] or "arrastre" in result["activity_summary"])

    def test_evaluate_poza_lead_graduation(self):
        """Verify sinker weight dynamically scales with current and wave height."""
        sample_poza = self.pozas[1]

        # Calm conditions
        calm_res = evaluate_poza_fishability(sample_poza, "Media marea subiendo", 60.0, 0.4, 0.3)
        self.assertIn(calm_res["recommended_lead_g"], [110, 120])

        # Moderate conditions
        mod_res = evaluate_poza_fishability(sample_poza, "Media marea subiendo", 75.0, 1.1, 1.3)
        self.assertEqual(mod_res["recommended_lead_g"], 130)

        # Strong conditions
        strong_res = evaluate_poza_fishability(sample_poza, "Media marea subiendo", 85.0, 1.6, 2.0)
        self.assertIn(strong_res["recommended_lead_g"], [140, 150])

    def test_filter_pozas(self):
        """Verify filtering pozas by beach name, method, and casting distance."""
        # 1. Filter by beach
        canela_pozas = filter_pozas(self.pozas, beach="Canela")
        self.assertGreaterEqual(len(canela_pozas), 1)
        for p in canela_pozas:
            self.assertTrue("canela" in p.beach_name.lower() or "canela" in p.name.lower())

        # 2. Filter by detection method
        stumpf_pozas = filter_pozas(self.pozas, method="SDB_STUMPF")
        self.assertGreater(len(stumpf_pozas), 0)
        for p in stumpf_pozas:
            self.assertEqual(p.detection_method, "SDB_STUMPF")

        breaker_pozas = filter_pozas(self.pozas, method="BREAKER_GAP")
        self.assertGreater(len(breaker_pozas), 0)
        for p in breaker_pozas:
            self.assertEqual(p.detection_method, "BREAKER_GAP")

        ortho_pozas = filter_pozas(self.pozas, method="PNOA_ORTHO")
        self.assertGreater(len(ortho_pozas), 0)
        for p in ortho_pozas:
            self.assertEqual(p.detection_method, "PNOA_ORTHO")

        # 3. Filter by maximum casting distance
        short_reach = filter_pozas(self.pozas, max_distance=60)
        self.assertGreater(len(short_reach), 0)
        for p in short_reach:
            self.assertLessEqual(p.distance_from_shore_m, 60)

        # 4. Combined filter
        combined = filter_pozas(self.pozas, beach="Cristina", method="BREAKER_GAP", max_distance=90)
        for p in combined:
            self.assertEqual(p.detection_method, "BREAKER_GAP")
            self.assertIn("cristina", p.beach_name.lower())
            self.assertLessEqual(p.distance_from_shore_m, 90)

    def test_sync_pozas_with_satellite_pass(self):
        """Verify updating pozas with Sentinel-2 pass metadata."""
        meta = SentinelPassMetadata(
            scene_id="S2A_MSIL2A_20260918T112131_R037_T29SPB",
            datetime="2026-09-18T11:21:31Z",
            cloud_cover_pct=2.1,
            sun_elevation=54.2,
            tile_id="29SPB",
            visual_url="https://example.com/visual.tif",
            b02_blue_url="https://example.com/b02.tif",
            b03_green_url="https://example.com/b03.tif",
            b04_red_url="https://example.com/b04.tif",
            b08_nir_url="https://example.com/b08.tif",
            cached_at="2026-09-18T12:00:00Z",
        )

        synced = sync_pozas_with_satellite_pass(self.pozas, meta)
        self.assertEqual(len(synced), len(self.pozas))

        for p in synced:
            self.assertEqual(p.satellite_pass_date, "2026-09-18")

        # Under clear skies (<5% cloud) and high sun elevation (>45 deg),
        # confidence scores for SDB and Breaker Gap should be maintained or enhanced
        stumpf_original = next(p for p in self.pozas if p.detection_method == "SDB_STUMPF")
        stumpf_synced = next(p for p in synced if p.id == stumpf_original.id)
        self.assertGreaterEqual(stumpf_synced.confidence_score, stumpf_original.confidence_score)


if __name__ == "__main__":
    unittest.main()
