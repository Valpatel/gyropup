"""Run logs: every tick of a rig run (500 Hz), and its summary in rig-results.json's terms.

    log = RunLog('can', 'squat', meta={...})
    log.add(tick, command, pol)               # every tick
    paths = log.save(summary)                 # exports/rig/runs/<stamp>-<backend>-<test>[-tag].npz and .json

The .npz holds one array per field (float32; the phases as small integers with their names in the JSON). The JSON
holds the run's metadata (backend, rate, mass, the motors' start-up record with the damper switch, the git commit),
the summary (the keys of exports/leg/rig-results.json that a run can measure), the timing, and the verdict that
rig/compare.py adds.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np

R = Path(__file__).resolve().parents[1]
RUNS = R / 'exports' / 'rig' / 'runs'
PHASES = ['', 'track', 'push', 'air', 'land', 'off', 'sitdown', 'limp', 'stopped']
FIELDS = ('t', 'phi_f', 'phi_r', 'w_f', 'w_r', 'tau_f', 'tau_r', 'tau_cmd_f', 'tau_cmd_r', 'kd', 'temp_f', 'temp_r',
          'vbus', 'L', 'th', 'dL', 'L_cmd', 'contact', 'run', 'ok', 'phase')
SIM_FIELDS = ('rail_mm', 'wheel_fz_n', 'contact_true', 'ibus_a')
CAN_FIELDS = ('rtt_ms', 'height_mm', 'force_n', 'vbus_mean')


def git_commit() -> Optional[str]:
    try:
        return subprocess.run(['git', '-C', str(R), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True,
                              timeout=5).stdout.strip() or None
    except Exception:
        return None


class RunLog:
    def __init__(self, backend: str, test: str, meta: Optional[dict] = None, tag: str = ''):
        self.backend, self.test, self.tag = backend, test, tag
        self.meta = {'backend': backend, 'test': test, 'started': dt.datetime.now().isoformat(timespec='seconds'),
                     'commit': git_commit(), **(meta or {})}
        self.rows = {k: [] for k in FIELDS + SIM_FIELDS + CAN_FIELDS}
        self.aborts = []

    def add(self, tk, cmd, pol=None) -> None:
        nan = float('nan')
        L, th, dL = (pol[0], pol[1], pol[2]) if pol is not None else (nan, nan, nan)
        row = {'t': tk.t, 'phi_f': tk.f.phi, 'phi_r': tk.r.phi, 'w_f': tk.f.w, 'w_r': tk.r.w, 'tau_f': tk.f.tau,
               'tau_r': tk.r.tau, 'tau_cmd_f': cmd.tau_f, 'tau_cmd_r': cmd.tau_r, 'kd': cmd.kd, 'temp_f': tk.f.temp_c,
               'temp_r': tk.r.temp_c, 'vbus': tk.vbus if tk.vbus is not None else nan, 'L': L, 'th': th, 'dL': dL,
               'L_cmd': cmd.L_cmd if cmd.L_cmd is not None else nan, 'contact': float(cmd.contact), 'run': float(tk.run),
               'ok': float(tk.ok), 'phase': float(PHASES.index(cmd.phase) if cmd.phase in PHASES else 0)}
        ex = tk.extra or {}
        node = ex.get('node') or {}
        row.update({'rail_mm': ex.get('rail_mm', nan), 'wheel_fz_n': ex.get('wheel_fz_n', nan),
                    'contact_true': float(ex['contact']) if 'contact' in ex else nan, 'ibus_a': ex.get('ibus_a', nan),
                    'rtt_ms': ex.get('rtt_ms', nan),
                    'height_mm': node.get('height_mm') if node.get('height_mm') is not None else nan,
                    'force_n': node.get('force_n') if node.get('force_n') is not None else nan,
                    'vbus_mean': node.get('vbus_mean') if node.get('vbus_mean') is not None else nan})
        for k, v in row.items():
            self.rows[k].append(v)
        if cmd.abort and (not self.aborts or self.aborts[-1][1] != cmd.abort):
            self.aborts.append((round(tk.t, 4), cmd.abort))

    def arrays(self) -> dict:
        return {k: np.asarray(v, dtype=np.float32 if k != 't' else np.float64) for k, v in self.rows.items() if v}

    def measured(self) -> dict:
        """What the run itself shows, in rig-results.json's terms (what the rig can measure)."""
        a = self.arrays()
        if not len(a.get('t', [])):
            return {}
        fin = lambda x: x[np.isfinite(x)]
        out = {'peak_motor_nm': round(float(max(np.max(np.abs(fin(a['tau_f'])), initial=0), np.max(np.abs(fin(a['tau_r'])), initial=0))), 1),
               'peak_motor_speed_rad_s': round(float(max(np.max(np.abs(fin(a['w_f'])), initial=0), np.max(np.abs(fin(a['w_r'])), initial=0))), 2),
               'L_range_mm': [round(float(np.nanmin(a['L'])) * 1000, 1), round(float(np.nanmax(a['L'])) * 1000, 1)],
               'vbus_range_v': ([round(float(np.nanmin(a['vbus'])), 2), round(float(np.nanmax(a['vbus'])), 2)]
                                if np.isfinite(a['vbus']).any() else None),
               'temp_rise_c': round(float(np.nanmax(a['temp_f'][-1:] - a['temp_f'][:1])), 2) if np.isfinite(a['temp_f']).any() else None,
               'ticks': int(len(a['t'])), 'missed_ticks': int(np.sum(a['ok'] < 0.5)),
               'aborts': self.aborts}
        h = fin(a['height_mm'])
        if len(h):
            out['jump_height_tof_mm'] = round(float(np.max(h) - h[0]), 1)
        f = fin(a['force_n'])
        if len(f):
            out['load_plate_n'] = [round(float(np.min(f)), 1), round(float(np.max(f)), 1)]
        return out

    def save(self, summary: Optional[dict] = None, folder: Path = RUNS) -> dict:
        folder.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime('%Y-%m-%d-%H%M%S')
        name = f'{stamp}-{self.backend}-{self.test}' + (f'-{self.tag}' if self.tag else '')
        a = self.arrays()
        np.savez_compressed(folder / f'{name}.npz', **a)
        doc = {'meta': self.meta, 'phases': PHASES, 'measured': self.measured(), 'summary': summary or {}}
        (folder / f'{name}.json').write_text(json.dumps(doc, indent=1, default=_json) + '\n')
        return {'npz': folder / f'{name}.npz', 'json': folder / f'{name}.json'}


def _json(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, float) and not math.isfinite(o):
        return None
    if isinstance(o, Path):
        return str(o)
    return str(o)


def load(path) -> tuple:
    """(json document, arrays) of a saved run, from either file's path."""
    p = Path(path)
    stem = p.with_suffix('')
    doc = json.loads(stem.with_suffix('.json').read_text())
    with np.load(stem.with_suffix('.npz')) as z:
        arr = {k: z[k] for k in z.files}
    return doc, arr
