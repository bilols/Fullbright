"""Building blocks for composing tiling materials in numpy.

Everything here wraps around the image edges, so anything built from these
pieces tiles seamlessly by construction:

- noise is shaped in the frequency domain (FFT), which is periodic;
- gradients, blurs and distances use wrap-around neighbours.

Conventions: arrays are float64 in 0-1, shape (h, w) or (h, w, 3); row 0 is
the top of the image (v = 1 in UV terms). Normal maps are OpenGL / Y+
(green = surface faces up in the image).
"""

from __future__ import annotations

import numpy as np


def fft_noise(size: int, seed: int, feature_px: float, aniso: tuple = (1.0, 1.0),
              octaves: int = 1, falloff: float = 0.5) -> np.ndarray:
    """Seamless noise, normalised to 0-1.

    feature_px: typical blob size in pixels. aniso=(sx, sy) stretches
    features: (8, 1) gives long horizontal streaks (brushed metal).
    octaves > 1 adds finer detail, each octave half the size and
    `falloff` times the amplitude.
    """
    rng = np.random.default_rng(seed)
    fy = np.fft.fftfreq(size)[:, None] * size
    fx = np.fft.fftfreq(size)[None, :] * size
    out = np.zeros((size, size))
    amp, feat = 1.0, float(feature_px)
    for _ in range(octaves):
        white = rng.standard_normal((size, size))
        k = size / max(feat, 1.0)  # cycles per image at the feature size
        r = np.sqrt((fx * aniso[0] / k) ** 2 + (fy * aniso[1] / k) ** 2)
        layer = np.real(np.fft.ifft2(np.fft.fft2(white) * np.exp(-r * r)))
        out += amp * layer / (layer.std() + 1e-9)
        amp *= falloff
        feat /= 2
    lo, hi = np.percentile(out, [0.5, 99.5])
    return np.clip((out - lo) / (hi - lo + 1e-9), 0, 1)


def blur(a: np.ndarray, sigma_px: float) -> np.ndarray:
    """Wrap-around gaussian blur (FFT)."""
    if sigma_px <= 0:
        return a
    h, w = a.shape[:2]
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    g = np.exp(-2 * (np.pi * sigma_px) ** 2 * (fx * fx + fy * fy))
    if a.ndim == 2:
        return np.real(np.fft.ifft2(np.fft.fft2(a) * g))
    return np.dstack([np.real(np.fft.ifft2(np.fft.fft2(a[..., c]) * g)) for c in range(a.shape[2])])


def normal_from_height(h: np.ndarray, strength: float) -> np.ndarray:
    """OpenGL / Y+ tangent-space normal map (0-1 encoded) from a height map.
    strength: height units per pixel of slope; larger = deeper relief."""
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    drow = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    n = np.dstack([-dx * strength, drow * strength, np.ones_like(h)])
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def cavity_ao(h: np.ndarray, radius_px: float, depth: float) -> np.ndarray:
    """Cheap ambient occlusion: darken where a pixel sits below its
    surroundings. 1 = open, lower in crevices."""
    return np.clip(1 - depth * np.clip(blur(h, radius_px) - h, 0, None) * 4, 0, 1)


def smoothstep(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def wrap_dist(coord: np.ndarray, lines, period: int) -> np.ndarray:
    """Distance (px) from each coordinate to the nearest of `lines`,
    measured around the wrap."""
    d = np.full(coord.shape, np.inf)
    for c in lines:
        a = np.abs(coord - c) % period
        d = np.minimum(d, np.minimum(a, period - a))
    return d


def tint(value: np.ndarray, rgb) -> np.ndarray:
    """Multiply a 0-1 value field by a colour."""
    return value[..., None] * np.asarray(rgb, dtype=np.float64)[None, None, :]


def periodic_rows(a: np.ndarray, band: float = 0.25) -> np.ndarray:
    """Make a slice of rows wrap top-to-bottom on its own (a trim band that
    must also tile vertically, like stair risers). Half-offset crossfade
    along v only; left/right wrapping of the input is kept."""
    h = a.shape[0]
    rolled = np.roll(a, h // 2, 0)
    x = np.arange(h) / (h - 1)
    m = np.clip(np.minimum(x, 1 - x) / band, 0, 1)
    m = m * m * (3 - 2 * m)
    m = m.reshape((h,) + (1,) * (a.ndim - 1))
    return a * m + rolled * (1 - m)


def retro_finish(maps: dict, q: int, seed: int, light=(-0.4, 0.8, 0.45), shade=0.7,
                 ao_mix=0.55, edge=0.35, grain=0.10, normal_keep=0.55) -> dict:
    """Quake-style finish: bake soft shading into the base colour.

    - top-left light on the bevels (relief strength from the height map), so
      upper edges catch light and lower edges fall dark, as id's textures do;
    - ambient occlusion multiplied in (crevices and joints darken);
    - a thin highlight on convex edges (rivets, lips, bevel tops);
    - grain at about one palette step, so it survives the snap as pixel grit;
    - the delivered normal map is flattened (normal_keep) so the engine's real
      lights add to the painted shading rather than doubling it.
    """
    h = maps["height"]
    size = h.shape[0]
    n = maps["normal"] * 2 - 1
    L = np.asarray(light, dtype=np.float64)
    L = L / np.linalg.norm(L)
    lam = np.clip(n @ L, 0, 1)
    flat = L[2]
    s = 1 + shade * (lam - flat) / flat
    s *= (1 - ao_mix) + ao_mix * maps["ao"]
    convex = np.clip(h - blur(h, 0.6 * q), 0, None)
    s *= 1 + edge * np.clip(convex / (convex.max() + 1e-9) * 3, 0, 1)
    g = fft_noise(size, seed + 91, feature_px=0.5 * q, octaves=2)
    s *= 1 + grain * (g - 0.5) * 2
    out = dict(maps)
    out["albedo"] = np.clip(maps["albedo"] * s[..., None], 0, 1)
    nn = n.copy()
    nn[..., :2] *= normal_keep
    nn /= np.linalg.norm(nn, axis=-1, keepdims=True)
    out["normal"] = nn * 0.5 + 0.5
    return out
