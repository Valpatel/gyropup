#!/usr/bin/env python3
"""The print package's chart (docs/leg-print-package.md, section 8): each printed leg part's study, its safety factor
over its target on dev's record (before) and on the print-ready re-run (now), for the isotropic gate and for the layer
check. The rows are screen.py's final_record, so the chart and the table read the same evidence.

    python research/leg-preprint/figure.py      # needs matplotlib; writes docs/img/leg-print-ready-sf.png
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import NullLocator  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import screen  # noqa: E402

OUT = screen.ROOT / 'docs/img/leg-print-ready-sf.png'
INK, INK2, GRID, SURFACE = '#0b0b0b', '#52514e', '#e6e5e1', '#fcfcfb'
# one hue, two ordinal steps (before light, now dark); a "now" under target in the status red, named in the legend
BEFORE, NOW, FAIL = '#86b6ef', '#1c5cab', '#d03b3b'


def panel(ax, rows, before, now, title):
    n = len(rows)
    lo, hi = 0.2, 4
    ax.set_xscale('log')
    ax.set_xlim(lo, hi)
    ax.axvline(1.0, color=INK2, lw=1, zorder=1)
    for i, r in enumerate(rows):
        y = n - 1 - i
        b, a = r[before] / r['target'], r[now] / r['target']
        ax.plot([min(b, hi), min(a, hi)], [y, y], color=GRID, lw=2, zorder=2, solid_capstyle='round')
        ax.scatter([min(b, hi)], [y], s=26, color=BEFORE, zorder=3, edgecolor=SURFACE, linewidth=1.5)
        ax.scatter([min(a, hi)], [y], s=30, color=FAIL if a < 1 else NOW, zorder=4, edgecolor=SURFACE, linewidth=1.5)
        ax.annotate(f"{r[now]:.2f} / {r['target']:g}", (1.02, y), xycoords=('axes fraction', 'data'), fontsize=6.5,
                    color=INK2, va='center', ha='left', annotation_clip=False)
    ax.set_ylim(-0.7, n - 0.3)
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xticks([0.25, 0.5, 1, 2])
    ax.set_xticklabels(['0.25', '0.5', '1', '2'], fontsize=8, color=INK2)
    ax.grid(axis='x', color=GRID, lw=0.6, zorder=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.set_title(title, fontsize=9, color=INK, loc='left')


def main():
    repo = screen.Repo(screen.ROOT)
    fr = screen.final_record(repo, screen.materials(repo))
    rows = fr['rows']
    n = len(rows)
    fig, (g, lc) = plt.subplots(1, 2, figsize=(10, 0.24 * n + 1.9), dpi=130, sharey=True)
    fig.patch.set_facecolor(SURFACE)
    for ax in (g, lc):
        ax.set_facecolor(SURFACE)
    panel(g, rows, 'gate_before', 'gate_now', 'Isotropic gate (SF / target)')
    panel(lc, rows, 'layer_before', 'layer_now',
          f"Layer check, S_s assumed {fr['S_s_assumed_mpa']:g} MPa (SF / target)")
    g.set_yticks(range(n))
    g.set_yticklabels([f"{r['part']} {r['case']}" for r in reversed(rows)], fontsize=7, color=INK)
    fig.suptitle(f"Leg printed parts: dev's record to print-ready ({fr['source_revision'][:7]}, cad-agent "
                 f"{fr['toolkit']}). Under 1 misses its target; right-hand numbers are now's SF / target",
                 fontsize=9, color=INK, x=0.01, ha='left')
    handles = [Line2D([], [], marker='o', ls='', color=BEFORE, label="before (dev's record)"),
               Line2D([], [], marker='o', ls='', color=NOW, label='now, at target'),
               Line2D([], [], marker='o', ls='', color=FAIL, label='now, under target')]
    fig.legend(handles=handles, loc='lower center', ncol=3, fontsize=7, frameon=False, labelcolor=INK2)
    fig.tight_layout(rect=(0, 0.04, 1, 0.97), w_pad=4)
    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT, facecolor=SURFACE, metadata={'Software': None})
    print('wrote', OUT.relative_to(screen.ROOT), n, 'rows')


if __name__ == '__main__':
    main()
