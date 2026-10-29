# A successful image URL does not establish part identity

On 2026-10-29 UTC, the Build portal's image catalogue listed render and vendor entries, but the body's first-frame parts and machined rows had missing images. Existing names could also point outside this repository or at the wrong material/version.

Receipt from the source audit:

```text
python3: catalog/images.json['pan_clamp']
source_url: gyropup-turret/exports/turret/pan_clamp.stl
material: pa6-cf
python3: exports/turret/turret.json['sheet']['pan_clamp']
material: 6061-T6 aluminium
step: exports/turret/pan_clamp.step (not published)
```

The old crawler considered a fetchable URL useful even when it was a banner; the old renderer searched adjacent checkouts and picked the newest matching filename. Neither establishes the identity of the current BOM part. Private/ignored vendor thumbnails also do not survive the public static builder.

The correction uses assembly-scoped keys, committed source geometry and SHA-256 receipts. The current clamp uses the published manifest's exact hashed STL. Vendor imagery needs a matching product page and visual inspection; unavailable images remain honest source links rather than invented product photographs. Do not silently substitute a different seller's board under a shared sensor name.

Validation receipt:

```text
python3 tools/part-media-generation.py --check
PASS: 26 exact-source thumbnails; 13 body prints and 13 machined/cut parts.
```

The rule is encoded by that check and documented in `docs/part-image-provenance.md`. Limits: matching geometry hashes does not validate manufacturability or physical safety; a remote product image can change after its recorded verification date. Historical renders outside the new scoped coverage are not retroactively certified.
