# Part images

Designed-part thumbnail identity is the assembly-scoped key plus the committed geometry SHA-256. Regenerate with `python tools/part-media-generation.py --render --check`; CI can run its standard-library `--check` mode. The receipt in `catalog/designed-media-validation.json` covers every first-frame body print and current machined/cut-to-order row. Do not choose geometry from neighboring worktrees or by newest filename.

Vendor imagery needs exact product identity, a public source page and a dated verification record, not just a successful HTTP response. Do not show a banner, logo, printed filament sample or another supplier's electronics board as the product. Do not publish ignored/private vendor downloads. Preserve the source link when a verified remote image fails. Shared image keys must not replace one workstream's selected component with another workstream's supplier variant.

See `docs/part-image-provenance.md` for generation settings, scope and limitations.
