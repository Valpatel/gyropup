"""Build the body (milestone M5): the frame's parts for SendCutSend (formed STEP + flat DXF with bend lines, material and
thickness in the file names), the printed parts (STEP + print-ready STL), the assembly with both legs, a clash sweep of
the body against both legs over their whole range, the parts' masses, the print plan, the SendCutSend cart and pictures.

    .venv/bin/python cad/build_body.py [--no-render] [--no-clash] [--quick]

Writes exports/body/: body.json (numbers, interface, sheet orders and rule checks, clash sweep, masses),
sendcutsend/<part>_<material>_<thickness>_x<qty>.{step,dxf}, <printed part>.{step,stl}, body_stand.step (the frame
and both legs at 300 mm, motors as envelopes), print-plan.json, *.png.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
import time
from pathlib import Path

import cadquery as cq

R = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / 'cad'))
import body_frame as bf  # noqa: E402
import body_params as bp  # noqa: E402
import printplan  # noqa: E402
from cadagent.geometry import export_print_stl  # noqa: E402
from cadagent.robot import solid_mass_properties  # noqa: E402

OUT = R / 'exports' / 'body'
SCS = OUT / 'sendcutsend'
MATERIALS = json.loads((R / 'catalog/materials.json').read_text())

# leg parts fixed to the hip frame (checked against the body once); the rest move
STATIC = ('hip_frame', 'output_adapter', 'motor_', 'bearing_61812', 'stop_', 'screws_lugs')


def _v(s):
    return s.val() if hasattr(s, 'val') else s


def _layout():
    """The layout (cad/body_layout.py): its items as shapes for the pictures and the clash sweep."""
    import body_layout as bl
    L = bl.layout()
    items = []
    for it in L['items']:
        if it.keepout:
            continue
        x0, x1, y0, y1, z0, z1 = it.box
        if it.cyl:
            cx, cy, r = it.cyl
            shape = bf.cyl_z(r, z0, z1, cx, cy)
        else:
            shape = bf.box(x0, x1, y0, y1, z0, z1)
        items.append({'name': it.name, 'shape': shape, 'rgb': it.rgb, 'mass_g': it.mass_g, 'group': it.group, 'stage': it.stage})
    return {'items': items, 'mounts': L['mounts'], 'checks': bl.check(L['items'], bl.frame_boxes()), 'cell': L['cell'],
            'raw': L}


def sheet_file_stem(p) -> str:
    s = p.sheet.s
    mat = s['material'].split()[0]
    return f"{p.sheet.name}_{mat}_{s['t_in']:.3f}in_x{p.sheet.qty}"


def mass_g(p) -> float:
    if p.kind == 'sheet':
        dens = bp.STOCK[{'C110 copper': 'C110-0.125'}.get(p.material, None) or next(k for k, v in bp.STOCK.items() if v['material'] == p.material)]['density']
        return solid_mass_properties(_v(p.local), dens, 1.0, p.name).mass * 1000
    if p.kind == 'printed':
        return solid_mass_properties(_v(p.shape), MATERIALS[p.material]['density_g_cm3'], 1.0, p.name).mass * 1000
    return p.mass_g or 0.0


def cheek_holes_robot(parts):
    """The cheeks' frame holes in the robot frame (on each cheek's outer face)."""
    cp = parts['cheek_left'].sheet
    m = bp.frame_mounts()
    out = {}
    for side in ('left', 'right'):
        pts = []
        for f in cp.features:
            if f.kind == 'hole' and f.note.startswith('hip frame'):
                u, v = f.at
                x, z = bp.SPINE_X[1] - u, v - bf.ZT
                pts.append((x, bf.FACE_Y, z) if side == 'left' else (-x, -bf.FACE_Y, z))
        out[side] = [tuple(round(c, 3) for c in p) for p in pts]
    assert len(out['left']) == len(m['holes'])
    return out


# ------------------------------------------------------------------------------------------- the clash sweep

def poses(quick=False):
    hs = (102, 130, 200, 300, 392) if quick else (102, 110, 130, 160, 200, 240, 280, 300, 320, 350, 380, 392)
    out = []
    for h in hs:
        for lean in ((-20.0, 0.0, 20.0) if 200 <= h <= 340 else (0.0,)):
            out.append((float(h), lean))
    return out


def in_range(h, lean):
    fb = bp._fivebar()
    phi = fb.stance(h, lean)
    if phi is None:
        return None
    fo, fi, ro, ri = fb.stop_angles()
    tol = 1e-6
    if not (fi - tol <= phi[0] <= fo + tol and ro - tol <= phi[1] <= ri + tol):
        return None
    return phi


def body_shapes(parts, items=None):
    out = {n: _v(p.shape) for n, p in parts.items() if p.shape is not None}
    for it in (items or []):
        if it.get('shape') is not None:
            out[f'item.{it["name"]}'] = _v(it['shape'])
    return out


def clash_sweep(parts, items=None, quick=False, min_mm3=1.0, near_mm=12.0):
    """Every leg part (both legs) against every body part at each stance: intersections over min_mm3, and the nearest
    approach of the moving parts to the body (measured where their boxes come within near_mm)."""
    body = body_shapes(parts, items)
    bboxes = {n: s.BoundingBox() for n, s in body.items()}
    clashes, near, checked, skipped = [], {}, [], []
    first = True
    for h, lean in poses(quick):
        if in_range(h, lean) is None:
            skipped.append([h, lean])
            continue
        legs = bf.legs(h, lean)
        checked.append([h, lean])
        for ln, ls in legs.items():
            static = ln.split('.', 1)[1].startswith(STATIC)
            if static and not first:
                continue
            lv = _v(ls)
            lb = lv.BoundingBox()
            for bn, bv in body.items():
                bb = bboxes[bn]
                if (lb.xmax < bb.xmin - near_mm or bb.xmax < lb.xmin - near_mm or lb.ymax < bb.ymin - near_mm or bb.ymax < lb.ymin - near_mm
                        or lb.zmax < bb.zmin - near_mm or bb.zmax < lb.zmin - near_mm):
                    continue
                try:
                    vol = lv.intersect(bv).Volume()
                except Exception:
                    vol = 0.0
                if vol > min_mm3:
                    clashes.append([ln, bn, round(vol, 1), [h, lean]])
                    continue
                if not static:
                    try:
                        d = lv.distance(bv)
                    except Exception:
                        continue
                    key = (ln.split('.', 1)[1], bn)
                    if key not in near or d < near[key][0]:
                        near[key] = (round(d, 2), [h, lean])
        first = False
    worst = sorted(([a, b, d, p] for (a, b), (d, p) in near.items()), key=lambda r: r[2])[:20]
    return {'poses_checked': checked, 'poses_past_a_stop': skipped, 'clashes': clashes, 'nearest_moving_mm': worst,
            'note': 'both legs (the right one is the left turned 180 deg about z), motors as envelopes; intersections over '
                    f'{min_mm3} mm3 are clashes; nearest approaches of the moving leg parts to the body within {near_mm} mm'}


def body_internal_clashes(parts, items=None, min_mm3=1.0):
    """Body parts against each other (everything is placed to touch at most)."""
    body = body_shapes(parts, items)
    bbs = {n: s.BoundingBox() for n, s in body.items()}
    out = []
    for (a, sa), (b, sb) in itertools.combinations(body.items(), 2):
        A, B = bbs[a], bbs[b]
        if A.xmax < B.xmin or B.xmax < A.xmin or A.ymax < B.ymin or B.ymax < A.ymin or A.zmax < B.zmin or B.zmax < A.zmin:
            continue
        try:
            vol = sa.intersect(sb).Volume()
        except Exception:
            vol = 0.0
        if vol > min_mm3:
            out.append([a, b, round(vol, 1)])
    return out


def frame_vs_legs_static(parts):
    """The hip frames against the cheeks: they must touch (face to face), not overlap."""
    legs = bf.legs(300.0)
    out = []
    for side, tag in (('left', 'L'), ('right', 'R')):
        hf = _v(legs[f'{tag}.hip_frame'])
        ch = _v(parts[f'cheek_{side}'].shape)
        out.append({'side': side, 'overlap_mm3': round(hf.intersect(ch).Volume(), 2), 'gap_mm': round(hf.distance(ch), 3)})
    return out


# ------------------------------------------------------------------------------------------- pictures

COL = {'cheek': (0.72, 0.75, 0.80), 'floor_tray': (0.62, 0.66, 0.72), 'belly_plate': (0.55, 0.58, 0.64), 'deck': (0.24, 0.26, 0.30),
       'compute_pallet': (0.70, 0.72, 0.76), 'post': (0.30, 0.32, 0.35), 'riser': (0.30, 0.32, 0.35), 'spacers': (0.85, 0.85, 0.87),
       'screw': (0.12, 0.12, 0.14), 'nuts': (0.55, 0.55, 0.57)}
LEG_COL = {'hip_frame': (0.40, 0.43, 0.48), 'output_adapter': (0.62, 0.65, 0.70), 'upper_link': (0.96, 0.72, 0.16),
           'front_link': (0.96, 0.72, 0.16), 'wheel_link': (0.93, 0.60, 0.12), 'motor': (0.17, 0.18, 0.2), 'wheel_tyre': (0.1, 0.1, 0.11),
           'wheel_hub': (0.3, 0.32, 0.35), 'stop_sleeve': (0.85, 0.22, 0.2)}


def colour(n):
    k = n.split('.', 1)[-1]
    for key, c in {**COL, **LEG_COL}.items():
        if k.startswith(key) or (key == 'screw' and 'screw' in k) or (key == 'nuts' and 'nuts' in k):
            return c
    return (0.6, 0.6, 0.6)


def render(parts, items, out: Path):
    from cadagent.render import Renderer
    r = Renderer(out, subtitle='GYROPUP BODY P1 | OPEN FRAME, BOTH LEGS')
    made = []
    legs = bf.legs(300.0)
    body = [(_v(p.shape), p.colour if p.colour else colour(n)) for n, p in parts.items() if p.shape is not None]
    its = [(_v(it['shape']), it.get('rgb', (0.5, 0.55, 0.6))) for it in (items or []) if it.get('shape') is not None]
    legsh = [(_v(s), colour(n)) for n, s in legs.items()]
    views = {'iso': (1.0, -1.05, 0.8), 'front': (1.0, 0.0, 0.12), 'side': (0.0, -1.0, 0.1), 'top': (0.0, 0.0, 1.0), 'rear': (-0.9, 0.9, 0.6)}
    for v in ('iso', 'front', 'side', 'rear'):
        r.render(f'body-p1-{v}.png', shapes=body + its + legsh, view=views[v], caption=f'P1 open frame with both legs at 300 mm, {v}')
        made.append(f'body-p1-{v}.png')
    r.render('body-frame-iso.png', shapes=body + its, view=views['iso'], caption='The frame alone: cheeks, tray, belly plate, deck on posts, riser')
    made.append('body-frame-iso.png')
    spine = [(_v(parts[n].shape), parts[n].colour) for n in parts if n.startswith(('cheek', 'spacer', 'frame_screws', 'cheek_nuts'))]
    hf = [(_v(s), colour(n)) for n, s in legs.items() if n.split('.', 1)[1].startswith(('hip_frame', 'motor', 'output_adapter', 'bearing'))]
    r.render('body-spine-iso.png', shapes=spine + hf, view=(0.9, -1.1, 0.7), caption='The spine: two C-channel cheeks on six standoffs, each hip frame on its own cheek')
    made.append('body-spine-iso.png')
    for h, tag in ((102, 'crouch'), (392, 'tall')):
        lg = bf.legs(float(h))
        r.render(f'body-p1-{tag}-side.png', shapes=body + its + [(_v(s), colour(n)) for n, s in lg.items()], view=views['side'],
                 caption=f'P1 with the legs at {h} mm ({tag})')
        made.append(f'body-p1-{tag}-side.png')
    return made


def render_flats(parts, out: Path):
    """Each sheet part's flat pattern as a picture (matplotlib), from its DXF geometry."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import ezdxf
    made = []
    for n, p in parts.items():
        if p.kind != 'sheet' or n == 'cheek_right' or p.sheet is None:
            continue
        f = SCS / f'{sheet_file_stem(p)}.dxf'
        doc = ezdxf.readfile(str(f))
        fig, ax = plt.subplots(figsize=(10, 7))
        for e in doc.modelspace():
            c = '#c0392b' if e.dxf.layer == 'BEND' else '#1f2a33'
            ls = '--' if e.dxf.layer == 'BEND' else '-'
            if e.dxftype() == 'LINE':
                ax.plot([e.dxf.start.x, e.dxf.end.x], [e.dxf.start.y, e.dxf.end.y], c, ls=ls, lw=1)
            elif e.dxftype() == 'CIRCLE':
                ax.add_patch(plt.Circle((e.dxf.center.x, e.dxf.center.y), e.dxf.radius, fill=False, color=c, lw=0.8))
            elif e.dxftype() == 'ARC':
                import numpy as np
                a0, a1 = math.radians(e.dxf.start_angle), math.radians(e.dxf.end_angle)
                if a1 < a0:
                    a1 += 2 * math.pi
                t = np.linspace(a0, a1, 24)
                ax.plot(e.dxf.center.x + e.dxf.radius * np.cos(t), e.dxf.center.y + e.dxf.radius * np.sin(t), c, lw=1)
        o = p.sheet.order()
        ax.set_aspect('equal')
        ax.set_title(f"{p.sheet.name}: {o['material']} {o['thickness_in']} in, flat {o['flat_mm'][0]} x {o['flat_mm'][1]} mm, "
                     f"{o['bends']} bends, PEM {o['hardware'] or '-'}, x{o['qty']}", fontsize=10)
        ax.set_xlabel('mm (dashed red: bend centrelines)')
        fig.tight_layout()
        fig.savefig(out / f'flat-{p.sheet.name}.png', dpi=110)
        plt.close(fig)
        made.append(f'flat-{p.sheet.name}.png')
    return made


# ------------------------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-render', action='store_true')
    ap.add_argument('--no-clash', action='store_true')
    ap.add_argument('--quick', action='store_true', help='fewer stances in the clash sweep')
    a = ap.parse_args()
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    SCS.mkdir(parents=True, exist_ok=True)
    lay = _layout()
    mounts = lay['mounts'] if lay else None
    items = lay['items'] if lay else []
    parts = bf.frame_parts(mounts)
    sheet, plan, masses = {}, {}, {}
    printed_done = {}
    for n, p in parts.items():
        masses[n] = round(mass_g(p), 1)
        if p.kind == 'sheet':
            if n == 'cheek_right' or p.sheet is None:
                continue
            stem = sheet_file_stem(p)
            cq.exporters.export(_v(p.local), str(SCS / f'{stem}.step'))
            p.sheet.export_dxf(SCS / f'{stem}.dxf')
            o = p.sheet.order()
            sheet[p.sheet.name] = {**o, 'rule_violations': p.sheet.checks(), 'step': f'exports/body/sendcutsend/{stem}.step',
                                   'dxf': f'exports/body/sendcutsend/{stem}.dxf', 'mass_g_each': masses[n],
                                   'features': len(p.sheet.features)}
        elif p.kind == 'printed':
            base = n.rstrip('0123456789').rstrip('_')
            if base in printed_done:
                printed_done[base]['qty'] += 1
                continue
            printed_done[base] = {'qty': 1, 'part': p, 'name': n}
    for base, d in printed_done.items():
        p = d['part']
        local = bf.post() if base == 'post' else bf.riser() if base == 'riser' else bf.bus_insulator() if base == 'bus_insulator' else _v(p.shape)
        cq.exporters.export(_v(local), str(OUT / f'{base}.step'))
        export_print_stl(_v(local), OUT / f'{base}.stl', rotation=p.print_rotation)
        plan[base] = printplan.row(_v(local), p.print_rotation, p.material, d['qty'], masses[d['name']], p.material == 'pa6-cf', p.note)
    too_big = printplan.write(OUT / 'print-plan.json', plan, note='body P1: hours are rough (grams / density / a strength-holding rate)')
    legs = bf.legs(300.0)
    comp = cq.Compound.makeCompound([_v(p.shape) for p in parts.values() if p.shape is not None] + [_v(s) for s in legs.values()]
                                    + [_v(it['shape']) for it in items if it.get('shape') is not None])
    cq.exporters.export(comp, str(OUT / 'body_stand.step'))
    summary = {
        'numbers': bp.summary(),
        'interface': {'cheek_holes': cheek_holes_robot(parts), 'frame_mounts': {k: v for k, v in bp.frame_mounts().items() if k != 'key'},
                      'frame_screw': bp.FRAME_SCREW, 'frame_to_cheek': frame_vs_legs_static(parts),
                      'harness_exits': [[n, [round(v, 1) for v in e], round(ang, 1)] for n, e, ang in bf.harness_windows()],
                      'cheek_windows': bf.cheek_windows()},
        'sheet': sheet,
        'print': {'too_big': too_big, 'hours': round(sum(p['hours'] for p in plan.values()), 1), 'parts': plan},
        'mass_g': {'frame_parts': masses, 'frame_total': round(sum(masses.values()), 1)},
        'internal_clashes': body_internal_clashes(parts, items),
    }
    if not a.no_clash:
        summary['clash_sweep'] = clash_sweep(parts, items, quick=a.quick)
    if lay:
        import body_layout as bl
        summary['layout'] = {'checks': lay['checks'], 'cell': lay['cell'],
                             'items': [{'name': i.name, 'box': [round(v, 2) for v in i.box], 'mass_g': i.mass_g, 'basis': i.basis, 'group': i.group,
                                        'stage': i.stage, 'catalog': i.catalog, 'note': i.note, 'keepout': i.keepout}
                                       for i in lay['raw']['items']]}
        led = {st: bl.ledger(lay['raw'], parts, stage=st) for st in ('P1', 'P3')}
        (OUT / 'mass.json').write_text(json.dumps(led, indent=1) + '\n')
        summary['mass'] = {st: {k: v for k, v in d.items() if k != 'rows'} for st, d in led.items()}
    if not a.no_render:
        summary['pictures'] = render(parts, items, OUT) + render_flats(parts, OUT)
    (OUT / 'body.json').write_text(json.dumps(summary, indent=1, default=str) + '\n')
    print(f"body: frame {summary['mass_g']['frame_total'] / 1000:.2f} kg; track {bp.track():.2f} mm; spine top z {bf.ZT}")
    for n, s in sheet.items():
        print(f"  {n:15} {s['material']:20} {s['thickness_in']} in x{s['qty']}  flat {s['flat_mm']}  bends {s['bends']}  "
              f"PEM {s['hardware']}  csk {s['countersinks']}  {s['mass_g_each']:.0f} g  rules: {s['rule_violations'] or 'ok'}")
    for n, p in plan.items():
        print(f"  {n:15} x{p['qty']} {p['material']} {p['grams_each']} g {p['size_mm']} {p['placement']} {p['hours']} h")
    print('  frame to cheek:', summary['interface']['frame_to_cheek'])
    print('  internal clashes:', summary['internal_clashes'] or 'none')
    if 'clash_sweep' in summary:
        c = summary['clash_sweep']
        print(f"  clash sweep: {len(c['poses_checked'])} stances, {len(c['clashes'])} clashes", *[f'    {x}' for x in c['clashes'][:20]], sep='\n')
        print('  nearest:', *[f'    {x}' for x in c['nearest_moving_mm'][:8]], sep='\n')
    print(f'  {time.time() - t0:.0f} s')


if __name__ == '__main__':
    main()
