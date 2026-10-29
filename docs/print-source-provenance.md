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

## Adversarial packaging review (2026-10-29)

The first review reproduced four failures even though the initial six tests passed: an STL changed between preflight and packaging, an inherited slicer profile changed without invalidating a partial package, nonzero slicer exits were accepted, and bench totals still copied rejected historical aggregates. PR #63 records those findings and their resolution.

Packaging now copies verified STL bytes and retained 3MF bytes into an isolated generation. It checks the original receipts, CAD/context inputs, staged meshes, output hashes and slicing inputs again immediately before publication. Writers use an exclusive lock. Ordinary publication errors restore the previous package and document. A process/host crash between directory renames can leave `exports/turret/print-previous-generation`; the next run stops for explicit recovery rather than deleting that evidence. This is not a multi-file filesystem transaction or protection against arbitrary hostile concurrent writers.

Sliced rows bind the exact inherited profile file hashes, fully resolved and overridden profile JSON, and slicer executable identity. Snap installations additionally bind their installed revision, package manifest and actual Bambu executable, rather than only `/usr/bin/snap`. The command consumes captured profile files; those settings are retained in `print.json`. The executable and installed profiles are checked before and after slicing. Shared libraries, operating-system behavior and physical printer calibration are outside this build-identity boundary. Failed work folders retain logs and settings for diagnosis.

A sliced result requires exit code zero, no reported error, an absent or zero slicer result code, and positive finite mass/time. Bench totals are calculated only from accepted current rows and list their coverage. Rejected rows cannot survive through an old aggregate. `complete` means all planned 3MF rows are present; `slice_complete` separately requires every row to be successfully sliced. `--no-slice` records null totals, and a partial run cannot mix sliced and unsliced generations.

Validation now includes 16 kernel-free adversarial tests plus `tools/test-print-packaging-mesh.py`, a small real STL→3MF round trip using the CAD environment. The latter verifies a 1 mm cube, mutates original and staged inputs to a 2 mm cube, and verifies rejection preserves the previously published files and document. These are packaging tests, not a full turret export, fabrication qualification or a physical printer trial.
