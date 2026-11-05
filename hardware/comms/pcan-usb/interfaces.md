# PCAN-USB interfaces

```mermaid
flowchart LR
  U["USB"] --> A["PCAN-USB"]
  A --> D["D-Sub 9 male<br/>2 CAN_L, 7 CAN_H, 3 GND"]
```

| Item | Value | Source |
|---|---|---|
| Host | USB, Linux `peak_usb` (SocketCAN), a `can` link named `can0` or as `can-names.conf` says | `deploy/jetson/`; `rig/rs04_bridge.py` |
| CAN connector | D-Sub 9 male, the CiA 303-1 convention: pin 2 CAN_L, pin 7 CAN_H, pin 3 GND (check the adapter's own manual) | general CAN practice; the manual is not kept |
| Termination | none built in: a 120 ohm at each end of the bus | the RS-04 bring-up, step 1 |
| Bit rate | 1 Mbit/s classic CAN for the RS-04s and the robot's buses | `rig/rs04.py`; docs/body-electrical.md 4 |
| Isolation | the IPEH-002022 is opto-isolated, the IPEH-002021 is not: use isolation when the laptop is on mains | `catalog/alternates.json`; docs/leg-rig-wiring.md |
| On the robot | only on a leg's bus with the balance MCU off: two masters never command the same motors | [the RS-04 interfaces](../../actuators/rs04/interfaces.md) |
