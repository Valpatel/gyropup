# Withdraw unsupported assembly instructions in their generator too

On 2026-10-31 UTC, a follow-up search after correcting the public assembly page
found that its generator still wrote the withdrawn RS-04 lug torque and old
counterbore depth:

```text
rg -n '10 mm|counterbore|2\.5' cad/rig_assembly.py
92: ... heads 10 mm down ...
93: ... the counterbores; 2.5 N m ...
260: ... Motor lugs ... | 2.5 N m |
```

The page had been corrected, but a normal regeneration would erase the warning
and restore those instructions. The generator now keeps the unqualified status,
links current mounting/fit evidence, preserves the bounded pre-link tool-access
order, and leaves lug tightening torque unestablished.

`python3 tools/test-rs04-lug-stacks.py --pure` runs the actual Markdown writer and
its actual motor-step prose in a temporary directory without importing CAD or
overwriting historical images. The regression rejects a missing warning or
restored motor-lug torque/depth instruction. Sixteen controls run; the one actual
receipt check is intentionally deferred in pure mode until fresh CAD evidence.

Corrective rule: follow a generated instruction back to its producer when
withdrawing a dimension, torque or qualification claim. Check both the direct
public document and a subsequent generation. Keep source-bound evidence strict;
this CAD-directory source edit requires fresh receipts even though it changes
prose rather than solids. Do not re-sign prior reports.

Limits: this change supplies no torque, preload, physical fit or full-rig
qualification. Other historical joint instructions remain subject to their own
evidence and the page's unreleased status.
