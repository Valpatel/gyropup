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
| Aiming laser | Green, mounted beside the barrel, Class 1 or low-power Class 2 (≤ 1 mW) | Shown in the simulator; it follows the never-above-horizontal rule, so it never reaches eye height from a robot this size |
| Range | Knee-height targets out to about 4.7 m with foam balls at 21.3 m/s (70 fps) without aiming upwards; the `targets` scenario knocks all five down at 3.0–4.2 m | Gyropup stands tall to shoot; a higher muzzle reaches further |
| Reload | The dock pours counted balls into the hopper (D18; research/turret-launcher-study.md §8.4) | Gyropup sits down onto the dock, so the hopper's fill flap sits at a repeatable height and position |

Changes to these numbers are made here and in `designs/*.json` (`head_payload`), then the suite is re-run
(`tools/simulate.py --all`).
