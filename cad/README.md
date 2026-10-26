# Printed parts (CAD)

[`build.py`](build.py) makes every printed part of a design in CadQuery, from the design file and the designer's layout, so each design gets parts that fit it. The interfaces it builds to are in [`parameters.json`](parameters.json). Values marked ASSUMED in that file need checking against the real part, starting with the RS-03 bolt pattern and the RS-06 and RS-00 bolt patterns for the tail.

```
.venv/bin/python cad/build.py designs/default.json   # STEP + print-ready STL in exports/, then:
.venv/bin/cad-agent view                              # the 3D assembly, at /_cadagent/kit/viewer.html
```

| Assembled, standing | Exploded |
|---|---|
| ![assembly](assembly.png) | ![exploded](exploded.png) |

| Part | Qty | Notes |
|---|---|---|
| `tray` | 1 | Battery tray and hip frame. Also has 4× M5 inserts under the back for the tail mount. Hangs under the J501 box on its four M3 stacking standoffs, holds the FLEXVOLT pack (strapped), and carries the yokes, face, cameras and lidar on heat-set inserts |
| `hip_yoke` | 2 | C-yoke: hip motor inboard, knee motor outboard, coaxial (the Diablo layout). PETG (touches the motor cases) |
| `thigh` | 2 | On the hip motor output; knee pivot at the far end. Printed corner to corner on the bed |
| `shin` | 2 | Two 6000-2RS knee bearings, a push-rod lever, and the BotWheel flange (4× M6 on a 36 mm PCD) |
| `knee_crank` | 2 | On the knee motor output; drives the shin through the push-rod (parallelogram four-bar). PETG |
| `pushrod` | 2 | Two 625-2RS bearings, one thigh-length apart |
| `head_saddle` | 1 | Open frame on the J501 lid screws; lifts the turret ring 20 mm so the cooler grille keeps breathing |
| `face` | 1 | DualEye window and two headlight bosses |
| `camera_cradle` | 2 | D415 or D435 on its 1/4-20, front and rear |
| `lidar_hanger` | 1 | VLP-16 under the waist: 1/4-20 and two locating pins |
| `tail_mount` | 1 | The tail's lift motor (RS-06) under the back of the tray, on 4× M5 inserts, behind the lidar. PETG |
| `tail_yoke` | 1 | **Aluminium**, not printed: 5 mm 6061, cut and bent once (SendCutSend). Joins the lift motor's output to the wag motor (RS-00); takes the catch loads |
| `tail_clamp` | 1 | Under the wag motor's output; split clamp on the 20 mm carbon tube. PETG |
| `tail_shoe` | 1 | TPU 95A skid shoe on the end of the tube: it slides, it is not driven. Replaceable |

Every part passes cad-agent's checks: a valid single solid, watertight STL, and a fit on the P1S bed (`exports/geometry-checks.json`). The CAD masses (2 mm walls, 40 % infill: about 2.3 kg of filament) go to [`exports/mass-properties.json`](../exports/mass-properties.json), and `sim/model.py` uses them in place of the designer's estimates. This is revision 0.1: the leg links are not yet checked against simulated loads (FEA is next), and the bought parts in the assembly are simple envelopes.
