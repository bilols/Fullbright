"""Delivery: full-size maps -> the texture files a game kit imports.

    <out_root>/<ID>/<hi>/T_<ID>_<hi>_BC.png   base colour, sRGB, palette-locked
                         T_<ID>_<hi>_N.png    normal, OpenGL / Y+
                         T_<ID>_<hi>_MS.png   R metallic (0/1), G AO, B 0, A smoothness
                                              (Unity URP Lit "metallic smoothness" packing)
                         T_<ID>_<hi>_E.png    emission mask, white where it glows (only if any)
    <out_root>/<ID>/<lo>/...                  the same art downsampled from the <hi> files

(hi, lo) is (512, 256) by default: a 64-unit tile at 8 px per unit. A family
on a 128-unit repeat uses (1024, 512) to keep the same density.

- The low-res set is the delivered high-res set downsampled, never a separate design.
- Metallic is written 0 or 1 per pixel.
- Emission is a mask: an engine multiplies it by a glow colour, so it is
  written white/grey, not coloured.
- Base colour snaps to a palette (Quake by default; fullbright colours are
  never used here), optionally limited to a list of allowed colours.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from fullbright.retro import Palette, _box


def palette_subset(colours=None, palette: str = "quake") -> tuple[Palette, np.ndarray]:
    """The palette plus the indices base colour may use: every non-fullbright
    colour, or only those whose hex (e.g. "5b5b7f") is in `colours`."""
    pal = Palette.load(palette)
    if not colours:
        return pal, np.asarray(pal.normal_idx)
    hexes = ["%02x%02x%02x" % tuple(c) for c in np.round(pal.rgb * 255).astype(int)]
    want = {c.lower().lstrip("#") for c in colours}
    allowed = np.array([i for i in pal.normal_idx if hexes[i] in want])
    if not len(allowed):
        raise ValueError(f"none of {sorted(want)[:5]}... are non-fullbright colours of the {palette} palette")
    return pal, allowed


def _save(arr, path: Path, mode: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(arr * 255 + 0.5, 0, 255).astype(np.uint8), mode).save(path)


def _renorm(n01):
    n = n01 * 2 - 1
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9
    return n * 0.5 + 0.5


def deliver(maps: dict, art_id: str, out_root, colours=None, palette: str = "quake",
            dither: float = 0.0, emission_threshold: float = 0.05, resolutions=(512, 256)) -> dict:
    """maps: full-size float arrays (any multiple of the high resolution):
        albedo (h,w,3), normal (h,w,3, 0-1 encoded), ao (h,w), roughness (h,w),
        metallic (h,w), optional emission (h,w) 0-1.
    colours: allowed base colours (hex list) or None for the whole palette.
    Returns {ok, files, base_colour_colors, bc512, bc256} (bc* = the delivered
    high / low base colour arrays, for checks)."""
    pal, allowed = palette_subset(colours, palette)
    root = Path(out_root) / art_id
    files = []

    def w(res, suffix, arr, mode):
        p = root / str(res) / f"T_{art_id}_{res}_{suffix}.png"
        _save(arr, p, mode)
        files.append(str(p))

    hi, lo = resolutions
    albedo_hi = _box(maps["albedo"], hi)
    snap = (lambda a: pal.dither(a, allowed, strength=dither)) if dither > 0 else \
        (lambda a: pal.snap(a, allowed))
    bc_hi = snap(albedo_hi)
    bc_lo = pal.snap(_box(bc_hi, lo), allowed)

    emission = maps.get("emission")
    out = {"ok": True, "files": files, "art_id": art_id}
    for res, bc in ((hi, bc_hi), (lo, bc_lo)):
        w(res, "BC", bc, "RGB")
        w(res, "N", _renorm(_box(maps["normal"], res)), "RGB")
        metal = (_box(maps["metallic"], res) >= 0.5).astype(np.float64)
        ms = np.dstack([metal, _box(maps["ao"], res), np.zeros((res, res)),
                        1 - _box(maps["roughness"], res)])
        w(res, "MS", ms, "RGBA")
        if emission is not None and emission.max() > emission_threshold:
            e = _box(emission, res)
            e = np.where(e > emission_threshold, e / (e.max() + 1e-9), 0)
            w(res, "E", np.dstack([e, e, e]), "RGB")
    out["base_colour_colors"] = int(len(np.unique(np.round(bc_hi.reshape(-1, 3), 4), axis=0)))
    out["bc512"], out["bc256"] = bc_hi, bc_lo
    return out
