# What stops an over-commanded leg from breaking itself

The owner asked on 2026-11-03: "what prevents us from ripping apart the legs by over commanding the motors?" and
"What's the point of having 120nm motors if we cap at 60nm?" ([issue #202](https://github.com/Valpatel/gyropup/issues/202)).

This page answers both. Section 1 is the audit: every layer between a command (the Jetson, a gamepad, a slider, the
rig laptop) and the leg's plastic, what each layer already did, what was missing and what was added. Section 2 derives
the torque each leg build may take, and section 3 answers the 120 N m question with the rig's jump at each cap.
Decision [D78](decisions.yaml) records the result; it replaces D33's flat 60 N m cap.

Every number here is generated: `python -m sim.leg_limits` writes [exports/leg/limits.json](../exports/leg/limits.json)
from the FEA summary, the motor-day derating and the five-bar's stops, and
`python firmware/balance/tools/gen_limits.py` turns it into the firmware's `include/gp/gp_limits.h`. CI checks both
are current (`sim/test_leg_limits.py`, `gen_limits.py --check`). These are simulated and analysed limits, not a
loaded leg: nothing here has been run on hardware.

## 1. The layers

The leg's two RS-04s run in MIT mode with Kp = Kd = 0: the firmware sends a torque and nothing else, so the
firmware's torque is the whole command. The layers, outermost first:

| Layer | What existed (file:line) | Gap | What was added | Test |
|---|---|---|---|---|
| Command clamp: height, lean, speed, turn | `gp_control.c:145-164`: height 0..1 slewed at 0.6/s, lean (look) clamped -0.1..0.35 rad at 0.5 rad/s, speed clamped to half the wheels' no-load speed, 1.5 m/s² | Out-of-range commands were clamped, not refused (kept). Yaw rate is unclamped (its torque is: `tau_yaw` to a share of the wheel peak) | Nothing: clamping is right for a balancing robot (a refusal would drop the command mid-stride). The playground gets the same rates: `designer/leg_limits.js` | `tools/test-leg-limits.mjs` checks the rates against `gp_model.h` |
| Commanded reach (five-bar workspace) | `gp_config.h:30`: a *measured* leg outside 95-395 mm limps | The *commanded* length was never checked against the lean: full height leaning back 0.35 rad (375 mm) is outside the five-bar's reach, so the leg's spring would have driven a motor into a stop or toward a dead point | `gp_guard_clamp_L` (`gp_guard.c:70`, called at `gp_control.c:194`): each leg's commanded length is clamped to the window at its lean that keeps both motors 2° inside their stops and 25° from a dead point (0.107-0.383 m upright, 0.207-0.343 m at ±0.35 rad; 21 rows, `gp_lim_window`) | `sim/test_leg_limits.py::test_every_commanded_pose_is_reachable...`, host `test_guard` |
| Five-bar singularity, controller output | `gp_control.c:55, 128`: a leg whose Jacobian fails gets no torque | none on output; the command side was the gap above | the window's 25° dead-point margin | as above |
| Soft joint limits | none: only the TPU-sleeved hard stops (D38: front +3/-97°, rear -183/-83°) | A spring command near a stop pushed straight into it at the full cap | `gp_guard_soft_stop` (`gp_guard.c:31`, `gp_control.c:207`): inside 2° of a stop no torque goes into it; inside 10°, an approach faster than the stop can absorb at the every-day torque (`approach_limit = sqrt(w_c² + 2 (T/J) d)`, `w_c = T / sqrt(k J)`) brakes at 20 N m s/rad of the excess, never more than the every-day torque. Same rule in `sim/leg_limits.py:290`, `rig/leg_control.py:225` and `sim/leg_rig.py:395` | `test_soft_stops_never_push_further...` (20,000 random states), `rig/tests/test_control.py::test_the_soft_stops...`, host `test_guard` |
| Measured joint range | the 95-395 mm length window only | A motor could be measured well past its hard stop (a broken stop post, a slipped zero) and still be driven | `gp_guard_angle_ok` (`gp_guard.c:77`, `gp_app.c:489`): a motor more than 10.13° past a stop (the TPU sleeve's squeeze at the R3 fault torque, 121.5 N m on 856 N m/rad, plus 2°) limps, reason 17 | host supervisor test (joint range) |
| Torque cap, firmware | `gp_config.h`: one `GP_RS04_LIMIT_TORQUE` 60 N m, D33's, on every build including the PLA bench leg | The PLA leg's own limit (12 N m, the motor-day derating) lived only in the rig laptop's `--cap`; the robot had no reason for 60 and no peak/continuous split | `gp_limits.h` (generated) per build: robot 61 every day / 69 in the jump's push only (at most `GP_JUMP_PUSH_MAX_S` 0.35 s), PLA bench 12 / 12. `gp_app.c:947` picks the cap each tick, `gp_control.c:211` clips to it; an unset cap falls back to the PLA's, never to "no cap". The rig profile's build is a CMake option, `-DGP_RIG_BUILD=pla_bench\|robot`, PLA by default | host suite run for both rig builds (CI: `body-firmware.yml`) |
| Torque cap, in the motor | `limit_torque` 60 written and read back at boot | as above | `limit_torque` = the build's `GP_LIM_*_MOTOR_NM` (robot 69, PLA 12), written and read back (`gp_app.c:311, 345`): the motor's own backstop if the firmware misbehaves | host supervisor test (limit_torque readback) |
| Continuous / RMS | none in firmware (the rig laptop sits over 80 °C winding: `rig/leg_control.py:165`) | A long crouch or repeated jumps could hold the peak far past the motor's rated torque | Each motor's running mean square torque (time constant 30.2 s: the winding's R_wc × C_w): over 28.5 N m rms the cap drops to 28.5 until it is under 0.9 of it (`gp_app.c:1010, 948`). No jump while a motor's rms is over 0.8 of it or its reported temperature over 70 °C (refusal 6); a motor over 80 °C sits the robot (reason 18). PENDING #195's heat model | host supervisor tests (rms hot, temperature) |
| Jump gate | voltage, people, link, standing, height 0 (`gp_app.c:529`) | A stuck jump request could chain jumps back to back | No jump within 1 s of the last landing (refusal 7, `gp_app.c:536`) | host supervisor test (cooldown) |
| Bus current | 30 A continuous, 80 A for 0.5 s, the push at `s(V) × 72 A` (`gp_app.c:245`), the regen clamp | none for the leg (it caps the push's power, not its torque) | nothing | existing HIL |
| Radio stop, heartbeat, CAN timeout | stop relay sensed in 2 ms, a fast sit; heartbeat sit at 2.2 s; each RS-04 drops to reset 0.1 s after its last frame (`GP_RS04_CAN_TIMEOUT`) | none | nothing | existing HIL |
| Hard stops | TPU-sleeved stop posts, 856 N m/rad at the motor; FEA `stop_post` E3 (SF 2.11 at 60 N m), R3 (1.04 at 121.5 N m) | Impact energy was never compared with what the stop takes | The soft stop's approach limit is that comparison: at the every-day torque a stop is met with T²/2k, 2.17 J on the robot (12.5 rad/s), 0.08 J on the PLA leg (2.46 rad/s); faster approaches are braked | `test_the_approach_limit_meets_the_stop...` |
| Rig laptop (`rig/run.py`) | `--cap` 1-60 N m, default 60 | Without `--cap` the PLA bench leg ran at 60 N m | `--build pla_bench\|robot` (PLA by default): without `--cap` the build's every-day cap; no higher `--cap` accepted; soft stops in the limiter | `rig/tests/test_rs04.py`, `rig/tests/test_control.py` |
| Browser playground | sliders and the gamepad set the pose directly | The 3D pup could be asked for poses and rates the real leg cannot make | `designer/leg_limits.js`: the firmware's rates and the reach window, clamping. **Not yet called from `designer/sim.js`** (see section 5) | `tools/test-leg-limits.mjs` |
| Python robot sim (`sim/controller_v2.py`) | the controller the firmware ports | no window or soft stops yet | nothing (section 5) | |

The stops alone already rule out a crossed or unreachable leg: a survey of the whole stop box finds every pose
reachable and none crossed, but the stops let the leg reach within 6.1° of a dead point (at both knee-in stops, leg
392 mm). That is why the commanded window has its own 25° margin.

## 2. The torque each build may take

The FEA is linear, so a row whose safety factor is SF at torque T0 carries T0 × SF / target at its target. The targets
are D33's: 2 for every-day cases, 1.2 for rare ones, 1.0 for faults.

### The robot's leg (PA6-CF links and hip frame, D33/D38; CNC 6061 output adapters, D46)

Every day, any pose (from `exports/leg/fea/summary.json`, 18.75 kg a leg):

| Row | SF at 60 N m | Allowable at SF 2 |
|---|---|---|
| **hip_frame E3o**: a motor into the knee-out stop post, its ear past the motor ring | 2.04 | **61.2 N m** |
| stop_post E3, the pin's bearing in the printed web | 2.11 | 63.3 |
| hip_frame E3i, the knee-in stop post between the motors | 2.21 | 66.3 |
| upper_link E2, a motor at its cap against a stalled leg | 2.70 | 81.0 |
| upper_link E3, a link driven into a stop post | 5.63 | 168.9 |
| output_adapter E1, the cap through the 6061 adapter | 22.8 | 683 |

So the every-day cap is **61 N m**, set by the hip frame's stop ear, not by the motor or the adapter.

The peak, in the jump's push only, is set by the knees: the jump's knee force rises with the cap (section 3), and the
weakest knee-driven rare row is the front link's R1, SF 1.38 at 574 N, so 660 N at SF 1.2. The sweep reaches 660 N at
**69 N m**. The other peak rows sit higher: the RS-04's own 120, upper_link R2 135, the AO-L hub dowels 189, the 6061
adapter 1,350. The landing's gearbox torque (79 N m, the leg back-driving the motors) does not grow with the cap.

Continuous: **28.5 N m rms** over a 30.2 s time constant, the RS-04 manual's stall table rated row (section 1.3, item
14; the spec sheet's 40 N m at 50 rpm is a moving rating). The time constant is the winding's R_wc 0.4113 K/W × C_w
73.4 J/K, as the motor heat model on branch `thermal/rs04-motor-heat` takes them
([PR #195](https://github.com/Valpatel/gyropup/pull/195), **pending**: `sim/leg_limits.py` reads its
`exports/leg/thermal/motor_thermal.json` once it merges, and the numbers here are re-derived then).

### The PLA bench leg (docs/motor-day.md)

**12 N m**, every day and peak, from `exports/motor-day/derating.json` (PLA at 25 MPa, every-day targets at the boom
stand's mass). The first failure is the wheel link's R1w, which falls under its target at 15 N m (SF 1.83). The PLA
leg's continuous limit is its face, not the motor: stop when a motor case passes 50 °C (#195's bench limits). The
firmware cannot see the case temperature, so that stays on the bench checklist.

| Build | Every day | Peak (push only, ≤ 0.35 s) | RS-04 `limit_torque` | RMS | Governing |
|---|---|---|---|---|---|
| robot | 61 N m | 69 N m | 69 N m | 28.5 N m (pending #195) | hip_frame E3o; front_link R1 |
| pla_bench | 12 N m | 12 N m | 12 N m | the 50 °C case rule | motor-day derating; first failure wheel_link R1w at 15 |

## 3. What the 120 N m motor buys

The rig's jump (`sim/leg_rig.py`, 18.75 kg a leg, 36 V), each cap applied to both motors for the whole jump:

| Cap (N m) | Jump (mm) | Gearbox push / landing (N m) | Knee push / landing (N) | Peak motor speed (rad/s) |
|---|---|---|---|---|
| 30 | 70.6 | 29.4 / 54.3 | 292 / 410 | 8.6 |
| 45 | 130.9 | 43.6 / 70.5 | 433 / 526 | 11.7 |
| **60** | **151.9** | 57.4 / 77.3 | 574 / 569 | 12.7 |
| 61 (every day) | 152.5 | 58.2 / 76.9 | 584 / 564 | 12.7 |
| 69 (peak) | 156.2 | 65.7 / 79.3 | 659 / 577 | 12.8 |
| 75 | 159.1 | 71.2 / 79.6 | 715 / 579 | 13.0 |
| 90 | 161.1 | 85.1 / 79.1 | 857 / 575 | 12.9 |
| 105 | 158.3 | 99.2 / 78.8 | 998 / 573 | 12.9 |
| **120** | **160.3** | 109.8 / 78.9 | 1,097 / 573 | 13.0 |

Doubling the cap from 60 to 120 N m buys 8 mm of jump (5 %) and nearly doubles the knees' push load (574 to 1,097 N;
the front link's R1 would be at 0.72 of its rare target). The jump is limited by speed, not torque: the motors reach
about 13 of their 15.7 rad/s no-load speed in every push over 60 N m, and back-EMF takes the torque away there.

That is the point of the 120 N m motor. Capped at 60, an RS-04 still makes its 60 N m up to about half its no-load
speed, because its torque-speed line starts at 120. A motor whose peak *is* 60 N m, at the same no-load speed, jumps
only **91.4 mm** (push gearbox 56.1 N m, knee 564 N): its torque falls from stall. The headroom above the cap is what
keeps the torque available while the leg is moving fast. The rest is held in reserve for a stronger leg: a front link
that passes its R1 at higher knee force moves the peak to the next row, the upper link's R2 (135 N m), and so to the
RS-04's own 120.

The firmware's push is also limited by the bus current (`s(V) × 72 A`, section 1), which the rig sweep does not model;
at 36 V it held the HIL's push (at 60 N m) to 50 A and 150 mm, so at mid-pack voltage the bus, not the cap, may set
the push above 60 N m.

## 4. How to regenerate

```
python -m sim.leg_limits --sweep                    # the jump sweep (MuJoCo, a few minutes) and exports/leg/limits.json
python -m sim.leg_limits                            # limits.json from the committed sweep (seconds)
python firmware/balance/tools/gen_limits.py         # include/gp/gp_limits.h
python -m pytest sim/test_leg_limits.py -q
```

Re-run them when the FEA summary, the motor-day derating, the stops or the motor heat model change.

## 5. Not done

- The playground's `designer/leg_limits.js` is not yet called from `designer/sim.js`: the landing highlights reel
  hash-binds `sim.js`, and the gamepad PR changes the same loop and re-records the reel. The hook is
  `const cmd = legLimits.step(state, motionDt, state.robot.info)` before the bob, `cmd.*` for the pose and the drive,
  and `legLimits.fit(...)` into `setPose`.
- The Python robot sim (`sim/controller_v2.py`) has neither the window nor the soft stops.
- The HIL (`firmware/balance/hil/`) was not re-run for this change; its results predate the per-build cap.
- The RMS limit and its time constant are pending #195.
- The firmware cannot see the PLA leg's motor-face temperature.
