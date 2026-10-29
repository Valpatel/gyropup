# Cached tessellation bounds are not sheet-stock dimensions

2026-10-29 UTC, mechanical integration issue61 / PR63. While replacing four missing turret cut-part previews, a source-bound export exited successfully but its independent STEP/STL readback check rejected the recorded stock thickness.

## Evidence

On the isolated CAD compute environment, CadQuery2.8.0 / cadquery-ocp7.9.3.1.1:

```text
source 59ababbd5e66b7fb3b1a99284f66303827067d5a
python tools/export-turret-cut-previews.py
RUN-DONE rc=0
pan_clamp after STL export: z=[46.988912367729576, 50.18608763227042]
recorded thickness=3.197175264540844 mm; declared sheet stock=3.175 mm
independent cq.importers.importStep(...).val().BoundingBox(): z=[47.0, 50.175]
```

The initial receipt was not committed. Its exporter queried `solid.BoundingBox()` after STL generation populated the shape's triangulation cache. These bounds included tessellation deflection rather than just the analytic faces. The geometry itself had not become thicker.

The corrected exporter at `9d5e53c7b5c1177fc262c20aebe81227605135b6` asks `BRepBndLib.AddOptimal_s(solid.wrapped, bounds, False, False)` for analytic BREP bounds, without triangulation or shape-tolerance expansion. The same bounded four-part command completed with:

```text
pan_clamp BREP z=[47.0, 50.175], stock=3.175 mm
cradle_plate_l BREP y=[53.61, 56.785], stock=3.175 mm
cradle_plate_r BREP y=[-56.785, -53.61], stock=3.175 mm
stop_lug BREP y=[-59.325, -56.785], stock=2.54 mm
largest STEP bounds error: 6.424e-12 mm
largest STEP volume error: 4.030e-10 mm^3
largest STL bounds error: 0.011090 mm (export tolerance 0.08 mm)
all four STEP files: valid single solid
all four STL files: watertight, consistent winding, one connected component
RUN-DONE rc=0
```

Exact inputs, output hashes, stock, bounds and readback results live in `exports/turret/component-preview/manifest.json`. The source snapshot includes the exporter and files read at module import, checked before those imports and again after generation.

## Corrective rule and limits

Use explicitly chosen BREP bounds for dimensional checks. Do not mistake tessellation/cache-dependent viewer bounds for fabrication dimensions. Keep mesh bounds separate and compare them with a stated discretization tolerance. Reopen the files actually written before recording export success; the bounded exporter now enforces stock thickness, STEP solid/bounds/volume agreement and STL topology/bounds on every run.

These checks cover serialization and these four plate models only. Equal bounds and volume are not a general proof of geometric equivalence. They do not verify tolerances, hole fits, load capacity, assembled motion, tool access or safe operation. The previews remain WIP authored inspection geometry, not released manufacturing files or proof that the historical whole-robot snapshot is current. Any dependency hash change requires regeneration.
