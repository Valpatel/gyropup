# A material-data change: rescale the stress, re-run for the design

On 2026-11-01, issue #29 re-ran the FEA records on cad-agent v0.6.0. That release's humid PA6-CF and 6061-T6 data
lowered the strengths (x0.833 along the layers, x0.788 across, x0.874 for 6061) and the PA6-CF moduli (x0.343,
x0.203). cad-agent #197 had projected the effect by multiplying each recorded SF by the strength ratio.

What the re-run showed:

- **The rescale itself is exact here.** Every study in these records is one material under force loads, so its stress
  field does not depend on E. The checks were run at one revision on one host, under v0.4.2 and under v0.6.0. All 10
  `cad/studies.py` studies gave the same meshes and the same design stress. So did all 26 `cad/leg_studies.py`
  studies and their load shares. Only the SF (by the strength ratio) and the deflection (by the modulus ratio) moved
  (`research/fea-v060-29/evidence/`). Today's leg passes every target on v0.4.2 and misses 7 on v0.6.0.
- **The record is not today's design.** The leg record predates #134's frame and knee, and several turret parts
  changed after their record was made (turret stress ratio 0.57 to 1.13 on the same host and mesh). A rescale of the
  record answers a question about a part that no longer exists.
- **The projection read a stale checkout.** #197's counts reproduce only from a `main` checkout at `a79e48c`, whose
  turret record had 22 studies. Dev's has 28.
- **A verdict that is not the gate SF moves differently.** The turret judges printed parts on a layer-aware SF.
  Below target on that verdict went from 1 case to 9. The isotropic gate SF alone showed 2.

Corrective rule:

- When a toolkit's material data change, re-run the records on the host and mesher that made them, at today's
  revision. To separate the design's drift from the data's change, run the old toolkit at the same revision too.
- A rescale is only as good as a control run showing the stress field is unchanged. A study with contact, preload,
  mixed materials or a displacement load needs the re-run.
- A downstream-impact claim names the project revision and the record files it read.
- Report the verdict each record actually judges on, not only its gate column.
