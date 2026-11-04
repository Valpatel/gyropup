# PEAK PCAN-USB (the configuration CAN adapter)

The USB-to-CAN adapter the owner uses with the [RS-04 motor tool](../../../docs/rs04-motor-tool.md): on a laptop or
the robot computer it becomes a SocketCAN interface (`can0`) through Linux's `peak_usb` driver, and the bridge
(`rig/rs04_bridge.py`) speaks to the motors through it. **The owner's own adapter** (the owner: "probably a PEAK
Pcan"); not bought for the project, its model and serial not recorded.

The catalogue also has cheaper candleLight (gs_usb) adapters for the leg rig and the robot: the BTT U2C V2.1
(`catalog/rig.json`), an isolated InnoMaker USB2CAN, the CANable 2.0 and the FYSETC UCAN (`catalog/alternates.json`,
`catalog/sourcing.json`). The deployment and the bridge accept both drivers.

```mermaid
flowchart LR
  PC["laptop or Jetson<br/>peak_usb: can0"] -->|"USB"| A["PCAN-USB<br/>D-Sub 9 male"]
  A -->|"CAN H, L, GND<br/>1 Mbit/s"| T["120 ohm"]
  T --- M["RS-04 (one at a time when new)"]
  M --- T2["120 ohm"]
```

## References

- PEAK-System's PCAN-USB page and user manual ([peak-system.com](https://www.peak-system.com/)), not kept. The
  catalogued listing: `catalog/alternates.json` (IPEH-002021, and IPEH-002022 opto-isolated).
- Linux's `peak_usb` SocketCAN driver ([kernel docs](https://docs.kernel.org/networking/can.html)).

## Interfaces

The D-Sub 9 pinout, termination and isolation: [interfaces.md](interfaces.md).

## Config and profiles

The bit rate and interface set-up are the deployment's: [deploy/jetson](../../../deploy/jetson/README.md) brings up any
`peak_usb` or `gs_usb` interface at 1 Mbit/s (`/etc/gyropup/can.env`) and can give it a stable name by USB port or
serial (`can-names.conf`). By hand: `sudo ip link set can0 up type can bitrate 1000000`.

## Driver

The kernel's `peak_usb`; the RS-04 protocol over it is [`rig/rs04.py`](../../../rig/rs04.py) and the browser's bridge
[`rig/rs04_bridge.py`](../../../rig/rs04_bridge.py).

## Inventory

[`inventory.json`](inventory.json): 1 held (the owner's), model and serial not recorded.

## Bring-up and tests

The adapter's part of the [RS-04 bring-up](../../actuators/rs04/bring-up.md), steps 1-4: the bus at about 60 ohm, the
`can` link from `peak_usb`, `ERROR-ACTIVE` at 1 Mbit/s, the bridge connected.

## Open questions

- The exact model (isolated or not) and its serial. `sudo deploy/jetson/install.sh --list-can` shows a USB serial
  only if the adapter reports one; a PCAN-USB may not (it has a device number set by PEAK's tools instead), so
  name it by its USB port (`path=`) and read the serial from its label.
- A GH1.25-to-D-Sub 9 lead for the RS-04 is not in the repository yet.
