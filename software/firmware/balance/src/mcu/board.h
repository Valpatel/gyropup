/* The Nucleo-G474RE as the balance firmware uses it (docs/body-firmware.md 6 has the pin table). */
#ifndef BOARD_H
#define BOARD_H

#include "gp/gp_types.h"
#include "stm32g4xx_hal.h"

/* pins */
#define PIN_STOP_SENSE GPIO_PIN_0  /* PC0: the stop relay coil's + side through 27k/10k (closed = run) */
#define PORT_STOP_SENSE GPIOC
#define PIN_MCU_RUN GPIO_PIN_1     /* PC1: the gate of the relay's low-side MOSFET (100k pull-down on the gate) */
#define PORT_MCU_RUN GPIOC
#define PIN_LED GPIO_PIN_5         /* PA5: LD2 */
#define PORT_LED GPIOA

extern FDCAN_HandleTypeDef hfdcan[GP_NBUS];
extern UART_HandleTypeDef huart_vn;
extern I2C_HandleTypeDef hi2c_ina;
extern TIM_HandleTypeDef htim_tick, htim_us;
extern IWDG_HandleTypeDef hiwdg;
extern volatile uint32_t tick_due;

bool board_clock(void);        /* HSE 24 MHz -> 170 MHz; false if the crystal does not start */
void board_init(void);         /* GPIO, FDCAN x3, USART1 + DMA, I2C1, TIM2 (us), TIM6 (1 kHz) */
uint32_t board_us(void);
void board_watchdog_start(void);

/* CAN: frames the ISRs received, and the queue the tick fills */
bool board_can_pop(uint8_t bus, gp_can_frame *f);
void board_can_flush(void);

/* VN-100 on USART1: configure it, then the bytes the DMA has brought since the last call */
void board_vn100_setup(void);
size_t board_vn100_bytes(const uint8_t **p);

/* INA228 on I2C1 */
bool board_ina228_setup(uint16_t config, uint16_t adc_config, uint16_t shunt_cal);
void board_ina228_start(void);
bool board_ina228_take(uint8_t vbus[3], uint8_t current[3]);

#endif
