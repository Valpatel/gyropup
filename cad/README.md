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
