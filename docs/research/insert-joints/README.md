# Insert and clamped-plastic joints

Issue [#137](https://github.com/Valpatel/gyropup/issues/137), with
[#133](https://github.com/Valpatel/gyropup/issues/133) (notes that disagree with the checked joints). It feeds
[cad-agent #230](https://github.com/Valpatel/cad-agent/issues/230), which adds general insert and limiter checks to
the toolkit.

**This is a screen, not a qualification.** Nothing here has been printed, installed, torqued or pulled. The pull-out
capacities are scaled from published M3 tests, and the bearing limits are the repository's own creep screens. Each
number shows where it came from. The bench tests (B4: insert pull-out and bearing creep) and the fit specimens
(`research/carrier-insert-fit/`) decide.

- [joints.md](joints.md): the table, the findings and a note for each joint, generated.
- [joints.json](joints.json): the same, with every source line it read (`bindings`).
- `inventory.py` writes both; `test_inventory.py` checks them (CI: the mechanism suite).

```sh
python3 research/insert-joints/inventory.py            # regenerate after a bound source changes
python3 research/insert-joints/inventory.py --check    # exit 1 when joints.json / joints.md are stale
python3 research/insert-joints/test_inventory.py       # the checks, kernel-free
python3 research/insert-joints/inventory.py --cad-agent ../cad-agent/src   # optional: the same sums through cadagent
```

## Phase 2: the joints through cad-agent

`phase2.py` runs `joints.json` through cad-agent v0.18.2's insert and limiter checks and sets each result beside this
inventory's figure. The output is [phase2.md](phase2.md) and `phase2.json`, with a tolerance for each check and a
reason for each disagreement. Of 271 comparisons on 41 joints, 203 agree. The main differences:

- The toolkit wants every pilot 0.2-0.3 mm over the maker's hole.
- The PETG pull-out figures here are 1.08-1.27 x the toolkit's high end.
- On the toolkit's low end, scaled to this inventory's PA6-CF basis, the TM riser's pull-out margin is 1.58, not 2.34.
- The wheel bolts' 1.8 N m is over the toolkit's 1.18 N m on their DIN 433 washer. At 1.18 N m the preload does not
  assure the 1331 N the flange needs: an owner decision.
- The toolkit caps 14 joints at 0.14-0.44 N m, where a printed part is clamped on the insert's end.

```sh
python3 research/insert-joints/phase2.py --cad-agent PATH   # regenerate (a cad-agent checkout at v0.18.2)
python3 research/insert-joints/phase2.py --check            # exit 1 when stale against joints.json or the generator
python3 research/insert-joints/test_phase2.py               # the checks, toolkit-free (CI: the mechanism suite)
```

## What it covers

Every joint where a screw goes into a heat-set insert, and every printed part that metal clamps. That is the legs,
the body (P3, from `exports/body/integrity.json`), the turret, and the bench furniture: the stand, the
J501 box and the leg rig. Each joint records:

- the insert, its pilot (diameter, depth, blind or through), the boss around it, and the part's material and infill;
- the insert axis against the layers, and which side the screw comes from;
- where the screw tip ends against the pilot's floor, and how much thread engages;
- what the screw clamps, whether plastic is in that clamp, and whether anything limits the crush;
- the torque the documents give, the preload it makes, and the load from the repository's own studies.

The body's insert joints are read from the body's joint check, so a new body insert joint the generator does not
know fails the generator. Elsewhere, the generator reads each pilot and boss, and most stack numbers, by pattern from
the line that cuts them. A turret pilot is read from its own `insert_hole()` call, with `INSERT_DEPTH` only as the default. A
pattern binds every line it matches, and they must agree. Screw lengths come from the BOM where it has a line of its
own. When a bound line changes, generation stops and names the line.

Some numbers are not modelled anywhere the generator can read: a few screw lengths in shared BOM groups or code
comments, panel thicknesses, standard washer sizes and the estimated loads. Each joint lists them under **Typed into the generator**
in `joints.md` (`typed` in `joints.json`). A change to one of them is not noticed. Fix findings are conditional on
the bound values, so a fix applied to the CAD clears its finding at the next regeneration.

## Method

| Check | Rule | Source |
|---|---|---|
| Pilot diameter | at most the maker's maximum hole; reported if over 0.25 mm under it | McMaster 94459A tables (`catalog/`) |
| Blind pilot depth | at least the insert length; noted when under insert + 2 pitches (room for displaced melt) | Spirol, *How to design the proper hole for heat/ultrasonic inserts* |
| Screw tip | must stop short of a blind pilot's floor; a screw that bottoms jacks the insert out instead of clamping | Spirol; `cadagent.mechanical.fasteners.blind_insert_stack` |
| Engagement | at least 1.2 d of thread into an insert | `cad/body_joints.py` `ENGAGE['insert']` |
| Boss | diameter at least 2 x the insert's (Spirol: 2 to 3 x) | Spirol |
| Orientation | an insert axis lying in the layer plane opens the layer bonds through the axis (noted) | CNC Kitchen, Spirol |
| Mating hole | the clamped part's hole smaller than the insert, so it bears on the brass | Spirol (jack-out) |
| Pull-out | knurl shear: tau x pi x hole x length. Tau is 16.3 MPa from CNC Kitchen's M3 x 5.7 test in PETG (119 kgf). PA6-CF uses the humid across-layer strength ratio (10.5 MPa). The repository's own estimates win when lower. | [CNC Kitchen, PETG](https://www.cnckitchen.com/blog/helicoils-threaded-insets-and-embedded-nuts-in-3d-prints-strength-amp-strength-assessment), [PLA](https://www.cnckitchen.com/blog/threaded-inserts-for-3d-prints-cheap-vs-expensive), [hole size](https://www.cnckitchen.com/blog/are-our-heat-set-insert-datasheets-wrong) |
| Preload | F = T / (K d), K = 0.2 when the condition is not stated | `cadagent.formulas.screws.preload_from_torque` |
| Printed clamp | head pressure against 25 MPa sustained and 40 MPa humid | `cad/studies.py` `JOINT` |

Levels: **fix** is a clear correction (a wrong depth, a screw that bottoms, a note that disagrees with the checked
joint). **owner** is a design trade with its numbers. **check** is an assembly or qualification step. **note** is
recorded and needs no action unless the duty changes.

## Limits

- The pull-out scaling assumes failure by shear along the knurl in solid material. Parts with 40 % (or 20 %) gyroid
  inside a few walls are not covered by the 100 % tests (pan base, compute tray, the stand).
- Loads marked *estimate* are this inventory's own rough figures for light-duty joints. The rest come from
  `exports/body/leg-loads.json`, `exports/leg/fea/summary.json` and the turret's hand checks.
- The hip-frame row tension treats the flange as rigid (M / (3 x 140 mm)). The wheel bolt tension takes the moment
  about the flange's centre. Neither is a contact or preload model.
- The TM bolts' 30 g load is taken about the TM face, which is the pan base's foot again since D76 (frame T's origin;
  D66's plinth put the face 86 mm lower): the centre's height from `mount.json` `com_mm`, checked against
  `frame_t_above_face_mm` and `envelope.lowest_z_mm`.
- `--cad-agent` places the screw from the stack's geometry (head seat and screw length) where a joint records it
  (`stack`). Elsewhere it is given this inventory's own tip depth, so it re-checks only the subtraction.
- Nothing here changes the CAD. Fixes that need `cad/` or `catalog/` edits are listed for a CAD-host regeneration.
  Those directories are hashed whole by the five carrier receipts.
