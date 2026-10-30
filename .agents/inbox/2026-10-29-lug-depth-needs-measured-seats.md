# A plausible engagement comment cannot replace measured screw seats

On 2026-10-30 06:29 UTC (2026-10-29 local), independent recovery of Gyropup
`fa1b5ee` found that the RS-04 lug screw comments disagreed with the generated stack.
The incoming-motor preparation is tracked in #116 / PR #117.

## Evidence

`sed -n '805,830p' cad/fivebar.py` showed `LUG_CB = 11.0` beside a claim of 4.9 mm
engagement. `screw_groups()` seats M4×20 screws at `Y['frame'][1] - LUG_CB`.
The actual frame interval is `[-25.1,-1.0]`: seat −12, tip −32, mounting face −25.1,
hence **6.9 mm penetration**, not 4.9. `cad/rig_bench.py` used a 14 mm plate, giving
6 mm penetration. `catalog/interfaces.json` records only 5 mm guaranteed usable
front thread. The cached manufacturer PDF page 10 was visually checked against it.

The STEP's 7 mm drilled cylinders are not usable-thread evidence. The normalized
McMaster 91290A168 screw was inspected: tip −20, under-head face 0, head Ø7 × 4.
Private files remain untracked; the bounded report records their hashes.

Reading `coupon_frame_ring()` found another mismatch: a 14 mm bearing-seat ring
with no counterbores, despite its docstring claiming the parent motor mounting
geometry. Its print orientation also differed from `build_leg.ROT['hip_frame']`.
The apparently simple proposal to thicken the whole dyno plate would intersect
the rotating Ø90 hub disc; local raised head seats and a front relief avoid that
new defect.

## Cause and corrective rule

Separate hand-maintained comments, stack arithmetic and simplified coupons drifted
from actual seats. Measure the placed manufacturer's screw and actual parent CAD
using cad-agent fastener tools, then apply the drawing's usable-depth constraint
separately. A modeled drill hole may be deeper than the guaranteed thread. Include
negative controls using the previous defective geometry. Never convert geometry
exceptions into clearance.

Clip fit specimens from their parent where practical, preserve the parent's layer
orientation, and test their actual seats. Review neighboring moving envelopes
before moving a mounting surface. Source-bound reports must reject missing check
members and changed artifacts as well as failed checks.

## Limits

Four millimetres engagement and 0.5 mm nominal reserve are screening assumptions,
not thread-strength or production tolerances. Measure the real screw, printed
grip and motor interface before assembly. This correction does not qualify the
whole motor assembly, driver access after links are installed, frame strength,
physical fits, preload, cable routing or powered operation.
