"""
Unit tests for Sentinel-2 satellite fetcher and DetectedPoza data models.
"""

import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import json
from unittest.mock import patch, MagicMock

from src.models.poza import (
    DetectedPoza,
    SentinelPassMetadata,
    DetectionMethod,
)
from src.fetchers.sentinel_satellite import (
    get_latest_huelva_sentinel_pass,
    is_cache_fresh,
    get_huelva_coastal_bounds,
    _generate_mock_sentinel_metadata,
)


class TestSentinelPipeline(unittest.TestCase):
    """Test suite for Sentinel pipeline models and fetchers."""

    def test_detected_poza_model(self):
        """Verify DetectedPoza dataclass instantiation and dictionary conversion."""
        poza = DetectedPoza(
            id="poza_islantilla_01",
            name="Poza del Rompiente de Poniente - Islantilla",
            beach_name="Islantilla / La Redondela",
            latitude=37.1985,
            longitude=-7.2280,
            detection_method="SDB_STUMPF",
            distance_from_shore_m=75,
            width_m=35,
            length_m=90,
            relative_depth_m=1.8,
            confidence_score=92.5,
            target_species=["Dorada", "Herrera", "Lubina", "Lenguado"],
            optimal_tide_stage="Media marea subiendo",
            satellite_pass_date="2026-09-17",
            coordinates_polygon=[(37.1980, -7.2285), (37.1990, -7.2275)],
        )

        self.assertEqual(poza.id, "poza_islantilla_01")
        self.assertEqual(poza.detection_method, "SDB_STUMPF")
        self.assertEqual(poza.relative_depth_m, 1.8)
        self.assertEqual(len(poza.target_species), 4)

        # Dictionary round-trip
        data = poza.to_dict()
        self.assertIn("confidence_score", data)
        reconstructed = DetectedPoza.from_dict(data)
        self.assertEqual(reconstructed.id, poza.id)
        self.assertEqual(reconstructed.latitude, poza.latitude)
        self.assertEqual(reconstructed.coordinates_polygon, poza.coordinates_polygon)

    def test_sentinel_pass_metadata_model(self):
        """Verify SentinelPassMetadata dataclass and serialization."""
        meta = SentinelPassMetadata(
            scene_id="S2A_MSIL2A_TEST",
            datetime="2026-09-17T11:21:31Z",
            cloud_cover_pct=2.5,
            sun_elevation=53.0,
            tile_id="29SPB",
            visual_url="https://example.com/visual.tif",
            b02_blue_url="https://example.com/b02.tif",
            b03_green_url="https://example.com/b03.tif",
            b04_red_url="https://example.com/b04.tif",
            b08_nir_url="https://example.com/b08.tif",
            cached_at="2026-09-18T10:00:00Z",
        )

        d = meta.to_dict()
        self.assertEqual(d["scene_id"], "S2A_MSIL2A_TEST")
        loaded = SentinelPassMetadata.from_dict(d)
        self.assertEqual(loaded.tile_id, "29SPB")
        self.assertEqual(loaded.cloud_cover_pct, 2.5)

    def test_huelva_coastal_bounds(self):
        """Verify coastal bounds for Huelva."""
        bounds = get_huelva_coastal_bounds()
        self.assertEqual(bounds["min_lon"], -7.45)
        self.assertEqual(bounds["min_lat"], 36.95)
        self.assertEqual(bounds["max_lon"], -6.50)
        self.assertEqual(bounds["max_lat"], 37.30)
        self.assertEqual(bounds["west"], -7.45)
        self.assertEqual(bounds["south"], 36.95)
        self.assertEqual(bounds["east"], -6.50)
        self.assertEqual(bounds["north"], 37.30)

    def test_cache_freshness(self):
        """Verify cache freshness checks under fresh, expired, and non-existent files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_cache = Path(tmpdir) / "test_cache.json"

            # Non-existent
            self.assertFalse(is_cache_fresh(max_age_days=5, cache_path=temp_cache))

            # Fresh cache (< 5 days old)
            fresh_time = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            with open(temp_cache, "w", encoding="utf-8") as f:
                json.dump({"cached_at": fresh_time}, f)
            self.assertTrue(is_cache_fresh(max_age_days=5, cache_path=temp_cache))

            # Stale cache (> 5 days old)
            stale_time = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            with open(temp_cache, "w", encoding="utf-8") as f:
                json.dump({"cached_at": stale_time}, f)
            self.assertFalse(is_cache_fresh(max_age_days=5, cache_path=temp_cache))

    def test_offline_fallback_resilience(self):
        """Verify that when network is down or API errors, fallback mock metadata is returned and cached."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_cache = Path(tmpdir) / "offline_cache.json"

            with patch("src.fetchers.sentinel_satellite.requests.post") as mock_post:
                mock_post.side_effect = Exception("Connection timed out or network offline")

                meta = get_latest_huelva_sentinel_pass(force_refresh=True, cache_path=temp_cache)
                self.assertIsNotNone(meta)
                self.assertIn("29SPB", meta.tile_id)
                self.assertTrue(temp_cache.is_file())
                self.assertLess(meta.cloud_cover_pct, 15.0)

    def test_live_or_cached_pass_retrieval(self):
        """Verify normal retrieval flow returns valid SentinelPassMetadata."""
        meta = get_latest_huelva_sentinel_pass(force_refresh=False)
        self.assertIsInstance(meta, SentinelPassMetadata)
        self.assertEqual(meta.tile_id, "29SPB")
        self.assertGreater(meta.sun_elevation, 0.0)


if __name__ == "__main__":
    unittest.main()
