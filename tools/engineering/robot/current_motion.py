"""Independent current-robot source references and existing shared trace checks.

Reads accepted original266 triangles and current CAD's pure mechanical functions,
never animation owner/pivot metadata. No CAD, browser, sampler or new validator.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tools/site/assembly')]
from robot_data import sha,vertices,landmarks,module_point
from tools.site.robot_current_model import source_fivebar
import robot_current_print_match as accepted

MODEL_SHA='3183870617a7ca3182c4a79a2afd8890a546ac2a3353cacc98e5295a63e64fe3'
PLAN=Path('tests/fixtures/current-robot-motion-plan.json')
PLAN_SHA='400d82302d8057cd72ade98c17d5f21553b13c1fa76d00860d09ba5e62b5f2c4'
# Independent ownership audit of fivebar.assembly/bought_parts/screw_groups.
# Do not import the animation converter's LEG_OWNERS/owners/landmarks map.
LEG={
 'fixed':'hip_frame motor_front motor_rear bearing_61812_front bearing_61812_rear stop_posts screws_lugs stop_sleeve_1 stop_sleeve_2 stop_sleeve_3 stop_sleeve_4'.split(),
 'upper_front':'output_adapter_front upper_link_front knee_nut_upper_front'.split(),
 'upper_rear':'output_adapter_rear upper_link_rear knee_nut_upper_rear'.split(),
 'front_link':['front_link'],'wheel_link':['wheel_link'],
 'C':'knee_bearing_front_in knee_bearing_front_out knee_pin_front knee_washer_front knee_spacer_front eye_sleeve_front'.split(),
 'D':'knee_bearing_rear_in knee_bearing_rear_out knee_pin_rear knee_washer_rear knee_spacer_rear eye_sleeve_rear'.split(),
 'E':'apex_spacer apex_61812 apex_circlip wheel_hub screws_wheel washers_wheel'.split(),
 'wheel':['wheel_tyre']}
LEG_OWNER={name:owner for owner,names in LEG.items()for name in names}


def load_motion(toolkit,revision):
    toolkit=Path(toolkit).resolve()
    current=subprocess.check_output(['git','-C',str(toolkit),'rev-parse','HEAD'],text=True).strip()
    if current!=revision or subprocess.check_output(['git','-C',str(toolkit),'status','--porcelain']):
        raise ValueError('Explicit clean immutable shared toolkit required')
    sys.path.insert(0,str(toolkit/'software'))
    from cadagent.mechanical import motion_trace
    if Path(motion_trace.__file__).resolve()!=toolkit/'software/cadagent/mechanical/motion_trace.py':
        raise ValueError('Executed motion toolkit origin differs')
    return motion_trace


def rotate_y(p,a):
    c,s=math.cos(a),math.sin(a);x,y,z=p
    return [c*x+s*z,y,-s*x+c*z]


def plus(a,b):return [x+y for x,y in zip(a,b)]
def minus(a,b):return [x-y for x,y in zip(a,b)]


def turret_reference():
    """Reuse the existing independently audited product turret intent, not its STL."""
    file=ROOT/'tools/engineering/turret/reference-turret-motion.py'
    spec=importlib.util.spec_from_file_location('current_turret_intent',file)
    oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    owners={'turret.'+(name[:-2]+'_2' if name.endswith('_m')else name):owner
            for owner,names in oracle.OWNERSHIP.items()if owner not in ('adapter','j501')for name in names}
    if len(owners)!=62:raise ValueError('Audited turret ownership changed')
    joints={}
    for name,j in oracle.JOINTS.items():
        joints['turret.'+name]={**j,'parent':'turret.'+j['parent']if j['parent']else None,
            'pivot':plus(j['pivot'],[-40,0,246-145])}
    return owners,joints


def observations(collection,folder):
    """Independent ordered actual landmarks and source screw-circle partitions."""
    records={}
    std=json.loads((ROOT/'hardware/cad/robot/interfaces.json').read_bytes())['AO-L']
    out=json.loads((ROOT/'hardware/catalog/interfaces.json').read_bytes())['robstride-rs-04']['output']
    for part in collection['parts']:
        file=folder/part['file']
        if file.is_symlink()or sha(file)!=part['sha256']:raise ValueError('Original observation mesh differs')
        points=vertices(file);name=part['name'];groups={None:list(range(len(points)//3))}
        if name.endswith(('.screws_links','.screws_outputs')):
            side,logical=name.split('.',1);sign=1 if side=='L'else -1
            radius=std['pcd']/2+8.5/2 if logical=='screws_links'else out['bolts']['pcd']/2+std['head']['d']/2
            groups={'upper_front':[],'upper_rear':[]}
            for i in range(0,len(points),3):
                matches=[key for key,x in [('upper_front',75),('upper_rear',-75)]
                    if all(math.hypot(sign*p[0]-x,p[2])<=radius+.001 for p in points[i:i+3])]
                if len(matches)!=1:raise ValueError('Unresolved independent screw partition')
                groups[matches[0]].append(i//3)
            if not all(groups.values())or sorted(sum(groups.values(),[]))!=list(range(len(points)//3)):
                raise ValueError('Independent triangle coverage incomplete')
        for owner,triangles in groups.items():
            selected=[points[t*3+k]for t in triangles for k in range(3)]
            marks=landmarks(selected);component=name+('@'+name[:2]+owner if owner else '')
            role=owner or (LEG_OWNER.get(name.split('.',1)[1])if name.startswith(('L.','R.'))else None)
            if name.startswith(('L.','R.'))and role is None:raise ValueError('Unaudited leg component')
            records[component]={'source_part':name,'file':part['file'],'sha256':part['sha256'],
                'vertex_indices':[selected.index(p)for p in marks],'points':[list(p)for p in marks],
                'role':role,'partition':owner,'triangles':len(triangles)}
    if len(records)!=228:raise ValueError('Complete224/four-partition observation inventory required')
    return records


def source_points(record,pose,mechanism):
    """CAD source's explicit link placement or translate-only envelope, per pose."""
    name=record['source_part']
    if not name.startswith(('L.','R.')):return record['points']
    side=name[0];sign=1 if side=='L'else -1;h=pose['leg_mm']+sign*pose['roll_mm']/2
    current,joints=mechanism['link_frames'](*mechanism['stance'](h,sign*pose['pitch_deg']))
    home,origin=mechanism['link_frames'](*mechanism['stance'](300.))
    role=record['role'];result=[]
    for point in record['points']:
        p=[sign*point[0],sign*point[1]-accepted.Y_OFF,point[2]]
        if role in ('upper_front','upper_rear','front_link','wheel_link'):
            (hx,hz),ha=home[role];(x,z),a=current[role]
            p=plus(rotate_y(rotate_y(minus(p,[hx,0,hz]),math.radians(-ha)),math.radians(a)),[x,0,z])
        elif role in ('C','D','E','wheel'):
            key='E'if role=='wheel'else role
            old,new=origin[key],joints[key];p=plus(p,[new[0]-old[0],0,new[1]-old[1]])
            if role=='wheel':p=plus(rotate_y(minus(p,[new[0],0,new[1]]),sign*math.radians(pose['wheel_deg'])),[new[0],0,new[1]])
        elif role!='fixed':raise ValueError('Unknown independent source owner')
        result.append(list(module_point(p,side,accepted.Y_OFF)))
    return result


def header(reference,joints,components):
    return {'schema_version':1,'length_unit':'mm','frame':'assembly-home',
        'reference':reference,'joints':joints,'components':components}


def helper_reference():
    # CAD body_shell source datums and turret source axes, not animation data.
    anchors={'eyes':([162.6,0,182],None),'camera_front':([192.6,0,142.5],None),
        'headlight_l':([55,155,160],None),'headlight_r':([55,-155,160],None),
        'pan':([-40,0,246],'turret.pan'),'tilt':([-40,0,386],'turret.tilt'),
        'muzzle':([110,0,371],'turret.tilt'),'laser_origin':([44.5,0,400.5],'turret.tilt')}
    return {'helper.'+name:{'joint':joint,'points':[point,*[plus(point,v)for v in ([1,0,0],[0,1,0],[0,0,1])]],
        'basis':'Source datum frame markers, not CAD surface geometry'}for name,(point,joint)in anchors.items()}


def build_reference(folder,motion):
    folder=Path(folder);collection=json.loads((folder/'collection.json').read_bytes())
    if sha(folder/'manifest.json')!=MODEL_SHA or sha(folder/'collection.json')!=accepted.COLLECTION_SHA:
        raise ValueError('Independently accepted original candidate required')
    conversion=json.loads((folder/'manifest.json').read_bytes())['conversion']
    if any(sha(ROOT/file)!=digest for file,digest in conversion['inputs'].items()):
        raise ValueError('Accepted converter dependency bytes changed')
    accepted.binding(ROOT,collection,folder)
    if sha(ROOT/PLAN)!=PLAN_SHA:raise ValueError('Pre-capture pose corpus/tolerance changed')
    plan=json.loads((ROOT/PLAN).read_bytes());mechanism=source_fivebar(ROOT)
    records=observations(collection,folder);turret_owners,turret_joints=turret_reference()
    if {r['source_part']for r in records.values()if r['source_part'].startswith('turret.')}!=set(turret_owners):
        raise ValueError('Same-collection mounted turret must match independent source inventory')
    home_frames,home=mechanism['link_frames'](*mechanism['stance'](300.))
    joints={};loops={};components={}
    for side in ('L','R'):
        sign=1 if side=='L'else -1
        for name,parent,pivot in [('upper_front',None,'A'),('upper_rear',None,'B'),('front_link','upper_front','C'),('wheel_link','upper_rear','D')]:
            if name.startswith('upper'):
                phi=-home_frames[name][1];lo,hi=(mechanism['P']['knee_in_deg'],mechanism['P']['knee_out_deg'])if name.endswith('front')else(-180-mechanism['P']['knee_out_deg'],-180-mechanism['P']['knee_in_deg'])
                span=[phi-hi,phi-lo]
            else:span=[-170,170]
            joints[side+'.'+name]={'parent':side+'.'+parent if parent else None,
                'pivot':list(module_point([home[pivot][0],0,home[pivot][1]],side,accepted.Y_OFF)),
                'axis':[0,sign,0],'range_deg':span}
        loops[side]={'closes':[side+'.front_link',side+'.wheel_link'],
            'pin':list(module_point([home['E'][0],0,home['E'][1]],side,accepted.Y_OFF)),
            'inputs':[side+'.upper_front',side+'.upper_rear']}
    for name,r in records.items():
        part=r['source_part'];role=r['role']
        if part.startswith('turret.'):continue
        if part.startswith(('L.','R.'))and role not in ('fixed','upper_front','upper_rear','front_link','wheel_link'):continue
        components[name]={'joint':part[:2]+role if role not in (None,'fixed')else None,'points':r['points']}
    rigid=header('Protected current CAD source hinge/link ownership and ideal five-bar loops; original266 world mesh landmarks. Composite internals not qualified.',joints,components)
    rigid['loops']=loops
    rigid_poses=motion.required_poses(rigid)
    live=[];helpers=helper_reference()
    for pose in plan['live_poses']:
        js=json.loads(json.dumps(turret_joints));cs={}
        for side in ('L','R'):
            sign=1 if side=='L'else -1;h=pose['leg_mm']+sign*pose['roll_mm']/2
            fk=mechanism['fk'](*mechanism['stance'](h,sign*pose['pitch_deg']))
            js[side+'.wheel']={'parent':None,'pivot':list(module_point([fk['E'][0],0,fk['E'][1]],side,accepted.Y_OFF)),
                'axis':[0,1,0],'range_deg':plan['shared_protocol']['wheel_tyre_range_deg']}
        for name,r in records.items():
            part=r['source_part'];owner=None
            if part.startswith('turret.'):
                role=turret_owners[part];owner='turret.'+role if role!='base'else None
            elif part.endswith('.wheel_tyre'):owner=part[:2]+'wheel'
            cs[name]={'joint':owner,'points':source_points(r,pose,mechanism)}
        cs.update({name:{key:helper[key]for key in ('joint','points')}for name,helper in helpers.items()})
        contract=header('Independent current CAD source FK at frozen live pose '+pose['id']+'; all224 original meshes/four exact partitions, translate-only envelopes explicit; shared turret/wheel frame coverage.',js,cs)
        live.append({'id':pose['id'],'pose':pose,'contract':contract,'required_poses':motion.required_poses(contract)})
    return {'schema':'gyropup.current-robot-motion-reference/1','collection_sha256':accepted.COLLECTION_SHA,
        'manifest_sha256':MODEL_SHA,'pose_plan_sha256':PLAN_SHA,'tolerance_mm':plan['tolerance_mm'],
        'component_observations':records,'helper_observations':helpers,
        'home_owner_angle_rad':{s+'.'+k:math.radians(home_frames[k][1]-(home_frames['upper_front'if k=='front_link'else'upper_rear'][1]if k in ('front_link','wheel_link')else 0))
            for s in ('L','R')for k in ('upper_front','upper_rear','front_link','wheel_link')},
        'rigid':{'contract':rigid,'required_poses':rigid_poses},'live':live,
        'source_files':{file:sha(ROOT/file)for file in [str(PLAN),'hardware/cad/legs/fivebar.py','hardware/cad/body/body_params.py','hardware/cad/turret/turret.py','tools/engineering/turret/reference-turret-motion.py','tools/engineering/robot/current_motion.py']},
        'engineering':plan['engineering'],'limits':plan['limits']}


def validate_rigid_controls(reference,baseline,fault_data,motion):
    tolerance=reference['tolerance_mm']
    baseline_report=motion.validate_motion_trace(reference['rigid']['contract'],baseline,tolerance_mm=tolerance)
    if baseline_report['status']!='pass':raise ValueError('Actual rigid baseline failed: '+json.dumps(baseline_report['failures']))
    faults={}
    for name,probe in fault_data.items():
        # Retain the complete baseline coverage and substitute actual fault
        # observations at the same input pose. Missing coverage alone is never
        # counted as a demonstrated geometry fault.
        trace=json.loads(json.dumps(baseline));trace['samples'][probe['sample_index']]=probe['sample']
        if name=='missing-part':
            expected=set(reference['rigid']['contract']['components']);actual=set(probe['sample']['components'])
            if len(expected-actual)!=1 or actual-expected:raise ValueError('Missing-part control must remove exactly one actual component')
            try:motion.validate_motion_trace(reference['rigid']['contract'],trace,tolerance_mm=tolerance)
            except ValueError as error:faults[name]={'status':'rejected-incomplete-input','reason':str(error)}
            else:raise ValueError('Missing actual component escaped')
        else:
            report=motion.validate_motion_trace(reference['rigid']['contract'],trace,tolerance_mm=tolerance)
            if report['status']!='fail' or report['coverage']!=baseline_report['coverage']:
                raise ValueError('Fault did not fail with unchanged complete coverage: '+name)
            if not any(f.get('check')=='rendered-landmarks' for f in report['failures']):
                raise ValueError('No geometric mismatch demonstrated: '+name)
            faults[name]={'status':report['status'],'failures':report['failures']}
        for control in (('home','restored')if probe.get('home_preserved')else('restored',)):
            restored=json.loads(json.dumps(baseline));restored['samples'][probe[control+'_index']]=probe[control]
            result=motion.validate_motion_trace(reference['rigid']['contract'],restored,tolerance_mm=tolerance)
            if result['status']!='pass':raise ValueError('Fault '+control+' control failed: '+name)
    required={'right-rotation','wrong-pivot-home-preserved','axis-sign','units','lost-parent','stationary-owner','missing-part'}
    if set(faults)!=required:raise ValueError('Incomplete actual fault membership')
    return {'status':'pass','baseline_report':baseline_report,'rejected_faults':faults}


def validate_capture(reference,folder,motion):
    """Only existing shared validator decides geometric/coverage verdicts."""
    folder=Path(folder);tolerance=reference['tolerance_mm']
    index=json.loads((folder/'capture-index.json').read_bytes())
    if (index.get('status')!='CAPTURED_AWAITING_INDEPENDENT_SHARED_VALIDATION' or index.get('listenerClosed')is not True
            or index.get('pageErrors')!=[] or index.get('manifestSha256')!=MODEL_SHA
            or index.get('collectionSha256')!=accepted.COLLECTION_SHA):
        raise ValueError('Incomplete/failed actual browser campaign')
    for file,binding in index['outputs'].items():
        path=folder/file
        if path.is_symlink()or not path.resolve().is_relative_to(folder.resolve())or sha(path)!=binding['sha256']or path.stat().st_size!=binding['bytes']:
            raise ValueError('Actual captured output identity differs')
    controls=validate_rigid_controls(reference,json.loads((folder/'rigid-capture.json').read_bytes()),
        json.loads((folder/'fault-captures.json').read_bytes()),motion)
    reports={'rigid':controls['baseline_report']}
    for row in reference['live']:
        trace=json.loads((folder/('live-'+row['id']+'.json')).read_bytes())
        report=motion.validate_motion_trace(row['contract'],trace,tolerance_mm=tolerance)
        if report['status']!='pass':raise ValueError('Actual complete live trace failed: '+row['id']+' '+json.dumps(report['failures']))
        reports[row['id']]=report
    operation=json.loads((folder/'operation-capture.json').read_bytes())
    if any(operation.get(key)is not True for key in ('exploded','reset','flapClosed'))or len(operation['trace']['samples'])!=91:
        raise ValueError('Incomplete actual operation/reset coverage')
    trace=json.loads((folder/'live-home.json').read_bytes());trace['samples']+=operation['trace']['samples']
    operation_report=motion.validate_motion_trace(reference['live'][0]['contract'],trace,tolerance_mm=tolerance)
    if operation_report['status']!='pass':raise ValueError('Actual operation trace failed')
    reports['operation']=operation_report
    async_controls=json.loads((folder/'async-model-controls.json').read_bytes())
    if (async_controls['failedRecorded'].get('rejected')is not True or async_controls['failedRecorded'].get('sameBase')is not True
            or async_controls['staleRecorded'].get('mode')!='current' or async_controls['staleRecorded'].get('holders')!=1
            or async_controls['disposedPending'].get('rejected')is not True or async_controls['disposedPending'].get('lateReady')is not False):
        raise ValueError('Actual asynchronous current/recorded recovery controls incomplete')
    modes=json.loads((folder/'mode-transitions.json').read_bytes());ui=json.loads((folder/'ui-model-roundtrip.json').read_bytes())
    if (modes.get('unchanged')is not True or modes.get('laserVisible')is not True or ui.get('sameRobot')is not True or ui.get('laser')is not True
            or modes['current']['info']['massKg']is not None or modes['restored']['info']['massKg']is not None
            or modes['recorded']['presentation']['mode']!='recorded'):
        raise ValueError('Actual complete-mode/readout/laser roundtrip incomplete')
    mobile=json.loads((folder/'mobile-error-recovery.json').read_bytes())
    if mobile.get('falseReady')is not False:raise ValueError('Mobile failed data was presented as ready')
    for route in ('hero','talk'):
        trace=json.loads((folder/('route-'+route+'-home-capture.json')).read_bytes())
        result=motion.validate_motion_trace(reference['live'][0]['contract'],trace,tolerance_mm=tolerance)
        if result['status']!='pass':raise ValueError('Actual route home/protocol failed: '+route)
        reports['route-'+route]=result
        combined=json.loads((folder/('live-'+reference['live'][-1]['id']+'.json')).read_bytes())
        combined['samples'].append(json.loads((folder/('route-'+route+'-combined-sample.json')).read_bytes()))
        result=motion.validate_motion_trace(reference['live'][-1]['contract'],combined,tolerance_mm=tolerance)
        if result['status']!='pass':raise ValueError('Actual route combined/non-home failed: '+route)
        reports['route-'+route+'-combined']=result
    return {'status':'pass','baseline_reports':reports,'rejected_faults':controls['rejected_faults'],
        'engineering':reference['engineering'],'limits':reference['limits']}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--candidate',type=Path)
    mode.add_argument('--reference',type=Path)
    parser.add_argument('--captures',type=Path)
    parser.add_argument('--reference-sha256')
    parser.add_argument('--toolkit',required=True,type=Path)
    parser.add_argument('--toolkit-revision',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    if args.output.exists():raise ValueError('Use a fresh independent reference output')
    motion=load_motion(args.toolkit,args.toolkit_revision)
    if args.candidate:
        result=build_reference(args.candidate,motion)
        result['shared_toolkit']={'revision':args.toolkit_revision,'motion_trace_sha256':sha(motion.__file__)}
        message='Wrote source reference only; no renderer/capture/qualification result'
    else:
        if not args.captures or not args.reference_sha256 or sha(args.reference)!=args.reference_sha256:
            raise ValueError('Actual capture directory and external reviewed reference digest required')
        reference=json.loads(args.reference.read_bytes())
        if reference.get('shared_toolkit')!={'revision':args.toolkit_revision,'motion_trace_sha256':sha(motion.__file__)}:
            raise ValueError('Recorded shared validator identity differs')
        if any(sha(ROOT/file)!=digest for file,digest in reference['source_files'].items()):
            raise ValueError('Independent source reference dependency changed')
        result=validate_capture(reference,args.captures,motion)
        message='Actual presentation traces pass; no physical/engineering qualification'
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(message)


if __name__=='__main__':main()
