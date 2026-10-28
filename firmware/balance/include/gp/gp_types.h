/* Gyropup balance firmware: types shared by the portable core, the MCU build and the host (HIL) build. */
#ifndef GP_TYPES_H
#define GP_TYPES_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* The three CAN buses (docs/body-electrical.md 4), all 1 Mbit/s classic CAN. */
#define GP_BUS_A 0u /* FDCAN1: the left leg's two RS-04s */
#define GP_BUS_B 1u /* FDCAN2: the right leg's two RS-04s */
#define GP_BUS_C 2u /* FDCAN3: the two VESCs, the BMS bridge, the J501's can0 */
#define GP_NBUS 3u

/* One classic CAN frame. Kept at 16 bytes with natural alignment: hil/fwlib.py mirrors it with ctypes. */
typedef struct {
    uint32_t id;     /* 11-bit (ext = 0) or 29-bit (ext = 1) identifier */
    uint8_t len;     /* 0..8 */
    uint8_t ext;     /* 1: extended (29-bit) frame */
    uint8_t data[8];
} gp_can_frame;

/* The only call the portable core makes into the platform (src/mcu/ on the Nucleo, src/host/ in the host library):
 * queue one frame for transmission on a bus. Returns false when the frame could not be queued. */
bool gp_plat_can_send(uint8_t bus, const gp_can_frame *f);

#endif
