/* The Nucleo-G474RE's peripherals for the balance firmware: clocks, the three FDCANs at 1 Mbit/s classic, the VN-100's
 * UART with a circular DMA, the INA228 on I2C, the 1 kHz tick and the microsecond clock, the watchdog. */
#include "board.h"

#include <string.h>

#include "gp/gp_vn100.h"

FDCAN_HandleTypeDef hfdcan[GP_NBUS];
UART_HandleTypeDef huart_vn;
DMA_HandleTypeDef hdma_vn;
I2C_HandleTypeDef hi2c_ina;
TIM_HandleTypeDef htim_tick, htim_us;
IWDG_HandleTypeDef hiwdg;
volatile uint32_t tick_due;

/* ------------------------------------------------------------------------------------------- clocks */

bool board_clock(void)
{
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};
    RCC_PeriphCLKInitTypeDef per = {0};
    HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1_BOOST);
    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE | RCC_OSCILLATORTYPE_LSI;
    osc.HSEState = RCC_HSE_ON;
    osc.LSIState = RCC_LSI_ON;
    osc.PLL.PLLState = RCC_PLL_ON;
    osc.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    osc.PLL.PLLM = RCC_PLLM_DIV6;  /* 24 MHz / 6 = 4 MHz */
    osc.PLL.PLLN = 85;             /* 340 MHz VCO */
    osc.PLL.PLLP = RCC_PLLP_DIV2;
    osc.PLL.PLLQ = RCC_PLLQ_DIV4;  /* 85 MHz: the FDCAN kernel clock */
    osc.PLL.PLLR = RCC_PLLR_DIV2;  /* 170 MHz SYSCLK */
    if (HAL_RCC_OscConfig(&osc) != HAL_OK) {
        return false; /* no crystal: CAN at 1 Mbit/s needs it (HSI's 1 % is outside the 0.78 % this timing allows) */
    }
    clk.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider = RCC_SYSCLK_DIV1;
    clk.APB1CLKDivider = RCC_HCLK_DIV1;
    clk.APB2CLKDivider = RCC_HCLK_DIV1;
    if (HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_4) != HAL_OK) {
        return false;
    }
    per.PeriphClockSelection = RCC_PERIPHCLK_FDCAN | RCC_PERIPHCLK_USART1 | RCC_PERIPHCLK_I2C1;
    per.FdcanClockSelection = RCC_FDCANCLKSOURCE_PLL;
    per.Usart1ClockSelection = RCC_USART1CLKSOURCE_PCLK2;
    per.I2c1ClockSelection = RCC_I2C1CLKSOURCE_PCLK1;
    return HAL_RCCEx_PeriphCLKConfig(&per) == HAL_OK;
}

/* ------------------------------------------------------------------------------------------- GPIO */

static void pin_af(GPIO_TypeDef *port, uint32_t pins, uint8_t af, uint32_t pull, uint32_t mode)
{
    GPIO_InitTypeDef g = {0};
    g.Pin = pins;
    g.Mode = mode;
    g.Pull = pull;
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    g.Alternate = af;
    HAL_GPIO_Init(port, &g);
}

static void gpio_init(void)
{
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();
    HAL_GPIO_WritePin(PORT_MCU_RUN, PIN_MCU_RUN, GPIO_PIN_RESET); /* the relay open until the firmware says run */
    HAL_GPIO_WritePin(PORT_LED, PIN_LED, GPIO_PIN_RESET);
    GPIO_InitTypeDef g = {0};
    g.Pin = PIN_MCU_RUN;
    g.Mode = GPIO_MODE_OUTPUT_PP;
    g.Pull = GPIO_PULLDOWN;
    g.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(PORT_MCU_RUN, &g);
    g.Pin = PIN_LED;
    g.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(PORT_LED, &g);
    g.Pin = PIN_STOP_SENSE;
    g.Mode = GPIO_MODE_INPUT;
    g.Pull = GPIO_PULLDOWN; /* an open wire reads stop */
    HAL_GPIO_Init(PORT_STOP_SENSE, &g);
    /* FDCAN1 PA11 RX / PA12 TX, FDCAN2 PB12 RX / PB13 TX (AF9); FDCAN3 PA8 RX / PA15 TX (AF11) */
    pin_af(GPIOA, GPIO_PIN_11 | GPIO_PIN_12, GPIO_AF9_FDCAN1, GPIO_NOPULL, GPIO_MODE_AF_PP);
    pin_af(GPIOB, GPIO_PIN_12 | GPIO_PIN_13, GPIO_AF9_FDCAN2, GPIO_NOPULL, GPIO_MODE_AF_PP);
    pin_af(GPIOA, GPIO_PIN_8 | GPIO_PIN_15, GPIO_AF11_FDCAN3, GPIO_NOPULL, GPIO_MODE_AF_PP);
    /* USART1 PA9 TX / PA10 RX (AF7): the VN-100 */
    pin_af(GPIOA, GPIO_PIN_9 | GPIO_PIN_10, GPIO_AF7_USART1, GPIO_PULLUP, GPIO_MODE_AF_PP);
    /* I2C1 PB8 SCL / PB9 SDA (AF4): the INA228 (the breakout's pull-ups) */
    pin_af(GPIOB, GPIO_PIN_8 | GPIO_PIN_9, GPIO_AF4_I2C1, GPIO_NOPULL, GPIO_MODE_AF_OD);
}

/* ------------------------------------------------------------------------------------------- CAN */

#define RXQ 64u
#define TXQ 32u
static struct {
    gp_can_frame rx[RXQ];
    volatile uint32_t rx_head, rx_tail; /* the ISR writes head, the tick reads tail */
    gp_can_frame tx[TXQ];
    uint32_t tx_head, tx_tail;          /* the tick only */
    uint32_t rx_lost, tx_lost;
} canq[GP_NBUS];

static int bus_of(const FDCAN_HandleTypeDef *h)
{
    return h->Instance == FDCAN1 ? 0 : h->Instance == FDCAN2 ? 1 : 2;
}

static void fdcan_init(void)
{
    static FDCAN_GlobalTypeDef *const inst[GP_NBUS] = {FDCAN1, FDCAN2, FDCAN3};
    static const IRQn_Type irq[GP_NBUS] = {FDCAN1_IT0_IRQn, FDCAN2_IT0_IRQn, FDCAN3_IT0_IRQn};
    __HAL_RCC_FDCAN_CLK_ENABLE();
    for (int b = 0; b < (int)GP_NBUS; b++) {
        FDCAN_HandleTypeDef *h = &hfdcan[b];
        memset(h, 0, sizeof *h);
        h->Instance = inst[b];
        h->Init.ClockDivider = FDCAN_CLOCK_DIV1;
        h->Init.FrameFormat = FDCAN_FRAME_CLASSIC;
        h->Init.Mode = FDCAN_MODE_NORMAL;
        h->Init.AutoRetransmission = ENABLE;
        h->Init.TransmitPause = DISABLE;
        h->Init.ProtocolException = DISABLE;
        /* 85 MHz / 1 = 85 tq a bit: 1 + 67 + 17, the sample point at 80 %, SJW 17 -> 1 Mbit/s */
        h->Init.NominalPrescaler = 1;
        h->Init.NominalSyncJumpWidth = 17;
        h->Init.NominalTimeSeg1 = 67;
        h->Init.NominalTimeSeg2 = 17;
        h->Init.DataPrescaler = 1;
        h->Init.DataSyncJumpWidth = 1;
        h->Init.DataTimeSeg1 = 1;
        h->Init.DataTimeSeg2 = 1;
        h->Init.StdFiltersNbr = 0;
        h->Init.ExtFiltersNbr = 0;
        h->Init.TxFifoQueueMode = FDCAN_TX_FIFO_OPERATION;
        if (HAL_FDCAN_Init(h) != HAL_OK) continue;
        /* everything into FIFO 0 (the firmware sorts by id); no remote frames */
        HAL_FDCAN_ConfigGlobalFilter(h, FDCAN_ACCEPT_IN_RX_FIFO0, FDCAN_ACCEPT_IN_RX_FIFO0, FDCAN_REJECT_REMOTE, FDCAN_REJECT_REMOTE);
        HAL_FDCAN_ActivateNotification(h, FDCAN_IT_RX_FIFO0_NEW_MESSAGE, 0);
        HAL_NVIC_SetPriority(irq[b], 1, 0);
        HAL_NVIC_EnableIRQ(irq[b]);
        HAL_FDCAN_Start(h);
    }
}

void HAL_FDCAN_RxFifo0Callback(FDCAN_HandleTypeDef *h, uint32_t its)
{
    (void)its;
    const int b = bus_of(h);
    FDCAN_RxHeaderTypeDef hdr;
    uint8_t d[8];
    while (HAL_FDCAN_GetRxFifoFillLevel(h, FDCAN_RX_FIFO0) > 0 && HAL_FDCAN_GetRxMessage(h, FDCAN_RX_FIFO0, &hdr, d) == HAL_OK) {
        if (canq[b].rx_head - canq[b].rx_tail >= RXQ) {
            canq[b].rx_lost++;
            continue;
        }
        gp_can_frame *f = &canq[b].rx[canq[b].rx_head % RXQ];
        f->id = hdr.Identifier;
        f->ext = hdr.IdType == FDCAN_EXTENDED_ID;
        f->len = (uint8_t)(hdr.DataLength > 8u ? 8u : hdr.DataLength);
        memcpy(f->data, d, 8);
        __DMB();
        canq[b].rx_head++;
    }
}

bool board_can_pop(uint8_t bus, gp_can_frame *f)
{
    if (canq[bus].rx_tail == canq[bus].rx_head) return false;
    *f = canq[bus].rx[canq[bus].rx_tail % RXQ];
    __DMB();
    canq[bus].rx_tail++;
    return true;
}

void board_can_flush(void)
{
    for (int b = 0; b < (int)GP_NBUS; b++) {
        while (canq[b].tx_tail != canq[b].tx_head && HAL_FDCAN_GetTxFifoFreeLevel(&hfdcan[b]) > 0) {
            const gp_can_frame *f = &canq[b].tx[canq[b].tx_tail % TXQ];
            FDCAN_TxHeaderTypeDef hdr = {0};
            hdr.Identifier = f->id;
            hdr.IdType = f->ext ? FDCAN_EXTENDED_ID : FDCAN_STANDARD_ID;
            hdr.TxFrameType = FDCAN_DATA_FRAME;
            hdr.DataLength = f->len; /* classic frames: FDCAN_DLC_BYTES_n == n on the G4 */
            hdr.ErrorStateIndicator = FDCAN_ESI_ACTIVE;
            hdr.BitRateSwitch = FDCAN_BRS_OFF;
            hdr.FDFormat = FDCAN_CLASSIC_CAN;
            hdr.TxEventFifoControl = FDCAN_NO_TX_EVENTS;
            if (HAL_FDCAN_AddMessageToTxFifoQ(&hfdcan[b], &hdr, f->data) != HAL_OK) break;
            canq[b].tx_tail++;
        }
    }
}

bool gp_plat_can_send(uint8_t bus, const gp_can_frame *f)
{
    if (bus >= GP_NBUS || canq[bus].tx_head - canq[bus].tx_tail >= TXQ) {
        if (bus < GP_NBUS) canq[bus].tx_lost++;
        return false;
    }
    canq[bus].tx[canq[bus].tx_head % TXQ] = *f;
    canq[bus].tx_head++;
    return true;
}

/* ------------------------------------------------------------------------------------------- the VN-100 */

#define VN_BUF 1024u
static uint8_t vn_buf[VN_BUF];
static uint32_t vn_pos;

static void uart_init(uint32_t baud)
{
    huart_vn.Instance = USART1;
    huart_vn.Init.BaudRate = baud;
    huart_vn.Init.WordLength = UART_WORDLENGTH_8B;
    huart_vn.Init.StopBits = UART_STOPBITS_1;
    huart_vn.Init.Parity = UART_PARITY_NONE;
    huart_vn.Init.Mode = UART_MODE_TX_RX;
    huart_vn.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    huart_vn.Init.OverSampling = UART_OVERSAMPLING_16;
    huart_vn.Init.OneBitSampling = UART_ONE_BIT_SAMPLE_DISABLE;
    huart_vn.Init.ClockPrescaler = UART_PRESCALER_DIV1;
    huart_vn.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_RXOVERRUNDISABLE_INIT;
    huart_vn.AdvancedInit.OverrunDisable = UART_ADVFEATURE_OVERRUN_DISABLE; /* a lost byte is a CRC error, not a stop */
    HAL_UART_DeInit(&huart_vn);
    HAL_UART_Init(&huart_vn);
}

static void vn_send(const char *body)
{
    char cmd[64];
    const size_t n = gp_vn100_command(body, cmd, sizeof cmd);
    HAL_UART_Transmit(&huart_vn, (uint8_t *)cmd, (uint16_t)n, 20);
    HAL_Delay(20);
}

void board_vn100_setup(void)
{
    __HAL_RCC_USART1_CLK_ENABLE();
    __HAL_RCC_DMAMUX1_CLK_ENABLE();
    __HAL_RCC_DMA1_CLK_ENABLE();
    /* at the factory 115200 baud: ASCII output off, the binary output (register 75: both serial ports, divisor 1 of the
     * 800 Hz IMU rate, group 1: YawPitchRoll + AngularRate), then 921600 baud; the same again at 921600 in case the
     * sensor was already there. Volatile: the sensor is set up at every boot. */
    uart_init(115200);
    vn_send("VNWRG,06,0");
    vn_send("VNWRG,75,3,1,01,0028");
    vn_send("VNWRG,05,921600");
    uart_init(921600);
    vn_send("VNWRG,06,0");
    vn_send("VNWRG,75,3,1,01,0028");
    hdma_vn.Instance = DMA1_Channel1;
    hdma_vn.Init.Request = DMA_REQUEST_USART1_RX;
    hdma_vn.Init.Direction = DMA_PERIPH_TO_MEMORY;
    hdma_vn.Init.PeriphInc = DMA_PINC_DISABLE;
    hdma_vn.Init.MemInc = DMA_MINC_ENABLE;
    hdma_vn.Init.PeriphDataAlignment = DMA_PDATAALIGN_BYTE;
    hdma_vn.Init.MemDataAlignment = DMA_MDATAALIGN_BYTE;
    hdma_vn.Init.Mode = DMA_CIRCULAR;
    hdma_vn.Init.Priority = DMA_PRIORITY_HIGH;
    HAL_DMA_Init(&hdma_vn);
    __HAL_LINKDMA(&huart_vn, hdmarx, hdma_vn);
    HAL_UART_Receive_DMA(&huart_vn, vn_buf, VN_BUF);
    __HAL_DMA_DISABLE_IT(&hdma_vn, DMA_IT_HT | DMA_IT_TC); /* polled from the tick */
    vn_pos = 0;
}

size_t board_vn100_bytes(const uint8_t **p)
{
    const uint32_t head = VN_BUF - __HAL_DMA_GET_COUNTER(&hdma_vn);
    *p = &vn_buf[vn_pos];
    size_t n;
    if (head >= vn_pos) {
        n = head - vn_pos;
        vn_pos = head % VN_BUF;
    } else { /* wrapped: hand over the tail now, the head next tick */
        n = VN_BUF - vn_pos;
        vn_pos = 0;
    }
    return n;
}

/* ------------------------------------------------------------------------------------------- the INA228 */

#define INA_ADDR (0x40u << 1)
static uint8_t ina_raw[2][3];
static volatile uint8_t ina_stage; /* 0 idle, 1 reading VBUS, 2 reading CURRENT, 3 a sample waiting */

static void i2c_init(void)
{
    __HAL_RCC_I2C1_CLK_ENABLE();
    hi2c_ina.Instance = I2C1;
    /* 400 kHz from 170 MHz: PRESC 3 (23.5 ns), SCLDEL 4, SDADEL 2, SCLH 0x22, SCLL 0x3B (1.4 us low, 0.8 us high) */
    hi2c_ina.Init.Timing = 0x3042223Bu;
    hi2c_ina.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
    hi2c_ina.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
    hi2c_ina.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
    hi2c_ina.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE;
    HAL_I2C_Init(&hi2c_ina);
    HAL_NVIC_SetPriority(I2C1_EV_IRQn, 3, 0);
    HAL_NVIC_EnableIRQ(I2C1_EV_IRQn);
    HAL_NVIC_SetPriority(I2C1_ER_IRQn, 3, 0);
    HAL_NVIC_EnableIRQ(I2C1_ER_IRQn);
}

static bool ina_write(uint8_t reg, uint16_t v)
{
    uint8_t b[2] = {(uint8_t)(v >> 8), (uint8_t)v};
    return HAL_I2C_Mem_Write(&hi2c_ina, INA_ADDR, reg, I2C_MEMADD_SIZE_8BIT, b, 2, 5) == HAL_OK;
}

bool board_ina228_setup(uint16_t config, uint16_t adc_config, uint16_t shunt_cal)
{
    uint8_t id[2] = {0};
    if (HAL_I2C_Mem_Read(&hi2c_ina, INA_ADDR, 0x3E, I2C_MEMADD_SIZE_8BIT, id, 2, 5) != HAL_OK || id[0] != 0x54 || id[1] != 0x49) {
        return false; /* not a TI part at 0x40 */
    }
    return ina_write(0x00, config) && ina_write(0x01, adc_config) && ina_write(0x02, shunt_cal);
}

void board_ina228_start(void)
{
    if (ina_stage == 0 && HAL_I2C_Mem_Read_IT(&hi2c_ina, INA_ADDR, 0x05, I2C_MEMADD_SIZE_8BIT, ina_raw[0], 3) == HAL_OK) {
        ina_stage = 1;
    }
}

void HAL_I2C_MemRxCpltCallback(I2C_HandleTypeDef *h)
{
    if (ina_stage == 1 && HAL_I2C_Mem_Read_IT(h, INA_ADDR, 0x07, I2C_MEMADD_SIZE_8BIT, ina_raw[1], 3) == HAL_OK) {
        ina_stage = 2;
    } else {
        ina_stage = ina_stage == 2 ? 3 : 0;
    }
}

void HAL_I2C_ErrorCallback(I2C_HandleTypeDef *h)
{
    (void)h;
    ina_stage = 0; /* the reading is lost; the next one starts afresh (50 ms without one: the firmware sits) */
}

bool board_ina228_take(uint8_t vbus[3], uint8_t current[3])
{
    if (ina_stage != 3) return false;
    memcpy(vbus, ina_raw[0], 3);
    memcpy(current, ina_raw[1], 3);
    ina_stage = 0;
    return true;
}

/* ------------------------------------------------------------------------------------------- timers, watchdog */

static void timers_init(void)
{
    __HAL_RCC_TIM2_CLK_ENABLE();
    __HAL_RCC_TIM6_CLK_ENABLE();
    htim_us.Instance = TIM2; /* 32-bit, 1 MHz: the firmware's clock */
    htim_us.Init.Prescaler = 169;
    htim_us.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim_us.Init.Period = 0xFFFFFFFFu;
    htim_us.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    HAL_TIM_Base_Init(&htim_us);
    HAL_TIM_Base_Start(&htim_us);
    htim_tick.Instance = TIM6; /* the 1 kHz loop */
    htim_tick.Init.Prescaler = 169;
    htim_tick.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim_tick.Init.Period = 999;
    HAL_TIM_Base_Init(&htim_tick);
    HAL_NVIC_SetPriority(TIM6_DAC_IRQn, 2, 0);
    HAL_NVIC_EnableIRQ(TIM6_DAC_IRQn);
    HAL_TIM_Base_Start_IT(&htim_tick);
}

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *h)
{
    if (h->Instance == TIM6) {
        tick_due++;
    }
}

uint32_t board_us(void)
{
    return TIM2->CNT;
}

void board_watchdog_start(void)
{
    hiwdg.Instance = IWDG;
    hiwdg.Init.Prescaler = IWDG_PRESCALER_8; /* 32 kHz / 8 = 4 kHz */
    hiwdg.Init.Reload = 80;                  /* 20 ms without a tick: reset (MCU_RUN falls, the motors' 0.1 s timeouts stop them) */
    hiwdg.Init.Window = IWDG_WINDOW_DISABLE;
    HAL_IWDG_Init(&hiwdg);
}

void board_init(void)
{
    gpio_init();
    fdcan_init();
    i2c_init();
    timers_init();
}
