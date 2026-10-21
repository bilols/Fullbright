# concrete_green: cracked green concrete floor (image to material)

- **Kind:** image to material
- **Surface:** floor, rough concrete with an olive-green tint, irregular slab cracks
- **Source:** `sources/concrete_green.png` (1024, AI generated, already tiles closely enough to skip `make_tileable`). Brightened at generation time ("+20" in the generation prompt), so `source_gamma` = 1.0.
- **Retro settings:** `render_retro(size=256, dither=0.8)`, Quake palette
- **Status:** accepted 2026-10-21

## Graph

| Node | Type | Role |
|---|---|---|
| `Source` | image | the source picture, straight into albedo |
| `CrackHeight` | colorize | luminance threshold: black below 0.22, white above 0.32. Cracks are the darkest 3-5% of this image; the slab grain sits above 0.28, so it flattens out |
| `CrackSoften` | fast_blur | sigma 4 at 2048, turns the hard mask into a bevel |
| `CrackNormal` | normal_map | strength 1.0, from the softened crack height |
| `Roughness` | colorize | luminance to roughness 0.95 (dark) to 0.75 (light) |
| `CrackAO` | colorize | softened crack height to AO 0.4 to 1.0 |

## What worked

- Building height from a **thresholded crack mask** instead of raw luminance. Raw luminance of a grainy photo-like source gives a normal map that is all noise and hides the cracks.
- **Dither 0.8.** The Quake palette has no muted olive at this brightness; plain snapping turned the floor pinkish brown. Error diffusion averages ramp colors back to the source tint (mean 112,107,73 vs source 113,108,77), and the concrete grain hides the pattern.

## What didn't

- Raw luminance into `normal_map` (first attempt): noise, cracks barely visible.
- Plain palette snap, and hue-weighted snapping: both stayed brown.

## Reuse

Any cracked or tiled hard surface from a source image: retune the two `CrackHeight` thresholds from the source's luminance percentiles (crack pixels are roughly the darkest few percent), and keep dither on if the palette lacks the source's hue.
