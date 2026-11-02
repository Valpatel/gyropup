#!/usr/bin/env python3
"""The study page's figures (research/body-sheet-metal/README.md), from study.json and the body's own dimensions.

    .venv/bin/python research/body-sheet-metal/figures.py      # needs matplotlib; writes fig-*.png here

fig-sections.png   each option's cross-section through the body, the parts it changes in its colour
fig-cost.png       SendCutSend's price for each option's metal, part by part
fig-counts.png     plates, bends, PEM nuts, unique bought fasteners, build steps, print hours
fig-fea.png        each FEA case's safety factor (or deflection) over its target, per option
fig-joints.png     a PEM nut in 5052 beside a heat-set insert in PA6-CF, thread by thread
fig-pem-rules.png  SendCutSend's PEM layout rules and the right way to load a clinch nut
fig-probe.png      what a bend and a PEM nut add to a plate's price
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402
from matplotlib.patches import FancyArrowPatch, Rectangle  # noqa: E402

plt.rcParams['text.parse_math'] = False      # prices carry '$'

HERE = Path(__file__).resolve().parent
S = json.loads((HERE / 'study.json').read_text())
INK, INK2, MUTED, GRID, SURFACE = '#0b0b0b', '#52514e', '#8a8984', '#e6e5e1', '#fcfcfb'
METAL, PRINT = '#b9b8b2', '#f1dfc0'          # unchanged sheet metal; printed parts
FAIL = '#d03b3b'
OPT = {'today': '#2a78d6', 'A': '#eb6834', 'B': '#1baf7a', 'C': '#eda100'}     # categorical slots 1-4, fixed order
NAME = {'today': 'Today', 'A': 'A  PEM plates', 'B': 'B  riveted keel', 'C': 'C  printed plates'}
ORDER = ['today', 'A', 'B', 'C']


def _style(ax):
    ax.set_facecolor(SURFACE)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0, colors=INK2, labelsize=8)


def _fig(w, h):
    fig = plt.figure(figsize=(w, h), dpi=130)
    fig.patch.set_facecolor(SURFACE)
    return fig


def _save(fig, name):
    fig.savefig(HERE / name, facecolor=SURFACE, bbox_inches='tight')
    plt.close(fig)
    print('wrote', name)


# --------------------------------------------------------------------------------------------- sections

def _box(ax, y0, y1, z0, z1, fc, ec=INK2, lw=0.6, hatch=None, z=2):
    ax.add_patch(Rectangle((min(y0, y1), min(z0, z1)), abs(y1 - y0), abs(z1 - z0), fc=fc, ec=ec, lw=lw, hatch=hatch, zorder=z))


def _section(ax, opt):
    c = OPT[opt]
    new = lambda *names: c if opt != 'today' and any(n for n in names) else METAL
    zt, top = 90.5, 216.0
    # cheeks: 4.75 mm plates either side of the 31 mm gap, 30 mm flanges turned out top and bottom, PEM nuts in them
    for s in (1, -1):
        _box(ax, s * 15.5, s * 20.25, -zt, zt, METAL)
        _box(ax, s * 15.5, s * 50.0, zt - 4.75, zt, METAL)
        _box(ax, s * 15.5, s * 50.0, -zt, -zt + 4.75, METAL)
    _box(ax, -15.5, 15.5, -3, 3, PRINT, hatch='////')            # the standoffs across the gap (printed spacers' stand-in)
    # floor tray and deck
    if opt == 'C':
        tt, dt, fc_td, h = 8.0, 8.0, PRINT, '////'
    else:
        tt, dt, fc_td, h = 3.175, (3.175 if opt in ('A', 'B') else 2.54), (c if opt in ('A', 'B') else METAL), None
    fc_t = fc_td if opt == 'C' else METAL                   # the tray keeps its four bends except in C
    _box(ax, -127, 127, zt, zt + tt, fc_t, hatch=h)
    _box(ax, -127, 127, top - dt, top, fc_td, hatch=h)
    for s in (1, -1):
        _box(ax, s * 127, s * (127 - tt), zt - 15, zt + tt, fc_t, hatch=h)
        _box(ax, s * 127, s * (127 - dt), top - 20, top, fc_td, hatch=h)
        _box(ax, s * 95, s * 107, zt + tt, top - dt, PRINT, hatch='////')        # deck posts (printed PA6-CF)
    # compute pallet and power plate (stand-ins on the tray)
    pal = PRINT if opt == 'C' else METAL
    _box(ax, -80, 0, zt + 18, zt + 18 + (6 if opt == 'C' else 3.2), pal, hatch='////' if opt == 'C' else None)
    _box(ax, 20, 85, zt + 30, zt + 30 + (6 if opt == 'C' else 2.5), pal, hatch='////' if opt == 'C' else None)
    # turret plate under the deck at the riser
    if opt in ('today', 'C'):
        _box(ax, -70, 70, top - dt - 3.175, top - dt, METAL)
    # the battery bay
    zf = -221.64
    if opt in ('today', 'A'):
        _box(ax, -58, 58, -zt - 2.54, -zt, METAL)                               # belly plate
        for s in (1, -1):
            _box(ax, s * 49.6, s * 51.2, zf + 1.6, -zt - 2.54, METAL)            # bay sides
            _box(ax, s * 49.6, s * 51.2, zf, zf + 20, METAL)                     # floor flange
        _box(ax, -51.2, 51.2, zf, zf + 1.6, METAL)                              # bay floor
    else:
        t = 2.286
        for s in (1, -1):
            _box(ax, s * 3, s * 51.2, -zt - t, -zt, c)                          # top flange
            _box(ax, s * (51.2 - t), s * 51.2, zf, -zt, c)                      # web
            _box(ax, s * 3, s * 51.2, zf, zf + t, c)                            # floor flange
        _box(ax, -20, 20, -zt - 2 * t, -zt - t, c)                              # straps
        _box(ax, -20, 20, zf - t, zf, c)
        for y in (-10, 10):
            for z in (-zt - 1.5 * t, zf - 0.5 * t):
                ax.plot([y], [z], marker='o', ms=3, color=INK, zorder=5)
    _box(ax, -43.5, 43.5, -219.0, -122.0, '#e6e5e1', ec=MUTED, lw=0.5, z=1)     # the packs
    ax.text(0, -170, 'packs', ha='center', va='center', fontsize=7, color=INK2)
    ax.set_xlim(-140, 140)
    ax.set_ylim(-240, 232)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(NAME[opt], fontsize=10, color=INK, loc='left')


def fig_sections():
    fig = _fig(13.0, 6.2)
    notes = {'today': ['10 SendCutSend parts, 14 bends', 'tray + deck: 4 bends, corner reliefs', 'belly plate, bay floor, 2 bay sides', 'turret plate under the deck'],
             'A': ['9 parts, 12 bends, 81 PEM', 'deck 1/8 in, 2 bends, turret plate folded in', 'PEM nuts: 6 a cheek (hip frame), 4 at the riser', 'tray keeps 4 bends (T1); bay as today'],
             'B': ['8 parts, 14 bends', 'A, plus the bay + belly as two identical', 'C-channels riveted to two flat straps', '32 x 1/8 in blind rivets'],
             'C': ['5 parts, 8 bends', 'deck, tray, pallet, power plate printed', 'in PA6-CF (8 / 6 mm solid)', 'keel as B; turret plate back']}
    for i, o in enumerate(ORDER):
        ax = fig.add_axes([0.005 + i * 0.25, 0.14, 0.24, 0.78])
        _section(ax, o)
        for j, line in enumerate(notes[o]):
            fig.text(0.01 + i * 0.25, 0.10 - j * 0.028, line, fontsize=7.5, color=INK if j == 0 else INK2,
                     weight='bold' if j == 0 else 'normal')
    fig.text(0.005, 1.02, 'Section across the body at the hips (y-z, mm, to scale). Grey: SendCutSend sheet as today; colour: '
             'the sheet each option changes; hatched: printed PA6-CF; dots: rivet rows', fontsize=8.5, color=INK2, va='top')
    _save(fig, 'fig-sections.png')


# --------------------------------------------------------------------------------------------- cost

def fig_cost():
    fig = _fig(10.5, 3.6)
    ax = fig.add_axes([0.13, 0.17, 0.80, 0.70])
    _style(ax)
    for i, o in enumerate(ORDER):
        rows = sorted(S['options'][o]['sheet'], key=lambda r: -(r['price_line'] or 0))
        left = 0.0
        y = len(ORDER) - 1 - i
        for j, r in enumerate(rows):
            v = r['price_line'] or 0.0
            ax.barh(y, v, left=left, height=0.62, color=OPT[o], alpha=1.0 - 0.13 * min(j, 6), edgecolor=SURFACE, linewidth=2)
            if v > 40:
                ax.text(left + v / 2, y, {'cheek': 'cheeks', 'cheek_pem': 'cheeks', 'compute_pallet': 'pallet', 'power_plate': 'power', 'turret_plate': 'turret', 'belly_plate': 'belly', 'floor_tray_2b': 'tray', 'floor_tray': 'tray', 'deck_2b': 'deck', 'bay_floor': 'bay floor', 'bay_side': 'sides', 'keel_half': 'keel halves', 'bus_bar': 'bus'}.get(r['part'], r['part']), ha='center', va='center',
                        fontsize=6.5, color=INK if j > 1 else SURFACE)
            left += v
        tot = S['options'][o]['summary']['sheet_usd']
        ax.text(left + 8, y, f"${tot:,.0f}" if tot else 'n/a', va='center', fontsize=9, color=INK, weight='bold')
    ax.set_yticks(range(len(ORDER)))
    ax.set_yticklabels([NAME[o] for o in reversed(ORDER)], fontsize=9, color=INK)
    ax.grid(axis='x', color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.set_xlabel("USD, SendCutSend's instant quote, deburred, qty 1 set (read 2026-11-01; no account, no order)",
                  fontsize=8, color=INK2)
    ax.set_title('Sheet-metal cost of the body by option, part by part (largest first)', fontsize=10, color=INK, loc='left')
    _save(fig, 'fig-cost.png')


# --------------------------------------------------------------------------------------------- counts

def fig_counts():
    metrics = [('plates_unique', 'unique SendCutSend parts', lambda s: s['plates_unique']),
               ('bends', 'bends (all pieces)', lambda s: s['bends']),
               ('pem', 'PEM hardware (arrives pressed in)', lambda s: s['pem']),
               ('fast', 'unique bought fasteners', lambda s: s['unique_bought_fasteners']),
               ('steps', 'build steps (parts + screws + inserts + rivets)', lambda s: s['build_steps']['total']),
               ('hours', 'print hours (body)', lambda s: s['print_hours'])]
    fig = _fig(12.0, 4.6)
    for k, (key, title, f) in enumerate(metrics):
        ax = fig.add_axes([0.03 + (k % 3) * 0.33, 0.56 - (k // 3) * 0.48, 0.27, 0.33])
        _style(ax)
        vals = [f(S['options'][o]['summary']) for o in ORDER]
        ax.bar(range(4), vals, color=[OPT[o] for o in ORDER], width=0.66, edgecolor=SURFACE, linewidth=2)
        for i, v in enumerate(vals):
            ax.text(i, v, f'{v:g}', ha='center', va='bottom', fontsize=8.5, color=INK)
        ax.set_xticks(range(4))
        ax.set_xticklabels(['Today', 'A', 'B', 'C'], fontsize=8, color=INK)
        ax.set_yticks([])
        ax.set_ylim(0, max(vals) * 1.22)
        ax.set_title(title, fontsize=9, color=INK, loc='left')
    fig.text(0.03, 0.005, 'Lower is simpler, except PEM hardware: it arrives pressed in, so it adds no build step; rivets and '
             'heat-set inserts do. Print hours: the body print plan, with the new printed parts at its own PA6-CF rate.',
             fontsize=7.5, color=INK2)
    _save(fig, 'fig-counts.png')


# --------------------------------------------------------------------------------------------- FEA

def fig_fea():
    fea = S.get('fea') or {}
    if not fea:
        print('fig-fea.png: no FEA results yet')
        return
    t = json.loads((HERE.parents[1] / 'exports/body/fea/summary.json').read_text())['targets']
    cases = ['S1-landing', 'S1F-collapse', 'S2-twist', 'S3-pitch', 'T1-tray', 'D1-hand-front', 'D1-hand-riser', 'D2-turret-fall']
    rows = []
    for c in cases:
        for o in ORDER:
            r = (fea.get(o) or {}).get('results', {}).get(c)
            if not r or not r.get('sf') or not r.get('target') or r.get('run') != o:
                continue                            # each option's own runs only: a case it inherits is the other's dot
            rows.append((c, o, r['sf'] / r['target'], r))
            if r.get('deflection_mm') is not None:
                rows.append((c + ', deflection', o, t['deck_mm'] / r['deflection_mm'], r))
            if r.get('twist_deg') is not None:
                rows.append((c + ', twist angle', o, t['twist_deg'] / r['twist_deg'], r))
    r2 = (fea.get('A-tray2b') or {}).get('results', {}).get('T1-tray')
    if r2 and r2.get('sf') and r2.get('target'):
        rows.append(('T1-tray, two-bend tray', 'A', r2['sf'] / r2['target'], r2))
    labels = []
    for c, _, _, _ in rows:
        if c not in labels:
            labels.append(c)
    fig = _fig(10.0, 0.42 * len(labels) + 1.4)
    ax = fig.add_axes([0.24, 0.17, 0.72, 0.76])
    _style(ax)
    ax.set_xscale('log')
    ax.axvline(1.0, color=INK2, lw=1)
    off = {'today': 0.24, 'A': 0.08, 'B': -0.08, 'C': -0.24}
    for c, o, v, r in rows:
        y = len(labels) - 1 - labels.index(c) + off[o]
        ax.scatter([min(v, 30)], [y], s=34, color=FAIL if v < 1 else OPT[o], zorder=3, edgecolor=SURFACE, linewidth=1.2,
                   marker='X' if v < 1 else 'o')
        if v < 1:
            ax.text(min(v, 30) * 0.92, y, f'{NAME[o].split()[0]} misses', fontsize=7, color=INK2, va='center', ha='right')
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(list(reversed(labels)), fontsize=8, color=INK)
    ax.set_xticks([0.25, 0.5, 1, 2, 4, 8, 16])
    ax.set_xticklabels(['0.25', '0.5', '1', '2', '4', '8', '16'], fontsize=8, color=INK2)
    ax.grid(axis='x', color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    fig.text(0.24, 0.035, 'An option shows only the cases it changes: A the deck, B the spine (its keel), C the deck and tray; '
             'the rest are today\'s or the option\'s it builds on.', fontsize=7.5, color=INK2)
    ax.set_xlabel('margin over the body plan\'s target, log scale (strength: SF / target; deck deflection: 0.5 mm / '
                  'deflection; twist: 0.1 deg / twist). Under 1 misses.', fontsize=8, color=INK2)
    for o in ORDER:
        ax.scatter([], [], s=34, color=OPT[o], label=NAME[o])
    ax.legend(loc='lower right', fontsize=7.5, frameon=False, labelcolor=INK)
    ax.set_title('FEA at 18.75 kg a leg: every option on the same cases, loads and mesh (4 mm; D2 2 mm), on one host',
                 fontsize=10, color=INK, loc='left')
    _save(fig, 'fig-fea.png')


# --------------------------------------------------------------------------------------------- joints

def fig_joints():
    rows = [r for r in S['joints'] if r['material'] == 'pa6-cf20-polymaker-wet']
    fig = _fig(11.5, 3.9)
    th = [r['thread'] for r in rows]
    ax = fig.add_axes([0.06, 0.2, 0.42, 0.66])
    _style(ax)
    ax.set_yscale('log')
    series = [('insert: allowable pull-out\n(cad-agent check_joint, low / 2)', [r['insert_allowable_pull_n'] for r in rows], '#86b6ef'),
              ('PEM: pushout (screw in its head side,\nthe way PEM says never to load it)', [r['pem_pushout_n'] for r in rows], '#e6a37f'),
              ('PEM: min. axial strength, loaded\ntoward the sheet (PEM, unified analogue)', [r['pem_axial_min_n'] for r in rows], '#1c5cab')]
    w = 0.26
    for k, (lab, vals, col) in enumerate(series):
        xs = [i + (k - 1) * w for i in range(len(rows))]
        ax.bar(xs, vals, width=w, color=col, edgecolor=SURFACE, linewidth=2, label=lab)
        for x, v in zip(xs, vals):
            ax.text(x, v * 1.08, f'{v:,.0f}', ha='center', va='bottom', fontsize=7, color=INK)
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels(th, fontsize=9, color=INK)
    ax.set_ylim(100, 300000)
    ax.set_yticks([100, 300, 1000, 3000, 10000, 30000])
    ax.set_yticklabels(['100', '300', '1,000', '3,000', '10,000', '30,000'])
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_ylabel('N (log)', fontsize=8, color=INK2)
    ax.grid(axis='y', color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=7, frameon=False, loc='upper left', labelcolor=INK)
    ax.set_title('Holding a load along the screw', fontsize=10, color=INK, loc='left')
    ax2 = fig.add_axes([0.56, 0.2, 0.42, 0.66])
    _style(ax2)
    series = [('insert: most to tighten, a metal plate on it\n(cad-agent check_joint)', [r['insert_tighten_nm'] for r in rows], '#86b6ef'),
              ('PEM: torque-out (the nut spinning in\nthe sheet, no clamp; PEM average)', [r['pem_torque_out_nm'] for r in rows], '#e6a37f'),
              ('PEM: recommended tightening torque,\ngrade 5 screw (PEM, unified analogue)', [r['pem_tighten_grade5_nm'] for r in rows], '#1c5cab')]
    for k, (lab, vals, col) in enumerate(series):
        xs = [i + (k - 1) * w for i in range(len(rows))]
        ax2.bar(xs, vals, width=w, color=col, edgecolor=SURFACE, linewidth=2, label=lab)
        for x, v in zip(xs, vals):
            ax2.text(x, v + 0.05, f'{v:.2f}', ha='center', va='bottom', fontsize=7, color=INK)
    ax2.set_xticks(range(len(rows)))
    ax2.set_xticklabels(th, fontsize=9, color=INK)
    ax2.set_ylim(0, 6.2)
    ax2.set_ylabel('N m', fontsize=8, color=INK2)
    ax2.grid(axis='y', color=GRID, lw=0.6)
    ax2.set_axisbelow(True)
    ax2.legend(fontsize=7, frameon=False, loc='upper left', labelcolor=INK)
    ax2.set_title('Clamping it: tightening torque', fontsize=10, color=INK, loc='left')
    fig.text(0.06, 0.02, 'Insert: McMaster 94459A140 / A160 / A775 in printed PA6-CF (humid), a 1/8 in metal plate clamped on it, '
             'class 8.8 screw (cad-agent v0.13.0).\nPEM S-M3-0 / S-M4-0 / SS-M5-0 in 5052-H34: PennEngineering bulletin CL '
             '(10/13/26) and its axial-strength sheet (S-440-0 / S-832-0 / SS-024-0).', fontsize=7, color=INK2)
    _save(fig, 'fig-joints.png')


# --------------------------------------------------------------------------------------------- PEM rules

def fig_pem_rules():
    fig = _fig(12.0, 4.0)
    # plan view: a plate with a bend, a nut near the edge and near the bend
    ax = fig.add_axes([0.0, 0.05, 0.42, 0.85])
    ax.axis('off')
    ax.set_aspect('equal')
    ax.add_patch(Rectangle((0, 0), 100, 60, fc='#eceae4', ec=INK2, lw=0.8))
    ax.add_patch(Rectangle((0, 60), 100, 6, fc=GRID, ec=INK2, lw=0.6, hatch='....'))     # bend zone
    ax.text(102, 63, 'bend', fontsize=8, color=INK2, va='center')
    pts = [(20, 7.1), (40, 7.1), (70, 47)]
    for x, y in pts:
        ax.add_patch(plt.Circle((x, y), 4.3, fc=SURFACE, ec=INK, lw=0.8))
        ax.add_patch(plt.Circle((x, y), 2.5, fc='#cfcdc6', ec=INK2, lw=0.5))

    def dim(x0, y0, x1, y1, lab, dx=0, dy=0):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle='<->', mutation_scale=7, color=OPT['today'], lw=0.9))
        ax.text((x0 + x1) / 2 + dx, (y0 + y1) / 2 + dy, lab, fontsize=8, color=INK, ha='center', va='center')
    dim(20, 0, 20, 7.1, 'K', dx=-4)
    dim(20, 13, 40, 13, 'M', dy=2.5)
    dim(70, 47, 70, 60, 'N', dx=4)
    dim(84, 47 - 3.2, 84, 47 + 3.2, 'H', dx=4)
    ax.plot([70, 84], [47 + 3.2, 47 + 3.2], color=MUTED, lw=0.5)
    ax.plot([70, 84], [47 - 3.2, 47 - 3.2], color=MUTED, lw=0.5)
    ax.set_xlim(-5, 115)
    ax.set_ylim(-8, 72)
    ax.set_title("SendCutSend's PEM layout rules (its hardware catalogue)", fontsize=10, color=INK, loc='left')
    rules = ['H  the hole SendCutSend cuts for the nut (SS-M5-0: 0.251 in)', 'K  least centre-to-edge (SS-M5-0: 0.280 in)',
             'M  least centre-to-centre (SS-M5-0: 0.407 in)', 'N  centre to a bend: J/2 + the die\'s half width',
             'no hardware on an acute bend; 4-sided boxes with', 'hardware: flanges 3 in or less']
    for j, line in enumerate(rules):
        fig.text(0.43, 0.82 - j * 0.075, line, fontsize=8, color=INK2)
    # side views: right way and wrong way
    for k, (title, right) in enumerate((('right: load toward the sheet', True), ('wrong: screw in the head side', False))):
        ax = fig.add_axes([0.70 + k * 0.155, 0.08, 0.14, 0.78])
        ax.axis('off')
        ax.set_aspect('equal')
        sheet_z = 0.0
        ax.add_patch(Rectangle((-14, sheet_z), 28, 3.2, fc='#cfcdc6', ec=INK2, lw=0.6))
        ax.add_patch(Rectangle((-4.3, sheet_z + 3.2), 8.6, 2.0, fc=INK2, ec=INK, lw=0.5))        # nut head above
        ax.add_patch(Rectangle((-3.2, sheet_z + 0.6), 6.4, 2.6, fc=INK2, ec=INK, lw=0.5))        # shank in the sheet
        if right:
            ax.add_patch(Rectangle((-14, -4), 28, 4, fc=OPT['B'], ec=INK2, lw=0.6))           # mating part on the flush side
            ax.add_patch(Rectangle((-1.25, -9), 2.5, 16, fc=MUTED, ec=INK2, lw=0.4))
            ax.add_patch(Rectangle((-4, -11), 8, 2, fc=MUTED, ec=INK2, lw=0.4))
            ax.add_patch(FancyArrowPatch((0, 9), (0, 14), arrowstyle='<-', mutation_scale=9, color=INK, lw=1))
            note = 'the nut bears on the sheet:\nscrew- or thread-limited\n(SS-024-0: 9.96 kN min.)'
        else:
            ax.add_patch(Rectangle((-14, 5.2), 28, 4, fc=FAIL, ec=INK2, lw=0.6, alpha=0.75))  # mating part on the head side
            ax.add_patch(Rectangle((-1.25, -2), 2.5, 13, fc=MUTED, ec=INK2, lw=0.4))
            ax.add_patch(Rectangle((-4, 9.2), 8, 2, fc=MUTED, ec=INK2, lw=0.4))
            ax.add_patch(FancyArrowPatch((0, -3), (0, -8), arrowstyle='<-', mutation_scale=9, color=INK, lw=1))
            note = 'only the clinch holds:\npushout 300 N\n(SS-M5-0 in 5052, avg.)'
        ax.text(0, -15, note, fontsize=7, color=INK, ha='center', va='top')
        ax.set_xlim(-16, 16)
        ax.set_ylim(-26, 18)
        ax.set_title(title, fontsize=8, color=INK, loc='left')
        ax.text(0, 16.5, 'arrow: the force on the nut', fontsize=6.5, color=MUTED, ha='center')
    fig.text(0.70, 0.94, 'PennEngineering: "Install from opposite side so that the fastener load is toward sheet."',
             fontsize=7.5, color=INK2)
    _save(fig, 'fig-pem-rules.png')


# --------------------------------------------------------------------------------------------- probe

def fig_probe():
    p = S['scs_price_probes']
    if not p:
        return
    fig = _fig(9.5, 2.9)
    ax = fig.add_axes([0.08, 0.2, 0.88, 0.62])
    _style(ax)
    steps = [('flat plate,\n4 holes', p['flat'], 0), ('+ 2 bends', p['two_bends'] - p['flat'], p['flat']),
             ('4 PEM nuts\ninstead of holes', p['four_pem'] - p['flat'], p['flat']),
             ('+ 8 more\nPEM nuts', p['twelve_pem'] - p['four_pem'], p['four_pem'])]
    for i, (lab, v, base) in enumerate(steps):
        ax.bar(i, v, bottom=base, color=OPT['today'] if i == 0 else OPT['A'], width=0.6, edgecolor=SURFACE, linewidth=2)
        ax.text(i, base + v + 0.8, f"${base + v:.2f}" if i == 0 else f"+${v:.2f}", ha='center', va='bottom', fontsize=8.5, color=INK)
    ax.set_xticks(range(len(steps)))
    ax.set_xticklabels([s[0] for s in steps], fontsize=8, color=INK)
    ax.set_ylim(0, 50)
    ax.set_ylabel('USD', fontsize=8, color=INK2)
    ax.grid(axis='y', color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.set_title(f"What a bend and a PEM nut cost: a 200 x 150 mm plate of 1/8 in 5052, qty 1 (SendCutSend, {p['read_on']}). "
                 f"About ${p['per_pem_usd']:.2f} a nut after a ${p['hardware_setup_usd']:.2f} setup per part",
                 fontsize=9, color=INK, loc='left')
    _save(fig, 'fig-probe.png')


if __name__ == '__main__':
    fig_sections()
    fig_cost()
    fig_counts()
    fig_fea()
    fig_joints()
    fig_pem_rules()
    fig_probe()
