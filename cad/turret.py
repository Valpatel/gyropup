"""Gyropup's foam-ball turret (head payload), in CadQuery: every made part printed (D33), the bought parts as envelopes.

    .venv/bin/python cad/turret.py [designs/default.json] [--no-render]

The concept is research/turret-launcher-study.md section 8 and docs/cad-plan.md section 4: Rival-size foam balls, a
gravity hopper over an 8-pocket dial on an STS3215 servo, twin SunnySky X2216 flywheels in the horizontal plane, a 100 mm
barrel, an aiming laser on the cradle, an STS3215 ring-gear pan on a 61810-2RS bearing and an STS3215 tilt with a hard
stop at 0 deg (the barrel can never point above horizontal: kid-safety rule S5 / study 6.3).

Frames (mm). Robot frame: x forward, y left, z up, origin on the hip axis. The turret is built in its own frame T (the
same axes, origin on the pan axis at the top face of the head's turret ring = the TM mounting face) and moved up by
mount_z = bodyTop + 20 + SADDLE_T. The parts that tilt are built in the cartridge frame C (x along the barrel, the ball
path on z = 0, the dial axis on x = 0); at tilt 0 C sits PATH_T above the mount face and TILT_X behind the pan axis.
Pan turns about the T z axis, tilt about a y axis through C (TILT_X, TILT_C), which lies on the pan axis. Negative
tilt = muzzle down; the hard stops allow 0 .. -25 deg. The tilting group's centre of mass sits a few mm behind the
tilt axis, so unpowered the barrel rises to the 0 deg stop (it cannot drop onto the lidar in front of the turret).

How the ball moves (turret-section.png): hopper (30 balls) -> dial pocket -> a hole in the dial-housing floor -> a
curved chute that turns it forward -> the nip of the two flywheels -> the barrel. Each shot steps the dial 45 deg and
stops it with a pocket over the hole: the ball drops while the dial stands still. A baffle in the hopper covers the
pocket over the hole, so nothing can refill it: one ball per step (no double feed), and with the dial parked no ball
can reach the wheels.

Made parts (one function each; PA6-CF = loaded, 100 % solid; PETG = 2 mm walls, 40 % infill; TPU 95A; three parts are
laser-cut 6061-T6 from SendCutSend, D40/D48: the pan clamp, the two cradle plates and the stop lug, SHEET_PARTS):
  pan_base (PA6-CF)        on the TM pattern; holds the 61810 outer race, the pan servo, the DT receptacle, the pan
                           hard-stop post, the bumper tabs
  pan_clamp (PA6-CF)       clamps the 61810 outer race down (3 x M3 into inserts)
  pan_ring (PA6-CF)        the turntable: 63 T m1.25 spur gear on its rim, journal through the inner race (DIN 471-50
                           circlip below), 40 mm open centre for the cable, pan stop finger; the yoke bolts on top
  pan_pinion (PA6-CF)      21 T m1.25 on the pan servo's horn (63:21 = 3:1)
  tilt_yoke (PA6-CF)       bridge + two arms; tilt servo on the +y arm, MR126 on the -y arm, hard stops at 0 / -25 deg
  cradle (PA6-CF)          the rail frame (D48): rails the cartridge sits on (CT: 2 dowels + a thumbscrew), laser tab,
                           rebates and inserts for the two aluminium cheek plates (cradle_plate_l/r, SendCutSend 6061-T6
                           0.125 in) that carry it on the tilt axis; the hard stop is an aluminium lug (stop_lug, 0.100 in)
  horn_boss, pivot_spacer (PA6-CF)  between the plates and the tilt servo's horn (+y) and the MR126 (-y)
  cartridge_body (PA6-CF)  dial housing, drop chute, flywheel cage (motors hang under its top plate), barrel socket
  flywheel (PA6-CF)        hub on the X2216's prop adapter; flywheel_tyre (TPU 95A) Ø38 tyre bonded over it (D68)
  dial (PETG)              8 pockets, stirring cone, on the feed servo's horn
  hopper, hopper_lid, hopper_flap (PETG, translucent)  30 balls; fill port with a sprung flap for the dock spout
  barrel (PETG, orange tip)  Ø30 x 100, bore = ball + 1.5, two chronograph gates
  laser_mount (PETG)       ring with three M3 boresight screws, on the cradle
  bumper_ring (TPU 95A)    around the pan base
head_ring_tm(L) is the proposed replacement for the ring of build.py's head_saddle (see its docstring).
"""
from __future__ import annotations

import itertools
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import cadquery as cq
import numpy as np

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import gmi  # noqa: E402

FAST = gmi.FAST
BED = gmi.STD['print']['bed_mm']
INSERT_DEPTH = 8.0

# ------------------------------------------------------------------------------------------------ fixed sizes (mm)
SADDLE_T = 8.0            # proposed head ring thickness (M5 inserts need 8 mm)
TM_BOLTS = [(40.0, 40.0), (-40.0, 40.0), (-40.0, -40.0), (40.0, -40.0)]      # 4 x M5 on 80 x 80
TM_DOWELS = [(52.0, 0.0), (0.0, -52.0)]                                     # 2 x Ø5, not symmetric: one way only
TM_HOLE = 45.0
# 6810-2Z (= 61810-2Z, McMaster 6656K229): 50 x 65 x 7, 52 g. Anything turning with the inner ring may bear on it only
# inside Ø52.5 and anything fixed on the outer ring only outside Ø62 (NSK 6810ZZ abutments: da 52..52.5, Da max 63); the
# shields between are recessed (0.2 mm, est).
BRG = {'d': 50.0, 'D': 65.0, 'B': 7.0, 'mass_g': 52.0, 'd_land': 52.4, 'D_land': 62.0, 'shield_recess': 0.2}
# 126-2Z (MR126 size, McMaster 7804K112): 6 x 12 x 4; lands est for a 6 x 12 miniature (inner ring to Ø7.2, outer
# ring from Ø10.6): check on the bearing in hand
MR126 = {'d': 6.0, 'D': 12.0, 'B': 4.0, 'mass_g': 1.75, 'd_land': 7.2, 'D_land': 10.6, 'shield_recess': 0.1}
# DIN 471-50 external ring (McMaster 98541A167; DIN 471:2011 table): groove Ø47 x 2.15, ring 2 thick, section b 5.1 at
# the back, lugs a 6.9 (to r 30.4 fitted), edge margin n >= 4.5 on steel. Its back and lugs overhang the 6810's shield,
# so it sits under a printed spacer (pan_spacer), 4 mm below the bearing, and the journal runs 6 mm past its groove.
CIRCLIP = {'d2': 47.0, 'm': 2.15, 's': 2.0, 'b': 5.1, 'a': 6.9, 'n_min': 4.5, 'mass_g': 11.4}
JOURNAL_LIP = 6.0
SPACER = {'h': 4.0, 'land_h': 1.0, 'r_out': 29.5}          # pan_spacer under the 61810's inner ring
# ISO 7379 shoulder screw 6 x 12, M5 x 10 (McMaster 92981A101): the tilt pivot on the -y side
SHOULDER = {'d': 6.0, 'L': 12.0, 'head_d': 10.0, 'head_h': 5.0, 'thread_d': 5.0, 'thread_L': 10.0, 'mass_g': 6.7}
# Feetech STS3215 12 V (ST-3215-C018; Feetech's drawing and datasheet, references/vendor/feetech-sts3215): case 45.2 x
# 24.7, 32 between the two mounting faces (35 over the label band on the output face and the bump on the idler face);
# the output 10.11 from the horn end, centred across; the horn Ø19.95 with 4 x M3 tapped on Ø14 and a Ø3.2 centre hole,
# its face 3.0 above the output face; the idler boss Ø6 x 4.1; 4 x M2 in each mounting face, +-10.25 across, at 8.30 and
# 29.00 (output face) or 8.30 and 32.75 (idler face) from the axis towards the far end; the two 3-pin bus sockets
# (Molex 5264) on the idler face about 14 mm from the axis, plugged straight in: 12 mm of room is kept under that face.
# 55 g bare (Feetech), 60 g with the horn and its lead.
SERVO = {'L': 45.2, 'W': 24.7, 'H': 32.0, 'band': 1.1, 'bump': 1.9, 'shaft_from_end': 10.11, 'horn_d': 19.95, 'horn_t': 3.0,
         'horn_pcd': 14.0, 'idler_boss': (6.0, 4.1), 'holes_out': (8.30, 29.00), 'holes_idler': (8.30, 32.75), 'holes_x': 10.25,
         'plugs': (9.0, 24.0, 7.5), 'plug_room': 12.0, 'mass_g': 60.0}
# The flywheel motor (D68; D42 chose the 880 KV of the same motor): SunnySky X2216 1400KV V3, short shaft. Every KV of the
# X2216 V3 is the same can, stator, shaft and prop adapter, so this drawing holds (SunnySky's drawing "X2216 short shaft" on
# en.rcsunnysky.com/x-fixedwingseries/1102.html, references/vendor/sunnysky-x2216). Ø27.7; 32 from the mount face (the
# base's end) to the bell's front face, a Ø9 boss 2.0 proud of that face (34), and the Ø3.175 shaft's rear end with its
# clip 2.5 behind the mount face (36.5 overall). The base is the first 7.5 (est from the drawing: the leads leave it
# radially, 18 AWG x 100); the bell turns from there. 4 x M3 x 0.5 in the mount face, 2.8 deep (a screw must not reach
# further: the windings), on the two diagonals 45 deg either side of the lead exit, 19 apart on one and 16 on the other.
# The bolt-on prop adapter in the box carries the hub: a Ø17 x 4 flange on 3 x M2 into the bell on Ø12 (a Ø9 recess
# over the boss centres it), a Ø5 (0/-0.03) pilot 5.5 long, then an M5 x 0.8 stud 13 long; the Ø14.8 x 2 washer (Ø5.1)
# and an M5 nylon-insert nut clamp the hub against the flange, as a propeller is. 72 g with its leads (SunnySky's
# table; RMRC lists 67.5 g), 12N14P (7 pole pairs). The 1400 KV: 55 mOhm between leads, 1.3 A at no load at 10 V, 2-4S
# (the 880 KV: 117 mOhm, 0.5 A). On the trimmed ~11.3 V flywheel rail it turns 15,722 rpm (sim/turret_launch.py).
MOTOR = {'name': 'SunnySky X2216 1400KV V3 (short shaft)', 'd': 27.7, 'len': 32.0, 'boss': (9.0, 2.0), 'stub': (7.0, 2.5),
         'base_h': 7.5, 'holes_r': (8.0, 9.5), 'flange': (17.0, 4.0), 'pilot': (5.0, 5.5), 'stud': (5.0, 13.0),
         'washer': (14.8, 2.0), 'nut': (9.2, 5.0), 'kv': 1400.0, 'pole_pairs': 7, 'R_ohm': 0.055, 'I0_a': 1.3, 'mass_g': 72.0}
# Repeat Robotics AM32 35 A (catalog repeat-robotics-am32-35a-esc): 26 x 13 x 5, 5 g with its wires. The backup ESC,
# the Lumenier Razor Pro F4 45A AM32, is 28 x 12 x 5 and fits the same place.
AM32 = {'size': (26.0, 13.0, 5.0), 'mass_g': 5.0}
# The cartridge board (docs/turret-wiring.md 6, cad/turret_boards.py): a 50 x 44 piece of perfboard over the cage plate on
# four printed posts (M3 inserts, 4 x M3 x 6), clear of the hopper by 3 mm and overhanging the cage's front over the barrel
# socket: the 6 x IRLZ44N of the phase-short brake stand in a row along its front edge (TO-220, 21 mm tall), the LM393
# gate comparator, the feed servo's polyfuse and the resistors behind them. The two ESCs lie on the cage plate under it.
CART_BOARD = {'x': (54.0, 104.0), 'y': 22.0, 'boss_h': 6.0, 'standoff': 12.0, 'parts_h': 21.0, 'board_t': 1.6, 'mass_g': 30.0,
              'bosses': ((58.0, 16.0), (58.0, -16.0), (90.0, 18.5), (90.0, -18.5))}
# Quarton VLM-650-03 LPT (D42): 650 nm, 1 mW (Class 2), Ø7.00 x 22.50, 2.6-6 V, < 35 mA (Quarton's datasheet; Digi-Key)
LASER = {'d': 7.0, 'L': 22.5, 'mass_g': 3.0, 'name': 'Quarton VLM-650-03 LPT, 650 nm, < 1 mW (Class 2)'}
# Deutsch DT04-12PA-L012 flange receptacle and its DT06-12SA plug (est; check against the TE drawings)
# TE Deutsch DT04-12PA-L012 flange receptacle (TE drawing DT04-12PX-L012 rev D2): flange 55.12 x 35.56 x 5.08, 4 x Ø4.29 on
# 44.96 x 23.88 (M4), panel cutout 41.83 x 23.52 R6.35, shroud 40.56 x 22.25 standing 19.81 proud, ~21 behind the panel.
# The robot's DT06-12SA plug goes into the shroud; a 1011-248-1205 90 deg backshell turns its harness down (est size).
DT = {'flange': (55.12, 5.08, 35.56), 'body': (40.6, 21.0, 22.3), 'front': (40.56, 19.81, 22.25), 'plug': (44.0, 45.0, 28.0),
      'holes': (44.96, 23.88), 'cutout': (41.83, 23.52), 'mass_g': 20.0,
      'sweep': 30.0}
NOT_MODELLED_G = {'wiring and the cable loops': 50, 'chronograph emitters/receivers + hopper-full beam': 10,
                  'LEDs and buzzer': 15, 'screws, inserts, dowels, springs': 17, 'CT connector pair (Micro-Fit 3.0 class)': 12}
# ---- the pan joint (docs/turret-plan.md 3.1, research/turret-slip-ring.md): a Ø22 gold capsule slip ring, flange down
# in the base on a printed carrier, its rotor turned by the turntable through a soft silicone tube. The candidates
# share the Ø22 body and the Ø44-44.5 flange (one carrier); the driver reaches each rotor stub through the tube.
# Flange hole patterns other than Servotecnica's (3 x Ø5.5 on Ø35) are not published: measure the ring in hand.
RING_MODELS = {
    'sparkfun_rob13065': {'name': 'SparkFun ROB-13065 (Senring M220 series): 12 x 2 A, Ø22 x 26.5, flange Ø44.5', 'body_l': 26.5,
                          'stub': (6.0, 5.0), 'flange': (44.5, 2.5), 'pcd': 35.0, 'mass_g': 25.0},
    'adafruit_1196': {'name': 'Adafruit 1196 (Prosper SRC022A-12): 12 x 2 A, Ø22, flange Ø44', 'body_l': 26.0,
                      'stub': (6.0, 5.0), 'flange': (44.0, 2.5), 'pcd': 35.0, 'mass_g': 20.0},
}
# D2 (decided 2026-10-27, docs/decisions.yaml D41): the SparkFun ring on the bench and on the robot; the 200 ms soft
# start keeps every circuit under 2 A (2.2 A peak at the ring, two circuits per power rail)
RING_MODEL = 'sparkfun_rob13065'
# D1 (decided): continuous pan through the ring. False brings back the stop post and finger (+-170 deg on a cable loop)
CONTINUOUS_PAN = True
# the carrier drops into the foot's Ø65 opening from below (the opening is that big so the DIN 471 circlip can pass,
# its d4 install space being Ø64.5) and is held by 3 x M3 x 10 flat heads through tabs sunk flush in the foot's
# underside into inserted bosses on the housing tube; the head ring (Ø60 hole) or the stand's top then traps it too
CARRIER = {'r': 32.25, 'h': 12.0, 'tab_angles': (60.0, 135.0, 300.0), 'tab_r': 38.5, 'tab_t': 4.0, 'screw_r': 35.75,
           'flange_seat': 2.6, 'bore': 23.1}
# the rotor coupling (McMaster 51225K24, 65A TPV): 3/16 in ID stretched 26 % over the ring's Ø6 rotor stub, so it grips
# it (the 5/16 in tube first drawn here sat 1 mm loose round the stub: cad/turret_gates.py found the rotor floating);
# its far end pushed into the driver's socket, 0.3 mm under its OD
TUBE = {'id': 4.76, 'od': 7.94, 'socket_d': 7.64, 'note': 'soft TPV rubber tube 3/16 in ID x 5/16 in OD (McMaster 51225K24)'}
MAGNET = {'d': 4.76, 'h': 3.18, 'r': 35.0, 'note': 'neodymium disc 3/16 x 1/8 in (McMaster 5862K102), the pan index: ~760 G at the hall\'s element 3.5 mm over it (Br 1.32 T, on-axis formula), 4x the A1120\'s highest operate point'}
HALL = {'size': (4.1, 3.0, 1.6), 'note': 'Allegro A1120LUA-T unipolar hall switch (UA package), on the turntable'}
DENS = {k: v['density_g_cm3'] for k, v in json.loads((R / 'catalog/materials.json').read_text()).items()}
PRINT_RATE_CM3_H = {'pa6-cf': 14.0, 'petg': 20.0, 'tpu95': 8.0}       # same rates as build.py's print plan


class Geo:
    """Every size that follows from the ball. ball_d: Rival rounds are 22.2-22.8 mm (study 2.1); 22.7 is the design
    ball. Bores and pockets are ball + 1.5 mm."""

    def __init__(self, ball_d: float = 22.7, wheel_d: float = 38.0, crush: float = 0.40):
        self.ball = ball_d
        self.bore = ball_d + 1.5
        self.br = self.bore / 2
        # from the nip to the muzzle the bore is ball + 2.0: with 1 mm of play the ball rides the floor and rolls up to a
        # steady topspin instead of rattling (docs/turret-physics.md finding 14: pitch scatter 11.5 -> 5 mrad, the speed
        # lost in the bore 1.0 -> 0.7 fps); the dial's pockets and the chute stay at ball + 1.5, which fed cleanly
        self.bore_out = ball_d + 2.0
        self.br_out = self.bore_out / 2
        self.wall = 2.5
        # dial: 8 pockets, spokes 4 mm; pitch radius so the gap between spokes >= the bore
        self.n_pockets = 8
        self.spoke_w = 4.0
        self.rp = math.ceil((self.bore + self.spoke_w + 0.5) * self.n_pockets / (2 * math.pi))
        self.dial_hub_r = self.rp - self.br                      # inner wall of the ball channel
        self.dial_wall_r = self.rp + self.br                     # outer wall (housing / hopper inside)
        self.housing_r = self.dial_wall_r + self.wall
        self.floor_z = 10.0                                      # top of the dial-housing floor (C frame)
        self.floor_t = 3.0
        self.dial_z0 = self.floor_z + 0.75
        self.dial_h = 20.0
        # the feed servo's output face sits in a 0.75 mm pocket in the floor's underside, so its horn's top is level with the
        # dial's underside and the dial sits flat on it (no spigot: the dial prints flat on its bottom)
        self.feed_face = self.dial_z0 - SERVO['horn_t']
        self.housing_top = 35.0
        # the lid's underside: a physics fill (sim/turret_feed.py, 40 balls jostled in) fits 15-16 balls under 70 mm,
        # 29 under 95 and 34 under 100, so 100 holds the 30-ball load with room to spare
        self.hopper_top = 100.0
        self.exit_x = float(self.rp)                             # the exit hole under the front pocket
        self.ball_z_dial = self.floor_z + ball_d / 2             # ball centre in a pocket
        self.chute_r = self.ball_z_dial                          # the chute turns the ball down to the path (z = 0)
        self.chute_cx = self.exit_x + self.chute_r               # centre of the turn, at (chute_cx, chute_r)
        # flywheels (sim/turret_launch.py, D68): Ø38 tyres squeeze the ball 40 % (to 13.6 mm), enough that a Hasbro
        # round catches the tyre and leaves near its surface speed (95-100 fps); on the trimmed flywheel rail their
        # no-load speed is the hardware ceiling (every accepted ball at 100 % throttle stays under 105 fps). The cage is
        # as wide as it was for Ø36 at 25 % (cage_y 49.3 against 49.0)
        self.wheel_d = wheel_d
        self.crush = crush
        self.wheel_c = wheel_d + ball_d * (1 - crush)            # centre distance (51.62 for Ø38 tyres at 40 %)
        self.wheel_y = self.wheel_c / 2
        self.tyre_w = 12.0
        self.tyre_t = 4.0                                        # TPU 95A on the hub's rim
        nip = math.sqrt((wheel_d / 2) ** 2 - ((self.wheel_c - ball_d) / 2) ** 2)   # ball touches both wheels here
        self.wheel_x = math.ceil(self.chute_cx + nip + 2.0)
        self.cav_r = wheel_d / 2 + 2.0                           # the cage's shells are built on this radius ...
        self.cav_cut = wheel_d / 2 + 2.5                         # ... and cut to this: the bonded TPU tyre grows 0.04 mm
                                                                  # at no-load (2.4 mm if it came loose), so 2.5 mm stays clear
        self.cage_x0 = self.wheel_x - self.cav_r - self.wall
        self.cage_x1 = self.wheel_x + self.cav_r + self.wall
        self.cage_y = self.wheel_y + self.cav_r + self.wall      # half-width of the cartridge
        self.base_z0 = -(self.br + 3.0)                          # underside of the cartridge base
        # the X2216s hang bell-down under the cage's top plate; each hub sits on its motor's prop adapter with the tyre's
        # mid-plane on the ball path, so the hub's top face (on the adapter's flange) is half a tyre above it
        self.hub_top = self.tyre_w / 2
        self.bell_z0 = self.hub_top + MOTOR['flange'][1]        # the bell's front face, under the adapter's flange
        self.plate_z0 = self.bell_z0 + MOTOR['len']              # the motors' mount face: the plate's underside
        self.plate_z1 = self.plate_z0 + 3.5
        self.barrel_od = 30.0
        self.barrel_len = 100.0
        self.socket_x0 = self.cage_x1 + 1.5                      # barrel shoulder
        self.socket_x1 = self.socket_x0 + 14.0
        self.barrel_x0 = self.socket_x0
        self.barrel_x1 = self.barrel_x0 + self.barrel_len
        # tilt and pan
        self.tilt_c = 15.0                                       # tilt axis above the ball path ...
        # ... and this far ahead of the dial axis, so the tilting group's centre of mass sits a few mm behind the axis
        # with an empty or a full hopper: unpowered, the barrel rises to the 0 deg stop and never drops onto the lidar
        # in front of it (it was 32-35 mm ahead with the axis on the dial axis). The axis stays on the pan axis, so the
        # dial and hopper sit tilt_x behind it. 48 with the X2216s (72 g each, ahead of the axis) and the servo feed:
        # 8.5 mm behind with 30 balls, 5.2 empty (at 40 it was 0.9 behind full and 2.3 ahead empty)
        self.tilt_x = 48.0
        self.cheek_y = (self.cage_y + 1.5, self.cage_y + 7.5)              # the cheeks' envelope (v0's printed cheeks)
        self.arm_y = (self.cheek_y[1] + 4.0, self.cheek_y[1] + 12.0)
        self.rail_y = (self.cage_y - 10.5, self.cheek_y[1])
        self.rail_z = (self.base_z0 - 5.0, self.base_z0)
        # D48: the aluminium cheek plates sit in a rebate in the rails' outer faces: inner face on the rebate, outer
        # face 4.0 mm from the yoke's arm (where v0's printed cheek was)
        self.plate_y = (self.cheek_y[1] - PLATE['rebate'], self.cheek_y[1] - PLATE['rebate'] + SHEET['al6061']['thickness_mm'])
        self.foot_z = (self.rail_z[1] - PLATE['foot_h'], self.rail_z[1])
        self.stop_r = (24.0, 32.0)
        self.tilt_min = -25.0
        # pan stack (T frame, mount face z = 0)
        self.foot_t = 5.0
        self.brg_z = 40.0                                        # bottom of the 61810
        self.housing_r_out = 37.0
        self.turntable_z = (53.0, 69.0)
        self.gear = {'m': 1.25, 'z_ring': 63, 'z_pinion': 21}
        self.centre_d = self.gear['m'] * (self.gear['z_ring'] + self.gear['z_pinion']) / 2 + 0.15
        self.servo_pan_xy = (-self.centre_d, 0.0)
        # the pan servo stands on four posts with its idler face 12 mm over the foot: its bus plugs go in from below
        self.servo_z0 = self.foot_t + SERVO['plug_room']
        self.base_r = 72.0
        # 12 mm (10 in v0): the push on the muzzle twists the bridge next to the -y arm, and with the yoke printed on its
        # back that torsion is interlaminar shear (cad/turret_studies.py, layer-aware: 1.76 at 10 mm)
        self.bridge_z = (self.turntable_z[1], self.turntable_z[1] + 12.0)
        self.post_r = (68.5, 74.0)
        self.post_top = 62.0
        self.dt_y = 73.0                                         # DT pad face (flange seat)
        self.bumper_r = (82.0, 86.0)                             # 4 mm of TPU 95A (mass: it was 6)
        self.bumper_z = (6.0, 20.0)                              # on 6 mm tabs: the M3 x 4.3 inserts need 5.1 mm
        # height of the ball path above the mount face. Two limits: the feed servo's bus plugs (under the dial, tilt_x
        # behind the pan axis) 3 mm over the turntable; and, binding, the front of the cradle (the laser tab and the laser
        # mount's screw heads under it) at full depression passing over the pan pinion, whose 16 mm face reaches z 69
        # (the clash sweep at pans 0..350 asks for 1 mm: 125 gives ~2)
        feed_bottom = self.feed_face - SERVO['H'] - SERVO['plug_room']
        self.path_t = max(math.ceil(self.turntable_z[1] + 3.0 - feed_bottom), 125)
        self.tilt_t = self.path_t + self.tilt_c


# ------------------------------------------------------------------------------------------------ small helpers

def box(x0, x1, y0, y1, z0, z1):
    (x0, x1), (y0, y1), (z0, z1) = sorted((x0, x1)), sorted((y0, y1)), sorted((z0, z1))
    return cq.Workplane('XY').box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cyl_z(r, z0, z1, x=0.0, y=0.0):
    return cq.Workplane('XY').circle(r).extrude(z1 - z0).translate((x, y, z0))


def ring_z(ro, ri, z0, z1, x=0.0, y=0.0):
    return cq.Workplane('XY').circle(ro).circle(ri).extrude(z1 - z0).translate((x, y, z0))


def cyl_y(r, y0, y1, x=0.0, z=0.0):
    return cq.Workplane('XZ', origin=(0, y1, 0)).center(x, z).circle(r).extrude(y1 - y0)


def cyl_x(r, x0, x1, y=0.0, z=0.0):
    return cq.Workplane('YZ', origin=(x0, 0, 0)).center(y, z).circle(r).extrude(x1 - x0)


def sector_y(r0, r1, a0, a1, y0, y1, cx=0.0, cz=0.0, n=24):
    """An annular sector in the x-z plane (angles in degrees from +x towards +z) between y0 and y1."""
    a = [math.radians(a0 + (a1 - a0) * k / n) for k in range(n + 1)]
    pts = [(cx + r1 * math.cos(t), cz + r1 * math.sin(t)) for t in a] + [(cx + r0 * math.cos(t), cz + r0 * math.sin(t)) for t in reversed(a)]
    return cq.Workplane('XZ', origin=(0, y1, 0)).polyline(pts).close().extrude(y1 - y0)


def arc_sector_y(r0, r1, a0, a1, y0, y1, cx=0.0, cz=0.0):
    """sector_y with true circular arcs (no facets): clipping or meeting another face leaves no sliver edges."""
    P = lambda r, d: (cx + r * math.cos(math.radians(d)), cz + r * math.sin(math.radians(d)))
    am = (a0 + a1) / 2
    w = (cq.Workplane('XZ', origin=(0, y1, 0)).moveTo(*P(r0, a0)).lineTo(*P(r1, a0)).threePointArc(P(r1, am), P(r1, a1))
         .lineTo(*P(r0, a1)).threePointArc(P(r0, am), P(r0, a0)).close())
    return w.extrude(y1 - y0)


def polar(r, a):
    return (r * math.cos(a), r * math.sin(a))


def gear_profile(m, z, backlash=0.15, n=6, round_root=True):
    """Involute spur gear outline (20 deg pressure angle, addendum m, dedendum 1.25 m) as one closed polyline.
    backlash thins every tooth at the pitch circle (printed gears). round_root: each gap's root is one circular arc
    from flank to flank through the root circle (a full-round fillet: printed teeth break at a sharp root)."""
    alpha = math.radians(20.0)
    rp, ra, rf = m * z / 2, m * z / 2 + m, m * z / 2 - 1.25 * m
    rb = rp * math.cos(alpha)
    inv = lambda x: math.tan(x) - x
    psi = (math.pi * m / 2 - backlash) / (2 * rp) + inv(alpha)
    r0 = max(rb, rf)
    flank = [(r, psi - inv(math.acos(min(1.0, rb / r)))) for r in (r0 + (ra - r0) * k / n for k in range(n + 1))]
    pitch = 2 * math.pi / z
    pts = []
    for i in range(z):
        c = i * pitch
        if not round_root and rf < rb:
            pts.append(polar(rf, c - flank[0][1]))
        pts += [polar(r, c - f) for r, f in flank]
        pts += [polar(r, c + f) for r, f in reversed(flank)]
        if not round_root:
            if rf < rb:
                pts.append(polar(rf, c + flank[0][1]))
            pts.append(polar(rf, c + pitch / 2))
            continue
        # the arc through this flank's foot, the root circle mid-gap and the next tooth's flank foot
        p1, pm, p2 = polar(r0, c + flank[0][1]), polar(rf, c + pitch / 2), polar(r0, c + pitch - flank[0][1])
        pts += _arc3(p1, pm, p2, 6)[1:-1]
    return pts


def _arc3(p1, p2, p3, n):
    """n + 1 points on the circle through p1, p2, p3, from p1 through p2 to p3."""
    (x1, y1), (x2, y2), (x3, y3) = p1, p2, p3
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-12:
        return [p1, p2, p3]
    ux = ((x1 ** 2 + y1 ** 2) * (y2 - y3) + (x2 ** 2 + y2 ** 2) * (y3 - y1) + (x3 ** 2 + y3 ** 2) * (y1 - y2)) / d
    uy = ((x1 ** 2 + y1 ** 2) * (x3 - x2) + (x2 ** 2 + y2 ** 2) * (x1 - x3) + (x3 ** 2 + y3 ** 2) * (x2 - x1)) / d
    r = math.hypot(x1 - ux, y1 - uy)
    a1, a2, a3 = (math.atan2(y - uy, x - ux) for x, y in (p1, p2, p3))
    # go from a1 to a3 the way that passes a2
    da = (a3 - a1) % (2 * math.pi)
    if not (0 < (a2 - a1) % (2 * math.pi) < da):
        da -= 2 * math.pi
    return [(ux + r * math.cos(a1 + da * k / n), uy + r * math.sin(a1 + da * k / n)) for k in range(n + 1)]


def spur(m, z, z0, z1, x=0.0, y=0.0):
    return cq.Workplane('XY').polyline(gear_profile(m, z)).close().extrude(z1 - z0).translate((x, y, z0))


def insert_hole(x, y, z_top, size='M3', depth=INSERT_DEPTH):
    """Pilot for a heat-set insert, from a top face down."""
    return cyl_z(FAST[size]['insert_pilot'] / 2, z_top - depth, z_top + 0.1, x, y)


def through_z(x, y, d, z0=-50.0, z1=400.0):
    return cyl_z(d / 2, z0, z1, x, y)


def servo_envelope(G, shaft_xyz, axis):
    """STS3215 with its horn, the idler boss and the room its bus plugs need under the idler face. The output face is at
    shaft_xyz and the horn faces along `axis` ('+z' for the pan servo, '-y' for the tilt servo); the case runs 10.11 one
    way and 35.09 the other along its length (+y for the pan servo, -z for the tilt servo). The label band (output
    face) and the bump (idler face) are drawn over the middle of those faces (their extent is est)."""
    L, W, H = SERVO['L'], SERVO['W'], SERVO['H']
    s = SERVO['shaft_from_end']
    # built with the output axis +z, the output face at z = 0, the far end towards +y
    e = box(-W / 2, W / 2, -s, L - s, -H, 0)
    e = e.union(box(-6.5, 6.5, 12.0, L - s - 1.0, 0, SERVO['band']))
    e = e.union(box(-7.0, 7.0, 4.0, L - s - 4.0, -H - SERVO['bump'], -H))
    e = e.union(cyl_z(SERVO['idler_boss'][0] / 2, -H - SERVO['idler_boss'][1], -H))
    pg = SERVO['plugs']
    e = e.union(box(-pg[2], pg[2], pg[0], pg[1], -H - SERVO['plug_room'], -H))                 # the two bus plugs (est)
    e = e.union(cyl_z(SERVO['horn_d'] / 2, 0, SERVO['horn_t']))
    x, y, z = shaft_xyz
    if axis == '+z':
        return e.translate((x, y, z))
    # horn towards -y, length downwards: local z -> -y, local y -> -z
    return e.rotate((0, 0, 0), (1, 0, 0), 90).rotate((0, 0, 0), (0, 1, 0), 180).translate((x, y, z))


# ------------------------------------------------------------------------------------------------ fixed (pan base) parts

def pan_base(G):
    """The fixed base, printed PA6-CF on its foot (100 % solid): a Ø144 x 5 foot on the TM pattern (4 x M5 x 16
    counterbored through it into the head ring's inserts, 2 x Ø5 dowel holes, a Ø65 centre opening (wider than the
    TM's Ø45 so the pan_spacer and the circlip go on from below), six lightening windows), a housing tube holding the
    61810 outer race (Ø65 seat on a Ø62 shoulder; the pan_clamp holds it down with 3 x M3 into the housing ears), the
    STS3215 pan servo in a pocket on four posts (4 x M2 x 20 up through the foot into its idler face; its bus plugs
    have 12 mm under it and the lead goes through the housing tube to the centre), a 2.5 mm drip skirt, a flat pad with the DT04-12PA flange receptacle on the -y side (window for its body, 2 x M3
    inserts), a window into the housing for the cable, three inserted bosses for the slip ring's carrier with its tabs'
    pockets under the foot, the base-board bay (a wall at +x carrying a 50 x 35 board on 4 x M3), 5 tabs with M3
    inserts that carry the TPU bumper ring, and (only with CONTINUOUS_PAN off) the pan hard-stop post at the front."""
    t = G.foot_t
    hz1 = G.brg_z + BRG['B']
    s = cyl_z(G.base_r, 0, t)
    s = s.union(ring_z(G.base_r, G.base_r - 2.5, 0, 18))                                    # drip skirt
    s = s.union(ring_z(35.5, 32.5, 0, G.brg_z - 2))                                         # housing tube
    s = s.union(ring_z(G.housing_r_out, BRG['D_land'] / 2, G.brg_z - 2, hz1))               # bearing seat ring
    for a in CLAMP_EARS:                                                                    # clamp ears
        ear = box(G.housing_r_out - 0.5, 42.0, -7, 7, hz1 - 4, hz1).rotate((0, 0, 0), (0, 0, 1), a)
        s = s.union(ear).union(cyl_z(7.0, hz1 - 4, hz1, *polar(42.0, math.radians(a))))
    # pan servo pocket (walls 3 mm up to 25 mm over its idler face, servo + 0.3 mm) and the four posts it stands on
    sx, sy = G.servo_pan_xy
    W, L, sft = SERVO['W'], SERVO['L'], SERVO['shaft_from_end']
    px0, px1, py0, py1 = sx - W / 2 - 0.3, sx + W / 2 + 0.3, sy - sft - 0.3, sy + L - sft + 0.3
    s = s.union(box(px0 - 3, px1 + 9.0, py0 - 3, py1 + 3, 0, G.servo_z0 + 25))   # inner wall runs well into the housing tube
    s = s.cut(box(px0, px1, py0, py1, t, G.servo_z0 + 40))
    posts = [(sx + sgn * SERVO['holes_x'], sy + d) for sgn in (1, -1) for d in SERVO['holes_idler']]
    for (x, y) in posts:
        s = s.union(cyl_z(2.75, t - 0.01, G.servo_z0, x, y))
    s = s.union(box(-29, 29, -G.dt_y, -(G.base_r - 8), 0, DT_Z + DT['flange'][2] / 2 + 1.0))   # DT pad (-y)
    if not CONTINUOUS_PAN:
        s = s.union(box(G.post_r[0], G.post_r[1], -4, 4, 0, G.post_top))                    # hard-stop post (front)
    C = CARRIER
    for a in C['tab_angles']:                                                               # the carrier's screw bosses
        s = s.union(box(32.6, C['screw_r'] + 4.5, -6, 6, 0, C['tab_t'] + 9.0).rotate((0, 0, 0), (0, 0, 1), a))
    s = s.union(box(BB['x0'], BB['x0'] + BB['t'], -BB['w'] / 2, BB['w'] / 2, 0, BB['h']))     # the base-board bay's wall
    for (y, z) in BB['holes']:                                                              # and its 4 standoff bosses
        s = s.union(cyl_x(3.5, BB['x0'] - BB['standoff'], BB['x0'] + 0.01, y, z))
    for a in BUMPER_TABS:
        s = s.union(box(G.base_r - 1, BUMPER_LUG[1], -6, 6, 0, G.bumper_z[0]).rotate((0, 0, 0), (0, 0, 1), a))
    # --- cuts
    s = s.cut(cyl_z(BRG['D'] / 2, G.brg_z, hz1 + 1))                                       # bearing seat
    s = s.cut(cyl_z(32.5, -1, G.brg_z - 2 + 0.01))                                         # centre opening and the tube's bore
    for (x, y) in TM_BOLTS:
        s = s.cut(through_z(x, y, FAST['M5']['clear'], -1, 60)).cut(cyl_z(5.0, t - 0.01, 60, x, y))
    for (x, y) in TM_DOWELS:
        s = s.cut(cyl_z(2.5, -1, t - 1.0, x, y))
    for a in (67.5, 112.5, 247.5, 292.5):                                                  # foot windows (none under the bay)
        s = s.cut(sector_z(40.0, 63.0, a - 10, a + 10, -1, t + 1))
    for a in C['tab_angles']:                                                               # tab pockets under the foot
        s = s.cut(sector_z(C['r'] - 0.5, C['tab_r'] + 0.3, a - 13.3, a + 13.3, -1, C['tab_t']))
        x, y = polar(C['screw_r'], math.radians(a))
        s = s.cut(cyl_z(FAST['M3']['insert_pilot'] / 2, C['tab_t'] - 0.1, C['tab_t'] + 7.0, x, y))     # M3 insert from below
    for (y, z) in BB['holes']:                                                              # 4 x M3 inserts for the board
        s = s.cut(cyl_x(FAST['M3']['insert_pilot'] / 2, BB['x0'] - BB['standoff'] - 0.1, BB['x0'] - BB['standoff'] + 6.0, y, z))
    for a in CLAMP_EARS:
        x, y = polar(42.0, math.radians(a))
        s = s.cut(insert_hole(x, y, hz1, 'M3', 6.0))
    for (x, y) in posts:                                                                    # M2 up into the servo
        s = s.cut(through_z(x, y, 2.4, -1, G.servo_z0 + 1)).cut(cyl_z(2.1, -1, 2.2, x, y))
    s = s.cut(box(sx + 4, -26.0, sy - 7, sy + 7, t, G.servo_z0 - 1))                         # the servo's lead to the centre
    cw, ch = DT['cutout']
    s = s.cut(box(-cw / 2, cw / 2, -G.dt_y - 1, -(G.base_r - 30), DT_Z - ch / 2, DT_Z + ch / 2))  # the receptacle's body goes in
    for sx_ in (-1, 1):
        for sz_ in (-1, 1):
            x, z = sx_ * DT['holes'][0] / 2, DT_Z + sz_ * DT['holes'][1] / 2
            s = s.cut(cyl_y(FAST['M4']['insert_pilot'] / 2, -G.dt_y - 0.1, -G.dt_y + 8.0, x, z))     # 4 x M4 inserts
    s = s.cut(box(-10, 10, -40, 0, t, t + 18))                                              # cable window (-y)
    for a in BUMPER_TABS:
        x, y = polar(BUMPER_BOLT_R, math.radians(a))
        s = s.cut(insert_hole(x, y, G.bumper_z[0], 'M3', 5.5))                             # short insert, 4.3 mm
    return s


BUMPER_TABS = (30.0, 90.0, 150.0, 210.0, 330.0)   # none straight ahead: the lidar is 10 mm from the bumper there
# the 4 mm bumper is widened to a lug at each tab (r 80..87.5) for its screw and washer
BUMPER_LUG = (80.0, 87.5)
BUMPER_BOLT_R = 84.0
DT_Z = 19.0
# the base-board bay (docs/turret-plan.md 3.3): the 555 safety-pulse oscillator, the pan servo's 12 V regulator, the
# ring's stator connector; a 50 x 35 board standing on 5 mm standoffs on the wall's inner face, components inwards
BB = {'x0': 53.0, 't': 3.0, 'w': 54.0, 'h': 38.0, 'holes': ((-22.4, 9.0), (22.4, 9.0), (-22.4, 33.0), (22.4, 33.0)),
      'board': (30.0, 50.8, 1.6), 'standoff': 5.0, 'parts_h': 12.0}   # Adafruit 1608 Perma-Proto cut to 30 x 50.8, corners drilled
# the ring's rotor leads: a Ø7.5 bundle on -y, 13 mm off the axis (3 mm from the turntable's bore)
LEADS = {'d': 7.5, 'r': 13.0, 'z_run': 89.0}


def sector_z(r0, r1, a0, a1, z0, z1, n=16):
    """An annular sector about the z axis (angles in degrees)."""
    a = [math.radians(a0 + (a1 - a0) * k / n) for k in range(n + 1)]
    pts = [polar(r1, t) for t in a] + [polar(r0, t) for t in reversed(a)]
    return cq.Workplane('XY').polyline(pts).close().extrude(z1 - z0).translate((0, 0, z0))


def pan_clamp(G):
    """The clamp ring, laser-cut by SendCutSend from 0.125 in (3.175 mm) 6061-T6 aluminium (exports/turret/pan_clamp.dxf):
    Ø61 to Ø74, its bore over the 6810's outer race by 1.5 mm, holding it down with 5 x M3 x 8 into the housing ears at
    CLAMP_EARS (none at 180 deg, where the pan servo stands); its Ø74 outside keeps 1.25 mm from the pinion's tips. A
    printed ring of the same outline needed 5 mm of PA6-CF and still only just passed (FEA); aluminium is four times as
    strong and 1.8 mm thinner. The turntable's shoulder passes through it with 2.5 mm to spare. The pan index
    magnet (3/16 x 1/8 in disc) sits through it on the housing's top at pan 0, under the hall switch in the turntable."""
    z0 = G.brg_z + BRG['B']
    t = CLAMP_T
    s = ring_z(G.housing_r_out, 30.5, z0, z0 + t)
    for a in CLAMP_EARS:
        lug = box(0, 46.0, -7, 7, z0, z0 + t).rotate((0, 0, 0), (0, 0, 1), a)
        s = s.union(lug.cut(cyl_z(G.housing_r_out, z0 - 1, z0 + t + 1)).union(cyl_z(7.0, z0, z0 + t, *polar(42.0, math.radians(a)))))
        s = s.cut(through_z(*polar(42.0, math.radians(a)), FAST['M3']['clear']))
    s = s.cut(cyl_z(30.5, z0 - 1, z0 + t + 1))
    s = s.cut(cyl_z(MAGNET['d'] / 2 + 0.05, z0 - 1, z0 + 4, MAGNET['r'], 0.0))      # the pan index magnet: on the housing's top, through the clamp
    return s


def pan_pinion(G):
    """21 T module 1.25 spur pinion (printed PA6-CF, 16 mm face, full-round roots) on a Ø20 flange that screws to the
    STS3215's aluminium horn: 4 x M3 x 16 on Ø14 into the horn's tapped holes, their heads sunk flush, a Ø6.5 hole over
    the horn's centre screw. 63 : 21 = 3 : 1, so the 2.94 N·m servo gives 8.8 N·m at the turntable. FEA of one tooth
    loaded at its tip (cad/turret_studies.py): SF 1.26 at the servo's stall (rare, >= 1.2) and 2.52 at the firmware's
    50 % torque cap (everyday, >= 2); the 12 mm face with sharp roots was SF 0.49 at stall."""
    m = G.gear
    x, y = G.servo_pan_xy
    z0 = G.servo_z0 + SERVO['H'] + SERVO['horn_t']
    z1 = z0 + 1.0 + PINION_FACE
    s = spur(m['m'], m['z_pinion'], z0 + 1.0, z1, x, y).union(cyl_z(10.0, z0, z0 + 1.0, x, y))
    s = s.cut(cyl_z(3.25, z0 - 1, z1 + 1, x, y))                                         # over the horn's centre screw
    for k in range(4):
        hx, hy = polar(SERVO['horn_pcd'] / 2, math.pi / 4 + k * math.pi / 2)
        s = s.cut(cyl_z(FAST['M3']['clear'] / 2, z0 - 1, z1 + 1, x + hx, y + hy)).cut(cyl_z(2.9, z1 - 3.4, z1 + 1, x + hx, y + hy))
    return s


def bumper_ring(G):
    """TPU 95A ring, 4 mm wide and 14 mm tall, widened to a lug at each of the base's five tabs for its M3 screw and
    washer; a gap
    on -y lets the DT plug in. It takes the knocks before the pan base does."""
    s = ring_z(G.bumper_r[1], G.bumper_r[0], *G.bumper_z)
    for a in BUMPER_TABS:
        s = s.union(sector_z(BUMPER_LUG[0], BUMPER_LUG[1], a - 7.0, a + 7.0, *G.bumper_z))
    s = s.cut(box(-31, 31, -120, -50, 0, 40))
    for a in BUMPER_TABS:
        s = s.cut(through_z(*polar(BUMPER_BOLT_R, math.radians(a)), FAST['M3']['clear']))
    return s


# ------------------------------------------------------------------------------------------------ pan parts (turn with pan)

def circlip_z(G):
    """(bottom, top) of the DIN 471-50 ring: it pushes the pan_spacer up into the 61810's inner race."""
    top = G.brg_z - SPACER['h']
    return top - CIRCLIP['s'], top


def pan_ring(G):
    """The turntable, printed PA6-CF upside down (100 % solid): a 63 T module 1.25 spur gear (16 mm face) with a
    Ø40 open centre, a shoulder that sits on the 61810's inner race (only inside Ø52.4: a 1 mm relief keeps it off
    the shield), a Ø50 journal through it, the pan_spacer and a DIN 471-50 circlip below the race (the journal runs
    6 mm past the groove), 4 x M4 inserts for the tilt yoke, the pan index hall switch in a pocket in its underside
    3 mm over the magnet in the clamp ring (its leads up a Ø2.8 hole), and, only with CONTINUOUS_PAN off, the pan stop
    finger at the rear (reaches over the pinion and meets the base's post at +-173.5 deg; software limit +-170)."""
    z0, z1 = G.turntable_z
    m = G.gear
    s = spur(m['m'], m['z_ring'], z0, z1)
    s = s.union(ring_z(28.0, 20.0, G.brg_z + BRG['B'], z0 + 0.01))                         # shoulder on the inner race
    cz0, cz1 = circlip_z(G)
    groove0 = cz1 - CIRCLIP['m']
    s = s.union(ring_z(BRG['d'] / 2, 20.0, groove0 - JOURNAL_LIP, G.brg_z + BRG['B'] + 0.01))   # journal
    if not CONTINUOUS_PAN:
        s = s.union(box(-G.post_r[1], -30.0, -4, 4, z1, z1 + 3.0))                          # stop finger: arm over the pinion
        s = s.union(box(-G.post_r[1], -G.post_r[0], -4, 4, z0, z1 + 3.0))                   # ... and down beside it
    s = s.cut(cyl_z(20.0, z0 - 30, z1 + 1))
    s = s.cut(ring_z(BRG['d'] / 2 + 1, CIRCLIP['d2'] / 2, groove0, cz1))                   # circlip groove
    s = s.cut(ring_z(28.5, BRG['d_land'] / 2, G.brg_z + BRG['B'] - 0.1, G.brg_z + BRG['B'] + 1.0))   # shield relief
    for (x, y) in YOKE_BOLTS:
        s = s.cut(insert_hole(x, y, z1, 'M4'))
    for k in range(6):                                                                      # lightening pockets from below
        a = 30.0 + 60.0 * k
        # outside the shoulder (r 28) by 1 mm: cut from r 23 they notched the shoulder's root, where the side-fall case
        # peaked (FEA: SF 1.12); 1 mm under the yoke's insert pilots
        s = s.cut(sector_z(29.0, 34.0, a - 20.0, a + 20.0, z0 - 0.01, z0 + 7.0))
    hx, hy, hz = HALL['size']
    s = s.cut(box(MAGNET['r'] - hx / 2 - 0.2, MAGNET['r'] + hx / 2 + 0.2, -hy / 2 - 0.2, hy / 2 + 0.2, z0 - 1, z0 + 0.1 + hz))  # hall switch: CA'd up against the pocket's roof
    s = s.cut(cyl_z(1.4, z0, z1 + 1, MAGNET['r'] - 3.5, 0.0))                              # its 3 leads up through
    return s


def pan_spacer(G):
    """Printed PA6-CF thrust ring (100 % solid) between the 61810's inner race and the DIN 471-50 circlip: it slides
    up the journal (Ø50.3 bore), bears on the race only inside Ø52.4 (a 1 mm land) and holds the circlip, whose back
    and lugs reach Ø60.8, 4 mm below the bearing's shield. Print it standing on its wide end."""
    z1 = G.brg_z
    z0 = z1 - SPACER['h']
    s = ring_z(SPACER['r_out'], BRG['d'] / 2 + 0.15, z0, z1 - SPACER['land_h'])
    return s.union(ring_z(BRG['d_land'] / 2, BRG['d'] / 2 + 0.15, z1 - SPACER['land_h'] - 0.01, z1))


YOKE_BOLTS = [(10.0, 28.0), (-10.0, 28.0), (10.0, -28.0), (-10.0, -28.0)]
# sheet stock for the parts ordered from SendCutSend (D40), by their catalogue names
SHEET = {'al6061': {'name': '6061-T6 aluminium', 'thickness_mm': 3.175, 'thickness_in': 0.125, 'density_g_cm3': 2.70,
                    'vendor': 'SendCutSend', 'url': 'https://sendcutsend.com/materials/6061-t6-aluminum/'},
         'al6061_100': {'name': '6061-T6 aluminium', 'thickness_mm': 2.54, 'thickness_in': 0.100, 'density_g_cm3': 2.70,
                        'vendor': 'SendCutSend', 'url': 'https://sendcutsend.com/materials/6061-t6-aluminum/'}}
# the SendCutSend cart (D40, D48): the pan clamp, the cradle's two cheek plates and the hard-stop lug; each with what
# the order adds to the plain cut (tapped holes, countersinks), and which face of the part is its DXF's face
SHEET_PARTS = {'pan_clamp': 'al6061', 'cradle_plate_l': 'al6061', 'cradle_plate_r': 'al6061', 'stop_lug': 'al6061_100'}
SHEET_OPS = {'pan_clamp': 'none',
             'cradle_plate_l': '4 holes countersunk 90 deg to Ø6.4 on the face drawn (the face on the rail; DIN 7991 M3 flat heads)',
             'cradle_plate_r': 'the Ø4.2 hole tapped M5 x 0.8; 2 holes countersunk 90 deg to Ø6.4 on the face drawn (the face on the rail)',
             'stop_lug': '2 holes tapped M3 x 0.5'}
# D48 (docs/turret-next-plan.md 1.3): the cradle is a printed PA6-CF rail frame with two laser-cut cheek plates. Each
# plate is an inverted T in the x-z plane (C frame): a foot on its rail along x -10..80 (10 mm, the rail's depth there)
# with four M3 x 8 button heads into inserts in the rail's 3.2 mm rebate, and a 44 mm cheek up to the Ø44 round at the
# tilt axis. The rebate brings the plate's outer face back to where the printed cheek's was (y +-56.5): 4 mm from the
# yoke's arm, as before. The +y plate carries the tilt servo's horn through a printed boss (horn_boss, 4 x M3 x 14 flat
# heads from the plate's inner face); the -y plate is tapped M5 for the shoulder screw (the printed pivot_spacer and its
# land between the plate and the MR126) and carries the aluminium hard-stop lug on its outer face.
# The plan's 12 mm feet (rails 12 deep there) passed 0.37 mm over the slip ring's rotor-lead bundle where it crosses the
# yoke's bridge (z 89) at full depression: 10 mm keeps 2.3 mm.
PLATE = {'foot_x': (-10.0, 80.0), 'foot_h': 10.0, 'half_w': 22.0, 'rebate': 3.2, 'foot_holes_x': (-3.0, 33.0, 58.0, 70.0),
         'fillet': 5.0, 'csk_d': 6.4, 'horn_screw_l': 14.0, 'rebate_back': 2.5, 'rebate_fillet': 2.0}      # csk: DIN 7991 M3 heads are Ø6.0 (McMaster 91294A, 92125A)
# the hard stop (D48): a 2.54 mm 6061-T6 lug on the -y plate's outer face, 1.5 mm from the yoke's arm. Its stop band
# (+-STOP_HALF_DEG about straight down at tilt 0, r 22.5..32) meets the yoke's two sectors (r 24..32, YOKE_STOP_PROUD off
# the arm's inner face: 1.5 mm onto the lug); its pad (r 11..22.5, +-32 deg) sits inside the sectors' annulus with two
# M3 x 6 flat heads from the plate's inner face into holes tapped in it (and a drop of CA gel). Wider than v0's printed
# lug (+-7.5 deg): the band's root is the lug's weak section, and the sectors moved with it, so the range is still 0..-25.
STOP_HALF_DEG = 10.0
YOKE_STOP_PROUD = 3.0
YOKE_ROOT_FILLET = (6.0, 3.0)     # where the arms meet the bridge (D48's FEA): 6 mm, but 3 under the rotor leads ...
YOKE_LEAD_GAP = 6.0               # ... within this of x = 0, where they cross the bridge's top (1.25 mm over the 3 mm fillet)
YOKE_STOP_BUTTRESS = 5.0          # each stop sector's buttress reaches this far past its r 32
YOKE_WINDOW_R = 3.0               # the -y arm's lead window, its corners ...
YOKE_WINDOW_HALF_X = 6.0          # ... and its half width (the rotor-lead bundle is Ø7.5 at x = 0)
LUG = {'band_r': (22.5, 32.0), 'pad_r': (11.0, 22.5), 'pad_half_deg': 32.0, 'screw_r': 17.0, 'screw_deg': 15.0, 'fillet': 1.5,
       'screw_l': 6.0}
# the printed parts between the plates and the yoke: the horn boss (+y, Ø20, the horn's 4 x M3 on Ø14 and its centre
# screw's Ø6.5) and the pivot spacer (-y: a Ø18 boss on the plate and a Ø6.8 x 1 land on the MR126's inner race, the
# shoulder screw's step seated on the land as v0's was on its insert; bore Ø5.3 for the M5 thread)
HORN_BOSS = {'d': 20.0}
PIVOT = {'boss_d': 18.0, 'land_d': 6.8, 'land_h': 1.0, 'bore': 5.3}
CLAMP_EARS = (0.0, 60.0, 120.0, 240.0, 300.0)      # the pan servo stands at 180 deg
CLAMP_T = 3.175                                   # SendCutSend 6061-T6 aluminium, 0.125 in
YOKE_RELIEF = {'r': 35.0, 'h': 1.5, 'chamfer': 3.0}    # the bridge bears on the turntable inside r 35; a cone to 1.5 mm up at r 38
# printed with 4 perimeters, 5 top and bottom layers and 40 % gyroid instead of solid (mass): the pan base's walls are
# all perimeter at that, and its FEA peaks sit in them (cad/turret_studies.py)
PARTIAL_FILL = {'pan_base'}
PINION_FACE = 16.0


def ring_geom(G, model=None):
    """z of the slip ring's flange seat, body top and stub top, and the driver's socket (T frame)."""
    M = RING_MODELS[model or RING_MODEL]
    seat = CARRIER['h'] - CARRIER['flange_seat']
    body0 = seat + M['flange'][1]
    top = body0 + M['body_l'] - M['flange'][1]
    stub_top = top + M['stub'][1]
    drv0 = G.turntable_z[1] - 6.0
    return {'seat': seat, 'body0': body0, 'top': top, 'stub_top': stub_top, 'driver': (drv0, G.turntable_z[1]),
            'socket': (drv0 - 8.0, drv0), 'M': M}


def ring_carrier(G):
    """The slip ring's carrier, printed PA6-CF on its top face (100 % solid): a Ø64.5 x 12 disc in the foot's Ø65
    opening with three tabs that sit flush in pockets under the foot (3 x M3 x 10 flat heads up into the housing
    tube's inserted bosses); a Ø44.6 x 2.6 seat on top for the ring's flange (3 x M3 x 8 with washers into inserts on
    Ø35: measure the ring in hand), a Ø23.1 bore for its body, and a slot from the bore to the side towards -y for the
    stator leads, which climb the housing to its cable window. The head ring (or the stand's top) traps it from
    below once the turret is mounted: the ring is serviced with the turret off its mount."""
    C = CARRIER
    rg = ring_geom(G)
    M = rg['M']
    s = cyl_z(C['r'], 0, C['h'])
    for a in C['tab_angles']:
        s = s.union(sector_z(C['r'] - 1.0, C['tab_r'], a - 12.0, a + 12.0, 0, C['tab_t']))
    s = s.cut(cyl_z(M['flange'][0] / 2 + 0.05, rg['seat'], C['h'] + 1))                        # flange seat
    s = s.cut(cyl_z(C['bore'] / 2, -1, C['h'] + 1))                                          # body / stator leads
    s = s.cut(box(-5.0, 5.0, -C['r'] - 1, 0, 1.5, rg['seat'] - 1.0))                         # stator lead slot to -y
    for k in range(3):
        x, y = polar(M['pcd'] / 2, math.radians(90 + 120 * k))
        s = s.cut(cyl_z(FAST['M3']['insert_pilot'] / 2, rg['seat'] - 6.0, rg['seat'] + 0.1, x, y))     # flange screws
    for a in C['tab_angles']:
        x, y = polar(C['screw_r'], math.radians(a))
        s = s.cut(through_z(x, y, FAST['M3']['clear'], -1, C['tab_t'] + 1))
        s = s.cut(cq.Workplane('XY').circle(3.4).workplane(offset=1.9).circle(1.7).loft().translate((x, y, -0.01)))   # countersink
    for k in range(3):                                                                      # pockets from below, between the
        a = 90 + 120 * k + 60                                                               # flange inserts, off the tabs
        if any(abs(((a - t + 180) % 360) - 180) < 22 for t in C['tab_angles']) or abs(((a - 270 + 180) % 360) - 180) < 25:
            continue
        s = s.cut(sector_z(C['bore'] / 2 + 2.0, C['r'] - 3.0, a - 32, a + 32, -1, rg['seat'] - 2.0))
    return s


def ring_driver(G):
    """The slip ring's driver, printed PA6-CF: a Ø39.6 x 6 disc held in the top of the turntable's Ø40 bore (three
    crush ribs, a drop of CA), a socket under it (Ø7.64 inside, 8 deep) that grips the rubber tube coupling the
    ring's rotor stub (the tube pushed in), and a crescent slot beside it for the rotor leads. It turns the ring's rotor with the
    turntable and never pushes on it: the tube takes the misalignment."""
    rg = ring_geom(G)
    d0, d1 = rg['driver']
    k0, k1 = rg['socket']
    s = cyl_z(19.7, d0, d1)
    for k in range(3):
        s = s.union(cyl_z(0.5, d0, d1, *polar(19.7, math.radians(30 + 120 * k))))             # crush ribs (0.2 mm interference)
    s = s.union(ring_z(7.0, TUBE['socket_d'] / 2, k0, d0 + 0.01))                            # the socket (the tube pushed in)
    s = s.cut(cyl_z(TUBE['socket_d'] / 2, k0 - 1, d1 - 2.0))
    s = s.cut(sector_z(LEADS['r'] - LEADS['d'] / 2 - 0.75, LEADS['r'] + LEADS['d'] / 2 + 0.75, 230.0, 310.0, d0 - 1, d1 + 1))   # the leads' crescent
    return s


# the turret-board bay (docs/turret-plan.md 2.4, 3.3): a PETG tray on the -y yoke arm's outer face holding three
# 52 x 50 boards (perfboard cut to size, Ø3.2 holes drilled at the corners), stacked on M3 standoffs. What sits on each
# is cad/turret_boards.py's (checked there part by part): level 0 (on the tray's bosses) the D24V150F12 12 V regulator
# (43.2 x 31.8 x 11) and the laser's switch; level 1 (on 12 mm standoffs) the Pololu 2815 switch, the D36V28F5 5 V
# regulator, the 2 x 1000 uF bank lying down, the opto and the one-shots; level 2 (on 14 mm standoffs) the Feather M4
# CAN (50.8 x 22.8), the trip latch, the ARM gate and the servo bus buffer. The tray reaches y -115 at x +-29 (r 118.6): the tilt servo on the other arm already sweeps r 112, and
# nothing fixed stands above z 69 out there (the pinion's top), so it clears every pan.
TB = {'x': 29.0, 'z': (71.0, 128.0), 'y_out': 115.0, 'wall': 1.2, 'back': 3.0, 'board': (52.0, 50.0, 1.6), 'boss': 5.0,
      'levels': ((11.0, 12.0), (12.5, 14.0), (8.5, None)),        # (tallest part, standoff to the next board) per level
      'screws': ((10.0, 78.0), (-10.0, 78.0), (10.0, 121.0), (-10.0, 121.0)), 'mass_g': 100.0}


def bay_boards(G):
    """The boards' corner holes (x, z) and each board's underside y (T frame), level 0 first."""
    a1 = G.arm_y[1]
    zc = sum(TB['z']) / 2
    bw, bh, bt = TB['board']
    holes = [(sx * (bw / 2 - 3.0), zc + sz * (bh / 2 - 3.0)) for sx in (1, -1) for sz in (1, -1)]
    ys = [-a1 - TB['back'] - TB['boss']]
    for _, gap in TB['levels'][:-1]:
        ys.append(ys[-1] - bt - gap)
    return holes, ys


def board_bay(G):
    """The turret-board bay, printed PETG on its back: a 58 x 57 tray with 2 mm walls out to y -115, screwed to the -y
    yoke arm's outer face with 4 x M3 x 8 flat heads (countersunk in its 3 mm back, into inserts in the arm, beside and
    under the arm's lightening window; fit them before the boards), 4 bosses with M3 inserts for the level-0 board,
    and a window in the back for the ring's rotor leads, which come through the arm's window. The open face takes a
    snap lid (not modelled)."""
    a1 = G.arm_y[1]
    X, (z0, z1), Y, w, t = TB['x'], TB['z'], TB['y_out'], TB['wall'], TB['back']
    s = box(-X, X, -Y, -a1, z0, z1).cut(box(-X + w, X - w, -Y - 1, -a1 - t, z0 + w, z1 - w))
    holes, ys = bay_boards(G)
    y1 = ys[0]
    for (x, z) in holes:
        s = s.union(cyl_y(5.0, y1, -a1 - t + 0.01, x, z))                                  # into the side wall and floor
        s = s.cut(cyl_y(FAST['M3']['insert_pilot'] / 2, y1 - 0.1, y1 + 6.0, x, z))      # 5.7 mm insert: into the back
    for (x, z) in TB['screws']:
        s = s.cut(cyl_y(FAST['M3']['clear'] / 2, -a1 - t - 1, -a1 + 0.1, x, z))
        s = s.cut(cq.Workplane('XZ').circle(3.3).workplane(offset=-1.8).circle(1.7).loft().translate((x, -a1 - t - 0.01, z)))   # countersink
    rl = LEADS['d'] / 2 + 1.5
    s = s.cut(box(-11.0, 11.0, -a1 - t - 1, -a1 + 0.1, LEADS['z_run'] - rl, LEADS['z_run'] + rl))   # the rotor leads come in
    return s


def tilt_yoke(G):
    """Printed PA6-CF on its back (layers run along the arms): a 12 mm bridge on the turntable (4 x M4) and two 8 mm
    arms up to the tilt axis, a 3 mm fillet where each meets the bridge. +y arm: a pocket for the STS3215 tilt servo on its outer face, the servo's output face
    on four pads round its M2 holes (the rest relieved 1.5 mm for its label band), 4 x M2 x 10 from the arm's inner face
    (heads sunk), its horn through a Ø26 hole; its bus plugs face outwards. -y arm: the MR126 seat on the inner face (a Ø9.4 x 1.3 relief in its floor, so only
    the fixed outer race sits on it, not the inner race that turns with the cradle), a Ø6.5 hole for the ISO 7379
    6 x 12 shoulder screw. The hard stop: two sectors on the -y arm's inner face, 3.0 mm proud, that the cradle's
    aluminium lug (D48) hits at tilt 0 (barrel horizontal; it cannot go above) and at -25 deg. Outside r 37 its underside stands 1.5 mm above the
    turntable's top, so the pan pinion (16 mm face, level with the turntable's top) passes under it."""
    zt = G.tilt_t
    b0, b1 = G.bridge_z
    a0, a1 = G.arm_y
    s = box(-20, 20, -a1, a1, b0, b1)
    for sgn in (1, -1):
        y0, y1 = (a0, a1) if sgn > 0 else (-a1, -a0)
        arm = box(-20, 20, y0, y1, b0, zt).union(cyl_y(20.0, y0, y1, 0, zt))
        s = s.union(arm)
        # a concave fillet where the arm's inner face meets the bridge's top: the 50 N push and the falls peaked in that
        # sharp corner (FEA, with the stresses split by the layers: interlaminar shear at the arm's foot)
        yi = sgn * a0
        r = YOKE_ROOT_FILLET[1]
        s = s.union(box(-20, 20, yi - sgn * r, yi, b1 - 0.01, b1 + r).cut(cyl_x(r, -21, 21, yi - sgn * r, b1 + r)))
        r = YOKE_ROOT_FILLET[0]                                 # the bigger fillet everywhere but under the rotor leads
        for xa, xb in ((-20.0, -YOKE_LEAD_GAP), (YOKE_LEAD_GAP, 20.0)):
            s = s.union(box(xa, xb, yi - sgn * r, yi, b1 - 0.01, b1 + r).cut(cyl_x(r, xa - 1, xb + 1, yi - sgn * r, b1 + r)))
    # tilt servo pocket on the +y arm (servo + 0.3, walls 3, 15 deep)
    W, L, sft = SERVO['W'], SERVO['L'], SERVO['shaft_from_end']
    pocket = box(-W / 2 - 3.3, W / 2 + 3.3, a1, a1 + 15, zt - (L - sft) - 3.3, zt + sft + 3.3)
    s = s.union(pocket).cut(box(-W / 2 - 0.3, W / 2 + 0.3, a1, a1 + 16, zt - (L - sft) - 0.3, zt + sft + 0.3))
    holes = [(sgn * SERVO['holes_x'], zt - d) for sgn in (1, -1) for d in SERVO['holes_out']]
    relief = box(-W / 2 - 0.3, W / 2 + 0.3, a1 - 1.5, a1 + 0.01, zt - (L - sft) - 0.3, zt + sft + 0.3)
    for (x, z) in holes:
        relief = relief.cut(cyl_y(3.0, a1 - 2, a1 + 1, x, z))
    s = s.cut(relief)
    for (x, z) in holes:
        s = s.cut(cyl_y(1.2, a0 - 1, a1 + 1, x, z)).cut(cyl_y(2.1, a0 - 1, a0 + 2.0, x, z))
    # hard stops on the -y arm's inner face; the cradle's aluminium lug (D48) sits at -90 deg at tilt 0 and sweeps to
    # -115 at -25. The sectors stand YOKE_STOP_PROUD (3.0) off the arm: 1.5 mm onto the lug, 1.0 mm from the -y plate
    w = STOP_HALF_DEG
    up_face, low_face = -90 + w, -90 + G.tilt_min - w
    # each sector clipped to the arm's width: their far ends overhung the arm's edges (never loaded) and left slivers
    # where the faceted arcs crossed them (zero-volume elements in the FEA mesh)
    clip = box(-20.0, 20.0, -a0 - 1.0, -a0 + YOKE_STOP_PROUD + 1.0, b0, zt + 40.0)
    s = s.union(arc_sector_y(G.stop_r[0], G.stop_r[1], up_face, up_face + 30, -a0, -a0 + YOKE_STOP_PROUD, 0, zt).intersect(clip))
    s = s.union(arc_sector_y(G.stop_r[0], G.stop_r[1], low_face - 30, low_face, -a0, -a0 + YOKE_STOP_PROUD, 0, zt).intersect(clip))
    # behind each stop face a buttress carries the sector's root further out (the push's peak was the interlaminar shear
    # at the root's outer corner beside the stop face); it starts 2 deg behind the face, so the lug's contact is still
    # r 24..32 and the lug never reaches it (1.1 mm at the stop)
    b0r, b1r, off = G.stop_r[1] - 1.0, G.stop_r[1] + YOKE_STOP_BUTTRESS, 2.0
    s = s.union(arc_sector_y(b0r, b1r, up_face + off, up_face + 30, -a0, -a0 + YOKE_STOP_PROUD, 0, zt).intersect(clip))
    s = s.union(arc_sector_y(b0r, b1r, low_face - 30, low_face - off, -a0, -a0 + YOKE_STOP_PROUD, 0, zt).intersect(clip))
    # holes
    # a window in the -y arm for the ring's rotor leads (round-cornered: the side falls peaked at a square corner); the
    # +y arm has none since D48 (nothing passes it, and the +y fall peaked at its window's corner)
    # (12 x 10.5, just round the Ø7.5 bundle: v0's 24 x 14 window left 8 mm of arm each side, and with the stiffer root
    # fillets the side fall and the push peaked at its corners)
    wz0, wz1 = LEADS['z_run'] - LEADS['d'] / 2 - 0.75, LEADS['z_run'] + LEADS['d'] / 2 + 2.25
    s = s.cut(cq.Workplane('XZ', origin=(0, -a0 + 1, 0)).center(0, (wz0 + wz1) / 2).rect(2 * YOKE_WINDOW_HALF_X, wz1 - wz0)
              .extrude(a1 - a0 + 2).edges('|Y').fillet(YOKE_WINDOW_R))
    s = s.cut(cyl_y(13.0, a0 - 1, a1 + 1, 0, zt))                                           # servo horn
    s = s.cut(cyl_y(MR126['D'] / 2, -a0 - MR126['B'], -a0 + 3, 0, zt))                      # MR126 seat (inner face)
    s = s.cut(cyl_y(4.7, -a0 - MR126['B'] - 1.3, -a0 - MR126['B'] + 0.01, 0, zt))          # relief: only the outer race sits
    s = s.cut(cyl_y(3.25, -a1 - 1, -a0, 0, zt))
    rl = LEADS['d'] / 2 + 3.0                                                               # the ring's rotor leads pass here (3 mm clear)
    s = s.cut(box(-rl, rl, -LEADS['r'] - rl, -LEADS['r'] + rl, b0 - 1, b1 + 1))
    # the pinion's top is level with the turntable's (z 69): outside the turntable's gear (r 38 up, where the pinion's
    # teeth reach) the bridge and the arms' feet stand 1.5 mm clear of that plane, so the pinion passes under them at
    # every pan. The relief is a 27 deg cone from r 35 to r 38 (it was three 0.5 mm steps: the E-push case's peak sat
    # in the first step's re-entrant corner, cad/turret_studies.py)
    r0r, hr, ch = YOKE_RELIEF['r'], YOKE_RELIEF['h'], YOKE_RELIEF['chamfer']
    cone = (cq.Workplane('XZ').polyline([(r0r, b0), (r0r + ch, b0 + hr), (110.0, b0 + hr), (110.0, b0 - 1.0), (r0r, b0 - 1.0)])
            .close().revolve(360.0, (0, 0, 0), (0, 1, 0)))
    s = s.cut(cone)
    for (x, z) in TB['screws']:                                                             # the turret-board bay's inserts
        s = s.cut(cyl_y(FAST['M3']['insert_pilot'] / 2, -a1 - 0.1, -a1 + 6.0, x, z))
    for (x, y) in YOKE_BOLTS:
        # the heads sit 6 mm above the bridge's underside, so an M4 x 10 keeps 4 mm in the turntable's insert
        s = s.cut(through_z(x, y, FAST['M4']['clear'], b0 - 1, b1 + 1)).cut(cyl_z(4.0, b0 + 6.0, b1 + 1, x, y))
    return s


# ------------------------------------------------------------------------------------------------ tilting parts (C frame)

def cradle(G):
    """The cradle's rail frame (D48), printed PA6-CF flat (100 % solid, no supports): two rails under the cartridge
    joined by a rear cross bar (the latched cartridge ties the front; nothing hangs low at the nose when it tilts), the
    CT interface on the rails as v0 (2 x Ø4 dowel holes, the captive DIN 464 M4 x 12 thumbscrew up from below on an
    O-ring in a counterbore on the rail's top), and a tab at the front left for the laser mount (2 x M3 x 10 up through
    it). Along the cheek plates' feet (x -10..80) each rail is 10 mm deep and its outer face is rebated 3.2 mm: the
    aluminium plate sits in the rebate on 4 x M3 x 8 button heads into inserts, its outer face where v0's printed cheek
    was; the latch's collar sits in a pocket under the -y rail, 7 mm under its top as before. v0's cheeks, servo hub, pivot boss and hard-stop lug are gone (cradle_plate, stop_lug, horn_boss,
    pivot_spacer): re-solved by stress direction they failed across the layers in every print orientation
    (docs/turret-next-plan.md 1.3), while the frame is loaded in its own plane, along its layers."""
    r0, r1 = G.rail_y
    z0, z1 = G.rail_z
    xr0, xr1 = -(G.housing_r + 2.0), G.socket_x0 - 2.0
    fx0, fx1 = PLATE['foot_x']
    fz0 = G.foot_z[0]
    zb = min(fz0, z0 - RAIL_DEEP['dz']) - 1.0                    # below everything: the through holes start here
    s = None
    for sgn in (1, -1):
        ra, rb = (r0, r1) if sgn > 0 else (-r1, -r0)
        rail = box(xr0, xr1, ra, rb, z0, z1)
        rail = rail.union(box(xr0, RAIL_DEEP['x1'], ra, rb, z0 - RAIL_DEEP['dz'], z0 + 0.01))   # 2 mm deeper behind the front dowel
        rail = rail.union(box(fx0, fx1, ra, rb, fz0, z0 + 0.01))                                # 10 mm deep along the plate's foot
        s = rail if s is None else s.union(rail)
    s = s.union(box(xr0, xr0 + 8, -r1, r1, z0 - RAIL_DEEP['dz'], z1))                          # rear cross bar
    s = s.union(box(xr1 - 8, LASER_X[1] + 2, -r1 + 7, -22.0, z0, z1))                            # laser tab
    # the plates' rebates (0.3 mm longer than the foot at each end) and their 3 x M3 inserts, put in from the rebate
    p0 = G.plate_y[0]
    zf = (fz0 + z1) / 2
    for sgn in (1, -1):
        ya, yb = (p0, r1 + 1.0) if sgn > 0 else (-r1 - 1.0, -p0)
        # the rebate starts REBATE_BACK behind the plate's rear end, its inner corner rounded there (the rail's root, where
        # the FEA peaked), so the plate's square corner never meets the fillet
        s = s.cut(box(fx0 - PLATE['rebate_back'], fx1 + 0.3, ya, yb, zb, z1 + 1))
        s = _fillet_edge_near(s, (fx0 - PLATE['rebate_back'], sgn * p0, (z0 + z1) / 2), PLATE['rebate_fillet'], sel='|Z')
        for x in PLATE['foot_holes_x']:
            y0, y1 = (p0 - INSERT_M3_SIDE, p0 + 0.1) if sgn > 0 else (-p0 - 0.1, -p0 + INSERT_M3_SIDE)
            s = s.cut(cyl_y(FAST['M3']['insert_pilot'] / 2, y0, y1, x, zf))
    ct_dowels, ct_latch = ct_points(G)
    for (x, y) in ct_dowels:
        s = s.cut(cyl_z(2.0, zb, z1 + 1, x, y))
    s = s.cut(through_z(*ct_latch, FAST['M4']['clear'], zb, z1 + 1))
    s = s.cut(cyl_z(THUMB['oring_seat'][0] / 2, z1 - THUMB['oring_seat'][1], z1 + 1, *ct_latch))      # the captive O-ring
    # the latch is inside the plate's foot zone, where the rail is 10 mm deep: a pocket from below keeps its collar's seat
    # 7 mm under the rail's top as in v0 (the M4 x 12 keeps 5 mm in the cartridge's insert), open to the rail's inner side
    lx, ly = ct_latch
    zs = z0 - RAIL_DEEP['dz']
    s = s.cut(cyl_z(THUMB['collar'][0] / 2 + 1.0, zb, zs, lx, ly)).cut(box(lx - THUMB['collar'][0] / 2 - 1.0, lx + THUMB['collar'][0] / 2 + 1.0,
                                                                             ly, -r0 + 1.0, zb, zs))
    for x in (LASER_X[0] + 4, LASER_X[1] - 4):
        s = s.cut(through_z(x, LASER_Y, FAST['M3']['clear'], z0 - 1, z1 + 1))
    # lightening windows in the rails, kept 4 mm clear of every CT hole and off the plates' feet
    holes = ct_dowels + [ct_latch]
    for sgn in (1, -1):
        yc = sgn * (r0 + r1) / 2
        for xa, half in RAIL_WINDOWS:
            win = (xa - half, xa + half, yc - 3, yc + 3)
            if any(win[0] - 6 < hx < win[1] + 6 and abs(hy - yc) < 9 for hx, hy in holes) or (win[0] < fx1 + 4 and win[1] > fx0 - 4):
                continue
            s = s.cut(box(win[0], win[1], win[2], win[3], zb, z1 + 1))
    return s


RAIL_WINDOWS = [(-38.0, 8.0), (2.0, 8.0), (82.0, 4.0)]             # (centre x, half length); C frame
RAIL_DEEP = {'x1': 80.0, 'dz': 2.0}                                 # deeper rails behind the front dowel
INSERT_M3_SIDE = 6.5                                                # an M3 x 5.7 insert's pilot, put in from a side face


def _fillet_edge_near(s, point, r, sel='|Y'):
    """Fillet the one edge parallel to `sel` nearest to `point` (a re-entrant corner of a flat part)."""
    return s.edges(sel).edges(cq.selectors.NearestToPointSelector(point)).fillet(r)


def _csk_y(x, z, y_face, direction, d_head=PLATE['csk_d'], d_hole=FAST['M3']['clear']):
    """A 90 deg countersink for an ISO 10642 flat head, from the face at y_face into the part along `direction` (+1/-1)."""
    h = (d_head - d_hole) / 2
    return cq.Workplane('XY').add(cq.Solid.makeCone(d_head / 2, d_hole / 2, h, cq.Vector(x, y_face - direction * 0.01, z),
                                                    cq.Vector(0, direction, 0)))


def cradle_plate(G, side):
    """One of the cradle's two cheek plates (D48), laser-cut by SendCutSend from 0.125 in (3.175 mm) 6061-T6 (DXF and
    STEP in exports/turret/): an inverted T in the x-z plane, a 90 x 10 foot in its rail's rebate (4 x Ø3.4 for M3 x 8
    button heads into the rail's inserts; it reaches 10 mm short of the rear CT dowel, so the printed rail is never a
    long cantilever) and a 44 mm cheek up to the Ø44 round at the tilt axis (5 mm radii where its edges meet the foot). side +1, the +y plate (cradle_plate_l): the tilt servo's horn, Ø6.5 at the
    axis over its centre screw and 4 x Ø3.4 on Ø14, countersunk 90 deg on the plate's inner face for M3 x 14 flat heads
    through the plate and the printed horn_boss into the horn. side -1 (cradle_plate_r): the pivot, Ø4.2 tapped M5 for
    the ISO 7379 shoulder screw, and 2 x Ø3.4 countersunk on its inner face for the stop lug's M3 x 6 flat heads."""
    xt, zt = G.tilt_x, G.tilt_c
    fx0, fx1 = PLATE['foot_x']
    fz0, fz1 = G.foot_z
    hw = PLATE['half_w']
    p0, p1 = G.plate_y
    ya, yb = (p0, p1) if side > 0 else (-p1, -p0)
    s = box(fx0, fx1, ya, yb, fz0, fz1)
    s = s.union(box(xt - hw, xt + hw, ya, yb, fz1 - 0.01, zt)).union(cyl_y(hw, ya, yb, xt, zt))
    for xe in (xt - hw, xt + hw):                       # where the cheek's edges meet the foot's top
        s = _fillet_edge_near(s, (xe, (ya + yb) / 2, fz1), PLATE['fillet'])
    zf = (fz0 + fz1) / 2
    for x in PLATE['foot_holes_x']:
        s = s.cut(cyl_y(FAST['M3']['clear'] / 2, ya - 1, yb + 1, x, zf))
    inner, inward = (p0, 1) if side > 0 else (-p0, -1)           # the inner face (on the rail) and the way into the plate
    if side > 0:
        s = s.cut(cyl_y(3.25, ya - 1, yb + 1, xt, zt))                                            # over the horn's centre screw
        for k in range(4):
            hx, hz = polar(SERVO['horn_pcd'] / 2, math.pi / 4 + k * math.pi / 2)
            s = s.cut(cyl_y(FAST['M3']['clear'] / 2, ya - 1, yb + 1, xt + hx, zt + hz)).cut(_csk_y(xt + hx, zt + hz, inner, inward))
    else:
        s = s.cut(cyl_y(FAST['M5']['tap'] / 2, ya - 1, yb + 1, xt, zt))                          # tapped M5 by SendCutSend
        for (hx, hz) in lug_screws(G):
            s = s.cut(cyl_y(FAST['M3']['clear'] / 2, ya - 1, yb + 1, hx, hz)).cut(_csk_y(hx, hz, inner, inward))
    return s


def lug_screws(G):
    """The stop lug's two M3 screws (x, z), C frame: on r = LUG['screw_r'] about the tilt axis, +-LUG['screw_deg'] off
    straight down."""
    return [(G.tilt_x + LUG['screw_r'] * math.cos(math.radians(-90 + sg * LUG['screw_deg'])),
             G.tilt_c + LUG['screw_r'] * math.sin(math.radians(-90 + sg * LUG['screw_deg']))) for sg in (-1, 1)]


def stop_lug(G):
    """The hard stop (D48), laser-cut by SendCutSend from 0.100 in (2.54 mm) 6061-T6 with two holes tapped M3: on the
    -y plate's outer face, 1.5 mm from the yoke's arm. Its stop band (r 22.5..32, +-STOP_HALF_DEG about straight down at
    tilt 0) meets the yoke's sectors (r 24..32) at tilt 0 and -25 deg, 1.5 mm deep, loaded in its own plane: a push on
    the muzzle puts 262 N on it (50 N x 147 / 28 mm). Its pad (r 11..22.5, +-32 deg) lies inside the sectors' annulus,
    held by 2 x M3 x 6 flat heads from the plate's inner face (and a drop of CA gel). The barrel cannot be pushed above
    level while it is there: it is the kid-safety stop."""
    xt, zt = G.tilt_x, G.tilt_c
    p1 = G.plate_y[1]
    t = SHEET['al6061_100']['thickness_mm']
    y0, y1 = -p1 - t, -p1
    a, b = STOP_HALF_DEG, LUG['pad_half_deg']
    (ri, rm), ro = LUG['pad_r'], LUG['band_r'][1]
    P = lambda r, d: (xt + r * math.cos(math.radians(d)), zt + r * math.sin(math.radians(d)))
    w = (cq.Workplane('XZ', origin=(0, y1, 0)).moveTo(*P(ri, -90 - b)).threePointArc(P(ri, -90), P(ri, -90 + b))
         .lineTo(*P(rm, -90 + b)).threePointArc(P(rm, -90 + (a + b) / 2), P(rm, -90 + a))
         .lineTo(*P(ro, -90 + a)).threePointArc(P(ro, -90), P(ro, -90 - a))
         .lineTo(*P(rm, -90 - a)).threePointArc(P(rm, -90 - (a + b) / 2), P(rm, -90 - b)).close())
    s = w.extrude(y1 - y0)
    for sg in (-1, 1):                                                    # the band's root into the pad
        px, pz = P(rm, -90 + sg * a)
        s = _fillet_edge_near(s, (px, (y0 + y1) / 2, pz), LUG['fillet'])
    for (hx, hz) in lug_screws(G):
        s = s.cut(cyl_y(FAST['M3']['tap'] / 2, y0 - 1, y1 + 1, hx, hz))
    return s


def horn_boss(G):
    """Printed PA6-CF (100 % solid, on an end face): a Ø20 x 9 boss between the +y cheek plate's outer face and the tilt
    servo's horn, with the horn's 4 x Ø3.4 on Ø14 and a Ø6.5 hole over its centre screw. The 4 x M3 x 14 flat heads go
    through the plate and the boss into the horn: 1.8 mm of thread in the horn's 2.5 mm flange (the tip short of the
    servo's face), the heads flush with the plate's inner face, 4.3 mm from the cartridge."""
    xt, zt = G.tilt_x, G.tilt_c
    y0, y1 = G.plate_y[1], G.arm_y[1] - SERVO['horn_t']
    s = cyl_y(HORN_BOSS['d'] / 2, y0, y1, xt, zt).cut(cyl_y(3.25, y0 - 1, y1 + 1, xt, zt))
    for k in range(4):
        hx, hz = polar(SERVO['horn_pcd'] / 2, math.pi / 4 + k * math.pi / 2)
        s = s.cut(cyl_y(FAST['M3']['clear'] / 2, y0 - 1, y1 + 1, xt + hx, zt + hz))
    return s


def pivot_spacer(G):
    """Printed PA6-CF (100 % solid, on its boss face): between the -y cheek plate's outer face and the MR126's inner
    race, a Ø18 boss and a Ø6.8 x 1 land that bears only on the inner race (inside its Ø7.2; the shields 0.3 mm
    clear), bore Ø5.3. The ISO 7379 shoulder screw's step seats on the land, as v0's did on its insert, and its M5 thread
    goes on into the plate's tapped hole: snug, a drop of CA gel on the thread (the shank carries the load; the thread retains it).
    It carries the cradle's -y loads (a side fall) into the bearing."""
    xt, zt = G.tilt_x, G.tilt_c
    yp, yr = -G.plate_y[1], -G.arm_y[0]                    # the plate's outer face, the inner race's face
    yl = yr + PIVOT['land_h']
    s = cyl_y(PIVOT['boss_d'] / 2, yl, yp, xt, zt).union(cyl_y(PIVOT['land_d'] / 2, yr, yl + 0.01, xt, zt))
    return s.cut(cyl_y(PIVOT['bore'] / 2, yr - 1, yp + 1, xt, zt))
def ct_points(G):
    """The CT interface (cradle <-> cartridge), C frame: two Ø4 x 8 dowels and the M4 captive thumbscrew up through the
    cradle's rail into an insert in the cartridge's base, 6 mm inside the cartridge's sides."""
    yy = G.cage_y - 6.0
    return [(-20.0, yy), (75.0, -yy)], (20.0, -yy)


# the CT latch: a DIN 464 knurled thumbscrew M4 x 12 (McMaster 92581A250: head Ø16 x 3.5 on a Ø8 x 6 collar) up through
# the rail into the cartridge's M4 insert, kept in the rail by an O-ring on its thread in a counterbore on the rail's top
THUMB = {'head': (16.0, 3.5), 'collar': (8.0, 6.0), 'l': 12.0, 'oring_seat': (8.6, 2.0), 'mass_g': 4.0}   # O-ring: AS568-006, 9452K14
LASER_X = (106.0, 126.0)
LASER_Y = -32.0


def cartridge_body(G):
    """The ball cartridge, printed PA6-CF on its base (100 % solid, 2.5 mm walls): a base plate on the cradle rails
    (CT dowels, thumbscrew insert), the dial housing (its floor carries the feed servo: an STS3215 hanging under it, its
    output face 0.75 mm up in a pocket in the floor's underside (so its horn's top is level with the dial's underside)
    with a relief for its label band, the horn up through a Ø21 hole, 4 x M2 x 6 countersunk from above flush with the
    floor (3.75 mm into the servo); the servo's length runs to the rear and its bus plugs face down
    through the base plate's window; side windows in the housing below the floor), the chute that drops the ball out of
    the dial and turns it forward onto the path, the flywheel cage (two shells round the wheels and the hanging motors; a
    top plate the X2216s screw under, 4 x M3 x 6 each in four radial slots that take the motor's 16/19 cross in any
    quarter turn, a Ø10.5 hole over its shaft's rear end and clip, a slot outboard of each for its leads; four printed
    posts with M3 inserts that carry the cartridge board over the plate (the two ESCs lie on the plate under it); a hole over the hopper's front
    lug for its screw; a Ø37.5 opening in the bottom plate under each wheel, through which a motor goes in with its wheel
    already on), the ball channel and the barrel socket (M3 insert on top)."""
    br, w = G.br, G.wall
    hr = G.housing_r
    fz = G.floor_z
    bz0 = G.base_z0
    fz0 = fz - G.floor_t                                                                    # the floor's underside
    # base plate (windowed) under everything; the window takes the feed servo (its length runs to the rear)
    s = box(-hr - 2.0, G.cage_x1, -G.cage_y, G.cage_y, bz0, bz0 + 3)
    s = s.cut(box(-37, 26, -34, 34, bz0 - 1, bz0 + 4))
    # dial housing: wall from the base to the top, floor, flange lugs for the hopper
    s = s.union(ring_z(hr, G.dial_wall_r, bz0 + 3, G.housing_top))
    s = s.union(cyl_z(G.dial_wall_r, fz0, fz))
    for a in HOPPER_LUGS:
        lug = cyl_z(5.0, G.housing_top - 6, G.housing_top, *polar(hr + 3.5, math.radians(a)))
        s = s.union(lug.union(box(hr - 1.0, hr + 3.5, -5.0, 5.0, G.housing_top - 6, G.housing_top).rotate((0, 0, 0), (0, 0, 1), a)))
    for sy in (1, -1):
        s = s.cut(box(-20, 20, sy * 20, sy * 60, -5, fz0 - 3))                              # side windows
    # chute and channel walls
    chute = cq.Workplane('XY').add(cq.Solid.makeTorus(G.chute_r, br + w, cq.Vector(G.chute_cx, 0, G.chute_r), cq.Vector(0, 1, 0)))
    quad = box(G.exit_x - br - w - 1, G.chute_cx, -br - w - 1, br + w + 1, -br - w - 1, fz - G.floor_t + 0.5)
    s = s.union(chute.intersect(quad))
    s = s.union(cyl_x(br + w, G.chute_cx, G.socket_x0))
    s = s.union(box(G.exit_x - 4, G.chute_cx, -br - w + 1.5, br + w - 1.5, bz0, 0))        # web under the chute
    # flywheel cage: two shells, plates, socket
    for sy in (1, -1):
        s = s.union(ring_z(G.cav_r + w, G.cav_r, bz0, G.plate_z1, G.wheel_x, sy * G.wheel_y))
    plate = cyl_z(G.cav_r + w, 0, 1, G.wheel_x, G.wheel_y).union(cyl_z(G.cav_r + w, 0, 1, G.wheel_x, -G.wheel_y)) \
        .union(box(G.cage_x0, G.cage_x1, -G.wheel_y, G.wheel_y, 0, 1))
    hop = G.dial_wall_r + HOPPER_WALL + 1.0                                                 # the hopper's outside + 1 mm
    s = s.union(_slab(plate, G.plate_z0, G.plate_z1).cut(cyl_z(hop, G.plate_z0 - 1, G.plate_z1 + 1)))   # not over the hopper
    s = s.union(_slab(plate, bz0, bz0 + 3))
    s = s.union(box(G.cage_x1 - w, G.cage_x1 + 1.5, -br - w - 3, br + w + 3, bz0, br + w + 3))   # front wall
    s = s.union(cyl_x(br + 6.0, G.socket_x0 - 1.5, G.socket_x1))                            # barrel socket
    s = s.union(box(G.socket_x0 + 3, G.socket_x0 + 11, -5, 5, 0, br + 8.5))                 # socket screw boss
    cb = CART_BOARD
    for (x, y) in cb['bosses']:                                                             # posts for the cartridge board
        s = s.union(cyl_z(3.5, G.plate_z1 - 0.01, G.plate_z1 + cb['boss_h'] + cb['standoff'], x, y))
    # cuts: cavities, ball path, mounts
    for sy in (1, -1):
        xw, yw = G.wheel_x, sy * G.wheel_y
        s = s.cut(cyl_z(G.cav_cut, -8.0, G.bell_z0 - 0.5, xw, yw))                         # the tyre and the adapter
        s = s.cut(cyl_z(MOTOR['d'] / 2 + 1.5, G.bell_z0 - 0.6, G.plate_z0, xw, yw))        # the motor (its bell turns)
        s = s.cut(cyl_z(18.5, G.plate_z0 - MOTOR['base_h'] - 1.0, G.plate_z0, xw, yw))     # room for the leads at its base
        s = s.cut(cyl_z(5.25, G.plate_z0 - 1, G.plate_z1 + 1, xw, yw))                    # the shaft's rear end and clip
        for a in (45.0, 135.0, 225.0, 315.0):                                               # 4 x M3: radial slots r 8..9.5
            for r in MOTOR['holes_r']:
                s = s.cut(through_z(xw + r * math.cos(math.radians(a)), yw + r * math.sin(math.radians(a)), FAST['M3']['clear'],
                                    G.plate_z0 - 1, G.plate_z1 + 1))
            slot = box(MOTOR['holes_r'][0], MOTOR['holes_r'][1], -FAST['M3']['clear'] / 2, FAST['M3']['clear'] / 2, G.plate_z0 - 1, G.plate_z1 + 1)
            s = s.cut(slot.rotate((0, 0, 0), (0, 0, 1), a).translate((xw, yw, 0)))
        s = s.cut(box(xw - 4, xw + 4, yw + sy * 14.0, yw + sy * 18.0, G.plate_z0 - 1, G.plate_z1 + 1))   # its leads, outboard
        s = s.cut(cyl_z(G.wheel_d / 2 + 0.75, bz0 - 1, -7.9, xw, yw))                      # a motor + wheel go in here
    s = s.cut(cyl_z(3.6, G.plate_z0 - 1, G.plate_z1 + 1, hr + 3.5, 0.0))                   # over the hopper's front lug: its screw
    for (x, y) in cb['bosses']:
        s = s.cut(insert_hole(x, y, G.plate_z1 + cb['boss_h'] + cb['standoff'], 'M3', 6.0))
    s = s.cut(ball_path(G))
    s = s.cut(cyl_x(G.barrel_od / 2 + 0.1, G.socket_x0, G.socket_x1 + 1))
    s = s.cut(insert_hole(G.socket_x0 + 7, 0, br + 8.5, 'M3', 8.0 - 0.5))
    # the feed servo under the floor: the horn's hole, the label band's relief, 4 x M2 countersunk from above
    s = s.cut(cyl_z(10.5, fz0 - 1, fz + 1))
    L_, W_, sft = SERVO['L'], SERVO['W'], SERVO['shaft_from_end']
    s = s.cut(box(-(L_ - sft) - 0.3, sft + 0.3, -W_ / 2 - 0.3, W_ / 2 + 0.3, fz0 - 1, G.feed_face))   # its face, 0.75 up into the floor
    for (x0, x1, y0, y1, z0, z1) in feed_servo_cuts(G):
        s = s.cut(box(x0, x1, y0, y1, z0, z1))
    for (hx, hy) in feed_servo_holes():
        s = s.cut(through_z(hx, hy, 2.4, fz0 - 1, fz + 1))
        s = s.cut(cq.Workplane('XY').circle(1.2).workplane(offset=1.1).circle(2.3).loft().translate((hx, hy, fz - 1.09)))
    ct_dowels, ct_latch = ct_points(G)
    for (x, y) in ct_dowels:
        s = s.cut(cyl_z(2.0, bz0 - 1, bz0 + 2.5, x, y))
    s = s.union(cyl_z(5.0, bz0, bz0 + 9, *ct_latch))
    s = s.cut(cyl_z(FAST['M4']['insert_pilot'] / 2, bz0 - 1, bz0 + 8.0, *ct_latch))       # insert from below
    for a in HOPPER_LUGS:
        s = s.cut(insert_hole(*polar(hr + 3.5, math.radians(a)), G.housing_top, 'M3', 6.0))
    return s


HOPPER_LUGS = (0.0, 135.0, 225.0)
HOPPER_WALL = 1.6


def feed_servo_holes():
    """The feed servo's four M2 holes in its output face (SERVO: +-10.25 across, 8.30 and 29.00 from the axis towards
    its far end), in the C frame: the servo's axis on the dial axis, its length running to the rear (-x)."""
    return [(-d, sgn * SERVO['holes_x']) for d in SERVO['holes_out'] for sgn in (1, -1)]


def feed_servo_cuts(G):
    """Boxes (x0, x1, y0, y1, z0, z1) cut from the floor's underside for the feed servo's label band (1.1 mm, 13 wide,
    from 12 mm off the axis to 1 mm short of the far end: est), with 0.3 mm to spare."""
    L, s = SERVO['L'], SERVO['shaft_from_end']
    return [(-(L - s - 1.0) - 0.3, -12.0 + 0.3, -6.8, 6.8, G.feed_face - 0.01, G.feed_face + SERVO['band'] + 0.3)]


def _slab(plate, z0, z1):
    """The outline of `plate` (built 0..1 thick, z from 0) as a slab from z0 to z1."""
    face = plate.faces('<Z').val()
    return cq.Workplane('XY').add(cq.Solid.extrudeLinear(face, cq.Vector(0, 0, z1 - z0))).translate((0, 0, z0 - face.Center().z))


def ball_path(G):
    """The ball's free space: from a dial pocket down through the floor, round the chute and along the path to the nip
    at ball + 1.5, then from the nip to the barrel socket at ball + 2.0 (the floor steps down 0.25 mm at the nip, in
    the direction of travel)."""
    br = G.br
    up = cyl_z(br, G.chute_r, G.housing_top, G.exit_x, 0)
    t = cq.Workplane('XY').add(cq.Solid.makeTorus(G.chute_r, br, cq.Vector(G.chute_cx, 0, G.chute_r), cq.Vector(0, 1, 0)))
    quad = box(G.exit_x - br - 1, G.chute_cx, -br - 1, br + 1, -br - 1, G.chute_r)
    return up.union(t.intersect(quad)).union(cyl_x(br, G.chute_cx, G.wheel_x + 0.01)).union(cyl_x(G.br_out, G.wheel_x, G.socket_x0 + 0.5))


def flywheel(G):
    """Flywheel hub, printed PA6-CF (100 % solid) on its top face: a Ø30 x 12 rim for the TPU tyre and a 5.5 mm web whose
    top face sits flat on the X2216's prop-adapter flange (Ø17) under the bell, its bore on the adapter's Ø5 pilot
    (printed Ø4.9 and reamed to 5.00: a close slip fit that centres it), clamped by the adapter's Ø14.8 washer and an M5
    nylon-insert nut in the recess under the web, as a propeller is; the stud's thread starts below the web, so the bore
    rides only the pilot. A 0.5 mm chamfer at the top clears the stud's root. Runout is measured on the motor before the
    tyre goes on (bench test 1.5). The tyre's diameter is the launch speed's hardware ceiling (study 8.3,
    sim/turret_launch.py)."""
    x, y = G.wheel_x, G.wheel_y
    top = G.hub_top                                                     # on the adapter's flange
    web0 = top - MOTOR['pilot'][1]                                      # the web's underside: where the pilot ends
    rr = G.wheel_d / 2 - G.tyre_t                                       # the rim, under the tyre
    s = ring_z(rr, rr - 3.0, -G.tyre_w / 2, G.tyre_w / 2, x, y)
    s = s.union(cyl_z(rr - 2.9, web0, top, x, y))
    s = s.cut(cyl_z(2.45, web0 - 1, top + 1, x, y))
    s = s.cut(cq.Workplane('XY').circle(2.45).workplane(offset=0.51).circle(2.96).loft().translate((x, y, top - 0.5)))
    return s


# the tyre's bore is printed 4 % under the hub's rim and the tyre is BONDED to it (D68: a cyanoacrylate for elastomers,
# Loctite 406 class, on the rim before the tyre is stretched on). At D68's ~15,700 rpm a free TPU ring would grow ~8 %
# in its bore on a 10 MPa TPU (docs/turret-physics.md section 4), twice the stretch, so a stretch fit alone would
# float the tyre (2.4 mm of growth, the crush to 61 %, the fastest ball 113 fps); bonded, the rim holds its bore and the
# face grows 0.05 mm. The set: Ø38 at 40 % crush on this cage (D68, sim/turret_launch.py); every accepted ball at 100 %
# throttle on the trimmed rail stays under 105 fps (sim/turret_launch3d.py ceiling_map), the Hasbro ball leaves at ~97.
TYRE_STRETCH = 0.04
TYRE_SET = (38.0,)


def flywheel_tyre(G):
    """TPU 95A tyre as mounted, Ø38 x 12 (TYRE_SET), 4 mm thick on the hub's Ø30 rim and bonded to it (the assembly; the
    printed blank is flywheel_tyre_print). It crushes the 22.7 mm ball 40 % and keeps 2.5 mm from the cavity's wall."""
    rim = G.wheel_d / 2 - G.tyre_t
    return ring_z(TYRE_SET[0] / 2, rim, -G.tyre_w / 2, G.tyre_w / 2, G.wheel_x, G.wheel_y)


def flywheel_tyre_print(G, d=None):
    """The tyre as printed (TPU 95A, flat on the bed): its bore TYRE_STRETCH under the Ø30 rim, its outside sized so
    that stretched on the rim it is Ø d (TPU is nearly incompressible: the cross-section's area is kept)."""
    d = d or G.wheel_d
    rim = G.wheel_d / 2 - G.tyre_t
    ri = rim * (1 - TYRE_STRETCH)
    ro = math.sqrt((d / 2) ** 2 - rim ** 2 + ri ** 2)
    return ring_z(ro, ri, -G.tyre_w / 2, G.tyre_w / 2, G.wheel_x, G.wheel_y)


PRINT_AS = {'flywheel_tyre': lambda G: flywheel_tyre_print(G, TYRE_SET[0])}   # parts printed in a shape other than the one they have mounted


def dial(G):
    """The feed dial, printed PETG: a shelled Ø50 hub (2 mm rim, 2 mm top, four ribs to a Ø22 boss), 8 spokes 4 mm
    thick that push one ball per pocket round the housing to the exit hole, and a 30 deg cone on top with four fins
    that stir the hopper's pile at every step.
    It sits flat on the feed servo's horn (Ø19.95, its top 0.75 above the floor: the dial's running clearance), a Ø7
    pocket over the horn's centre screw, and 4 x M3 x 8 go down through the boss into the horn's tapped holes (Ø14),
    their heads 5.5 above the horn, put in from the top through Ø6.5 holes in the cone with the hopper off. Each shot steps it 45 deg and stops it with a pocket centred over the exit hole (the servo's zero is
    set so): the ball drops while it stands still, and the hopper's baffle covers that pocket, so it cannot refill.
    Parked there, powered or not, the path is blocked: the pockets either side are on the floor behind a spoke."""
    z0, h = G.dial_z0, G.dial_h
    s = ring_z(G.dial_hub_r, G.dial_hub_r - 2.0, z0, z0 + h).union(cyl_z(G.dial_hub_r, z0 + h - 2, z0 + h))
    s = s.union(cyl_z(11.0, z0, z0 + h))
    for k in range(4):
        s = s.union(box(5.0, G.dial_hub_r - 1.0, -1.25, 1.25, z0, z0 + h).rotate((0, 0, 0), (0, 0, 1), 45 + 90 * k))
    # the hub's cone, 30 deg: the pile's middle rolls out to the pocket ring; four fins on it stir the pile at every
    # step (physics finding 1: with a 100 ms step only 3 of 7 pockets filled under a settled pile). The fins end at
    # r 18, inside the baffle (r 19 up), and slope down outwards to 3.5 mm over the hub's top
    s = s.union(cq.Workplane('XY').circle(G.dial_hub_r).workplane(offset=DIAL_CONE['h']).circle(DIAL_CONE['r_top']).loft()
                .translate((0, 0, z0 + h)))
    for k in range(DIAL_CONE['fins']):
        fin = cq.Workplane('XZ').polyline([(DIAL_CONE['r_top'] - 1.0, z0 + h), (18.0, z0 + h), (18.0, z0 + h + 3.5),
                                           (DIAL_CONE['r_top'] - 1.0, z0 + h + DIAL_CONE['fin_top'])]).close() \
            .extrude(DIAL_CONE['fin_t'] / 2, both=True)
        s = s.union(fin.rotate((0, 0, 0), (0, 0, 1), 22.5 + 90 * k))
    for k in range(G.n_pockets):
        a = (k + 0.5) * 360 / G.n_pockets
        sp = box(G.dial_hub_r - 1, G.dial_wall_r - 0.75, -G.spoke_w / 2, G.spoke_w / 2, z0, z0 + h - 2)
        s = s.union(sp.rotate((0, 0, 0), (0, 0, 1), a))
    horn = G.feed_face + SERVO['horn_t']                                   # the horn's top face: the dial's underside
    s = s.cut(cyl_z(3.5, horn - 1, horn + 4.0))                            # over the horn's centre screw
    top = z0 + h + max(DIAL_CONE['h'], DIAL_CONE['fin_top']) + 1
    seat = horn + 5.5                                                      # M3 x 8: 2.5 mm into the horn's thread
    for k in range(4):                                                     # 45 deg off the fins' lines (clear of them)
        hx, hy = polar(SERVO['horn_pcd'] / 2, math.radians(67.5 + 90 * k))
        s = s.cut(cyl_z(FAST['M3']['clear'] / 2, horn - 1, seat + 0.01, hx, hy)).cut(cyl_z(3.25, seat, top, hx, hy))
    return s


BAFFLE = {'half_deg': 24.0, 'r0': 19.0, 't': 3.0, 'land': 0.5, 'chamfer': 2.5}
DIAL_CONE = {'h': 11.0, 'r_top': 6.0, 'fins': 4, 'fin_t': 2.5, 'fin_top': 24.0}


def baffle(G):
    """The exit baffle: a fixed sector over the dial from Ø38 to the housing wall, +-24 deg about the exit (it covers the
    pocket over the exit hole, +-20.2 deg at the wall, and the spokes either side), its underside at the housing top,
    2.3 mm over a seated ball and 4 mm over the hub. Both edges have a 0.5 mm land and a 45 deg chamfer, so a ball
    resting on a full pocket is lifted off as the pocket goes under, not pinched (the dial reverses to clear jams)."""
    z0 = G.housing_top
    B = BAFFLE
    s = sector_z(B['r0'], G.dial_wall_r + 0.5, -B['half_deg'], B['half_deg'], z0, z0 + B['t'], n=24)
    L = G.dial_wall_r + 2.0
    tri = [(-0.01, z0 + B['land']), (-0.01, z0 + B['t'] + 0.01), (B['chamfer'], z0 + B['t'] + 0.01)]
    for a, side in ((-B['half_deg'], 1.0), (B['half_deg'], -1.0)):
        w = cq.Workplane('YZ').polyline([(side * y, z) for y, z in tri]).close().extrude(L).translate((B['r0'] - 1.0, 0, 0))
        # the chamfer's tangential width grows a little with the radius at a fixed angle: cut it along the edge line
        s = s.cut(w.rotate((0, 0, 0), (0, 0, 1), a))
    return s


def hopper(G):
    """The hopper, printed PETG (translucent, so the balls show): a Ø102 tube from the dial housing to z = 100 in the
    cartridge frame (30 balls with the dial's pockets: sim/turret_feed.py fills it in physics), the exit baffle in its bottom (see baffle()), three lugs
    that screw to the housing (M3), and two Ø5 holes for the hopper-full IR beam near the top. Printed standing on its
    bottom rim and the baffle."""
    r_in, r_out = G.dial_wall_r, G.dial_wall_r + HOPPER_WALL
    z0, z1 = G.housing_top, G.hopper_top
    s = ring_z(r_out, r_in, z0, z1).union(baffle(G))
    for a in HOPPER_LUGS:
        x, y = polar(G.housing_r + 3.5, math.radians(a))
        lug = cyl_z(5.0, z0, z0 + 3, x, y).union(box(r_out - 1.0, G.housing_r + 3.5, -5.0, 5.0, z0, z0 + 3).rotate((0, 0, 0), (0, 0, 1), a))
        s = s.union(lug)
        s = s.cut(through_z(x, y, FAST['M3']['clear'], z0 - 1, z0 + 4))
    s = s.cut(cyl_y(2.5, -r_out - 1, r_out + 1, 0, z1 - 6))
    return s


def hopper_lid(G):
    """Lid, printed PETG: a 2 mm disc with a spigot into the hopper, a Ø32 fill port where the dock's spout pushes the
    sprung flap open, and two hinge lugs for the flap (Ø2 steel pin, torsion spring)."""
    z1 = G.hopper_top
    r = G.dial_wall_r + 2.0
    s = cyl_z(r, z1, z1 + 2).union(ring_z(G.dial_wall_r - 0.1, G.dial_wall_r - 2.1, z1 - 4, z1 + 0.01))
    s = s.cut(sector_z(12.0, G.dial_wall_r - 3, 30, 150, z1 - 1, z1 + 1.0)).cut(sector_z(12.0, G.dial_wall_r - 3, 210, 330, z1 - 1, z1 + 1.0))
    s = s.cut(cyl_z(16.0, z1 - 5, z1 + 4, FILL_PORT[0], 0))
    for y in (-12.0, 9.0):
        s = s.union(box(FILL_PORT[0] - 22, FILL_PORT[0] - 16, y, y + 3, z1 + 2 - 0.01, z1 + 9))
    s = s.cut(cyl_y(1.05, -15, 15, FILL_PORT[0] - 19, z1 + 6))
    return s


FILL_PORT = (-20.0, 0.0)


def hopper_flap(G):
    """The fill-port flap, printed PETG: a Ø36 x 2 disc and a hinge knuckle between the lid's lugs."""
    z = G.hopper_top + 3
    s = cyl_z(18.0, z, z + 2, FILL_PORT[0], 0)
    s = s.union(box(FILL_PORT[0] - 21, FILL_PORT[0] - 16, -8.6, 8.6, z, z + 2)).union(cyl_y(3.0, -8.6, 8.6, FILL_PORT[0] - 19, z + 3))
    s = s.cut(cyl_y(1.05, -10, 10, FILL_PORT[0] - 19, z + 3))
    return s


GATES = {'x': (22.0, 82.0), 'hole_d': 3.2, 'slit': (1.0, 2.0)}


def barrel(G):
    """Barrel, printed PETG standing up: Ø30 x 100 with a bore of ball + 2.0 mm (docs/turret-physics.md finding 14), 14 mm
    in the socket (a nylon-tip M3 set screw). Two chronograph gates 60 mm apart, 22 and 82 mm from the shoulder (8 mm
    past the socket, clear of the orange tip; physics section 10): on each, a Ø3.2 pocket from either side for the IR
    emitter (TSAL4400) and the receiver (TEFT4300), stopping 1 mm short of the bore, and a 1 x 2 mm slit through to the
    bore, so the beam the ball cuts is 1 mm wide. The last 15 mm printed in blaze orange (15 U.S.C. 5001)."""
    x0, x1 = G.barrel_x0, G.barrel_x1
    s = cyl_x(G.barrel_od / 2, x0, x1)
    sw, sh = GATES['slit']
    for dx in GATES['x']:
        xg = x0 + dx
        s = s.union(cyl_y(4.5, -G.barrel_od / 2 - 2.5, G.barrel_od / 2 + 2.5, xg, 0))
        for sy in (1, -1):
            y0, y1 = sorted((sy * (G.br_out + 1.0), sy * 30.0))
            s = s.cut(cyl_y(GATES['hole_d'] / 2, y0, y1, xg, 0))
        s = s.cut(box(xg - sw / 2, xg + sw / 2, -G.br_out - 1.1, G.br_out + 1.1, -sh / 2, sh / 2))
    s = s.cut(cyl_x(G.br_out, x0 - 1, x1 + 1))
    return s


def laser_mount(G):
    """Laser holder, printed PETG: a ring round the Ø7 laser (Ø11 bore with an O-ring at the back) and three M3
    boresight screws at 120 deg (tapped), on a foot screwed to the cradle's tab (2 x M3). It stays on the cradle when
    a cartridge is swapped, so the boresight holds."""
    x0, x1 = LASER_X
    y = LASER_Y
    s = cyl_x(9.0, x0, x1, y, 0).union(box(x0, x1, y - 9, y + 9, G.rail_z[1], -4))
    s = s.cut(cyl_x(5.5, x0 - 1, x1 + 1, y, 0))
    for k in range(3):
        s = s.cut(_radial_hole(G, (x0 + x1) / 2, y, math.radians(90 + 120 * k)))
    for x in (x0 + 4, x1 - 4):
        s = s.cut(cyl_z(1.25, G.rail_z[1] - 1, G.rail_z[1] + 6, x, y))
    return s


def _radial_hole(G, x, y, a):
    d = cq.Workplane('XY').circle(1.25).extrude(12).translate((0, 0, 6))
    return d.rotate((0, 0, 0), (1, 0, 0), math.degrees(a) - 90).translate((x, y, 0))


# ------------------------------------------------------------------------------------------------ the head ring (proposal)

def head_ring_tm(L, G=None):
    """PROPOSED replacement for the ring of build.py head_saddle() so the TM interface of docs/cad-plan.md is met
    (today: Ø114/Ø60 x 6 at bodyTop + 20 with 4 x M4 inserts at (+-28.4, +-28.4), legs at r = 44 on the diagonals).
    Change: Ø132 OD (Ø60 ID kept, so the Ø45 TM hole is clear), 8 mm thick (bodyTop + 20 .. + 28), 4 x M5 inserts on
    80 x 80 (Ø6.4 x 8), 2 x Ø5 H7 holes for 5 x 12 dowel pins at (52, 0) and (0, -52), and the four legs moved to
    (+-40, +-40), Ø16, so the bolt loads go straight down; print it in PA6-CF (it now carries the turret's fall load).
    Robot frame."""
    top = L['bodyTop']
    z0, z1 = top + 20.0, top + 20.0 + SADDLE_T
    s = ring_z(66.0, 30.0, z0, z1)
    for (x, y) in TM_BOLTS:
        s = s.union(cyl_z(8.0, top, z0 + 0.01, x, y))
        s = s.cut(cyl_z(FAST['M5']['insert_pilot'] / 2, z1 - 8.0, z1 + 1, x, y))
    for (x, y) in TM_DOWELS:
        s = s.cut(cyl_z(2.5, z0 - 1, z1 + 1, x, y))
    return s


# ------------------------------------------------------------------------------------------------ bought parts

def bought_parts(G):
    """Envelopes of the bought parts with their real (or catalogue) sizes, each in its build frame. Returns
    {name: (shape, frame, mass_g, note)} with frame 'base' (T), 'pan' (T, turns with pan) or 'tilt' (C)."""
    out = {}
    sx, sy = G.servo_pan_xy
    out['pan_servo'] = (servo_envelope(G, (sx, sy, G.servo_z0 + SERVO['H']), '+z'), 'base', SERVO['mass_g'],
                        'Feetech STS3215 12 V; horn up, pinion on the horn')
    # the bearings in two pieces: the outer race with its shields stays with its seat, the inner race turns with the
    # shaft, so the clash sweep sees every rotating part that comes near a shield
    z0, z1 = G.brg_z, G.brg_z + BRG['B']
    rec = BRG['shield_recess']
    outer = ring_z(BRG['D'] / 2, BRG['D_land'] / 2, z0, z1).union(ring_z(BRG['D_land'] / 2 + 0.01, BRG['d_land'] / 2 + 0.4, z0 + rec, z1 - rec))
    out['pan_bearing'] = (outer, 'base', BRG['mass_g'] - 15.0, '6810-2Z (= 61810-2Z, 50 x 65 x 7): outer race and shields; McMaster 6656K229')
    out['pan_bearing_inner'] = (ring_z(BRG['d_land'] / 2 + 0.3, BRG['d'] / 2, z0, z1), 'pan', 15.0,
                                "the 6810-2Z's inner race (turns with the pan ring; bought with pan_bearing)")
    cz0, cz1 = circlip_z(G)
    r0, rb, ra = CIRCLIP['d2'] / 2, CIRCLIP['d2'] / 2 + CIRCLIP['b'], CIRCLIP['d2'] / 2 + CIRCLIP['a']
    clip = ring_z(rb, r0, cz0, cz1).union(sector_z(r0, ra, 75.0, 105.0, cz0, cz1))          # back b 5.1, lugs a 6.9
    out['circlip_50'] = (clip, 'pan', CIRCLIP['mass_g'], 'DIN 471-50 external ring under the pan_spacer; McMaster 98541A167')
    # parts ordered to our drawing (D40: an instant online price, not printed): the pan clamp from SendCutSend
    clamp = pan_clamp(G)
    out['pan_clamp'] = (clamp, 'base', round(clamp.val().Volume() / 1000 * SHEET['al6061']['density_g_cm3'], 1),
                        'pan clamp ring, SendCutSend 6061-T6 aluminium 0.125 in (exports/turret/pan_clamp.dxf)')
    # ... and the cradle's two cheek plates and its hard-stop lug (D48), in the same cart (tilting, C frame)
    for nm, side, what in (('cradle_plate_l', 1, 'the +y cheek plate: the tilt servo\'s horn through the horn boss (4 x M3 x 14 flat heads, '
                                                 'countersunk on its inner face)'),
                           ('cradle_plate_r', -1, 'the -y cheek plate: tapped M5 for the shoulder screw, the stop lug on its outer face')):
        sh = cradle_plate(G, side)
        out[nm] = (sh, 'tilt', round(sh.val().Volume() / 1000 * SHEET['al6061']['density_g_cm3'], 1),
                   f'{what}; SendCutSend 6061-T6 aluminium 0.125 in (exports/turret/{nm}.dxf), on 4 x M3 x 8 button heads into the rail')
    lug = stop_lug(G)
    out['stop_lug'] = (lug, 'tilt', round(lug.val().Volume() / 1000 * SHEET['al6061_100']['density_g_cm3'], 1),
                       'the tilt hard stop: SendCutSend 6061-T6 aluminium 0.100 in, 2 holes tapped M3 (exports/turret/stop_lug.dxf); '
                       '2 x M3 x 6 flat heads from the -y plate\'s inner face, and a drop of CA gel')
    # the pan joint: the slip ring (stator in the carrier; its rotor stub turns with pan), the tube coupling, the rotor
    # leads (beside the coupling, then up the axis through the yoke and along its bridge to the -y arm's bay)
    rg = ring_geom(G)
    M = rg['M']
    stator = cyl_z(M['flange'][0] / 2, rg['seat'], rg['body0']).union(cyl_z(11.0, rg['body0'] - 0.01, rg['top']))
    out['slip_ring'] = (stator, 'base', M['mass_g'], M['name'] + ' (envelope from the vendor sheets; flange holes to measure)')
    out['slip_ring_rotor'] = (cyl_z(M['stub'][0] / 2, rg['top'] - 0.01, rg['stub_top']), 'pan', 0.0, 'the ring\'s rotor stub (bought with the ring)')
    k0, k1 = rg['socket']
    stub_r = M['stub'][0] / 2
    od_on = math.sqrt(stub_r ** 2 + (TUBE['od'] / 2) ** 2 - (TUBE['id'] / 2) ** 2)           # stretched over the stub (same area)
    tube = ring_z(od_on, stub_r, rg['top'] + 0.3, rg['stub_top']).union(
        ring_z(TUBE['socket_d'] / 2, TUBE['id'] / 2, rg['stub_top'] - 0.01, k0 + 6.0))          # free, then squeezed in the socket
    out['ring_coupling'] = (tube, 'pan', 1.0, TUBE['note'] + ', coupling the rotor to the driver')
    rl, zl = LEADS['d'] / 2, LEADS['z_run']
    leads = cyl_z(rl, rg['top'] + 0.3, zl + rl, 0.0, -LEADS['r']).union(cyl_y(rl, -G.arm_y[1] - 3.0, -LEADS['r'], 0.0, zl))
    out['ring_leads_rotor'] = (leads, 'pan', 0.0, 'the ring\'s rotor leads, a Ø7.5 bundle (12 x 26 AWG + 2 x 17 AWG): beside the coupling, up '
                               'through the driver and the yoke\'s slot, along the bridge and through the -y arm\'s window to the bay')
    x0 = BB['x0'] - BB['standoff']
    out['base_board'] = (box(x0 - BB['board'][2] - BB['parts_h'] + 2.0, x0, -BB['board'][1] / 2, BB['board'][1] / 2, 6.0, 6.0 + BB['board'][0]), 'base', 30.0,
                         'base board (est): DT12 fuse, the 555 safety-pulse oscillator, the pan servo\'s 12 V regulator, the ring\'s stator connector')
    holes, ys = bay_boards(G)
    zc, (bw, bh, bt) = sum(TB['z']) / 2, TB['board']
    stack = None
    for k, (yb, (parts_h, gap)) in enumerate(zip(ys, TB['levels'])):
        lvl = box(-bw / 2, bw / 2, yb - bt - parts_h, yb, zc - bh / 2, zc + bh / 2)
        stack = lvl if stack is None else stack.union(lvl)
        if gap:
            for (x, z) in holes:                                                           # the M3 standoffs to the next
                stack = stack.union(cyl_y(2.75, yb - bt - gap + 0.01, yb - bt - 0.01, x, z))
    out['turret_board'] = (stack, 'pan', TB['mass_g'], 'turret boards (cad/turret_boards.py): level 0 the D24V150F12 12 V regulator (always on); level 1 the '
                           'Pololu 2815 switch (12 V to the flywheels and the feed), the 5 V regulator, 2 x 1000 uF, the opto and the one-shots; level 2 '
                           'the Feather M4 CAN, the trip latch, the ARM gate and the bus buffer')
    zc0 = G.brg_z + BRG['B']                                                                # the housing's top: the clamp's underside
    out['index_magnet'] = (cyl_z(MAGNET['d'] / 2, zc0, zc0 + MAGNET['h'], MAGNET['r'], 0.0), 'base', 0.8, MAGNET['note'] + '; on the housing\'s top, through the clamp ring (0.2 mm proud), glued')
    hx, hy, hz = HALL['size']
    out['hall_switch'] = (box(MAGNET['r'] - hx / 2, MAGNET['r'] + hx / 2, -hy / 2, hy / 2, G.turntable_z[0] + 0.1, G.turntable_z[0] + 0.1 + hz), 'pan', 0.3, HALL['note'])
    yb = G.dt_y
    f, b, fr, pl = DT['flange'], DT['body'], DT['front'], DT['plug']
    zc = DT_Z
    flip = lambda w: w.rotate((0, 0, 0), (0, 0, 1), 180)                  # built on +y, mounted on -y
    dt = box(-f[0] / 2, f[0] / 2, yb, yb + f[1], zc - f[2] / 2, zc + f[2] / 2)
    dt = dt.union(box(-b[0] / 2, b[0] / 2, yb - b[1], yb, zc - b[2] / 2, zc + b[2] / 2))
    dt = dt.union(box(-fr[0] / 2, fr[0] / 2, yb + f[1], yb + f[1] + fr[1], zc - fr[2] / 2, zc + fr[2] / 2))
    out['dt_receptacle'] = (flip(dt), 'base', DT['mass_g'], 'TE Deutsch DT04-12PA-L012 flange receptacle (TE drawing): the TM connector')
    plug = box(-pl[0] / 2, pl[0] / 2, yb + f[1], yb + f[1] + pl[1], zc - pl[2] / 2, zc + pl[2] / 2)
    plug = plug.union(box(-pl[0] / 2, pl[0] / 2, yb + f[1] + pl[1] - 22.0, yb + f[1] + pl[1], zc - pl[2] / 2 - 35.0, zc))   # the 90 deg backshell, down
    out['dt_plug'] = (flip(plug), 'base', 0.0,
                      'DT06-12SA plug on the robot harness (robot side; use a 90 deg boot so the harness turns down)')
    a0, a1 = G.arm_y
    out['tilt_servo'] = (servo_envelope(G, (0, a1, G.tilt_t), '-y'), 'pan', SERVO['mass_g'], 'Feetech STS3215 12 V on the +y arm')
    B, rec = MR126['B'], MR126['shield_recess']
    on_y = lambda w, zc: w.rotate((0, 0, 0), (1, 0, 0), 90).translate((0, -a0, zc))      # ring_z from z 0..B -> y -a0..-a0-B
    t_outer = ring_z(MR126['D'] / 2, MR126['D_land'] / 2, 0, B).union(ring_z(MR126['D_land'] / 2 + 0.01, MR126['d_land'] / 2 + 0.1, rec, B - rec))
    out['tilt_bearing'] = (on_y(t_outer, G.tilt_t), 'pan', MR126['mass_g'] * 0.75, '126-2Z (MR126 size, 6 x 12 x 4): outer race and shields; McMaster 7804K112')
    out['tilt_bearing_inner'] = (on_y(ring_z(MR126['d_land'] / 2, MR126['d'] / 2, 0, B), G.tilt_c).translate((G.tilt_x, 0, 0)), 'tilt', MR126['mass_g'] * 0.25,
                                 "the 126-2Z's inner race (turns with the cradle; bought with tilt_bearing)")
    # tilting (C frame)
    S = SHOULDER
    ys = -a0                                                   # the shoulder's end seats on the cradle's spacer
    xt, zt = G.tilt_x, G.tilt_c
    sh = cyl_y(S['d'] / 2, ys - S['L'], ys, xt, zt).union(cyl_y(S['head_d'] / 2, ys - S['L'] - S['head_h'], ys - S['L'], xt, zt))
    sh = sh.union(cyl_y(S['thread_d'] / 2 - 0.4, ys, ys + S['thread_L'], xt, zt))
    out['shoulder_screw'] = (sh, 'tilt', S['mass_g'], 'ISO 7379 shoulder screw 6 x 12, M5 x 10: the tilt pivot (-y); McMaster 92981A101')
    M = MOTOR
    for sgn, nm in ((1, 'flywheel_motor_l'), (-1, 'flywheel_motor_r')):
        x, y = G.wheel_x, sgn * G.wheel_y
        m = cyl_z(M['d'] / 2, G.bell_z0, G.plate_z0, x, y)                                   # base and bell (from base_h, it turns)
        m = m.union(cyl_z(M['stub'][0] / 2, G.plate_z0 - 0.01, G.plate_z0 + M['stub'][1], x, y))   # the shaft's rear end and clip
        m = m.union(cyl_z(M['flange'][0] / 2, G.hub_top, G.bell_z0 + 0.01, x, y))           # the prop adapter's flange (over the boss)
        web0 = G.hub_top - M['pilot'][1]
        m = m.union(cyl_z(2.4, web0, G.hub_top + 0.01, x, y))                                # its Ø5 pilot (drawn 4.8: in the hub's bore)
        m = m.union(cyl_z(M['stud'][0] / 2, web0 - M['stud'][1], web0 + 0.01, x, y))         # the M5 stud
        m = m.union(cyl_z(M['washer'][0] / 2, web0 - M['washer'][1], web0, x, y))            # the washer under the hub's web
        m = m.union(cyl_z(M['nut'][0] / 2, web0 - M['washer'][1] - M['nut'][1], web0 - M['washer'][1] + 0.01, x, y))   # M5 nylon-insert nut
        out[nm] = (m, 'tilt', M['mass_g'], f"{M['name']} (SunnySky's drawing): hangs bell-down under the cage plate (4 x M3 x 6), "
                                          'the hub on its prop adapter under the bell (washer + M5 nylon-insert nut)')
    cb = CART_BOARD
    zb = G.plate_z1 + cb['boss_h'] + cb['standoff']                                       # the board's underside
    board = box(cb['x'][0], cb['x'][1], -cb['y'], cb['y'], zb, zb + cb['board_t'])
    board = board.union(box(cb['x'][1] - 10.2, cb['x'][1], -17.8, 17.8, zb + cb['board_t'] - 0.01, zb + cb['board_t'] + cb['parts_h']))
    out['cartridge_board'] = (board, 'tilt', cb['mass_g'], 'cartridge board (est): 6 x IRLZ44N phase-short brake FETs standing along its front edge, '
                              'the LM393 gate comparator, the feed servo\'s polyfuse; on 4 printed posts over the ESCs and the cage plate')
    ex, ey, ez = AM32['size']
    for sgn, nm in ((1, 'esc_l'), (-1, 'esc_r')):
        y0, y1 = (1.5, 1.5 + ey) if sgn > 0 else (-1.5 - ey, -1.5)
        out[nm] = (box(62.0, 62.0 + ex, y0, y1, G.plate_z1 - 0.01, G.plate_z1 + ez), 'tilt', AM32['mass_g'],
                   'Repeat Robotics AM32 35 A, on the cage plate under the cartridge board (the backup Lumenier Razor Pro F4 45A AM32 is 28 x 12 x 5)')
    # the feed servo (D42): an STS3215 under the dial floor, its output face against the floor's underside, horn up, its
    # length to the rear (the servo's far end towards -x), its bus plugs down
    feed = servo_envelope(G, (0.0, 0.0, 0.0), '+z').rotate((0, 0, 0), (0, 0, 1), 90).translate((0, 0, G.feed_face))
    out['feed_motor'] = (feed, 'tilt', SERVO['mass_g'], 'Feetech STS3215 12 V (bus ID 3) under the dial floor, horn up through it; '
                                                     '4 x M2 x 6 countersunk from above; the dial on its horn')
    (lx, ly) = ct_points(G)[1]
    z0r = G.rail_z[0] - RAIL_DEEP['dz']                                                     # the rail is deeper there
    hd, hh = THUMB['head']
    cd, ch = THUMB['collar']
    thumb = cyl_z(cd / 2, z0r - ch, z0r + 0.01, lx, ly).union(cyl_z(hd / 2, z0r - ch - hh, z0r - ch + 0.01, lx, ly))
    out['ct_thumbscrew'] = (thumb, 'tilt', THUMB['mass_g'], 'DIN 464 knurled thumbscrew M4 x 12 (McMaster 92581A250), the CT latch, under the rail')
    out['laser'] = (cyl_x(LASER['d'] / 2, LASER_X[0] - 2, LASER_X[0] - 2 + LASER['L'], LASER_Y, 0), 'tilt', LASER['mass_g'],
                    LASER['name'] + ' (D42)')
    return out


def balls(G, n_hopper=22):
    """Balls for the pictures (not checked for clashes): the dial pockets, the chute, the nip, and a pile in the
    hopper."""
    r = G.ball / 2
    pts = []
    for k in range(G.n_pockets):
        a = math.radians(k * 360 / G.n_pockets)
        if k == 0:
            continue
        pts.append((G.rp * math.cos(a), G.rp * math.sin(a), G.ball_z_dial))
    t = math.radians(45)
    pts.append((G.chute_cx - G.chute_r * math.cos(t), 0, G.chute_r - G.chute_r * math.sin(t)))
    pts.append((G.wheel_x - 7.0, 0, 0))
    z = G.dial_z0 + G.dial_h + r + 3
    rings = [(0, 1), (G.rp - 4, 7), (G.dial_wall_r - r - 1, 10)]
    while len(pts) < G.n_pockets + 1 + n_hopper:
        for rr, n in rings:
            for k in range(n):
                a = 2 * math.pi * k / n + z * 0.05
                pts.append((rr * math.cos(a), rr * math.sin(a), z))
        z += G.ball * 0.9
    return [cq.Workplane('XY').sphere(r).translate(p) for p in pts[:G.n_pockets + 1 + n_hopper]]


# ------------------------------------------------------------------------------------------------ assembly

MADE = [
    # name, function, frame, material, qty, print rotation, note
    ('pan_base', pan_base, 'base', 'pa6-cf', 1, None, 'PA6-CF on its foot; 4 x M5 x 16 into the head ring, 2 x Ø5 dowels'),
    ('pan_ring', pan_ring, 'pan', 'pa6-cf', 1, ((1, 0, 0), 180), 'PA6-CF upside down; DIN 471-50 circlip; 4 x M4 inserts'),
    ('pan_spacer', pan_spacer, 'pan', 'pa6-cf', 1, ((1, 0, 0), 180), 'PA6-CF on its wide end; between the 61810 inner race and the circlip'),
    ('pan_pinion', pan_pinion, 'pinion', 'pa6-cf', 1, None, 'PA6-CF; 4 x M2 to the horn; turns -3 x pan about the servo axis'),
    ('tilt_yoke', tilt_yoke, 'pan', 'pa6-cf', 1, ((0, 1, 0), 90), 'PA6-CF on its back; 4 x M4 x 10 to the turntable (heads 6 mm down in the 12 mm bridge)'),
    ('cradle', cradle, 'tilt', 'pa6-cf', 1, None, 'PA6-CF flat, no supports: the rail frame (D48); 8 x M3 inserts for the aluminium cheek plates'),
    ('horn_boss', horn_boss, 'tilt', 'pa6-cf', 1, ((1, 0, 0), 90), 'PA6-CF on an end face; between the +y plate and the tilt servo\'s horn (4 x M3 x 14 flat heads)'),
    ('pivot_spacer', pivot_spacer, 'tilt', 'pa6-cf', 1, ((1, 0, 0), -90), 'PA6-CF on its boss face, land up; between the -y plate and the MR126 (the shoulder screw through it)'),
    ('cartridge_body', cartridge_body, 'tilt', 'pa6-cf', 1, None, 'PA6-CF on its base; supports under the chute'),
    ('flywheel', flywheel, 'tilt', 'pa6-cf', 2, ((1, 0, 0), 180), 'PA6-CF on its top face; on the X2216\'s prop adapter: washer + M5 nylon-insert nut; bore reamed to 5.00'),
    ('flywheel_tyre', flywheel_tyre, 'tilt', 'tpu95', 2, None, 'TPU 95A tyre'),
    ('dial', dial, 'tilt', 'petg', 1, None, 'PETG; 4 x M3 x 8 down into the feed servo\'s horn, from the top'),
    ('hopper', hopper, 'tilt', 'petg', 1, None, 'translucent PETG; 3 x M3 to the housing'),
    ('hopper_lid', hopper_lid, 'tilt', 'petg', 1, ((1, 0, 0), 180), 'PETG'),
    ('hopper_flap', hopper_flap, 'tilt', 'petg', 1, None, 'PETG; Ø2 pin + torsion spring'),
    ('barrel', barrel, 'tilt', 'petg', 1, ((0, 1, 0), -90), 'PETG standing; last 15 mm blaze orange'),
    ('laser_mount', laser_mount, 'tilt', 'petg', 1, None, 'PETG; 3 x M3 boresight, 2 x M3 to the cradle'),
    ('bumper_ring', bumper_ring, 'base', 'tpu95', 1, None, 'TPU 95A; 5 x M3 with washers'),
    ('ring_carrier', ring_carrier, 'base', 'pa6-cf', 1, ((1, 0, 0), 180), 'PA6-CF on its top face; 3 x M3 x 10 flat heads up into the base; 3 x M3 inserts for the ring'),
    ('ring_driver', ring_driver, 'pan', 'pa6-cf', 1, ((1, 0, 0), 180), 'PA6-CF on its top face; in the turntable\'s bore (ribs + CA)'),
    ('board_bay', board_bay, 'pan', 'petg', 1, ((1, 0, 0), -90), 'PETG on its back; 4 x M3 x 8 flat heads to the -y yoke arm; 4 x M3 inserts for the boards'),
]


class Turret:
    """Builds every part once in its own frame and poses them for any pan/tilt."""

    def __init__(self, L, ball_d=22.7):
        self.L = L
        self.G = Geo(ball_d)
        self.mount_z = L['bodyTop'] + 20.0 + SADDLE_T
        self.local = {}
        self.frame = {}
        self.meta = {}
        for name, fn, frame, mat, qty, rot, note in MADE:
            self.local[name] = fn(self.G)
            self.frame[name] = frame
            self.meta[name] = {'material': mat, 'qty': qty, 'note': note, 'solid': mat == 'pa6-cf' and name not in PARTIAL_FILL, 'frame': frame,
                               'print_rotation': rot, 'doc': (fn.__doc__ or '').split('\n')[0].strip()}
        self.bought = bought_parts(self.G)
        for name, (shape, frame, _, _) in self.bought.items():
            self.local[name] = shape
            self.frame[name] = frame

    def pose_shape(self, shape, frame, pan=0.0, tilt=0.0, robot=True):
        G = self.G
        s = shape
        if frame == 'pinion' and pan:              # meshes with the ring: turns -63/21 x pan about the servo shaft
            x, y = G.servo_pan_xy
            s = s.rotate((x, y, 0), (x, y, 1), -pan * G.gear['z_ring'] / G.gear['z_pinion'])
        if frame == 'tilt':
            s = s.translate((-G.tilt_x, 0, G.path_t))
            if tilt:
                s = s.rotate((0, 0, G.tilt_t), (0, 1, G.tilt_t), -tilt)
        if frame in ('pan', 'tilt') and pan:
            s = s.rotate((0, 0, 0), (0, 0, 1), pan)
        if robot:
            s = s.translate((0, 0, self.mount_z))
        return s

    def posed(self, pan=0.0, tilt=0.0, names=None, robot=True):
        names = names or list(self.local)
        return {n: self.pose_shape(self.local[n], self.frame[n], pan, tilt, robot) for n in names}

    def point(self, p, frame, pan=0.0, tilt=0.0, robot=True):
        """A point from a build frame to the robot (or T) frame."""
        v = cq.Vertex.makeVertex(*p)
        s = self.pose_shape(cq.Workplane('XY').add(v), frame, pan, tilt, robot)
        q = s.val()
        return (round(q.X, 2), round(q.Y, 2), round(q.Z, 2))


# designed contacts (bought part in its seat, plug on its receptacle): checked, but only flagged above the threshold
SKIP_PAIRS = {frozenset(p) for p in [('dt_plug', 'dt_receptacle')]}
# parts in different motion groups that touch by design: bearings on their journals and spacers, the horns on the
# pinion and on the cradle hub, the gear mesh (0.15 mm backlash per flank)
# (the outer races and shields are checked against everything that turns; the inner races turn with their shafts)
DESIGNED_CONTACTS = {frozenset(p) for p in [('pan_bearing', 'pan_bearing_inner'), ('tilt_bearing', 'tilt_bearing_inner'),
                                            ('tilt_servo', 'horn_boss'), ('pan_ring', 'pan_pinion'), ('pan_servo', 'pan_pinion'),
                                            ('shoulder_screw', 'tilt_yoke'),            # the Ø6 shoulder turns in the arm's Ø6.5 hole
                                            ('shoulder_screw', 'tilt_bearing'),         # inside the inner race, which turns with it
                                            ('slip_ring', 'slip_ring_rotor'),           # the ring's own rotor and stator
                                            ('slip_ring', 'ring_coupling'),             # the tube sits on the rotor stub at its end face
                                            ('slip_ring', 'ring_leads_rotor')]}         # the rotor leads leave the rotor's end
# turning parts that bear on an inner race inside its abutment limit (6810: Ø52.5, NSK; 126: Ø7.2, est) pass the
# shield closer than the usual 1 mm: these pairs are flagged only under the gap given
PAIR_MIN_GAP = {frozenset(('pan_spacer', 'pan_bearing')): 0.3, frozenset(('pan_ring', 'pan_bearing')): 0.3,
                frozenset(('pivot_spacer', 'tilt_bearing')): 0.2}
# the tilt hard stop: the pair that touches by design at tilt 0 and at the lower stop
STOP_PAIR = frozenset(('tilt_yoke', 'stop_lug'))


def clashes(T: Turret, tilts=(0.0, -20.0, -25.0), pans=(0.0, 90.0, -90.0, 170.0, -170.0), min_mm3=10.0, verbose=False,
            gaps=None, min_gap=1.0):
    """Pairs of turret parts (made and bought) that overlap by more than min_mm3, like leg.clashes_for_design. Parts in
    the same rigid group are checked once; base-pan pairs at every pan angle; pan-tilt pairs at every tilt; base-tilt
    pairs at every pan x tilt; the pinion turns with the ring (-3 x pan). Includes the proposed head ring and the DT
    plug's 30 mm withdrawal path (against fixed parts only: plug it in with the turret parked). Returns [[part, part, mm3, pan, tilt], ...]."""
    G = T.G
    names = list(T.local)
    extra = {'head_ring': (head_ring_tm(T.L).translate((0, 0, -T.mount_z)), 'base')}
    pl, f = DT['plug'], DT['flange']
    sweep = box(-pl[0] / 2, pl[0] / 2, -(G.dt_y + f[1] + pl[1] + DT['sweep']), -(G.dt_y + f[1] + pl[1]), DT_Z - pl[2] / 2, DT_Z + pl[2] / 2)
    local = dict(T.local)
    frame = dict(T.frame)
    for n, (s, fr) in extra.items():
        local[n], frame[n] = s, fr
        names.append(n)
    local['dt_plug_sweep'], frame['dt_plug_sweep'] = sweep, 'base'
    out = []
    cache = {}

    def get(n, pan, tilt):
        fr = frame[n]
        key = (n, pan if fr != 'base' else 0.0, tilt if fr == 'tilt' else 0.0)
        if key not in cache:
            s = T.pose_shape(local[n], fr, key[1], key[2], robot=False)
            v = s.val() if hasattr(s, 'val') else s
            cache[key] = (v, v.BoundingBox())
        return cache[key]

    def vol(a, b):
        try:
            return a.intersect(b).Volume()
        except Exception:
            return 0.0

    checked = set()
    allnames = names + ['dt_plug_sweep']
    for pan in pans:
        for tilt in tilts:
            for n1, n2 in itertools.combinations(allnames, 2):
                if frozenset((n1, n2)) in SKIP_PAIRS or {n1, n2} == {'dt_plug_sweep', 'dt_plug'}:
                    continue
                fs = {'pan' if frame[n] == 'pinion' else frame[n] for n in (n1, n2)}
                if 'dt_plug_sweep' in (n1, n2) and fs != {'base'}:
                    continue                              # the plug goes in with the turret parked: fixed parts only
                if 'pinion' in (frame[n1], frame[n2]):
                    key = (n1, n2, pan, tilt if 'tilt' in fs else 0.0)      # the pinion turns with pan
                elif len(fs) == 1:
                    key = (n1, n2, 0.0, 0.0)              # same rigid group: once
                elif fs == {'base', 'pan'}:
                    key = (n1, n2, pan, 0.0)
                elif fs == {'pan', 'tilt'}:
                    key = (n1, n2, 0.0, tilt)
                else:
                    key = (n1, n2, pan, tilt)
                if key in checked:
                    continue
                checked.add(key)
                a, ba = get(n1, key[2], key[3])
                b, bb = get(n2, key[2], key[3])
                g = PAIR_MIN_GAP.get(frozenset((n1, n2)), min_gap) if gaps is not None and frame[n1] != frame[n2] and \
                    frozenset((n1, n2)) not in DESIGNED_CONTACTS else 0.0
                if ba.xmax + g < bb.xmin or bb.xmax + g < ba.xmin or ba.ymax + g < bb.ymin or bb.ymax + g < ba.ymin or \
                        ba.zmax + g < bb.zmin or bb.zmax + g < ba.zmin:
                    continue
                v = vol(a, b)
                if g and v <= min_mm3:                    # moving past each other: how close?
                    dmin = a.distance(b)
                    if dmin < g:
                        gaps.append([n1, n2, round(dmin, 2), key[2], key[3]])
                if verbose and v > 0.5:
                    print(f'    {n1} x {n2}: {v:.1f} mm3 at pan {key[2]}, tilt {key[3]}')
                if v > min_mm3:
                    out.append([n1, n2, round(v, 1), key[2], key[3]])
    return out


SWEEP_TILTS = (0.0, -5.0, -12.5, -20.0, -25.0)      # D48: the lug swings between the yoke's two stop sectors


def sweep(T: Turret, out_dir: Path, step=10.0, tilts=SWEEP_TILTS):
    """The clash sweep the pan joint's acceptance asks for (docs/turret-plan.md 7.1 T1): every pan from 0 to 350 deg in
    `step` steps at each tilt (0, -5, -12.5, -20, -25 since D48), all parts with their designed contacts, moving pairs
    flagged under 1 mm; the tilt hard stop (STOP_PAIR) may touch only at 0 and -25 deg. Writes clash-sweep.json."""
    pans = [float(p) for p in np.arange(0.0, 360.0, step)]
    t0 = time.time()
    gaps = []
    cl = clashes(T, tilts=tilts, pans=pans, gaps=gaps)
    stop = lambda a, b, t: frozenset((a, b)) == STOP_PAIR and t in (0.0, T.G.tilt_min)
    res = {'pans_deg': pans, 'tilts_deg': list(tilts), 'continuous_pan': CONTINUOUS_PAN, 'ring_model': RING_MODEL,
           'clashes': cl, 'gaps_under_1mm': [g + (['the tilt hard stop, touching by design'] if stop(g[0], g[1], g[4]) else []) for g in gaps],
           'unexpected_gaps': [g for g in gaps if not stop(g[0], g[1], g[4])], 'seconds': round(time.time() - t0)}
    (out_dir / 'clash-sweep.json').write_text(json.dumps(res, indent=1) + '\n')
    return res


def pinion_check(T: Turret, out_dir: Path, pans=range(130, 231), tilt=None):
    """The fine check of the pan joint's acceptance (docs/turret-plan.md 7.1 T1): at full depression, every degree where
    the cradle's nose passes over the pan pinion (pans 130..230: the pinion stands behind the pan axis), each tilting
    part's nearest approach to the pinion (it turns -3 x pan). Writes over_pinion_tilt_-25 in t1-fine-checks.json, keeping
    the file's other sections (the lead bundle's clearances, which no turret change has touched)."""
    tilt = T.G.tilt_min if tilt is None else tilt
    names = [n for n in T.local if T.frame[n] == 'tilt' and n not in ('flywheel', 'flywheel_tyre')]
    near = {}
    for pan in pans:
        pin = T.pose_shape(T.local['pan_pinion'], 'pinion', float(pan), tilt, robot=False).val()
        pbb = pin.BoundingBox()
        for n in names:
            v = T.pose_shape(T.local[n], 'tilt', float(pan), tilt, robot=False).val()
            bb = v.BoundingBox()
            gap = max(bb.xmin - pbb.xmax, pbb.xmin - bb.xmax, bb.ymin - pbb.ymax, pbb.ymin - bb.ymax, bb.zmin - pbb.zmax, pbb.zmin - bb.zmax)
            if gap > 20.0 and n in near:          # far off by its box: only refine the near ones
                continue
            d = v.distance(pin) if gap <= 20.0 else gap
            if n not in near or d < near[n][0]:
                near[n] = [round(d, 2), pan]
    f = out_dir / 't1-fine-checks.json'
    res = json.loads(f.read_text()) if f.exists() else {}
    res[f'over_pinion_tilt_{tilt:.0f}'] = dict(sorted(near.items(), key=lambda kv: kv[1][0]))
    res['over_pinion_how'] = f'nearest approach to the pan pinion (mm, at the pan in deg), pans {min(pans)}..{max(pans)} every 1 deg, tilt {tilt:.0f}'
    f.write_text(json.dumps(res, indent=1) + '\n')
    return near


def mass_properties(T: Turret, tilt=0.0, with_balls=True, pan=0.0):
    """Mass and centre of mass of every part (printed parts by cadagent's printed-part model: PA6-CF 100 % solid,
    PETG and TPU 2 mm walls + 40 % infill) and of the whole turret, in the T frame (relative to the mount point:
    the pan axis on the TM face). Bought parts: catalogue mass at the envelope's centroid."""
    from cadagent.robot import printed_part_body
    rows = {}
    for name, m in T.meta.items():
        s = T.pose_shape(T.local[name], T.frame[name], pan, tilt, robot=False)
        v = s.val()
        wall, infill = (500.0, 1.0) if m['solid'] else (2.0, 0.4)
        body, rep = printed_part_body(v, DENS[m['material']], wall_mm=wall, infill=infill, name=name)
        com = [c * 1000 for c in body.com]
        rows[name] = {'mass_g': rep['mass_g'], 'qty': m['qty'], 'com_mm': com, 'volume_cm3': rep['volume_cm3'],
                      'material': m['material'], 'made': True}
        if m['qty'] == 2:                    # the second flywheel and tyre: mirror in y (in the cartridge frame)
            c2 = T.pose_shape(T.local[name].mirror('XZ'), T.frame[name], pan, tilt, robot=False).val()
            rows[name]['com_mm_2'] = [c * 1000 for c in printed_part_body(c2, DENS[m['material']], wall_mm=wall, infill=infill)[0].com]
    for name, (shape, frame, mass, note) in T.bought.items():
        if mass <= 0:
            continue
        c = cq.Shape.centerOfMass(T.pose_shape(shape, frame, pan, tilt, robot=False).val())
        rows[name] = {'mass_g': mass, 'qty': 1, 'com_mm': [c.x, c.y, c.z], 'made': False, 'note': note}
    G = T.G
    other_z = G.turntable_z[1]
    rows['not_modelled'] = {'mass_g': float(sum(NOT_MODELLED_G.values())), 'qty': 1, 'com_mm': [0.0, 0.0, other_z], 'made': False,
                            'note': '; '.join(f'{k} {v} g' for k, v in NOT_MODELLED_G.items()) + ' (est, at the turntable)'}
    if with_balls:
        bm = 30 * 1.83
        c = T.point((0, 0, (G.dial_z0 + G.hopper_top) / 2 - 8), 'tilt', pan, tilt, robot=False)
        rows['balls_30'] = {'mass_g': bm, 'qty': 1, 'com_mm': list(c), 'made': False, 'note': '30 Rival rounds x 1.83 g'}
    tot, mom = 0.0, [0.0, 0.0, 0.0]
    for r in rows.values():
        coms = [r['com_mm']] + ([r['com_mm_2']] if 'com_mm_2' in r else [r['com_mm']] * (r['qty'] - 1))
        for c in coms:
            tot += r['mass_g']
            mom = [m + r['mass_g'] * ci for m, ci in zip(mom, c)]
    com = [m / tot for m in mom]
    return rows, tot, com


def turret_parts(L, ball_d=22.7, pan=0.0, tilt=0.0):
    """The turret for the robot build, in the robot frame (x forward, y left, z up; mm), posed at (pan, tilt).

    Returns (made, meta, bought, info):
      made   {name: shape}  printed parts (qty in meta; the two flywheels/tyres: the +y one, mirror for the other)
      meta   {name: {material, qty, note, solid, frame, print_rotation}}  frame: 'base' fixed to the head, 'pan' turns
             about the pan axis, 'tilt' turns about the tilt axis too, 'pinion' turns -3 x pan about the pan servo's
             shaft (it meshes with the pan ring)
      bought {name: shape}  envelopes (servos, bearings, motors, ESCs, laser, DT receptacle and plug)
      info   {mount, pan_axis, tilt_axis, muzzle, muzzle_dir, tilt_range_deg, pan_range_deg, mass_estimate_g, com,
              head_ring, ...}"""
    T = Turret(L, ball_d)
    G = T.G
    P = T.posed(pan, tilt)
    made = {n: P[n] for n in T.meta}
    bought = {n: P[n] for n in T.bought}
    meta = {n: {k: v for k, v in m.items()} for n, m in T.meta.items()}
    rows, tot, com = mass_properties(T, tilt, pan=pan)
    rad = math.radians
    a = rad(tilt)
    d = (math.cos(a) * math.cos(rad(pan)), math.cos(a) * math.sin(rad(pan)), math.sin(a))
    info = {
        'mount': {'point': [0.0, 0.0, T.mount_z], 'interface': 'TM: 4 x M5 on 80 x 80, 2 x Ø5 dowels at (52, 0) and (0, -52), Ø45 centre hole',
                  'needs': 'head_ring_tm(L) in place of the head_saddle ring (see its docstring)'},
        'pan_axis': {'point': [0.0, 0.0, T.mount_z], 'dir': [0, 0, 1]},
        'tilt_axis': {'point': list(T.point((G.tilt_x, 0, G.tilt_c), 'tilt', pan, 0.0)), 'dir': [-math.sin(rad(pan)), math.cos(rad(pan)), 0.0]},
        'muzzle': list(T.point((G.barrel_x1, 0, 0), 'tilt', pan, tilt)),
        'muzzle_dir': [round(c, 4) for c in d],
        'laser_origin': list(T.point((LASER_X[1], LASER_Y, 0), 'tilt', pan, tilt)),
        'tilt_range_deg': [G.tilt_min, 0.0], 'pan_range_deg': [-170.0, 170.0], 'pan_hard_stop_deg': 173.5,
        'mass_estimate_g': round(tot, 1),
        'com': [round(c, 1) for c in (com[0], com[1], com[2] + T.mount_z)],
        'com_above_mount_mm': round(com[2], 1),
        'ball_d': ball_d, 'bore': G.bore, 'pose': {'pan': pan, 'tilt': tilt},
        'head_ring': head_ring_tm(L),
    }
    return made, meta, bought, info


# ------------------------------------------------------------------------------------------------ main

def derive(design: Path) -> dict:
    out = subprocess.run(['node', str(R / 'tools/derive.mjs'), str(design)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)['layout']


# which way each sheet part's DXF looks at it: the face its countersinks are cut in (the one a screw head goes into)
# faces the viewer, so the DXF is the part as SendCutSend sees it with that face up (a mirror image would put the
# countersinks on the wrong side of an asymmetric part)
SHEET_VIEW = {'pan_clamp': (0, 0, 1), 'cradle_plate_l': (0, -1, 0), 'cradle_plate_r': (0, 1, 0), 'stop_lug': (0, 1, 0)}


def sheet_flat(name, shape):
    """A sheet part's outline as one planar face in the XY plane at z = 0 for its DXF: turned so its SHEET_VIEW side
    faces +z, and taken from its far face (through holes at their cut size, without the countersinks)."""
    v = SHEET_VIEW.get(name, (0, 0, 1))
    s = shape
    if v == (0, -1, 0):
        s = s.rotate((0, 0, 0), (1, 0, 0), -90)
    elif v == (0, 1, 0):
        s = s.rotate((0, 0, 0), (1, 0, 0), 90)
    elif v != (0, 0, 1):
        raise ValueError(f'{name}: SHEET_VIEW {v} not handled')
    f = s.faces('<Z').val()
    return f.translate(cq.Vector(0, 0, -f.Center().z))


def print_fit(shape, rotation):
    s = shape
    if rotation:
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(*rotation[0]), rotation[1])
    bb = s.BoundingBox()
    dims = sorted((bb.xlen, bb.ylen), reverse=True) + [bb.zlen]
    return [round(d, 1) for d in dims], dims[0] <= BED[0] - 6 and dims[1] <= BED[1] - 6 and dims[2] <= BED[2] - 6


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    design = Path(args[0]) if args else R / 'designs/default.json'
    L = derive(design)
    out = R / 'exports' / 'turret'
    out.mkdir(parents=True, exist_ok=True)
    T = Turret(L)
    G = T.G
    print(f'turret on {design.name}: mount face at z = {T.mount_z:.1f} (bodyTop {L["bodyTop"]} + 20 + {SADDLE_T:.0f}); '
          f'ball path {G.path_t} mm and tilt axis {G.tilt_t} mm above it; ball Ø{G.ball}, bore Ø{G.bore}')

    # validity, bed fit, masses
    rows, tot, com = mass_properties(T, 0.0)
    _, tot_empty, com_empty = mass_properties(T, 0.0, with_balls=False)
    from cadagent.geometry import export_print_stl
    print('\nMADE PARTS (printed)')
    print(f'  {"part":16} {"qty":>3}  {"material":8} {"g each":>7} {"g total":>8} {"hours":>6}  {"bed (mm)":>18}  valid')
    made_g = made_h = 0.0
    summary = {'parts': {}, 'bought': {}}
    for name, m in T.meta.items():
        v = T.local[name].val()
        valid = v.isValid() and len(T.local[name].solids().vals()) == 1
        dims, fits = print_fit(v, m['print_rotation'])
        g = rows[name]['mass_g']
        hrs = g * m['qty'] / DENS[m['material']] / PRINT_RATE_CM3_H[m['material']]
        made_g += g * m['qty']
        made_h += hrs
        print(f'  {name:16} {m["qty"]:>3}  {m["material"]:8} {g:7.1f} {g * m["qty"]:8.1f} {hrs:6.1f}  {str(dims):>18}  '
              f'{"ok" if valid else "INVALID"}{"" if fits else "  DOES NOT FIT THE BED"}')
        summary['parts'][name] = {**{k: v for k, v in m.items() if k != 'print_rotation'}, 'mass_g_each': g, 'print_h': round(hrs, 1),
                                  'bed_mm': dims, 'fits_bed': fits, 'valid_single_solid': valid}
        posed = T.pose_shape(T.local[name], T.frame[name], robot=True).val()
        cq.exporters.export(posed, str(out / f'{name}.step'))
        pv = PRINT_AS[name](G).val() if name in PRINT_AS else v
        export_print_stl(pv, out / f'{name}.stl', rotation=m['print_rotation'])
    print(f'  {"made total":16} {"":>3}  {"":8} {"":>7} {made_g:8.1f} {made_h:6.1f}')
    summary['tyre_set'] = {}
    for d in TYRE_SET:                                   # the tyre set the bench chooses from (TYRE_SET's note)
        tv = flywheel_tyre_print(G, d).val()
        fn = f'flywheel_tyre_d{d:.0f}.stl'
        export_print_stl(tv, out / fn, rotation=T.meta['flywheel_tyre']['print_rotation'])
        bb = tv.BoundingBox()
        summary['tyre_set'][f'{d:.0f}'] = {'file': fn, 'mounted_d_mm': d, 'printed_od_mm': round(bb.xlen, 2),
                                           'printed_bore_mm': round(2 * (G.wheel_d / 2 - G.tyre_t) * (1 - TYRE_STRETCH), 2),
                                           'crush_on_this_cage': round(1 - (G.wheel_c - d) / G.ball, 3)}
    print('  tyre set (as printed): ' + ', '.join(f"Ø{k} mounted (print OD {v['printed_od_mm']}, bore {v['printed_bore_mm']}, "
                                                 f"crush {v['crush_on_this_cage'] * 100:.1f} %)" for k, v in summary['tyre_set'].items()))
    print('\nBOUGHT PARTS (envelopes)')
    bought_g = 0.0
    for name, (shape, frame, mass, note) in T.bought.items():
        print(f'  {name:18} {mass:6.1f} g  {note}')
        bought_g += mass
        summary['bought'][name] = {'mass_g': mass, 'note': note, 'frame': frame}
        cq.exporters.export(T.pose_shape(shape, frame, robot=True).val(), str(out / f'asm_{name}.step'))
    # the parts ordered from SendCutSend: a DXF of the outline (mm, 1:1, its holes as closed contours) and a STEP
    summary['sheet'] = {}
    for name, stock in SHEET_PARTS.items():
        shape = T.local[name]
        flat = sheet_flat(name, shape)
        cq.exporters.export(cq.Workplane('XY').add(flat), str(out / f'{name}.dxf'), exportType='DXF')
        cq.exporters.export(shape.val(), str(out / f'{name}.step'))
        bb = flat.BoundingBox()
        st = SHEET[stock]
        summary['sheet'][name] = {'dxf': f'exports/turret/{name}.dxf', 'step': f'exports/turret/{name}.step', 'vendor': st['vendor'],
                                  'material': st['name'], 'thickness_in': st['thickness_in'], 'thickness_mm': st['thickness_mm'],
                                  'size_mm': [round(bb.xlen, 1), round(bb.ylen, 1)], 'mass_g': T.bought[name][2], 'order': st['url'],
                                  'operations': SHEET_OPS.get(name, 'none')}
        print(f'  {name}: {st["vendor"]} {st["name"]} {st["thickness_in"]} in, {bb.xlen:.0f} x {bb.ylen:.0f} mm -> {name}.dxf'
              f'{"; " + SHEET_OPS[name] if SHEET_OPS.get(name, "none") != "none" else ""}')
    nm = sum(NOT_MODELLED_G.values())
    print(f'  {"not modelled":18} {nm:6.1f} g  ' + ', '.join(f'{k} {v}' for k, v in NOT_MODELLED_G.items()))
    cq.exporters.export(head_ring_tm(L).val(), str(out / 'head_ring_tm.step'))
    print(f'\nTURRET: {tot / 1000:.3f} kg with 30 balls ({tot_empty / 1000:.3f} kg empty): made {made_g:.0f} g, bought {bought_g:.0f} g, '
          f'not modelled {nm} g, balls 55 g')
    print(f'  centre of mass from the mount point (pan axis on the TM face): x {com[0]:+.1f}, y {com[1]:+.1f}, z {com[2]:+.1f} mm '
          f'(empty: {com_empty[0]:+.1f}, {com_empty[1]:+.1f}, {com_empty[2]:+.1f})')
    # tilt balance: the moving group's centre of mass about the tilt axis
    tilt_names = [n for n in T.local if T.frame[n] == 'tilt']
    tm = sum(rows[n]['mass_g'] * rows[n].get('qty', 1) for n in tilt_names if n in rows) + rows['balls_30']['mass_g']
    tx = (sum(rows[n]['mass_g'] * (rows[n]['com_mm'][0] + (rows[n].get('com_mm_2') or rows[n]['com_mm'])[0] * (rows[n]['qty'] - 1))
              for n in tilt_names if n in rows) + rows['balls_30']['mass_g'] * rows['balls_30']['com_mm'][0]) / tm
    print(f'  tilting group {tm:.0f} g, centre {tx:+.1f} mm ahead of the tilt axis: holding torque {tm / 1000 * 9.81 * tx / 1000:.2f} N·m '
          f'(STS3215 stall 2.94); unpowered it ' + ('drops to the -25 deg stop' if tx > 0 else 'rises to the 0 deg stop'))

    # clash check
    print('\nCLASH CHECK (tilt 0, -20, -25 deg x pan 0, +-90, +-170 deg; incl. the proposed head ring and the DT plug path)')
    gaps = []
    cl = clashes(T, verbose=True, gaps=gaps)
    print('  no clashes' if not cl else '\n'.join(f'  CLASH {a} x {b}: {v} mm3 at pan {p}, tilt {t}' for a, b, v, p, t in cl))
    stop = lambda a, b, t: frozenset((a, b)) == STOP_PAIR and t in (0.0, G.tilt_min)
    print('  moving parts closer than 1 mm (designed contacts excluded): ' +
          ('none' if not gaps else '; '.join(f'{a} x {b} {d} mm at pan {p}, tilt {t}' + (' (the tilt hard stop, touching by design)' if stop(a, b, t) else '')
                                            for a, b, d, p, t in gaps)))
    made, meta, bought, info = turret_parts(L)
    info_out = {k: v for k, v in info.items() if k != 'head_ring'}
    print('\nINFO', json.dumps(info_out, indent=None)[:1500])
    summary.update({'info': info_out, 'clashes': cl, 'gaps_under_1mm': gaps, 'mass_g_with_balls': round(tot, 1), 'mass_g_empty': round(tot_empty, 1),
                    'com_from_mount_mm': [round(c, 1) for c in com], 'not_modelled_g': NOT_MODELLED_G,
                    'print_hours': round(made_h, 1), 'made_g': round(made_g, 1)})
    (out / 'turret.json').write_text(json.dumps(summary, indent=1, default=str) + '\n')
    if '--sweep' in sys.argv:
        r = sweep(T, out)
        print(f"\nSWEEP pans 0..350 every 10 deg x tilts {r['tilts_deg']}: {len(r['clashes'])} clashes, "
              f"{len(r['gaps_under_1mm'])} moving pairs under 1 mm ({r['seconds']} s)")
        pc = pinion_check(T, out)
        print('OVER THE PINION at full depression (nearest, mm @ pan): ' + ', '.join(f'{n} {d} @ {p}' for n, (d, p) in
                                                                                 sorted(pc.items(), key=lambda kv: kv[1][0])[:6]))
    if '--no-render' not in sys.argv:
        render(T, L, out)


COL = {
    'ct_thumbscrew': (0.10, 0.10, 0.11),
    'pan_base': (0.30, 0.32, 0.35), 'pan_clamp': (0.40, 0.42, 0.45), 'pan_ring': (0.85, 0.42, 0.10), 'pan_pinion': (0.95, 0.62, 0.30),
    'tilt_yoke': (0.35, 0.37, 0.40), 'cradle': (0.20, 0.45, 0.75), 'cartridge_body': (0.45, 0.47, 0.50),
    'cradle_plate_l': (0.74, 0.76, 0.80), 'cradle_plate_r': (0.74, 0.76, 0.80), 'stop_lug': (0.62, 0.64, 0.68),
    'horn_boss': (0.20, 0.45, 0.75), 'pivot_spacer': (0.20, 0.45, 0.75),
    'flywheel': (0.25, 0.25, 0.27), 'flywheel_tyre': (0.10, 0.10, 0.10), 'dial': (0.95, 0.80, 0.20),
    'hopper': (0.70, 0.85, 0.95, 0.35), 'hopper_lid': (0.70, 0.85, 0.95, 0.6), 'hopper_flap': (0.70, 0.85, 0.95, 0.8),
    'barrel': (0.95, 0.45, 0.10), 'laser_mount': (0.30, 0.65, 0.35), 'bumper_ring': (0.15, 0.15, 0.17),
    'pan_servo': (0.12, 0.12, 0.14), 'tilt_servo': (0.12, 0.12, 0.14), 'pan_bearing': (0.75, 0.75, 0.78),
    'tilt_bearing': (0.75, 0.75, 0.78), 'dt_receptacle': (0.55, 0.55, 0.20), 'dt_plug': (0.55, 0.55, 0.20, 0.5),
    'pan_bearing_inner': (0.80, 0.80, 0.83), 'tilt_bearing_inner': (0.80, 0.80, 0.83), 'circlip_50': (0.10, 0.10, 0.11),
    'shoulder_screw': (0.10, 0.10, 0.11), 'pan_spacer': (0.85, 0.42, 0.10),
    'ring_carrier': (0.30, 0.32, 0.35), 'ring_driver': (0.85, 0.42, 0.10), 'board_bay': (0.55, 0.60, 0.65),
    'slip_ring': (0.80, 0.65, 0.20), 'slip_ring_rotor': (0.80, 0.65, 0.20), 'ring_coupling': (0.95, 0.95, 0.90),
    'ring_leads_rotor': (0.75, 0.15, 0.15), 'base_board': (0.10, 0.45, 0.20), 'turret_board': (0.10, 0.45, 0.20),
    'index_magnet': (0.60, 0.60, 0.65), 'hall_switch': (0.10, 0.10, 0.10),
    'flywheel_motor_l': (0.65, 0.15, 0.15), 'flywheel_motor_r': (0.65, 0.15, 0.15), 'esc_l': (0.1, 0.35, 0.15), 'esc_r': (0.1, 0.35, 0.15),
    'feed_motor': (0.12, 0.12, 0.14), 'cartridge_board': (0.10, 0.45, 0.20), 'laser': (0.15, 0.6, 0.15),
    'head_ring': (0.80, 0.82, 0.85, 0.5), 'j501_top': (0.80, 0.82, 0.85, 0.25), 'ball': (0.98, 0.55, 0.10),
}


def _shape_items(P, extra=()):
    items = []
    for n, s in P.items():
        if n == 'flywheel' or n == 'flywheel_tyre':
            items.append((s.val(), COL[n]))
            items.append((s.mirror('XZ').val(), COL[n]))
            continue
        items.append((s.val() if hasattr(s, 'val') else s, COL.get(n, (0.6, 0.6, 0.6))))
    items += list(extra)
    return items


def _place_labels(items, view, top=150, bottom=950, x_left=40, x_right=1080):
    """Callouts without crossing leaders: project each anchor along the camera direction (parallel projection, as the
    renderer does), send it to the left or right column by its screen x, order each column by screen y, and number
    them in reading order. items: [(text, world_point)]."""
    d = view
    n = math.sqrt(sum(c * c for c in d))
    f = [-c / n for c in d]                                     # looking direction
    up = (0.0, 0.0, 1.0)
    right = (f[1] * up[2] - f[2] * up[1], f[2] * up[0] - f[0] * up[2], f[0] * up[1] - f[1] * up[0])
    rn = math.sqrt(sum(c * c for c in right))
    right = [c / rn for c in right]
    upv = (right[1] * f[2] - right[2] * f[1], right[2] * f[0] - right[0] * f[2], right[0] * f[1] - right[1] * f[0])
    proj = [(sum(a * b for a, b in zip(pt, right)), -sum(a * b for a, b in zip(pt, upv)), text, pt) for text, pt in items]
    order = sorted(proj, key=lambda q: q[0])                    # the left half of the anchors goes to the left column
    half = (len(order) + 1) // 2
    cols = [sorted(order[:half], key=lambda q: q[1]), sorted(order[half:], key=lambda q: q[1])]
    out, k = [], 1
    for col, x in zip(cols, (x_left, x_right)):
        step = (bottom - top) / max(1, len(col) - 1) if len(col) > 1 else 0
        for i, (_, _, text, pt) in enumerate(col):
            out.append((str(k), text, pt, (x, int(top + i * step))))
            k += 1
    return out


def render(T, L, out):
    from cadagent.render import Renderer
    G = T.G
    r = Renderer(out, size=(1600, 1150), subtitle='Gyropup foam-ball turret (Rival rounds Ø22.7): every part printed, bought parts as envelopes')
    P = T.posed(0.0, 0.0)
    B = L['body']
    j501 = box(-B['depth'] / 2, B['depth'] / 2, -B['width'] / 2, B['width'] / 2, L['bodyTop'] - 40, L['bodyTop'])
    extra = [(head_ring_tm(L).val(), COL['head_ring']), (j501.val(), COL['j501_top'])]
    p = lambda pt, fr='tilt': T.point(pt, fr, 0.0, 0.0)
    mz = T.mount_z
    view = (0.45, -1.0, 0.5)
    labels = _place_labels([
        ('hopper, 30 balls (translucent PETG)', p((-30, -G.dial_wall_r - 2, 55))),
        ('fill port + sprung flap (dock spout)', p((FILL_PORT[0], 0, G.hopper_top + 3))),
        ('tilt yoke; hard stops at 0 and -25 deg inside', (0, -G.arm_y[1], mz + G.tilt_t - 40)),
        ('feed servo STS3215 (ID 3) under the dial floor', p((-20, -SERVO['W'] / 2, -10))),
        ('pan servo STS3215 + 21 T pinion', (G.servo_pan_xy[0], -16.0, mz + 20)),
        ('pan base on the TM pattern', (30, -64, mz + 12)),
        ('proposed head ring: 4 x M5 inserts', (60, -20, mz - 4)),
        ('X2216 motors hang under this plate; cartridge board and ESCs on posts above', p((G.wheel_x, -G.wheel_y, G.plate_z1))),
        ('cartridge: dial housing, chute, flywheel cage', p((G.wheel_x, -G.cage_y, 10))),
        ('barrel: bore ball + 2.0, 2 gates', p((G.barrel_x1 - 20, -G.barrel_od / 2, 0))),
        ('aiming laser (on the cradle)', p((LASER_X[1] + 10, LASER_Y - 6, 0))),
        ('cradle: cartridge on 2 dowels + thumbscrew', p((40, -G.cheek_y[1], G.rail_z[0] + 2))),
        ('turntable: 63 T gear on the 6810-2Z', (0, -40, mz + 52)),
        ('turret-board bay (three boards, PETG tray)', (0, -(G.arm_y[1] + TB['y_out']) / 2 - 5, mz + sum(TB['z']) / 2 + 20)),
        ('DT 12-way receptacle (head <-> turret)', (0, -(G.dt_y + 20), mz + DT_Z)),
        ('TPU bumper ring', (60, -55, mz + 12)),
    ], view)
    r.render('turret.png', shapes=_shape_items(P, extra), view=view, labels=labels, zoom=0.86,
             caption='The turret at tilt 0: pan base, yoke, cradle and ball cartridge',
             note=('Mount face at bodyTop + 28 mm. Continuous pan through a slip ring (index magnet at pan 0); ' if CONTINUOUS_PAN else
                   'Mount face at bodyTop + 28 mm. Pan +-170 deg (hard stops at +-173.5); ') + 'tilt 0 .. -25 deg: the barrel cannot point above horizontal.')
    # section through the ball path (y = 0), with balls
    bl = [(T.pose_shape(b, 'tilt').val(), COL['ball']) for b in balls(G)]
    Ps = {n: s for n, s in P.items() if n not in ('hopper_lid', 'hopper_flap', 'dt_plug')}
    items = [(sh, (*c[:3], 1.0)) for sh, c in _shape_items(Ps, [(head_ring_tm(L).val(), COL['head_ring'])])] + bl
    lab = _place_labels([
        ('hopper: balls fall into the dial pockets', p((-30, 0, 55))),
        ('dial (8 pockets) on the feed servo\'s horn', p((-G.rp, 0, G.dial_z0 + 10))),
        ('exit hole: the ball drops ...', p((G.exit_x, 0, G.floor_z))),
        ('... and the chute turns it forward', p((G.chute_cx - 15, 0, 3))),
        (f'flywheel nip (crush {G.crush * G.ball:.1f} mm)', p((G.wheel_x, 4, 0))),
        (f'barrel, bore Ø{G.bore_out:.1f} from the nip on', p((G.barrel_x0 + 50, 0, G.br_out))),
        (f'tilt axis ({G.tilt_x:.0f} mm ahead of the dial axis)', p((G.tilt_x, 0, G.tilt_c))),
        ('feed servo (STS3215) under the dial floor', p((-25, 0, -5))),
        ('pan: 6810-2Z bearing round the slip ring', (BRG['D'] / 2 - 2, 0, mz + G.brg_z + 3)),
        ('slip ring on its carrier (flange down)', (11.0, 0, mz + ring_geom(G)['top'] - 12)),
        ('ring driver: turns the rotor through a tube', (0, 0, mz + ring_geom(G)['driver'][1] - 2)),
    ], (0.0, -1.0, 0.0), top=170, bottom=900)
    r.render('turret-section.png', shapes=items, view='section', labels=lab, zoom=1.0, clip=((0, 0.01, 0), (0, 1, 0)),
             caption='Section on the ball path (y = 0): hopper -> dial -> chute -> flywheels -> barrel',
             note=f'Ball Ø{G.ball} in a Ø{G.bore} path (+1.5 mm), Ø{G.bore_out} from the nip to the muzzle. The dial stops with a pocket over the exit hole; '
                  f'the baffle above it stops a refill, so one ball per step.')
    # the pan joint from below: the carrier's three flat heads in the foot's underside (the turret off its mount), and
    # the same with the head ring in place, which covers them: the ring is serviced with the turret off its mount
    base_names = [n for n in P if T.frame[n] in ('base',) or n in ('pan_ring', 'ring_driver', 'slip_ring_rotor', 'ring_coupling')]
    Pb = {n: P[n] for n in base_names if n not in ('dt_plug',)}
    up = (0.35, -0.55, -1.0)
    C = CARRIER
    lab_b = _place_labels([
        ('carrier: 3 x M3 x 10 flat heads, flush', (*polar(C['screw_r'], math.radians(C['tab_angles'][0])), mz)),
        ('slip ring flange in the carrier, stator leads to -y', (0, -C['r'] + 4, mz + 2)),
        ('TM: 4 x M5 x 16 and 2 x Ø5 dowels', (*TM_BOLTS[0], mz)),
        ('base-board bay above this (+x)', (BB['x0'], 0, mz)),
        ('DT 12-way receptacle', (0, -G.dt_y, mz + DT_Z)),
    ], up, top=170, bottom=900)
    r.render('turret-pan-joint.png', shapes=_shape_items(Pb), view=up, labels=lab_b, zoom=1.1,
             caption='The pan joint from below, off its mount: the slip ring\'s carrier is held by three flat heads in the foot',
             note='On the robot the head ring (Ø60 hole) covers these screws: lift the turret off (4 x M5, the DT12) to change the ring.')


if __name__ == '__main__':
    main()
