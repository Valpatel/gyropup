# Part images

Designed-part thumbnail identity is the assembly-scoped key plus the committed geometry SHA-256. Regenerate with `python tools/part-media-generation.py --render --check`; CI can run its standard-library `--check` mode. The receipt in `catalog/designed-media-validation.json` covers every first-frame body print and current machined/cut-to-order row. Do not choose geometry from neighboring worktrees or by newest filename.

Vendor imagery needs exact product identity, a public source page and a dated verification record, not just a successful HTTP response. Do not show a banner, logo, printed filament sample or another supplier's electronics board as the product. Do not publish ignored/private vendor downloads. Preserve the source link when a verified remote image fails. Shared image keys must not replace one workstream's selected component with another workstream's supplier variant.

See `docs/part-image-provenance.md` for generation settings, scope and limitations.

Current turret cut parts use their own source-bound inspection export (`tools/export-turret-cut-previews.py`), not the historical whole-robot snapshot. The media checker requires all four unique parts and hashes of both STEP and STL. Rebuild when a dependency hash changes. For dimensional checks, use analytic BREP bounds explicitly excluding triangulation/tolerance expansion; CadQuery bounds queried after tessellation can include deflection. Reopen written STEP/STL and check the appropriate solid/topology/bounds evidence. These checks do not qualify manufacturing or assembly fit. See [the measured bounds incident](../inbox/2026-10-29-tessellated-bounds-are-not-stock-dimensions.md).
