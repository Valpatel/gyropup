# Balance MCU interfaces

```mermaid
flowchart LR
  B["5 V buck (W28)"] -->|"E5V"| N["Nucleo-G474RE"]
  N -->|"PA11/12, PB12/13, PA8/15"| T["3 x CAN Pal<br/>TJA1051T/3, 120 ohm on"]
```

| Signal | Pin | To | Source |
|---|---|---|---|
| FDCAN1 RX / TX (bus A) | PA11 / PA12 (AF9) | CAN Pal 1: the left leg | docs/body-firmware.md 6 |
| FDCAN2 RX / TX (bus B) | PB12 / PB13 (AF9) | CAN Pal 2: the right leg | docs/body-firmware.md 6 |
| FDCAN3 RX / TX (bus C) | PA8 / PA15 (AF11) | CAN Pal 3: the VESCs and the Jetson | docs/body-firmware.md 6 |
| USART1 TX / RX | PA9 / PA10 (AF7) | the VN-100's 3 V serial port | docs/body-firmware.md 6 |
| I2C1 SCL / SDA | PB8 / PB9 (AF4) | the INA228 at 0x40 | docs/body-firmware.md 6 |
| STOP sense | PC0 | the stop relay coil's + side through 27 k / 10 k | docs/body-firmware.md 6 |
| MCU_RUN | PC1 | the stop relay's MOSFET gate | docs/body-firmware.md 6 |
| Clock | PF0 / PF1 | the Nucleo's 24 MHz crystal; 170 MHz SYSCLK, FDCAN at 85 MHz | docs/body-firmware.md 6 |
| SWD | PA13 / PA14 | the on-board ST-LINK | docs/body-firmware.md 6 |
| Power | E5V | the 5 V buck (W28, W29) | docs/body-electrical.md |

| Bus | Bit rate | Termination | Source |
|---|---|---|---|
| A, B, C | 1 Mbit/s classic CAN, 80 % sample point | 120 ohm on each CAN Pal and at each bus's far end | docs/body-electrical.md 4 |

The transceivers are 3 x Adafruit CAN Pal 5708 (TJA1051T/3, a switchable 120 ohm; `catalog/body.json`).
