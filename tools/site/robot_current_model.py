"""Product frame/ownership conversion of accepted collection266, without CAD.

Original STL bytes remain world CAD mm/Z-up. This adds presentation ownership;
it does not reconstruct solids, rerun physics or accept manufacturing evidence.
The command writes a fresh candidate only. Public adoption is a separate action.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(Path(__file__).with_name('assembly'))]
from robot_data import sha, vertices, landmarks
from export_robot_guide import verified_parts, encode
import robot_current_print_match as accepted

SCHEMA = 'gyropup.current-robot-presentation/1'
LEG_SOURCE = 'hardware/cad/legs/fivebar.py'
TURRET_SOURCE = 'hardware/cad/turret/turret.py'
LIMITS = ('Presentation of accepted tessellated envelopes only. No new physics, '
          'mass/COM, continuous clearance, bought-interface, load, support, drop, '
          'physical fit or manufacturing qualification. Historical studies keep '
          'their original geometry, frames and failures.')

# Source ownership, not fivebar.STATIC (a collision optimization). Point owners
# preserve the source's translate-only bearing/pin/washer envelopes. The D69
# hub combines drum and axle, so its unsplit source envelope never spins as a
# whole. Only the independently named tyre rotates for wheel presentation.
LEG_OWNERS = {
    'fixed': ['hip_frame', 'motor_front', 'motor_rear', 'bearing_61812_front',
              'bearing_61812_rear', 'stop_posts', 'screws_lugs',
              *['stop_sleeve_'+str(i) for i in range(1,5)]],
    'upper_front': ['output_adapter_front', 'upper_link_front', 'knee_nut_upper_front'],
    'upper_rear': ['output_adapter_rear', 'upper_link_rear', 'knee_nut_upper_rear'],
    'front_link': ['front_link'], 'wheel_link': ['wheel_link'],
    'knee_front_point': ['knee_bearing_front_in', 'knee_bearing_front_out',
                         'knee_pin_front', 'knee_washer_front', 'knee_spacer_front', 'eye_sleeve_front'],
    'knee_rear_point': ['knee_bearing_rear_in', 'knee_bearing_rear_out',
                        'knee_pin_rear', 'knee_washer_rear', 'knee_spacer_rear', 'eye_sleeve_rear'],
    'apex_point': ['apex_spacer', 'apex_61812', 'apex_circlip', 'wheel_hub',
                   'screws_wheel', 'washers_wheel'],
    'wheel': ['wheel_tyre'],
}
GROUPED = ('screws_links', 'screws_outputs')


def source_fivebar(root):
    """Read only the existing current pure mechanical functions, without imports.

    The caller must first validate the exact accepted input closure. No CAD
    module/top-level statement or historical checkout is executed. Expected
    poses remain independently sourced from these CAD functions, not JS groups.
    """
    tree = ast.parse((Path(root)/LEG_SOURCE).read_text())
    params = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                  and any(isinstance(t,ast.Name) and t.id=='PARAMS' for t in n.targets))
    names = {'motors','fk','ik','stance','link_frames','_rear'}
    functions = [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    if {n.name for n in functions} != names or any(n.decorator_list for n in functions):
        raise ValueError('Current pure mechanical function boundary changed')
    scope = {'math':math, 'P':params}
    exec(compile(ast.Module(body=functions,type_ignores=[]), LEG_SOURCE+' pure frames', 'exec'),scope)
    return scope


def turret_owners(root):
    """Read current made/bought frame declarations; never use bench geometry."""
    tree = ast.parse((Path(root)/TURRET_SOURCE).read_text())
    made = next(n.value for n in tree.body if isinstance(n,ast.Assign)
                and any(isinstance(t,ast.Name) and t.id=='MADE' for t in n.targets))
    owners = {}
    for entry in made.elts:
        name,frame,quantity = (ast.literal_eval(entry.elts[i]) for i in (0,2,4))
        for i in range(quantity): owners[name if i==0 else name+'_'+str(i+1)] = frame
    bought = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='bought_parts')
    for n in ast.walk(bought):
        if not isinstance(n,ast.Assign) or not isinstance(n.value,ast.Tuple):continue
        for target in n.targets:
            if (isinstance(target,ast.Subscript) and isinstance(target.value,ast.Name)
                    and target.value.id=='out' and isinstance(target.slice,ast.Constant)):
                owners[ast.literal_eval(target.slice)] = ast.literal_eval(n.value.elts[1])
    # Named paired cheek plates, flywheel motor envelopes and ESCs.
    paired=0
    for loop in bought.body:
        if not isinstance(loop,ast.For) or not isinstance(loop.target,ast.Tuple) or not isinstance(loop.iter,ast.Tuple):continue
        names=[t.id if isinstance(t,ast.Name) else None for t in loop.target.elts]
        if 'nm' not in names:continue
        assignments=[n for n in ast.walk(loop) if isinstance(n,ast.Assign) and isinstance(n.value,ast.Tuple)
                     and any(isinstance(t,ast.Subscript) and isinstance(t.slice,ast.Name) and t.slice.id=='nm' for t in n.targets)]
        if len(assignments)!=1:raise ValueError('Turret variable bought-frame declaration changed')
        frame=ast.literal_eval(assignments[0].value.elts[1])
        for entry in loop.iter.elts:owners[ast.literal_eval(entry.elts[names.index('nm')])]=frame
        paired+=1
    if paired!=3:raise ValueError('Turret paired bought-frame membership changed')
    board_tree=ast.parse((Path(root)/'hardware/cad/turret/turret_base_board.py').read_text())
    public=next(n for n in board_tree.body if isinstance(n,ast.FunctionDef) and n.name=='public_parts')
    board_loop=next(n for n in public.body if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='group')
    for key in ast.literal_eval(board_loop.iter):owners[key]='base'
    # These mechanisms are explicitly separated by the existing turret-box
    # presentation exporter; all their meshes still come from collection266.
    owners.update(flywheel='wheel_l',flywheel_2='wheel_r',
                  flywheel_tyre='wheel_l',flywheel_tyre_2='wheel_r',dial='dial',hopper_flap='flap')
    if len(owners)!=62 or set(owners.values())-{'base','pan','tilt','pinion','wheel_l','wheel_r','dial','flap'}:
        raise ValueError('Current turret ownership membership changed')
    return owners


def partition_screws(points, side, logical, root):
    """Disjoint source motor-centred screw envelopes; every triangle once."""
    standard=json.loads((Path(root)/'hardware/cad/robot/interfaces.json').read_text())['AO-L']
    output=json.loads((Path(root)/'hardware/catalog/interfaces.json').read_text())['robstride-rs-04']['output']
    # screw_groups: links use AO-L PCD/head8.5; outputs use output PCD/AO-L head.
    radius = (standard['pcd']/2+8.5/2 if logical=='screws_links'
              else output['bolts']['pcd']/2+standard['head']['d']/2)
    sign=1 if side=='L' else -1
    result={'upper_front':[], 'upper_rear':[]}
    if len(points)%3:raise ValueError('Incomplete source triangle')
    for i in range(0,len(points),3):
        triangle=points[i:i+3]
        possible=[name for name,cx in [('upper_front',75.),('upper_rear',-75.)]
                  if all(math.hypot(sign*p[0]-cx,p[2])<=radius+.001 for p in triangle)]
        if len(possible)!=1:raise ValueError('Ambiguous/straddling grouped screw triangle')
        result[possible[0]].append(i//3)
    if not all(result.values()) or sorted(sum(result.values(),[]))!=list(range(len(points)//3)):
        raise ValueError('Incomplete/duplicate grouped screw partition')
    return result


def generate(root, collection, folder):
    root,folder=Path(root),Path(folder)
    evidence=accepted.binding(root,collection,folder)
    parts=verified_parts(collection,folder)
    mechanical=source_fivebar(root)
    phi=mechanical['stance'](300.)
    frames,joints=mechanical['link_frames'](*phi)
    p=mechanical['P']; owners={'body':{'parent':None,'origin_mm':[0,0,0],'axis':[0,0,0],'home_rad':0}}
    def owner(name,parent,origin,axis=(0,0,0),angle=0):
        owners[name]={'parent':parent,'origin_mm':list(origin),'axis':list(axis),'home_rad':angle}
    for side in ('L','R'):
        module=side+'.module'
        owner(module,'body',[0,(1 if side=='L' else -1)*accepted.Y_OFF,0],(0,0,1),0 if side=='L' else math.pi)
        owner(side+'.fixed',module,[0,0,0])
        for key,parent in [('upper_front',module),('upper_rear',module),('front_link',side+'.upper_front'),('wheel_link',side+'.upper_rear')]:
            (x,z),rot=frames[key]
            parent_key=parent.split('.')[-1]
            if parent_key in frames:
                origin=[p['l1'],0,0];angle=math.radians(rot-frames[parent_key][1])
            else:origin=[x,0,z];angle=math.radians(rot)
            owner(side+'.'+key,parent,origin,(0,1,0),angle)
        for key,j in [('knee_front_point','C'),('knee_rear_point','D'),('apex_point','E')]:
            owner(side+'.'+key,module,[joints[j][0],0,joints[j][1]])
        owner(side+'.wheel',side+'.apex_point',[0,0,0],(0,1,0))
    tm=collection['datums']['tm']; mount=[tm['pan_x'],0,tm['face_z']]
    owner('turret.base','body',mount)
    owner('turret.pan','turret.base',[0,0,0],(0,0,1))
    owner('turret.tilt','turret.pan',[0,0,140],(0,-1,0))
    owner('turret.pinion','turret.base',[-52.65,0,0],(0,0,1))
    for key,origin,axis in [('dial',[-48,0,0],(0,0,1)),('wheel_l',[25,25.81,0],(0,0,1)),
                            ('wheel_r',[25,-25.81,0],(0,0,1)),('flap',[-87,0,91],(0,-1,0))]:
        owner('turret.'+key,'turret.tilt',origin,axis)
    turret=turret_owners(root)
    leg={n:k for k,names in LEG_OWNERS.items() for n in names}
    if len(leg)!=38:raise ValueError('Leg ownership inventory changed')
    model=[];counts={'body':0,'leg':0,'turret':0}
    for part in parts:
        name=part['name'];points=vertices(folder/part['file'])
        record={key:part[key] for key in ('name','file','sha256','bounds_mm','color','source_group','visible')}
        record['landmarks_mm']=landmarks(points)
        record['landmark_vertex_indices']=[points.index(point) for point in record['landmarks_mm']]
        if name.startswith(('L.','R.')):
            side,logical=name.split('.',1);counts['leg']+=1
            if logical in GROUPED:
                partition=partition_screws(points,side,logical,root)
                record['partitions']=[]
                for key,ids in partition.items():
                    selected=[points[t*3+v]for t in ids for v in range(3)]
                    marks=landmarks(selected)
                    record['partitions'].append({'owner':side+'.'+key,'triangle_indices':ids,
                        'landmarks_mm':marks,'landmark_vertex_indices':[selected.index(point)for point in marks]})
                record['triangle_records_sha256']=hashlib.sha256((folder/part['file']).read_bytes()[84:]).hexdigest()
            elif logical in leg:record['owner']=side+'.'+leg[logical]
            else:raise ValueError('Unassigned current leg part: '+name)
        elif name.startswith('turret.'):
            counts['turret']+=1;record['owner']='turret.'+turret[name.removeprefix('turret.')]
        else:counts['body']+=1;record['owner']='body'
        model.append(record)
    if counts!={'body':82,'leg':80,'turret':62}:raise ValueError('Current complete224 ownership differs')
    bounds=[min(part['bounds_mm'][i]for part in parts)for i in range(3)]+[max(part['bounds_mm'][i]for part in parts)for i in range(3,6)]
    conversion_inputs=['tools/site/robot_current_model.py','tools/site/assembly/robot_data.py',
        'tools/site/assembly/export_robot_guide.py','tools/site/assembly/robot_recipe.py',
        'tools/site/assembly/robot_current_print_match.py','tools/site/assembly/robot_current_print_acceptance.py',
        'tools/evidence/manufacturing/retained_fit_history.py']
    return {'schema':SCHEMA,'units':'mm','up':'z','native_source':accepted.SOURCE,
            'collection_sha256':accepted.COLLECTION_SHA,'native_producer_inputs':collection['producer_inputs'],
            'native_runtime':collection['runtime'],'current_inputs':evidence['current_inputs'],
            'conversion':{'file':Path(__file__).relative_to(ROOT).as_posix(),'sha256':sha(__file__),
                          'python':list(sys.version_info[:3]),'inputs':{file:sha(root/file)for file in conversion_inputs},
                          'method':'original world STL + product joint ownership; no CAD execution'},
            'ownership_counts':counts,'owners':owners,'parts':model,
            'moving_coverage':{'mesh_inventory_complete':True,'mechanical_ownership_verified':False,
                'unresolved_composite_envelopes':['L.wheel_hub','R.wheel_hub','turret.flywheel_motor_l','turret.flywheel_motor_r'],
                'basis':'Source envelopes combine rotating and fixed subcomponents. Whole-envelope support ownership is presentation only; rotating internal components are not independently resolved. Tyres and separate turret flywheels still require motion traces.'},
            'home':{'leg_mm':300.,'pan_rad':0.,'tilt_rad':0.,'wheel_rad':0.},
            'home_bounds_mm':bounds,
            'frame_contract':'Original world CAD-mm/Z-up vertices; each display mesh is localized by the inverse owner home world matrix. Right module is a proper RZ180 rotation. All child origins/axes are in parent-local CAD coordinates.',
            'fivebar':{'D_mm':p['D'],'l1_mm':p['l1'],'l2_mm':p['l2'],'y_off_mm':accepted.Y_OFF,
                       'h_range_mm':[185.,375.],'wheel_radius_mm':127.,'right_basis':'RZ180; no reflection',
                       'wheel_hub_basis':'Unsplit drum+axle source envelope translates at apex; only tyre spins.'},
            'mounts':{'eyes':[162.6,0,182.],'eyes_board_front':[160.6,0,182.],
                      'camera_front':[192.6,0,142.5],'camera_rear':[-192.6,0,142.5],
                      'headlights':[[55.,155.,160.],[55.,-155.,160.]],
                      'pan':mount,'tilt':[mount[0],0,mount[2]+140.],
                      'muzzle':[110.,0,371.],'laser':[44.5,0,400.5]},
            'engineering':{'mass_kg':None,'com_mm':None,'physics_current':False,
                           'manufacturing_released':False,'physical_qualified':False},'limits':LIMITS}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args(argv)
    raw=args.collection.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=accepted.COLLECTION_SHA:raise ValueError('Original accepted collection bytes required')
    collection=json.loads(raw);folder=args.collection.parent
    model=generate(ROOT,collection,folder)
    outputs={'manifest.json':encode(model),'collection.json':raw,
             **{p['file']:(folder/p['file']).read_bytes()for p in model['parts']}}
    if not args.check and args.out.exists():raise ValueError('Use a fresh candidate output root')
    for name,data in outputs.items():
        path=args.out/name
        if args.check:
            if path.is_symlink() or path.read_bytes()!=data:raise ValueError('Current presentation artifact differs: '+name)
        else:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    if args.check and {p.relative_to(args.out).as_posix() for p in args.out.rglob('*') if p.is_file()}!=set(outputs):
        raise ValueError('Current presentation output membership differs')
    print(('PASS' if args.check else 'Candidate only:')+'224 original meshes; complete ownership; no physical qualification')


if __name__=='__main__':main()
