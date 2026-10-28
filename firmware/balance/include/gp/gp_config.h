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

/* ---------------------------------------------------------------- the battery (D65): every voltage window, one place
 * Two DeWalt DCB609 FLEXVOLT packs in 20 V mode in series: 10S3P, 36.0 V nominal, about 41 V full (4.1 V a cell),
 * 30 V empty. The packs have no BMS the robot can talk to, so the robot enforces the cut-off and the current limit
 * itself. The windows are per cell x GP_CELLS; "resting" is the bus with the sag taken back out (V + I x R_pack,
 * filtered over GP_VREST_TAU_S), "under load" the bus itself (GP_CUTOFF_TAU_S). docs/body-firmware.md 5. */
#define GP_CELLS 10.0f                  /* 10S (two 5S3P packs in series) */
#define GP_PACK_NOMINAL_V 36.0f         /* 3.60 V a cell */
#define GP_PACK_FULL_V 41.0f            /* 4.10 V a cell (DeWalt's charge end, about 20.5 V a pack) */
#define GP_R_PACK_OHM 0.100f            /* two DCB609s + their dock adapters + leads (D65's rig figure; measure at B12) */
#define GP_VREST_TAU_S 1.0f             /* the resting-voltage filter: a jump's 0.3 s sag is not a flat pack */
#define GP_UVLO_WARN_V 35.0f            /* 3.50 V a cell, resting: warn (the Jetson goes home) */
#define GP_UVLO_WARN_CLEAR_V 35.3f      /* 3.53 V a cell */
#define GP_UVLO_SIT_V 32.0f             /* 3.20 V a cell, resting: sit and stay down */
#define GP_UVLO_STAND_V 33.0f           /* 3.30 V a cell, resting: no arming below this (and after a UVLO sit) */
#define GP_CUTOFF_V 30.0f               /* 3.00 V a cell UNDER LOAD: legs down, motors off, latched until power cycle */
#define GP_CUTOFF_TAU_S 0.1f            /* the cut-off's filter on the loaded bus: PWM ripple and spikes, not sag */
#define GP_REGEN_START_V 41.5f          /* 4.15 V a cell on the bus: the regen clamp starts (charging current limited, D65: no BMS) */
#define GP_REGEN_ZERO_V 42.5f           /* 4.25 V a cell: no charging current allowed */
#define GP_REGEN_I_A 15.0f              /* A of charging allowed at 41.5 V, falling to 0 at 42.5 V: (42.5 - 41.0) V / 0.100 ohm, a full pack's */
#define GP_REGEN_GAIN 5.0f              /* /(A s): the braking factor's fall per amp of charging over the allowance (52 A: 2 samples to 0) */
#define GP_REGEN_RECOVER 10.0f          /* /s: the factor back up to 1 */
#define GP_OVERCHARGE_V 44.0f           /* 4.40 V a cell on the bus: sit and stop, latched until power cycle */
#define GP_OVERCHARGE_TAU_S 0.02f       /* the over-charge latch's filter: one sample's spike is not a charger */
#define GP_ARM_MAX_V 42.0f              /* 4.20 V a cell, resting: no arming over it (an over-full or wrong pack: the clamp would take the braking) */
#define GP_JUMP_MIN_V 34.0f             /* 3.40 V a cell, resting: no jump below this */
#define GP_JUMP_FLOOR_V 31.0f           /* the bus floor in the push: 1 V over the cut-off (the 24 V converter is rated lower, D65) */
#define GP_JUMP_FULL_V 38.2f            /* the full push at and above this, resting: its 7.2 V sag (HIL, 72 A x 0.1 ohm) reaches the floor */
#define GP_JUMP_I_FULL_A 72.0f          /* A: the push's bus current limit at s(V) = 1, (GP_JUMP_FULL_V - GP_JUMP_FLOOR_V) / R_pack */
#define GP_JUMP_V_MAX 3.2f              /* m/s: the take-off speed cap at jump height 15/15, above the full push (it ends at 310 mm) */

/* ---------------------------------------------------------------- the bus current limit (D65), from the INA228
 * Not a trip: every motor's current command is scaled down (one factor, legs and wheels) while the bus is over the
 * limit. The limit is GP_BUS_I_PEAK_A for at most GP_BUS_I_PEAK_S at a time, else GP_BUS_I_CONT_A, and GP_BUS_I_CONT_A
 * whenever the 1 s average is over it. B12 checks the adapters' contact temperature after ten jumps. */
#define GP_BUS_I_CONT_A 30.0f           /* A, the 1 s average: the Terrafirma 10 AWG DeWalt 20 V dock adapters' stated 30 A */
#define GP_BUS_I_PEAK_A 80.0f           /* A, at most GP_BUS_I_PEAK_S at a time: the jump's push (the 80 A MRBF main fuse, D55) */
#define GP_BUS_I_PEAK_S 0.5f
#define GP_BUS_I_AVG_S 1.0f             /* the average's window (first order) */
#define GP_BUS_SCALE_MIN 0.5f           /* the factor never goes under this: balance and the legs' weight need torque */
#define GP_BUS_SCALE_RECOVER 4.0f       /* /s: the factor's climb back to 1 under the limit */
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
#define GP_SETTLE_S 0.15f               /* at the bottom: the feed-forward fades to zero, then the motors stop */
#define GP_SIT_L_ROBOT_M 0.110f         /* m: near the stops (101.5 mm); the D65 battery bay's skids reach the floor at 139 mm */
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

/* The leg rig node (rig/node.py): 11-bit frames on the leg's bus, used by the rig profile's bench source */
#define GP_ID_RIG_RUN 0x700u
#define GP_ID_RIG_VBUS 0x702u
#define GP_RIG_RUN_CLOSED 0x5Au
#define GP_RIG_NODE_FRESH_US 50000u

#endif
