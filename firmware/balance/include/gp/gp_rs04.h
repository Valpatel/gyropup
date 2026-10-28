/* RobStride RS-04: the private CAN protocol as the leg rig's rig/rs04.py defines it (29-bit frames, 1 Mbit/s):
 * bits 28-24 the communication type, 23-8 'data area 2', 7-0 the destination (manual 4.1). 16-bit fields scale
 * over 0..65535 by the manual's float_to_uint (clamp, scale, truncate). */
#ifndef GP_RS04_H
#define GP_RS04_H

#include "gp/gp_types.h"

enum {
    GP_RS04_GET_ID = 0,
    GP_RS04_MIT = 1,
    GP_RS04_FEEDBACK = 2,
    GP_RS04_ENABLE = 3,
    GP_RS04_STOP = 4,
    GP_RS04_SET_ZERO = 6,
    GP_RS04_SET_ID = 7,
    GP_RS04_READ = 17,
    GP_RS04_WRITE = 18,
    GP_RS04_FAULT = 21,
    GP_RS04_SAVE = 22,
    GP_RS04_REPORT = 24,
};

/* The 16-bit fields' full scale for the RS-04 (manual 4.1.2 and 4.4) */
#define GP_RS04_P_MAX 12.566370614f /* 4 pi rad */
#define GP_RS04_V_MAX 15.0f         /* rad/s */
#define GP_RS04_T_MAX 120.0f        /* N m */
#define GP_RS04_KP_MAX 5000.0f
#define GP_RS04_KD_MAX 100.0f

/* Parameter indices (manual 4.1.13) the firmware writes or reads */
#define GP_RS04_P_RUN_MODE 0x7005u     /* uint8: 0 operation (MIT) */
#define GP_RS04_P_LIMIT_TORQUE 0x700Bu /* float, N m */
#define GP_RS04_P_MECHPOS 0x7019u      /* float, rad */
#define GP_RS04_P_VBUS 0x701Cu         /* float, V */
#define GP_RS04_P_CAN_TIMEOUT 0x7028u  /* uint32, 1/20000 s */
#define GP_RS04_P_ZERO_STA 0x7029u     /* uint8: 1 -> power-on angle in -pi..pi */
#define GP_RS04_P_DAMPER 0x702Au       /* uint8: power-off anti-backdrive, 0 on */

#define GP_RS04_MODE_RESET 0u
#define GP_RS04_MODE_CAL 1u
#define GP_RS04_MODE_RUN 2u

uint32_t gp_rs04_id(uint8_t kind, uint16_t data2, uint8_t dest);
uint16_t gp_rs04_f2u(float x, float lo, float hi);
float gp_rs04_u2f(uint16_t u, float lo, float hi);

/* host -> motor */
void gp_rs04_mit(uint8_t motor, float p, float v, float kp, float kd, float t, gp_can_frame *f);
void gp_rs04_enable(uint8_t motor, gp_can_frame *f);
void gp_rs04_stop(uint8_t motor, bool clear_fault, gp_can_frame *f);
void gp_rs04_read(uint8_t motor, uint16_t index, gp_can_frame *f);
void gp_rs04_write_u8(uint8_t motor, uint16_t index, uint8_t v, gp_can_frame *f);
void gp_rs04_write_u32(uint8_t motor, uint16_t index, uint32_t v, gp_can_frame *f);
void gp_rs04_write_f32(uint8_t motor, uint16_t index, float v, gp_can_frame *f);

/* motor -> host */
typedef struct {
    uint8_t motor, host, mode, faults; /* faults: the six feedback bits, bit 0 = id bit 16 (under-voltage) */
    float p, v, t, temp_c;
} gp_rs04_feedback;

typedef struct {
    uint8_t motor, host;
    uint16_t index;
    bool ok;
    uint8_t raw[4];
} gp_rs04_param;

typedef struct {
    uint8_t motor, host;
    uint32_t fault, warning;
} gp_rs04_fault;

typedef struct {
    int kind; /* GP_RS04_FEEDBACK, GP_RS04_READ, GP_RS04_FAULT, or -1 */
    gp_rs04_feedback fb;
    gp_rs04_param param;
    gp_rs04_fault fault;
} gp_rs04_msg;

/* A frame a motor sent; false for anything else (11-bit frames, the version frame, a host's own requests). */
bool gp_rs04_parse(const gp_can_frame *f, gp_rs04_msg *m);

float gp_rs04_param_f32(const gp_rs04_param *p);
uint32_t gp_rs04_param_u32(const gp_rs04_param *p);

#endif
