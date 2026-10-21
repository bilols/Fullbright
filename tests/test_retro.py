"""Unit tests for fullbright.retro (no Godot needed)."""
import json

import numpy as np
from PIL import Image

from fullbright import retro


def _write(path, arr, mode):
    Image.fromarray(arr.astype(np.uint8), mode).save(path)


def _material(tmp_path, size=64, emission=None):
    alb = np.zeros((size, size, 4), np.uint8)
    alb[..., 0], alb[..., 1], alb[..., 2], alb[..., 3] = 200, 120, 60, 255  # orange
    alb[: size // 2, : size // 2, 3] = 0  # transparent corner
    _write(tmp_path / "m_albedo.png", alb, "RGBA")
    orm = np.zeros((size, size, 3), np.uint8)
    orm[..., 0], orm[..., 1], orm[..., 2] = 255, 128, 0
    _write(tmp_path / "m_orm.png", orm, "RGB")
    nrm = np.zeros((size, size, 3), np.uint8)
    nrm[..., 0], nrm[..., 1], nrm[..., 2] = 128, 128, 255
    _write(tmp_path / "m_normal.png", nrm, "RGB")
    if emission is not None:
        _write(tmp_path / "m_emission.png", emission, "RGB")


def _palette():
    return json.loads((retro.PALETTE_DIR / "quake.json").read_text())


def test_quake_palette_shape():
    pal = _palette()
    assert len(pal["colors"]) == 244
    assert pal["colors"][pal["exclude"][0]] == "9f5b53"
    assert len(pal["fullbright"]) == 30


def test_albedo_is_palette_locked_and_avoids_fullbrights(tmp_path):
    _material(tmp_path)
    r = retro.process(tmp_path, "m", size=16, targets=("godot",))
    assert r["ok"] and r["fullbright_pixels"] == 0
    pal = _palette()
    normal = {pal["colors"][i] for i in range(len(pal["colors"]))
              if i not in pal["fullbright"] and i not in pal["exclude"]}
    alb = np.asarray(Image.open(tmp_path / "retro/m/godot/m_albedo.png"))
    used = {"%02x%02x%02x" % tuple(p) for p in alb[..., :3].reshape(-1, 3)}
    assert used <= normal
    assert set(np.unique(alb[..., 3])) == {0, 255}  # cutout alpha
    em = np.asarray(Image.open(tmp_path / "retro/m/godot/m_emission.png"))
    assert em.max() == 0


def test_emission_snaps_to_fullbrights(tmp_path):
    em = np.zeros((64, 64, 3), np.uint8)
    em[32:, 32:] = (255, 200, 80)
    _material(tmp_path, emission=em)
    r = retro.process(tmp_path, "m", size=16, targets=("godot",))
    assert r["fullbright_pixels"] == 64  # 8x8 quarter of a 16x16 map
    pal = _palette()
    fb = {pal["colors"][i] for i in pal["fullbright"]}
    out = np.asarray(Image.open(tmp_path / "retro/m/godot/m_emission.png"))
    lit = out[8:, 8:].reshape(-1, 3)
    assert {"%02x%02x%02x" % tuple(p) for p in lit} <= fb
    assert out[:8, :8].max() == 0


def test_engine_packing(tmp_path):
    _material(tmp_path)
    retro.process(tmp_path, "m", size=16)
    base = tmp_path / "retro/m"
    orm = np.asarray(Image.open(base / "godot/m_orm.png"))
    assert tuple(orm[0, 0]) == (255, 146, 0)  # roughness 128/255 snaps to 4/7 with 8 levels
    ms = np.asarray(Image.open(base / "unity_urp/m_metallic_smoothness.png"))
    assert ms[0, 0, 0] == 0 and ms[0, 0, 3] == 109  # smoothness = 1 - 4/7
    for f in ("roughness", "metallic", "ao", "normal", "albedo", "emission"):
        assert (base / f"blender/m_{f}.png").exists()
