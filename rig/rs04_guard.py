"""The RS-04 configuration tool's safety rules, on every frame a host sends: what the bridge (rig/rs04_bridge.py) lets
through to a real bus. The browser tool runs the same rules in designer/kit/rs04/guard.js on every transport; both are
checked against the same scenarios in designer/kit/rs04/vectors.json (python -m rig.rs04_vectors).

    g = Guard(limits)                      # limits from a build profile (rig/rs04_profiles.py)
    g.observe(cid, data, ext)              # every frame the bus delivers
    ok, code, why = g.check(cid, data, ext)  # every frame a client asks to send; refused frames are not sent
    g.arm([1, 2]); g.disarm()

The rules (hardware/actuators/rs04/README.md has them for people):
  - Only the RS-04's own 29-bit frames; never the bit-rate or protocol changes (types 23 and 25).
  - A motor is enabled or sent motion (MIT frames) only after an explicit arm, and only if in this session it answered
    a get-id as an RS-04 and read back, within CONFIRM_S, run_mode 0 (MIT), limit_torque at or under the profile's jog
    torque and canTimeout on (1 .. the profile's maximum): a closed tab or a pulled lead then stops it.
  - MIT frames stay inside the profile's jog limits: |t_ff| <= jog torque, |v| <= jog speed, Kp and Kd under their caps.
  - No write puts limit_torque over the profile's cap or turns canTimeout off; no write selects a mode other than MIT
    or sets a current, speed or position command; nothing is written to, zeroed, renumbered or saved on an armed motor.
"""
from __future__ import annotations

import math
import time
from typing import Callable, Dict, Iterable, Optional, Set, Tuple

from rig import rs04 as P

CONFIRM_S = 10.0          # a read-back older than this does not allow an enable: re-read just before arming
COMMANDS = ('iq_ref', 'spd_ref', 'loc_ref')     # mode commands that would move a motor outside the MIT limits


class Guard:
    def __init__(self, limits: dict, clock: Callable[[], float] = time.monotonic):
        self.lim = dict(limits)
        self.clock = clock
        self.seen: Set[int] = set()                   # ids that answered a get-id this session
        self.armed: Set[int] = set()
        self.confirmed: Dict[int, Dict[str, Tuple[float, float]]] = {}   # motor -> name -> (value, when read)

    # ------------------------------------------------------------------ what the bus says
    def observe(self, cid: int, data: bytes, ext: bool = True) -> None:
        if not ext:
            return
        m = P.parse(cid, data)
        if isinstance(m, P.DeviceId):
            self.seen.add(m.motor)
        elif isinstance(m, P.ParamReply) and m.ok and m.index in P.BY_INDEX:
            name = P.BY_INDEX[m.index].name
            if name in ('run_mode', 'limit_torque', 'canTimeout'):
                self.confirmed.setdefault(m.motor, {})[name] = (float(m.value), self.clock())

    # ------------------------------------------------------------------ arming
    def arm(self, ids: Iterable[int]) -> Tuple[bool, str, str]:
        ids = list(ids)
        missing = [i for i in ids if i not in self.seen]
        if missing:
            return False, 'not-seen', f'motor {missing[0]} has not answered a scan in this session'
        self.armed.update(ids)
        return True, 'ok', ''

    def disarm(self, ids: Optional[Iterable[int]] = None) -> None:
        if ids is None:
            self.armed.clear()
        else:
            self.armed.difference_update(ids)

    def stop_targets(self) -> list:
        """Every motor a stop-all must reach: the ones seen, the armed ones and the factory id."""
        return sorted(self.seen | self.armed | {P.FACTORY_ID})

    def ready(self, motor: int) -> Tuple[bool, str, str]:
        """May this motor be enabled now? (ok, code, why)."""
        if motor not in self.seen:
            return False, 'not-seen', f'motor {motor} has not answered a scan in this session'
        if motor not in self.armed:
            return False, 'not-armed', f'motor {motor} is not armed: arm it first'
        c = self.confirmed.get(motor, {})
        now = self.clock()
        for name in ('run_mode', 'limit_torque', 'canTimeout'):
            if name not in c or now - c[name][1] > CONFIRM_S:
                return False, 'not-confirmed', f'motor {motor}: read {name} back just before arming'
        if c['run_mode'][0] != 0:
            return False, 'mode', f'motor {motor} is in run_mode {c["run_mode"][0]:g}: the tool runs MIT (0) only'
        if c['limit_torque'][0] > self.lim['jog_torque_nm'] + 1e-6:
            return False, 'jog-torque', (f'motor {motor} holds limit_torque {c["limit_torque"][0]:g} N m: over the '
                                         f'profile\'s jog torque {self.lim["jog_torque_nm"]:g} N m')
        to = c['canTimeout'][0]
        if to < 1 or to > self.lim['can_timeout_max_ticks']:
            return False, 'watchdog', f'motor {motor} has canTimeout {to:g}: it must be on (1..{self.lim["can_timeout_max_ticks"]})'
        return True, 'ok', ''

    # ------------------------------------------------------------------ what a client asks to send
    def check(self, cid: int, data: bytes, ext: bool = True) -> Tuple[bool, str, str]:
        if not ext:
            return False, 'not-rs04', 'only 29-bit RS-04 frames are sent'
        req = P.parse_request(cid, data)
        if req is None:
            return False, 'unknown', f'not an RS-04 request (type {P.id_fields(cid)[0]})'
        k, m = req.kind, req.motor
        if k in (P.SET_BAUD, P.SET_PROTOCOL):
            return False, 'forbidden', 'bit-rate and protocol changes are not sent by this tool'
        if k in (P.GET_ID, P.READ_PARAM, P.REPORT):
            return True, 'ok', ''
        if k == P.STOP:
            if req.fields.get('version') and m in self.armed:
                return False, 'armed', f'motor {m} is armed: disarm before reading the version'
            return True, 'ok', ''
        if k == P.ENABLE:
            return self.ready(m)
        if k == P.MIT:
            ok = self.ready(m)
            if not ok[0]:
                return ok
            f, lim = req.fields, self.lim
            if abs(f['t']) > lim['jog_torque_nm'] + 0.01:
                return False, 'jog-torque', f'feed-forward {f["t"]:.2f} N m is over the jog torque {lim["jog_torque_nm"]:g} N m'
            if abs(f['v']) > lim['jog_speed_rad_s'] + 0.01:
                return False, 'jog-speed', f'speed {f["v"]:.2f} rad/s is over the jog speed {lim["jog_speed_rad_s"]:g} rad/s'
            if f['kp'] > lim['jog_kp_max'] + 0.1 or f['kd'] > lim['jog_kd_max'] + 0.01:
                return False, 'jog-gain', f'Kp {f["kp"]:.1f} / Kd {f["kd"]:.2f} over the profile\'s {lim["jog_kp_max"]:g} / {lim["jog_kd_max"]:g}'
            return True, 'ok', ''
        if m in self.armed:
            return False, 'armed', f'motor {m} is armed: disarm before writing, zeroing, renumbering or saving'
        if k == P.SET_ID:
            new = req.fields['new_id']
            if new in self.seen and new != m:
                return False, 'id-taken', f'id {new} already answers on this bus'
            self.seen.discard(m)                  # it answers as `new` from now on (its id reply adds that)
            self.confirmed.pop(m, None)
            return True, 'ok', ''
        if k in (P.SET_ZERO, P.SAVE):
            return True, 'ok', ''
        if k == P.WRITE_PARAM:
            return self._write(m, req.fields['index'], req.fields['value'])
        return False, 'unknown', f'type {k} is not sent by this tool'

    def _write(self, motor: int, index: int, v) -> Tuple[bool, str, str]:
        p = P.BY_INDEX.get(index)
        if p is None:
            return False, 'unknown', f'parameter 0x{index:04X} is not in the RS-04 table'
        if not p.writable:
            return False, 'read-only', f'{p.name} is read-only'
        v = float(v)
        if not math.isfinite(v):
            return False, 'range', f'{p.name}: not a number'
        if p.lo is not None and v < p.lo - 1e-6 or p.hi is not None and v > p.hi + 1e-6:
            return False, 'range', f'{p.name} {v:g} is outside the manual\'s {p.lo}..{p.hi}'
        if p.name == 'limit_torque' and v > self.lim['limit_torque_nm'] + 1e-6:
            return False, 'cap', f'limit_torque {v:g} N m is over the profile\'s cap {self.lim["limit_torque_nm"]:g} N m'
        if p.name == 'canTimeout' and not 1 <= v <= self.lim['can_timeout_max_ticks']:
            return False, 'watchdog', f'canTimeout {v:g} would turn the watchdog off or past {self.lim["can_timeout_max_ticks"]} (the tool keeps it on)'
        if p.name == 'run_mode' and v != 0:
            return False, 'mode', 'the tool runs MIT mode (run_mode 0) only'
        if p.name in COMMANDS and v != 0:
            return False, 'command', f'{p.name} is a motion command: the tool moves motors only by its limited jog'
        if p.name in ('run_mode', 'limit_torque', 'canTimeout'):
            self.confirmed.get(motor, {}).pop(p.name, None)       # changed: read it back again before arming
        return True, 'ok', ''
