/* Gyropup balance firmware: the hand-set numbers (rates, safety limits, CAN ids). The model's numbers (masses, the
 * five-bar, the motors, the LQR table) are generated into gp_model.h by tools/gen_model.py.
 * Every number here is quoted in docs/body-firmware.md with where it comes from. */
#ifndef GP_CONFIG_H
#define GP_CONFIG_H

/* ---------------------------------------------------------------- the loop */
#define GP_TICK_HZ 1000u                /* the control loop (D63): 1 kHz */
#define GP_DT 0.001f                    /* s, the loop's fixed step */
#define GP_TICK_US 1000u

/* ---------------------------------------------------------------- the leg motors (RS-04, rig/rs04.py) */
#define GP_RS04_HOST 0xFDu              /* the motors' CAN_MASTER (manual 3.3) */
#define GP_RS04_LIMIT_TORQUE 60.0f      /* N m: D38's cap, written into every motor at boot (limit_torque, 0x700B) */
#define GP_RS04_CAN_TIMEOUT 2000u       /* 1/20000 s: 0.1 s without a frame and the motor drops to reset (0x7028) */
#define GP_RS04_V_RAIL 14.955f          /* rad/s: a reported speed this close to the 16-bit field's +-15 is its rail */
#define GP_MISS_MAX 3u                  /* ticks in a row without a motor's feedback -> limp (rig Limits.miss_max) */
#define GP_BOOT_STEP_US 20000u          /* a boot request's reply timeout */
#define GP_BOOT_RETRIES 3u

/* ---------------------------------------------------------------- the wheels (VESC on bus C) */
#define GP_WHEEL_CURRENT_MAX_A 25.0f    /* A: the firmware's limit on the wheel's commanded current (W14/W15) */
#define GP_VESC_ID_LEFT 10u
#define GP_VESC_ID_RIGHT 11u
#define GP_VESC_TIMEOUT_US 50000u       /* no STATUS frame for this long: the wheel's speed is stale */

/* ---------------------------------------------------------------- the leg window and the bus (rig Limits) */
#define GP_L_MIN_M 0.095f               /* m: a leg reported shorter than this -> limp */
#define GP_L_MAX_M 0.395f
#define GP_VBUS_OVER_V 58.0f            /* V, instantaneous: regeneration; the RS-04 trips at 60 V */
#define GP_FALLEN_RAD 0.9f              /* rad of pendulum angle: fallen (sim/scenarios.py) -> limp */

/* ---------------------------------------------------------------- battery: UVLO and the jump gate (D63) */
#define GP_R_PACK_OHM 0.112f            /* 13S2P P30B + BMS + leads (docs/body-next-plan.md 1.3) */
#define GP_VREST_TAU_S 1.0f             /* the resting-voltage filter: a jump's 0.3 s sag is not a flat pack */
#define GP_UVLO_WARN_V 45.5f            /* 3.50 V a cell: warn (the Jetson goes home) */
#define GP_UVLO_WARN_CLEAR_V 45.8f
#define GP_UVLO_SIT_V 41.6f             /* 3.20 V a cell: sit and stay down */
#define GP_UVLO_STAND_V 42.6f           /* no stand-up below this after a UVLO sit */
#define GP_JUMP_MIN_V 44.0f             /* no jump below 44 V resting: 80 A x 0.112 ohm leaves 35 V */
#define GP_JUMP_FLOOR_V 35.0f           /* the bus floor in the push: the DDR-120C-24 needs 33.6 V */
#define GP_JUMP_FULL_V 48.1f            /* the full jump at and above the nominal pack */
#define GP_JUMP_V_MAX 2.3f              /* m/s: the full jump's take-off speed (the push stops on reaching it) */
#define GP_VBUS_TIMEOUT_US 50000u       /* no bus voltage reading for this long: sit, refuse to stand */

/* ---------------------------------------------------------------- the Jetson link and people near (D63) */
#define GP_HEARTBEAT_LOST_US 200000u    /* no fresh setpoint for 200 ms: the link is lost */
#define GP_HEARTBEAT_HOLD_US 2000000u   /* then balance in place for 2 s, then sit */
#define GP_PEOPLE_SPEED_MAX 0.5f        /* m/s with people near */
#define GP_PEOPLE_SIT_US 2000000u       /* people near for 2 s: sit */

/* ---------------------------------------------------------------- the radio stop and MCU_RUN */
#define GP_STOP_DEBOUNCE_TICKS 2u       /* the coil sense low for 2 ms: STOP */
#define GP_RUN_HOLD_US 100000u          /* the coil sense high for 100 ms before an arm */
#define GP_ARM_TIMEOUT_US 50000u        /* every RS-04 in run mode within 50 ms of the enable */

/* ---------------------------------------------------------------- sitting */
#define GP_SIT_FAST_S 0.3f              /* the radio stop: down in 0.3 s (B13: torque off and sat within 0.5 s) */
#define GP_SIT_NORMAL_S 1.0f            /* UVLO, link lost, people near, the Jetson's sit */
#define GP_SETTLE_S 0.3f                /* at the bottom: the feed-forward fades to zero, then the motors stop */
#define GP_SIT_L_ROBOT_M 0.110f         /* m: near the stops (25 mm under the skids at 101.5 mm) */
#define GP_SIT_L_RIG_M 0.150f           /* m: the rig's sit-down (rig Limits.sit_to) */

/* ---------------------------------------------------------------- the jump sequence (sim/leg_rig.py 'jump') */
#define GP_JUMP_CROUCH_L_M 0.150f
#define GP_JUMP_CROUCH_S 0.5f
#define GP_JUMP_PUSH_AT_S 0.6f
#define GP_JUMP_PUSH_F_N 5000.0f        /* "as hard as the motors allow": saturates at the torque cap */
#define GP_JUMP_PUSH_END_L_M 0.310f
#define GP_JUMP_PUSH_MAX_S 0.35f
#define GP_JUMP_LAND_L_M 0.250f
#define GP_JUMP_MIN_AIR_S 0.12f         /* rig/leg_control.py Flight */
#define GP_JUMP_LAND_DL -0.60f          /* m/s */
#define GP_JUMP_RECOVER_S 0.5f

/* ---------------------------------------------------------------- CAN ids on bus C (docs/body-firmware.md 4) */
#define GP_ID_JET_SETPOINT 0x110u       /* Jetson -> MCU, 100 Hz */
#define GP_ID_JET_BENCH 0x111u          /* Jetson / laptop -> MCU, on demand (rig profile only) */
#define GP_ID_MCU_STATE_A 0x120u        /* MCU -> Jetson, 200 Hz */
#define GP_ID_MCU_STATE_B 0x121u        /* 200 Hz */
#define GP_ID_MCU_STATUS 0x122u         /* 200 Hz */
#define GP_ID_MCU_FAULTS 0x123u         /* 10 Hz */
/* 0x130-0x13F: reserved for the BMS bridge (the QT Py ESP32-S3; its firmware is not part of B8) */

/* The leg rig node (rig/node.py): 11-bit frames on the leg's bus, used by the rig profile's bench source */
#define GP_ID_RIG_RUN 0x700u
#define GP_ID_RIG_VBUS 0x702u
#define GP_RIG_RUN_CLOSED 0x5Au
#define GP_RIG_NODE_FRESH_US 50000u

#endif
