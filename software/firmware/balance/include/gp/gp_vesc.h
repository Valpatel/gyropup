/* VESC (Flipsky 75100) on CAN: extended ids (command << 8 | controller id), big-endian payloads (the VESC firmware's
 * comm_can.c). The firmware drives the wheel in current mode and reads the status messages 1-5. */
#ifndef GP_VESC_H
#define GP_VESC_H

#include "gp/gp_types.h"

#define GP_VESC_SET_CURRENT 1u /* int32 mA */
#define GP_VESC_STATUS_1 9u    /* int32 ERPM, int16 current x10, int16 duty x1000 */
#define GP_VESC_STATUS_2 14u   /* int32 Ah x1e4, int32 Ah charged x1e4 */
#define GP_VESC_STATUS_3 15u   /* int32 Wh x1e4, int32 Wh charged x1e4 */
#define GP_VESC_STATUS_4 16u   /* int16 FET C x10, int16 motor C x10, int16 input current x10, int16 PID pos x50 */
#define GP_VESC_STATUS_5 27u   /* int32 tachometer, int16 input voltage x10 */

typedef struct {
    int32_t erpm;
    float current, duty;          /* status 1: A, -1..1 */
    float ah, ah_charged;         /* status 2 */
    float wh, wh_charged;         /* status 3 */
    float temp_fet, temp_motor;   /* status 4: C */
    float current_in, pid_pos;
    int32_t tach;                 /* status 5 */
    float v_in;
} gp_vesc_status;

void gp_vesc_set_current(uint8_t id, float amps, gp_can_frame *f);

/* A VESC status frame: its controller id and command in *id / *cmd; the matching fields of *s updated.
 * False for anything that is not a status 1-5 frame. */
bool gp_vesc_parse(const gp_can_frame *f, uint8_t *id, uint8_t *cmd, gp_vesc_status *s);

#endif
