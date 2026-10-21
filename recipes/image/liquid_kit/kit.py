"""Liquid kit: one grayscale caustic base + one color preset -> a .ptex graph.

    python recipes/image/liquid_kit/kit.py lava contrast2          # prints the graph JSON
    python recipes/image/liquid_kit/kit.py lava contrast2 -o x.ptex

Feed the result to render_retro (size 256, no dither). To add a liquid,
add a preset: `ramp` colors the surface, `glow` (optional) is the emission
ramp. Glow colors must be Quake fullbrights to survive the palette snap:
the fire ramp (dark red to pale yellow), a few reds, the light blues
7fbfff / abe7ff / d7ffff, and white. There are no green or purple
fullbrights.

Ramp and glow positions are on the normalized base (0 = darkest 1% of the
base image, 1 = brightest 0.5%), so a preset lands the same way on every
base. Measure a new base's lo/hi with its luminance percentiles.
"""
import argparse
import json

SOURCES = "C:/Dev/MaterialGenerator/sources/liquids/tiled"

# name: (file, lo, hi) -- lo/hi are the base's 1st and 99.5th luminance percentiles
BASES = {
    "contrast1": ("watercontrast1.png", 0.063, 0.647),  # fine, wispy caustics on near-black
    "contrast2": ("watercontrast2.png", 0.447, 0.933),  # bold clean veins on mid gray
    "grey": ("watergrey.png", 0.408, 0.733),            # busy, grainy, low contrast
}


def _h(x):
    return tuple(int(x[i:i + 2], 16) / 255 for i in (0, 2, 4))


K = (0, 0, 0)
PRESETS = {
    "water": dict(ramp=[(0, _h("1b1b27")), (.25, _h("2f2f3f")), (.6, _h("5b5b7f")), (1, _h("8b8bcb"))],
                  glow=None, rough=.15, normal=.35),
    "lava": dict(ramp=[(0, _h("170000")), (.3, _h("3f0000")), (.55, _h("7f1707")), (1, (.6, .2, .05))],
                 glow=[(0, K), (.4, K), (.5, _h("b7330f")), (.75, _h("e3974f")), (1, _h("f7d38b"))],
                 rough=.6, normal=.35),
    "slime": dict(ramp=[(0, (.06, .09, .05)), (.35, (.15, .22, .12)), (.7, (.27, .38, .22)), (1, (.42, .55, .35))],
                  glow=None, rough=.25, normal=.35),
    "tar": dict(ramp=[(0, (.03, .03, .035)), (.5, (.08, .08, .09)), (1, (.30, .30, .32))],
                glow=None, rough=.35, normal=.6),
    "energy": dict(ramp=[(0, _h("7fbfff")), (.5, _h("abe7ff")), (1, (1, 1, 1))],
                   glow=[(0, _h("7fbfff")), (.5, _h("abe7ff")), (1, (1, 1, 1))], rough=.2, normal=.2),
}


def _grad(stops):
    return {"interpolation": 1, "type": "Gradient",
            "points": [{"pos": p, "r": c[0], "g": c[1], "b": c[2], "a": 1} for p, c in stops]}


def build(preset: str, base: str) -> dict:
    p, (fname, lo, hi) = PRESETS[preset], BASES[base]
    nodes = [
        {"name": "Material", "type": "material", "node_position": {"x": 1100, "y": 0},
         "parameters": {"albedo_color": {"a": 1, "r": 1, "g": 1, "b": 1, "type": "Color"}, "metallic": 0,
                        "roughness": 1, "size": 11, "resolution": 1, "normal_scale": 1, "ao_light_affect": 1,
                        "depth_scale": 1, "emission_energy": 1, "subsurf_scatter_strength": 0}},
        {"name": "Source", "type": "image", "node_position": {"x": 0, "y": 0},
         "parameters": {"image": f"{SOURCES}/{fname}"}},
        {"name": "Normalize", "type": "colorize", "node_position": {"x": 250, "y": 0},
         "parameters": {"gradient": _grad([(lo, K), (hi, (1, 1, 1))])}},
        {"name": "LiquidRamp", "type": "colorize", "node_position": {"x": 550, "y": 0},
         "parameters": {"gradient": _grad(p["ramp"])}},
        {"name": "RippleHeight", "type": "fast_blur", "node_position": {"x": 550, "y": 250},
         "parameters": {"param0": 11, "param1": 6, "param2": 1, "param3": 1}},
        {"name": "RippleNormal", "type": "normal_map", "node_position": {"x": 800, "y": 250},
         "parameters": {"param0": 11, "param1": p["normal"], "param2": 0, "param3": 0, "param4": 0}},
        # Roughness must be a node: a bare Material roughness value exports no ORM map.
        {"name": "Gloss", "type": "uniform_greyscale", "node_position": {"x": 800, "y": -150},
         "parameters": {"color": p["rough"]}},
    ]
    links = [("Source", "Normalize", 0), ("Normalize", "LiquidRamp", 0), ("LiquidRamp", "Material", 0),
             ("Normalize", "RippleHeight", 0), ("RippleHeight", "RippleNormal", 0),
             ("RippleNormal", "Material", 4), ("Gloss", "Material", 2)]
    if p["glow"]:
        nodes.append({"name": "GlowRamp", "type": "colorize", "node_position": {"x": 550, "y": -150},
                      "parameters": {"gradient": _grad(p["glow"])}})
        links += [("Normalize", "GlowRamp", 0), ("GlowRamp", "Material", 3)]
    return {"type": "graph", "name": f"liquid_{preset}_{base}", "node_position": {"x": 0, "y": 0},
            "parameters": {}, "nodes": nodes,
            "connections": [{"from": a, "from_port": 0, "to": b, "to_port": t} for a, b, t in links]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("preset", choices=PRESETS)
    ap.add_argument("base", choices=BASES)
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    text = json.dumps(build(a.preset, a.base), indent=1)
    if a.out:
        open(a.out, "w").write(text)
    else:
        print(text)
