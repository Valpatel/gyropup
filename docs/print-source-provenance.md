# Print artifacts must match their source

The old print plan selected `flywheel_tyre_d34.stl` while the newer CAD selected a Ø38 tyre. Partial reruns also kept old rows without checking which geometry produced them. Neither filename existence nor an old slicer time establishes a coherent kit.

`cad/turret_print.py` now consumes the canonical `flywheel_tyre.stl`, which `cad/turret.py` generates through its selected `PRINT_AS` shape. It requires a `print-meshes.json` receipt beside each source STL. The turret and stand exporters write those receipts only after export, and reject inputs that changed while exporting.

The receipts bind:

- Every Python/JSON file under `cad`, `catalog` and `designs`, conservatively, plus the effective optional `GYROPUP_CAD_PARAMS` file hash.
- The selected design file, including a project-local trial outside the standard folders.
- Installed CAD/kernel/numpy package versions and the actual cad-agent Python sources.
- Every exported print mesh's filename and SHA-256, with the generating Git revision as additional context.

No private file contents or external absolute paths are published. These are the current generators' declared input boundary. A future generator that reads another file must register it with `context_snapshot`; this helper does not discover arbitrary runtime file reads or prove the CAD models themselves correct.

Generate geometry with the normal turret and stand exporters before packaging. Legacy exports without receipts are rejected. A full package rebuild uses fresh rows; `--only` validates every retained row's source identity, recipe and 3MF bytes before writing anything. A partial first build is explicitly marked partial. Changed or unbound retained rows require a full rebuild. Bench BOM generation drops stale slicer measurements rather than attaching them to new geometry.

Geometry identity is separate from readiness. Receipts and generated print documentation explicitly leave mechanical/physical acceptance unqualified. Known assembly, wall, structural, hardware and measurement blockers in [mechanical readiness](mechanical-readiness.md) still apply. No new full kit or slicing result has been released by adding this guard.

Run `python3 tools/test-print-provenance.py` for source/catalogue changes, missing receipts, changed meshes, changes during export, nonstandard selected designs, mixed partial packages and stale slicer reuse. Those tests exercise packaging decisions; they do not run a CAD solve, slicer or physical print.
