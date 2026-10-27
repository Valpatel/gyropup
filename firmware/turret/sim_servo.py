"""A simulated STS3215 on the bus: it answers packets (sts.py) and moves, for the feed's unit test and the simulated
turret (sim_turret.py). Not firmware.

Kept simple and stated: a position loop that is time-optimal under a speed limit (the goal-speed register, or the
servo's 12 V no-load speed) and an acceleration limit (the ACC register x 100 counts/s^2, or ~50,000 counts/s^2 when
ACC is 0: the 50 % torque cap through the gearbox, est), a 10 ms linear zone at the goal, a load reading that is the
start-up torque plus friction plus the torque cap when blocked, and a power input: unpowered it neither moves nor
answers, and it boots 0.3 s after its rail returns with torque off and the RAM registers at their defaults.

Modes: 0 (position: an absolute goal inside the angle limits) and 3 (step: a relative step, applied to the present
position, or to the last goal with ref='goal', the alternative the bench rules out or in).
"""
from __future__ import annotations

import math
import random
from typing import Optional

import sts

A_MAX = 50_000.0        # counts/s^2 with ACC = 0 (est)
V_NO_LOAD = 3072.0      # counts/s at 12 V (45 rpm)
BOOT_S = 0.3


class SimServo:
    def __init__(self, sid: int, mode: int = 3, pos: float = 0.0, min_angle: int = 0, max_angle: int = 0,
                 rng: Optional[random.Random] = None, ref: str = 'present', p_corrupt: float = 0.0,
                 read_noise: float = 1.0):
        self.sid = sid
        self.rng = rng or random.Random(sid)
        self.ref = ref
        self.p_corrupt = p_corrupt            # probability that a reply is corrupted (checksum fails)
        self.read_noise = read_noise          # +- counts on position reads
        self.eeprom = {'mode': mode, 'min_angle': min_angle, 'max_angle': max_angle}
        self.pos = float(pos)                 # output shaft, counts, continuous
        self.vel = 0.0
        self.goal = float(pos)
        self.powered = True
        self.boot_at = 0.0                    # answers from this time on
        self.blocked_hi: Optional[float] = None   # forward motion stops here (a jam, a hard stop)
        self.blocked_lo: Optional[float] = None
        self.load_factor = 1.0                # speed under load (1 = no-load line)
        self.extra_load = 0.0                 # 0.1 % units of steady load (a full hopper)
        self._acc_now = 0.0
        self.pushing = False
        self.vel_meas: Optional[float] = None   # set by a plant that integrates the motion itself (the pan)
        self.writes = 0
        self._reset_ram()

    # ---------------------------------------------------------------- power
    def _reset_ram(self):
        self.torque_on = False
        self.acc = 0
        self.goal_speed = 0
        self.torque_limit = 1000
        self.goal = self.pos

    def set_power(self, on: bool, t: float):
        if on and not self.powered:
            self.boot_at = t + BOOT_S
            self._reset_ram()
        if not on:
            self.torque_on = False
        self.powered = on

    def online(self, t: float) -> bool:
        return self.powered and t >= self.boot_at

    # ---------------------------------------------------------------- the bus
    def handle(self, pkt: bytes, t: float) -> Optional[bytes]:
        p = sts.parse(pkt)
        if p is None or not self.online(t):
            return None
        sid, instr, params = p
        if sid not in (self.sid, sts.BROADCAST):
            return None
        reply = b''
        if instr == sts.PING:
            pass
        elif instr == sts.READ:
            addr, n = params[0], params[1]
            reply = self._read(addr, n)
        elif instr == sts.WRITE:
            self._write(params[0], params[1:], t)
        else:
            return None
        if sid == sts.BROADCAST:
            return None
        out = sts.packet(self.sid, 0, reply)
        if self.p_corrupt and self.rng.random() < self.p_corrupt:
            out = out[:-1] + bytes([out[-1] ^ 0x5A])
        return out

    def raw(self) -> int:
        return int(round(self.pos + self.rng.uniform(-self.read_noise, self.read_noise))) % 4096

    def load(self) -> int:
        if not (self.powered and self.torque_on):
            return 0
        cap = self.torque_limit
        if self.pushing:
            mag = cap
        else:
            mag = min(cap, 30 + self.extra_load + cap * min(1.0, abs(self._acc_now) / A_MAX))
        return int(math.copysign(mag, self.vel if abs(self.vel) > 1 else (self.goal - self.pos) or 1.0))

    def _read(self, addr: int, n: int) -> bytes:
        mem = {}
        for a, b in ((sts.R_MIN_ANGLE, sts.u16(self.eeprom['min_angle'])),
                     (sts.R_MAX_ANGLE, sts.u16(self.eeprom['max_angle'])),
                     (sts.R_MODE, bytes([self.eeprom['mode']])),
                     (sts.R_ID, bytes([self.sid])),
                     (sts.R_TORQUE_ENABLE, bytes([1 if self.torque_on else 0])),
                     (sts.R_ACC, bytes([self.acc])),
                     (sts.R_GOAL_SPEED, sts.u16(self.goal_speed)),
                     (sts.R_TORQUE_LIMIT, sts.u16(self.torque_limit)),
                     (sts.R_PRESENT_POS, sts.u16(self.raw())),
                     (sts.R_PRESENT_SPEED, sts.sm16(int(round(self.vel if self.vel_meas is None else self.vel_meas)))),
                     (sts.R_PRESENT_LOAD, sts.sm16(self.load(), 10)),
                     (sts.R_PRESENT_VOLTAGE, bytes([120])),
                     (sts.R_PRESENT_TEMP, bytes([32])),
                     (sts.R_MOVING, bytes([1 if abs(self.vel) > 10 else 0]))):
            for k, byte in enumerate(b):
                mem[a + k] = byte
        return bytes(mem.get(addr + k, 0) for k in range(n))

    def _write(self, addr: int, data: bytes, t: float):
        self.writes += 1
        regs = {addr + k: data[k] for k in range(len(data))}
        if sts.R_ACC in regs:
            self.acc = regs[sts.R_ACC]
        if sts.R_GOAL_SPEED in regs and sts.R_GOAL_SPEED + 1 in regs:
            self.goal_speed = regs[sts.R_GOAL_SPEED] | (regs[sts.R_GOAL_SPEED + 1] << 8)
        if sts.R_TORQUE_LIMIT in regs and sts.R_TORQUE_LIMIT + 1 in regs:
            self.torque_limit = min(1000, regs[sts.R_TORQUE_LIMIT] | (regs[sts.R_TORQUE_LIMIT + 1] << 8))
        if sts.R_TORQUE_ENABLE in regs:
            on = regs[sts.R_TORQUE_ENABLE] == 1
            if on and not self.torque_on:
                self.goal = self.pos                      # enabling holds where it is
            self.torque_on = on
        if sts.R_GOAL_POS in regs and sts.R_GOAL_POS + 1 in regs:
            v = regs[sts.R_GOAL_POS] | (regs[sts.R_GOAL_POS + 1] << 8)
            if self.eeprom['mode'] == 3:
                rel = sts.from_sm(v)
                self.goal = (self.goal if self.ref == 'goal' else self.pos) + rel
            else:
                lo, hi = self.eeprom['min_angle'], self.eeprom['max_angle']
                g = sts.from_sm(v)
                if lo or hi:
                    g = min(max(g, lo), hi)
                self.goal = float(g)

    # ---------------------------------------------------------------- motion
    def v_max(self) -> float:
        return min(self.goal_speed or V_NO_LOAD, V_NO_LOAD) * self.load_factor

    def control(self, dt: float, pos: Optional[float] = None) -> float:
        """The servo's loop: the velocity it drives toward its goal, given its position (counts/s)."""
        if pos is not None:
            self.pos = pos
        if not (self.powered and self.torque_on):
            self.vel *= max(0.0, 1.0 - dt / 0.01)
            self._acc_now = 0.0
            return self.vel
        a = self.acc * 100.0 if self.acc else A_MAX
        e = self.goal - self.pos
        # time-optimal approach on 80 % of the deceleration it has (no overshoot), a half-count dead band at the goal
        v_des = 0.0 if abs(e) < 0.5 else math.copysign(min(self.v_max(), math.sqrt(1.6 * a * abs(e))), e)
        dv = max(-a * dt, min(a * dt, v_des - self.vel))
        self._acc_now = dv / dt if dt > 0 else 0.0
        self.vel += dv
        return self.vel

    def advance(self, dt: float):
        """Integrate its own position (the feed, the tilt), against any block."""
        self.control(dt)
        new = self.pos + self.vel * dt
        self.pushing = False
        if self.blocked_hi is not None and new > self.blocked_hi:
            new, self.vel, self.pushing = self.blocked_hi, 0.0, self.torque_on and self.goal > self.blocked_hi
        if self.blocked_lo is not None and new < self.blocked_lo:
            new, self.vel, self.pushing = self.blocked_lo, 0.0, self.torque_on and self.goal < self.blocked_lo
        self.pos = new


class SimBus:
    """Several simulated servos on one wire: a transaction goes to whichever answers."""

    def __init__(self, servos, t_fn):
        self.servos = {s.sid: s for s in servos}
        self.t = t_fn

    def txn(self, pkt: bytes) -> Optional[bytes]:
        p = sts.parse(pkt)
        if p is None:
            return None
        s = self.servos.get(p[0])
        return s.handle(pkt, self.t()) if s else None
