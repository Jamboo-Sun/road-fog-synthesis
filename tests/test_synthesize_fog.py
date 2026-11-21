import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

import numpy as np
from PIL import Image


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "synthesize_fog.py"
LEVELS = ("light", "medium", "heavy")


class FogSynthesisTest(unittest.TestCase):
    def setUp(self):
        parent = Path(tempfile.gettempdir()).resolve()
        self.root = parent / f"road-fog-test-{uuid4().hex}"
        self.root.mkdir()
        self.addCleanup(self.clean_up)
        for folder in ("images", "depth", "labels"):
            (self.root / folder / "scene").mkdir(parents=True)
        self.rgb = np.full((12, 18, 3), (36, 47, 58), dtype=np.uint8)
        self.rgb[7:10, 7:12] = [14, 18, 22]
        self.frame = self.root / "images/scene/road.png"
        Image.fromarray(self.rgb).save(self.frame)
        self.depth = np.broadcast_to(np.linspace(0, 1, 18), self.rgb.shape[:2])
        self.depth_file = self.root / "depth/scene/road.npy"
        self.label = b"0 0.5 0.7 0.3 0.2\n"
        (self.root / "labels/scene/road.txt").write_bytes(self.label)

    def clean_up(self):
        if self.root.resolve() == self.root and self.root.name.startswith("road-fog-test-"):
            shutil.rmtree(self.root)

    def run_cli(self, *args, success=True):
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(SCRIPT), *map(str, args)],
            capture_output=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return result

    def test_relative_depth_preserves_geometry_and_labels(self):
        np.save(self.depth_file, self.depth)
        output = self.root / "relative"
        self.run_cli("--images", self.root / "images", "--depth-dir", self.root / "depth",
                     "--depth-unit", "relative", "--labels", self.root / "labels",
                     "--levels", 0, 0.5, 1, "--output", output)
        previous = None
        for level in LEVELS:
            with Image.open(output / level / "images/scene/road.png") as image:
                rendered = np.array(image)
            self.assertEqual(rendered.shape, self.rgb.shape)
            np.testing.assert_array_equal(rendered[:, 0], self.rgb[:, 0])
            self.assertEqual((output / level / "labels/scene/road.txt").read_bytes(), self.label)
            if previous is None:
                np.testing.assert_array_equal(rendered, self.rgb)
            else:
                self.assertTrue(np.all(rendered[:, -1] > previous[:, -1]))
            previous = rendered

    def test_metric_and_preview_record_distinct_depth_units(self):
        np.save(self.depth_file, 100 * self.depth)
        output = self.root / "metric"
        self.run_cli("--images", self.frame, "--depth-dir", self.depth_file.parent,
                     "--depth-unit", "meters", "--output", output)
        info = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(info["strength_unit"], "m^-1")
        self.assertEqual(list(info["strengths"].values()), [0.005, 0.01, 0.02])
        preview = self.root / "preview"
        self.run_cli("--images", self.frame, "--row-proxy", "--output", preview)
        info = json.loads((preview / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(info["depth_mode"], "row_proxy_preview")
        self.assertEqual(info["output_images"], 3)
        with Image.open(preview / "heavy/images/road.png") as image:
            rendered = np.array(image)
        self.assertTrue(np.all(rendered[0] > self.rgb[0]))
        np.testing.assert_array_equal(rendered[-1], self.rgb[-1])

    def test_bad_depth_leaves_no_partial_output(self):
        np.save(self.depth_file, self.depth[:3])
        output = self.root / "failed"
        result = self.run_cli("--images", self.frame, "--depth-dir", self.depth_file.parent,
                              "--depth-unit", "relative", "--output", output, success=False)
        self.assertIn("expected depth shape", result.stderr)
        self.assertFalse(output.exists())
        self.assertFalse(list(self.root.glob(".fog-*")))
