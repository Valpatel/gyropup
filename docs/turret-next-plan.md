# Turret next plan: the cradle, the Rev 0.9 box, and the road onto the robot

Written 2026-10-27 by the planner (Fable 5.1) for the next turret implementer (Opus), from a read of main ab5b263 (the
v0 package: docs/turret-prototype-plan.md T0-T5 and T7-T9 done, the order sheets, the print files, the FEA, the wiring
as reviewed under D47, the firmware and its simulated bench) and of the J501 project's working tree (~/Code/j501-agx,
read only). The rules stand: the barrel never points above level (the hard stop); at most 70 fps, held by the fixed
12 V flywheel rail; nothing spins or feeds unless the safety line is held; parts off the shelf with a listed price,
printed, or ordered online at an instant price (D40). Scratch work for this page (the cradle FEA re-read, its pictures)
is in /mnt/storage-10tb/claude-scratch/gyropup/turret-planner/.

Section 4 is the task list; every task names its files, its acceptance check and an estimate, and **API** marks a task
that changes `cad/turret.py`'s `Turret(L)`, `.posed()`, `.meta` or `.bought` (names, frames or envelopes), because
`cad/build.py`, `sim/robot_v2.py`, `cad/build_turret_box.py`, `cad/turret_assembly.py`, `cad/turret_motion.py`,
`cad/turret_lidar.py`, `cad/turret_studies.py`, `cad/turret_print.py` and `tools/part_images.py` build on it. Section 5
makes the five open decisions (D48-D52) so nothing waits on the user.

## 0. In one paragraph

The v0 package can be ordered today as it stands (125 lines, 17 sellers, $1,609.89 with the stand and the tools, every
line priced with a second seller) and 12 of its 19 printed parts can go on the printer today. One part must change
before it is printed: the **cradle**. Re-reading its three failing FEA cases by stress direction shows that no print
orientation saves it (flat 0.73, on its side 0.57, on its tail 0.67 in the sideways fall; the push case reaches 1.13
at best against 2.0), and that the weak spot in the everyday push is the root of the hard-stop lug, which is the part that keeps
the barrel from being pushed above level. So the cradle becomes a printed PA6-CF rail frame with two laser-cut
6061-T6 cheek plates from SendCutSend, in the same cart as the pan clamp (D48): the across-layer load paths disappear,
the hard stop is an aluminium lug loaded in its own plane, and the bench turret stays the robot turret. The J501 box adapter is
rebuilt on the box's Rev 0.9 parameters (the tower cooler, the flush fan grille 20 mm further forward, the roof 5 mm
higher); its intake shroud keeps the same idea with a wider collar. For the robot the turret gives the body one
interface file (the TM pattern, the foot, the DT12 plug's side and sweep, the harness, the mass and centre of mass,
the lidar scene) and gets back a riser, a 24 V branch, a CAN port and a dry STOP contact; the turret-side work is a
host bridge for the Jetson, the robot CONFIG rows, the robot harness and the lidar table at the body's lidar position.
Two open hardware questions are closed by cheap insurance: the backup ESC pair with documented eRPM telemetry goes in
the first order (D51), and the gate comparator's alternate resistors go in with it.

## 1. Review: what is ready today and what must change

### 1.1 Ready to order today

| Item | State | Evidence |
|---|---|---|
| Every bought part priced, with a buy link and a second seller | `not_in_a_catalogue`, `no_listed_price`, `no_second_source` all empty; 125 lines, 17 sellers, $1,609.89 in whole packs; the servos and the X2216s first (Waveshare ships from China) | exports/turret/bench/bom.json, exports/turret/bench/orders/README.md |
| The one custom part | the pan clamp, 6061-T6 0.125 in, instant price on upload | exports/turret/pan_clamp.dxf |
| Wiring, reviewed | the arm chain on 3.3 V, the 555 on the pendant loop's 12 V, the brake FETs to ground, the set-only trip latch, every part with a designator; the pendant on a keyed mini-XLR | docs/turret-wiring.md, D47 |
| Firmware and its bench host | 19 firmware tests pass; 33 of 33 simulated bench tests pass | docs/turret-firmware.md section 7 |
| Physics | the ceiling 67.6 fps at the worst corner on Ø34 (2.3 under the cap); 52 fps at 8,855 rpm; 3 balls/s; the brake before a dropped ball | docs/turret-physics.md sections 3-5 |

Add to the first order (task N3): the Lumenier Razor Pro F4 45A pair (D51) and the gate pull-up alternates (bench test
3.10). Nothing else changes in the sheets.

### 1.2 Ready to print today, and what waits

From docs/turret-print.md (19 parts, 1,291 g, 50.1 h on one P1S):

- **Print now:** stand_box, stand_bottom (PETG, 10.9 h); pan_base, pan_ring, pan_spacer, pan_pinion, ring_driver
  (PA6-CF, 11.2 h); board_bay, laser_mount, barrel, hopper, hopper_lid (PETG, 5.0 h). None of these depends on a
  part in hand or on an open decision.
- **Wait for a part in hand:** ring_carrier (the ROB-13065's flange holes are assumed: measure, then print, plan T6);
  cartridge_body, flywheel hubs, dial, tyres (the X2216 and a servo checked against the drawings, bench test 1.8).
- **Wait for a design change:** the cradle (section 1.3) and, because the cradle's new stop lug asks the yoke's stop
  sectors to reach 0.5 mm further, the tilt_yoke (4.8 h). Both are one task (N1) and the pan stack prints meanwhile.

### 1.3 The cradle: fix it before its first print, with aluminium cheeks

**What the FEA says.** cad/turret_studies.py charges the whole cradle against the across-layer allowable (23 MPa,
humid printed PA6-CF) and gets SF 0.78 / 0.62 in the 30 g falls and 0.77 under a 50 N push on the muzzle
(exports/turret/fea/summary.json). To see whether that is the allowable or the part, the planner re-solved the same
three cases (same selectors, loads and 2.5 mm mesh) and split each element's corner stress into the component across
the layers (tension), the interlaminar shear and the in-plane von Mises, for each way the part could be printed
(cradle_layers2.py in the scratch folder; allowables 49 along, 23 across, 11.5 shear, the studies' own values):

| Case (target) | Isotropic, 23 MPa | Printed flat (layers x-y) | On its side (layers x-z) | On its tail (layers y-z) |
|---|---|---|---|---|
| R-fall-down (1.2) | 0.78 | 0.87 (shear 13.3 MPa at the rail-cheek fillet root) | 1.10 | 0.85 (the rail's bending runs across) |
| R-fall-side (1.2) | 0.62 | 0.73 (31.6 MPa tension at the servo hub's root) | 0.57 (20 MPa shear at the hub root) | 0.67 |
| E-push-up (2.0) | 0.77 | 0.86 (shear 13.3 MPa at the stop lug's root) | 1.13 | 0.90 |

Three readings follow. (1) The in-plane stresses are fine everywhere (28-40 MPa against 49: 1.2-1.8 in the falls); the
part fails only on its across-layer components. (2) Every orientation has an across-layer hot spot: flat, the hub
root in tension and the fillet and lug roots in shear; on its side, the hub and boss roots in shear (the boss is then
a column built along the build direction with the cheek bending it sideways); on its tail, the rails' bending. (3) The
peaks are local (the 99th percentile of the across-layer components is 3-9 MPa) and sit at the model's sharp corners.
A conical flare at the hub and boss roots (3 mm tall, +0.8 g; cradle_layers.py `--variant flare`) brings the side
fall's tension from 31.6 to 17.1 MPa (0.73 to 1.35) but leaves every shear peak at 12.6-14.9 MPa (0.77-0.91).

Hand checks agree with the model and say where the real loads are: the rear dowel's 90 N bends the +y rail about the
cheek's rear edge (46 mm lever on an 18 x 7 mm section: 28 MPa, along the layers, matches the 28.8 in-plane peak); the
sideways 90 N per cheek bends a 44 x 6 mm plate about the pivot 30 mm up (10 MPa nominal; the 31.6 at the hub root is
that times a sharp-corner factor of 3); the push puts 262 N on the stop lug (50 N x 147 / 28 mm), an 8.4 x 14 mm pad
2.5 mm proud of the cheek face, loaded along its root.

**Why not print it anyway.** The lug is a kid-safety part: a push on the muzzle with 50 N is 7.4 N m at the tilt axis,
more than the servo's 2.9 N m stall, so only the lug on the yoke's stop keeps the barrel from going above level. The
push case is the everyday case, its target is 2.0, and no orientation or flare gets the lug root past 1.13. The falls
are the robot's case (30 g), and the bench never sees one, so a printed cradle is fine for the bench; but the bench
turret is meant to be the robot turret, there is time in the schedule (the servos are 1-3 weeks away and the cradle is
step 8 of the assembly), and the one SendCutSend order is placed on day one anyway.

**Decision (D48): the cradle becomes a printed rail frame with two aluminium cheek plates.** In cad/turret.py:

- `cradle` (PA6-CF, printed flat, 100 %): the two rails, the rear cross bar, the laser tab, the CT dowel holes and the
  captive thumbscrew exactly as now; no cheeks, hub, boss, lug or spacer. Along the plates' feet (x 20..80) each rail
  is 12 mm tall instead of 7 (the clearance under the rails there is over 20 mm at every tilt: the cradle's front is
  what passes the pinion) and its outer face is rebated 3.2 mm so the plate's outer face comes back to y = 56.5, where
  the cheek's was: the 4 mm gap to the yoke arm is unchanged. Three M3 inserts per side in the rebate.
- `cradle_plate` x 2 (6061-T6 0.125 in, SendCutSend, `SHEET_PARTS`; one DXF, the two sides are the same outline with
  different holes, or two DXFs): an L in the x-z plane, a 60 x 12 mm foot on the rail with three M3 clearance holes
  and a 44 mm wide cheek up to the Ø44 round at the tilt axis. The +y plate: Ø6.5 at the axis and 4 x Ø3.4 on Ø14 for
  the servo horn. The -y plate: the pivot hole tapped M5 (SendCutSend taps 0.125 in aluminium; a hand tap is the
  backup) for the ISO 7379 shoulder screw. 24 g each (est): the plate's out-of-plane bending in the sideways fall is
  2.7 N m on a 44 x 3.175 section, 37 MPa against 276, SF 7.5 before any corner factor.
- `stop_lug` (6061-T6 0.100 in = 2.54 mm, SendCutSend, the fourth part of the same cart): the hard stop, on the -y
  plate's outer face where the printed lug was. A flat cheek cannot carry a proud lug, and the yoke's stop sectors
  live in the cheek's own x-z region, so the lug stays a separate proud piece: a 15 deg sector at r 24..32 with a
  20 x 12 mm pad below it (outside the sectors' annulus), bonded and held by two M3 flat heads countersunk in the
  cheek plate from its inner face into holes tapped in the lug (or two M3 blind rivets). Its outer face sits 1.5 mm
  from the yoke arm; the push's 262 N goes through it in its own plane and through the screws in shear. 2 g.
- `horn_boss` (PA6-CF, Ø20 x 9, 4 x Ø3.4 + Ø6.5): between the +y plate and the horn's face, 4 x M3 x 14 flat heads in
  SendCutSend's 90 deg countersinks (they countersink 0.125 in stock) through plate and boss into the horn's flange
  (today's M3 x 12 through a 6 mm cheek), so nothing stands proud on the plate's inner face, 4.3 mm from the
  cartridge. `pivot_spacer` (PA6-CF, the Ø18 x 3 boss and the 1 mm land on the MR126's inner race, Ø6.5 bore):
  between the -y plate and the bearing.
- `tilt_yoke`: its two stop sectors reach 3.0 mm proud of the arm's inner face instead of 2.5, so they overlap the
  lug by 1.5 mm (it was 1.0: bearing 8 x 1.5 mm at 262 N, 22 MPa on the sector's radial face, in-plane) and stay
  1.0 mm from the cheek plate's outer face; `stop_r` (24, 32) is unchanged. The sweep is run at tilts 0, -5, -12.5,
  -20 and -25 for the cradle-yoke pair (the lug swings between the sectors; the plates never meet them).
- Mass: about +28 g (two plates 48 g, the lug 2 g, two small printed parts 4 g, the rail frame 50 g, against the 76 g
  cradle): 1.667 kg with 30 balls, inside D49's 1.70 kg.

**API:** additive (new part names `cradle_plate_l/r`, `stop_lug`, `horn_boss`, `pivot_spacer`; `cradle` keeps its
name, frame and outer envelope; the yoke's change is inside the arm gap), so the consumers rebuild without edits, but
every one is rerun. The flared, flat-printed PA6-CF cradle is the hedge only if SendCutSend slips past the day the yoke goes on:
3.5 h, 77 g, proof-tested at the fall load (test 2.4 below) before it carries the cartridge, never on the robot.

### 1.4 The other FEA shortfalls: accepted for the bench, with the tests that prove them

| Part, case | SF (target) | Why it is accepted for v0 | Proof |
|---|---|---|---|
| tilt yoke, 50 N push | 1.82 (2.0), p99 4.4; the peak at the stop sector | the sector grows under D48 (more bearing, a wider root); rerun in N1 | bench test 2.1 (50 N x 200) |
| cartridge, recoil at 66 fps | 1.57 (2.0), p99 11 | 36 N of recoil for 5 ms on a modelled sharp corner | the first 100 balls (test 4.2-4.4) |
| pan base, servo at stall | 1.13 (1.2), p99 9 | the firmware caps the servo at 50 % (2.26 there); stall needs the cap to fail | bench test 2.3 |

N2 adds the directional (layer-aware) column to cad/turret_studies.py for every printed part, so these numbers are
read against the way each part is printed, as the cradle's were above.

### 1.5 Open items carried from v0

- **eRPM telemetry from the Repeat Robotics AM32 35 A ESC** (the pre-feed check and the whole flywheel loop depend on
  it: firmware/turret/flywheel.py `ErpmGuard`). The seller's page calls the ESC "bi-directional" in the sense of a
  reversible drive and says nothing about DShot telemetry; the catalogue says "RPM telemetry on this board not
  confirmed"; AM32's own bidirectional DShot works on its stock builds and the firmware's am32_settings.md already says
  to flash the stock release. D51: the Lumenier Razor Pro F4 45A pair (stock AM32, bidirectional DShot and a telemetry
  pad, the catalogue's backup, 28 x 12 x 5 in the same place) goes in the first order; the first bench hour with any
  ESC (N10) decides which pair is built in.
- **The gates' light** (bench test 3.10): the TSAL4400 through a 1 mm slit onto the TEFT4300; the 39 k pull-ups go in
  the order as the alternate (N3).
- **Bench tasks needing parts in hand:** plan T6 (measure the ring, the rocker, the socket), T10-T15 (print, assemble,
  electrics, flywheels, feed and accuracy, sign-off): section 4.2 carries them with the deltas of this page.

## 2. The J501 box adapter and Rev 0.9

### 2.1 What changed in the J501 (its working tree, read only)

cad/turret_box.py was drawn round Rev 0.8 (~/Code/j501-agx cad/parameters.json "0.8-thermal" at HEAD 0a6c28a). The
working tree is Rev 0.9 ("0.9-g48r": 48 files modified, uncommitted, on branch rev0.8-thermal; its README calls it the
"Rev 0.9 fit-check prototype"; no rev0.9 tag yet). What matters to the adapter:

| | Rev 0.8 (the adapter's fallback) | Rev 0.9 (the working tree) |
|---|---|---|
| Cooler | Seeed WS-RDN-601, 100 x 87 x 34, 8015 fan at PCB (90, 90.5) | Seeed reComputer mini J501 heatsink (SKU 100099421), 110 x 100 x 50: a heat-pipe tower on a 2 mm spreader, a 9215 fan (92 x 92 x 15, 12 V, 14-55 CFM) at PCB (88, 70.5) +-3 mm, blowing down; the fins exhaust to +-y (the box's front and rear) and under the fins |
| Roof | 92 high, 4.5 thick; hex cells inside a Ø80 duct ring feed the fan, the cells round it exhaust | 97 high, 3.5 thick with 8 ribs; over the fan the roof is cut to a flush 3 mm grille (hub Ø20, 2 rings, 12 spokes) on the fan's octagonal outline + 3 mm clearance, the fan top 2.44 mm under it, a 2.4 mm skirt wall round the fan frame; the hex field stays everywhere outside the skirt (the exhaust path) |
| Lid screws, bulkheads, footprint | M3 x 16 at (8.8/197.2, 30/162), heads at z 78, Ø6.4 counterbores; RP-SMA at z 62; 206 x 181 | unchanged |
| Fan centre in the box frame (x = 96 - y_j, y = x_j - 103) | (-9.5, +2) | (+10.5, 0): 20 mm further forward |
| Thermal (exports/thermal/cooled-0.9.json, bare box, 40 W) | 12.94 m3/h at 10.14 Pa, not converged | 27.5 m3/h (29 % of free air) at 19.9 Pa, air into the fan 28.5 C in 25 C (the criterion is 3 K), killed unconverged at 43 min |

The adapter's `_j501()` already reads the file and keeps the Rev 0.8 ring sizes when `fan_duct` is missing, so the
Rev 0.9 build today puts a Ø80 collar 20 mm behind the fan's centre, over a grille it was not drawn for.

### 2.2 What the adapter needs (task N4)

1. **The shroud's collar on the Rev 0.9 grille.** Its inner outline is the fan's octagon (92, corner chamfer 17.5)
   grown by `fan_grille.clearance` + `skirt_wall` + 1 mm (the roof's own open-cell boundary), about Ø104 round; the
   collar stands on the roof outside the skirt on foam tape, so the fan breathes only through the collar and the duct,
   and the exhaust leaves through the hex cells round it under the deck, out at the sides as before. The duct keeps
   its front mouth (124 mm wide); from the fan at x = +10.5 the flare is 80 mm long instead of 100.
2. **Heights:** the roof at `enclosure.height` (97): Z_TM 141, the legs' screws M3 x 40 (ROOF + 5 - (78 - 16)); the
   antennas' tops then 29 mm above the TM face (34 before).
3. **The pod's panel brought to the stand's** (cad/turret_stand.py PANEL): the Ø20.2 keyed rocker (D42), the TB3M
   mini-XLR D-hole 11.3 x 10.3 (D47) instead of the 3.5 mm jack, the XT60E-M slots as drawn; the pod's bought list and
   the box page's labels with them.
4. **Airflow by hand, then by thermometer.** `airflow_estimate()` rerun with the 9215's curve (28.1 Pa at zero flow,
   93.9 m3/h free) through the Rev 0.9 operating point (27.5 m3/h at 19.9 Pa): the duct's cost should stay under 10 %
   of the fan's flow. The J501's CFD has no option for an attached part and its own Rev 0.9 case is unconverged, so the
   adapter is checked on the box: a thermocouple in the collar and one in the room, 30 min at 40 W, the intake within
   3 K of the room (the J501's own criterion) and the module's temperatures from `tegrastats` no worse than without
   the adapter.
5. **The clearance study:** `cad/turret_lidar.py --scene box` rerun (the deck and antennas moved 5 mm down relative to
   the TM face); the keep-out behind the box stays (|pan| >= 120 deg).
6. **Provenance:** box.json records the J501 revision string and the file's git state (modified or committed); the
   build prints a warning when the revision string changes, so the adapter is rebuilt when Rev 0.9 is tagged.

Nothing is drilled in the box (the legs still ride the lid screws), nothing in the turret changes, and the adapter
stays three PETG prints (about 12 h). Decision D50.

## 3. From the bench prototype to the robot

### 3.1 What the turret gives the body (interface facts, from the CAD as merged)

| Item | Value | Source |
|---|---|---|
| Mount | the TM pattern: 4 x M5 on 80 x 80, dowels Ø5 at (52, 0) and (0, -52) (one way only), Ø45 hole (unused on the robot: the harness leaves by the DT12, nothing passes it); the foot Ø144 flat on the TM face; nothing below the face | cad/turret.py TM_BOLTS, TM_DOWELS, TM_HOLE, `pan_base` |
| Riser | 30 mm, on the top deck, open sides (D41, body plan): the turret only needs its top ring solid under the four bolts and the two dowels (M5 inserts 8 mm deep) and clear of the DT plug's sweep | docs/body-plan.md 1.1 |
| The DT12 plug | the DT04 receptacle is on the base's **-y pad (the robot's right)**, its centre 19 mm above the TM face; the DT06 plug stands 45 mm proud (y -78 to -123 in the turret frame) and withdraws 30 mm further (to -153); a 90 deg backshell turns the pigtail down | cad/turret.py DT, DT_Z, `pan_base`; docs/turret-wiring.md 1.1 |
| Harness | pins 1-2 +24 V, 3-4 GND (18 AWG), 5-6 CAN (twisted), 7-8 the dry safety loop (closed = run); 9-12 spare; the turret's own 5 A MINI fuse and reverse diode behind the receptacle | docs/turret-wiring.md 1.1, 4 |
| Mass, centre | 1.639 kg with 30 balls, 1.584 empty, +0.028 under D48; the centre (-5.6, -4.9, 95.5) mm from the pan axis on the TM face: 125 mm above the deck on the riser | exports/turret/turret.json |
| Power | 24 V, 2.5 A peak with the 300 ms ramp (never a stepped start on the robot), 40 W average; 3 x 1,000 uF behind the ring: plug the DT12 with the body's 24 V branch off | docs/turret-physics.md 9, wiring 5 |
| CAN | classic 1 Mbit/s, the turret's Feather terminates its own end; the body's end terminates at the J501's can1 | docs/turret-firmware.md 6 |
| Clearance over the lidar | the depression table (every 5 deg of pan) for the VLP-16 on the deck's front edge, its top 41.7 mm above the TM face; limited only within pan +-26 deg, to -16 deg at worst, with the lidar's axis 147.65 mm ahead of the pan axis | exports/turret/lidar/lidar.json |
| Recoil | 0.030 N s a shot, 0.9 N s for a hopper | docs/turret-physics.md 8 |

Two things the body plan has differently, to settle in N5: (a) its deck layout puts the lidar's axis **143 mm** ahead
of the pan axis (5 mm between the lidar and the bumper), not 147.65 (10 mm): the table is regenerated at 143 and the
body's constant becomes the one source; (b) its turret harness drops through a deck grommet at robot (-130, +60), the
**left** rear, while the plug is on the turret's **right**: with a 300 mm pigtail that route does not reach. The
recommendation to the body (D52): the grommet at robot (-130, -60), the right rear, the 24 V and CAN leads crossing
inside the body where wire is free.

### 3.2 What the turret needs from the body

1. The riser and the deck under it (body T2), printed PA6-CF, with the TM inserts and dowel holes.
2. A 24 V branch from the DDR-120C-24 through its 5 A fuse (body plan 1.3; shared with the J501), switched off while the
   DT12 is plugged.
3. A dry contact across DT12 pins 7-8, closed = run, rated for 12 V at 2 mA, that opens on the radio stop, on the
   receiver's failsafe (link lost) and when the robot sits (D37); a second pole of the same relay in the turret's 24 V
   branch as the independent cut Pololu's note asks for. The turret's own reaction is 20 ms in hardware once the
   contact opens, and 200 ms in firmware when the host's heartbeat stops.
4. The J501's can1 (the Seeed wiki's second CAN-FD port; the body plan's P0 confirms it with `ip link`); if only can0
   comes up, the turret stays on the USB-CAN adapter it uses on the bench.
5. A host process on the Jetson (section 3.3's bridge), and a "people near" input for it (the lidar and the cameras:
   the body's people-near mode).

### 3.3 Turret-side work for the robot (no body needed)

- **The host bridge** (N6): one Python host, `firmware/turret/host.py`, built on bench_host.py's protocol layer, that
  runs on the laptop (USB-CAN) and later on the Jetson (SocketCAN can1): the 10 Hz heartbeat, the CONFIG rows for the
  mount in use (depression table from lidar.json or box.json, keep-outs, tyre 34, ring 1, launch ratio, the throttle
  map after bench test 4.3), AIM / FIRE / LASER with a pan-rate cap that drops to 50 deg/s when "people near" is set
  and holds fire while it is, the SHOT / FEED / POWER / HEALTH logs; a CLI for manual firing and an API the game page
  can call. It runs end to end against `sim_turret.py` now and against the real turret in N13.
- **The robot harness page** (N7): a section of docs/turret-wiring.md: the DT06-12SA plug with the 1011-248-1205 90 deg
  backshell, the 300 mm pigtail, the STOP contact, the 24 V and CAN ends at the body, the grommet.
- **The mount file** (N5): `exports/turret/mount.json` with section 3.1's numbers and the plug sweep as a box, read
  by the body's `cad/body_params.py`.
- **The lidar table at the body's lidar position** (N5): `cad/turret_lidar.py --x 143`.
- **The bumper ring** fitted (v1 hardware; its tabs' short inserts, 5 x M3 x 20 with washers: the v1 lines in bom.json).
- **The drop test and the ring's life test** (N18, N19): the 30 cm drop onto the TM face and its side with a full
  hopper, on the stand; the ring at 60 rpm on a gearmotor, 100,000 turns (docs/turret-plan.md 6.4).

### 3.4 Blocked on the body workstream

The riser and deck (body T2), the 24 V branch and the STOP relay (body T5 and the radio stop, D37), the J501 can1
check (body P0), and the open frame balancing on its tether (body P1): the turret goes on at P2. Until then the
turret's robot work is the bench, the Orin box (section 2) and the software above. Nothing in this plan waits on a
decision; the body's two interface items (the lidar at 143 mm, the grommet side) are the only cross-workstream edits.

## 4. Tasks for the implementer

Estimates are agent working hours (an Opus session); printer, shipping and bench days are noted separately. Work in a
feat/ worktree of ~/Code/gyropup with a PR into dev (the repo's workflow). Section 4.1 runs now, with no hardware;
section 4.2 as parts arrive. T-numbers refer to docs/turret-prototype-plan.md section 6.

### 4.1 Now: CAD and software

| # | Task | Files | Acceptance | Est. |
|---|---|---|---|---|
| N0 | **Baseline.** Build main ab5b263: `cad/turret.py`, `cad/build_turret.py --no-render`, `cad/turret_motion.py`, `cad/turret_studies.py --only cradle --no-anim`, the firmware tests, `bench_host.py --sim`. Record mass 1.639 / 1.584 kg, 0 clashes, tilt margin 5.9, pan 8.9, the cradle's 0.78 / 0.62 / 0.77 | exports/turret/* | every build runs; the numbers reproduced within 2 % | 0.5 h |
| N1 | **The cradle with aluminium cheeks (D48, section 1.3).** `cradle` as a rail frame (12 mm rails and 3.2 mm rebates along x 20..80, three M3 inserts a side); `cradle_plate` (0.125 in) and `stop_lug` (0.100 in) in `SHEET` / `SHEET_PARTS` (DXF + STEP as the clamp); `horn_boss`, `pivot_spacer`; the yoke's sectors 3.0 mm proud; the hardware (M3 x 14 flat heads x 4, M3 x 8 x 6, M3 x 6 flat heads x 2, a shoulder screw into the tapped plate, a 1 mm shim); `MADE`, `bought_parts`, the print plan and `cad/turret_print.py` (the rail frame flat, no supports), `cad/turret_assembly.py` step 8 and its picture, bom.json and the order sheets (the SendCutSend cart: the clamp, two plates, the lug), docs/turret-print.md, docs/turret-assembly.md. FEA: the rail frame's three cases, each plate (out-of-plane 181 N, in-plane 181 N), the lug and its two screws under the push's 262 N, the yoke's push and side cases, with N2's columns. **API** (additive) | cad/turret.py, cad/turret_studies.py, cad/turret_print.py, cad/turret_assembly.py, cad/build_turret.py, exports/turret/cradle_plate*.dxf, exports/turret/stop_lug.dxf, docs | `clashes()` and `sweep()` clean at pans 0..350 x tilts 0, -5, -12.5, -20, -25 (the stop contact at 0 and -25 only); the plates' outer faces at y = +-56.5, 4.0 mm from the arms, the lug 1.5 mm from its arm; rail frame SF >= 1.2 falls / >= 2.0 push on the layer-aware column; plates and lug >= 2 on yield; yoke push >= 2.0; mass with balls <= 1.70 kg; the bench build, the box build and `cad/build.py` rebuild without edits; the SendCutSend cart has four parts in two thicknesses | 8 h + 1 h compute |
| N2 | **Layer-aware strength for every printed part.** In cad/turret_studies.py a post-process after each solve (as the scratch script does): the across-layer tension, the interlaminar shear and the in-plane von Mises of each element corner against 23 / 11.5 / 49 MPa (PETG: its own values), with the layer normal taken from the part's print rotation in `MADE`; summary.json gets both columns (isotropic against the weak allowable, as now, and layer-aware) and the verdict uses the layer-aware one with the isotropic one reported; the docstring says why | cad/turret_studies.py, exports/turret/fea/summary.json, docs/turret-program.md (the checklist line) | every printed part has both numbers; the cradle rail frame and the yoke pass on the layer-aware column; the pan base, pinion and cartridge rows unchanged or better; a note in cad/leg_studies.py's docstring that the same post-process applies there (not done here) | 3 h + 1 h compute |
| N3 | **The order sheets, amended (D51).** The Lumenier Razor Pro F4 45A x 2 (racedayquads.com, the catalogue's backup) as a line of the first batch; the 39 k gate pull-ups (test 3.10's alternate) and the resistor for the trip window's selection range on the Digi-Key sheet; the SendCutSend sheet with N1's plates; the totals and README regenerated | catalog/turret.json, exports/turret/bench/orders/*, exports/turret/bench/bom.json | the sheets total within $100 of $1,700; every new line has a price, a link and a second seller | 1 h |
| N4 | **The J501 Rev 0.9 adapter (D50, section 2.2).** `_j501()` reads `fan_grille`, the cooler's fan frame and chamfer and `center_in_pcb`; the collar on the grille's outline; the heights; the pod panel as the stand's; the airflow estimate on the 9215; box.json's provenance and warning; the box scene rerun; the box page's text (Rev 0.9, the tower cooler) | cad/turret_box.py, cad/build_turret_box.py, exports/turret/box/*, exports/turret/lidar/box.json | the adapter builds from the Rev 0.9 file and from the Rev 0.8 fallback; the collar clears the lid screws' legs and the TM bosses by >= 3 mm; the box scene clean with the keep-out as before; the three prints fit the bed; the hand estimate's flow loss <= 10 % | 4 h |
| N5 | **The mount file and the lidar table at 143 mm.** `exports/turret/mount.json` (section 3.1, the plug's sweep as a box in the turret frame, the mass and centre with and without balls, the recoil); `cad/turret_lidar.py --x 143` with the body's constant named as the source in the docstring; the firmware's CONFIG default for the robot mount from the new table | cad/build_turret.py (writes mount.json), cad/turret_lidar.py, exports/turret/lidar/lidar.json, firmware/turret/config.py | mount.json round-trips the TM constants from cad/turret.py; the table at 143 regenerated (expect the window about +-27 deg and the worst row -15 to -16 deg); the mock-lidar test 6.8 reads the new table | 2.5 h + 5 min compute |
| N6 | **The host bridge** (section 3.3): `firmware/turret/host.py` on bench_host.py's protocol layer, SocketCAN and the USB-CAN, the CONFIG rows for bench / box / robot, the people-near cap, logs to exports/turret/bench/host-*.json, a CLI; a test in test_firmware.py that runs it against `sim_turret.py`: home, config, aim, 24 balls, a people-near hold | firmware/turret/host.py, firmware/turret/test_firmware.py, docs/turret-firmware.md section 7 | the new test passes with the other 19; the bridge refuses to arm without the mount's table loaded; `--mount robot` loads N5's table | 6 h |
| N7 | **The robot harness and safety line in the wiring page** (section 3.2 item 3, D52): the DT06 plug and backshell, the 300 mm pigtail, the STOP contact and its second pole, the body's termination, the grommet at the right rear, the plug-with-the-branch-off rule | docs/turret-wiring.md (a section 1.1b), docs/body-plan.md is **not** edited (a note to the body workstream in the program log instead) | a reviewer can trace +24 V from the body's fuse to each ESC phase and the STOP contact to the 555 without a question | 1.5 h |
| N8 | **Record.** D48-D52 in docs/decisions.yaml (section 5.2's text), the program log entry, the checklist lines (structure: the cradle; box-specific; torque caps, which the firmware already writes at BOOT), the body's two interface items noted for its implementer | docs/decisions.yaml, docs/turret-program.md | the charter's open lines each point at a task of this page or a bench test | 1 h |

Dependencies: N0 first; N1 and N2 together (N2's post-process is what N1's acceptance reads); N3 after N1 (the
SendCutSend line); N4, N5, N6, N7 independent of N1; N8 last. About 27 h of agent time and 2 h of compute: three
sessions. The pan stack and the stand print during N1.

### 4.2 With the parts in hand

| # | Task | Files | Acceptance | Est. |
|---|---|---|---|---|
| N9 | **Receive and measure** (plan T6, bench test 1.8): the X2216 against SunnySky's drawing (the 16/19 cross, the 32 mm stack, the Ø5 pilot and M5 stud), a servo, the ring's flange holes into `RING_MODELS`, the rocker and the TB3M against the stand's panel; the carrier and the cartridge printed after | cad/turret.py, exports/turret/bench/fits.json | test 1.8 and the carrier's holes recorded; the cartridge print released | 3 h (after the parts) |
| N10 | **ESC telemetry on day one** (D51): the Feather, one ESC, one motor without a hub, on the bench supply at 12 V with a 1 A limit: bidirectional DShot eRPM in the WHEELS frame at idle and at 50 %; if none from the Repeat ESC, flash the stock AM32 release for its target and retry; the pair that returns eRPM is the one built in, the other is the spare | exports/turret/bench/erpm.json, firmware/turret/am32_settings.md | eRPM within 2 % of a strobe or a phase-frequency reading on both ESCs of the chosen pair; the pair named in am32_settings.md | 2 h (after the ESCs) |
| N11 | **Print** (T10) in the order of section 1.2: the stand and the pan stack now; the yoke and the rail frame after N1; the carrier after N9; the cartridge, hubs, dial and tyres after N9's measurements; fits.json as parts come off | exports/turret/print/*, exports/turret/bench/fits.json | fits.json complete; nothing printed twice for the same reason | 2 h + ~3 printer days |
| N12 | **Assemble** (T11), with the new step 8 (plates, boss, spacer, the shoulder screw into the tapped plate) and the new **test 2.4**: before the cartridge goes on, the cradle on the yoke takes 180 N down and 180 N sideways through a bar in the CT dowel holes (a luggage scale), 10 s, five times each way, then test 2.1's 50 N x 200 on the muzzle | docs/turret-assembly.md, docs/turret-bench-tests.md, exports/turret/bench/strength.json | tests 1 and 2 green; no crack, no set over 0.2 mm at the stops | 3 h + the user's hands |
| N13 | **Electrics without motors** (T12: 3.1-3.10, the ring tests included), the host bridge driving it | exports/turret/bench/*.json | 3.1-3.10 green, or the ring fails 3.7 / 3.8 and plan 2.4's cable-loop fallback starts | 3 h, 1-2 bench days |
| N14 | **Flywheels** (T13: 4.1 and 4.2 before anything else) | ceiling.json, speed_map.json, release.json, power.json, rails.json | 4.1-4.10 green; the throttle map into CONFIG through the bridge | 2 h, 1 bench day |
| N15 | **Feed and accuracy** (T14) | feed.json, groups.json, game.json | green, or each failure named with its count; the drop table into the firmware | 2 h, 1-2 bench days |
| N16 | **v0 sign-off** (T15): the checklist ticked with the JSON files; the measured masses by group; numbers back to the physics, the CAD and the firmware | docs/turret-program.md, docs/turret-physics.md, docs/turret-firmware.md | every claim of plan section 2.2 has a file | 2 h |
| N17 | **The Orin box:** the three adapter prints when the J501's Rev 0.9 cover is printed and fits its cooler; the thermometer check of section 2.2 item 4; manual firing from the Jetson through the bridge on the USB-CAN, the pendant held, the box's keep-out loaded | exports/turret/box/*.json | the intake within 3 K of the room for 30 min at 40 W; 24 balls on command from the Jetson, every shot logged, no fault | 3 h, 2 bench days (+12 h printer) |
| N18 | **On the robot** (blocked on body P2): the riser, the harness and the STOP contact, CONFIG mount = robot from N5's table, the mock-lidar sweep on the real lidar (test 6.8), the bumper fitted, then the 30 cm drop test on the stand with a full hopper (TM face down, then on its side) | exports/turret/bench/robot-*.json, exports/turret/fea/ | the barrel and every ball 10 mm clear at every pan; the drop: no crack, the stops and the ring unchanged, homing within 7 s after | 4 h, 2 bench days |
| N19 | **v1 background and awesome** (T17): the ring's life test on a gearmotor stand; the lights and buzzer, the hopper beam, the fill flap and spring, a green laser if the red dot is hard to see; the 24-ball hopper only if the mass line is crossed | cad/turret.py, docs/turret-wiring.md | each item's acceptance from the charter's checklist | 10 h, 2 bench days |

Dependencies: N9 and N10 as soon as their parts arrive (the ESCs and the Feather come from US sellers in days; the
servos are the critical path); N11 overlaps N1-N8; N12-N16 in order; N17 needs the J501's own Rev 0.9 prints; N18
needs body P2; N19 after N16.

## 5. Risks and decisions

### 5.1 Risks

| Risk | Likelihood / effect | What to do |
|---|---|---|
| The Repeat ESC returns no eRPM, nor after a stock AM32 flash | medium / no flywheel loop, no pre-feed check | D51: the Lumenier pair in the first order; N10 on day one; the catalogue's 4-in-1 fallback stays listed |
| The SendCutSend tapped M5 is refused for 0.125 in, or the tap strips | low / the pivot's retention | a hand tap (the shank carries the load, the thread only retains the screw); the backup is a Ø6 reamed hole and a longer shoulder screw with a thin nut on the yoke side |
| The aluminium lug wears the yoke's sector, or its two M3 screws loosen | low / the stop's position creeps | aluminium on PA6-CF at 22 MPa bearing; the lug bonded as well as screwed; test 2.1's 200 pushes measure the creep; a TPU pad on the sector if it does |
| The flat-printed rail frame still shows an across-layer peak at the rebate or the inserts | low / a reprint | N2's column shows it before the print; the rails' bending is in-plane by construction |
| The J501's Rev 0.9 numbers move (the fan centre is +-3 mm from a photo; the revision is uncommitted) | medium / the collar misses the grille | the adapter reads the file at build time and the collar has 3 mm of clearance; box.json's provenance warning; the adapter prints only when the Rev 0.9 cover is printed and fits |
| The adapter's duct starves the 9215 or re-breathes the exhaust | low / the Orin throttles on the bench | the hand estimate <= 10 %; the thermometer test; the duct's mouth can be opened to the full deck width |
| The body keeps the grommet on the left | medium / a pigtail that does not reach | N7 states the fact and a 450 mm pigtail as the alternative; the plug's side cannot move (the one-way dowels) |
| The lidar at 143 mm limits the depression more than the table says | low / a ball into the lidar | N5 regenerates the table at the body's number; test 6.8 on the real lidar (N18) |
| The mass line | the turret is 1.667 kg with the plates against the old 1.5 kg | D49 sets 1.70 kg and the body's ledger takes it; the levers (a 24-ball hopper -11 g, a one-board bay -40 g) stay listed, not scheduled |
| The ring under flywheel current | medium / the v1 risk, retired or not in v0 | tests 3.7, 3.8, 4.5 as before; the cable-loop fallback written (plan 2.4) |

### 5.2 Proposed decisions (for docs/decisions.yaml; the implementer records them in N8)

- **D48 (proposed): the cradle is a printed PA6-CF rail frame with two SendCutSend 6061-T6 0.125 in cheek plates,
  from the first print.** Why: re-solved by stress direction, the printed cradle fails across the layers in every
  print orientation (sideways fall 0.73 flat, 0.57 on its side, 0.67 on its tail; the 50 N push 0.86-1.13 against
  2.0), the push's weak spot is the root of the hard-stop lug that keeps the barrel from being pushed above level,
  and a flare at the hub root fixes only the one tension peak (0.73 to 1.35). The plates carry the pivot and the horn
  in their own plane (SF 7.5 in the sideways fall before any corner factor), a 2.54 mm aluminium lug screwed to the
  -y plate is the hard stop, all four parts ride in the pan clamp's SendCutSend cart, and the change adds about 28 g.
  The flared printed cradle is the schedule hedge only, proof-tested at the fall load and never on the robot.
  Supersedes plan T16's "fixed in v1 if under 1.2".
- **D49 (proposed): the head payload's mass budget is 1.70 kg with a full hopper, its centre at most 100 mm above the
  TM face (130 mm above the deck on the 30 mm riser).** Why: the turret as drawn is 1.639 kg (the slip ring, its
  carrier and driver, the board bays, the X2216s and the cartridge board are what the 1.5 kg of docs/head-payload.md
  did not have) and D48 adds 26 g; the leg rig is run at the real mass anyway (body T4), where 0.2 kg is 0.7 % of the
  robot; cutting it would cost the FEA margins the v0 FEA just bought. docs/head-payload.md and the body's mass ledger
  (which still carries 1.34 kg) take 1.70.
- **D50 (proposed): the turret-on-J501 adapter is rebuilt on the J501's Rev 0.9 parameters and printed only once the
  J501's own Rev 0.9 cover fits its cooler.** The intake shroud keeps its front duct, with the collar on the flush
  grille's outline and the fan 20 mm further forward; the pod's panel takes the stand's cutouts; the airflow is
  estimated by hand and proven with a thermometer in the collar (intake within 3 K of the room at 40 W).
- **D51 (proposed): both AM32 ESC pairs are bought in the first order, and the pair that returns bidirectional-DShot
  eRPM on the bench is the one built in.** The Repeat Robotics 35 A pair as catalogued and the Lumenier Razor Pro F4
  45A pair (stock AM32 with a telemetry pad) as the documented one; $63 of insurance for the check the whole flywheel
  loop depends on.
- **D52 (proposed): on the robot the turret's safety line is a dry contact across DT12 pins 7-8 from the body's radio
  stop (closed = run; open on the stop, on the receiver's failsafe and when the robot sits), with the same relay's
  second pole in the turret's 24 V branch; the harness is a 300 mm DT06 pigtail with a 90 deg backshell on the
  turret's right (-y), so the deck grommet goes to the robot's right rear (-130, -60).** The turret's hardware and
  firmware need nothing new for it; the body's radio-stop design (D37) and its deck drawing take these two facts.

## Appendix: the numbers behind section 1.3

From /mnt/storage-10tb/claude-scratch/gyropup/turret-planner/cradle-layers2-base.json and cradle-layers-flare.json
(the same selectors, loads and 2.5 mm P2 mesh as cad/turret_studies.py; peaks over the elements that touch no clamp or
load patch; allowables along 49, across 23, interlaminar shear 11.5 MPa; C frame, mm):

| Case | Component | Flat (normal z) | On its side (normal y) | On its tail (normal x) |
|---|---|---|---|---|
| R-fall-down | in-plane VM | 28.8 (1.70) at (9, 51, -21) | 30.3 (1.62) | 21.9 (2.24) |
| | across-layer tension | 14.7 (1.56) at (25, 51, -11) | 12.3 (1.87) | 27.2 (0.85) at (9, 51, -16) |
| | interlaminar shear | 13.3 (0.87) at (22, 51, -13) | 10.5 (1.10) | 13.3 (0.87) |
| R-fall-side | in-plane VM | 39.8 (1.23) at (40, 57, 10) | 31.3 (1.57) | 36.7 (1.33) |
| | across-layer tension | 31.6 (0.73) at (41, 56, 7) | 32.8 (0.70) at (40, 57, 10) | 26.5 (0.87) |
| | interlaminar shear | 14.1 (0.82) at (39, 56, 9) | 20.1 (0.57) | 17.2 (0.67) |
| E-push-up | in-plane VM | 27.1 (1.81) at (9, 51, -21) | 29.4 (1.67) | 23.6 (2.08) |
| | across-layer tension | 21.3 (1.08) at (50, -56, -17) | 14.1 (1.64) | 25.7 (0.90) at (9, 51, -16) |
| | interlaminar shear | 13.3 (0.86) at (51, -56, -17) | 10.2 (1.13) | 12.6 (0.92) |

With 3 mm conical flares at the hub and boss roots, printed flat: fall-down 28.8 / 15.6 / 13.2 (0.87); fall-side
25.7 / 17.1 / 12.6 (0.91); push 27.2 / 15.9 / 14.9 (0.77). The 99th-percentile values of the across-layer components
are 3.3-9.2 MPa in every case: the peaks are the model's corners, and the push's sits at the lug root, (50, -56, -17).

Geometry used (cad/turret.py `Geo` defaults): cheeks y 50.5..56.5 (6 mm), arms 60.5..68.5, rails y 38.5..56.5 and
z -22.1..-15.1 (7 mm behind x 80), the tilt axis at (48, 15), the lug at r 18..32 over -97.5..-82.5 deg (x 43.8..52.2,
z -17..-3), the dowels at (-20, +43) and (75, -43), the latch at (20, -43). Hand numbers: rail bending at the cheek's
rear edge 90 N x 46 mm / 147 mm3 = 28 MPa; cheek bending 90 N x 30 mm / 264 mm3 = 10 MPa; the lug's stop load
50 x 147 / 28 = 262 N. J501 Rev 0.9 in the box frame: fan (10.5, 0), Z_TM 141, lid screws M3 x 40.
