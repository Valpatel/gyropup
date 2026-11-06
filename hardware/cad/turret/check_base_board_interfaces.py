"""Bounded candidate space checks; explicitly not a complete harness qualification."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time
from dataclasses import replace

ROOT=Path(__file__).resolve().parents[1]
import print_provenance as provenance
# Capture the complete CAD/config/catalog closure before geometry imports read it.
IMPORTED_INPUTS=provenance.snapshot(ROOT)
import cadquery as cq
import OCP
from cadagent.gates import Tolerances, relate
from cadagent.gates.relations import RELATIONS_VERSION
import turret as tu
import turret_base_board as bb
import turret_carrier_interfaces as ci

CLEARANCE_VOLUME_MM3=1e-6
# Preserve the original total1e-6 symmetric-difference allowance by allocating
# just under half to each outside volume (the former sum used strict '<').
# Uncertainty consumes these budgets in relate().
TOL=Tolerances(overlap_mm3=CLEARANCE_VOLUME_MM3,
               contain_mm3=math.nextafter(CLEARANCE_VOLUME_MM3/2,0.))
RELATION_EVIDENCE=[]


def body(kind,side,travel=0.):
    c=ci.POWER if kind=='power' else ci.SIGNAL
    x,z=c['centre_xz_mm']; dx,dz=c.get('body_xz_mm',c.get('reservation_xz_mm'))
    y0,y1=c['source_body_y_mm'] if side=='fixed' else c['module_body_y_mm']
    return bb.box(x-dx/2,x+dx/2,y0+travel,y1+travel,z-dz/2,z+dz/2)


def overlap(a,b):
    """Thresholded interference; doubtful topology/numerics can never become zero.

    This is not raw common volume. Zero means the reviewed relation predicate
    found apart/touching under the declared threshold. Full numerical witnesses
    are retained in the receipt. No unvalidated supplied volumes are passed in.
    """
    r=relation(a,b)
    if r.state in ('apart','touching'):
        return 0.
    return max(CLEARANCE_VOLUME_MM3,r.overlap_mm3)


def relation(a,b,tol=TOL):
    a=a.val() if hasattr(a,'val') else a;b=b.val() if hasattr(b,'val') else b
    r=relate(a,b,tol,contact_area=False)
    RELATION_EVIDENCE.append({**r.to_dict(),'requested_tolerances':vars(tol)})
    if r.state not in ('apart','touching','overlapping','contains'):
        raise ValueError('Undecidable BREP relation: '+str(r.error or r.state))
    return r


def clear_of_all(a,obstacles):
    """Allocate one aggregate clearance budget before classifying any pair.

    Do not add thresholded overlap() values: several individually sub-threshold
    overlaps could exceed the original total allowance. Equal allocation is
    deliberately conservative. One nextafter step preserves the strict '<'
    acceptance rule; every pair's numerical uncertainty consumes its share.
    """
    obstacles=tuple(obstacles)
    if not obstacles:
        raise ValueError('An aggregate clearance check requires explicit obstacles')
    per_pair=math.nextafter(CLEARANCE_VOLUME_MM3/len(obstacles),0.)
    tol=replace(TOL,overlap_mm3=per_pair)
    states=[relation(a,b,tol).state for b in obstacles]
    evidence={'total_overlap_budget_mm3':CLEARANCE_VOLUME_MM3,
              'per_pair_overlap_budget_mm3':per_pair,'pair_states':states,
              'allocation':'equal conservative shares; no thresholded-volume summation'}
    return all(s in ('apart','touching') for s in states),evidence


def preserved_region(a,b,region):
    """Validate clipped BREPs and both outside volumes; never mass an unchecked cut."""
    a=a.val() if hasattr(a,'val') else a;b=b.val() if hasattr(b,'val') else b
    region=region.val() if hasattr(region,'val') else region
    r=relation(a.intersect(region),b.intersect(region))
    return r.state=='contains' and r.contained=='both',r.to_dict()


def run(out):
    started=time.monotonic();checks=[];RELATION_EVIDENCE.clear();query_start=0
    if os.environ.get('GYROPUP_CAD_PARAMS'):
        raise ValueError('Carrier interface candidate requires the committed default configuration')
    if RELATIONS_VERSION!='4':
        raise ValueError('Carrier predicates require reviewed relations engine4 (cad-agent v0.4.2); no older volume fallback')
    inputs=provenance.snapshot(ROOT)
    if inputs!=IMPORTED_INPUTS:
        raise ValueError('CAD/config/runtime inputs changed after geometry imports; restart in a fresh process')
    def check(name,ok,**evidence):
        nonlocal query_start
        evidence['relation_query_indices']=list(range(query_start,len(RELATION_EVIDENCE)))
        query_start=len(RELATION_EVIDENCE)
        checks.append({'id':name,'pass':bool(ok),'evidence':evidence})
    g=tu.Geo();old=tu.pan_base(g,board_service=False);base=tu.pan_base(g)
    carrier=bb.carrier();closed=bb.carrier(wiring=False)
    check('carrier_valid_one_solid',carrier.val().isValid() and len(carrier.val().Solids())==1)
    bounds=carrier.val().BoundingBox()
    check('carrier_preserves_flat_print_depth',abs(bounds.xmax-56.)<1e-6 and abs(bounds.xmin-48.)<1e-6,
          x_bounds_mm=[bounds.xmin,bounds.xmax])
    check('base_valid_one_solid',base.val().isValid() and len(base.val().Solids())==1)
    regions={'foot':bb.box(-120,120,-120,120,-1,5),'bearing_tube':cq.Solid.makeCylinder(35.5,38),
             'bearing_seat':bb.box(-43,43,-50,50,38,60),'servo_pocket':bb.box(-85,-25,-50,60,0,65)}
    for name,region in regions.items():
        same,r=preserved_region(old,base,region)
        check('protected:'+name,same,relation=r)
    # Exact neighbourhoods around every original mount, not only their centre points.
    for group,holes in [('pcb',bb.BOARD_HOLES),('retainer',bb.CARRIER_HOLES)]:
        for i,(y,z) in enumerate(holes):
            r=bb.cx(3.5,47.9,56.1,y,z).val()
            same,rel=preserved_region(closed,carrier,r)
            check(f'unchanged_mount:{group}:{i}',same,relation=rel)
    # Straight solder-side exit reservations; their net/pad assignment is still unproved.
    lanes=[(23.,z,.7) for z in (15.5,18.,20.5,23.)]+[(20.,17.,1.016),(20.,24.,1.016)]
    leads=[bb.cx(r,48.05,60.,y,z) for y,z,r in lanes]
    for i,lead in enumerate(leads):
        clear,allocation=clear_of_all(lead,(carrier,base))
        check(f'window_exit:{i}',clear,**allocation,axis_yz_radius_mm=lanes[i])
    check('negative:closed_window',all(overlap(l,closed)>1 for l in leads))
    reservations=[]
    for kind in ('power','signal'):
        c=ci.POWER if kind=='power' else ci.SIGNAL
        module=body(kind,'module');reservations.append(module)
        for step in range(9):
            travel=c['unmate_travel_mm']*step/8
            source=body(kind,'fixed',travel)
            clear,allocation=clear_of_all(source,(carrier,base))
            check(f'unmate_reservation:{kind}:{step}',clear,travel_mm=travel,**allocation)
        clear,allocation=clear_of_all(module,(carrier,base))
        check(f'module_connector_reservation:{kind}',clear,**allocation)
        reservations.append(body(kind,'fixed'))
    # Latch/grip spaces are declared design envelopes, not anthropometric validation.
    accesses={'signal_latch':bb.box(74,104,-6,8,21,37),
              'power_grip':bb.box(68,100,-11,11,5.25,18)}
    for name,access in accesses.items():
        clear,allocation=clear_of_all(access,(base,carrier))
        check('access_reservation:'+name,clear,**allocation)
    check('negative:bumper_blocks_power_grip',overlap(accesses['power_grip'],tu.bumper_ring(g))>1.)
    check('negative:blocked_latch',overlap(accesses['signal_latch'],bb.box(78,82,-4,4,23,35))>1.)
    for i,(y,z) in enumerate(bb.CARRIER_HOLES):
        shaft=bb.cx(3.,56.01,116.,y,z)
        clear,allocation=clear_of_all(shaft,[carrier,base,*reservations])
        check(f'driver_shaft_reservation:{i}',clear,**allocation)
    tails=[ci.tail_requirements(k,s) for k in ('power','signal') for s in ('fixed','module')]
    for tail in tails:
        check(f'tail_lower_bound:{tail["connector"]}:{tail["side"]}',tail['length_lower_bound_pass'],
              retained_free_length_mm=tail['retained_free_length_mm'],
              required_lower_bound_mm=tail['required_geometric_lower_bound_mm'])
    for kind in ('power','signal'):
        short=ci.tail_requirements(kind,'fixed',retained_mm=10.)
        pulling=ci.tail_requirements(kind,'fixed',module_travel=ci.MODULE_TRAVEL_MM)
        check('negative:short_tail:'+kind,not short['length_lower_bound_pass'])
        check('negative:withdraw_still_mated:'+kind,not pulling['length_lower_bound_pass'],
              required_lower_bound_mm=pulling['required_geometric_lower_bound_mm'])
    evidence={'geometry':all(c['pass'] for c in checks)}
    result={'schema':'gyropup.carrier-interfaces/1','bounded_reservation_checks_pass':evidence['geometry'],
            'readiness':ci.readiness(evidence),'physical_fit_verified':False,
            'coverage':evidence,'checks':checks,'tails':tails,'connectors':{'power':ci.POWER,'signal':ci.SIGNAL},
            'anchors_mm':ci.ANCHORS,'module_service_pose_mm':[ci.MODULE_TRAVEL_MM,0.,0.],
            'source_urls':ci.SOURCES,'seconds':round(time.monotonic()-started,2),
            'runtime':{'cadquery':cq.__version__,'OCP':OCP.__version__},
            'relations_engine_version':RELATIONS_VERSION,
            'inputs':inputs,'source_sha256':inputs['files'],'input_fingerprint':provenance.fingerprint(inputs),
            'relation_tolerances':vars(TOL),'relation_queries':RELATION_EVIDENCE,
            'limits':['Connector solids are authored dimension/space reservations, not manufacturer models.',
                      'Molex latch/ears are reserved, not mechanically validated; XT30 mated depth is unknown.',
                      'Straight wire exits and endpoint distance are necessary lower bounds, not bend or cable sweep proofs.',
                      'Tie hardware, actual clamp retention, abrasion sleeve, solder pads and insulation remain unqualified.',
                      'C3 and pan-servo unplugging remain mandatory and are not covered by the C2 candidate.',
                      '45 mm module pose is not a new full insertion/removal sweep result.',
                      'Source fuse/TVS/regulator coordination and DT contact/seal compatibility remain open.',
                      'Base and carrier changes require renewed structural, print and physical-fit qualification.']}
    out.mkdir(parents=True,exist_ok=True)
    cq.exporters.export(carrier,str(out/'carrier-wiring-candidate.step'))
    cq.exporters.export(base,str(out/'pan-base-wiring-candidate.step'))
    # Preserve names/colours in XCAF: review must distinguish authored mechanical
    # parts, public simplified hardware, component envelopes and reservations.
    layout=cq.Assembly(name='carrier_interface_candidate_unqualified')
    layout.add(base,name='pan_base_authored',color=cq.Color(.40,.46,.52))
    layout.add(carrier,name='carrier_authored',color=cq.Color(.20,.48,.68))
    layout.add(bb.pcb(),name='cut_PCB_nominal_stock',color=cq.Color(.12,.48,.28))
    for i,(name,component) in enumerate(bb.components().items()):
        layout.add(component,name=f'component_envelope_{i}_{name}',color=cq.Color(.26,.29,.33))
    for name,hardware in bb.hardware().items():
        colour=cq.Color(.72,.53,.20) if 'inserts' in name else cq.Color(.72,.75,.78)
        layout.add(hardware,name='authored_public_'+name,color=colour)
    for kind in ('power','signal'):
        for side in ('module','fixed'):
            layout.add(body(kind,side),name=f'RESERVATION_ONLY_C2_{kind}_{side}',color=cq.Color(.95,.36,.09,.65))
    layout.save(str(out/'carrier-wiring-layout.step'))
    result['artifact_sha256']={p:hashlib.sha256((out/p).read_bytes()).hexdigest() for p in
                              ('carrier-wiring-candidate.step','pan-base-wiring-candidate.step','carrier-wiring-layout.step')}
    if provenance.snapshot(ROOT)!=inputs:
        raise ValueError('CAD/config/runtime inputs changed during generation; discard the candidate and rerun')
    # A partial export must not publish a new completed receipt.
    (out/'interfaces.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'checks':len(checks),'failed':[c['id'] for c in checks if not c['pass']],
                      'bounded_reservation_checks_pass':evidence['geometry'],'readiness':result['readiness'],
                      'seconds':result['seconds']}))
    return 0 if evidence['geometry'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'exports/turret/base-board-service/interfaces')
    raise SystemExit(run(p.parse_args().out))
