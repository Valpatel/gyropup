/* VectorNav VN-100: the binary output the firmware configures (output register 75: serial ports 1 and 2, rate divisor 1
 * of the 800 Hz IMU rate, group 1 with YawPitchRoll and AngularRate) and its parser.
 *
 *     0xFA  0x01  0x28 0x00  yaw pitch roll (3 x float32 LE, deg)  rates x y z (3 x float32 LE, rad/s)  CRC (BE)
 *
 * 30 bytes at 800 Hz: 240 kbit/s of a 921.6 kbit/s UART. The CRC is CRC-16-CCITT (poly 0x1021, init 0) over the bytes
 * after the sync byte, CRC included: 0 when good. Angles and rates are in the sensor's frame (x forward, y right,
 * z down when it is mounted so): gp_app.c turns them into the robot's (x forward, y left, z up). */
#ifndef GP_VN100_H
#define GP_VN100_H

#include "gp/gp_types.h"

#define GP_VN100_SYNC 0xFAu
#define GP_VN100_PACKET 30u

typedef struct {
    float yaw, pitch, roll; /* deg, VectorNav's 3-2-1 sequence: pitch + = nose up, roll + = right side down */
    float gx, gy, gz;       /* rad/s about the sensor's x, y, z */
} gp_vn100_sample;

typedef struct {
    uint8_t buf[GP_VN100_PACKET];
    uint8_t n;
    uint32_t packets, crc_errors, resyncs;
} gp_vn100_parser;

void gp_vn100_init(gp_vn100_parser *p);

/* Feed received bytes; returns the number of good packets decoded, the newest one in *out. */
int gp_vn100_feed(gp_vn100_parser *p, const uint8_t *data, size_t n, gp_vn100_sample *out);

uint16_t gp_vn100_crc(const uint8_t *d, size_t n);

/* A packet as the sensor sends it (the HIL's emulated VN-100 and the tests); returns GP_VN100_PACKET. */
size_t gp_vn100_encode(const gp_vn100_sample *s, uint8_t out[GP_VN100_PACKET]);

/* An ASCII command "$<body>*XX\r\n" with its 8-bit XOR checksum; returns its length (0 if it does not fit). */
size_t gp_vn100_command(const char *body, char *out, size_t cap);

#endif
