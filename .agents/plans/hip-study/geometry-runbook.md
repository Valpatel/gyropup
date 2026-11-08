# One whole-foot geometry collection

This is the actual issue #8 design experiment in PR265, not a tool-only release.
Build the frozen retained HIP baseline (zero foot radius) and the source-default
candidate (3.5 mm) in separate processes with the existing hip-frame-study.py
geometry-only mode. Compare their finished BREP solids, actual mounting/pilot
measurements, unchanged body/bed criteria, retained material, bounded foot
additions and motor clearances. Exercise the three actual finished-shape faults.
No FEA, engineering-export adoption, strength result or physical qualification.

Use the already-reviewed retained v0.6.0 runtime read-only for comparability;
no installs, upgrades or shared-environment changes. The exact private RS04 STEP
is SHA256 92859a1e85a8846881432e193c808fe03a3da49ac18ad201c2d89de1746b9082
(8,675,109 bytes), retained as 43 solids; never use the envelope fallback or
redistribute that input. Staging copies only this existing input into the owned
run, outside the checkout and output archive. The old accepted topology remains
diagnostic reference at source2251f009; it is not new candidate qualification.

The frozen public operator is submit-foot-geometry-once.py. Exact selector,
OS-user runtime paths and input-cache path live in a private configuration.
Require its/source/config hashes, independent source/native-plan review, fresh
cpu-a capacity (load <=8, >=32GiB available), no competing allocation, and a new
exclusive fsynced receipt. Four actual affinity CPUs, 24GiB address space,
600s per native phase, 1800s outer wall and 8GiB owned scratch remain bounded.
One detached SSH bootstrap/launch only; uncertainty stops, never auto-repeat.

Recover the exact relative owned run from the issue launch checkpoint. Completion
requires exit.done, outer-group-state.json and every owned phase group gone.
Collect out/ plus bootstrap/run/done/group logs with ordinary rsync after
quiescence. geometry.tgz and its seal/inventory preserve all partial results.
Before any use, independently verify the actual source/private-input/runtime
before-after identities, output hashes and geometry findings. Keep baseline
failures and SF1.60<2.00 explicit. FEA requires a separate exact reviewed plan
after the real geometry/interfaces justify it.

## Retained first construction failure

The first source `6c373e51` run is FAILED: baseline built and passed body/bed;
candidate failed at the 3.5 mm OCP fillet before a candidate/comparison existed.
See [sealed failure proof](whole-foot-attempt1-failure.json). A corrected local
construction keeps 3.5 mm and every finished interface/clearance check; any new
run needs a distinct exclusive output/receipt and the same bounded procedure.

The local-material continuation at `c90caf86` also failed at 3.5 mm. Its own proof
and failed local/back BREP fixture remain separate from a valid candidate.
The retained `fault_diagnostic` configuration selected ONLY the existing
`--diagnose-foot` saved-shape inspection (60s native phase), under the unchanged
outer runtime/source/process/scratch guards. It imports the sealed owned local
BREP, uniquely rebinds all five saved edges at CadQuery representation tolerance,
and calls OCP at the same 3.5 mm to collect contours/faults. No baseline/candidate
rebuild, private manufacturer CAD import, FEA, result adoption or physical
acceptance occurs in this mode. The fresh shoulder experiment removes that selector for a separately reviewed
actual construction experiment.

## Real shoulder candidate

The candidate retains the 3.5 mm blend and adds a 4 mm offset / 3.5 mm deep
local supporting shoulder, including an explicit unqualified 0.5 mm land.
Fillet the complete source polygon foot before its motor cut; retain only the
rounded shoulder addition after restoring the original 66 mm cut. Keep the
old motor round and protected 62.5 mm void. The independent finished-addition
region explicitly includes this shoulder. The normal three genuine phases
and all existing finished-solid/interface/manufacturer/fault checks apply.
No geometry success, strength improvement or physical qualification is implied.

## Saved rejoin diagnosis and source-object reuse

The current `rejoin_diagnostic` selector runs only a 120-second saved-shape
study through the same bounded collector/runtime. It checks seven sealed
operands, recomputes subtraction stages, and reports two finite join orders.
There is no baseline rebuild, product build, FEA or finished-candidate adoption.
Only after those facts justify a construction correction should the normal
finished geometry/interface/manufacturer comparison run again. Baseline reuse
with its original provenance is not implemented or silently substituted.

Bootstrap uses an explicitly pinned completed owned source donor with
`git clone --shared --dissociate --no-checkout`, then public origin/exact
target fetch/checkout, connectivity and no-alternates checks. It records donor
Git state before/after and keeps its original directories. New output/HOME
and checkout are isolated; the retained runtime remains read-only. Source
object reuse never substitutes an old geometry or engineering result.
