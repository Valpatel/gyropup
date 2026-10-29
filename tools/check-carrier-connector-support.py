#!/usr/bin/env python3
"""Bounded support candidate checks. No strength, snap-flex or harness approval.

Exact private hardware is used without publishing vendor geometry. All reports
bind the complete CAD/configuration closure and every additional source input.
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
PUBLIC_FILES={'carrier-support-candidate.step','C3-support-candidate.step','C3-support-layout.step'}


def expected_check_ids():
    """Published evidence coverage; a missing failed result cannot become green."""
    names={'valid:carrier','valid:support','carrier_depth_unchanged','carrier_added_material_valid',
           'carrier_added_material:all_neighbours','carrier:nonmating_neighbours','support:installed_neighbours',
           'support:carrier_seat','negative:closed_panel_blocks_housing','latch_finger_reservation',
           'C3_straight_exit:module','C3_straight_exit:fixed','C3_service:mated->unplugged',
           'C3_service:unplugged->outboard_before_park','C3_service:outboard_before_park->parked',
           'negative:C3_unplug_blocker','negative:blocked_new_hole','panel_thickness_in_drawing_range',
           'public_STEP_roundtrip:carrier-support-candidate','public_STEP_roundtrip:C3-support-candidate'}
    names|={f'valid:{group}#{i}' for group in ('c3_support_nuts','c3_support_screws') for i in range(2)}
    names|={f'{prefix}{i}' for prefix in ('preserve_original_mount:pcb:','preserve_original_mount:retainer:',
                                        'original_retainer_driver:') for i in range(4)}
    names|={f'C2_straight_exit:{i}' for i in range(6)}
    names|={f'{prefix}{i}' for prefix in ('nut_seated:','screw_clearance_holes:','nut_inside_sweep:',
                                        'nut_install_before_PCB:','negative:nut_removal_with_PCB:',
                                        'support_driver_bench:','negative:blocked_driver:',
                                        'screw_nut_nominal_stack:') for i in range(2)}
    return names


def context_paths(root=ROOT):
    return [root/'tools/check-carrier-connector-support.py',
            root/'tools/check-carrier-connector-inputs.py',
            root/'tools/check-carrier-connector-pose.py',
            root/'research/carrier-service-connectors/private-inputs.json',
            root/'research/carrier-service-connectors/support-hardware-catalog.json']


def validate_receipt(receipt,root=ROOT):
    current=provenance.snapshot(root);recorded=receipt['inputs']
    if receipt['input_fingerprint']!=provenance.fingerprint(recorded):
        raise ValueError('Support input fingerprint is inconsistent')
    for key in ('files','GYROPUP_CAD_PARAMS_sha256'):
        if recorded.get(key)!=current[key]:raise ValueError('Support geometry input closure changed')
    if receipt['context_files']!=provenance.context_snapshot(root,context_paths(root)):
        raise ValueError('Support checker or supplier source changed')
    hardware=json.loads((root/'research/carrier-service-connectors/support-hardware-catalog.json').read_text())
    expected={e['model']:e['private_file_sha256'][e['cad']['file']] for e in hardware}
    if receipt['private_hardware_sha256']!=expected:
        raise ValueError('Support hardware identities differ')
    connectors=json.loads((root/'research/carrier-service-connectors/private-inputs.json').read_text())
    wanted={e['part']:e['sha256'] for e in connectors['parts'] if e['part'] in ('43020-1200','43025-1200')}
    if receipt['private_connector_sha256']!=wanted:
        raise ValueError('Support connector identities differ')
    if receipt['readiness'] is not False or receipt['load_screen']['structural_readiness'] is not False:
        raise ValueError('Bounded support check cannot establish readiness')
    checks=receipt.get('checks',[])
    ids=[c.get('id') for c in checks]
    if set(ids)!=expected_check_ids() or len(ids)!=len(expected_check_ids()):
        raise ValueError('Support check coverage is incomplete, duplicate or unexpected')
    if receipt.get('bounded_geometry_checks_pass') is not True or any(c['pass'] is not True for c in checks):
        raise ValueError('Support candidate has failed checks')
    artifacts=receipt.get('public_artifact_sha256')
    if not isinstance(artifacts,dict) or set(artifacts)!=PUBLIC_FILES:
        raise ValueError('Support public artifact binding is incomplete or unexpected')
    for name,wanted in artifacts.items():
        path=root/'exports/turret/base-board-service/connectors'/name
        if not path.is_file() or provenance.digest(path)!=wanted:
            raise ValueError('Support public artifact changed: '+name)
    return True


def run(output,public_out=None):
    started=time.monotonic();inputs=provenance.snapshot(ROOT)
    context=provenance.context_snapshot(ROOT,context_paths())
    import cadquery as cq
    from OCP.BRepBndLib import BRepBndLib
    from OCP.Bnd import Bnd_Box
    from cadagent.gates import Tolerances,relate
    from cadagent.gates.relations import RELATIONS_VERSION
    import turret as tu
    import turret_base_board as bb
    import turret_carrier_support as cs
    import check_base_board_interfaces as ci
    if RELATIONS_VERSION!='4':raise ValueError('Requires released v0.4.2 relation predicates')
    spec=importlib.util.spec_from_file_location('connector_inputs',context_paths()[1])
    source=importlib.util.module_from_spec(spec);spec.loader.exec_module(source)
    pose_spec=importlib.util.spec_from_file_location('connector_pose',context_paths()[2])
    pose=importlib.util.module_from_spec(pose_spec);pose_spec.loader.exec_module(pose)
    if provenance.snapshot(ROOT)!=inputs:raise ValueError('Inputs changed during imports')
    manifest=json.loads(source.MANIFEST.read_text())
    plug_entry=next(e for e in manifest['parts'] if e['part']=='43020-1200')
    plug=(cq.importers.importStep(str(source.private_path(plug_entry))).val()
          .rotate((0,0,0),(0,1,0),-90).translate((84.,-8.445,34.)))
    rec_entry=next(e for e in manifest['parts'] if e['part']=='43025-1200')
    rec=(cq.importers.importStep(str(source.private_path(rec_entry))).val()
         .rotate((0,0,0),(0,0,1),180).translate((0.,12.325,0.))
         .rotate((0,0,0),(0,1,0),-90).translate((84.,-8.445,34.)))
    hardware=cs.hardware(private=True)
    hardware={n:s.val() for n,s in hardware.items()}
    carrier=cs.carrier().val();support=cs.support().val();original=bb.carrier().val()
    g=tu.Geo();pcb=bb.pcb().val()
    obstacles={'pan_base':tu.pan_base(g).val(),'PCB_and_packages':bb.board().val(),
               'bumper_installed':tu.bumper_ring(g).val(),'pan_clamp':tu.pan_clamp(g).val(),
               'pan_ring':tu.pan_ring(g).val(),
               'pan_servo_RESERVATION':tu.servo_envelope(g,(*g.servo_pan_xy,g.servo_z0+tu.SERVO['H']),'+z').val()}
    for kind in ('power','signal'):
        obstacles[f'C2_{kind}_module_RESERVATION']=ci.body(kind,'module').val()
        obstacles[f'C2_{kind}_released_RESERVATION']=ci.body(kind,'fixed',14. if kind=='power' else 16.).val()
    for n,s in bb.hardware().items():obstacles[n+'_AUTHORED']=s.val()
    checks=[];relations=[];query_start=0
    def shape(s):return s.val() if hasattr(s,'val') else s
    def bounds(s):
        b=Bnd_Box();BRepBndLib.AddOptimal_s(shape(s).wrapped,b,False,False);return list(b.Get())
    def check(name,ok,**evidence):
        nonlocal query_start
        evidence['relation_query_indices']=list(range(query_start,len(relations)));query_start=len(relations)
        checks.append({'id':name,'pass':bool(ok),'evidence':evidence})
        print(name,'PASS' if ok else 'FAIL',flush=True)
    def relation(a,b,tol=None):
        r=relate(shape(a),shape(b),tol or Tolerances(),contact_area=False)
        relations.append(r.to_dict())
        if r.state not in ('apart','touching','overlapping','contains'):
            raise ValueError('Undecidable relation: '+str(r.error))
        return r
    def clear(a,others):
        others=dict(others)
        if not others:raise ValueError('Explicit obstacles required')
        tol=Tolerances(overlap_mm3=math.nextafter(1e-6/len(others),0.))
        pairs={n:relation(a,b,tol).state for n,b in others.items()}
        return all(s in ('apart','touching') for s in pairs.values()),{
            'pair_states':pairs,'total_budget_mm3':1e-6,'per_pair_budget_mm3':tol.overlap_mm3}
    for n,s in {'carrier':carrier,'support':support,**hardware}.items():
        check('valid:'+n,s.isValid() and len(s.Solids())==1,bounds_mm=bounds(s))
    check('carrier_depth_unchanged',bounds(carrier)[0]==bounds(original)[0] and bounds(carrier)[3]==bounds(original)[3])
    for group,holes in [('pcb',bb.BOARD_HOLES),('retainer',bb.CARRIER_HOLES)]:
        for i,(y,z) in enumerate(holes):
            region=bb.cx(3.5,47.9,56.1,y,z).val()
            tol=Tolerances(contain_mm3=math.nextafter(.5e-6,0.))
            r=relation(original.intersect(region),carrier.intersect(region),tol)
            check(f'preserve_original_mount:{group}:{i}',r.state=='contains' and r.contained=='both')
    # The four heat-set interfaces already interfere before this change. Preserve
    # their raw relations and the exact unchanged local-region proof above; do
    # not mislabel their fit as clearance or add an intended-overlap waiver.
    mating_names={n for n in obstacles if n.startswith('base_board_inserts#')}
    existing_mates={n:{'baseline':relation(original,obstacles[n]).to_dict(),
                       'candidate':relation(carrier,obstacles[n]).to_dict(),
                       'physical_fit_verified':False,
                       'qualification':'Unchanged existing heat-set mate; not an accepted clearance.'}
                    for n in sorted(mating_names)}
    added=carrier.cut(original)
    check('carrier_added_material_valid',added.isValid() and len(added.Solids())==2)
    ok,ev=clear(added,obstacles);check('carrier_added_material:all_neighbours',ok,**ev)
    ok,ev=clear(carrier,{n:s for n,s in obstacles.items() if n not in mating_names})
    check('carrier:nonmating_neighbours',ok,excluded_existing_mates=sorted(mating_names),**ev)
    ok,ev=clear(support,obstacles);check('support:installed_neighbours',ok,**ev)
    ok,ev=clear(support,{'carrier':carrier});check('support:carrier_seat',ok,**ev)
    lanes=[(23.,z,.7) for z in (15.5,18.,20.5,23.)]+[(20.,17.,1.016),(20.,24.,1.016)]
    for i,(y,z,r) in enumerate(lanes):
        ok,ev=clear(bb.cx(r,48.05,60.,y,z),{'carrier':carrier,'support':support})
        check('C2_straight_exit:'+str(i),ok,**ev)
    # Original retainer driver shafts must remain accessible after adding support.
    for i,(y,z) in enumerate(bb.CARRIER_HOLES):
        ok,ev=clear(bb.cx(3.,59.01,119.,y,z),{'support':support})
        check('original_retainer_driver:'+str(i),ok,**ev)
    for i,(y,z) in enumerate(cs.HOLES):
        nut=hardware[f'c3_support_nuts#{i}'];screw=hardware[f'c3_support_screws#{i}']
        ok,ev=clear(nut,{'carrier':carrier,'support':support,'PCB':pcb})
        check('nut_seated:'+str(i),ok,**ev)
        ok,ev=clear(screw,{'carrier':carrier,'support':support,'PCB':pcb})
        check('screw_clearance_holes:'+str(i),ok,**ev)
        # Exact hex outer-prism sweep conservatively contains the real chamfered
        # nut for every straight-X translation, verified at its final endpoint.
        sweep=cs.hex_prism(5.5,13.,(40.,y,z)).val()
        r=relation(sweep,nut)
        check('nut_inside_sweep:'+str(i),r.state=='contains' and r.contained in ('b_in_a','both'))
        ok,ev=clear(sweep,{'carrier':carrier,'support':support})
        check('nut_install_before_PCB:'+str(i),ok,**ev)
        r=relation(sweep,pcb)
        check('negative:nut_removal_with_PCB:'+str(i),r.state=='overlapping',
              prerequisite='Remove PCB on bench before replacing support; not required for normal whole-module removal.')
        tool=bb.cx(3.,61.01,121.01,y,z)
        ok,ev=clear(tool,{'support':support,'carrier':carrier,'PCB':pcb})
        check('support_driver_bench:'+str(i),ok,**ev)
        r=relation(tool,bb.cx(4.,70.,75.,y,z))
        check('negative:blocked_driver:'+str(i),r.state in ('contains','overlapping'))
        check('screw_nut_nominal_stack:'+str(i),math.isclose(8.-(2.+3.+2.4),.6),
              grip_mm=5.,nut_thickness_mm=2.4,nominal_projection_mm=.6,
              exact_nut_bounds_mm=bounds(nut),exact_screw_bounds_mm=bounds(screw),
              thread_mate_qualified=False)
    # The static vendor clip cannot be treated as flexed clearance. Record the
    # relation rather than turning an expected snap overlap into a passing fit.
    panel_relation=relation(plug,support)
    check('negative:closed_panel_blocks_housing',relation(plug,cs.support(cutout=False)).state=='overlapping')
    finger=bb.box(90.71,105.,-6.12,7.88,27.,41.)
    ok,ev=clear(finger,{'support':support});check('latch_finger_reservation',ok,**ev)
    for side,y0,y1 in [('module',-35.99,-16.89),('fixed',7.88,26.98)]:
        # Full-array rectangle is deliberately conservative; no claimed wire OD.
        exit_box=bb.box(82.15,85.85,y0,y1,24.925,43.075)
        ok,ev=clear(exit_box,{'support':support});check('C3_straight_exit:'+side,ok,**ev)
    # Recheck every existing C3 service segment against this actual new support,
    # including all attached new hardware, not only the earlier bare carrier.
    def swept_box(initial,final):
        a=bounds(rec.translate(initial));b=bounds(rec.translate(final))
        lo=[min(a[i],b[i]) for i in range(3)];hi=[max(a[i+3],b[i+3]) for i in range(3)]
        return bb.box(lo[0],hi[0],lo[1],hi[1],lo[2],hi[2])
    states=list(pose.STATES.items())
    new_obstacles={'carrier':carrier,'support':support,**hardware}
    for (a,initial),(b,final) in zip(states,states[1:]):
        sweep=swept_box(initial,final)
        ok,ev=clear(sweep,new_obstacles);check('C3_service:'+a+'->'+b,ok,**ev)
    first=swept_box(states[0][1],states[1][1])
    check('negative:C3_unplug_blocker',relation(first,bb.box(80.,85.,13.,15.,30.,35.)).state in ('contains','overlapping'))
    missing_hole=carrier.fuse(bb.cx(1.7,53.,56.,*cs.HOLES[0]).val())
    check('negative:blocked_new_hole',relation(hardware['c3_support_screws#0'],missing_hole).state=='overlapping')
    check('panel_thickness_in_drawing_range',1.4<=cs.PANEL_Y[1]-cs.PANEL_Y[0]<=2.54,
          thickness_mm=cs.PANEL_Y[1]-cs.PANEL_Y[0],physical_fit=False)
    records=json.loads(cs.HARDWARE_RECORD.read_text())
    result={'schema':1,'readiness':False,'bounded_geometry_checks_pass':all(c['pass'] for c in checks),
            'inputs':inputs,'input_fingerprint':provenance.fingerprint(inputs),'context_files':context,
            'private_hardware_sha256':{e['model']:e['private_file_sha256'][e['cad']['file']] for e in records},
            'private_connector_sha256':{e['part']:e['sha256'] for e in (plug_entry,rec_entry)},
            'checks':checks,'relations':relations,'existing_unqualified_mates':existing_mates,
            'panel_housing_relation':panel_relation.to_dict(),'panel_retention_qualified':False,
            'load_screen':cs.load_screen(),'assembly_order':cs.assembly_order(),'rigid_module_members':cs.module_members(),
            'limits':['Not a full insertion/removal sequence or upper-head-motion check.',
                      'Panel snap flex, thread clocking, torque, strength, creep and physical fit remain unqualified.',
                      'Nut pockets resist rotation only after assembly; hold loose nuts until screws engage.',
                      'C2/C3/servo parking, actual retained tails/junctions and added protection board remain incomplete.',
                      'Wire-exit and tool corridors are explicit design reservations, not detailed cable/tool models.'],
            'elapsed_seconds':round(time.monotonic()-started,3)}
    if public_out is not None:
        import hashlib
        public_out.mkdir(parents=True,exist_ok=True)
        layout=cq.Assembly(name='C3_support_ACCESS_CANDIDATE_NOT_STRENGTH_QUALIFIED')
        layout.add(obstacles['pan_base'],name='pan_base_authored',color=cq.Color(.40,.46,.52))
        layout.add(carrier,name='carrier_candidate_authored',color=cq.Color(.20,.48,.68))
        layout.add(support,name='C3_support_candidate_authored',color=cq.Color(.93,.49,.12))
        layout.add(pcb,name='cut_PCB_nominal_stock',color=cq.Color(.12,.48,.28))
        for i,(n,s) in enumerate(bb.components().items()):
            layout.add(s,name=f'component_ENVELOPE_{i}_{n}',color=cq.Color(.26,.29,.33))
        for n,s in {**bb.hardware(),**cs.hardware()}.items():
            layout.add(s,name='authored_public_'+n,color=cq.Color(.72,.53,.20) if 'inserts' in n else cq.Color(.72,.75,.78))
        # Independent drawing-dimension body only. No shape, mesh or topology
        # from the private Molex input is included in any published artifact.
        public_housing=bb.box(84.-6.85/2,84.+6.85/2,-16.89,0.,34.-18.85/2,34.+18.85/2)
        layout.add(public_housing,name='C3_BODY_DIMENSION_ONLY_not_complete_hardware',color=cq.Color(.16,.18,.22))
        for kind in ('power','signal'):
            layout.add(ci.body(kind,'module'),name=f'RESERVATION_ONLY_C2_{kind}_module',color=cq.Color(.65,.24,.60,.65))
        paths=[]
        for name,s in [('carrier-support-candidate',carrier),('C3-support-candidate',support)]:
            p=public_out/(name+'.step');cq.exporters.export(s,str(p));paths.append(p)
            loaded=cq.importers.importStep(str(p)).val()
            r=relation(s,loaded,Tolerances(contain_mm3=math.nextafter(.5e-6,0.)))
            check('public_STEP_roundtrip:'+name,loaded.isValid() and len(loaded.Solids())==1
                  and r.state=='contains' and r.contained=='both',bounds_mm=bounds(loaded))
        assembly_path=public_out/'C3-support-layout.step';layout.save(str(assembly_path));paths.append(assembly_path)
        result['public_artifact_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        result['public_geometry_note']=cs.PUBLIC_NOTE
        result['bounded_geometry_checks_pass']=all(c['pass'] for c in checks)
    if provenance.snapshot(ROOT)!=inputs or provenance.context_snapshot(ROOT,context_paths())!=context:
        raise ValueError('Inputs changed during candidate check; discard generated artifacts')
    result['elapsed_seconds']=round(time.monotonic()-started,3)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'failed':[c['id'] for c in checks if not c['pass']],
                      'panel_relation':panel_relation.state,'seconds':result['elapsed_seconds'],'readiness':False}))
    return 0 if result['bounded_geometry_checks_pass'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True,type=Path)
    p.add_argument('--public-out',type=Path)
    args=p.parse_args();raise SystemExit(run(args.out,args.public_out))
