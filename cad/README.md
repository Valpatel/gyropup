# Printed parts (CAD)

[`build.py`](build.py) makes every part of a design in CadQuery: the aluminium chassis, the two leg modules ([`leg.py`](leg.py), built on the mechanical interface standard in [`gmi.py`](gmi.py) and [`../docs/mechanical-interfaces.md`](../docs/mechanical-interfaces.md)), and the printed head, face and sensor mounts. The motor interfaces come from the vendors' drawings ([`../catalog/interfaces.json`](../catalog/interfaces.json)). [`studies.py`](studies.py) runs the stiffness and strength studies, and [`cables.py`](cables.py) checks the cable routes over the leg's whole range of motion.

```
.venv/bin/python cad/build.py designs/default.json   # STEP + print-ready STL in exports/, then:
.venv/bin/cad-agent view                              # the 3D assembly, at /_cadagent/kit/viewer.html
```

| Assembled, standing | Exploded |
|---|---|
| ![assembly](assembly.png) | ![exploded](exploded.png) |

| Part | Qty | Made | Notes |
|---|---|---|---|
| `chassis` | 1 | 3 mm 6061, laser cut and bent (SendCutSend) | The spine: floor, side walls with the HM pattern where the legs bolt on (6 × M6 + 2 dowels each side) and the cable passes, front and rear walls for the face and cameras, top flanges where the J501 box stands on its four M3 standoffs |
| `battery_cradle` | 1 | printed PLA | Rails and strap channels for the FLEXVOLT pack inside the chassis |
| `yoke_bracket` | 2 | printed PA6-CF | Wall plate on the chassis (HM), deck over both motors, drop faces onto both motor plates' tabs: with the three posts it closes a box around the joint |
| `hip_motor_plate`, `knee_motor_plate` | 2 + 2 | CNC 6061 | The motor-specific AC part: the motor's mounting lugs and spigot, a 61812 support bearing around the output adapter, standard post and bracket holes |
| `hip_output_adapter`, `knee_output_adapter` | 2 + 2 | CNC 6061 | The motor-specific AO part: dowels into the motor's output, a Ø60 journal for the support bearing, the standard face (Ø40 spigot, 8 × M5 on Ø50, 2 dowels) |
| `thigh` | 2 | CNC 6061 box (or 40 × 30 × 3 tube with bonded ends) | On the hip's standard face; knee pin at the far end; the wheel's cables run inside |
| `shin` | 2 | CNC 6061 box | Two 6001-2RS knee bearings, the push-rod lever, the WH face for the wheel adapter; cables inside |
| `knee_crank` | 2 | CNC 6061 | On the knee's standard face; drives the shin through the push-rod (two M6 rod ends and a Ø12 tube, bought) |
| `wheel_adapter` | 2 | 6061 | WH face to the shin, the BotWheel's 4 × M6 flange and boss on the other side, the cable through the middle |
| `head_saddle` | 1 | printed PLA | Open frame on the J501 lid screws; lifts the turret ring 20 mm so the cooler grille keeps breathing |
| `face` | 1 | printed PLA | DualEye window and two headlight bosses |
| `camera_cradle` | 2 | printed PLA | D415 or D435 on its 1/4-20, front and rear |
| `lidar_hanger` | 1 | printed PLA | VLP-16 under the waist: 1/4-20 and two locating pins |

Every part is a valid single solid; the printed ones also pass the watertight-STL and P1S bed checks (`exports/geometry-checks.json`). The CAD masses go to [`exports/mass-properties.json`](../exports/mass-properties.json), and `sim/model.py` uses them in place of the designer's estimates, together with the real hip and wheel positions from [`exports/mech-layout.json`](../exports/mech-layout.json).

The stiffness studies, the cable routes and the open weight work are in [`../docs/mechanical-interfaces.md`](../docs/mechanical-interfaces.md#results-rev-02-2026-10-25). The vendor STEP files used for the clash checks stay local (`references/vendor/`, no licence to redistribute). The assembly shows bought parts as simple envelopes.

## The turret on the Orin AGX compute box

[`turret_box.py`](turret_box.py) mounts the turret ([`turret.py`](turret.py)) on the lid of the J501 enclosure
(`~/Code/j501-agx`, Rev 0.9 with the tower cooler: the Seeed reComputer mini J501 heatsink, its 9215 fan under a flush
grille in a 97 mm roof), so it can be aimed and fired from the computer that will drive it (D50). Nothing is drilled in
the box: four legs stand on the lid's screw corners and longer screws (M3 × 40 for the J501's M3 × 16) clamp leg, lid
and base into the same inserts. The fan breathes in through the grille and the hex cells round it let the exhaust
out, so the deck stands 44 mm up (the TM face at 141 mm) and an intake shroud keeps the two apart: a Ø104 collar round
the grille, sealed on the roof's solid band by a foam ring under its floor's lip, fed by a 160 mm duct from the front.

```
.venv/bin/python cad/build_turret_box.py     # exports/turret/box/ (parts, print plan, parts list, checks) and exports/sim/turret_box/
.venv/bin/python cad/turret_lidar.py --scene box   # the 3D clearance study the box checks read (exports/turret/lidar/box.json)
```

The second folder is the scene for the 3D game page: pick **Turret on the Orin AGX box** in the simulator's design
list (`designer/sim.html?design=turret-box`). The build reads the J501's sizes from its `cad/parameters.json`, its fan
curve and CFD operating point from its `thermal` parameters and `exports/thermal/cooled-<rev>.json`, and its meshes from
its `exports/view/` (or its `exports/*.step` when the view meshes lag its parameters); set `J501_DIR` if the repo is
elsewhere, and rebuild after either project changes. It prints a warning when the J501's revision is not the one the
adapter was drawn for (`turret_box.BUILT_FOR`, "0.9-g48r") or its parameters are not committed there, and records the
revision and the file's git state in `box.json`: rebuild when Rev 0.9 is tagged, and print only once the J501's own
Rev 0.9 cover fits its cooler. Rev 0.8's parameters still build (the collar on its Ø80 duct ring), as the fallback.

| Part | Qty | Made | Notes |
|---|---|---|---|
| `box_deck` | 1 | printed PETG, upside down | The TM face (4 × M5 inserts in bosses deep enough for the turret's M5 × 16, 2 × Ø5 × 10 dowels), four hollow legs with spigots in the lid's counterbores, the front skirt, the control pod at the back with the bench stand's panel (XT60E-M 24 V inlet, Ø20.2 keyed DC rocker, 5 × 20 fuse holder, TB3M mini-XLR pendant socket, USB-CAN cable out) |
| `intake_shroud` | 1 | printed PETG, on its floor | Ø104 collar on the grille's outline, a 160 mm duct to a grille of 2 mm bars at the front, the floor's lip on 3 mm of foam tape; 6 × M3 × 10 up into the deck |
| `pod_cover` | 1 | printed PETG | Closes the pod from below (4 × M3 × 6 flat heads) |

`exports/turret/box/box.json` has the checks: the moving turret against the deck and against upright antennas on the
J501's RP-SMA bulkheads (and the 3D ball path from `cad/turret_lidar.py --scene box`), the shroud's fit to the legs and
the TM bosses, where the foam ring sits on the roof, the shroud's cost to the J501's fan (a hand estimate with its
method and sensitivity; the thermometer on the box is the proof), tipping, the top ball speed if the throttle limit
fails, and how long a ball can still fire after ARM is released. `bom.json` is what to buy for it, every line a
catalogue key with a listed price.
