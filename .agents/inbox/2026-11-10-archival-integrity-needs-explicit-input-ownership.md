# Historical integrity and current geometry need separate complete bindings

On 2026-11-10, PR287's retained-fit CI failed with `Source/context closure
changed` in [run42866125306/job130005097895](https://github.com/Valpatel/gyropup/actions/runs/42866125306/job/130005097895).
The unchanged lug receipt binds94 CAD/config inputs plus2 context files.
Eleven body/test inputs changed; unchanged leg source and80 collected leg
mesh hashes alone do not make the full old receipt current.

Independent [design review](https://github.com/Valpatel/gyropup/issues/193#issuecomment-6775808908)
accepted an explicit historical-integrity contract plus a separately measured
current hip correspondence contract. The matching input snapshot is
`f77fcde00880d4cedf8ca1a7edabd993714deaca`; it is not asserted to be the
slice execution revision `017e1e03eacdfaec7eda891a14143a2f9254581a`.

The implementation's bounded offline DATA snapshot contains exactly96 public
input files,2,997,841 raw bytes. `retained_fit_history.captured_inputs` verifies
fixed reviewed anchors and exact membership, materializes only verified data
in a temporary root, and calls the unchanged current strict validator against
the actual archived artifacts. Historical code never executes. The explicit
full verifier runs the unchanged packager with that input root; it preserves
322pass/40warn/8fail and false readiness. Default current-root validation
still rejects the old closure. No original receipt/output is restamped.

Evidence: `python tests/hardware/manufacturing/test_retained_fit_history.py`
exercises the actual receipt, source/context mutations, readiness/failure
negatives, bounded parser and cleanup. With the original pinned lightweight
toolkit/runtime, `verify-retained-fit-history.py` completed the full actual
geometry/archive/profile/G-code/metric verification with
`historical_archive_integrity:true,engineering_pass:false`. No CAD/slicing ran.

Corrective rule: name the input root and evidence scope explicitly. A changed
current closure must keep failing its default guard. Preserve a complete
historical positive and current-stale negative, and require independently
accepted actual current mesh-to-original correspondence before restoring a
current Prepare action. Never use a caught current failure as a fallback to
old evidence, or let a mutable manifest certify its own expected hashes.

Limits: current correspondence implementation/measurement/adoption and browser
acceptance remain separate review gates. Archive integrity does not establish
current body fit, adapter retention, support strength, physical printing or
the truth of a new measurement. The known engineering failures remain failures.

## Recorded current correspondence and consumer follow-through

The [independent artifact review](https://github.com/Valpatel/gyropup/issues/193#issuecomment-6776726093)
accepted the exact56.5317s current measurement. Its producer, sampler and
historical validator stayed unchanged when a separate acceptance record and
authority anchors were populated. The actual current mapper/exporter then
enabled exactly L/Rhip geometry preparation; changed input membership, source,
mesh, original, proof or acceptance disabled it and unrelated parts stayed
pending. No current-source exception or historical fallback was introduced.

On source520505f5, `WORKSPACE_CASE=print PRINT_CASE=current` ran in Chrome
and WebKit against an isolated current guide candidate. Both actual hip
Prepare actions downloaded the unchanged original STL and geometry-only3MF;
strict readbacks checked units, topology, original pose and generic-bed bounds.
Corrupt project bytes exposed no3MF download. All contexts/listeners closed.
The [canonical consumer record](../plans/end-packs/current-print-consumer-checks.json)
retains hashes, scope and actual readback values without private test URLs.
Public guide adoption and joint CI ownership still require independent review.

## Ordinary consumer tests must transfer the exact assertion ownership

After separately accepted266 collection, proof and233-guide readback, the current
cache and guides were adopted without regenerating geometry or historical assets.
CI source now assigns the dated complete archive to
`test_retained_fit_history.py --full` and `verify-retained-fit-history.py`, with
the original v0.4.2 helper pin. The original default current-root checker and
packager must still reject the stale source closure. The protected lug test's
existing `--pure` invocation transfers only its one dated committed-receipt
assertion to that mandatory full job;15 original controls still run. The checker,
context test, archive helper, receipt, producer and sampler bytes stay unchanged.

Author verification on2026-11-10: full historical tests10PASS in7.485s, including
the genuine archive positive and default-current stale negatives; actual adopted
`test_robot_current_print_match.py --collection-folder software/site/assets/robot-current`
6PASS in1.753s with0skips. Ordinary robot discovery64PASS in21.795s has7 optional
tests skipped; it does not replace that explicit mandatory actual-current command.
Both browser Print engines now have explicit `PRINT_CASE=current` invocations,
because the existing `PRINT_CASE=all` branch does not execute that current case.
Those final composed browser runs and source/CI acceptance remain pending.

The same ownership error affected historical arrival tests: regenerating a540
screen with the new end-pack recipe raised `KeyError: end_pack_holder_front`.
The original screen producer/report stay unchanged. Its test now fixes the old
report hash and recomputes all recorded22 cases and72 candidate pairs against
their actual bound archived triangles using the unchanged pure screen. Current
leg-order controls remain separate. Historical guide checks preserve all old
artifact hashes; the current233-output reproduction uses the adopted266 cache.
Neither test relabels an old source closure as current or executes historical code.

The accepted five-row candidate used escaped JSON Unicode for the middot in
titles, while the existing Turret producer checks its literal UTF-8 encoding.
The original `7e8a51f3` receipt remains immutable; only the public index was
canonicalized through the unchanged producer's existing `snapshot_index` encoder.
The [formatting correction](../plans/end-packs/guide-adoption/index-formatting-correction.json)
records both digests and exact parsed equality, including row order, old three
rows and unavailable entries. `export_turret_guide.py --check` now passes all60
original outputs without a new checker or any regenerated guide/model bytes.
