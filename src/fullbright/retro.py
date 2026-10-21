"""Retro post-processing for Material Maker maps.

Takes the full-size maps Material Maker bakes (always 2048) and turns them
into small, hard-pixel, palette-locked textures, then packs them for
Godot, Unity URP and Blender.

    python -m fullbright.retro OUTPUT_DIR BASENAME --size 256

reads OUTPUT_DIR/BASENAME_albedo.png, _orm.png, _normal.png and (if present)
_emission.png, and writes OUTPUT_DIR/retro/BASENAME/<target>/...

Albedo rules:
- Box-filter downscale (each output pixel is the plain average of the
  source pixels it covers). No Lanczos, no ringing, no soft halos.
- Every pixel snaps to the nearest palette color in OKLab, a perceptual
  color space, so the match tracks what the eye sees rather than raw RGB.
- Fullbright colors are only allowed where the emission map is lit. If they
  weren't held back, ordinary orange brick or yellow paint would grab Quake's
  glowing fire colors and light up in the engine.
- Alpha is kept, but snapped to fully on or fully off (cutout).

Emission comes for free: it's the albedo wherever a fullbright color landed,
black everywhere else.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image

PALETTE_DIR = Path(__file__).parent / "palettes"


# ---------------------------------------------------------------- palette

class Palette:
    def __init__(self, colors_hex, fullbright, exclude=()):
        rgb = np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in colors_hex],
                       dtype=np.float32) / 255.0
        excl = set(exclude)
        fb = set(fullbright) - excl
        self.normal_idx = np.array([i for i in range(len(rgb)) if i not in fb and i not in excl])
        self.fb_idx = np.array(sorted(fb))
        self.rgb = rgb
        self.lab = _oklab(rgb)

    @classmethod
    def load(cls, name_or_path: str = "quake") -> "Palette":
        p = Path(name_or_path)
        if not p.exists():
            p = PALETTE_DIR / f"{name_or_path}.json"
        if p.suffix.lower() == ".act":
            data = p.read_bytes()
            n = int.from_bytes(data[768:770], "big") if len(data) >= 770 else 256
            cols = [data[i * 3:i * 3 + 3].hex() for i in range(n or 256)]
            return cls(cols, fullbright=())
        d = json.loads(p.read_text())
        return cls(d["colors"], d.get("fullbright", ()), d.get("exclude", ()))

    def snap(self, rgb: np.ndarray, allowed: np.ndarray) -> np.ndarray:
        """Nearest palette color (OKLab distance) for each pixel, restricted
        to the palette indices in `allowed`. rgb is (..., 3) floats 0-1."""
        flat = _oklab(rgb.reshape(-1, 3))
        cand = self.lab[allowed]
        out = np.empty(len(flat), dtype=np.int64)
        for s in range(0, len(flat), 65536):  # chunk to bound memory
            d = ((flat[s:s + 65536, None, :] - cand[None, :, :]) ** 2).sum(-1)
            out[s:s + 65536] = allowed[d.argmin(1)]
        return self.rgb[out].reshape(rgb.shape)


def _srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _oklab(rgb):
    lin = _srgb_to_linear(np.asarray(rgb, dtype=np.float32))
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                   [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]], dtype=np.float32)
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                   [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]], dtype=np.float32)
    lms = np.cbrt(lin @ m1.T)
    return lms @ m2.T


# ---------------------------------------------------------------- helpers

def _load(path, mode):
    with Image.open(path) as im:
        return np.asarray(im.convert(mode), dtype=np.float32) / 255.0


def _box(arr: np.ndarray, size: int) -> np.ndarray:
    """Plain area-average downscale to size x size."""
    h, w = arr.shape[:2]
    if h % size == 0 and w % size == 0:
        fy, fx = h // size, w // size
        return arr.reshape(size, fy, size, fx, -1).mean((1, 3)).reshape(size, size, *arr.shape[2:])
    im = Image.fromarray((arr * 255).round().astype(np.uint8))
    return np.asarray(im.resize((size, size), Image.BOX), dtype=np.float32) / 255.0


def _save(arr, path, mode):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(np.clip(arr * 255 + 0.5, 0, 255).astype(np.uint8), mode).save(path)


def _quantize(a, levels):
    return np.round(a * (levels - 1)) / (levels - 1) if levels else a


# ---------------------------------------------------------------- main step

def process(src_dir, basename, size=256, palette="quake", out_dir=None,
            targets=("godot", "unity_urp", "blender"), emission_threshold=0.1,
            alpha_threshold=0.5, roughness_levels=8, normal_strength=1.0):
    src = Path(src_dir)
    pal = Palette.load(palette)
    out = Path(out_dir or src / "retro" / basename)

    alb = _box(_load(src / f"{basename}_albedo.png", "RGBA"), size)
    rgb, alpha = alb[..., :3], alb[..., 3]

    em_path = src / f"{basename}_emission.png"
    if em_path.exists():
        em = _box(_load(em_path, "RGB"), size)
        lit = em.max(-1) > emission_threshold
    else:
        lit = np.zeros(rgb.shape[:2], bool)

    snapped = pal.snap(rgb, pal.normal_idx)
    if lit.any() and len(pal.fb_idx):
        # glowing pixels take the emission map's color, snapped to fullbrights
        snapped[lit] = pal.snap(em[lit], pal.fb_idx)
    emission = np.where(lit[..., None], snapped, 0.0)
    alpha = (alpha >= alpha_threshold).astype(np.float32)

    orm_path = src / f"{basename}_orm.png"
    if orm_path.exists():
        orm = _box(_load(orm_path, "RGB"), size)
    else:
        orm = np.stack([np.ones((size, size)), np.full((size, size), 0.8), np.zeros((size, size))], -1)
    ao, rough, metal = orm[..., 0], _quantize(orm[..., 1], roughness_levels), orm[..., 2]

    nrm_path = src / f"{basename}_normal.png"
    if nrm_path.exists():
        n = _box(_load(nrm_path, "RGB"), size) * 2 - 1
        n[..., :2] *= normal_strength
        n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-6
        normal = n * 0.5 + 0.5
    else:
        normal = np.broadcast_to([0.5, 0.5, 1.0], (size, size, 3)).copy()

    albedo = np.dstack([snapped, alpha])
    written = []

    def w(target, suffix, arr, mode):
        p = out / target / f"{basename}_{suffix}.png"
        _save(arr, str(p), mode)
        written.append(str(p))

    for t in targets:
        w(t, "albedo", albedo, "RGBA")
        w(t, "normal", normal, "RGB")
        w(t, "emission", emission, "RGB")
        if t == "godot":
            w(t, "orm", np.dstack([ao, rough, metal]), "RGB")
        elif t == "unity_urp":
            w(t, "metallic_smoothness", np.dstack([metal, metal, metal, 1 - rough]), "RGBA")
            w(t, "occlusion", np.dstack([ao, ao, ao]), "RGB")
        elif t == "blender":
            w(t, "roughness", np.dstack([rough] * 3), "RGB")
            w(t, "metallic", np.dstack([metal] * 3), "RGB")
            w(t, "ao", np.dstack([ao] * 3), "RGB")

    # 4x nearest-neighbour contact sheet for eyeballing: albedo, emission, normal, ORM
    sheet = np.concatenate([snapped * alpha[..., None] + (1 - alpha[..., None]) * 0.5,
                            emission, normal, np.dstack([ao, rough, metal])], 1)
    sheet_im = Image.fromarray((sheet * 255 + 0.5).astype(np.uint8), "RGB")
    sheet_im = sheet_im.resize((sheet_im.width * 2, sheet_im.height * 2), Image.NEAREST)
    sheet_path = out / f"{basename}_sheet.png"
    sheet_im.save(sheet_path)
    return {"ok": True, "files": written, "sheet": str(sheet_path),
            "colors_used": int(len(np.unique(snapped.reshape(-1, 3), axis=0))),
            "fullbright_pixels": int(lit.sum())}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src_dir")
    ap.add_argument("basename")
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--palette", default="quake")
    ap.add_argument("--out")
    ap.add_argument("--targets", default="godot,unity_urp,blender")
    a = ap.parse_args(argv)
    r = process(a.src_dir, a.basename, a.size, a.palette, a.out, tuple(a.targets.split(",")))
    print(json.dumps(r, indent=1))


if __name__ == "__main__":
    main()
