/* The balance firmware on the Nucleo-G474RE: bring the board up, then run the application's 1 kHz tick
 * (gp_app.h) in thread mode whenever TIM6 says one is due. The ISRs only queue (CAN) or fill buffers (DMA, I2C);
 * everything the application owns is touched here alone. */
#include "board.h"
#include "gp/gp_app.h"

#ifndef GP_DEFAULT_PROFILE
#define GP_DEFAULT_PROFILE GP_PROFILE_ROBOT
#endif

static gp_app app;
static gp_config cfg;
volatile uint32_t loop_us_max, overruns;

static void halt_blinking(void)
{
    for (uint32_t k = 0;; k++) { /* no crystal: never drive anything */
        HAL_GPIO_WritePin(PORT_MCU_RUN, PIN_MCU_RUN, GPIO_PIN_RESET);
        HAL_GPIO_TogglePin(PORT_LED, PIN_LED);
        HAL_Delay(k % 2 ? 100 : 900);
    }
}

int main(void)
{
    HAL_Init();
    const bool clock_ok = board_clock();
    board_init();
    if (!clock_ok) {
        halt_blinking();
    }
    gp_config_default(&cfg, GP_DEFAULT_PROFILE);
    gp_app_init(&app, &cfg, board_us());
    board_ina228_setup(app.ina.config, app.ina.adc_config, app.ina.shunt_cal); /* absent: no readings, the robot stays sat */
    board_vn100_setup();
    board_watchdog_start();
    uint32_t last = 0;
    for (;;) {
        if (tick_due == last) {
            continue;
        }
        if (tick_due - last > 1u) {
            overruns++;
        }
        last = tick_due;
        const uint32_t t0 = board_us();
        gp_can_frame f;
        for (uint8_t b = 0; b < GP_NBUS; b++) {
            while (board_can_pop(b, &f)) {
                gp_app_can_rx(&app, b, &f, t0);
            }
        }
        const uint8_t *p;
        size_t n;
        while ((n = board_vn100_bytes(&p)) > 0) {
            gp_app_uart_rx(&app, p, n, t0);
        }
        uint8_t vb[3], cur[3];
        if (board_ina228_take(vb, cur)) {
            gp_app_ina228(&app, vb, cur, t0);
        }
        const gp_inputs in = {HAL_GPIO_ReadPin(PORT_STOP_SENSE, PIN_STOP_SENSE) == GPIO_PIN_SET};
        gp_outputs out;
        gp_app_tick(&app, t0, &in, &out);
        HAL_GPIO_WritePin(PORT_MCU_RUN, PIN_MCU_RUN, out.mcu_run ? GPIO_PIN_SET : GPIO_PIN_RESET);
        HAL_GPIO_WritePin(PORT_LED, PIN_LED, out.led ? GPIO_PIN_SET : GPIO_PIN_RESET);
        board_can_flush();
        if (app.tick % 2u == 0u) {
            board_ina228_start(); /* 500 Hz: VBUS then CURRENT, interrupt-driven */
        }
        HAL_IWDG_Refresh(&hiwdg);
        const uint32_t dt = board_us() - t0;
        if (dt > loop_us_max) {
            loop_us_max = dt;
        }
    }
}
