from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from cell_skeleton_detector.core import AnalysisEngine
from cell_skeleton_detector.exporters import export_results, render_overlay
from cell_skeleton_detector.models import AnalysisParams


def synthetic_astrocytes(size: int = 128) -> np.ndarray:
    image = np.zeros((size, size, 3), dtype=np.uint16)
    yy, xx = np.ogrid[:size, :size]
    red = image[..., 0]
    for cy, cx in ((42, 40), (85, 88)):
        soma = (yy - cy) ** 2 + (xx - cx) ** 2 <= 9**2
        red[soma] = 55000
        red[max(0, cy - 2) : cy + 3, max(0, cx - 28) : min(size, cx + 29)] = 42000
        red[max(0, cy - 28) : min(size, cy + 29), max(0, cx - 2) : cx + 3] = 42000
        for offset in range(-22, 23):
            y = cy + offset
            x = cx + offset
            if 0 <= y < size and 0 <= x < size:
                red[max(0, y - 1) : y + 2, max(0, x - 1) : x + 2] = 36000
    return image


class AnalysisEngineTests(unittest.TestCase):
    def test_manual_threshold_is_not_multiplied(self) -> None:
        params = AnalysisParams(
            threshold_method="manual",
            manual_threshold=0.5,
            threshold_multiplier=0.1,
            min_object_size=0,
            hole_area=0,
            closing_radius=0,
            bootstrap_n=0,
        )
        engine = AnalysisEngine(params)
        signal = np.array([[0.2, 0.4], [0.6, 0.8]], dtype=np.float32)
        binary, threshold = engine.make_binary(signal)
        np.testing.assert_array_equal(
            binary, np.array([[False, False], [True, True]])
        )
        self.assertEqual(threshold, 0.5)

    def test_junction_cluster_is_counted_as_one_node(self) -> None:
        params = AnalysisParams(bootstrap_n=0)
        engine = AnalysisEngine(params)
        skeleton = np.zeros((25, 25), dtype=bool)
        skeleton[12, 3:22] = True
        skeleton[3:22, 12] = True
        binary = skeleton.copy()
        signal = skeleton.astype(np.float32)
        metrics, _ = engine.skeleton_graph_analysis(
            skeleton, binary, signal, include_branches=True
        )
        self.assertEqual(metrics["junctions"], 1)
        self.assertEqual(metrics["endpoints"], 4)
        self.assertGreaterEqual(metrics["branches"], 4)

    def test_full_pipeline_and_export(self) -> None:
        params = AnalysisParams(
            threshold_method="manual",
            manual_threshold=0.15,
            min_object_size=8,
            hole_area=8,
            closing_radius=1,
            pixel_size_um=0.5,
            cluster_mode="two_largest",
            sholl_radius_step_um=5,
            sholl_max_radius_um=40,
            bootstrap_n=2,
        )
        result = AnalysisEngine(params).analyze(synthetic_astrocytes())
        self.assertEqual(result.binary.shape, (128, 128))
        self.assertEqual(result.skeleton.shape, (128, 128))
        self.assertGreater(result.metrics["mask_area_px"], 0)
        self.assertGreater(result.metrics["skeleton_length_px"], 0)
        self.assertTrue(result.sholl)
        self.assertGreaterEqual(len(result.uncertainty), 10)
        self.assertEqual(render_overlay(result).size, (128, 128))

        with tempfile.TemporaryDirectory() as directory:
            folder, archive = export_results(result, directory, "synthetic")
            self.assertTrue((folder / "report.html").is_file())
            self.assertTrue((folder / "metrics.csv").is_file())
            self.assertTrue((folder / "neurolucida_overlay.png").is_file())
            self.assertTrue(archive.is_file())


if __name__ == "__main__":
    unittest.main()
