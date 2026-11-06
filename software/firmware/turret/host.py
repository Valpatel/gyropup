"""The turret's host bridge (docs/turret-firmware.md section 7, task N6): one Python host for the turret, on the
laptop through a USB-CAN adapter and on the Jetson through the J501's SocketCAN can1, built on bench_host.py's
protocol layer (its SimLink and CanLink, its Turret).

    .venv/bin/python firmware/turret/host.py --sim --mount robot                          # a dry run on sim_turret.py
    .venv/bin/python firmware/turret/host.py --sim --mount robot --script "pendant on; arm; aim 0 -10; fire 5"
    .venv/bin/python firmware/turret/host.py --can socketcan:can0 --mount bench           # the laptop (gs_usb as can0)
    .venv/bin/python firmware/turret/host.py --can socketcan:can1 --mount robot           # the Jetson (the J501's can1)
    .venv/bin/python firmware/turret/host.py --can socketcan:can1 --mount robot --jsonl   # a bridge for a page's backend

What it does:
  - sends the 10 Hz HOST_HEARTBEAT; its arm-request bit is high only while the user has asked to arm, and drops on
    any SAFE, FAULT or turret restart (nothing re-arms by itself: the user asks again);
  - sends the CONFIG rows for the mount in use (--mount bench | box | robot, no default) as soon as the turret has
    homed, and again whenever it restarts: the depression table (robot: exports/turret/lidar/lidar.json
    `firmware_table`, made for the body's lidar position; box: exports/turret/lidar/box.json; bench: an explicit
    full-range table), the keep-outs (box: box.json's `keep_out_fire_pan_deg`; bench: within 60 deg of straight back,
    where the operator stands; robot: none, the body's business; --keepout overrides), tyre 38, ring on, the launch
    ratio, and the throttle map once bench test 4.3 has written one (exports/turret/bench/speed_map.json; in --sim
    the simulated one in exports/turret/bench/sim/);
  - refuses to arm until those rows have gone out since the turret's last boot and its next heartbeat has come back
    without CONFIG_MISMATCH. The firmware reference echoes no CONFIG row, so that heartbeat, with the restart watch
    (the heartbeat's sequence and gaps, a BOOT state), is the acknowledgement it allows;
  - AIM, FIRE and LASER: the tilt never asked above level (nor below the mount's table), pan and tilt at most
    90 deg/s and at most 50 deg/s while "people near" is set; while it is set no FIRE goes out (a burst under way is
    stopped and its wheels spun down) and an aim under way is slowed;
  - logs every SHOT, FEED, POWER, HEALTH and EVENT frame, the turret's state changes, the CONFIG rows and the commands
    to exports/turret/bench/host-<UTC time>-<mount>.json on hardware, and in --sim to exports/turret/bench/sim/ (as
    bench_host.py: a simulated result never lands in exports/turret/bench/ itself).
The arm request is only a request: the safety line (the pendant on the bench, the body's STOP contact on the robot),
the firmware's own conditions and the hardware arm chain decide, and nothing here relaxes any of them.

Commands (the CLI, --script and `TurretHost.command()`): status | aim PAN [TILT [RATE]] | fire N [RATE [FPS]] |
laser on|off | near on|off (people near) | arm | disarm | stop | spindown | rehome | clear | config | wait S | quit;
in --sim also pendant on|off and load N (balls into the hopper). In --sim the simulated time runs only inside a
command ('wait S' runs it). --jsonl reads one JSON object a line ({"cmd": "aim", "pan": 10, "tilt": -5}) and answers
each with one JSON line: the cheap bridge for the game page's backend, which can also use `TurretHost` directly.
"""
from __future__ import annotations

import argparse
import datetime
import json
import shlex
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import can_msgs as M  # noqa: E402
import config as C  # noqa: E402
from bench_host import BENCH_OUT, SIM_OUT, CanLink, SimLink, Turret  # noqa: E402

R = HERE.parents[1]
LIDAR_JSON = R / 'exports' / 'turret' / 'lidar' / 'lidar.json'
BOX_JSON = R / 'exports' / 'turret' / 'lidar' / 'box.json'
RATE_CAP = min(C.AIM_RATE_CAP, C.PAN_SPEED_MAX)      # 90 deg/s: the pan servo's top through 3:1
PEOPLE_NEAR_RATE = 50.0                              # deg/s, pan and tilt, while people are near
BEHIND = [(120.0, 240.0)]                            # no fire within 60 deg of straight back, where the operator stands
BENCH_TABLE = [(float(p), C.TILT_MIN_DEG) for p in range(-180, 180, 30)]   # explicit: the full range at every pan
SPINNING = ('SPIN_UP', 'READY', 'FIRING')
CONFIGURABLE = ('IDLE', 'ARMED', 'FAULT')           # the host sends CONFIG only here (the firmware drops it while spinning)
EV_NAMES = {v: k[3:].lower() for k, v in vars(M).items() if k.startswith('EV_') and isinstance(v, int)}
BURST_WHY = {v: k for k, v in M.BURST_END.items()}
REFUSED_WHY = {100: 'the feed was not parked', 200: 'the pan was in a keep-out sector'}
CF_NAMES = {M.CF_DEPRESSION: 'depression', M.CF_KEEPOUT: 'keep-out', M.CF_TYRE: 'tyre', M.CF_RING: 'ring',
            M.CF_MOUNT: 'mount', M.CF_LAUNCH_RATIO: 'launch ratio', M.CF_THROTTLE_MAP: 'throttle map', M.CF_CLEAR: 'clear'}


class HostError(Exception):
    pass


def wrap(d: float) -> float:
    return (d + 180.0) % 360.0 - 180.0


def _read(path: Path):
    try:
        return json.loads(path.read_text()) if path.exists() else None
    except (OSError, ValueError):
        return None


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(R))
    except ValueError:
        return str(path)


def sectors(pans: Iterable[float], step: float = 2.0) -> List[Tuple[float, float]]:
    """Sampled pans (deg) as closed sectors (from, to) mod 360, neighbours up to `step` apart merged, a sector through
    0 as (from, to) with from > to (as the firmware's keep-out test reads it)."""
    ps = sorted({round(p % 360.0, 6) for p in pans})
    if not ps:
        return []
    groups = [[ps[0], ps[0]]]
    for p in ps[1:]:
        if p - groups[-1][1] <= step + 1e-6:
            groups[-1][1] = p
        else:
            groups.append([p, p])
    if len(groups) > 1 and groups[0][0] <= 1e-6 and 360.0 - groups[-1][1] <= step + 1e-6:
        groups[-1][1] = groups.pop(0)[1]
    return [(a, b) for a, b in groups]


def parse_keepouts(text: Optional[str]) -> Optional[List[Tuple[float, float]]]:
    """--keepout: None keeps the mount's own, 'none' clears them, 'FROM:TO[,FROM:TO]' (deg, mod 360) replaces them."""
    if text is None:
        return None
    if text.strip().lower() == 'none':
        return []
    out = []
    for part in text.split(','):
        a, _, b = part.partition(':')
        out.append((float(a), float(b)))
    return out


def table_rows(path: Path) -> Optional[List[Tuple[float, float]]]:
    d = _read(path)
    try:
        return [(float(r['pan_deg']), float(r['min_tilt_deg'])) for r in d['firmware_table']] if d else None
    except (KeyError, TypeError, ValueError):
        return None


def same_table(a, b, step: float = 0.5) -> bool:
    """Two depression tables that clamp alike at every pan (the firmware's interpolation, every `step` deg)."""
    ca, cb = C.Config(depression=list(a)), C.Config(depression=list(b))
    return all(abs(ca.min_tilt(k * step) - cb.min_tilt(k * step)) < 1e-9 for k in range(int(-180 / step), int(180 / step) + 1))


def throttle_map(sim: bool) -> Tuple[List[Tuple[int, int]], str]:
    """The throttle map's rows (permille, rpm) from bench test 4.3, if it has run and passed: the bench's own reading
    on hardware, the simulated one in --sim (never one for the other)."""
    f = (SIM_OUT if sim else BENCH_OUT) / 'speed_map.json'
    d = _read(f)
    if not d:
        return [], f'none: bench test 4.3 has not written {_rel(f)} yet (the firmware\'s no-load model)'
    if d.get('mode') != ('sim' if sim else 'bench') or not d.get('pass'):
        return [], f'{_rel(f)} not loaded: mode {d.get("mode")}, pass {d.get("pass")}'
    rows = [(int(r['throttle_permille']), int(r['rpm'])) for r in d.get('readings', {}).get('config_throttle_map_rows', [])
            if r.get('rpm') and 0 < int(r['throttle_permille']) <= 1000]
    return rows, _rel(f) + ' (bench test 4.3)'


def mount_setup(mount: str, sim: bool, keepouts: Optional[List[Tuple[float, float]]] = None) -> dict:
    """The CONFIG rows for a mount, with where each part comes from."""
    if mount not in M.MOUNTS:
        raise HostError(f'unknown mount {mount!r}: {", ".join(M.MOUNTS)}')
    notes = []
    if mount == 'robot':
        table = table_rows(LIDAR_JSON)
        if table:
            src = f'{_rel(LIDAR_JSON)} firmware_table'
            lid = (_read(LIDAR_JSON) or {}).get('lidar', {})
            if lid:
                src += f" (the VLP-16 {lid.get('centre_x_mm')} mm ahead of the pan axis, its top {lid.get('top_above_tm_mm')} mm above the TM face)"
            if not same_table(table, C.ROBOT_DEPRESSION):
                notes.append('lidar.json\'s table differs from the firmware\'s built-in robot default (config.ROBOT_DEPRESSION): '
                             'the file is loaded; the default wants updating')
        else:
            table, src = list(C.ROBOT_DEPRESSION), f'firmware/turret/config.py ROBOT_DEPRESSION ({_rel(LIDAR_JSON)} not found)'
            notes.append(src)
        ko = sectors((_read(LIDAR_JSON) or {}).get('keep_out_fire_pan_deg') or [])
        ko_src = 'none: on the robot the keep-outs are the body\'s business (lidar.json keep_out_fire_pan_deg)'
    elif mount == 'box':
        d = _read(BOX_JSON)
        table = table_rows(BOX_JSON)
        if not table:
            raise HostError(f'no depression table for the box: {_rel(BOX_JSON)} (cad/turret_lidar.py --scene box)')
        src = f'{_rel(BOX_JSON)} firmware_table'
        ko, ko_src = sectors(d.get('keep_out_fire_pan_deg') or []), f'{_rel(BOX_JSON)} keep_out_fire_pan_deg'
    else:
        table, src = list(BENCH_TABLE), 'explicit: the full range (-25 deg) at every pan'
        ko, ko_src = list(BEHIND), 'within 60 deg of straight back, where the operator stands (as on the box)'
    if keepouts is not None:
        ko, ko_src = list(keepouts), '--keepout'
    tmap, tmap_src = throttle_map(sim)
    rows = [(M.CF_CLEAR, 0, 1, 0), (M.CF_CLEAR, 0, 2, 0), (M.CF_CLEAR, 0, 3, 0),
            (M.CF_TYRE, 0, C.TYRE_DESIGN_MM, 0), (M.CF_RING, 0, 1 if C.CONTINUOUS_PAN else 0, 0), (M.CF_MOUNT, 0, M.MOUNTS.index(mount), 0),
            (M.CF_LAUNCH_RATIO, 0, round(C.LAUNCH_RATIO * 10000), 0)]
    rows += [(M.CF_DEPRESSION, i, round(p * 10), round(m * 100)) for i, (p, m) in enumerate(table)]
    rows += [(M.CF_KEEPOUT, i, round(a * 10), round(b * 10)) for i, (a, b) in enumerate(ko)]
    rows += [(M.CF_THROTTLE_MAP, 0, t, r) for t, r in tmap]
    if len(table) > 255 or len(ko) > 255:
        raise HostError('a CONFIG table has more rows than its u8 index carries')
    return {'mount': mount, 'rows': rows, 'table': table, 'keepouts': ko, 'throttle_map': tmap,
            'sources': {'depression': src, 'keepouts': ko_src, 'throttle_map': tmap_src, 'tyre_mm': C.TYRE_DESIGN_MM,
                        'ring': C.CONTINUOUS_PAN, 'launch_ratio': round(C.LAUNCH_RATIO, 4)},
            'notes': notes}


# ===================================================================================== the log
class HostLog:
    """Everything the host saw and did, saved as one JSON file a session (rotated past ROWS_MAX rows)."""
    FIELDS = {'shots': ('t', 'shot', 'fps', 'rpm', 'flags'), 'feed': ('t', 'balls', 'empty', 'jams', 'flags', 'dial_deg'),
              'power': ('t', 'bus_v', 'pan_v', 'tilt_v', 'feed_v'),
              'health': ('t', 'tec', 'rec', 'busoff', 'ring_drops', 'servo_errors', 'index_worst_deg'),
              'events': ('t', 'event', 'seq', 'a', 'b', 'c'), 'states': ('t', 'state', 'faults'),
              'commands': ('t', 'command', 'detail'), 'notes': ('t', 'note')}
    ROWS_MAX = 100_000

    def __init__(self, folder: Optional[Path], head: dict):
        self.folder, self.head = folder, head
        self.path: Optional[Path] = None
        self.saved: List[Path] = []
        self.config: List[dict] = []                     # the CONFIG rows as sent (kept across a rotation)
        self._new()

    def _new(self):
        self.started = datetime.datetime.now(datetime.timezone.utc)
        self.rows = {k: [] for k in self.FIELDS}
        stamp = self.started.strftime('%Y%m%d-%H%M%S') + (f'-{len(self.saved)}' if self.saved else '')
        self.path = (self.folder / f"host-{stamp}-{self.head.get('mount')}.json" if self.folder else None)

    def add(self, kind: str, row: list):
        self.rows[kind].append(row)

    def save(self) -> Optional[Path]:
        if self.path is None:
            return None
        out = dict(self.head, started_utc=self.started.isoformat(timespec='seconds'), config_rows=self.config,
                   counts={k: len(v) for k, v in self.rows.items()},
                   **{k: {'fields': list(self.FIELDS[k]), 'rows': v} for k, v in self.rows.items()})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(out, default=str) + '\n')
        tmp.replace(self.path)
        if self.path not in self.saved:
            self.saved.append(self.path)
        if sum(len(v) for v in self.rows.values()) > self.ROWS_MAX:
            self._new()
        return self.path


class _Tee:
    """The link, with every frame the host receives also handed to the host (its log and its watch)."""

    def __init__(self, link, sink: Callable):
        self._link, self._sink = link, sink

    def __getattr__(self, k):
        return getattr(self._link, k)

    def poll(self):
        out = self._link.poll()
        for tf, cid, data in out:
            if cid in M.MSGS:
                self._sink(tf, *M.unpack(cid, data))
        return out


# ===================================================================================== the host
class TurretHost:
    """The turret's host, as an API: start(), status(), aim(), fire(), laser(), set_people_near(), arm(), disarm(),
    stop(), load_config(), close(); command(text) and call(obj) for the CLI and the JSON-lines bridge. Every method
    answers a dict ({'ok': bool, ...}; a refusal says why). Thread-safe: one lock around the turret's state; on
    hardware a pump thread reads the bus while the caller waits, in --sim the caller's waits run the simulation."""

    def __init__(self, link, mount: str, log_dir: Optional[Path] = None, keepouts: Optional[List[Tuple[float, float]]] = None,
                 auto_config: bool = True, log: bool = True, link_name: str = ''):
        self.sim = isinstance(link, SimLink)
        self.rig = link.rig if self.sim else None
        self.mount = mount
        self.setup = mount_setup(mount, self.sim, keepouts)
        self.cfg = C.Config(tyre_mm=C.TYRE_DESIGN_MM, mount=mount, depression=list(self.setup['table']), keepouts=list(self.setup['keepouts']))
        folder = Path(log_dir) if log_dir else (SIM_OUT if self.sim else BENCH_OUT)
        if self.sim and folder.resolve() == BENCH_OUT.resolve():
            raise HostError('a simulated log never goes to exports/turret/bench/ itself (use exports/turret/bench/sim/)')
        head = {'what': 'the turret host\'s log (firmware/turret/host.py)', 'mode': 'sim' if self.sim else 'hardware',
                'mount': mount, 'link': link_name or ('sim_turret.py' if self.sim else 'python-can'),
                'setup': {k: self.setup[k] for k in ('sources', 'notes', 'table', 'keepouts', 'throttle_map')}}
        if self.sim:
            head['warning'] = 'simulated turret (firmware/turret/sim_turret.py): not a bench reading'
        self.log = HostLog(folder if log else None, head)
        self.lock = threading.RLock()
        self.people_near = False
        self.auto_config = auto_config
        self.cfg_state, self.cfg_sent_t, self.cfg_sends = 'none', None, 0
        self.goal: Optional[Tuple[float, float]] = None
        self.goal_rate = RATE_CAP
        self._nudge = 0.05
        self.req = 0
        self.laser_on = False
        self.last_burst: Optional[dict] = None
        self._hb_last: Optional[Tuple[float, int]] = None
        self._state: Optional[str] = None
        self._closed = False
        self._save_t = 0.0
        self.link = _Tee(link, self._frame)
        self.tt = Turret(self.link)
        self._pump_thread = None
        if not self.sim:
            self._pump_thread = threading.Thread(target=self._pump_loop, daemon=True)
            self._pump_thread.start()

    # ---------------------------------------------------------------- time and the bus
    def now(self) -> float:
        return self.tt.now()

    def _pump(self):
        with self.lock:
            self.tt.pump()
            self._service()

    def _pump_loop(self):
        while not self._closed:
            self._pump()
            time.sleep(0.01)

    def _step(self, dt: float):
        if self.sim:
            self.link.sleep(dt)                    # the simulated turret runs dt
            self._pump()
        else:
            time.sleep(dt)                         # the pump thread reads the bus meanwhile

    def wait(self, s: float):
        end = self.now() + s
        while self.now() < end - 1e-9:
            self._step(min(0.01, end - self.now()))

    def wait_for(self, pred: Callable[[], bool], timeout: float) -> bool:
        end = self.now() + timeout
        while True:
            with self.lock:
                if pred():
                    return True
            if self.now() >= end:
                return False
            self._step(0.01)

    # ---------------------------------------------------------------- what the turret says
    def _frame(self, tf: float, name: str, f: dict):
        """Every frame received (inside the pump, the lock held): the log, the restart watch, the CONFIG check."""
        L = self.log
        if name == 'TURRET_HEARTBEAT':
            st = M.STATES[f['state']] if f['state'] < len(M.STATES) else str(f['state'])
            if self._hb_last is not None:
                t0, s0 = self._hb_last
                why = (f'no heartbeat for {tf - t0:.2f} s' if tf - t0 > 0.5 else
                       f'heartbeat sequence {f["seq"]} after {s0}' if f['seq'] != (s0 + 1) & 0xFF else
                       'the turret is in BOOT' if st == 'BOOT' and self._state != 'BOOT' else None)
                if why:
                    self._restarted(tf, why)
            self._hb_last = (tf, f['seq'])
            if st != self._state:
                L.add('states', [round(tf, 3), st, self._fault_names(f['faults'])])
                self._state = st
            if self.cfg_state == 'sent' and tf > self.cfg_sent_t + 0.05:
                bad = bool(f['faults'] & M.F_CONFIG_MISMATCH)
                self.cfg_state = 'refused' if bad else 'loaded'
                L.add('notes', [round(tf, 3), 'CONFIG refused: it does not match the build (CONFIG_MISMATCH)' if bad else
                                f'CONFIG for mount {self.mount} acknowledged: the heartbeat after its rows has no CONFIG_MISMATCH'])
            if self.tt.arm_req and st in ('SAFE', 'FAULT'):
                self.tt.arm_req = False
                L.add('notes', [round(tf, 3), f'arm request dropped: the turret went {st} ({", ".join(self._fault_names(f["faults"])) or "no fault bits"})'])
        elif name == 'SHOT':
            L.add('shots', [round(tf, 3), f['shot'], f['fps_d'] / 10.0, f['rpm'], f['flags']])
        elif name == 'FEED':
            L.add('feed', [round(tf, 3), f['balls'], f['empty'], f['jams'], f['flags'], round(f['dial'] * 360.0 / 256.0, 1)])
        elif name == 'POWER':
            L.add('power', [round(tf, 3), f['bus_mv'] / 1000.0, f['pan_dv'] / 10.0, f['tilt_dv'] / 10.0, f['feed_dv'] / 10.0])
        elif name == 'HEALTH':
            L.add('health', [round(tf, 3), f['tec'], f['rec'], f['busoff'], f['ring_drops'], f['servo_err'], f['index_worst'] / 100.0])
        elif name == 'EVENT':
            L.add('events', [round(tf, 3), EV_NAMES.get(f['code'], f['code']), f['seq'], f['a'], f['b'], f['c']])
            if f['code'] == M.EV_BURST_DONE:
                self.last_burst = {'t': round(tf, 3), 'balls': f['a'], 'steps': f['b'], 'end': BURST_WHY.get(f['c'], f['c'])}

    def _restarted(self, tf: float, why: str):
        if self.cfg_state != 'none':
            self.cfg_state = 'stale'
        self.tt.arm_req = False
        self.log.add('notes', [round(tf, 3), f'turret restart assumed ({why}): its CONFIG is sent again once it has homed; '
                                             f'the arm request is down until asked again'])

    def _service(self):
        """After each pump (the lock held): the CONFIG when it is due, the turret wrapper's lists trimmed, the log saved."""
        if self.auto_config and self.cfg_state in ('none', 'stale') and self._configurable():
            self._send_config('the turret has homed' if self.cfg_sends == 0 else 'again, after the turret restarted')
        tt = self.tt
        for lst in (tt.events, tt.shots):
            if len(lst) > 20_000:
                del lst[:10_000]
        if not self.sim and self.now() - self._save_t > 10.0:
            self._save_t = self.now()
            self.log.save()

    def _configurable(self) -> bool:
        return bool(self.tt.hb) and self.tt.homed() and self.tt.state() in CONFIGURABLE

    def _send_config(self, why: str):
        rows = self.setup['rows']
        for k, (kind, i, a, b) in enumerate(rows):
            self.tt.config(kind, i, a, b)
            if not self.sim and k % 8 == 7:
                time.sleep(0.002)                  # at most ~4 frames a millisecond into the Feather's receive FIFO
        self.cfg_state, self.cfg_sent_t = 'sent', self.now()
        self.cfg_sends += 1
        if not self.log.config:
            self.log.config = [{'kind': CF_NAMES.get(k, k), 'index': i, 'a': a, 'b': b} for k, i, a, b in rows]
        self.log.add('notes', [round(self.now(), 3), f'CONFIG sent for mount {self.mount} ({len(rows)} rows): {why}'])

    @staticmethod
    def _fault_names(bits: int) -> List[str]:
        return [n for k, n in M.FAULT_NAMES.items() if bits & k]

    def _cmd_log(self, command: str, detail):
        self.log.add('commands', [round(self.now(), 3), command, detail])

    # ---------------------------------------------------------------- state
    @property
    def table_loaded(self) -> bool:
        return self.cfg_state == 'loaded'

    def rate_cap(self) -> float:
        return PEOPLE_NEAR_RATE if self.people_near else RATE_CAP

    def _reached(self) -> bool:
        tt = self.tt
        if self.goal is None or tt.pan() is None or tt.tilt() is None:
            return False
        return abs(self.goal[0] - tt.pan()) <= C.AIM_TOL_DEG and abs(self.goal[1] - tt.tilt()) <= C.AIM_TOL_DEG

    def status(self) -> dict:
        with self.lock:
            tt = self.tt
            hb, w, fd, pw = tt.hb, tt.wheels, tt.feedmsg, tt.power
            fl = tt.flags()
            return {'ok': True, 't': round(self.now(), 2), 'mount': self.mount, 'state': tt.state(),
                    'faults': self._fault_names(tt.faults()) if hb else [],
                    'arm_line': bool(fl & M.H_ARM), 'homed': bool(fl & M.H_HOMED), 'armed': bool(fl & M.H_HOST_ARMED),
                    'wheels_ready': bool(fl & M.H_WHEELS_READY), 'trip': bool(fl & M.H_TRIP),
                    'pan': tt.pan(), 'tilt': tt.tilt(), 'pan_rate': tt.pose.get('pan_rate') if tt.pose else None,
                    'goal': [round(g, 2) for g in self.goal] if self.goal else None, 'rate_cap': self.rate_cap(),
                    'wheels_rpm': [w.get('rpm_l'), w.get('rpm_r')] if w else None,
                    'balls_fired': fd.get('balls') if fd else None, 'feed_jams': fd.get('jams') if fd else None,
                    'bus_v': pw.get('bus_mv', 0) / 1000.0 if pw else None,
                    'config': self.cfg_state, 'table_loaded': self.table_loaded, 'people_near': self.people_near,
                    'arm_request': tt.arm_req, 'laser': self.laser_on, 'shots_logged': len(self.log.rows['shots']),
                    'last_burst': self.last_burst, 'heartbeat': bool(hb)}

    # ---------------------------------------------------------------- start, config, arm
    def start(self, timeout: float = 30.0) -> dict:
        """Wait for the turret's heartbeat and its homing, then (auto_config) for its CONFIG to be acknowledged."""
        ok = self.wait_for(lambda: self._configurable(), timeout)
        if ok and self.auto_config:
            ok = self.wait_for(lambda: self.cfg_state in ('loaded', 'refused'), 3.0) and self.table_loaded
        return dict(self.status(), ok=ok)

    def load_config(self, timeout: float = 3.0) -> dict:
        """Send the mount's CONFIG rows now and wait for the acknowledgement."""
        with self.lock:
            st = self.tt.state()
            if st not in CONFIGURABLE or not self.tt.homed():
                return {'ok': False, 'refused': f'the turret is {st}{"" if self.tt.homed() else ", not homed"}: CONFIG waits'}
            self._send_config('asked')
            self._cmd_log('config', {'rows': len(self.setup['rows'])})
        ok = self.wait_for(lambda: self.cfg_state in ('loaded', 'refused'), timeout) and self.table_loaded
        return {'ok': ok, 'config': self.cfg_state, 'rows': len(self.setup['rows']), 'sources': self.setup['sources'],
                'notes': self.setup['notes']}

    def arm(self, timeout: float = 5.0) -> dict:
        """Ask the turret to arm: the request goes low for 0.3 s (the firmware's re-arm), then high until disarm()."""
        with self.lock:
            tt = self.tt
            st = tt.state()
            why = None
            if not self.table_loaded:
                why = f'the mount\'s table is not loaded in the turret (CONFIG {self.cfg_state})'
            elif st == 'ARMED' or st in SPINNING:
                return {'ok': True, 'state': st, 'note': 'already armed'}
            elif st != 'IDLE':
                why = f'the turret is {st}' + (f' ({", ".join(self._fault_names(tt.faults()))})' if tt.faults() else '')
            elif not tt.flags() & M.H_ARM:
                why = 'the safety line is not held (ARM low): hold the pendant, or close the robot\'s STOP contact'
            self._cmd_log('arm', why or 'asked')
            if why:
                return {'ok': False, 'refused': why}
            tt.arm_req = False
        self.wait(0.3)
        with self.lock:
            self.tt.arm_req = True
        ok = self.wait_for(lambda: self.tt.state() == 'ARMED', timeout)
        if not ok:
            with self.lock:
                self.tt.arm_req = False
                return {'ok': False, 'refused': f'the turret did not arm: {self.tt.state()} '
                                                f'({", ".join(self._fault_names(self.tt.faults())) or "no fault bits"})'}
        self.wait(0.8)                            # the ESCs arm on 0.6 s of zero throttle; the feed servo comes back
        return {'ok': True, 'state': self.tt.state()}

    def disarm(self) -> dict:
        with self.lock:
            self.tt.arm_req = False
            self._cmd_log('disarm', None)
        ok = self.wait_for(lambda: self.tt.state() in ('IDLE', 'FAULT', 'SAFE'), 3.0)
        return {'ok': ok, 'state': self.tt.state()}

    # ---------------------------------------------------------------- aim, fire, laser, people near
    def aim(self, pan: float, tilt: float = 0.0, rate: Optional[float] = None, wait: bool = False,
            timeout: Optional[float] = None, absolute: bool = False) -> dict:
        """Aim at `pan` (deg; the nearest turn of it unless `absolute`) and `tilt` (deg, never above level: clamped to
        [the mount's table at that pan, 0]), at `rate` deg/s capped at 90, or 50 while people are near."""
        with self.lock:
            tt = self.tt
            cur = tt.pan()
            goal = float(pan) if absolute or cur is None else cur + wrap(float(pan) - cur)
            want = float(tilt)
            t_goal = min(C.TILT_MAX_DEG, max(C.TILT_MIN_DEG, self.cfg.min_tilt(goal), want))
            cap = self.rate_cap()
            r = cap if rate is None else max(1.0, min(float(rate), cap))
            self.goal, self.goal_rate = (goal, t_goal), r
            tt.aim(goal, t_goal, r)
            self._cmd_log('aim', {'pan': round(goal, 2), 'tilt': t_goal, 'rate': r})
            dist = abs(goal - cur) if cur is not None else 360.0
        out = {'ok': True, 'pan_goal': round(goal, 2), 'tilt_goal': t_goal, 'rate': r}
        if t_goal != want:
            out['tilt_clamped_from'] = want
        if wait:
            out['reached'] = self.wait_for(self._reached, timeout or dist / r + 2.5)
            out.update(pan=self.tt.pan(), tilt=self.tt.tilt())
        return out

    def _fire_refusal(self) -> Optional[str]:
        tt = self.tt
        st = tt.state()
        if self.people_near:
            return 'people near: fire is held'
        if not self.table_loaded:
            return f'the mount\'s table is not loaded in the turret (CONFIG {self.cfg_state})'
        if st in ('SPIN_UP', 'FIRING'):
            return 'a burst is under way'
        if st not in ('ARMED', 'READY'):
            return f'not armed (the turret is {st})'
        if self.cfg.in_keepout(tt.pan() or 0.0):
            return 'the pan is in a keep-out sector'
        return None

    def fire(self, balls: int, rate: float = C.RATE_DEFAULT, fps: float = 0.0, wait: bool = False,
             timeout: Optional[float] = None) -> dict:
        """A burst of `balls` at `rate` per second (at most 3) and `fps` (0: the default 52; held to 40-56)."""
        with self.lock:
            why = self._fire_refusal()
            self._cmd_log('fire', {'balls': balls, 'rate': rate, 'fps': fps, 'refused': why})
            if why:
                return {'ok': False, 'refused': why}
            n = max(1, min(255, int(balls)))
            r = max(0.1, min(C.RATE_MAX, float(rate)))
            v = 0.0 if not fps else min(C.SET_FPS_MAX, max(C.SET_FPS_MIN, float(fps)))
            self.req = self.req % 255 + 1
            req, t0 = self.req, self.now()
            self.tt.fire(n, r, v, req=req)
        out = {'ok': True, 'req': req, 'balls': n, 'rate': r, 'fps': v or C.SET_FPS_DEFAULT[C.TYRE_DESIGN_MM]}
        if wait:
            done = lambda: bool(self.tt.ev(M.EV_BURST_DONE, t0)) or any(f['a'] == req for _, f in self.tt.ev(M.EV_SHOT_REFUSED, t0))
            self.wait_for(done, timeout or n / 1.5 + 8.0)
            # the heartbeat (10 Hz) follows the burst's end event by up to 100 ms: wait for it, so the state is current
            with self.lock:
                t_end = max([t for t, _f in self.tt.ev(M.EV_BURST_DONE, t0)] or [self.now()])
            self.wait_for(lambda: self.tt.hb.get('t', -1.0) > t_end, 0.3)
            with self.lock:
                refused = [f for _, f in self.tt.ev(M.EV_SHOT_REFUSED, t0) if f['a'] == req]
                burst = self.tt.ev(M.EV_BURST_DONE, t0)
                shots = [f for _, f in self.tt.shots_since(t0) if not f['flags'] & M.S_STRAY]
            if refused:
                b = refused[0]['b']
                why = REFUSED_WHY.get(b) or f'it was {M.STATES[b] if b < len(M.STATES) else b}'
                return {'ok': False, 'req': req, 'refused': 'by the turret: ' + why}
            out.update(done=bool(burst), shots=len(shots), fps=[s['fps_d'] / 10.0 for s in shots],
                       end=BURST_WHY.get(burst[-1][1]['c']) if burst else None)
            out['ok'] = bool(burst)
        return out

    def laser(self, on: bool) -> dict:
        with self.lock:
            self.tt.laser(bool(on))
            self.laser_on = bool(on)
            self._cmd_log('laser', bool(on))
        return {'ok': True, 'laser': bool(on)}

    def set_people_near(self, on: bool) -> dict:
        """People near (from the body's lidar and cameras, or the page): fire is held and pan and tilt drop to 50 deg/s.
        Setting it stops a burst under way and spins its wheels down, and slows an aim under way."""
        acted = []
        with self.lock:
            tt = self.tt
            self.people_near = bool(on)
            if on:
                st = tt.state()
                if st in SPINNING:
                    tt.cmd(M.CMD_SPIN_DOWN)
                    acted.append('the wheels spun down' if st == 'READY' else 'the burst stopped and its wheels spun down')
                if self.goal is not None and not self._reached() and self.goal_rate > PEOPLE_NEAR_RATE:
                    # the firmware takes a new rate with a new goal: the same goal, nudged 0.05 deg, at 50 deg/s
                    self._nudge = -self._nudge
                    g = (self.goal[0] + self._nudge, self.goal[1])
                    self.goal, self.goal_rate = g, PEOPLE_NEAR_RATE
                    tt.aim(g[0], g[1], PEOPLE_NEAR_RATE)
                    acted.append('the aim under way slowed to 50 deg/s')
            self._cmd_log('people_near', {'on': bool(on), 'acted': acted})
        return {'ok': True, 'people_near': bool(on), 'rate_cap': self.rate_cap(), 'acted': acted}

    def stop(self) -> dict:
        with self.lock:
            self.tt.cmd(M.CMD_STOP)
            self._cmd_log('stop', None)
        return {'ok': True}

    def spin_down(self) -> dict:
        with self.lock:
            self.tt.cmd(M.CMD_SPIN_DOWN)
            self._cmd_log('spindown', None)
        return {'ok': True}

    def rehome(self) -> dict:
        with self.lock:
            if self.people_near:
                return {'ok': False, 'refused': 'people near: homing sweeps at 60 deg/s'}
            if self.tt.state() not in ('IDLE', 'FAULT'):
                return {'ok': False, 'refused': f'the turret is {self.tt.state()}: re-home from IDLE or FAULT'}
            self.tt.cmd(M.CMD_REHOME)
            self._cmd_log('rehome', None)
        return {'ok': True}

    def clear_faults(self) -> dict:
        with self.lock:
            self.tt.cmd(M.CMD_CLEAR_FAULTS)              # the firmware clears only with the safety line released
            self._cmd_log('clear', None)
        return {'ok': True}

    # ---------------------------------------------------------------- the simulated bench (--sim only)
    def sim_pendant(self, held: bool) -> dict:
        if not self.sim:
            return {'ok': False, 'refused': 'the pendant is the operator\'s on hardware'}
        with self.lock:
            self.rig.hw.set_pendant(bool(held))
            self._cmd_log('pendant', bool(held))
        self.wait(0.1)
        return {'ok': True, 'pendant': bool(held), 'arm_line': bool(self.tt.flags() & M.H_ARM)}

    def sim_load(self, n: int) -> dict:
        if not self.sim:
            return {'ok': False, 'refused': 'load the hopper by hand on hardware'}
        with self.lock:
            self.rig.hw.hopper = int(n)
            self._cmd_log('load', int(n))
        return {'ok': True, 'hopper': int(n)}

    # ---------------------------------------------------------------- the CLI and the JSON-lines bridge
    def command(self, text: str) -> dict:
        """One CLI command (see the module's docstring)."""
        w = shlex.split(text.strip())
        if not w:
            return {'ok': True}
        c, args = w[0].lower(), w[1:]
        on = lambda: bool(args) and args[0].lower() in ('on', '1', 'yes', 'true', 'held', 'hold')
        f = lambda k, d=None: float(args[k]) if len(args) > k else d
        try:
            if c == 'status':
                return self.status()
            if c == 'aim':
                return self.aim(f(0), f(1, 0.0), f(2), wait=True)
            if c == 'fire':
                return self.fire(int(f(0, 1)), f(1, C.RATE_DEFAULT), f(2, 0.0), wait=True)
            if c == 'laser':
                return self.laser(on())
            if c in ('near', 'people'):
                return self.set_people_near(on())
            if c == 'arm':
                return self.arm()
            if c == 'disarm':
                return self.disarm()
            if c == 'stop':
                return self.stop()
            if c == 'spindown':
                return self.spin_down()
            if c == 'rehome':
                return self.rehome()
            if c == 'clear':
                return self.clear_faults()
            if c == 'config':
                return self.load_config()
            if c == 'wait':
                self.wait(f(0, 1.0))
                return self.status()
            if c == 'pendant':
                return self.sim_pendant(on())
            if c == 'load':
                return self.sim_load(int(f(0, 30)))
        except (TypeError, ValueError, IndexError) as e:
            return {'ok': False, 'error': f'{c}: {e} (see the commands in host.py\'s docstring)'}
        return {'ok': False, 'error': f'unknown command {c!r}'}

    def call(self, obj: dict) -> dict:
        """One JSON-lines request: {"cmd": ..., named arguments}."""
        c = str(obj.get('cmd', '')).lower()
        g = obj.get
        try:
            if c == 'aim':
                return self.aim(float(g('pan')), float(g('tilt', 0.0)), g('rate'), wait=bool(g('wait', False)))
            if c == 'fire':
                return self.fire(int(g('balls', 1)), float(g('rate', C.RATE_DEFAULT)), float(g('fps', 0.0)), wait=bool(g('wait', False)))
            if c == 'laser':
                return self.laser(bool(g('on')))
            if c in ('near', 'people_near'):
                return self.set_people_near(bool(g('on')))
            if c == 'pendant':
                return self.sim_pendant(bool(g('on')))
            if c == 'load':
                return self.sim_load(int(g('balls', 30)))
            if c == 'wait':
                self.wait(float(g('s', 1.0)))
                return self.status()
            if c == 'quit':
                return {'ok': True, 'bye': True}
        except (TypeError, ValueError) as e:
            return {'ok': False, 'error': f'{c}: {e}'}
        return self.command(c)

    def close(self) -> Optional[Path]:
        """The arm request down (the turret disarms to IDLE rather than going SAFE on a stale heartbeat), the threads
        stopped, the log saved. Returns the log's path."""
        if self._closed:
            return self.log.path
        with self.lock:
            self.tt.arm_req = False
        self.wait(0.3)
        self._closed = True
        if not self.sim:
            if self._pump_thread is not None:
                self._pump_thread.join(timeout=1.0)
            can_link = self.link._link
            can_link.stop = True                           # ends CanLink's receive and heartbeat threads
            time.sleep(0.15)
            try:
                can_link.bus.shutdown()
            except Exception:  # noqa: BLE001 - the bus may already be gone
                pass
        with self.lock:
            return self.log.save()


def fmt(res: dict) -> str:
    """A result as one line for the terminal."""
    if not res.get('ok', False):
        return 'REFUSED: ' + str(res.get('refused') or res.get('error') or res)
    keys = ('state', 'pan', 'tilt', 'tilt_clamped_from', 'goal', 'faults', 'config', 'people_near', 'arm_request', 'shots',
            'fps', 'end', 'reached', 'acted', 'note', 'laser', 'pendant', 'hopper', 'balls_fired', 'wheels_rpm', 'rate_cap')
    parts = []
    for k in keys:
        if k in res and res[k] not in (None, [], {}):
            v = res[k]
            v = round(v, 2) if isinstance(v, float) else v
            parts.append(f'{k}={v}')
    return 'ok ' + ' '.join(parts)


def run_jsonl(host: TurretHost, inp, out):
    """One JSON object a line in, one JSON line out for each, until {"cmd": "quit"} or the end of the input."""
    for line in inp:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError as e:
            obj, res = None, {'ok': False, 'error': f'not JSON: {e}'}
        else:
            obj = obj if isinstance(obj, dict) else {'cmd': str(obj)}
            res = host.call(obj)
        out.write(json.dumps(res, default=str) + '\n')
        out.flush()
        if obj and str(obj.get('cmd', '')).lower() == 'quit':
            break


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--mount', required=True, choices=M.MOUNTS, help='the CONFIG rows to load: bench, box or robot')
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--sim', action='store_true', help='the simulated turret (sim_turret.py)')
    src.add_argument('--can', help='python-can channel: socketcan:can0 (the laptop\'s gs_usb adapter), socketcan:can1 (the Jetson)')
    ap.add_argument('--keepout', default=None, help="'none', or FROM:TO[,FROM:TO] in deg: replaces the mount's keep-outs")
    ap.add_argument('--log-dir', default=None, help='where host-*.json goes (default exports/turret/bench/, --sim: its sim/)')
    ap.add_argument('--no-log', action='store_true')
    ap.add_argument('--script', default=None, help="commands separated by ';', then exit")
    ap.add_argument('--jsonl', action='store_true', help='JSON lines on stdin and stdout')
    ap.add_argument('--timeout', type=float, default=30.0, help='seconds to wait for the turret to home')
    ap.add_argument('--seed', type=int, default=1, help='--sim: the simulation\'s seed')
    ap.add_argument('--hopper', type=int, default=30, help='--sim: balls in the hopper')
    a = ap.parse_args()
    try:
        keepouts = parse_keepouts(a.keepout)
    except ValueError:
        ap.error(f"--keepout {a.keepout!r}: 'none' or FROM:TO[,FROM:TO] in degrees")
    if a.sim:
        import sim_turret
        link, name = SimLink(sim_turret.SimRig(seed=a.seed, hopper=a.hopper)), f'sim_turret.py seed {a.seed}'
    else:
        link, name = CanLink(a.can), a.can
    try:
        host = TurretHost(link, a.mount, log_dir=a.log_dir, keepouts=keepouts, log=not a.no_log, link_name=name)
    except HostError as e:
        sys.exit(f'host: {e}')
    say = (lambda s: sys.stderr.write(s + '\n')) if a.jsonl else print
    try:
        st = host.start(a.timeout)
        for n in host.setup['notes']:
            say(f'note: {n}')
        say(f"turret {st['state']}, mount {a.mount}, CONFIG {st['config']} ({len(host.setup['rows'])} rows; the table from "
            f"{host.setup['sources']['depression']})")
        if a.jsonl:
            sys.stdout.write(json.dumps(dict(st, event='ready'), default=str) + '\n')
            sys.stdout.flush()
            run_jsonl(host, sys.stdin, sys.stdout)
        elif a.script:
            for c in a.script.split(';'):
                if c.strip():
                    print(f'> {c.strip()}\n  {fmt(host.command(c))}')
        else:
            while True:
                try:
                    line = input('turret> ')
                except EOFError:
                    break
                if line.strip().lower() in ('quit', 'exit', 'q'):
                    break
                print('  ' + fmt(host.command(line)))
    except KeyboardInterrupt:
        pass
    finally:
        path = host.close()
        if path:
            say(f'log: {_rel(path)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
