# Leg rig: the design, section by section

The single-leg test rig (milestone M3) broken into its seven sections. For each section this page gives:

- what the section has to do, with numbers;
- where it meets its neighbours;
- every part in it, what it is made of and how it is held;
- why it is that way and not another;
- what checks it.

Coordinates are the rig's: x forward, y outwards (the leg and the wheel at +y), z up, with the origin on the deck's top
under the hip axis. At a hip height zh the leg's own frame sits at (0, 0, zh).

The numbers come from:

- the CAD: `cad/rig_parts.py`, `cad/build_rig.py`, and `cad/rig_hardware.py` for the bought parts and the screw table;
- the checks: `exports/rig/rig.json` and `exports/rig/integrity.json`.

The review pictures are in `exports/rig/views/` (`cad/rig_views.py`):

- `rig-solid.png` and `rig-solid-back.png`: the whole rig;
- `rig-section.png`: through the right rail;
- `rig-section-plan.png`: 30 mm above the hip;
- `rig-exploded.png`;
- `carriage-front.png`, `carriage-back.png` and `carriage-section.png`.

**The integrity checks** (`cad/rig_integrity.py`, run at the end of `cad/build_rig.py`, which fails if they fail) hold for every
section:

1. **Nothing floats.** The fixed rig, the carriage with the leg's frame, and the leg's links are each one connected group of
   parts. Parts count as joined when they touch, or when a screw in the joint table holds them. The carriage meets the
   rig only at its four blocks on the two rails (each 0.3 mm clear, the balls' gap).
2. **Nothing interferes** at 22 poses:
   - the carriage from its bumpers to the top stop, with the leg folded and stretched;
   - the leg's range on the deck at -20, 0 and +20 deg of lean.

   Every overlap over 1 mm³ fails, except the leg model's own fits (`LEG_OVERLAPS`, listed there with a reason each)
   and screw threads in holes drawn without their threads.
3. **Every screw fits its stack.** For each of the 86 screws, the length under the head is checked against the stack it
   clamps:
   - at least 0.8 d of steel thread engaged (an ISO nut's height), or the whole of a drop-in nut thinner than that;
   - 5 mm in the frame's M5 inserts;
   - the tip clear of whatever is behind the thread.

**Assumptions to check on arrival.** The 8-series slot data is not from a maker's drawing yet:

| Item | Assumed | Used for |
|---|---|---|
| Slot lip | 3.0 mm | the wall a drop-in nut pulls against |
| Drop-in nut thread length | M4 4, M6 5, M8 6 mm | the screws' engagement |
| Room behind a nut | 3 mm | where a screw's tip may go |
| HGH15CA threads | M4 x 5 deep (HIWIN) | the block screws |

Measure them on the first parts that arrive. If the lip is over 3.1 mm, the rails' M4 x 16 go to M4 x 20 (check that
they don't bottom).

## 1. Frame and rail

**What it does.** It holds the leg upright on a vertical slide that carries half the robot. That is 14.75 kg now and
16.25 kg after the stops review.

- Travel: from the carriage on its bumpers (hip 226 mm above the deck) to the jump's apex (593 mm on D65's bus, 631 at
  54 V), with at least 150 mm to spare under the top stop. The stop is at 811 mm.
- Stiffness: the slide must not let the hip sway more than 1 mm in a landing.
- Strength: the worst landing (3.4 kN on the tyre) must leave SF 2 or more everywhere.

**Interfaces.**

- The post's front face (y = -116.65) carries the rails. The rails' blocks carry the carriage plate (its back face at y
  = -88.65).
- The deck's top is the datum, z = 0. The deck sits on the base's members; their tops are at z = -18.
- The tyre lands on the deck over the wheel member (y +104.6).

**Parts.**

| Part | Material, process | Held by |
|---|---|---|
| Post, 8080, 1200 mm | 6063-T5 extrusion, MISUMI, cut to length | 4 cast corner brackets at its foot (2 per side face), on the 4080 member |
| Post member, 4080, 620 mm, flat | extrusion | between the sides, 1 corner bracket each end (its front face lies against the bumper member) |
| Sides, 4040, 900 mm; front, wheel, bumper and rear members, 4040, 620 mm | extrusion | corner brackets on every free vertical face of each joint (16 in all, their own M8 screws and drop-in nuts) |
| Brace, 4040, 720 mm, 60.4 deg | extrusion | free-angle brackets: on the post's back face 668 mm up, on the rear member's top |
| Rails, HGR15, 1000 mm x 2, at x = +-20 | hardened steel, bought kit | M4 x 16 at every 60 mm hole into drop-in nuts in the post's front slots (17 each) |
| Deck, 600 x 400 x 18 | sanded plywood, cut by the store, drilled 6.6 mm at the screws | 8 x M6 x 30 and 18 mm washers into the members' top slots |
| Rubber mat | bought | under the base |

**Decisions.**

| Decision | Why | Rejected |
|---|---|---|
| One 8080 post with a brace, behind the leg | the leg's front and sides stay open for the camera and hands; the brace takes the landing's moment (post at 15.5 MPa, SF 9.3, 0.37 mm of sway) | two posts or a gantry (in the way of the leg); an unbraced post (2.3 mm of sway) |
| HGR15 profile rails on the post's slot centres | no play, a known load rating (C0 16.97 kN, worst block 2.1 kN: SF 8 or more), 250 mm between the blocks against the leg's pitch moment | V-wheels on the extrusion (play, wear on aluminium); round shafts and bushings (play, cost) |
| A 4040 ladder base on the floor | it is a stable 900 x 700 footprint at a few dollars a metre; the deck spans it | a steel plate base (heavy, not instant-priced at this size) |
| Plywood deck | the tyre lands on wood much like a floor; it is cheap and screwed down at 8 points clear of the landing | an aluminium deck (cost; ringing under impacts) |

**Checks.**

- rig.json:
  - blocks: worst 2.13 kN, SF 8 on C0;
  - post: 15.5 MPa unbraced worst case, SF 9.3;
  - travel: the blocks stay on the rails at both ends; the apex is 218 mm under the top stop.
- Integrity: the frame is one group; no overlaps; every rail, deck and bracket screw fits its stack.
- On arrival: square the base by its diagonals (to 1 mm), plumb the post, and run each block along its rail by hand.

## 2. Carriage and plate

**What it does.** It carries the leg's hip frame, the ballast and the ToF target up and down the rails as one rigid
body. The 6.35 mm plate takes the leg's forces from the frame's six inserts into the four blocks.

**Interfaces.**

- The plate's front face is the hip frame's mount plane (y = -82.3, `fivebar.frame_mounts()`).
- Its back face sits on the four blocks at (+-20, +-125) from the hip axis.
- Its bottom edge strikes the bumpers. Its top edge strikes the top stop.

**Parts.**

| Part | Material, process | Held by |
|---|---|---|
| Carriage plate, 300 x 320 x 6.35 | 6061-T6, SendCutSend from the DXF or STEP; every hole a clearance hole, deburred | the four blocks |
| HGH15CA blocks x 4 | bought (the rail kit) | 16 x M4 x 10 from the plate's front into their M4 x 5 threads (3.65 mm engaged, 0.91 d) |
| Ballast posts x 2 (1 in x 6 in shaft, tapped 3/8-16 both ends) | steel, McMaster | 3/8-16 x 1 in and a plain washer from the plate's front at (+-138, 40) |
| Ballast spacers x 2 (Ø40 x 9) | PETG, printed | on each post against the plate |
| ToF target arm | PETG, printed, white | 2 x M4 x 10 from the plate's back into its heat-set inserts |

**Decisions.**

| Decision | Why | Rejected |
|---|---|---|
| A 1/4 in 6061 plate from SendCutSend | flat and stiff (1.6 kg); every hole located from the CAD; instant-priced (D40) | a printed plate (too soft at the blocks); 3/8 in (heavier, more cost for no need) |
| Every hole a clearance hole | no operations to order; the threads are in the blocks, the shafts and the frame's inserts | tapped holes (an operation, and aluminium threads) |
| Ballast posts at (+-138, 40) | the motors' rear covers sit 2 mm in front of the plate, so a head at the old (125, 20) hit them. Out here a 14.3 mm head and a 20.6 mm washer clear the Ø120 covers, and the hole keeps a 6.75 mm web to the edge (SendCutSend asks for the thickness) | countersunk screws flush with the plate (a countersink operation); posts inside the plate's outline (heads in the covers' way) |
| A spacer under the first weight plate | the plates (Ø129.5) reach the heads of the frame's outer M5s on the plate's back; 9 mm of spacer clears the head and its washer | lowering the posts (puts the front heads back into the motors' covers) |

**Checks.**

- The plate's webs are each 6.35 mm or more (rig.json: carriage_plate).
- The DXF is re-imported and checked against the hole table.
- Integrity: the carriage is one group; the blocks are 0.3 mm from their rails; the 16 block screws and the ballast and
  arm screws fit their stacks; no overlaps over the whole travel.

## 3. Leg mount

**What it does.** It bolts the leg's printed hip frame to the plate exactly as the robot's body will: through the same
six M5 heat-set inserts at the same mount plane. The rig then tests the leg's own joint, not a fixture's.

**Interfaces.**

- `fivebar.frame_mounts()`: plane y = -82.3; inserts at x 0 and +-83, z +-70, axis along y.
- The motors' leads leave their rear covers 6-19 mm in front of the mount plane and pass straight back through two
  slots in the plate (32 x 22, at the grommets' clocking).

**Parts.** Six M5 x 16 with M5 washers from the plate's back, into the frame's inserts. The stack is the washer (1 mm)
and the plate (6.35), which leaves 7.9 mm in the insert and 2.35 mm of room past it.

**Decisions.**

| Decision | Why | Rejected |
|---|---|---|
| The body's own six inserts | the leg on the rig is the leg on the robot | an adapter plate (a different joint from the robot's) |
| Screws from the plate's back | the inserts face the plate | through-bolts with nuts inside the frame (no room, no access) |
| **The upper half goes onto the plate on the bench, before the carriage goes on the rails** | the two centre M5s (x = 0) sit right behind the post once the carriage is on the rails: no key reaches them. The assembly order is changed to match (`docs/leg-rig-assembly.md` steps 9-10) | assembling it on the rig (impossible); only four screws (gives up a third of the joint) |
| Lead slots straight behind the grommets | between the frame's flanges the leads cannot turn | routing round the plate's edge (the leads are 310 mm) |

**Checks.** Integrity: the frame's six screws fit (7.9 mm in the inserts); the hip frame touches the plate; the leg's
static parts are one group with the carriage. The clearance sweep in rig.json finds no pair closer than 10 mm over 27
poses.

## 4. Stops and catch

**What it does.** It catches the carriage whenever the leg cannot.

- Bottom bumpers: a power cut while standing is 7 J at 0.95 m/s. A fault at the jump's apex is up to 33 J. Either must
  stop in 25 mm of crush with nothing broken.
- Top stop: catches the carriage before the blocks run off the rails' top ends.
- Drop-test pin, for S4.
- Tethers: hold the carriage and the leg in a hardware failure.

**Interfaces.**

- The plate's bottom edge meets the bumper caps when the leg is 140 mm long (contact at z 65.65). The bumpers are
  crushed at 115 mm. The leg's own stops are at 101.5 mm.
- The plate's top edge meets the top stop's TPU at z 971: the rails' top less 30 mm. The blocks are still 25 mm inside
  the rails when it is crushed.

**Parts.**

| Part | Material, process | Held by |
|---|---|---|
| Bumper bases x 2 | PETG, printed, 40 % gyroid | 2 x M6 x 35 each from the pocket's floor, through the deck into the bumper member's slot. The holes sit 11 mm behind the base's centre: the slot runs there, under the plate's edge |
| Bumper TPU blocks x 4 (two below, two in the top stop) | TPU 95A, 30 % gyroid (R0 sets the infill) | in their pockets and cups |
| Bumper caps x 2 | PETG, 100 % | over each TPU block |
| Top stop bracket | PETG, printed | 4 x M8 x 16 into drop-in nuts in the post's front slots above the rails (6 mm under each head) |
| Drop bracket (S4 only) | PETG, printed | 2 x M8 x 16 into the post's side slots |
| Slings, carabiners | bought | girth-hitched round the post |

**Decisions.**

| Decision | Why | Rejected |
|---|---|---|
| Printed TPU gyroid blocks | crush stiffness is set by the infill (0.26 MPa plateau at 30 %), so R0 tunes them on the rig itself | rubber feet (too stiff in 25 mm); springs (they give the energy back); a dashpot (cost) |
| The top stop on the post above the rails | the rails' own end caps are not rated for a carriage; the bracket's T-nuts slide in from the post's top | stops clamped on the rails (they would mark the raceways) |

**Checks.**

- rig.json bumpers: 6.9 J and a mean of 137 N per bumper in the S5 cut. R0 drops the carriage at 7, 15 and 33 J.
- Integrity: the bumper screws land on the member's slot. A screw off the slot would hit solid aluminium and show as an
  overlap, because the T-groove is modelled.

## 5. Load path and weights

**What it does.** It carries the design mass with the leg, so that what the leg feels is what it will feel under the
robot. It also takes every landing into the floor.

- The design mass is 14.75 kg now and 16.25 kg after the stops review.
- The carriage's own parts are 3.90 kg; the leg's frame group is 4.03 kg and its moving parts 4.95 kg.
- The ballast makes up the rest: one 2.5 lb plate per post at 14.75 kg (2.7 % over: no trim washers are bought), and a
  2.5 lb and a 1.25 lb per post at 16.25 kg.

**The path.**

1. The tyre and the wheel link.
2. The knees and the apex.
3. The upper links and the motors' outputs, through the machined adapters and the 61812s.
4. The hip frame.
5. Six M5 inserts into the plate.
6. Sixteen M4 screws into four blocks.
7. Two rails.
8. 34 M4 screws and drop-in nuts into the post.
9. The post's corner brackets and the brace.
10. The base, and the floor.

The plates are retained by a 2 in washer and a 3/8-16 x 3/4 in screw in each post's end (16 mm in its 19 mm thread).

**Decisions.**

| Decision | Why | Rejected |
|---|---|---|
| Standard 1 in cast-iron plates on steel shafts | they come in 1.25 and 2.5 lb steps, so the 11-16 kg sweep is a change of plates | a fixed steel stack (one mass only) |
| Posts behind the plate | the mass sits close to the blocks; nothing in front of the leg | weights on the leg's side (they would load the frame unlike the robot) |

**Checks.** rig.json: the mass table and the ballast table, block loads and post stresses; the landing's loads come from
`sim/leg_rig.py`'s rig results.

## 6. Electronics pod and wiring

**What it does.** It powers the motors from Gyropup's own bus and makes the power hold-to-run. D65's bus is two DeWalt
DCB609s in 20 V mode in series: 10S, 30-41 V.

- Hold-to-run: the contactor is closed only while the pendant is held, and opens 1.0 s after it is released.
- It hosts the CAN adapter and the rig node.
- The supervisor's window: it limps above 45 V or under a 26 V floor, and sits down under 32 V averaged.

**Interfaces.**

- The pod hangs on the post's back face, 120 mm above the deck, beside the brace's line, on 4 x M8 x 16 through 6 mm
  pads into the post's back slots.
- Its panel faces -x: the pair's XT60 inlet, the motors' XT60 outlet, the 12 V fuse and the pendant's jack.
- The pendant's clip sits on its -y wall.

**Parts.**

| Part | Material, process | Held by |
|---|---|---|
| Pod and its lid (140 x 200 x 230) | PETG, printed | 4 x M8 x 16 through its pads, which are 6 mm thick so the tips stay out of the groove's bottom |
| Contactor (TE LEV100), off-delay relay, Class CC fuse, 12 V DC-DC, U2C, Feather | bought | M4 heat-set inserts, a printed top-hat rail, a pocket, bosses |
| Two 20 V dock adapters in series | bought (Amazon) | on the bench beside the rig, their leads to the pair's XT60 |
| Pendant clip | PETG | 2 x M4 x 10 into the pod's inserts, below and above its cup, where a key reaches them |

**Decisions.**

| Decision | Why | Rejected |
|---|---|---|
| The robot's own two packs (D65) | the rig tests the bus the robot will have; there is no third voltage to manage | the old 60 V mode (a fresh pack sits at the RS-04's 60 V fault); a bench supply for motion (it cannot sink regeneration) |
| The pod on the post's back | the ballast plates sweep the post's sides | a commercial box (mounting and cutouts by hand) |
| A timed relay holding the contactor | the hardware cut happens whatever the software does | a pendant switching the coil directly (it has no current rating) |

**Checks.**

- `docs/leg-rig-wiring.md`: every wire has its gauge and both ends.
- `rig/tests`: the supervisor's aborts at the new window.
- Integrity: the pod's and the clip's screws fit their stacks.
- `docs/leg-rig-safety.md`: the session checklist.

## 7. Bench fixtures

**What it does.** It measures what the simulation assumes, before the leg runs:

- B1: the power-off drag;
- B2: the rotor inertia;
- B3: the stop sleeve's rate;
- B4: the inserts' and the link screws' preload;
- the coupons: the print offsets of every seat.

**Parts** (`exports/rig/bench/`, `cad/rig_bench.py`).

- **The dyno:** two printed lug plates on a plywood board (8 x M6 x 40 with lock nuts), two hubs on the leg's M5 x 25,
  and a TPU spider.
- **The press cage** (PETG) with:
  - the 500 kg S-type cell (Phidgets 3140_0) hung on an M12 x 30;
  - for B4: PA6-CF pullers on an M12 x 75 stud, with M5 or M8 inserts and keyed by wings against the walls; bearing
    discs;
  - for B3: an M12 x 80 press bolt through a base nut, a slider, the sleeve block and the anvil.
- **The coupons:** PA6-CF, at -0.1, 0 and +0.1 mm.

**Decisions.**

| Decision | Why | Rejected |
|---|---|---|
| A printed cage round the load cell | it keeps the cell on the screw's axis and needs no vise or press; one frame serves B3 and B4 | a through-hole load washer (none with a listed price found); a vise (the cell would sit off-axis) |
| B5 on the rig, with the motors as the press | the real wheel on its real hub, the load plate as the truth, no 400 mm press frame | a tyre cradle in a press (it does not fit the bed) |
| A 500 kg cell | B4 needs past 2.4 kN | the 200 kg TAS501 (rated 1.96 kN) |

**Checks.** `exports/rig/bench/bench.json` holds the cage's stack heights and screw reaches. Every fixture is a valid
single solid that fits the bed. The tests in `rig/tests/test_bench.py` cover the scripts.

## What this review changed

| Finding | Fix |
|---|---|
| The ballast screws' heads would have hit the motors' rear covers (2 mm in front of the plate) | posts moved to (+-138, 40) |
| The weight plates sat on the frame's M5 heads | a 9 mm printed spacer on each post |
| The bumpers' screws missed the bumper member's slot by 11 mm | holes moved over the slot |
| The two centre M5s of the leg mount cannot be reached on the rig | the upper half goes on the plate on the bench (assembly steps 9-10) |
| The pod's 4 mm wall let its M8 tips reach the groove's bottom | 6 mm pads |
| The pendant clip's lower screw sat behind its own cup, and the clip had nothing to screw into | screws below and above the cup, 2 heat-set inserts in the pod |
| The ToF arm's screws had nothing to thread into | 2 heat-set inserts in bosses |
| The ToF mount's screw heads hit its seat | holes moved out, base widened |
| The deck had no screw holes in the model | drilled 6.6 mm at the 12 screws |
| The rails, blocks and brace hinges were drawn as plain boxes overlapping each other | the HGR15 profile with counterbores, HGH15CA blocks with their channel, free-angle brackets |
| Only 20 corner brackets have room (two joints are faces against each other) | 20 plus 4 spares in the order |
