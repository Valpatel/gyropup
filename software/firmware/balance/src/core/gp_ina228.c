/* INA228 configuration and conversions (TI datasheet SBOSA20: registers 00h-3Fh, 8.1.2 the current and SHUNT_CAL). */
#include "gp/gp_ina228.h"

#include <math.h>

void gp_ina228_setup(gp_ina228_cfg *c, float r_shunt_ohm)
{
    /* the jump's 80 A pulse must fit the range: use the finer 40.96 mV range when it does (with 25 % headroom) */
    c->adcrange = (100.0f * r_shunt_ohm <= 0.04096f) ? 1u : 0u;
    const float v_fs = c->adcrange ? 0.04096f : 0.16384f;
    c->r_shunt = r_shunt_ohm;
    c->current_lsb = v_fs / r_shunt_ohm / 524288.0f;
    const float cal = 13107.2e6f * c->current_lsb * r_shunt_ohm * (c->adcrange ? 4.0f : 1.0f);
    c->shunt_cal = (uint16_t)lroundf(cal);
    c->config = (uint16_t)(c->adcrange ? 0x0010u : 0x0000u); /* CONVDLY 0, no temperature compensation */
    /* ADC_CONFIG: MODE 0xF (continuous bus, shunt and temperature), VBUSCT 150 us (2), VSHCT 280 us (3),
     * VTCT 50 us (0), AVG 4 (1): a full set every (150 + 280 + 50) x 4 = 1.92 ms */
    c->adc_config = (uint16_t)((0xFu << 12) | (2u << 9) | (3u << 6) | (0u << 3) | 1u);
}

static uint32_t rd24(const uint8_t raw[3])
{
    return ((uint32_t)raw[0] << 16) | ((uint32_t)raw[1] << 8) | raw[2];
}

float gp_ina228_vbus(const uint8_t raw[3])
{
    return (float)(rd24(raw) >> 4) * GP_INA228_VBUS_LSB;
}

float gp_ina228_current(const gp_ina228_cfg *c, const uint8_t raw[3])
{
    int32_t v = (int32_t)(rd24(raw) >> 4); /* 20-bit two's complement */
    if (v & 0x80000) {
        v -= 0x100000;
    }
    return (float)v * c->current_lsb;
}

float gp_ina228_dietemp(const uint8_t raw[2])
{
    return (float)(int16_t)((raw[0] << 8) | raw[1]) * 7.8125e-3f;
}

static void wr24(uint32_t v, uint8_t raw[3])
{
    raw[0] = (uint8_t)(v >> 16);
    raw[1] = (uint8_t)(v >> 8);
    raw[2] = (uint8_t)v;
}

void gp_ina228_encode_vbus(float v, uint8_t raw[3])
{
    float c = roundf(v / GP_INA228_VBUS_LSB);
    if (c < 0.0f) c = 0.0f;
    if (c > 524287.0f) c = 524287.0f;
    wr24((uint32_t)c << 4, raw);
}

void gp_ina228_encode_current(const gp_ina228_cfg *c, float a, uint8_t raw[3])
{
    float n = roundf(a / c->current_lsb);
    if (n > 524287.0f) n = 524287.0f;
    if (n < -524288.0f) n = -524288.0f;
    wr24(((uint32_t)(int32_t)n & 0xFFFFFu) << 4, raw);
}
