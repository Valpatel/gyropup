"""Separate C3 support candidate, millimetres in turret frame T.

This is an opt-in engineering candidate, not the default turret or a released
print. Original PCB/retainer stacks remain unchanged. Supplier CAD is only loaded
by explicit private=True requests and is never returned by public_parts().
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import cadquery as cq
import turret_base_board as bb

ROOT = Path(__file__).resolve().parents[1]
HARDWARE_RECORD = ROOT / 'research/carrier-service-connectors/support-hardware-catalog.json'
HOLES = ((-10., 10.), (10., 10.))  # Y/Z; separate from all original holes
FLANGE_X = (56., 58.)
NUT_X = (50.6, 53.)
PILOT_CLEAR_MM = 3.4
NUT_POCKET_AF_MM = 5.7  # design +0.2 mm AF; printed fit is unmeasured
NUT_BOSS_RADIUS_MM = 4.0
PANEL_Y = (-8.51, -6.51)  # raw plug stop Y=-0.065, transformed by -8.445
POST_Y = ((-26., -12.), (4., 18.))
POST_X = (56., 61.5)
POST_Z = (13.99, 56.)
RAIL_Z = (48., 56.)
PUBLIC_NOTE = 'Independently authored dimension representation; not manufacturer CAD; no threads or flexible clip geometry.'


def hex_prism(af, length, origin):
    """Normalised +Z hex rotated onto +X: flats parallel to turret Y."""
    return (cq.Workplane('XY').polygon(6, af/math.cos(math.pi/6)).extrude(length)
            .rotate((0,0,0),(0,1,0),90).translate(origin))


def carrier():
    """Add two inward-open nut pockets without altering the original mount stacks."""
    s = bb.carrier()
    for y,z in HOLES:
        s = s.union(bb.cx(NUT_BOSS_RADIUS_MM, 50.2, 53.01, y,z))
        s = s.cut(hex_prism(NUT_POCKET_AF_MM, 2.900001, (50.1,y,z)))
        s = s.cut(bb.cx(PILOT_CLEAR_MM/2, 52.99, 56.1, y,z))
    return s


def panel_cutout():
    """SDA-43020 rev G nominal 12-way cutout, authored from the drawing.

    Body width C=19.20 maps to Z; side steps D=22.89 map to Z; the key
    protrudes toward +X (raw -Z). Nominal dimensions, not an enlarged fit waiver.
    Sharp corners satisfy R <= 0.18 but print radius/tolerance remain unqualified.
    """
    y0,y1 = PANEL_Y[0]-.1,PANEL_Y[1]+.1
    s = bb.box(84.-7.11/2,84.+7.11/2,y0,y1,34.-19.20/2,34.+19.20/2)
    s = s.union(bb.box(84.-4.06/2,84.+4.06/2,y0,y1,34.-22.89/2,34.+22.89/2))
    return s.union(bb.box(84.+7.11/2,84.-7.11/2+8.71,y0,y1,34.-1.98/2,34.+1.98/2))


def support(*, cutout=True):
    """One connected frame. Two mm is local grip/panel, not the cantilever depth.

    Top rails are 14 x 8 mm; uprights 5.5 x 14 mm. They deliberately avoid the
    existing C2 straight exits at Y20/23. Strength, creep and print orientation
    still need qualification; no thin-section approval follows from clear CAD.
    """
    s = bb.box(*FLANGE_X,-27.,19.,6.,14.)
    for y0,y1 in POST_Y:
        s = s.union(bb.box(*POST_X,y0,y1,*POST_Z))
        s = s.union(bb.box(56.,93.,y0,y1,*RAIL_Z))
    s = s.union(bb.box(77.,93.,-26.,18.,*RAIL_Z))
    panel = bb.box(77.,93.,*PANEL_Y,20.5,56.)
    if cutout:
        panel = panel.cut(panel_cutout())
    s = s.union(panel)
    for y,z in HOLES:
        s = s.cut(bb.cx(PILOT_CLEAR_MM/2,55.9,58.1,y,z))
    return s


def public_nut():
    """Authored DIN934 nominal AF5.5 x 2.4; minor bore is a thread envelope."""
    return cq.Workplane('XY').polygon(6,5.5/math.cos(math.pi/6)).extrude(2.4).cut(
        cq.Workplane('XY').circle(1.25).extrude(2.4))


def private_model(pn):
    entries = json.loads(HARDWARE_RECORD.read_text())
    entry = next(e for e in entries if e['model']==pn)
    relative = entry['cad']['file']
    path = (ROOT / relative).resolve()
    if not path.is_relative_to((ROOT / 'references/vendor').resolve()):
        raise ValueError('Private hardware input escapes vendor directory')
    if not path.is_file():
        raise FileNotFoundError('Exact manufacturer input missing: '+pn)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['private_file_sha256'][relative]:
        raise ValueError('Exact manufacturer input changed: '+pn)
    s = cq.importers.importStep(str(path))
    if not s.val().isValid() or len(s.val().Solids())!=1:
        raise ValueError('Invalid manufacturer solid: '+pn)
    return s


def hardware(*, private=False):
    screw = private_model('91290A113') if private else bb.public_screw(8.)
    nut = private_model('90592A085') if private else public_nut()
    result = {}
    for i,(y,z) in enumerate(HOLES):
        result[f'c3_support_screws#{i}'] = screw.rotate((0,0,0),(0,1,0),90).translate((58.,y,z))
        result[f'c3_support_nuts#{i}'] = nut.rotate((0,0,0),(0,1,0),90).translate((50.6,y,z))
    return result


def module_members():
    """Exact retained identities; no unallocated wires/pads hidden in a compound."""
    return ['base_board_carrier','base_board','c3_support','C3_module_housing'] + [
        f'{group}#{i}' for group,count in (('base_board_screws',4),('base_board_inserts',4),
                                          ('c3_support_screws',2),('c3_support_nuts',2))
        for i in range(count)] + ['component:'+n for n in bb.components()]


def assembly_order():
    return [
        {'order':1,'fit':'base_board_carrier','note':'Bench; PCB absent.'},
        {'order':2,'fit':'c3_support_nuts','insertion':'+X','note':'Load inward-open pockets before PCB.'},
        {'order':3,'fit':'c3_support','insertion':'-X','fasteners':['c3_support_screws'],
         'note':'Hold nuts from the inward face until screws engage; screws and nuts remain with module.'},
        {'order':4,'fit':'C3_module_housing','insertion':'+Y',
         'note':'Snap-panel flex/retention unresolved; rigid supplier intersection is recorded, not waived.'},
        {'order':5,'fit':'base_board_inserts','note':'Existing qualified process still requires coupon measurements.'},
        {'order':6,'fit':'base_board','fasteners':['base_board_screws'],
         'note':'PCB prevents straight nut removal after installation; remove PCB first to replace bracket.'},
    ]


def load_screen():
    """Conservative section arithmetic, not a beam/FEA/strength acceptance.

    Supplier 8 N/circuit maximum mating force x12 =96 N. Put the entire load
    on one rail/post to avoid assuming equal sharing. Rectangular torsion uses
    a deliberately simple thin-section approximation, insufficient as an upper
    bound here; the output never establishes structural readiness.
    """
    force = 12*8.
    lever_x = 84.-56.
    lever_z = 34.-10.
    i_post = 5.5*14.**3/12.
    i_rail = 8.*14.**3/12.
    moment_z = force*lever_x
    moment_x = force*lever_z
    post_bending = moment_x*7./i_post
    rail_bending = force*(84.-61.5)*7./i_rail
    post_torsion_estimate = 3*moment_z/(14.*5.5**2)
    return {
        'mating_force_n':force,'unmating_force_max_n':None,
        'mating_source':'PS-43045-001 revision R,6.2 item7:8.0 N/circuit maximum;12 circuits',
        'force_direction':[0.,-1.,0.],'application_mm':[84.,0.,34.],
        'mating_motion':'Fixed receptacle moves -Y toward the supported module plug.',
        'unmating_force_direction':[0.,1.,0.],
        'mount_reference_mm':[56.,0.,10.],'outward_lever_mm':lever_x,'vertical_lever_mm':lever_z,
        'mount_moments_nmm':{'about_Z':-moment_z,'about_X':moment_x},
        'bolt_axis_couple_n':moment_z/(HOLES[1][0]-HOLES[0][0]),
        'bolt_vertical_shear_couple_n':moment_x/(HOLES[1][0]-HOLES[0][0]),
        'bolt_shear_resultant_n_if_direct_load_shared':math.hypot(force/2,moment_x/20.),
        'bolt_reaction_basis':'Static two-point force balance; no assumed friction/preload credit.',
        'post_section_mm':[5.5,14.],'rail_section_mm':[14.,8.],
        'one_post_bending_mpa':post_bending,'one_rail_bending_mpa':rail_bending,
        'one_post_torsion_estimate_mpa':post_torsion_estimate,
        'one_post_equivalent_estimate_mpa':math.sqrt(post_bending**2+3*post_torsion_estimate**2),
        'material':'PA6-CF candidate; no measured directional/moisture/creep allowable assigned',
        'allowable_mpa':None,'structural_readiness':False,
        'limits':['Actual flange contact, load sharing, bolt/printed-bearing stresses and joint stiffness remain unmodelled.',
                  'No stress concentration, panel clip stress, screw preload, nut-seat creep, print porosity or fatigue calculation.',
                  'The torsion approximation is a screening estimate, not a guaranteed conservative stress bound.',
                  'Use conditioned printed material evidence and a complete load/contact model before acceptance.'],
    }


def public_parts():
    return {'carrier_candidate_authored':carrier(),'C3_support_candidate_authored':support(),
            **{'authored_public_'+n:s for n,s in hardware().items()}}
