# Carrier insert-fit specimens

Issue #89 / parent #66. These small **unpowered fit specimens** are extracted from the current turret carrier and pan-base CAD. They provide a way to record real hole and insert-seating measurements before a larger print. **No specimen has been physically printed or tested.**

| Specimen | What it preserves | Inspection and downloads |
|---|---|---|
| Carrier boss | Local Ø7 boss, nearby outer edge and wiring-window edge; exterior face down, pilot vertical | [STEP](../../exports/turret/carrier-insert-fit/carrier-boss.step) |
| Base anchor | Local anchor rail and foot; foot down, pilot horizontal | [STEP](../../exports/turret/carrier-insert-fit/base-anchor.step) |

<details><summary>STL and geometry-only 3MF downloads</summary>

- [Carrier boss — STL mesh](../../exports/turret/carrier-insert-fit/carrier-boss.stl)
- [Carrier boss — geometry-only 3MF](../../exports/turret/carrier-insert-fit/carrier-boss.3mf)
- [Base anchor — STL mesh](../../exports/turret/carrier-insert-fit/base-anchor.stl)
- [Base anchor — geometry-only 3MF](../../exports/turret/carrier-insert-fit/base-anchor.3mf)

These files have the same print orientation as the corresponding STEP. The 3MF packages contain geometry only; apply and inspect the recipe before slicing.

</details>

Both retain the **nominal Ø4 blind pilot**, 6.5 mm hole depth and 8 mm axial stock. The bore floor leaves 1.5 mm of material. A nominal 5.74 mm insert, seated flush, leaves 0.76 mm between its tip and that floor. These are CAD dimensions, not measured print dimensions. One print orientation cannot qualify the other.

The selected insert is [McMaster 94459A140](https://www.mcmaster.com/94459A140/), M3×0.5. The cached manufacturer specification from 2026-10-26 states 5.7 mm installed length, maximum hole diameter4 mm and minimum material thickness6.5 mm. The normalized manufacturer model is5.74 mm long. The source identity is recorded in the existing [component checklist](../../docs/base-board-component-checklist.md). Private manufacturer CAD is not published in this package.

## Use and record

Download the [blank measurement sheet](../../exports/turret/carrier-insert-fit/measurements.csv) and keep each specimen associated with its row. The plan has three repeats per orientation. This is a small characterization exercise, not statistical qualification.

1. Inspect the original STEP and the print-oriented mesh before slicing. The two shapes deliberately have different layer orientations; do not auto-orient them together.
2. Apply and inspect the parent recipe recorded under `requested_recipe` in the [source/output receipt](../../exports/turret/carrier-insert-fit/receipt.json). The carrier uses the current solid PA6-CF recipe; the anchor uses the current pan-base recipe with 40% gyroid and support enabled. **The 3MF files contain geometry only:** no printer settings, filament profile or G-code. No slicing time or material use has been measured.
3. Record the actual printer, nozzle, filament lot/conditioning, resolved slicer settings and support removal. Verify that the horizontal bore can be cleared of support before attempting insertion. A different support treatment is a changed test condition, not an interchangeable result.
4. Measure the pilot and the actual insert before installation. A qualified operator must establish a controlled heat-setting method and suitable holding fixture; this package does not specify a proven temperature, dwell or installation force. Record those conditions and stop a trial if the specimen cracks, bulges, obstructs the thread or cannot seat correctly.
5. After cooling, record seating depth and visible deformation. Keep photos and failed specimens with the same batch identifiers. Do not infer retention torque or pull strength from successful seating. A loaded-joint acceptance procedure remains separate work.

Small specimens change heat flow, support, cooling and stress relative to complete parts. Their results can identify a poor pilot/process combination; they cannot establish the final assembly's strength, electrical isolation, heat-setting access, service clearance or detailed thread fit. Any pilot correction needs a reviewed CAD change and renewed checks before transfer to the real part.

## Reproduce

Use the reviewed cad-agent v0.4.2 source and the recorded CAD runtime. From a clean committed checkout:

```sh
python research/carrier-insert-fit/generate.py --out /absolute/fresh/output-directory
python research/carrier-insert-fit/verify.py /absolute/fresh/output-directory
```

The generator refuses an existing output directory. It binds all CAD/config/catalog inputs and this study's Python sources, then checks single valid solids, nominal bore/floor witnesses, print orientation, STEP readback against the extracted source, connected watertight STL and 3MF readback. Deliberate blocked-hole, through-hole and wrong-orientation variants must fail. These are digital checks only; the receipt keeps physical measurements empty and readiness false.

After installing a reviewed generated package at `exports/turret/carrier-insert-fit`, `python research/carrier-insert-fit/test_guards.py` checks that changed geometry, changed artifacts, new generation dependencies, extra package files and invented physical qualification are rejected. Runtime/toolkit fingerprints are recorded by generation; the kernel-free freshness guard does not recreate that runtime.
