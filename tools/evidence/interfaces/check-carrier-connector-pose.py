#!/usr/bin/env python3
"""Conservative external C3 space candidate, not connector/retention acceptance.

The supplied housing internals remain unqualified. Their exact external bounding
boxes conservatively enclose each translation segment; no sampled path can miss
an intervening collision. No vendor-derived STEP/STL is written.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'cad'))
import print_provenance as provenance
SPEC=importlib.util.spec_from_file_location('connector_inputs',Path(__file__).with_name('check-carrier-connector-inputs.py'))
source=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(source)

# Candidate design coordinates, not supplier dimensions or current mounts.
CENTRE_XZ=(84.,34.)
FIXED_ANCHOR=(40.,-35.5,13.)
MODULE_ANCHOR=(84.,-39.,34.)
FIXED_RETAINED_MM=145.
MODULE_RETAINED_MM=30.
FREE_EXIT_MM=19.1  # PS-43045-001 R, 10-16 circuits; NOT a minimum bend radius.
STATES={'mated':(0.,0.,0.),'unplugged':(0.,16.,0.),
        'outboard_before_park':(0.,43.,0.),'parked':(-30.,43.,0.)}


def validate_receipt(receipt,root=ROOT):
    recorded=receipt['inputs'];current=provenance.snapshot(root)
    if receipt['input_fingerprint']!=provenance.fingerprint(recorded):
        raise ValueError('External-pose input fingerprint differs')
    for key in ('files','GYROPUP_CAD_PARAMS_sha256'):
        if recorded.get(key)!=current[key]:raise ValueError('External-pose geometry input closure changed')
    paths=[root/'tools/check-carrier-connector-pose.py',root/'tools/check-carrier-connector-inputs.py',
           root/'research/carrier-service-connectors/private-inputs.json']
    if receipt['context_files']!=provenance.context_snapshot(root,paths):
        raise ValueError('External-pose probe or private manifest changed')
    manifest=json.loads(paths[-1].read_text())
    if receipt['private_inputs']!={e['part']:e['sha256'] for e in manifest['parts']}:
        raise ValueError('External-pose private input identities differ')
    if receipt.get('readiness') is not False:
        raise ValueError('This external pose cannot establish whole-service readiness')
    return True


def run(output):
    start=time.monotonic();inputs=provenance.snapshot(ROOT)
    context_paths=[Path(__file__),Path(source.__file__),source.MANIFEST]
    context=provenance.context_snapshot(ROOT,context_paths)
    manifest=json.loads(source.MANIFEST.read_text())
    paths={e['part']:source.private_path(e) for e in manifest['parts']}
    import cadquery as cq
    from OCP.BRepBndLib import BRepBndLib
    from OCP.Bnd import Bnd_Box
    from cadagent.gates import Tolerances,relate
    from cadagent.gates.relations import RELATIONS_VERSION
    import turret as tu
    import turret_base_board as bb
    import check_base_board_interfaces as ci
    if RELATIONS_VERSION!='4':raise ValueError('Requires released v0.4.2 relation predicates')
    if provenance.snapshot(ROOT)!=inputs:raise ValueError('Inputs changed during imports')
    g=tu.Geo()
    obstacles={'pan_base':tu.pan_base(g),'carrier':bb.carrier(),'pcb_and_packages':bb.board(),
               'bumper_installed':tu.bumper_ring(g),'pan_clamp':tu.pan_clamp(g),
               'pan_ring':tu.pan_ring(g),
               'pan_servo_RESERVATION':tu.servo_envelope(g,(*g.servo_pan_xy,g.servo_z0+tu.SERVO['H']),'+z')}
    for kind in ('power','signal'):
        obstacles['C2_'+kind+'_module_RESERVATION']=ci.body(kind,'module')
        # C2 is disconnected first; its full parking route remains a separate prerequisite.
        travel=14. if kind=='power' else 16.
        obstacles['C2_'+kind+'_source_released_RESERVATION']=ci.body(kind,'fixed',travel)
    for n,s in bb.hardware().items():obstacles[n+'_AUTHORED']=s
    obstacles={n:(s.val() if hasattr(s,'val') else s) for n,s in obstacles.items()}
    def world(s):return s.rotate((0,0,0),(0,1,0),-90).translate((84.,-8.445,34.))
    plug=world(cq.importers.importStep(str(paths['43020-1200'])).val())
    rec=cq.importers.importStep(str(paths['43025-1200'])).val()
    rec=world(rec.rotate((0,0,0),(0,0,1),180).translate((0,12.325,0)))
    def bounds(s):
        b=Bnd_Box();BRepBndLib.AddOptimal_s(s.wrapped,b,False,False);return list(b.Get())
    def sweep_box(s,initial,final):
        a=bounds(s.translate(initial));b=bounds(s.translate(final))
        lo=[min(a[i],b[i]) for i in range(3)];hi=[max(a[i+3],b[i+3]) for i in range(3)]
        return bb.box(lo[0],hi[0],lo[1],hi[1],lo[2],hi[2]).val(),lo+hi
    evidence=[]
    tol=Tolerances(overlap_mm3=math.nextafter(1e-6/len(obstacles),0.))
    def external(name,s):
        pairs={}
        for n,other in obstacles.items():
            r=relate(s,other,tol,contact_area=False)
            if r.state not in ('apart','touching','overlapping','contains'):
                raise ValueError(name+' undecidable versus '+n+': '+str(r.error))
            pairs[n]=r.to_dict()
        clear=all(r['state'] in ('apart','touching') for r in pairs.values())
        evidence.append({'id':name,'external_clear':clear,'bounds_mm':bounds(s),
                         'total_overlap_budget_mm3':1e-6,'per_pair_overlap_budget_mm3':tol.overlap_mm3,
                         'relations':pairs})
        return clear
    external('module_housing_installed',plug)
    ordered=list(STATES.items())
    for (a,initial),(b,final) in zip(ordered,ordered[1:]):
        sweep,bbox=sweep_box(rec,initial,final)
        external('fixed_housing_swept_box:'+a+'->'+b,sweep)
    # Outward finger-space reservation: design allowance, not latch deflection data.
    external('latch_finger_RESERVATION',bb.box(90.71,105.,-6.12,7.88,27.,41.).val())
    negative={
        'lower_housing_intersects_installed_bumper':not external('NEGATIVE:lowered_housing',plug.translate((0,0,-13))),
        'parked_housing_inside_carrier_is_rejected':not external('NEGATIVE:bad_park',rec.translate((-30.,20.,-9.))),
    }
    # Necessary retained lengths, including every endpoint of all straight segments.
    # Norm is convex along a segment, so the maximum lies at an endpoint.
    tails=[]
    for name,(dx,dy,dz) in STATES.items():
        rear=(84.+dx,7.88+dy,34.+dz)
        free=(rear[0],rear[1]+FREE_EXIT_MM,rear[2])
        required=FREE_EXIT_MM+math.dist(free,FIXED_ANCHOR)
        tails.append({'state':name,'rear_exit_mm':rear,'free_exit_end_mm':free,
                      'necessary_lower_bound_mm':required,'retained_mm':FIXED_RETAINED_MM,
                      'length_lower_bound_pass':required<=FIXED_RETAINED_MM})
    module_rear=(84.,-16.89,34.);module_free=(84.,-16.89-FREE_EXIT_MM,34.)
    module_required=FREE_EXIT_MM+math.dist(module_free,MODULE_ANCHOR)
    if provenance.snapshot(ROOT)!=inputs or provenance.context_snapshot(ROOT,context_paths)!=context:
        raise ValueError('Inputs changed during candidate probe')
    result={'schema':1,'readiness':False,'qualification':'External space candidate only; supports and routes are not qualified.',
            'inputs':inputs,'input_fingerprint':provenance.fingerprint(inputs),'context_files':context,
            'private_inputs':{e['part']:e['sha256'] for e in manifest['parts']},
            'pose':{'plug_raw_rotation':'-90 degrees about Y','plug_translation_mm':[84.,-8.445,34.],
                    'receptacle_relative_to_raw_plug':'Rz180 then translation(0,12.325,0), then same world transform',
                    'fixed_states_translations_mm':STATES},'external_checks':evidence,'negative_controls':negative,
            'fixed_tail':{'anchor_candidate_mm':FIXED_ANCHOR,'states':tails,'ring_to_anchor_route_qualified':False},
            'module_tail':{'anchor_candidate_mm':MODULE_ANCHOR,'rear_exit_mm':module_rear,
                           'free_exit_end_mm':module_free,'necessary_lower_bound_mm':module_required,
                           'retained_mm':MODULE_RETAINED_MM,'board_to_anchor_route_qualified':False},
            'limits':['Anchors and parking keeper are candidate points, not installed retention hardware.',
                      'Retained lengths are between anchor and connector, not total lead or cutting lengths.',
                      'Unknown bend radius, actual wire diameter, bundle, crimp and solder geometry remain open.',
                      'Mate pair deliberately not treated as a clearance proof: supplied internals remain unresolved.',
                      'C2 released-source reservations are not a complete parked harness; module withdrawal is not checked.',
                      'Upper head, remote hardware and all cable paths are not included; no whole-turret motion claim.'],
            'elapsed_seconds':round(time.monotonic()-start,3)}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'readiness':False,'external':{r['id']:r['external_clear'] for r in evidence},
                      'negative_controls':negative,'seconds':result['elapsed_seconds']}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=Path)
    run(p.parse_args().out)
