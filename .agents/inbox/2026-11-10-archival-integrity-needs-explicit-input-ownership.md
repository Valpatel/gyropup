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
