"""Passive removable base-board carrier; dimensions in turret frame T, millimetres.

Public hardware is independently authored simplified geometry, never a vendor STEP
conversion. ``hardware(private=True)`` is only for local engineering checks and
fails when a requested manufacturer's model is absent. No private models are
returned by the normal turret build or exported by this module.
"""
from __future__ import annotations

from pathlib import Path
import cadquery as cq
from turret_boards import BOARDS, FP

ROOT = Path(__file__).resolve().parents[1]
BOARD_HOLES = tuple((y, z) for y in (-22.4, 22.4) for z in (9.0, 33.0))
CARRIER_HOLES = tuple((y, z) for y in (-31.0, 31.0) for z in (9.0, 33.0))
M3_CLEAR = 3.4
INSERT_PILOT = 4.0  # catalogue maximum hole diameter; printed fit still needs a coupon
INSERT_LENGTH = 5.74  # normalized 94459A140 manufacturer model, nominal 5.7
PUBLIC_NOTE = 'authored simplified hardware; not manufacturer CAD; threads/knurls omitted'
MANUFACTURER_PARTS = ('91290A111', '91290A113', '94459A140')


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane('XY').box(x1-x0, y1-y0, z1-z0).translate(((x0+x1)/2, (y0+y1)/2, (z0+z1)/2))


def cx(radius, x0, x1, y, z):
    return cq.Workplane('XY').add(cq.Solid.makeCylinder(radius, x1-x0, cq.Vector(x0,y,z), cq.Vector(1,0,0)))


def service_base(original):
    """Replace the legacy board wall, retaining the foot and primary joint regions.

    Remove the *whole* old wall above the foot before opening the skirt: otherwise
    its top 0.25 mm becomes a disconnected sliver. The corridor stops below the
    bearing seat at z38 and outside the central tube's radius35.5.
    """
    s = original.cut(box(47.99,56.01,-27.01,27.01,5,38.01))
    s = s.cut(box(36.3,95,-35.25,35.25,5.25,37.75))
    for y in (-31,31):
        s = s.union(box(45,53,y-4,y+4,4.99,37))
    for y,z in CARRIER_HOLES:
        s = s.cut(cx(INSERT_PILOT/2,46.5,53.1,y,z))
    return s


def carrier(_G=None):
    """Print exterior face down (rotate +90 about Y); insert bosses point upward."""
    s = box(53,56,-35,35,5.5,37.5)
    for y,z in BOARD_HOLES:
        s = s.union(cx(3.5,48,53.01,y,z))
        s = s.cut(cx(INSERT_PILOT/2,47.9,54.5,y,z))
    for y,z in CARRIER_HOLES:
        s = s.cut(cx(M3_CLEAR/2,52.9,56.1,y,z))
    return s


def pcb():
    s = box(46.4,48,-25.4,25.4,6,36)
    for y,z in BOARD_HOLES:
        s = s.cut(cx(M3_CLEAR/2,46.3,48.1,y,z))
    return s


def components():
    """Position each footprint from the actual board layout; no shrunken aggregate box.

    These are labelled package/footprint envelopes, not solder or connector models.
    Board-local X maps to turret Y and board-local Y to turret Z.
    """
    out = {}
    for label, footprint, x, y, rotated, _note in BOARDS['base'][4]:
        w,h,tall = footprint[1:] if isinstance(footprint, tuple) else FP[footprint]
        if rotated:
            w,h = h,w
        out[label] = box(46.4-tall,46.4,x-25.4,x+w-25.4,y+6,y+h+6)
    return out


def board():
    s = pcb()
    for c in components().values():
        s = s.union(c)
    return s


def public_screw(length):
    """Authored ISO4762 envelope in the catalogue frame: head +Z, shank -Z."""
    s = cq.Workplane('XY').circle(1.5).extrude(-length).union(cq.Workplane('XY').circle(2.75).extrude(3))
    socket = cq.Workplane('XY').polygon(6,2.5/0.866025403784).extrude(1.4).translate((0,0,1.6))
    return s.cut(socket)


def public_insert():
    return cq.Workplane('XY').circle(2.36).circle(1.25).extrude(INSERT_LENGTH)


def normalized(part_number, private=False):
    if private:
        p = ROOT / f'references/vendor/mcmaster/{part_number}/{part_number}.norm.step'
        if not p.is_file():
            raise FileNotFoundError(f'private manufacturer CAD missing: {part_number}; no silent fallback')
        return cq.importers.importStep(str(p))
    return public_insert() if part_number == '94459A140' else public_screw({'91290A111':6,'91290A113':8}[part_number])


def screw_specs():
    return {
        'base_board_screws': dict(key='screw_m3x6', pn='91290A111', clamps='base_board', into='base_board_inserts',
                                 axes=[((46.4,y,z),(1,0,0)) for y,z in BOARD_HOLES], length_mm=6., thread_start_mm=1.6),
        'base_carrier_screws': dict(key='turret_screw_m3x8', pn='91290A113', clamps='base_board_carrier', into='base_carrier_inserts',
                                   axes=[((56.,y,z),(-1,0,0)) for y,z in CARRIER_HOLES], length_mm=8., thread_start_mm=3.),
    }


def hardware(private=False):
    """Individual instances, either all authored public or all private manufacturer CAD.

    A partial private cache must never quietly create a mixed manufacturer check.
    """
    out = {}
    def load(pn):
        return normalized(pn, private=private)
    for group,spec in screw_specs().items():
        shape = load(spec['pn'])
        for i,(o,d) in enumerate(spec['axes']):
            out[f'{group}#{i}'] = shape.rotate((0,0,0),(0,1,0),-90*d[0]).translate(o)
    ins = load('94459A140')
    for group,holes,x,angle in (('base_board_inserts',BOARD_HOLES,48,90),('base_carrier_inserts',CARRIER_HOLES,53,-90)):
        for i,(y,z) in enumerate(holes):
            out[f'{group}#{i}'] = ins.rotate((0,0,0),(0,1,0),angle).translate((x,y,z))
    return out


def public_parts():
    hw = hardware()
    groups = {}
    for group in ('base_board_screws','base_carrier_screws','base_board_inserts','base_carrier_inserts'):
        groups[group] = cq.Workplane('XY').add(cq.Compound.makeCompound([s.val() for n,s in hw.items() if n.startswith(group+'#')]))
    return groups
