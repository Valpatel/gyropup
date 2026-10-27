"""How printed parts go on the bed: size in print orientation, whether they fit (straight or turned), grams, hours, cost.

    row = printplan.row(solid, rotation, 'pa6-cf', qty=2, solid_fill=True, mass_g=..., how='...')
    printplan.write(path, {name: row, ...})
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import cadquery as cq

import gmi

R = Path(__file__).resolve().parents[1]
BED = gmi.STD['print']['bed_mm']
MATERIALS = json.loads((R / 'catalog/materials.json').read_text())
# volumetric rates that hold strength (0.4 mm hardened nozzle; PA6-CF slower), with travel and walls: rough hours
RATE_CM3_H = {'pa6-cf': 14.0, 'petg': 20.0, 'tpu95': 8.0, 'pla': 24.0}
MARGIN = 6.0


def fits(solid, rotation=None):
    """(size_mm sorted, 'straight' | 'turned' | 'TOO BIG'): the part's real outline is turned on the bed until it fits."""
    s = solid
    if rotation:
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(*rotation[0]), rotation[1])
    bb = s.BoundingBox()
    dx, dy = sorted((bb.xlen, bb.ylen), reverse=True)
    dz = bb.zlen
    if dz > BED[2] - MARGIN:
        return [round(dx), round(dy), round(dz)], 'TOO BIG'
    if dx <= BED[0] - MARGIN and dy <= BED[1] - MARGIN:
        return [round(dx), round(dy), round(dz)], 'straight'
    import numpy as np
    verts, _ = s.tessellate(2.0, 0.5)
    xy = np.array([(v.x, v.y) for v in verts])
    for a in np.radians(np.arange(0.0, 90.0, 1.0)):
        c, sn = math.cos(a), math.sin(a)
        w, h = np.ptp(xy @ np.array([[c, -sn], [sn, c]]), axis=0)
        if w <= BED[0] - MARGIN and h <= BED[1] - MARGIN:
            return [round(dx), round(dy), round(dz)], 'turned'
    return [round(dx), round(dy), round(dz)], 'TOO BIG'


def row(solid, rotation, material, qty, mass_g, solid_fill=True, how=''):
    size, placement = fits(solid, rotation)
    dens = MATERIALS[material]['density_g_cm3']
    grams = mass_g * qty
    return {'material': material, 'qty': qty, 'size_mm': size, 'fits': placement != 'TOO BIG', 'placement': placement,
            'grams_each': round(mass_g), 'grams': round(grams), 'hours': round(grams / dens / RATE_CM3_H.get(material, 15.0), 1),
            'cost_usd': round(grams / 1000 * MATERIALS[material].get('price_usd_per_kg', 30.0), 2),
            'infill': '100 %' if solid_fill else '2 mm walls, 40 % gyroid', 'how': how}


def write(path: Path, plan: dict, note: str = ''):
    by_mat = {}
    for r in plan.values():
        t = by_mat.setdefault(r['material'], {'grams': 0, 'hours': 0.0, 'cost_usd': 0.0, 'parts': 0})
        t['grams'] += r['grams']
        t['hours'] = round(t['hours'] + r['hours'], 1)
        t['cost_usd'] = round(t['cost_usd'] + r['cost_usd'], 2)
        t['parts'] += r['qty']
    too_big = [n for n, r in plan.items() if not r['fits']]
    Path(path).write_text(json.dumps({'bed_mm': BED, 'parts': plan, 'by_material': by_mat, 'too_big': too_big,
                                      'total_hours': round(sum(t['hours'] for t in by_mat.values()), 1),
                                      'total_grams': sum(t['grams'] for t in by_mat.values()),
                                      'note': note or 'hours are rough: grams / material density / a strength-holding volumetric rate'},
                                     indent=1) + '\n')
    return too_big
