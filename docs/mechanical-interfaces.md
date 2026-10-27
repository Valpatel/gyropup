# Gyropup mechanical interfaces (GMI v0.1)

**Goal:** swap motors and change leg designs without redesigning everything else. Each motor gets two **adapters**: one on its output, one on its case. They turn that motor's own bolt patterns into **standard faces**. Leg links, hip yokes, wheel mounts and the body only ever bolt to standard faces. A new motor means two new adapters. A new leg design means new links on the same faces.

The numbers live in [`cad/interfaces.json`](../cad/interfaces.json), and the CAD in [`cad/`](../cad/) reads them from there. Motor-side patterns come from [`catalog/interfaces.json`](../catalog/interfaces.json), checked against drawings; [`research/actuator-interfaces.md`](../research/actuator-interfaces.md) records where each number came from. Anything not yet confirmed from a drawing is flagged ASSUMED and printed in the build report.

## The modules

```
 chassis ──HM── hip module ─────────────── AO-L ── thigh ──KC── shin ──WH── wheel adapter ── wheel motor
                   (yoke, case adapters ×2,   AO-L ── knee crank ──PR── shin lever
                    hip + knee actuators)
```

| Code | Interface | Standard face | Carries (design load) |
|---|---|---|---|
| **AO-L** | Large actuator output (hip, knee): the output adapter | on the motor side, a contact boss the size of the motor's output flange, 0.6 mm clear of everything else (RobStride outputs sit flush with a stationary ring), dowels into the motor; a Ø60 journal for the 61812 support bearing; on the leg side, a Ø40 h7 spigot 3 mm proud, 8 × M5 on Ø50, and 2 × Ø5 dowels at 22.5° and 247.5° (one-way clocking) | 80 N·m peak torque, 2 kN radial, 60 N·m tilting (through the support bearing) |
| **AC-L** | Large actuator case: the motor plate | bolts to the motor's own mounting lugs (RobStride: the output-side lug face) and locates its spigot; holds the 61812 (60 × 78 × 10) support bearing around the adapter's journal, pressed in from the motor side against a 2 mm lip at the leg-side face (no retainers: its outer ring only takes outward thrust, which the lip carries, and the face stays flat 1 mm from the link); standard holes for three spacer posts (M5 on R82 at 30°, 90°, 150°) and the hip bracket (3 × M5 along the top) | the leg's bending goes through the support bearing into the plate, not into the motor's thin output bearing (RS-03: a 45 × 58 × 7 deep-groove) |
| **AO-S** | Small actuator output (turret, accessories) | Ø24 h7 spigot; 6 × M4 on Ø34 PCD; 2 × Ø4 dowels | 40 N·m, 1.2 kN radial |
| **AC-S** | Small actuator case | 6 × M4 on Ø84 PCD; Ø76 h7 pilot; 1 × Ø4 index pin | the same |
| **KC** | Knee cartridge (passive pivot) | 2 × 6001-2RS (12 × 28 × 8) in the shin hub, 20 mm apart; Ø12 h6 pin (M10 shoulder bolt); thigh clevis Ø12 H7 | 3 kN radial; the 6001's dynamic rating is 5.1 kN each |
| **PR** | Push-rod (knee drive) | two M6 rod ends (Igus or SKF type), centres one thigh-length apart; Ø12 × 1 steel tube or Ø12/10 carbon tube with bonded inserts | ±1.5 kN axial |
| **WH** | Wheel hub face on the shin | 6 × M5 on Ø50 PCD; Ø32 H7 bore; Ø16 cable bore on the axis | 400 N radial, 30 N·m tilting |
| **HM** | Hip module to body | 6 × M6 on a 100 × 60 mm rectangle + 2 × Ø6 dowels | the whole leg: 600 N, 80 N·m |
| **CP** | Cable pass at every module boundary | Ø18 grommet hole with a two-screw strain-relief clamp | — |

### Why these numbers

- **AO-L.** On Ø50, eight M5 12.9 bolts clamp about 9 kN each. At µ = 0.15 that holds about 270 N·m by friction, more than three times the peak.
- **The support bearing.** The sim's hardest turn puts 50 N·m of bending at the hip output. RobStride's output bearings are thin single-row ball bearings with no published moment rating. The 61812 in the motor plate and the motor's own bearing, about 18 mm apart (the 61812 sits under the plate's 2 mm lip), turn that moment into a pair of radial loads of about 2.8 kN, well inside a 61812's rating. The dowels take shock in shear if a printed part creeps and loses preload: 54 N·m on two Ø5 pins at r = 25 mm is about 1.1 kN per pin. That is why links get an **aluminium hub plate** at this face, not threads or holes in plastic.
- **The push-rod is the knee's real load path.** A Diablo-style coaxial knee motor drives the shin through a parallelogram. The rod force is the knee torque divided by the crank radius. The 54 N·m peak (hard-shove catch, in simulation) gives 1.35 kN on a 40 mm crank, or 1.2 kN on the 45 mm crank used here.
  - A printed rod buckles long before that. A Ø12 × 1 steel tube 200 mm long buckles at about 26 kN; a Ø12/10 carbon tube at about 8 kN.
  - M6 rod ends are rated for several kN static.
- **The knee pin** carries the shin load plus the rod load: about 0.3 kN plus 1.2 kN in the worst case. Two 6001s have a lot of margin.

## Cable routing rules

1. **Cross every joint close to its axis.** The cable's length change across a joint is (distance from the axis) × (joint travel). Hip and knee runs stay within 15 mm of the axis, so the change is under 30 mm over the full range.
2. **Service loops**, sized for each joint's full range: a loose U or clock-spring loop around the axis, never a taut chord.
3. **Bend radius:** at least 10 × the cable's outside diameter where it flexes, and at least 5 × where it is fixed.
4. **Clips every 60 mm** along links, molded into the printed parts (cable-tie slots or snap channels).
5. **Strain relief** within 30 mm of every connector, and at every CP.
6. **Clearance:** at least 5 mm from moving parts at every pose in the joint ranges (checked in CAD), and nothing crosses a pinch zone of the knee four-bar.
7. **Separation:** motor power (phases, battery) and signal (CAN, encoder, hall) in separate bundles where they can be, crossing at right angles. CAN uses twisted pair.

The harness definitions (waypoints on each link, cable size, and which joint each crosses) are in `cad/cables.py`, and the build checks rules 1, 3, 4 and 6 for every leg pose.

## Stiffness and strength targets

Checked with `cadagent.fea` (linear elastic, quadratic tetrahedra) using the simulator's worst joint loads ([`exports/fea/`](../exports/fea/)):

| Check | Target |
|---|---|
| Wheel position under the worst simulated leg load | total deflection of the thigh and shin at most 2 mm |
| Side load (turning, 0.5 g of the robot on one wheel) | wheel camber change at most 1.5° |
| AO-L adapter plus link hub, torsion | at least 100 N·m/° (well above the balance loop's needs) |
| Printed parts | safety factor at least 2 on the layer-direction strength at the worst simulated load, at least 3 for impact cases |
| Metal parts | safety factor at least 2 on yield |

## Results (rev 0.2, 2026-10-25)

From `cad/studies.py` (FEA, quadratic tetrahedra, about 3 mm mesh) under the simulator's worst joint loads over all nine scenarios. All parts are 6061-T6; the safety factor is against yield.

| Part | Case | Material | Load (from the simulator) | Design stress | Safety factor | Deflection at the load |
|---|---|---|---|---|---|---|
| thigh | T1 | Aluminium 6061-T6 | targets: shin force 206 N, knee torque 19 N·m -> push-rod 428 N | 74.31 MPa | 3.71 | 0.232 mm |
| thigh | T2 | Aluminium 6061-T6 | drive: hip moment 25 N·m (out of plane -17), lateral force -52 N | 52.18 MPa | 5.29 | 0.145 mm |
| shin | S1 | Aluminium 6061-T6 | curb: wheel force 268 N (0 N sideways), wheel offset 36 mm | 31.04 MPa | 8.89 | 0.102 mm |
| output_adapter | A1 | Aluminium 6061-T6 | motor torque 54 N·m with 17 N·m out of plane and 268 N radial | 6.34 MPa | 43.55 | 0.0 mm |
| motor_plate | P1 | Aluminium 6061-T6 | 268 N up and 0 N sideways through the bearing, 17 N·m out of plane, motor torque 54 N·m on the lugs | 41.96 MPa | 6.58 | 0.043 mm |
| yoke_bracket | Y1 | Aluminium 6061-T6 | the whole leg: 268 N up, 0 N sideways, 17 N·m out of plane, 54 N·m about the hip axis | 101.09 MPa | 2.73 | 0.27 mm |

- **Deflection:** the wheel moves about 0.57 mm under the worst load, against a 2 mm target.
- **Margins:**
  - Weakest: the yoke, at a safety factor of 2.73.
  - Strongest: the output adapters (about 44) and the shin (about 9). These can be lightened.
- **What the studies changed:**
  - A printed PA6-CF thigh failed the hard-turn case outright: safety factor 0.11, 38 mm of deflection.
  - A printed yoke bent 10 mm (safety factor 0.26).
  - The first motor plate's thin tab neck failed (safety factor 0.84).

Cables (`cad/cables.py`, `exports/cables.json`, `exports/cables.png`):
- The wheel harness runs inside the thigh and shin boxes with service loops at the knee and the hip.
- **Loop slack:** 16.3 mm at the knee and 36.7 mm at the hip.
- **Loop radius:** 46.6 mm, against the 20 mm minimum for loose 18 AWG conductors.
- **Clearance:** at least 6.0 mm from every moving part over the whole range.
- **Extension:** the route is 616 mm long, so the BotWheel's 300 mm lead needs about a 470 mm extension.

**Open: weight.** The made parts (chassis and both legs) come to about 6.9 kg, which puts the robot at about 22 kg in the physics model. The next pass:
- The yoke (950 g each) as a pocketed or welded frame.
- Pockets in the motor plates (420 g each).
- The output adapters (SF 44) hollowed out.
- A chassis with more cutouts.
