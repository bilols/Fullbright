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


# --- Kit: texture families built in code -------------------------------------

def _kit_finish(maps, art_id, out_root, colours, kind, dither, resolutions=(512, 256)):
    from fullbright.kit import checks, deliver
    r = deliver.deliver(maps, art_id, out_root, colours=colours, dither=dither, resolutions=resolutions)
    res = checks.run(art_id, r.pop("bc512"), r.pop("bc256"), height=maps.get("height"),
                     kind=kind, out_dir=f"{out_root}/{art_id}/checks")
    sheet = checks.review_sheet(art_id, out_root, f"{out_root}/{art_id}/{art_id}_review.png", label=art_id,
                                res=resolutions[0])
    return {**r, "checks": res, "review_sheet": sheet}


def kit_build(output_dir: str, family: str, variants: str = "all", bases_dir: str = "",
              family_path=(), family_packages=()) -> dict:
    """Build a texture family (a module that draws a tiling material in code)
    and deliver each variant as palette-locked BC / N / MS / E files.

    family: a family ID. Built-in examples are EXAMPLE_PANEL_WALL and
    EXAMPLE_DECK_FLOOR; your own families come from the packages named in
    MM_FAMILY_PACKAGES (importable from MM_FAMILY_PATH); see docs/KIT.md.
    variants: "all" or a comma list such as "R1,R3". bases_dir: optional
    folder of grayscale base textures the family layers in (default:
    `sources/bases` beside the output folder); missing bases fall back to
    procedural stand-ins.

    Writes `<output_dir>/art_delivery/<ID>_<variant>/<hi>|<lo>/T_<ID>_<variant>_<res>_<BC|N|MS|E>.png`
    (512 and 256 unless the family sets RES), check previews in `.../checks/`,
    and a review sheet `<ID>_<variant>_review.png` (BC | N | MS | E | offset | tall wall).
    Returns {ok, results: [{art_id, files, checks: {passed, seams, joints, notes}, review_sheet}]}.
    """
    import importlib
    from pathlib import Path
    from fullbright.kit import registry
    try:
        fams = registry.families(family_path, family_packages)
        if family not in fams:
            raise ValueError(f"no family {family}; known: {sorted(fams)}")
        mod = importlib.import_module(fams[family])
        names = list(mod.VARIANTS) if variants == "all" else [v.strip() for v in variants.split(",")]
        bad = [v for v in names if v not in mod.VARIANTS]
        if bad:
            raise ValueError(f"unknown variant(s) {bad}; {family} has {list(mod.VARIANTS)}")
        out_root = f"{output_dir}/art_delivery"
        bases = bases_dir or str(Path(output_dir).parent / "sources" / "bases")
        dither = getattr(mod, "DITHER", 0.0)  # a number, or {variant: number}
        results = [_kit_finish(mod.build(v, base_dir=bases), f"{mod.ART_ID}_{v}", out_root,
                               getattr(mod, "COLOURS", None), mod.KIND,
                               dither.get(v, 0.0) if isinstance(dither, dict) else dither,
                               getattr(mod, "RES", (512, 256))) for v in names]
        return {"ok": all(r["ok"] for r in results), "results": results}
    except (OSError, ValueError, KeyError, ImportError) as exc:
        return {"ok": False, "error": str(exc)}


def kit_deliver_bake(output_dir: str, basename: str, art_id: str, colours: str = "",
                     kind: str = "four_edge", dither: float = 0.0) -> dict:
    """Turn a Material Maker 2048 bake (render_graph output in MM_OUTPUT_DIR:
    `<basename>_albedo`, `_normal`, `_orm`, optional `_emission` and
    `_heightmap`) into a delivery set for `art_id`, the same files and checks
    as kit_build.

    colours: comma list of allowed palette hex colours for the base colour
    (e.g. "5b5b7f,474767"), or "" for the whole palette. kind: wall | floor |
    ceiling | four_edge | trim | single (which seam and joint checks apply).
    dither: as retro_process.
    """
    import numpy as np
    from PIL import Image
    from pathlib import Path
    try:
        src = Path(output_dir)
        load = lambda n, mode: np.asarray(Image.open(src / f"{basename}_{n}.png").convert(mode),
                                          dtype=np.float64) / 255
        orm = load("orm", "RGB")
        maps = {"albedo": load("albedo", "RGB"), "normal": load("normal", "RGB"),
                "ao": orm[..., 0], "roughness": orm[..., 1], "metallic": orm[..., 2]}
        if (src / f"{basename}_emission.png").exists():
            maps["emission"] = load("emission", "L")
        if (src / f"{basename}_heightmap.png").exists():
            maps["height"] = load("heightmap", "L")
        cols = [c.strip() for c in colours.split(",") if c.strip()] or None
        return {"ok": True, "results": [_kit_finish(maps, art_id, f"{output_dir}/art_delivery",
                                                    cols, kind, dither)]}
    except (OSError, ValueError, KeyError) as exc:
        return {"ok": False, "error": str(exc)}
