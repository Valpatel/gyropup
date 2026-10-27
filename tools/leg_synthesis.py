#!/usr/bin/env python3
"""How leg v2's five-bar got its numbers: a sweep over motor spacing D, upper links l1 and lower links l2.

    .venv/bin/python tools/leg_synthesis.py [--top 15]

Motors at (+-D/2, 0), equal upper links l1, equal lower links l2 meeting at the wheel axle E, knees out. For every
geometry the sweep visits the working region (leg 130-380 mm straight down, and +-10/20 deg of lean between 220 and
340 mm) and scores:
  - the most vertical force the leg can push at the 60 N m firmware cap, at its worst point in the region (higher is better);
  - the motor torque to hold 130 N (half a 26 kg robot);
  - transmission: the angle between each upper and lower link, and between the two lower links, kept 28-152 deg
    (away from the dead points);
  - the knees stay below the hip line (they are near the body's sides);
  - and every link printable: l2 <= 250 mm, so a lower link with its bearing eyes fits a 256 mm bed turned 45 deg.
Writes exports/leg/synthesis.json. cad/fivebar.py takes the chosen numbers (D 150, l1 150, l2 250).
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path

import numpy as np

R = Path(__file__).resolve().parents[1]


def ik(D, l1, l2, E, side):
    A = np.array([side * D / 2, 0.0])
    v = E - A
    r = np.linalg.norm(v)
    if r > l1 + l2 - 1e-6 or r < abs(l1 - l2) + 1e-6:
        return None
    a = (l1 ** 2 - l2 ** 2 + r ** 2) / (2 * r)
    h = math.sqrt(max(0.0, l1 ** 2 - a ** 2))
    m, n = A + a * v / r, np.array([-v[1], v[0]]) / r
    c1, c2 = m + h * n, m - h * n
    return A, (c1 if (c1[0] - c2[0]) * side > 0 else c2)


def fk(D, l1, l2, p1, p2):
    A, B = np.array([D / 2, 0.0]), np.array([-D / 2, 0.0])
    C = A + l1 * np.array([math.cos(p1), math.sin(p1)])
    Dk = B + l1 * np.array([math.cos(p2), math.sin(p2)])
    v = Dk - C
    r = np.linalg.norm(v)
    if r > 2 * l2 or r < 1e-9:
        return None
    m, h, n = (C + Dk) / 2, math.sqrt(l2 ** 2 - (r / 2) ** 2), np.array([-v[1], v[0]]) / r
    e1, e2 = m + h * n, m - h * n
    return e1 if e1[1] < e2[1] else e2


def angle(u, w):
    return math.degrees(math.acos(np.clip(u @ w / np.linalg.norm(u) / np.linalg.norm(w), -1, 1)))


def score(D, l1, l2, hmin=130, hmax=380):
    pts = [(0.0, -h) for h in np.linspace(hmin, hmax, 26)]
    for h in np.linspace(220, 340, 7):
        for a in (-20, -10, 10, 20):
            pts.append((h * math.sin(math.radians(a)), -h * math.cos(math.radians(a))))
    mus, psis, hold, kx, kz, fmax = [], [], [], [], [], []
    for (x, z) in pts:
        E = np.array([x, z])
        f, b = ik(D, l1, l2, E, 1), ik(D, l1, l2, E, -1)
        if f is None or b is None:
            return None
        (A, C), (B, Dk) = f, b
        p = np.array([math.atan2(C[1] - A[1], C[0] - A[0]), math.atan2(Dk[1] - B[1], Dk[0] - B[0])])
        J = np.zeros((2, 2))
        for k in range(2):
            dp = np.zeros(2)
            dp[k] = 1e-6
            ep, em = fk(D, l1, l2, *(p + dp)), fk(D, l1, l2, *(p - dp))
            if ep is None or em is None:
                return None
            J[:, k] = (ep - em) / 2e-6
        mus += [angle(A - C, E - C), angle(B - Dk, E - Dk)]
        psis.append(angle(C - E, Dk - E))
        hold.append(np.abs(J.T @ np.array([0.0, 130.0]) / 1000).max())
        fmax.append(60.0 / max(np.abs(J.T @ np.array([0.0, 1.0]) / 1000).max(), 1e-9))
        kx.append(max(abs(C[0]), abs(Dk[0])))
        kz.append(max(C[1], Dk[1]))
    return {'push_n_min': round(min(fmax)), 'push_n_crouch': round(fmax[0]), 'push_n_300': round(fmax[int(26 * 0.68)]),
            'hold_nm_max': round(max(hold), 1), 'mu_deg': [round(min(mus), 1), round(max(mus), 1)],
            'psi_deg': [round(min(psis), 1), round(max(psis), 1)], 'knee_x_max_mm': round(max(kx), 1), 'knee_z_max_mm': round(max(kz), 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=15)
    a = ap.parse_args()
    rows, tried = [], 0
    for D, l1, l2 in itertools.product([140, 150], range(110, 181, 5), range(200, 251, 5)):
        tried += 1
        s = score(D, l1, l2)
        if not s:
            continue
        ok = s['mu_deg'][0] >= 28 and s['mu_deg'][1] <= 152 and s['psi_deg'][0] >= 28 and s['psi_deg'][1] <= 152 and s['knee_z_max_mm'] <= 30
        if ok:
            rows.append({'D': D, 'l1': l1, 'l2': l2, **s})
    rows.sort(key=lambda r: -r['push_n_min'])
    out = R / 'exports' / 'leg' / 'synthesis.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'tried': tried, 'feasible': len(rows), 'chosen': {'D': 150, 'l1': 150, 'l2': 250},
                               'best': rows[:a.top]}, indent=1) + '\n')
    print(f'{tried} geometries, {len(rows)} feasible')
    print('push@60Nm  D   l1  l2   hold   mu          psi         knee x/z')
    for r in rows[:a.top]:
        print(f"{r['push_n_min']:6d} N  {r['D']} {r['l1']} {r['l2']}  {r['hold_nm_max']:5.1f}  {r['mu_deg']}  {r['psi_deg']}  {r['knee_x_max_mm']}/{r['knee_z_max_mm']}")


if __name__ == '__main__':
    main()
