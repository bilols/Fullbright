"""Tests for fullbright.seamless (no Godot needed)."""
import numpy as np
from PIL import Image

from fullbright import seamless, tools


def _gradient(n=64):
    # A ramp left to right: the worst possible seam (black meets white).
    x = np.linspace(0, 1, n)
    return np.dstack([np.tile(x, (n, 1))] * 3)


def test_crossfade_removes_a_hard_seam():
    a = _gradient()
    assert seamless.seam_ratio(a) > 10
    assert seamless.seam_ratio(seamless.crossfade(a)) < 2


def test_crossfade_keeps_the_center():
    a = np.random.default_rng(0).random((64, 64, 3))
    out = seamless.crossfade(a, band=0.15)
    assert np.allclose(out[24:40, 24:40], a[24:40, 24:40])


def test_make_seamless_default_output_path(tmp_path):
    src = tmp_path / "waterblu1.gen.png"
    Image.fromarray((_gradient() * 255).astype(np.uint8)).save(src)
    r = seamless.make_seamless(str(src))
    assert r["ok"] and r["path"] == str(tmp_path / "tiled" / "waterblu1.png")
    assert r["seam_before"] > 10 and r["seam_after"] < 2


def test_make_seamless_keeps_alpha(tmp_path):
    src = tmp_path / "grate.png"
    rgba = np.zeros((32, 32, 4), np.uint8)
    rgba[..., 3] = 255
    rgba[:16, :16, 3] = 0
    Image.fromarray(rgba, "RGBA").save(src)
    r = seamless.make_seamless(str(src))
    assert Image.open(r["path"]).mode == "RGBA"


def test_tool_errors_are_data(tmp_path):
    assert tools.make_seamless(str(tmp_path / "missing.png"))["ok"] is False
    assert "band" in tools.make_seamless(str(tmp_path / "x.png"), band=0.9)["error"]
