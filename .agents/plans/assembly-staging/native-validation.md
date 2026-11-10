# Preserve original CAD bytes before validating playback

Status on 2026-11-10: optional producer/consumer source prepared; no new native
robot collection, exact playback run or physical acceptance is claimed. This
follow-up depends on Gyropup PR279 and the independently reviewed core API in
[cad-agent PR513](https://github.com/Valpatel/cad-agent/pull/513). The original-byte binder at `011a29b6fe1ddf4a6726fa01f59d710cbf1d6757`
received independent source review; ordinary core CI/merge remain separate.
Native producer source review and retained-runtime preflight remain required
before a long robot run.

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
