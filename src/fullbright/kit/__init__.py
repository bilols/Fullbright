"""Fullbright kit: build tiling texture families in code and deliver them as
retro, palette-locked PBR sets.

- compose (fullbright.compose): seamless noise, blur, normals, AO, and the
  retro finish (soft shading baked into the base colour).
- bases: load optional grayscale base textures, with a procedural fallback.
- hardware: reusable shapes (bolts, seams, diamond plate, studs) and a
  paint-over-steel surface finish.
- deliver: full-size maps -> palette-snapped BC / N / MS / E files at two sizes.
- checks: seam, joint and repetition checks plus review sheets.
- registry: finds family modules (built-in examples and your own packages).

A family is a module with ART_ID, KIND, VARIANTS and build(variant, size,
base_dir) returning full-size maps; see docs/KIT.md.
"""
