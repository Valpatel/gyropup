/* The J501 (Jetson) <-> MCU protocol on bus C (the J501's can0), 11-bit frames; docs/body-firmware.md 4.3 is the
 * reference. All multi-byte fields little-endian.
 *
 * 0x110 SETPOINT, Jetson -> MCU, 100 Hz, 8 bytes (each one with a new seq is the heartbeat):
 *   b0-1 speed int16 mm/s | b2-3 yaw rate int16 mrad/s (+ = left) | b4 height uint8 0..200 (0.005 of the range)
 *   b5 lean int8 0.01 rad (+ = look up) | b6 flags: bit0 RUN (stand and balance; 0 = sit), bit1 PEOPLE_NEAR,
 *   bits2-3 JUMP_SEQ (a jump is asked for each time it changes), bits4-7 JUMP_HEIGHT (n/15 of the maximum)
 *   b7 seq uint8
 * 0x111 BENCH, Jetson or laptop -> MCU, on demand (rig profile, while sat): b0 1 = select the scenario in b1
 * 0x120 STATE_A, 200 Hz: pitch int16 1e-4 rad (+ = nose up) | pitch rate int16 1e-3 rad/s | speed int16 mm/s |
 *   yaw rate int16 mrad/s
 * 0x121 STATE_B, 200 Hz: L left, L right uint16 0.1 mm | lean left, lean right int16 1e-4 rad
 * 0x122 STATUS, 200 Hz: b0 mode | b1 flags | b2-3 vbus uint16 10 mV | b4-5 ibus int16 10 mA (+ = discharge) |
 *   b6 reason | b7 seq
 * 0x123 FAULTS, 10 Hz: b0-3 each motor (L front, L rear, R front, R rear): bit7 present, bits0-5 its feedback faults |
 *   b4 bit0-1 the VESCs present, bit2 IMU fresh, bit3 bus voltage fresh, bit4 latched fault | b5 jump height allowed
 *   (0..100 %) | b6 last refused jump's reason | b7 seq */
#ifndef GP_JETSON_H
#define GP_JETSON_H

#include "gp/gp_types.h"

typedef struct {
    float speed;    /* m/s */
    float yaw_rate; /* rad/s */
    float height;   /* 0..1 of the leg range */
    float lean;     /* rad, + = look up */
    bool run, people_near;
    uint8_t jump_seq;    /* 0..3 */
    uint8_t jump_height; /* 0..15 */
    uint8_t seq;
} gp_jet_setpoint;

typedef struct {
    float pitch, pitch_rate, speed, yaw_rate;
    float L[2], lean[2];
    uint8_t mode, flags, reason, seq;
    float vbus, ibus;
} gp_jet_state;

/* status flags (STATUS b1) */
#define GP_JF_STOP_RUN 0x01u    /* the stop relay's coil is powered: the radio says run */
#define GP_JF_MCU_RUN 0x02u     /* MCU_RUN is driven high */
#define GP_JF_LINK_OK 0x04u     /* the Jetson's setpoints are fresh */
#define GP_JF_PEOPLE 0x08u      /* people-near caps active */
#define GP_JF_UVLO_WARN 0x10u   /* resting voltage under 35.0 V (3.5 V a cell) */
#define GP_JF_UVLO_SIT 0x20u    /* resting voltage under 32.0 V (3.2 V a cell): sat, will not stand */
#define GP_JF_JUMP_OK 0x40u     /* a jump would be accepted now */
#define GP_JF_JUMPING 0x80u

bool gp_jet_decode_setpoint(const gp_can_frame *f, gp_jet_setpoint *s);
void gp_jet_encode_setpoint(const gp_jet_setpoint *s, gp_can_frame *f);

void gp_jet_encode_state_a(const gp_jet_state *s, gp_can_frame *f);
void gp_jet_encode_state_b(const gp_jet_state *s, gp_can_frame *f);
void gp_jet_encode_status(const gp_jet_state *s, gp_can_frame *f);

#endif
