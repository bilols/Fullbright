"""Automatic texture checks, plus the review previews a person needs to judge
what numbers can't.

Checks:
- seams: jump across each wrap edge vs. the ordinary neighbour-pixel jump
  (about 1 = invisible). Four-edge for walls/floors; left/right for trim
  sheets, whose bottom quarter (a riser band) must also wrap top to bottom.
- wall joints: a vertical joint at u = 0 and u = 0.5, so a half-tile cut
  (a 45-degree wall that shows 1.5 tiles) lands on a joint.
- thin features at the low resolution: joints must survive the downsample.
- single images (kind "single") are not tiles; no tiling checks apply.

Previews:
- offset: the tile rolled by half both ways, so its edges meet in the middle.
- tall wall: 3 x 12 tiles seen from a distance, the repetition ("polka-dot") test.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from fullbright.retro import _box


def _lum(a):
    return a @ np.array([0.2126, 0.7152, 0.0722]) if a.ndim == 3 else a


def seam_ratios(img: np.ndarray) -> dict:
    """Jump across each wrap edge divided by the jump between the edge pixels
    and their own inner neighbours (or the tile's average jump, if larger).
    Comparing with the neighbours, not only the tile average, keeps a flat,
    quiet tile from flagging ordinary pixel noise as a seam."""
    a = _lum(img.astype(np.float64))
    inner_x = np.abs(a[:, 1:] - a[:, :-1]).mean()
    inner_y = np.abs(a[1:] - a[:-1]).mean()
    local_x = (np.abs(a[:, 1] - a[:, 0]).mean() + np.abs(a[:, -1] - a[:, -2]).mean()) / 2
    local_y = (np.abs(a[1] - a[0]).mean() + np.abs(a[-1] - a[-2]).mean()) / 2
    return {"left_right": float(np.abs(a[:, 0] - a[:, -1]).mean() / (max(inner_x, local_x) + 1e-9)),
            "top_bottom": float(np.abs(a[0] - a[-1]).mean() / (max(inner_y, local_y) + 1e-9))}


def joint_signal(height: np.ndarray, us=(0.0, 0.5), half_width_frac=0.012) -> dict:
    """How recessed the height map is at each u, against the tile's median
    column. >= 0.15 of the full height range counts as a joint."""
    h = height.astype(np.float64)
    w = h.shape[1]
    col = h.mean(axis=0)
    med, rng = np.median(col), (h.max() - h.min() + 1e-9)
    hw = max(1, int(w * half_width_frac))
    out = {}
    for u in us:
        c = int(round(u * w)) % w
        cols = [(c + k) % w for k in range(-hw, hw + 1)]
        # lowest point along the column band, per row, averaged over rows that have a joint
        band = h[:, cols].min(axis=1)
        depth = (med - band) / rng
        out[f"u={u}"] = float(np.percentile(depth, 75))
    return out


def offset_preview(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    return np.roll(img, (h // 2, w // 2), (0, 1))


def tall_wall_preview(img256: np.ndarray, across=3, up=12, px_per_tile=48) -> np.ndarray:
    """The tile repeated across x up, each tile shown at px_per_tile pixels:
    roughly how a 12-storey wall reads from far away."""
    small = _box(img256, px_per_tile) if px_per_tile < img256.shape[0] else img256
    return np.tile(small, (up, across, 1))


def run(art_id: str, bc512, bc256, height=None, kind="wall", out_dir=None) -> dict:
    """kind: wall | floor | ceiling | four_edge | trim | trim_riser | single (no tiling)"""
    res = {"art_id": art_id, "seams": {}, "passed": True, "notes": []}
    if kind == "single":
        return res
    for name, img in (("512", bc512), ("256", bc256)):
        res["seams"][name] = seam_ratios(img)
    need_tb = kind not in ("trim",)
    for name, s in res["seams"].items():
        if s["left_right"] > 1.6 or (need_tb and s["top_bottom"] > 1.6):
            res["passed"] = False
            res["notes"].append(f"visible seam at {name}: {s}")
    if kind == "trim":
        # the riser band (bottom quarter of a trim sheet) also tiles top to bottom
        res["seams"]["riser"] = {r: seam_ratios(img[img.shape[0] * 3 // 4:])["top_bottom"]
                                for r, img in (("512", bc512), ("256", bc256))}
        for r, s in res["seams"]["riser"].items():
            if s > 1.6:
                res["passed"] = False
                res["notes"].append(f"riser band seam at {r}: {s:.2f}")
    if kind == "wall" and height is not None:
        js = joint_signal(height)
        res["joints"] = js
        for u, d in js.items():
            if d < 0.15:
                res["passed"] = False
                res["notes"].append(f"no clear vertical joint at {u} (depth {d:.2f})")
        # a 1-unit joint has to survive at the low resolution (4 px at 256)
        js256 = joint_signal(_box(height, 256), half_width_frac=0.012)
        res["joints_256"] = js256
        if min(js256.values()) < 0.1:
            res["passed"] = False
            res["notes"].append(f"joints fade at 256: {js256}")
    if out_dir:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        _png(offset_preview(bc512), out_dir / f"{art_id}_offset.png", scale=1)
        _png(tall_wall_preview(bc256), out_dir / f"{art_id}_tallwall.png", scale=1)
        res["previews"] = [str(out_dir / f"{art_id}_offset.png"), str(out_dir / f"{art_id}_tallwall.png")]
    return res


def _png(a, path, scale=1):
    im = Image.fromarray(np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8))
    if scale != 1:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    im.save(path)


def review_sheet(art_id: str, root, out_path, label=None, res=512):
    """One image per delivery: BC | N | MS (metal, AO, smoothness) | E | offset | tall wall."""
    root = Path(root) / art_id
    get = lambda s: _box(np.asarray(Image.open(root / str(res) / f"T_{art_id}_{res}_{s}.png"),
                                    dtype=np.float64) / 255, 512)
    bc, n, ms = get("BC"), get("N"), get("MS")
    e_path = root / str(res) / f"T_{art_id}_{res}_E.png"
    e = _box(np.asarray(Image.open(e_path), dtype=np.float64) / 255, 512) if e_path.exists() else np.zeros_like(bc)
    msv = np.dstack([ms[..., 0], ms[..., 1], ms[..., 3]])  # show metal/AO/smoothness as RGB
    tall = tall_wall_preview(_box(bc, 256), across=3, up=12, px_per_tile=42)  # 504 x 126
    tall = np.pad(tall, ((4, 4), (0, 512 - tall.shape[1]), (0, 0)), constant_values=1)[:512]
    tall = np.pad(tall, ((0, 512 - tall.shape[0]), (0, 0), (0, 0)), constant_values=1)
    row = np.concatenate([bc, n, msv, e, offset_preview(bc), tall], 1)
    im = Image.fromarray(np.clip(row * 255 + 0.5, 0, 255).astype(np.uint8))
    im = im.resize((im.width // 2, im.height // 2), Image.BOX)
    canvas = Image.new("RGB", (im.width, im.height + 22), "white")
    canvas.paste(im, (0, 22))
    d = ImageDraw.Draw(canvas)
    for i, t in enumerate(["BC", "N", "MS (R metal, G AO, B smooth)", "E", "offset", "tall wall 3x12"]):
        d.text((i * 256 + 4, 5), t, fill="black")
    if label:
        d.text((canvas.width - 7 * len(label) - 6, 5), label, fill="black")
    canvas.save(out_path)
    return str(out_path)
