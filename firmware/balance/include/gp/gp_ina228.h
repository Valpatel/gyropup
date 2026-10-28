/* TI INA228 (85 V, 20-bit power monitor) on the pack's shunt (docs/body-electrical.md W30-W32): register map, the
 * configuration the firmware writes, and the conversions. Multi-byte registers are big-endian (MSB first).
 *
 *   SHUNT_CAL = 13107.2e6 x CURRENT_LSB x R_SHUNT (x 4 with ADCRANGE = 1); CURRENT_LSB = full scale / 2^19.
 *   1 mOhm (the fuse board, P3): ADCRANGE 0 (+-163.84 mV) -> +-163.84 A, CURRENT_LSB 312.5 uA, SHUNT_CAL 4096.
 *   0.333 mOhm (the Blue Sea 150 A / 50 mV shunt of P0-P2): ADCRANGE 1 (+-40.96 mV) -> +-122.9 A, SHUNT_CAL 4096. */
#ifndef GP_INA228_H
#define GP_INA228_H

#include "gp/gp_types.h"

#define GP_INA228_ADDR 0x40u /* A0 = A1 = GND (the Adafruit 5832's default) */

#define GP_INA228_CONFIG 0x00u
#define GP_INA228_ADC_CONFIG 0x01u
#define GP_INA228_SHUNT_CAL 0x02u
#define GP_INA228_VSHUNT 0x04u
#define GP_INA228_VBUS 0x05u   /* 24 bits, value in 23..4, 195.3125 uV/LSB */
#define GP_INA228_DIETEMP 0x06u /* 16 bits, 7.8125 mC/LSB */
#define GP_INA228_CURRENT 0x07u /* 24 bits, signed value in 23..4, CURRENT_LSB */
#define GP_INA228_MANUFACTURER_ID 0x3Eu /* 0x5449 "TI" */
#define GP_INA228_DEVICE_ID 0x3Fu       /* 0x228x */

#define GP_INA228_VBUS_LSB 195.3125e-6f

/* Shunt resistances of the two builds */
#define GP_SHUNT_FUSE_BOARD_OHM 0.001f
#define GP_SHUNT_BLUE_SEA_OHM 0.000333f

typedef struct {
    float r_shunt;     /* ohm */
    float current_lsb; /* A */
    uint8_t adcrange;  /* 0: +-163.84 mV, 1: +-40.96 mV */
    uint16_t config;
    uint16_t adc_config;
    uint16_t shunt_cal;
} gp_ina228_cfg;

/* The configuration for a shunt: full scale at the ADC's range (ADCRANGE 1 when the 80 A jump fits in 40.96 mV). */
void gp_ina228_setup(gp_ina228_cfg *c, float r_shunt_ohm);

float gp_ina228_vbus(const uint8_t raw[3]);                            /* V */
float gp_ina228_current(const gp_ina228_cfg *c, const uint8_t raw[3]); /* A, + from IN+ to IN- */
float gp_ina228_dietemp(const uint8_t raw[2]);                         /* C */

/* The inverse conversions (an emulated INA228 in the HIL and the tests). */
void gp_ina228_encode_vbus(float v, uint8_t raw[3]);
void gp_ina228_encode_current(const gp_ina228_cfg *c, float a, uint8_t raw[3]);

#endif
