"""EXAMPLE_DECK_FLOOR: bare steel deck plates.

32 x 32 unit plates with recessed seams; diamond-plate tread (R1, R3) or
round studs (R2) kept off a border where countersunk bolts sit. Tread tops
are worn shiny. No single strong direction, so it survives 90-degree
rotation on floor pieces.
"""

from __future__ import annotations

import numpy as np

from fullbright import compose as C
from fullbright.kit import hardware as H

ART_ID = "EXAMPLE_DECK_FLOOR"
KIND = "floor"
SIZE = 1024
VARIANTS = {
    "R1": dict(seed=41, tread="diamond", mv=0.75),
    "R2": dict(seed=43, tread="studs", mv=0.75),
    "R3": dict(seed=47, tread="diamond", mv=0.6),
}
DITHER = 0.5


def build(variant="R1", size=SIZE, base_dir=None):
    p = VARIANTS[variant]
    q, y, x = H.grid(size)
    fy, dy = H.seams(y, [0, 32 * q], size, q)
    fx, dx = H.seams(x, [0, 32 * q], size, q)
    face = fy * fx
    dist = np.minimum(dx, dy)
    tread = H.diamond(y, x, 4 * q, q) if p["tread"] == "diamond" else H.studs(y, x, 4 * q, q)
    tread = tread * C.smoothstep(2.4 * q, 3.0 * q, dist)
    ctr = [(py + oy, px + ox) for py in (0, 32 * q) for px in (0, 32 * q)
           for oy in (2 * q, 30 * q) for ox in (2 * q, 30 * q)]
    b = H.bolts(y, x, ctr, 0.6 * q)
    height = 0.3 + 0.5 * face + 0.12 * tread * face + 0.05 * b
    value = (1 - 0.12 * H.grime(size, 1, base_dir)) * face + 0.6 * (1 - face)
    polish = (tread > 0.2).astype(float) * face
    return H.finish(size, q, p["seed"], height, dist, np.zeros((size, size)), value,
                    base_dir=base_dir, polish=polish, metal_value=p["mv"])
