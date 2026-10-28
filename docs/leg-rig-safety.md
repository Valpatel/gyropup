# Leg rig: safety

Read this before the first power-up. Go through the checklist before every session. The tests are in
`docs/leg-bench-tests.md` and the wiring in `docs/leg-rig-wiring.md`.

## What can hurt

- **The leg.** Two motors of up to 120 N m each (the firmware caps them at 60 N m). The five-bar's links scissor at
  the knees and between the upper links and the hip frame. A jump extends the leg 190 mm in under 0.2 s. Keep fingers
  out of the linkage whenever the pack is connected.
- **The carriage.** About 15 kg on the rails. A power cut drops it onto the bumpers (7 J). A hard fault at the
  jump's apex is up to 33 J. The ballast plates are cast iron.
- **The pack.**
  - Two DeWalt FLEXVOLTs in 20 V mode in series (D65): 30-41 V, with no cut-off of their own. They deliver 50-60 A in a jump.
  - The contactor stays closed for 1.0 s after the pendant is let go.
  - The bench supply cannot absorb the motors' regeneration: never run a squat, jump or drop on it.
- **The drop test.** The quick-release pin and the carriage under it.

## The rules

1. **One operator holds the pendant.** Nothing moves unless it is held and the runner has been armed (typing ARM).
   Let go at any doubt. The leg sits down in 0.3 s, and 1.0 s later the contactor opens whatever the software did.
2. **The clear zone.** Nobody within 1.5 m of the leg's front and sides while the pack is connected, the operator
   included. Tape it on the floor. Wear eye protection inside the room.
3. **The pack is the master switch.** Unplug its XT60 before touching the leg, its wiring or the pod. Wait 5 s after
   unplugging: the motors' capacitors discharge.
4. **The bench supply is only for the bench tests.** Use it for B1, B2 and C1-C6, never with the leg on the rig.
5. **Jumps and drops start at or under the start voltage:** 44.5 V - 40 A x the packs' resistance (B6), about 40.5 V
   until B6 has run (a pair fresh off the charger is 41 V: one stand-up brings it under). The runner refuses above it.
6. **The power-cut tests (S5, S6) cut the power by the pendant.** Hold it, let go, and the leg falls. S6 (onto the
   leg's own stops) only after B1 and the main session's rerun clear it.
7. **A pack that is damaged, swollen or hot goes outside onto concrete.** Keep an ABC extinguisher by the door.

## The checklist (each session)

| # | Check | How | OK when |
|---|---|---|---|
| 1 | The pendant and relay | Motors' XT60 unplugged at the pod. Hold the pendant, then let go | The contactor clicks in when held and opens 1.0 s (stopwatch) after release; the runner shows the node's RUN while held |
| 2 | The CAN bus | Power off: an ohmmeter across H and L at the junction | 60 ohm |
| 3 | The motors | `python -m rig.rs04 --iface can0 scan` | both ids (1, 2) answer; the start-up log shows limit_torque 60, canTimeout 2000 and damper 0 |
| 4 | The calibration | `python -m rig.calibrate --check` with the carriage on its bumpers | the leg's length within 5 mm of a tape measure |
| 5 | The packs | A multimeter at the pod's inlet | 33-41 V for stand and squat; at or under the start voltage for a jump or a drop |
| 6 | The tethers | Look | the carriage tether through the plate's tether hole on a locked screwgate, 150 mm slack above the highest jump; the link tether round the wheel link |
| 7 | The bumpers | A rule from the deck to the plate's edge, carriage resting | contact at a leg length of 140 mm (the base and cap seated); S6 only: 74 mm with its shims |
| 8 | The top stop | Look | at its mark above the rails (B5 lowers it onto the carriage: put it back after) |
| 9 | The ballast | Look and torque | the plates retained by the 2 in washer and the 3/8-16 screw at 25 N m |
| 10 | The screws | The paint marks | unbroken on the plate-to-frame M5s, the link screws, the knee nuts and the stop posts |
| 11 | The motors' temperature | The last run's log, or `python -m rig.rs04 --id N watch` | under 40 C before a jump or a drop; under 60 C for anything |
| 12 | The zone | Look | taped, empty, eye protection on; the laptop on battery (or the isolated USB-CAN if it is on mains) |

## If something goes wrong

- **The leg does something unexpected:** let go of the pendant. Do not reach for the leg.
- **A motor faults or the runner aborts:** the run's log says why. Read it before the next run. Clear a fault with
  `python -m rig.rs04 --id N clear` only once the cause is understood.
- **The contactor does not open on release:** unplug the pack's XT60. Do not run again until check 1 passes.
- **A part cracks or a screw backs out:** stop the series. Photograph it, write it down in `exports/rig/runs/notes.md`
  and tell the main session before any repair.
