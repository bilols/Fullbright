"""Make a source image tile seamlessly before it goes into a graph.

Half-offset crossfade: the image is rolled by half its size in both
directions, so its old edges meet in the middle and its new edges come
from the old interior, which wraps cleanly. The original is then laid
back over the middle with a smooth mask that fades to the rolled copy
over a `band` near the borders. Result: edges wrap with no break, the
center is untouched, and the only cost is faint ghosting inside the band.

Compared on a caustic-water source (2026-10-21) against Material Maker's
make_tileable (softer, doubled lines) and a periodic-plus-smooth
decomposition (fixes the color step but not lines that break at the
edge). The crossfade was the only one with continuous lines.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def crossfade(img: np.ndarray, band: float = 0.15) -> np.ndarray:
    """img: (h, w, c) floats. band: fraction of each side used for the fade."""
    h, w = img.shape[:2]
    rolled = np.roll(img, (h // 2, w // 2), (0, 1))

    def ramp(n):
        x = np.arange(n) / (n - 1)
        return np.clip(np.minimum(x, 1 - x) / band, 0, 1)

    m = ramp(h)[:, None] * ramp(w)[None, :]
    m = (m * m * (3 - 2 * m))[..., None]  # smoothstep
    return img * m + rolled * (1 - m)


def seam_ratio(img: np.ndarray) -> float:
    """Mean jump across the wrap edges divided by the mean jump between
    neighbouring pixels. About 1 means the seam is invisible; the liquid
    sources started at 2-4.5."""
    a = img.astype(np.float64)
    inner = (np.abs(a[:, 1:] - a[:, :-1]).mean() + np.abs(a[1:] - a[:-1]).mean()) / 2
    wrap = (np.abs(a[:, 0] - a[:, -1]).mean() + np.abs(a[0] - a[-1]).mean()) / 2
    return float(wrap / inner) if inner else 0.0


def make_seamless(src_path: str, out_path: str | None = None, band: float = 0.15) -> dict:
    src = Path(src_path)
    if not 0.02 <= band <= 0.5:
        raise ValueError("band must be 0.02-0.5")
    with Image.open(src) as im:
        mode = "RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB"
        a = np.asarray(im.convert(mode), dtype=np.float64) / 255.0
    out = crossfade(a, band)
    dest = Path(out_path) if out_path else src.parent / "tiled" / (src.name.split(".")[0] + ".png")
    dest.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8), mode).save(dest)
    return {"ok": True, "path": str(dest),
            "seam_before": round(seam_ratio(a), 2), "seam_after": round(seam_ratio(out), 2)}
