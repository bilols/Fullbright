"""EXAMPLE_PANEL_WALL: painted steel panels with corner bolts.

A minimal family to copy. One 64-unit tile (8 px per unit at 512): four
32 x 32 panels with recessed 1-unit seams (vertical seams at u = 0 and 0.5,
so a half-tile cut lands on a seam), a bolt 4 units in from each panel
corner, paint chipped near the seams, retro finish baked in.

Every family module provides:
    ART_ID, KIND (which checks apply), VARIANTS {name: settings},
    build(variant, size, base_dir) -> {albedo, normal, ao, roughness, metallic,
    height, optional emission}; optionally COLOURS (allowed palette hex list),
    DITHER (number or {variant: number}) and RES ((512, 256) by default).
"""

from __future__ import annotations

import numpy as np

from fullbright.kit import hardware as H

ART_ID = "EXAMPLE_PANEL_WALL"
KIND = "wall"
SIZE = 1024           # build size; delivered at 512 and 256
VARIANTS = {
    "R1": dict(seed=11, paint="gray", wear=0.45),
    "R2": dict(seed=23, paint="dark", wear=0.8),
    "R3": dict(seed=37, paint="blue", wear=0.4),
}
DITHER = 0.5


def build(variant="R1", size=SIZE, base_dir=None):
    p = VARIANTS[variant]
    q, y, x = H.grid(size)
    fy, dy = H.seams(y, [0, 32 * q], size, q)
    fx, dx = H.seams(x, [0, 32 * q], size, q)
    face = fy * fx
    dist = np.minimum(dx, dy)
    ctr = [(py + oy, px + ox) for py in (0, 32 * q) for px in (0, 32 * q)
           for oy in (4 * q, 28 * q) for ox in (4 * q, 28 * q)]
    bolts = H.bolts(y, x, ctr, 0.75 * q)
    height = 0.35 + 0.55 * face + 0.2 * bolts
    rng = np.random.default_rng(p["seed"])
    panel = (y // (32 * q)).astype(int) * 2 + (x // (32 * q)).astype(int)
    value = (1 + rng.uniform(-0.05, 0.05, 4))[panel] * face + 0.7 * (1 - face)
    painted = (bolts == 0).astype(float)
    return H.finish(size, q, p["seed"], height, dist, painted, value, paint=p["paint"],
                    wear=p["wear"], base_dir=base_dir)
