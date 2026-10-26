# Head payload interface

Gyropup carries a payload on its head; the first is the foam-dart turret, which is developed as its own project (D22).
This page is the contract between the two. The simulator holds the robot to it (`head_payload` in each design, and the
`recoil` scenario), so any payload that meets it can be bolted on.

| Item | Budget | Notes |
|---|---|---|
| Mass | ≤ 1.5 kg, including a full magazine | The designer and the physics model count it; the leg and wheel motors are sized with it |
| Centre of mass | ≤ 120 mm above the head plate, centred over the wheel axle | Higher makes balancing slower and falls harder |
| Recoil | ≤ 0.05 N·s per shot (1.3 g dart at 38 m/s) | The `recoil` scenario fires the whole magazine in bursts while standing and driving |
| Magazine | 24 shots, drum or belt | User target; a drum of 24 darts adds roughly 0.2–0.3 kg (estimate) |
| Rate of fire | bursts of 8 at up to 10 shots per second | |
| Power | fused 24 V bus (from the 8S pack), ≤ 40 W average, peaks to be agreed | Flywheel spin-up is the peak |
| Data | CAN-FD (the J501's second port) and USB to the Jetson | Aiming and firing commands come from the Jetson; the balance controller never waits on the payload |
| Safety line | The robot's e-stop and dead-man signal go to the payload; it must not spin up or fire when either is open | Kid safety (D19): muzzle-energy cap, no aiming above a set height, wireless e-stop |
| Mounting | Head plate with a bolt pattern centred on the axle (to be fixed with the turret project) | Heat-set inserts in the printed head plate, or a SendCutSend aluminium plate |
| Reload | Swap the magazine at the reload station, which is the dock (D18) | Gyropup sits down onto the dock, so the magazine sits at a repeatable height and position |

Changes to these numbers are made here and in `designs/*.json` (`head_payload`), then the suite is re-run
(`tools/simulate.py --all`).
