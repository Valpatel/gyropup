/* Interrupt handlers (the names ST's startup file's vector table uses). */
#include "board.h"

void NMI_Handler(void)
{
    for (;;) {
    }
}

void HardFault_Handler(void)
{
    HAL_GPIO_WritePin(PORT_MCU_RUN, PIN_MCU_RUN, GPIO_PIN_RESET); /* the relay open; the watchdog resets us */
    for (;;) {
    }
}

void SysTick_Handler(void)
{
    HAL_IncTick();
}

void TIM6_DAC_IRQHandler(void)
{
    HAL_TIM_IRQHandler(&htim_tick);
}

void FDCAN1_IT0_IRQHandler(void)
{
    HAL_FDCAN_IRQHandler(&hfdcan[0]);
}

void FDCAN2_IT0_IRQHandler(void)
{
    HAL_FDCAN_IRQHandler(&hfdcan[1]);
}

void FDCAN3_IT0_IRQHandler(void)
{
    HAL_FDCAN_IRQHandler(&hfdcan[2]);
}

void I2C1_EV_IRQHandler(void)
{
    HAL_I2C_EV_IRQHandler(&hi2c_ina);
}

void I2C1_ER_IRQHandler(void)
{
    HAL_I2C_ER_IRQHandler(&hi2c_ina);
}
