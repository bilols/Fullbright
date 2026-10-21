# liquids: caustic-cell water, murk and tar (image to material, batch of 12)

- **Kind:** image to material, one shared graph (`liquid.ptex`), image path and gloss swapped per liquid
- **Sources:** `sources/liquids/*.gen.png`, 1024, AI generated, gamma already fixed (`source_gamma` 1.0). Not seamless: wrap seams measured 2.3-4.4x the normal neighbour-pixel jump.
- **Seam fix:** `make_seamless(band=0.15)` to `sources/liquids/tiled/`. Seams came down to 0.8-1.7 before rendering, and 0.8-1.4 in the final 256 albedos.
- **Retro:** `render_retro(size=256)`, Quake palette, **no dither**
- **Status:** rendered 2026-10-21, awaiting review

## Graph (`liquid.ptex`)

| Node | Type | Role |
|---|---|---|
| `Source` | image | tiled source, straight into albedo |
| `RippleHeight` | fast_blur | sigma 6 at 2048: soft height from the bright caustic lines |
| `RippleNormal` | normal_map | strength 0.35: gentle ripples, not bumps |
| `Gloss` | uniform_greyscale | roughness, see table. Must be a node: a bare roughness number on the Material node exports no ORM map, and the retro step then falls back to 0.8 (matte) |

| Liquid | Gloss (roughness) | Colors used |
|---|---|---|
| waterblu1, waterblu2, waterteal1, waterpink1, watergrey, watercontrast1, watercontrast2 | 0.15 | 7-25 |
| watermurk1, watermurk2, watermurk3, waterbrwn1 | 0.30 | 13-22 |
| lava_tar02 | 0.40 | 66 |

## What worked

- Half-offset crossfade for seams: the only method that kept caustic lines continuous across the wrap (compared against Material Maker's `make_tileable` and a periodic-plus-smooth decomposition).
- Low normal strength (0.35) from blurred luminance: reads as surface ripple.

## What didn't

- **Dither on smooth liquids.** The Quake palette has nothing near the saturated blue-violet of waterblu1/2 or the teal of waterteal1, only grayish lavenders. Full-strength dither restores the hue only by sprinkling pure blue pixels (screen-door look); weak or neighbour-limited dither changes nothing. Plain snap goes slate, which is closer to how Quake water actually looked. Keep dither for grainy surfaces (concrete, rock, dirt).
- Roughness as a Material parameter instead of a node (see Gloss above).

## Open questions

- Are `watercontrast1`, `watercontrast2` and `watergrey` finished liquids or overlay/caustic masks? They're rendered as liquids for now.
- `lava_tar02` has no glow. If it should, it needs an emission mask (for example its bright specks) wired to the Material's emission input.
