#!/usr/bin/env python3
"""The before/after chart of issue #29's re-run (research/fea-v060-29/comparison.json): each regenerated study with a
target, the safety factor its record judges it on (the turret's printed parts: the layer-aware SF; otherwise the gate
SF), over its target, on the committed record (cad-agent v0.4.2) and on the re-run (v0.6.0).

    python research/fea-v060-29/figure.py        # needs matplotlib; writes sf-before-after.png
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

HERE = Path(__file__).resolve().parent
INK, INK2, MUTED, GRID, SURFACE = '#0b0b0b', '#52514e', '#8a8984', '#e6e5e1', '#fcfcfb'
# one hue, two ordinal steps (before light, after dark); below-target in the status red, always with its label
BEFORE, AFTER, FAIL = '#86b6ef', '#1c5cab', '#d03b3b'


def main():
    c = json.loads((HERE / 'comparison.json').read_text())
    rows = [r for r in c['rows'] if r.get('target') and 'sf_before' in r and r['after_kind'] == 're-run']
    for r in rows:
        r['b'] = (r['verdict_sf_before'] if r.get('verdict_sf_before') is not None else r['sf_before']) / r['target']
        r['a'] = (r['verdict_sf_after'] if r.get('verdict_sf_after') is not None else r['sf_after']) / r['target']
    order = {'leg': 0, 'turret': 1}
    rows.sort(key=lambda r: (order.get(r['record'], 2), -min(r['a'], 9)))
    n = len(rows)
    fig, ax = plt.subplots(figsize=(9.5, 0.24 * n + 1.6), dpi=130)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ax.set_xscale('log')
    lo, hi = 0.4, 16
    ax.set_xlim(lo, hi)
    ax.axvline(1.0, color=INK2, lw=1, zorder=1)
    for i, r in enumerate(rows):
        y = n - 1 - i
        b, a = r['b'], r['a']
        ax.plot([min(b, hi), min(a, hi)], [y, y], color=GRID, lw=2, zorder=2, solid_capstyle='round')
        ax.scatter([min(b, hi)], [y], s=26, color=BEFORE, zorder=3, edgecolor=SURFACE, linewidth=1.5)
        ax.scatter([min(a, hi)], [y], s=30, color=FAIL if a < 1 else AFTER, zorder=4, edgecolor=SURFACE, linewidth=1.5)
        if (a < 1) != (b < 1):
            note = f"{b * r['target']:.2f} -> {a * r['target']:.2f} (target {r['target']:g})"
            ax.text(min(max(a, b), hi) * 1.08, y, note, fontsize=7, color=INK2, va='center')
    ax.set_yticks(range(n))
    ax.set_yticklabels([f"{r['record'][:6]}  {r['part']} {r['case']}" for r in reversed(rows)], fontsize=7, color=INK)
    ax.set_ylim(-0.7, n - 0.3)
    ax.set_xticks([0.5, 0.75, 1, 1.5, 2, 3, 5, 10])
    ax.set_xticklabels(['0.5', '0.75', '1', '1.5', '2', '3', '5', '10'], fontsize=8, color=INK2)
    ax.set_xlabel('safety factor / target, log scale; under 1 misses its target. Turret printed parts: the layer-aware '
                  'SF its record judges them on', fontsize=8, color=INK2)
    ax.grid(axis='x', color=GRID, lw=0.6, zorder=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.set_title('Gyropup FEA records: cad-agent v0.4.2 (record) to v0.6.0 (re-run, issue #29)', fontsize=10,
                 color=INK, loc='left', pad=12)
    handles = [Line2D([], [], marker='o', ls='', color=BEFORE, label='record, v0.4.2'),
               Line2D([], [], marker='o', ls='', color=AFTER, label='re-run, v0.6.0'),
               Line2D([], [], marker='o', ls='', color=FAIL, label='re-run, below target')]
    ax.legend(handles=handles, loc='lower right', fontsize=7, frameon=False, labelcolor=INK2)
    fig.tight_layout()
    fig.savefig(HERE / 'sf-before-after.png', facecolor=SURFACE)
    print('wrote', HERE / 'sf-before-after.png', n, 'studies')


if __name__ == '__main__':
    main()
