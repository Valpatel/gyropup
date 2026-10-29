"""Bounded candidate space checks; explicitly not a complete harness qualification."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import time
import cadquery as cq
import turret as tu
import turret_base_board as bb
import turret_carrier_interfaces as ci

ROOT=Path(__file__).resolve().parents[1]


def body(kind,side,travel=0.):
    c=ci.POWER if kind=='power' else ci.SIGNAL
    x,z=c['centre_xz_mm']; dx,dz=c.get('body_xz_mm',c.get('reservation_xz_mm'))
    y0,y1=c['source_body_y_mm'] if side=='fixed' else c['module_body_y_mm']
    return bb.box(x-dx/2,x+dx/2,y0+travel,y1+travel,z-dz/2,z+dz/2)


def overlap(a,b):
    a=a.val() if hasattr(a,'val') else a;b=b.val() if hasattr(b,'val') else b
    return a.intersect(b).Volume()


def run(out):
    started=time.monotonic();checks=[]
    def check(name,ok,**evidence):
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
        r=region.val() if hasattr(region,'val') else region
        before=old.val().intersect(r);after=base.val().intersect(r)
        delta=before.cut(after).Volume()+after.cut(before).Volume()
        check('protected:'+name,delta<1e-6,symmetric_difference_mm3=delta)
    # Exact neighbourhoods around every original mount, not only their centre points.
    for group,holes in [('pcb',bb.BOARD_HOLES),('retainer',bb.CARRIER_HOLES)]:
        for i,(y,z) in enumerate(holes):
            r=bb.cx(3.5,47.9,56.1,y,z).val()
            a=closed.val().intersect(r);b=carrier.val().intersect(r)
            delta=a.cut(b).Volume()+b.cut(a).Volume()
            check(f'unchanged_mount:{group}:{i}',delta<1e-6,symmetric_difference_mm3=delta)
    # Straight solder-side exit reservations; their net/pad assignment is still unproved.
    lanes=[(23.,z,.7) for z in (15.5,18.,20.5,23.)]+[(20.,17.,1.016),(20.,24.,1.016)]
    leads=[bb.cx(r,48.05,60.,y,z) for y,z,r in lanes]
    for i,lead in enumerate(leads):
        v=overlap(lead,carrier)+overlap(lead,base)
        check(f'window_exit:{i}',v<1e-6,overlap_mm3=v,axis_yz_radius_mm=lanes[i])
    check('negative:closed_window',all(overlap(l,closed)>1 for l in leads))
    reservations=[]
    for kind in ('power','signal'):
        c=ci.POWER if kind=='power' else ci.SIGNAL
        module=body(kind,'module');reservations.append(module)
        for step in range(9):
            travel=c['unmate_travel_mm']*step/8
            source=body(kind,'fixed',travel)
            v=sum(overlap(source,o) for o in (carrier,base))
            check(f'unmate_reservation:{kind}:{step}',v<1e-6,travel_mm=travel,overlap_mm3=v)
        check(f'module_connector_reservation:{kind}',overlap(module,carrier)+overlap(module,base)<1e-6)
        reservations.append(body(kind,'fixed'))
    # Latch/grip spaces are declared design envelopes, not anthropometric validation.
    accesses={'signal_latch':bb.box(74,104,-6,8,21,37),
              'power_grip':bb.box(68,100,-11,11,5.25,18)}
    for name,access in accesses.items():
        v=overlap(access,base)+overlap(access,carrier)
        check('access_reservation:'+name,v<1e-6,overlap_mm3=v)
    check('negative:bumper_blocks_power_grip',overlap(accesses['power_grip'],tu.bumper_ring(g))>1.)
    check('negative:blocked_latch',overlap(accesses['signal_latch'],bb.box(78,82,-4,4,23,35))>1.)
    for i,(y,z) in enumerate(bb.CARRIER_HOLES):
        shaft=bb.cx(3.,56.01,116.,y,z)
        v=sum(overlap(shaft,o) for o in [carrier,base,*reservations])
        check(f'driver_shaft_reservation:{i}',v<1e-6,overlap_mm3=v)
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
            'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                            ('cad/turret.py','cad/turret_base_board.py','cad/turret_boards.py',
                             'cad/turret_carrier_interfaces.py','cad/check_base_board_interfaces.py')},
            'limits':['Connector solids are authored dimension/space reservations, not manufacturer models.',
                      'Molex latch/ears are reserved, not mechanically validated; XT30 mated depth is unknown.',
                      'Straight wire exits and endpoint distance are necessary lower bounds, not bend or cable sweep proofs.',
                      'Tie hardware, actual clamp retention, abrasion sleeve, solder pads and insulation remain unqualified.',
                      'C3 and pan-servo unplugging remain mandatory and are not covered by the C2 candidate.',
                      '45 mm module pose is not a new full insertion/removal sweep result.',
                      'Source fuse/TVS/regulator coordination and DT contact/seal compatibility remain open.',
                      'Base and carrier changes require renewed structural, print and physical-fit qualification.']}
    out.mkdir(parents=True,exist_ok=True)
    (out/'interfaces.json').write_text(json.dumps(result,indent=2)+'\n')
    cq.exporters.export(carrier,str(out/'carrier-wiring-candidate.step'))
    cq.exporters.export(cq.Compound.makeCompound([carrier.val(),bb.pcb().val(),*[s.val() for s in reservations]]),
                        str(out/'carrier-wiring-layout.step'))
    print(json.dumps({'checks':len(checks),'failed':[c['id'] for c in checks if not c['pass']],
                      'bounded_reservation_checks_pass':evidence['geometry'],'readiness':result['readiness'],
                      'seconds':result['seconds']}))
    return 0 if evidence['geometry'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'exports/turret/base-board-service/interfaces')
    raise SystemExit(run(p.parse_args().out))
