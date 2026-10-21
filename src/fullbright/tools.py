"""Fullbright MCP tools. Registered in mm_mcp/server.py next to the upstream
tools; kept here so upstream merges stay small."""

from __future__ import annotations

import os

from fullbright import retro

DEFAULT_TARGETS = "godot,unity_urp,blender"


def _targets(targets: str) -> tuple:
    names = tuple(t.strip() for t in targets.split(",") if t.strip())
    bad = [t for t in names if t not in ("godot", "unity_urp", "blender")]
    if bad:
        raise ValueError(f"unknown target(s) {bad}; use godot, unity_urp, blender")
    return names


def retro_process(output_dir: str, basename: str, size: int = 256,
                  palette: str = "quake", targets: str = DEFAULT_TARGETS,
                  emission_threshold: float = 0.1, roughness_levels: int = 8,
                  normal_strength: float = 1.0, dither: float = 0.0,
                  source_gamma: float = 1.0) -> dict:
    """Turn already-rendered Material Maker maps into retro, palette-locked
    textures packed per engine.

    Reads `<output_dir>/<basename>_albedo.png` plus `_orm`, `_normal` and
    `_emission` when present. Render at size 2048 first: the source should be
    the full bake, not a downsampled copy, or the box filter has nothing to
    average and the soft Lanczos smear is baked in.

    - Albedo is box-downscaled to `size`, then every pixel snaps to the
      nearest palette color (OKLab). Fullbright colors are only used where
      the emission map exceeds `emission_threshold`; emission is the
      snapped albedo there and black elsewhere. Alpha becomes a hard cutout.
    - Roughness is quantized to `roughness_levels` steps (0 disables);
      `normal_strength` scales the normal map's tilt before renormalizing.
    - dither: error-diffusion strength (0 = off). Use about 0.8 when the
      palette lacks the source's color (muted olives, warm grays) and the
      surface is grainy enough to hide the pattern (concrete, rock, dirt).
      Leave it off for smooth or painted surfaces.
    - source_gamma: Levels-style gamma applied to the albedo before the
      snap (>1 brightens midtones), for source images that came out too
      dark. 1.0 = untouched.
    - targets: comma list of godot, unity_urp, blender.

    Writes to `<output_dir>/retro/<basename>/<target>/` and a 2x
    nearest-neighbour contact sheet (albedo | emission | normal | ORM) at
    `<output_dir>/retro/<basename>/<basename>_sheet.png`. Returns
    {ok, files, sheet, colors_used, fullbright_pixels} or {ok: False, error}.
    """
    try:
        if not 16 <= size <= 2048:
            raise ValueError("size must be 16-2048")
        if os.sep in basename or "/" in basename or ".." in basename:
            raise ValueError("basename must be a plain name")
        return retro.process(output_dir, basename, size=size, palette=palette,
                             targets=_targets(targets),
                             emission_threshold=emission_threshold,
                             roughness_levels=roughness_levels,
                             normal_strength=normal_strength,
                             dither=dither, source_gamma=source_gamma)
    except (OSError, ValueError, KeyError) as exc:
        return {"ok": False, "error": str(exc)}


def render_retro(render_graph, output_dir: str, ptex: dict, basename: str = "material",
                 size: int = 256, palette: str = "quake", targets: str = DEFAULT_TARGETS,
                 emission_threshold: float = 0.1, roughness_levels: int = 8,
                 normal_strength: float = 1.0, dither: float = 0.0,
                 source_gamma: float = 1.0) -> dict:
    """render_graph at the full 2048 bake, then retro_process the result."""
    r = render_graph(ptex, size=2048, basename=basename, target="Godot/Godot 4 Standard")
    if not r.get("ok"):
        return {"ok": False, "stage": "render", **r}
    out = retro_process(output_dir, basename, size=size, palette=palette, targets=targets,
                        emission_threshold=emission_threshold,
                        roughness_levels=roughness_levels, normal_strength=normal_strength,
                        dither=dither, source_gamma=source_gamma)
    out["source_images"] = r["images"]
    if not out.get("ok"):
        out["stage"] = "retro"
    return out


def make_seamless(path: str, out_path: str = "", band: float = 0.15) -> dict:
    """Make a source image tile seamlessly before using it in a graph's
    `image` node.

    Half-offset crossfade: edges wrap cleanly, the center stays untouched,
    and the only cost is faint ghosting within `band` (fraction of each
    side, default 0.15) of the borders. Keeps continuous lines across the
    seam, which Material Maker's make_tileable node blurs and doubles.

    Writes to `out_path`, or by default `<source dir>/tiled/<name>.png`
    (anything after the first dot is dropped, so `waterblu1.gen.png`
    becomes `tiled/waterblu1.png`). Returns {ok, path, seam_before,
    seam_after}; the seam numbers are the jump across the wrap edges
    relative to ordinary neighbouring pixels, so about 1.0 means invisible.
    """
    from fullbright import seamless
    try:
        return seamless.make_seamless(path, out_path or None, band)
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}
