# liquid_kit: tintable liquids from grayscale caustic bases

- **Kind:** image to material, generated. `kit.py <preset> <base>` builds the graph; render with `render_retro(size=256)`, no dither.
- **Bases:** the three grayscale sources from `sources/liquids/`, seam-fixed with `make_seamless` (see `../liquids/`). They were made as overlay bases, not finished liquids.
- **Status:** 5 presets x 3 bases rendered 2026-10-21. Overview: `output/retro/liquid_kit_overview.png`.

## How it works

| Node | Type | Role |
|---|---|---|
| `Source` | image | grayscale caustic base |
| `Normalize` | colorize | stretches the base's 1st-99.5th luminance percentile to 0-1, so one preset lands the same way on every base |
| `LiquidRamp` | colorize | the preset's surface colors, by normalized brightness (cells dark, veins bright) |
| `GlowRamp` | colorize | optional emission ramp into Material port 3; black where nothing glows |
| `RippleHeight` / `RippleNormal` | fast_blur, normal_map | soft ripple relief, strength per preset |
| `Gloss` | uniform_greyscale | roughness per preset (must be a node, or no ORM map is exported) |

## Bases

| Base | Look | lo / hi |
|---|---|---|
| contrast1 | fine, wispy caustics on near-black | 0.063 / 0.647 |
| contrast2 | bold, clean veins; the most Quake-like | 0.447 / 0.933 |
| grey | busy, grainy, low contrast | 0.408 / 0.733 |

## Presets

| Preset | Glow | Roughness | Normal | Notes |
|---|---|---|---|---|
| water | none | 0.15 | 0.35 | dark slate-blue cells, lavender veins |
| lava | veins only, fire ramp | 0.6 | 0.35 | dark red crust; veins above 0.4 glow b7330f to f7d38b |
| slime | none | 0.25 | 0.35 | gray-green; no green fullbrights exist, so it can't glow (Quake's slime didn't either) |
| tar | none | 0.35 | 0.6 | near black, faint veins, stronger relief |
| energy | everything | 0.2 | 0.2 | light-blue cells, white veins; only 4 colors because the palette has just three light-blue fullbrights plus white |

## What worked

- Normalizing each base first, so presets are base-independent.
- Picking ramp colors from (or near) the Quake palette, so the snap doesn't shift hue.

## What didn't

- First slime ramp ran too yellow: the palette's brightest yellow-greens are olives. Moving the top stops toward the gray-green ramp (6f837b family) fixed it.

## Adding a liquid

Add a preset to `PRESETS` in `kit.py`. For glow, use fullbright colors only: fire ramp (2b0000 ... f7d38b), reds (8b0000 ... ff0000), light blues (7fbfff, abe7ff, d7ffff), white. Possible next ones: dark-cell energy (only veins glow), fire-colored energy, blood, sewage.
