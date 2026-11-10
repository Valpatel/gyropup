# Preserve original CAD bytes before validating playback

Status on 2026-11-10: genuine collection261 and the one-time pure original-byte
binding are complete and independently accepted for their stated input/identity
scope. The canonical [collection and binding checkpoint](native-261/README.md)
retains both execution identities, archive/member seals, original byte bindings,
author observations, independent receipts and a portable pure audit. No
validation BREP read-back/frame/path query or physical acceptance is claimed.

The original-byte binder at `011a29b6fe1ddf4a6726fa01f59d710cbf1d6757`
received independent source review; its exact tree merged into core dev at
`d24f4cf7b567278d7d93ed1779ebba6ca087aae6`. Actual binding used the immutable011
source pin. The separate core progress/frame-preflight follow-up requires its
own reviewed pin before the next native run. PR279's educational recipe and
PR280 remain held for that bounded evidence; no native gate pass is assumed.

The existing CAD collector intentionally requires its recorded toolkit
`e662a1ce79b4f63f7352b9d065c5027f77d53a81` and runtime. Keep that boundary.
Its optional `--emit-brep` calls the existing `shape_brep_text` on each original
collected worldshape immediately after exporting that shape's STL. It retains
the exact BREP bytes, raw and source-content hashes, world-frame identity
placement and producer hash platform. No shape is repaired, fused, renamed or
reconstructed to make validation pass. Default collector behavior and all
source/runtime/hardware guards remain in place.

Run this only through the established detached compute collection wrapper:

```text
python -I -B tools/site/assembly/run_robot_collection.py \
  --contract-json <reviewed-private-runtime-contract> \
  --source <pushed-source-commit> --emit-brep
```

Before dispatch, record the compute role, pushed source, actual command, resource
budget, log, done marker and collection instructions in issue276. Verify existing
runtime/toolkit fingerprints and host load; do not mutate a shared environment.
The existing worker's 4-CPU/phase/whole-run bounds and 512 MiB archive limit remain
unchanged. A budget or invalid-shape failure is evidence to retain and inspect.
Do not raise limits or reinterpret a failed run as successful collection.

After successful source-bound collection and generation, use a separate exact,
clean, reviewed core checkout for `robot_native_playback.py`. The pure binder
accepts original payload bytes; it must not reserialize a BREP read-back to
identify the producer's shape. Its `producer_hash_platform` comes from the
original receipt, independently of the consumer's platform.

```text
python -I -B tools/site/assembly/robot_native_playback.py \
  --collection <candidate>/collection.json --guides-root <generated-guides> \
  --guide robot-wip-<collection-revision>/guide.json \
  --guide combined-wip-<collection-revision>/guide.json \
  --toolkit <reviewed-core-checkout> --toolkit-revision <reviewed-core-commit> \
  --out <fresh-binding-output>
```

The consumer checks exact collection/mesh/source coverage and original BREP
identity/placement, then saves captured guide/model/mesh bytes, original BREP
payloads, bindings and its own source receipt. Binding alone executes no native
insertion query and is not a passing gate. Run explicit `--validate` separately
on the compute host under a recorded outer time/memory bound, preserving the
input bundle even if the native run stops. It calls the existing core
`playback_gate`, filters the reference overview exactly as the product does,
and retains per-guide verdicts. Any failing/undecided verdict returns exit1;
a binding/parse/native error must also remain failed.

The initial native result is expected to expose issues, including the existing
rigid circlip and grouped fastener/model contacts. Preserve the failures and
investigate them rather than adding implied-overlap exemptions. The core gate
checks declared finite rigid paths through its existing conservative advancement
and near-contact native queries; it does not prove continuous clearance,
gravity/support, fixtures, deformation, press fits, fastener engagement, tool or
hand access, wiring, loads or a physical assembly procedure.


The dedicated consumer controls also expose an optional real-core pure interface
preflight. With the exact clean reviewed core checkout above, all five dedicated
tests passed on 2026-11-10 in 0.170 seconds, including the real
`bind_inputs -> bind_playback_breps` call. The inputs are explicitly synthetic
non-CAD/non-STL bytes with string platform metadata; this verifies interface,
captured input hashes and original-byte/platform preservation only. It performs
no native query and is not robot geometry evidence.

```text
ROBOT_PLAYBACK_TOOLKIT=<reviewed-core-checkout> \
ROBOT_PLAYBACK_TOOLKIT_REVISION=011a29b6fe1ddf4a6726fa01f59d710cbf1d6757 \
python3 -B -m unittest discover -s tests/site/assembly -p test_robot_native_playback.py
```


Independent CLI review at product `55c7e815` exposed a failed real three-box gate
whose report said `pass=false/status=fail` while the CLI returned exit0. The
entry point now raises `SystemExit(main())`. Ordinary CI exercises a complete
CLI subprocess with an explicitly failed dependency double and checks exit1,
failed reports and preserved inputs; this double proves no CAD behavior.
The additional real three-box native subprocess control is explicitly enabled
with `ROBOT_PLAYBACK_NATIVE=1` alongside the reviewed core variables above and
an existing compatible native dependency environment. It must return exit1 with
its actual failed report preserved. These controls validate failure propagation,
not Gyropup insertion or physical assembly acceptance.


Actual job261 ran the reviewed producer at
`e5b3089277448e5ae3d546fc36c549a62949856b`: collection130.774s and generation1.222s,
normal exit0, both child groups gone and all five preservation guards true.
All233 fresh STL byte hashes exactly equal the retained540 snapshot; the95 CAD
inputs, hardware tree and both guides' actual operation/state/offset/camera/text
records also match. This explicit correspondence does not relabel either source
or automatically grant manufacturing-original approval.

The reviewed pure binding completed once with two171/233-instance bindings,
233 original BREP files, their original aarch64 platform and all captured mesh
bytes preserved. It wrote no native reports. The current e5 adapter's
`--validate` entry is regression-tested, but a potentially long full robot path
run must wait for separately reviewed native frame preflight and recoverable
per-pair/per-operation progress. Inspect actual changed-arrival and old-order/
wrong-side controls; preserve known terminal, knee, circlip and support unknowns
without inferring acceptable overlaps or requiring a fictitious whole-robot pass.

## Prepared native frame and progress protocol

The thin consumer now separates binding-only, `--preflight-only` and `--validate`
modes. Native modes require the reviewed core `preflight_only` / `on_progress`
interface; the original011 core remains usable for pure binding. The distinct
`assembly-playback-preflight` report must declare `paths_checked=false`.
A successful frame preflight is not a clearance verdict. The new protocol's
nine dedicated controls, including the small real three-box native fixture,
passed against independently reviewed core
`5c29c9e2abf2562baa72a05248f23de054b8241e`. The genuine233-instance frame-only
attempt262 stopped at an input permission comparison before any core checkout
or native query; retain its [failure checkpoint](native-262/README.md).
The documented post-job freeze changes producer0600 modes to retained0640.
A successor must separately bind a fresh reviewed source/packet, require that
exact transition with unchanged member/byte seals, and preserve complete actual
before/after inventories. No product frame or path pass is assumed.

Every requested native guide gets an exclusive `progress/<snapshot>.jsonl` and
`reports/<snapshot>.phase.json` before native work. JSONL envelopes retain the
guide/binding hashes, native source, core revision, mode, sequence and checking
wall time, plus the core's immutable event snapshot. Every record is flushed;
file fsync is requested every 128 records, after completed operations/preflight,
and at normal close. Phase receipts distinguish `progress_flushed_records` from
`progress_fsync_acknowledged_records`. A writer failure conservatively preserves
the last acknowledged fsync boundary and marks the tail uncertain; existing
flushed bytes do not certify the tail. These are recorded file operations, not
an assurance of hardware/power-loss durability.

Starting/completed load, world-bound and frame events expose where a preflight
stops. Pair/operation events preserve completed witnesses during a later path
sweep. A finished collision verdict can have a complete phase with gate_pass=false;
invalid inputs, interrupted work or progress-storage failure remain incomplete.
A killed process may leave only a running phase and an observed JSONL prefix;
absence of terminal evidence must never be interpreted as completion. Reports
and aggregate rows are written per guide, retaining earlier completed results.

`--max-samples` exposes only the existing core's per-pair cap, in 1..5000; an
exhausted budget remains unchecked. Time/memory/CPU/disk bounds belong to the
separately reviewed detached command. The ordinary tests use an explicit failed
non-CAD dependency double through the real CLI, verify distinct preflight and
path routing, incomplete serialization/storage behavior and fsync uncertainty.
The small real three-box control must be repeated with the final reviewed core
before a genuine 233-part native preflight. No new planner, repair, overlap
exemption, tolerance waiver or dependency installation is introduced.
