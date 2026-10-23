"""Fullbright kit: composer, delivery, checks, registry and the example
families (no Godot; missing base textures fall back to procedural stand-ins)."""
import sys

import numpy as np
from PIL import Image

from fullbright import compose as C, tools
from fullbright.kit import bases, checks, deliver, hardware as H, registry


def test_fft_noise_tiles_seamlessly():
    n = C.fft_noise(128, 1, feature_px=6, aniso=(0.2, 1), octaves=3)
    s = checks.seam_ratios(n)
    assert s["left_right"] < 1.5 and s["top_bottom"] < 1.5


def test_normal_from_height_is_opengl_y_up():
    h = np.zeros((32, 32))
    h[10:22, 10:22] = 1
    n = C.normal_from_height(h, 4)
    assert n[9, 16, 1] > 0.6 and n[22, 16, 1] < 0.4 and n[16, 9, 0] < 0.4


def _flat_maps(size=512):
    return {"albedo": np.full((size, size, 3), 0.45),
            "normal": np.dstack([np.full((size, size), .5)] * 2 + [np.ones((size, size))]),
            "ao": np.ones((size, size)), "roughness": np.full((size, size), 0.55),
            "metallic": np.zeros((size, size))}


def test_delivery_names_packing_and_low_res(tmp_path):
    m = _flat_maps()
    m["metallic"][:, :256] = 0.7
    r = deliver.deliver(m, "TEST", tmp_path)
    names = sorted(p.split("/")[-1] for p in r["files"])
    assert names == sorted(f"T_TEST_{res}_{s}.png" for res in (512, 256) for s in ("BC", "N", "MS"))
    ms = np.asarray(Image.open(tmp_path / "TEST/512/T_TEST_512_MS.png"))
    assert ms.shape == (512, 512, 4)
    assert ms[0, 0, 0] == 255 and ms[0, 400, 0] == 0
    assert ms[0, 0, 2] == 0 and abs(int(ms[0, 0, 3]) - 115) <= 1


def test_colour_subset_limits_the_base_colour(tmp_path):
    m = _flat_maps()
    m["albedo"][:] = (0.3, 0.3, 0.45)
    r = deliver.deliver(m, "BLUE", tmp_path, colours=["5b5b7f", "474767"])
    got = {"%02x%02x%02x" % tuple(c) for c in np.round(r["bc512"].reshape(-1, 3) * 255).astype(int)}
    assert got <= {"5b5b7f", "474767"}


def test_emission_is_a_white_mask(tmp_path):
    m = _flat_maps()
    m["emission"] = np.zeros((512, 512))
    m["emission"][200:220] = 0.4
    deliver.deliver(m, "GLOW", tmp_path)
    e = np.asarray(Image.open(tmp_path / "GLOW/512/T_GLOW_512_E.png"))
    assert e[210, 10].tolist() == [255, 255, 255] and e[0, 0].max() == 0


def test_no_emission_file_when_nothing_glows(tmp_path):
    assert not any(p.endswith("_E.png") for p in deliver.deliver(_flat_maps(), "DARK", tmp_path)["files"])


def test_deliver_128_unit_tile_at_1024(tmp_path):
    r = deliver.deliver(_flat_maps(1024), "X", tmp_path, resolutions=(1024, 512))
    assert r["bc512"].shape[0] == 1024 and r["bc256"].shape[0] == 512
    assert (tmp_path / "X" / "1024" / "T_X_1024_BC.png").exists()


def test_checks_catch_a_seam_and_a_missing_joint():
    ramp = np.tile(np.linspace(0, 1, 256), (256, 1))
    r = checks.run("X", np.dstack([ramp] * 3), np.dstack([ramp[::2, ::2]] * 3),
                   height=np.ones((256, 256)), kind="wall")
    assert not r["passed"]
    assert any("seam" in n for n in r["notes"]) and any("joint" in n for n in r["notes"])


def test_trim_checks_skip_top_bottom():
    a = np.zeros((64, 64, 3))
    a[:32] = 1
    assert checks.run("T", a, a[::2, ::2], kind="trim")["passed"]


def test_single_images_skip_tiling_checks():
    img = np.zeros((64, 64, 3))
    img[:, :32] = 1.0
    res = checks.run("PAD", img, img[::2, ::2], kind="single")
    assert res["passed"] and not res["seams"]


def test_seam_check_ignores_noise_on_a_flat_tile():
    rng = np.random.default_rng(0)
    flat = np.full((64, 64, 3), 0.5)
    flat[rng.random((64, 64)) > 0.97] = 0.45
    s = checks.seam_ratios(flat)
    assert s["left_right"] < 1.6 and s["top_bottom"] < 1.6


def test_retro_finish_bakes_light_and_flattens_normals():
    n = 64
    y = np.arange(n)[:, None] * np.ones((1, n))
    h = C.smoothstep(16, 24, y) * C.smoothstep(48, 40, y)
    normal = C.normal_from_height(h, strength=8)
    maps = {"albedo": np.full((n, n, 3), 0.5), "normal": normal, "ao": np.ones((n, n)),
            "height": h, "roughness": np.full((n, n), 0.5), "metallic": np.zeros((n, n))}
    out = C.retro_finish(maps, q=1, seed=0, grain=0.0, edge=0.0)
    assert out["albedo"][20].mean() > 0.5 > out["albedo"][44].mean()
    tilt = lambda m: np.abs(m[..., 1] - 0.5).max()
    assert tilt(out["normal"]) < tilt(normal)


def test_periodic_rows_wrap_on_their_own():
    r = np.random.default_rng(0).random((64, 32))
    p = C.periodic_rows(r)
    assert np.abs(p[0] - p[-1]).mean() < np.abs(p[1:] - p[:-1]).mean()


def test_missing_bases_fall_back_to_seamless_stand_ins(tmp_path):
    a = bases.load_base(str(tmp_path), "brushed_metal_1", 128)
    assert a.shape == (128, 128) and 0 <= a.min() and a.max() <= 1
    s = checks.seam_ratios(a)
    assert s["left_right"] < 1.6 and s["top_bottom"] < 1.6


def test_diamond_plate_is_periodic_on_its_grid():
    q, y, x = H.grid(256)
    d = H.diamond(y, x, 4 * q, q)
    assert np.allclose(d[:, :32], d[:, 32:64])          # lozenges alternate, so the repeat is two cells


def test_example_families_build_and_pass_checks(tmp_path):
    for fam in ("EXAMPLE_PANEL_WALL", "EXAMPLE_DECK_FLOOR"):
        r = tools.kit_build(str(tmp_path), fam, "R1", bases_dir=str(tmp_path / "none"))
        assert r["ok"], r
        assert r["results"][0]["checks"]["passed"], r["results"][0]["checks"]["notes"]


def test_kit_build_errors_are_data(tmp_path):
    assert "no family" in tools.kit_build(str(tmp_path), "NOPE")["error"]
    assert "unknown variant" in tools.kit_build(str(tmp_path), "EXAMPLE_PANEL_WALL", "R9")["error"]
    assert tools.kit_deliver_bake(str(tmp_path), "missing", "X")["ok"] is False


def test_registry_loads_families_from_your_own_package(tmp_path, monkeypatch):
    pkg = tmp_path / "myfams"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('FAMILIES = {"MY_WALL": "myfams.wall"}\n')
    (pkg / "wall.py").write_text("from fullbright.families.example_panel_wall import *\nART_ID = 'MY_WALL'\n")
    monkeypatch.syspath_prepend(str(tmp_path))                 # undone after the test
    monkeypatch.setattr(sys, "modules", dict(sys.modules))
    fams = registry.families([str(tmp_path)], ["myfams"])
    assert fams["MY_WALL"] == "myfams.wall" and "EXAMPLE_PANEL_WALL" in fams
    r = tools.kit_build(str(tmp_path / "out"), "MY_WALL", "R1", bases_dir=str(tmp_path / "none"),
                        family_path=[str(tmp_path)], family_packages=["myfams"])
    assert r["ok"] and r["results"][0]["art_id"] == "MY_WALL_R1", r
