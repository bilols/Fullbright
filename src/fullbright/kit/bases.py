"""Optional base textures: grayscale, seamless images a family layers in
(painted metal, brushed metal, grime, stone...). When a base is missing the
family still builds: a seamless procedural stand-in is used instead, so
example families run on any machine."""

from __future__ import annotations

import zlib
from pathlib import Path

import numpy as np

from fullbright import compose as C

# feature size (fraction of the tile) and anisotropy for the stand-ins, by name prefix
_STANDINS = {
    "brushed": (0.004, (0.06, 1.0)),
    "grime": (0.08, (1.0, 1.0)),
    "painted": (0.02, (1.0, 1.0)),
}


def load_base(base_dir, name: str, size: int, fallback: bool = True) -> np.ndarray:
    """`<base_dir>/<name>.png` as a 0-1 float array resized to `size` with
    wrap padding (edges keep meeting). Missing file: a procedural stand-in
    when fallback is True, else FileNotFoundError."""
    path = Path(base_dir) / f"{name}.png" if base_dir else None
    if path is None or not path.exists():
        if not fallback:
            raise FileNotFoundError(path)
        feat, aniso = next((v for k, v in _STANDINS.items() if name.startswith(k)), (0.03, (1.0, 1.0)))
        seed = zlib.crc32(name.encode()) & 0xFFFF
        return C.fft_noise(size, seed, feature_px=max(1.0, feat * size), aniso=aniso, octaves=3)
    from PIL import Image
    im = Image.open(path).convert("L")
    a = np.asarray(im, dtype=np.float64) / 255
    if a.shape[0] != size:
        pad = 8
        big = np.pad(a, pad, mode="wrap")
        k = size / a.shape[0]
        im = Image.fromarray((big * 65535).astype(np.uint16)).resize(
            (round(big.shape[1] * k), round(big.shape[0] * k)), Image.BICUBIC)
        a = np.asarray(im, dtype=np.float64)[round(pad * k):round(pad * k) + size,
                                            round(pad * k):round(pad * k) + size] / 65535
    return a


def norm(a: np.ndarray) -> np.ndarray:
    """Zero mean, unit deviation."""
    return (a - a.mean()) / (a.std() + 1e-9)
