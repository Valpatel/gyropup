# Part image provenance

The Build portal uses genuine vendor product imagery where verified, and CAD renders for designed parts. A thumbnail is a visual aid, not a claim that a part has been purchased, manufactured, tested or approved for use.

## Designed parts

`tools/part-media-generation.py` resolves sources from the committed body print plan, body/leg/rig made-to-order BOMs and the current turret manifest. It never searches neighboring checkouts or chooses geometry by modification time. Images have assembly-scoped keys (`body/riser`, `rig/carriage_plate`) so similarly named parts cannot silently share unrelated geometry.

Coverage added on 2026-10-29:

- All 13 parts in the body's first-frame print plan, from their original STL files.
- All 13 machined/cut-to-order rows: 10 body sheet parts, the leg output adapter, rig carriage plate and turret pan clamp.
- STEP sources are tessellated directly with CadQuery. The current pan clamp's original STEP is not published, so its image uses the exact hashed STL in the current turret manifest. This is the aluminium clamp, not the older PA6-CF image.

`catalog/designed-media-validation.json` records every source/output SHA-256, renderer versions, tessellation tolerances and view settings. The image records also contain bounds and triangle counts. Material colours aid distinction; they are illustrative rather than calibrated material samples. The view is orthographic and fitted to actual projected vertices with a 12% half-extent margin, so thin plates and tall posts remain fully visible.

Regenerate in an environment with the project's CadQuery/PyVista dependencies:

```sh
python tools/part-media-generation.py --render --check
```

Validate source identity, image bytes/dimensions and current required coverage without CAD dependencies:

```sh
python3 tools/part-media-generation.py --check
```

The generator does not modify any CAD or manufacturing export. The complete 26-part batch is a small render from existing geometry; sustained CAD generation/conversion work follows the compute-host rules in the `cad-remote-runs` skill. The check fails after a source, output or generator changes until the receipt is regenerated. A targeted `--render --only body/post` is diagnostic only and deliberately does not update the shared catalog or receipt.

## Vendor images

Vendor photos are displayed from verified public source URLs; licensed/private downloads under `references/vendor/thumbs/` remain ignored and are not republished. `catalog/vendor-media-verification.json` records the inspected product page, image URL, retrieval evidence, exact-match limitations and unavailable/rejected candidates. A successful HTTP response alone does not prove the image matches a part: logos, banners, printed filament samples and another supplier's board are not substitutes for the requested product photo.

Remote images can change or become unavailable after verification. The portal must preserve the part name and source link when an image fails. Product imagery does not change the selected BOM part, quantity, seller or price. Shared component names require assembly/catalog identity checks before reusing a vendor image across workstreams.
