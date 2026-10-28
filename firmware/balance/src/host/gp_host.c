/* The host build's platform: the firmware's application in a shared library (libgp_host.so) that hil/fwlib.py drives
 * through ctypes, one tick at a time. CAN frames the firmware sends wait in a queue for the caller; frames, VN-100
 * bytes and INA228 readings go in by the same entry points the MCU's drivers use. One firmware per process. */
#include <string.h>

#include "gp/gp_app.h"
#include "gp/gp_config.h"

#define TXQ 256u

static gp_config cfg;
static gp_app app;
static struct {
    uint8_t bus;
    gp_can_frame f;
} txq[TXQ];
static unsigned tx_head, tx_tail;
static unsigned tx_dropped;

bool gp_plat_can_send(uint8_t bus, const gp_can_frame *f)
{
    if (tx_head - tx_tail >= TXQ) {
        tx_dropped++;
        return false;
    }
    txq[tx_head % TXQ].bus = bus;
    txq[tx_head % TXQ].f = *f;
    tx_head++;
    return true;
}

/* sizes the Python side checks its mirrors against */
unsigned gp_host_sizeof(int which)
{
    switch (which) {
    case 0: return (unsigned)sizeof(gp_can_frame);
    case 1: return (unsigned)sizeof(gp_snapshot);
    default: return 0;
    }
}

void gp_host_default(int profile)
{
    gp_config_default(&cfg, (uint8_t)profile);
}

void gp_host_set_motor(int i, int id, int bus, int dir, float phi_zero)
{
    if (i < 0 || i > 3) return;
    cfg.motor[i].id = (uint8_t)id;
    cfg.motor[i].bus = (uint8_t)bus;
    cfg.motor[i].dir = (int8_t)dir;
    cfg.motor[i].phi_zero = phi_zero;
}

/* One named number of the configuration; returns 0 when the name is unknown. */
int gp_host_set(const char *key, float v)
{
    if (!strcmp(key, "leg_ff_n")) cfg.ctl.leg_ff_n = v;
    else if (!strcmp(key, "kp_L")) cfg.ctl.legs.kp_L = v;
    else if (!strcmp(key, "kd_L")) cfg.ctl.legs.kd_L = v;
    else if (!strcmp(key, "kp_th")) cfg.ctl.legs.kp_th = v;
    else if (!strcmp(key, "kd_th")) cfg.ctl.legs.kd_th = v;
    else if (!strcmp(key, "theta_trim")) cfg.ctl.theta_trim = v;
    else if (!strcmp(key, "balance")) cfg.ctl.balance = v != 0.0f;
    else if (!strcmp(key, "imu_required")) cfg.imu_required = v != 0.0f;
    else if (!strcmp(key, "vbus_source")) cfg.vbus_source = (uint8_t)v;
    else if (!strcmp(key, "bench_scenario")) cfg.bench_scenario = (uint8_t)v;
    else if (!strcmp(key, "r_pack")) cfg.r_pack = v;
    else if (!strcmp(key, "r_shunt")) cfg.r_shunt = v;
    else if (!strcmp(key, "ina_sign")) cfg.ina_sign = v;
    else if (!strcmp(key, "sit_L")) cfg.sit_L = v;
    else if (!strcmp(key, "wheel_dir_left")) cfg.wheel_dir[0] = (int8_t)v;
    else if (!strcmp(key, "wheel_dir_right")) cfg.wheel_dir[1] = (int8_t)v;
    else return 0;
    return 1;
}

void gp_host_init(uint32_t now_us)
{
    tx_head = tx_tail = 0;
    tx_dropped = 0;
    gp_app_init(&app, &cfg, now_us);
}

int gp_host_tx_pop(uint8_t *bus, gp_can_frame *f)
{
    if (tx_tail == tx_head) return 0;
    *bus = txq[tx_tail % TXQ].bus;
    *f = txq[tx_tail % TXQ].f;
    tx_tail++;
    return 1;
}

void gp_host_can_rx(uint8_t bus, const gp_can_frame *f, uint32_t now_us)
{
    gp_app_can_rx(&app, bus, f, now_us);
}

void gp_host_uart_rx(const uint8_t *data, unsigned n, uint32_t now_us)
{
    gp_app_uart_rx(&app, data, n, now_us);
}

/* An emulated VN-100 packet (encoded, then parsed by the firmware as the UART's bytes would be). */
void gp_host_vn100(float yaw, float pitch, float roll, float gx, float gy, float gz, uint32_t now_us)
{
    gp_vn100_sample s = {yaw, pitch, roll, gx, gy, gz};
    uint8_t b[GP_VN100_PACKET];
    gp_vn100_encode(&s, b);
    gp_app_uart_rx(&app, b, sizeof b, now_us);
}

/* An emulated INA228 reading: the bus voltage and the current through the shunt from IN+ to IN- (A), encoded into
 * the registers the MCU reads and handed to the firmware as raw bytes. */
void gp_host_ina228(float vbus, float current_in_to_out, uint32_t now_us)
{
    uint8_t v[3], i[3];
    gp_ina228_encode_vbus(vbus, v);
    gp_ina228_encode_current(&app.ina, current_in_to_out, i);
    gp_app_ina228(&app, v, i, now_us);
}

int gp_host_tick(uint32_t now_us, int stop_run)
{
    gp_inputs in = {stop_run != 0};
    gp_outputs out;
    gp_app_tick(&app, now_us, &in, &out);
    return out.mcu_run ? 1 : 0;
}

void gp_host_snapshot(gp_snapshot *s)
{
    gp_app_snapshot(&app, s);
    s->tx_drops += tx_dropped;
}

float gp_host_jump_scale(float vrest)
{
    return gp_jump_scale(vrest);
}
