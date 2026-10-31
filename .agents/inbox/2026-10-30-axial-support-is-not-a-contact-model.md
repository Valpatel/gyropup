# An axial support screen does not establish lateral load spreading or mounting torque

Investigation: 2026-10-31 UTC (2026-10-30 local), issue #116. The published
RS-04 receipt retains 322 passes, 40 warnings and eight failures over recessed
factory retainers. No engineering failure was waived during this follow-up.

Evidence from released cad-agent `2ad4269` (v0.4.2):

```text
rg -n 'nothing under|stack needs one clean ring' src/cadagent/gates/fasteners.py
83: ... the stack needs one clean ring per angle ...
463: ... nothing under {last} within {gap_tol:g} mm ...
```

The gate probes material along the fastener axis. The existing printed grip is
15.6 mm thick and may distribute force sideways around the small interrupted
sector; the ray screen does not calculate that behavior. Adding a metal washer
or ring also does not, by itself, prove its support or capacity. The current
linear-elastic `cadagent.fea.Study` explicitly excludes contact and bolt preload,
and its default reported stress excludes elements touching support/load patches.
Its ordinary safety-factor result cannot be presented as local bearing or
preload qualification.

The verified RS-04 drawing guarantees 5 mm minimum usable front M4 thread, but
the inspected manual does not establish mounting torque, preload, case-material
bearing capacity or thread pull-out strength. Repository search found an
unqualified 2.5 N m lug instruction in `docs/leg-bench-tests.md` and
`docs/leg-rig-assembly.md`; this follow-up withdraws that instruction and marks
the archived assembly sequence locally.

Corrective rule: state the physical assumption behind each failed screen. Keep
its failure visible while investigating the actual load path with appropriate
contact/preload evidence. Do not improve the reported result by reducing samples,
loosening gap tolerances, filling a real recess with fictitious hardware, or
substituting an unrelated scalar FEA pass. A proposed bridge and its stiffness,
contact, material and tolerance limits require separate evidence. A torque value
requires a source or a qualified measured joint; screw size alone is insufficient.

Limits: this incident does not establish that the current plastic bridge fails
physically, that a metal spreader is necessary, or that either design is accepted.
Unpowered dimensional/contact specimens and loaded mounting acceptance remain
separate. The existing strict receipt tests continue to reject deleted failures
or falsely promoted readiness.
