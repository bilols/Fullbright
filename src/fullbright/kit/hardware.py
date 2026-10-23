"""Reusable hardware shapes and one surface finish (paint over steel, chips at
edges, grime, retro shading), so families built from them wear the same way
and sit together in a scene.

Shapes work in a 64-unit tile: `grid(size)` returns q (pixels per unit) and
pixel coordinates; positions and sizes are given in units * q."""

from __future__ import annotations

import numpy as np

from fullbright import compose as C
from fullbright.kit.bases import load_base as _load_base, norm as _norm

STEEL = (0.56, 0.58, 0.60)
PAINTS = {"gray": (0.42, 0.46, 0.52), "dark": (0.33, 0.35, 0.39), "blue": (0.34, 0.34, 0.48),
          "light": (0.50, 0.53, 0.57)}


def grid(size):
    q = size // 64
    y, x = np.mgrid[0:size, 0:size].astype(np.float64)
    return q, y, x


def dome(y, x, cy, cx, r):
    return np.sqrt(np.clip(1 - ((y - cy) ** 2 + (x - cx) ** 2) / (r * r), 0, 1))


def bolts(y, x, centres, r):
    out = np.zeros_like(y)
    for cy, cx in centres:
        out = np.maximum(out, dome(y, x, cy, cx, r))
    return out


def diamond(y, x, g, q, length=1.5, width=0.35):
    """Diamond-plate lozenges on a g-px grid, alternating direction. 0-1 dome."""
    cx = (np.floor(x / g) + 0.5) * g
    cy = (np.floor(y / g) + 0.5) * g
    flip = ((np.floor(x / g) + np.floor(y / g)) % 2) * 2 - 1
    dx, dy = x - cx, y - cy
    ax = (dx + flip * dy) / np.sqrt(2)
    ay = (dx - flip * dy) / np.sqrt(2)
    return np.sqrt(np.clip(1 - (ax / (length * q)) ** 2 - (ay / (width * q)) ** 2, 0, 1))


def studs(y, x, g, q, r=0.7):
    """Round raised studs, rows offset by half a pitch (anti-slip tread)."""
    row = np.floor(y / g)
    cx = (np.floor(x / g - 0.5 * (row % 2)) + 0.5 + 0.5 * (row % 2)) * g
    cy = (row + 0.5) * g
    return dome(y, x, cy, cx, r * q)


def seams(coord, lines, size, q, half=0.5, bevel=0.6):
    """1 at the panel face, falling into a recessed seam at each line."""
    d = C.wrap_dist(coord, lines, size)
    return C.smoothstep(half * q, (half + bevel) * q, d), d


def finish(size, q, seed, height, dist, painted, value, paint="gray", wear=0.45, n=1,
           chip_shift=(0, 0), base_dir=None, metal_value=0.8, gate_extra=None,
           polish=None, emission=None, rough_paint=0.55, rough_steel=0.36, retro=None):
    """height: relief; dist: px to the nearest seam (chips gather there);
    painted: 1 paint / 0 bare steel; value: brightness multiplier (joints,
    per-panel shifts, grime already in it); polish: extra shine on worn bare tops."""
    B = base_dir  # optional; missing bases fall back to procedural stand-ins
    paint_tex = _norm(_load_base(B, f"painted_metal_{n}", size))
    steel = _load_base(B, f"brushed_metal_{n}", size)
    chipped = np.roll(_load_base(B, "painted_metal_chipped", size), chip_shift, (0, 1))
    chip = C.smoothstep(0.50, 0.44, C.blur(chipped, 0.6))
    gate = C.smoothstep(3.0 * q, 0.7 * q, dist)
    if gate_extra is not None:
        gate = np.clip(gate + gate_extra, 0, 1)
    worn = ((chip * C.smoothstep(0.1, 0.35, gate * wear)) > 0.5) * (painted > 0)
    paint_m = (painted > 0) & ~worn
    pol = np.zeros((size, size)) if polish is None else polish
    paint_rgb = C.tint(value, PAINTS.get(paint, paint) if isinstance(paint, str) else paint)
    steel_v = np.clip(metal_value + 0.6 * (steel - steel.mean()), 0, 1) * value * (1 + 0.28 * pol)
    steel_rgb = C.tint(steel_v, STEEL)
    albedo = np.where(paint_m[..., None], paint_rgb, steel_rgb)
    h = height + 0.008 * paint_tex * paint_m + 0.005 * _norm(steel) * ~paint_m - 0.015 * worn
    normal = C.normal_from_height(h, strength=size / 64 * 1.1)
    ao = C.cavity_ao(h, radius_px=1.5 * q, depth=1.0)
    rough = np.where(paint_m, rough_paint + 0.04 * paint_tex, rough_steel - 0.03 * _norm(steel) - 0.1 * pol)
    maps = {"albedo": np.clip(albedo, 0, 1), "normal": normal, "ao": np.clip(ao, 0, 1),
            "roughness": np.clip(rough, 0, 1), "metallic": (~paint_m).astype(float), "height": h}
    if emission is not None:
        maps["emission"] = emission
    return C.retro_finish(maps, q, seed, **(retro or {}))


def grime(size, n=1, base_dir=None):
    g = _load_base(base_dir, f"grime_{n}", size)
    return np.clip((g.mean() - g) / (g.std() * 3 + 1e-9), 0, 1)
