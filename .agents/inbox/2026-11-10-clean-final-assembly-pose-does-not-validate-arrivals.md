# Validate arrival paths and installed dependencies separately from the final pose

On 2026-11-10, inspection of the Robot Build guide at `33c4464b` found a single
outward 60 mm offset reused for every part in each physical leg. The existing
player installs each named instance in source order while keeping all earlier
instances fixed. Consequently an explanatory explosion became a rigid arrival
through already installed solids. The mesh source is `540056ba4e59`; all inputs
and actual mesh hashes are retained in
[the reproducible report](../plans/assembly-staging/arrival-witnesses.json).

Dated evidence, generated with
`python3 -B .agents/plans/assembly-staging/screen-arrivals.py`:

- Motor arrival through the installed hip: 45/48 sampled surface-interior
  witnesses for left/right, but zero at the final pose. Flipping inward crosses
  the installed cheek instead (57/58 witnesses). Reversing the dependency so the
  hip arrives around the motor has zero witnesses in this bounded pair screen.
- Output screws after the upper links: 55 witnesses on either side; installing
  the screws first and then presenting the links has zero in the reversed pair.
- Wheel washers arriving outward through the hub: 128 witnesses on either side;
  inboard arrival has zero in that bounded pair screen, matching the source's
  inner screw-seat description.
- The inboard knee bearing is obstructed from both directions: 32 witnesses
  through the lower-link shoulder from outside, 96 through the upper knee eye
  from inside. A direction flip alone cannot solve the installed dependency.
- The rigid circlip envelope already has 32 terminal witnesses inside the
  wheel-link mesh. A rigid straight-line arrival cannot represent expansion of
  a real circlip; grouped bought envelopes also limit part-by-part interpretation.

Cause: source membership, clean terminal transforms and visually plausible
explosion directions were treated as sufficient for sequential playback. They do
not establish swept clearance, feasible preassembly, support or fastening access.

Corrective rule: bind actual geometry, installed membership, order and each
arrival path together; reproduce the old order and wrong-side directions as
negative controls. Use the existing CAD insertion/subassembly gates for a core
validation bridge rather than a second planner. Screen against all installed
obstacles before accepting a candidate. Preserve unresolved path/support and
model-fidelity problems in the recipe and evidence; do not report a cosmetic
reordering as a physical build procedure.

Limits: this first regression uses 128 deterministic moving triangle centroids,
21 translations and axial ray parity, with a 0.05 mm interior margin. It reports
odd/edge rays as unknown. Interior witnesses expose sampled penetration; zero
witnesses do not establish collision-free continuous motion or reliable contact.
It does not run exact BREP checks or dynamics, model compliance/press fits,
qualify fixtures, or prove wiring/tool/hand access, loads or safe assembly.

The bounded candidate also screened every installed-obstacle broad-phase pair
for its changed motor/hip, output-screw/upper-link and wheel-fastener arrivals:
72 pairs across both sides. The remaining eight witness pairs are output screws
against motor cases and wheel screws against wheel link/hub; each already has
terminal interior witnesses. These retained envelope/thread contacts require
native or source-model review. They are not silently exempted as acceptable
physical contact, and this result is not a passing assembly gate. The selected
motor/hip, upper-link/output-screw and washer/hub path obstructions have no
witnesses in the candidate's sampled paths.

Before interpreting parity as a mesh interior, the regression now checks exact
STL edge incidence for every actual moving/fixed mesh in this screen: all 42
have closed oriented edges (two oppositely directed uses of each edge, with no
repeated-vertex triangles). An open-face negative fails that prerequisite. This
is a tessellation topology check, not proof of geometric equivalence to BREP,
absence of mesh self-intersection, continuous clearance or physical fit.

The existing real Chrome playback scope additionally captured eight targeted
arrivals across both physical sides, with 16 actual world-mesh vertices each.
[The normalized canonical receipt](../plans/assembly-staging/browser-playback.json)
preserves all 128 vertex deltas, original report/harness hashes and exact
candidate guide/model/instruction/171-mesh correspondence. Its worst translation
delta error is `2.08e-17 m` under the unchanged `1e-7 m` check. The build preceded
the candidate commit and records base `33c4464b`; the receipt preserves that
version alongside the measured staged-payload correspondence to `86514707`.
It is not immutable candidate-version or full both-engine acceptance. The
separate targeted poses have numeric vertex observations, not dedicated PNGs.
The original owned ephemeral listener closed after browser teardown. Use
`node .agents/plans/assembly-staging/run-playback-check.mjs` to repeat the same
existing harness against a fresh isolated build, preserving source/version
identity and closing its test listener in `finally`.
