# VectorNav VN-100 Rugged IMU

The balance loop's pitch and pitch rate: the IMU on the balance MCU's USART1, read at 800 Hz in VectorNav's binary
format ([D6](../../../docs/program/decisions.yaml)). **The owner's own unit** (`docs/body-plan.md`, `docs/cad-plan.md`): not
bought for the project and not yet on the bench.

```mermaid
flowchart LR
  BUCK["5 V buck (W28)"] -->|"4.5-5.5 V"| VN["VN-100 Rugged<br/>Harwin M80 10-pin"]
  VN -->|"3 V serial TTL<br/>921600 baud, binary, 800 Hz"| MCU["balance MCU<br/>USART1 PA9 / PA10"]
  MCU -->|"VNWRG at every boot"| VN
```

## References

- The VN-100 Rugged STEP and its mechanical drawing VN-100-CR-ASM rev 7.0.0, kept locally only (proprietary notice,
  no redistribution): where from and when in
  [references/vendor/vectornav-vn-100-rugged/SOURCE.txt](../../vendor/vectornav-vn-100-rugged/SOURCE.txt).
- The user manual and the register reference: VectorNav's site ([vectornav.com](https://www.vectornav.com/)), not kept.
- Dimensions, mounting and connector: `catalog/power_electronics.json` (`vectornav-vn-100-rugged`).

## Interfaces

Power, the 10-pin connector, the serial link and the mounting: [interfaces.md](interfaces.md).

## Config and profiles

[`config/registers.json`](config/registers.json): the three register writes the firmware sends at every boot (ASCII
output off, binary output on register 75, 921600 baud), each checked against `firmware/balance/src/mcu/board.c` by
`tools/check-hardware.py`. Nothing is saved in the sensor: it is set up again at each power-up.

## Driver

[`firmware/balance/src/core/gp_vn100.c`](../../../software/firmware/balance/src/core/gp_vn100.c) parses the 30-byte binary
packet and checks its CRC (`include/gp/gp_vn100.h`); `src/mcu/board.c` sends the register writes and runs the UART
on DMA.

## Inventory

[`inventory.json`](inventory.json): 1 held (the owner's), serial not read yet.

## Bring-up and tests

Not yet. On the bench (open in [docs/body-firmware.md](../../../docs/software/body-firmware.md)): which of the sensor's two
serial ports the harness uses, the 921600 baud change at every boot, and the mounting axes; then the firmware's IMU
freshness bit in the MCU's FAULTS frame (0x123) and the pitch against a level.

## Open questions

- Its mounting rotation is assumed aligned (x forward, y right, z down); a rotation is not in the code yet.
- Which serial port: both are configured (register 75, async mode 3).
- The model number and serial of the owner's unit are not recorded.
