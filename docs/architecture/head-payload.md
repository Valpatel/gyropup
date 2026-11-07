# Head payload interface

Gyropup carries a payload on its head; the first is the foam-ball turret, which is developed as its own project (D22).
This page is the contract between the two. The simulator holds the robot to it (`head_payload` in each design, and the
`recoil` scenario), so any payload that meets it can be bolted on.

| Item | Budget | Notes |
|---|---|---|
| Mass | ≤ 1.5 kg, including a full hopper | The designer and the physics model count it; the leg and wheel motors are sized with it |
| Centre of mass | ≤ 120 mm above the head plate, centred over the wheel axle | Higher makes balancing slower and falls harder |
| Recoil | ≤ 0.05 N·s per shot (a 1.83 g foam ball at 70 fps is 0.039 N·s) | The `recoil` scenario fires the whole magazine in bursts while standing and driving |
| Magazine | 24 shots or more | User target. The CAD turret (cad/turret.py) has a hopper of 30 Rival-size foam balls (22.7 mm, 55 g of balls); the simulator fires them |
| Rate of fire | bursts of 8 at up to 10 shots per second | |
| Power | fused 24 V bus (from the 8S pack), ≤ 40 W average, peaks to be agreed | Flywheel spin-up is the peak |
| Data | CAN-FD (the J501's second port) and USB to the Jetson | Aiming and firing commands come from the Jetson; the balance controller never waits on the payload |
| Safety line | The robot's e-stop and dead-man signal go to the payload; it must not spin up or fire when either is open | Kid safety (D19): muzzle-energy cap, no aiming above a set height, wireless e-stop |
| Mounting | Head plate with a bolt pattern centred on the axle (to be fixed with the turret project) | Heat-set inserts in the printed head plate, or a SendCutSend aluminium plate |
| Aiming laser | A green laser pointer module beside the barrel, in the same Ø7 mount (the owner, 2026-11-04: it replaces the red Class 2 dot; the catalogue's Quarton VLM-520-73 LPT, 520 nm, < 1 mW, Ø7 x 26.1, is one that fits). Its class is the one on the module's label: the kid-safety rule allows a labelled Class 2 (< 1 mW) only, never 3R or IIIa. The firmware lights it only while armed (firmware/turret/turret_fw.py, its interlock; test_firmware.py laser_only_when_armed) | Since D77 the barrel aims up to its +12 deg stop and fires up to +10 deg. From a 0.55-0.85 m muzzle the beam at +12 deg climbs 0.21 m a metre: through a child's eye height (about 1.1 m) 1.2-2.6 m out and an adult's (1.6 m) 3.5-4.9 m out, so a lit beam can cross faces in the play area. Open item for the owner (#201): ordinary green pointer modules are Class 2 or 3R, not Class 1, and Class 2 relies on the blink reflex, which is not reliable for children: accept the labelled Class 2 module once it is in hand, or keep the beam dark above level |
| Range | Knee-height targets out to about 4.7 m with foam balls at 21.3 m/s (70 fps) with a level barrel (further with it raised, within the stops, D77); the `targets` scenario knocks all five down at 3.0–4.2 m | Gyropup stands tall to shoot; a higher muzzle reaches further |
| Reload | The dock pours counted balls into the hopper (D18; research/turret-launcher-study.md §8.4) | Gyropup sits down onto the dock, so the hopper's fill flap sits at a repeatable height and position |

Changes to these numbers are made here and in `designs/*.json` (`head_payload`), then the suite is re-run
(`tools/simulate.py --all`).
