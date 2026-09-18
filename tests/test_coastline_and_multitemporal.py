"""
Unit tests for coastal coastline boundary detection, NDWI water-land masking,
and multi-temporal Sentinel-2 persistence contrast algorithms along Costa de Huelva.
"""

import unittest
from pathlib import Path

from src.models.poza import DetectedPoza, SentinelPassMetadata, DetectionMethod
from src.analytics.coastline import (
    compute_ndwi,
    compute_mndwi,
    get_shoreline_lat_at_lon,
    get_shoreline_normal_azimuth,
    is_in_ocean,
    calculate_distance_to_shore_m,
    project_seaward_point,
    enforce_marine_bounds,
    get_huelva_shoreline_folium_coords,
    HUELVA_SHORELINE_VERTICES,
)
from src.analytics.poza_detection import (
    load_pozas_from_json,
    filter_pozas,
    calculate_deterministic_littoral_drift,
    contrast_multi_temporal_pozas,
)
from src.fetchers.sentinel_satellite import (
    get_huelva_sentinel_series,
    get_latest_huelva_sentinel_pass,
)


class TestCoastlineModule(unittest.TestCase):
    """Test suite for shoreline boundary and water-land spectral masking."""

    def test_shoreline_vertices_structure(self):
        """Verify shoreline vertices span the entire Huelva Atlantic coast."""
        self.assertGreaterEqual(len(HUELVA_SHORELINE_VERTICES), 20)
        # Verify monotonically increasing longitudes from West (Ayamonte) to East (Doñana)
        longitudes = [pt[0] for pt in HUELVA_SHORELINE_VERTICES]
        for i in range(len(longitudes) - 1):
            self.assertLess(longitudes[i], longitudes[i + 1])

        # Bounds: West >= -7.45, East <= -6.30
        self.assertLessEqual(HUELVA_SHORELINE_VERTICES[0][0], -7.40)
        self.assertGreaterEqual(HUELVA_SHORELINE_VERTICES[-1][0], -6.40)

    def test_water_land_classification(self):
        """Verify points in the ocean are True and points on land/dunes are False."""
        # Test Point 1: Ocean off Isla Canela (-7.4082, 37.1700) -> Shoreline is at 37.1735
        self.assertTrue(is_in_ocean(lat=37.1700, lon=-7.4082))
        # Inland point (town of Ayamonte / marshes: lat=37.1850)
        self.assertFalse(is_in_ocean(lat=37.1850, lon=-7.4082))

        # Test Point 2: Ocean off Islantilla (-7.2345, 37.1970) -> Shoreline is at 37.1988
        self.assertTrue(is_in_ocean(lat=37.1970, lon=-7.2345))
        # Inland point (Islantilla promenade / golf: lat=37.2050)
        self.assertFalse(is_in_ocean(lat=37.2050, lon=-7.2345))

        # Test Point 3: Ocean off Cuesta Maneli (-6.7482, 37.0640) -> Shoreline is at 37.0665
        self.assertTrue(is_in_ocean(lat=37.0640, lon=-6.7482))
        # Inland point (Asperillo cliff pine forest: lat=37.0750)
        self.assertFalse(is_in_ocean(lat=37.0750, lon=-6.7482))

        # Test Point 4: Ocean off Matalascañas (-6.5394, 36.9890) -> Shoreline is at 36.9908
        self.assertTrue(is_in_ocean(lat=36.9890, lon=-6.5394))
        # Inland point (Matalascañas urban center: lat=36.9960)
        self.assertFalse(is_in_ocean(lat=36.9960, lon=-6.5394))

    def test_distance_to_shore(self):
        """Verify distance calculation returns positive in sea, negative on land."""
        lon = -7.2345  # Islantilla
        shore_lat = get_shoreline_lat_at_lon(lon)

        # 80m into sea (south)
        ocean_lat = shore_lat - (80.0 / 111139.0)
        dist_ocean = calculate_distance_to_shore_m(ocean_lat, lon)
        self.assertAlmostEqual(dist_ocean, 80.0, delta=1.5)

        # 50m inland (north)
        land_lat = shore_lat + (50.0 / 111139.0)
        dist_land = calculate_distance_to_shore_m(land_lat, lon)
        self.assertAlmostEqual(dist_land, -50.0, delta=1.5)

    def test_ndwi_spectral_index(self):
        """Verify McFeeters NDWI computation for typical water vs dry sand spectra."""
        # Clean coastal water: high green (0.18), very low NIR (0.02)
        ndwi_water = compute_ndwi(green_refl=0.18, nir_refl=0.02)
        self.assertGreater(ndwi_water, 0.5)

        # Dry dune sand: moderate green (0.22), high NIR (0.35)
        ndwi_sand = compute_ndwi(green_refl=0.22, nir_refl=0.35)
        self.assertLess(ndwi_sand, 0.0)

        # Pine tree vegetation: high NIR (0.45), lower green (0.08)
        ndwi_veg = compute_ndwi(green_refl=0.08, nir_refl=0.45)
        self.assertLess(ndwi_veg, -0.5)

    def test_mndwi_spectral_index(self):
        """Verify Modified NDWI (MNDWI Xu) for wet intertidal sand."""
        mndwi_val = compute_mndwi(green_refl=0.15, swir_refl=0.03)
        self.assertGreater(mndwi_val, 0.4)

    def test_enforce_marine_bounds_snaps_land_to_sea(self):
        """Verify that any poza mistakenly situated inland is projected into the marine surf zone."""
        # Create a mock poza situated on land (Islantilla promenade: 37.2050 > shoreline 37.1988)
        inland_poza = DetectedPoza(
            id="test_inland_01",
            name="Poza de Prueba Tierra",
            beach_name="Islantilla",
            latitude=37.2050,  # Inland!
            longitude=-7.2345,
            detection_method="SDB_STUMPF",
            distance_from_shore_m=70,
            width_m=35,
            length_m=80,
            relative_depth_m=1.8,
            confidence_score=90.0,
            target_species=["Dorada"],
            optimal_tide_stage="Pleamar",
            satellite_pass_date="2026-09-17",
            coordinates_polygon=[(37.2052, -7.2348), (37.2048, -7.2342)],
        )

        # Prior to enforcement: is on land
        self.assertFalse(is_in_ocean(inland_poza.latitude, inland_poza.longitude))

        # Enforce bounds
        snapped = enforce_marine_bounds(inland_poza)

        # After enforcement: strictly in ocean!
        self.assertTrue(is_in_ocean(snapped.latitude, snapped.longitude))
        self.assertTrue(snapped.is_shoreline_validated)
        self.assertGreaterEqual(snapped.distance_from_shore_m, 20)
        self.assertLessEqual(snapped.distance_from_shore_m, 130)

        # All polygon points are also in ocean
        for pt_lat, pt_lon in snapped.coordinates_polygon:
            self.assertTrue(is_in_ocean(pt_lat, pt_lon))

    def test_all_catalog_pozas_are_strictly_in_water(self):
        """Verify 100% of curated pozas in data/pozas_huelva.json are in the ocean."""
        pozas = load_pozas_from_json()
        self.assertGreaterEqual(len(pozas), 16)

        for p in pozas:
            # 1. Center coordinate in ocean
            in_sea = is_in_ocean(p.latitude, p.longitude)
            dist = calculate_distance_to_shore_m(p.latitude, p.longitude)
            self.assertTrue(in_sea, f"Poza {p.name} ({p.id}) is on land! Lat={p.latitude}, Lon={p.longitude}")
            self.assertGreaterEqual(dist, 20.0, f"Poza {p.name} too close to shore: {dist}m")
            self.assertLessEqual(dist, 135.0, f"Poza {p.name} too far from shore: {dist}m")
            self.assertTrue(p.is_shoreline_validated)

            # 2. Polygon vertices in ocean
            if p.coordinates_polygon:
                for pt_lat, pt_lon in p.coordinates_polygon:
                    self.assertTrue(
                        is_in_ocean(pt_lat, pt_lon),
                        f"Polygon vertex ({pt_lat}, {pt_lon}) of poza {p.name} is on land!"
                    )

    def test_get_huelva_shoreline_folium_coords(self):
        """Verify Folium polyline coordinates list formatting."""
        coords = get_huelva_shoreline_folium_coords()
        self.assertIsInstance(coords, list)
        self.assertGreaterEqual(len(coords), 20)
        for lat, lon in coords:
            self.assertGreaterEqual(lat, 36.7)
            self.assertLessEqual(lat, 37.3)
            self.assertGreaterEqual(lon, -7.45)
            self.assertLessEqual(lon, -6.35)


class TestMultiTemporalPersistence(unittest.TestCase):
    """Test suite for multi-pass Sentinel-2 series and temporal persistence contrast."""

    def test_get_huelva_sentinel_series(self):
        """Verify retrieving a multi-temporal series of Sentinel-2 passes."""
        series = get_huelva_sentinel_series(passes_count=3)
        self.assertIsInstance(series, list)
        self.assertGreaterEqual(len(series), 1)
        self.assertLessEqual(len(series), 3)

        for p in series:
            self.assertIsInstance(p, SentinelPassMetadata)
            self.assertEqual(p.tile_id, "29SPB")
            self.assertLessEqual(p.cloud_cover_pct, 20.0)

    def test_contrast_multi_temporal_pozas(self):
        """Verify multi-temporal contrast algorithm with realistic mock series."""
        raw_pozas = load_pozas_from_json()
        series = get_huelva_sentinel_series(passes_count=3)

        contrasted = contrast_multi_temporal_pozas(raw_pozas, series)
        self.assertEqual(len(contrasted), len(raw_pozas))

        for p in contrasted:
            self.assertTrue(p.is_shoreline_validated)
            self.assertGreaterEqual(p.persistence_score, 50.0)
            self.assertLessEqual(p.persistence_score, 100.0)
            self.assertIn(p.temporal_passes_count, [1, 2, 3])
            self.assertGreaterEqual(len(p.observation_dates), 1)
            self.assertGreaterEqual(p.drift_offset_m, 0.0)
            self.assertLessEqual(p.drift_offset_m, 45.0)

    def test_filter_pozas_by_persistence(self):
        """Verify filtering pozas by minimum persistence threshold."""
        pozas = load_pozas_from_json()
        # Filter with min_persistence = 90.0%
        high_pers = filter_pozas(pozas, min_persistence=90.0)
        self.assertGreaterEqual(len(high_pers), 1)
        for p in high_pers:
            self.assertGreaterEqual(p.persistence_score, 90.0)

    def test_deterministic_littoral_drift(self):
        """Verify physics-based CERC / Longuet-Higgins deterministic littoral drift calculation."""
        pozas = load_pozas_from_json()
        poza_matalascanas = next(p for p in pozas if "matalascanas" in p.id)
        poza_islantilla = next(p for p in pozas if "islantilla" in p.id)

        # Shoreline normals along Huelva coast face South (160° - 215°)
        normal_mat = get_shoreline_normal_azimuth(poza_matalascanas.longitude)
        self.assertGreaterEqual(normal_mat, 160.0)
        self.assertLessEqual(normal_mat, 215.0)

        # 1. Standard Atlantic WSW swell (235°):
        # Breaker angle alpha_b = 235 - normal > 0, sin(2*alpha_b) > 0 -> Drift to Levante (East)
        drift_wsw = calculate_deterministic_littoral_drift(
            poza_matalascanas,
            wave_height_m=1.0,
            wave_direction_deg=235.0,
            days_elapsed=5.0,
        )
        self.assertIn("Levante", drift_wsw["direction"])
        self.assertGreater(drift_wsw["daily_migration_m"], 0.0)
        self.assertGreaterEqual(drift_wsw["drift_offset_m"], 5.0)
        self.assertLessEqual(drift_wsw["drift_offset_m"], 25.0)
        self.assertAlmostEqual(
            drift_wsw["drift_offset_m"],
            round(abs(drift_wsw["daily_migration_m"] * 5.0), 1),
            delta=0.2,
        )

        # 2. Reverse swell from Southeast (120°):
        # alpha_b = 120 - normal < 0 -> Drift to Poniente (West)
        drift_se = calculate_deterministic_littoral_drift(
            poza_islantilla,
            wave_height_m=1.0,
            wave_direction_deg=120.0,
            days_elapsed=5.0,
        )
        self.assertIn("Poniente", drift_se["direction"])
        self.assertLess(drift_se["daily_migration_m"], 0.0)

        # 3. Wave energy dependence: higher wave height -> higher migration rate
        drift_small = calculate_deterministic_littoral_drift(
            poza_matalascanas, wave_height_m=0.5, wave_direction_deg=235.0, days_elapsed=5.0
        )
        drift_large = calculate_deterministic_littoral_drift(
            poza_matalascanas, wave_height_m=1.5, wave_direction_deg=235.0, days_elapsed=5.0
        )
        self.assertGreater(drift_large["daily_migration_m"], drift_small["daily_migration_m"])

    def test_legacy_pickled_poza_resilience(self):
        """Verify that older pickled or incomplete poza instances do not raise AttributeError upon replace/contrast."""
        import pickle
        # Simulate legacy serialized poza without modern attributes
        legacy_dict = {
            "id": "legacy_poza_01",
            "name": "Poza Antigua",
            "beach_name": "Islantilla",
            "latitude": 37.1970,
            "longitude": -7.2345,
            "detection_method": "SDB_STUMPF",
            "distance_from_shore_m": 70,
            "width_m": 35,
            "length_m": 80,
            "relative_depth_m": 1.8,
            "confidence_score": 90.0,
            "target_species": ["Dorada"],
            "optimal_tide_stage": "Pleamar",
            "satellite_pass_date": "2026-09-17",
        }
        poza = DetectedPoza.from_dict(legacy_dict)
        # Manually delete newly added attributes to simulate unpickling an older schema
        for attr in ["persistence_score", "observation_dates", "drift_offset_m", "morphodynamic_stability", "is_shoreline_validated"]:
            if attr in poza.__dict__:
                del poza.__dict__[attr]

        # 1. Attribute access via __getattr__ defaults without AttributeError
        self.assertEqual(poza.persistence_score, 90.0)
        self.assertEqual(poza.temporal_passes_count, 1)
        self.assertEqual(poza.drift_offset_m, 0.0)
        self.assertTrue(poza.is_shoreline_validated)

        # 2. enforce_marine_bounds doesn't crash
        enforced = enforce_marine_bounds(poza)
        self.assertIsNotNone(enforced)
        self.assertTrue(enforced.is_shoreline_validated)

        # 3. contrast_multi_temporal_pozas doesn't crash
        series = get_huelva_sentinel_series(passes_count=1)
        contrasted = contrast_multi_temporal_pozas([poza], series)
        self.assertEqual(len(contrasted), 1)

        # 4. Pickle roundtrip
        pickled_data = pickle.dumps(poza)
        unpickled = pickle.loads(pickled_data)
        self.assertEqual(unpickled.id, "legacy_poza_01")
        self.assertEqual(unpickled.persistence_score, 90.0)
        self.assertTrue(unpickled.is_shoreline_validated)


if __name__ == "__main__":
    unittest.main()
