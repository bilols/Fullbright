# Fullbright kit: texture families in code

The kit builds tiling game textures from a short Python description (a
*family*) and delivers them as retro, palette-locked PBR sets. It suits kits
with exact measurements: panel seams on a grid, trim bands on fixed rows,
bolts at set distances, shapes with equal sides. Those are easy to state in
code and fiddly to wire as nodes.

Everything is seamless by construction (noise is shaped in the frequency
domain, blurs and gradients wrap), re-runnable (a family plus a seed always
gives the same pixels), and checked automatically.

## Run it

From an MCP client, the server exposes:

- `kit_build(family, variants="all", bases_dir="")`: build a family's
  variants into `MM_OUTPUT_DIR/art_delivery/<ID>_<variant>/`.
- `kit_deliver_bake(basename, art_id, colours="", kind="four_edge")`: the
  same delivery and checks for a Material Maker 2048 bake.

From Python:

```python
from fullbright import tools
tools.kit_build("output", "EXAMPLE_PANEL_WALL", "R1,R2")
```

Two example families ship with the kit: `EXAMPLE_PANEL_WALL` (painted steel
panels with corner bolts) and `EXAMPLE_DECK_FLOOR` (diamond-plate and stud
deck plates). Copy one to start your own.

## What gets delivered

```
art_delivery/<ID>_<variant>/512/T_<ID>_<variant>_512_BC.png   base colour, palette-locked
                                ..._512_N.png                   normal map, OpenGL / Y+
                                ..._512_MS.png                  R metallic, G AO, B 0, A smoothness
                                ..._512_E.png                   emission mask (only if something glows)
                           /256/...                             the 512 set downsampled
                           <ID>_<variant>_review.png            BC | N | MS | E | offset | tall wall
                           checks/                              offset and tall-wall previews
```

512 px covers one 64-unit tile (8 px per unit). A family on a 128-unit
repeat sets `RES = (1024, 512)` to keep the same density; in the engine its
material then tiles at 0.5.

## The look: the retro finish

`compose.retro_finish` bakes soft shading into the base colour the way
1990s shooters did: upper bevels catch a top-left light, lower ones fall
dark, crevices darken (ambient occlusion), convex edges get a thin
highlight, and a grain about one palette step strong survives the snap as
pixel grit. The delivered normal map is flattened so real engine lights add
to the painted shading instead of doubling it. Hard cast shadows are never
painted.

Base colour then snaps to the Quake palette (fullbright colours excluded),
optionally limited to a list of allowed colours per family (`COLOURS`).
Error-diffusion dither (`DITHER`) suits grainy surfaces; leave it off for
smooth ones.

## Writing a family

A family is a module:

```python
ART_ID = "MY_WALL"
KIND = "wall"          # which checks apply: wall | floor | ceiling | four_edge | trim | single
VARIANTS = {"R1": dict(seed=1, paint="gray"), "R2": dict(seed=2, paint="blue")}
COLOURS = None         # optional: allowed palette hex colours for the base colour
DITHER = 0.5           # optional: a number or {variant: number}
RES = (512, 256)       # optional

def build(variant="R1", size=1024, base_dir=None):
    ...                # return full-size maps: albedo, normal, ao, roughness,
                       # metallic, height, optional emission
```

Build at 1024 or 2048 (multiples of the delivery size); delivery
box-downsamples. Useful pieces:

- `fullbright.compose`: `fft_noise` (seamless noise, stretchable), `blur`,
  `normal_from_height`, `cavity_ao`, `smoothstep`, `wrap_dist` (distance to
  seam lines around the wrap), `tint`, `periodic_rows` (make a band of rows
  wrap on its own), `retro_finish`.
- `fullbright.kit.hardware`: `grid` (pixels per unit and coordinates),
  `seams`, `bolts`, `dome`, `diamond`, `studs`, `grime`, and `finish`, which
  turns a height map, a seam-distance map, a painted mask and a value map into
  finished maps with paint chipped near seams, bare steel, grime and the
  retro finish.
- `fullbright.kit.bases.load_base`: optional grayscale base textures
  (`painted_metal_1.png`, `brushed_metal_1.png`, `grime_1.png`...) from
  `bases_dir`. Missing ones fall back to seamless procedural stand-ins.

## Keeping your families private

Your families do not need to live in this repository. Put them in any
package that exposes a `FAMILIES` dict:

```python
# mypackage/__init__.py
FAMILIES = {"MY_WALL": "mypackage.my_wall"}
```

and point the server at it (environment or `.env`):

```
MM_FAMILY_PATH=C:/path/to/the/folder/that/contains/mypackage
MM_FAMILY_PACKAGES=mypackage
```

`kit_build` then lists and builds your families next to the examples.

## Checks

Every build reports, and draws previews for:

- **Seams:** the jump across each wrap edge against ordinary neighbouring
  pixels (about 1 = invisible; above 1.6 fails). Trims check left/right only,
  plus top/bottom on their bottom-quarter riser band.
- **Wall joints:** a recessed vertical joint at u = 0 and u = 0.5, so a
  45-degree wall that shows 1.5 tiles ends on a joint; and joints that
  survive at the low resolution.
- **Previews:** the tile offset by half (edges meet in the middle) and a
  3 x 12 "tall wall" to judge repetition from a distance.

A false alarm is possible when a strong, intended edge lands exactly on the
wrap line; move the feature a few pixels off the edge.
