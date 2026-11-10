"""One fresh individual-part tessellation through the existing real robot collector.

Run only inside the separately reviewed bounded compute-host procedure. This
worker never calls robot.export/render or writes manufacturing products.
"""
from __future__ import annotations
import argparse
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
from robot_data import bounds, landmarks, module_point, nearest_errors, sha, vertices, inventory, mesh_files
from robot_recipe import robot_operations, validate_operations


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def git(root,*args):
    return subprocess.check_output(['git','-c','safe.directory='+str(root),'-C',str(root),*args],text=True).strip()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--toolkit',type=Path,required=True)
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[3]
    out=args.out.resolve();toolkit=args.toolkit.resolve()
    if out.is_relative_to(root) or out.exists():
        raise ValueError('Use a fresh output outside the source checkout')
    if git(root,'status','--porcelain','--untracked-files=all'):
        raise ValueError('A clean immutable worker checkout is required')
    sys.dont_write_bytecode=True
    helper=load('robot_assembly_source_guard',root/'tools/engineering/robot/readme_design.py')
    cfg=json.loads((root/helper.CONFIG).read_text())
    inputs=helper.verify_inputs(root,cfg);helper.verify_public_tree(root,cfg)
    if git(toolkit,'rev-parse','HEAD')!=cfg['toolkit']['revision'] or git(toolkit,'status','--porcelain'):
        raise ValueError('Use the exact clean recorded CAD toolkit')
    out.mkdir(mode=0o700,parents=True);(out/'meshes').mkdir();(out/'reference').mkdir()
    result={'status':'FAILED','adoption_approved':False,'limits':'CAD assembly/pose evidence only; no physical or manufacturing qualification','started':time.time()}
    before=helper.tracked(root);hardware_before=inventory(root/'hardware')
    save(out/'source-before.json',before);save(out/'hardware-before.json',hardware_before)
    primary=None
    try:
        os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',J501_DIR=str(out/'no-live-j501'))
        if any(n=='hardware' or n.startswith('hardware.') for n in sys.modules):
            raise ValueError('Fresh process without cached project CAD required')
        sys.path[:0]=[str(root),str(toolkit/'software')]
        import cadagent
        import cadquery as cq
        import numpy
        runtime={k:importlib.metadata.version(k) for k in ('cadquery','numpy','cadquery-ocp','vtk')}
        runtime['cad_agent_revision']=git(toolkit,'rev-parse','HEAD')
        origins_runtime={}
        for name,module in (('cadquery',cq),('numpy',numpy)):
            location=Path(module.__file__).resolve()
            if not location.is_relative_to(Path(sys.prefix).resolve()):
                raise ValueError('Native package imported outside the retained runtime: '+name)
            origins_runtime[name]=location.relative_to(Path(sys.prefix).resolve()).as_posix()
        if runtime!=cfg['runtime'] or not Path(cadagent.__file__).resolve().is_relative_to(toolkit/'software/cadagent'):
            raise ValueError('Actual imported CAD runtime differs')
        from hardware.cad.body import body_params as bp
        bp.CACHE=out/'body-measurement-cache'
        robot=load('robot_assembly_collector',root/helper.SOURCE_CONTEXT)
        print('Collecting actual named CAD assembly',flush=True)
        rows=robot.collect()
        if bp.j501_params().get('_source')!='hardware/vendor/j501/parameters-0.9-g48r.json':
            raise ValueError('Actual collector did not use tracked J501 parameters')
        names=[n for _,_,n,_,_ in rows]
        if len(names)!=len(set(names)) or not names:
            raise ValueError('Empty or duplicate source assembly names')
        validate_operations(robot_operations(),[n for n in names if not n.startswith('turret.')])
        filenames=mesh_files(names)
        parts=[]
        for group,color,name,shape,offset in rows:
            file=filenames[name]
            cq.exporters.export(shape,str(out/file),tolerance=.25,angularTolerance=.3,opt={'ascii':False})
            parts.append({'name':name,'file':file,'color':color,'visible':True,'bounds_mm':bounds(out/file),'sha256':sha(out/file),'source_group':group,'compound':len(shape.Solids())>1,'source_shape_valid':bool(shape.isValid())})
            print('PART '+name,flush=True)
        # Independent module-to-body reference: source local parts, not the display manifest.
        from hardware.cad.legs import fivebar as fb
        old=fb.gmi.STEP_FRAMES.pop(fb.MOTOR,None);fb.motor_model.cache_clear()
        try:
            module=fb.assembly(*fb.stance(robot.STANCE_MM),with_bought=True)
        finally:
            if old:fb.gmi.STEP_FRAMES[fb.MOTOR]=old
            fb.motor_model.cache_clear()
        references={};by_name={p['name']:p for p in parts}
        for name in ('hip_frame','motor_front','motor_rear','upper_link_front','upper_link_rear','front_link','wheel_link',
                     'knee_pin_front','knee_pin_rear','wheel_hub','wheel_tyre'):
            shape,_=module[name];file='reference/'+name+'.stl'
            cq.exporters.export(shape,str(out/file),tolerance=.25,angularTolerance=.3,opt={'ascii':False})
            local=landmarks(vertices(out/file));sides={}
            for side in ('L','R'):
                expected=[module_point(p,side,bp.y_off()) for p in local]
                actual=vertices(out/by_name[side+'.'+name]['file'])
                errors=nearest_errors(expected,actual)
                if max(errors)>.02:
                    save(out/'frame-failure.json',{'part':side+'.'+name,'local_file':file,'expected_mm':expected,
                         'errors_mm':[e if e!=float('inf') else None for e in errors],'world_file':by_name[side+'.'+name]['file'],
                         'limit_mm':.02,'reason':'Source module landmarks do not match actual assembled vertices'})
                    raise ValueError('Actual assembled vertices differ from physical source frame: '+side+'.'+name+' '+str(errors))
                sides[side]={'expected_mm':expected,'errors_mm':errors}
            references[name]={'file':file,'sha256':sha(out/file),'local_landmarks_mm':local,'sides':sides}
        tm=bp.tm()
        foot=vertices(out/by_name['turret.pan_base']['file'])
        contact=[p for p in foot if abs(p[2]-tm['face_z'])<=.02]
        riser_top=by_name['riser']['bounds_mm'][5]
        def circles_at_face(shape):
            points=[]
            for edge in shape.Edges():
                if edge.geomType()=='CIRCLE':
                    center=edge.arcCenter().toTuple()
                    if abs(center[2]-tm['face_z'])<=.02:points.append(center)
            return points
        shapes={name:shape for _,_,name,shape,_ in rows}
        expected_mount=[(tm['pan_x']+x,y,tm['face_z']) for x,y in tm['bolts']]
        mount_centers={n:circles_at_face(shapes[n]) for n in ('riser','turret.pan_base')}
        mount_errors={n:nearest_errors(expected_mount,points) for n,points in mount_centers.items()}
        if any(e>.02 for errors in mount_errors.values() for e in errors):
            save(out/'mount-xy-failure.json',{'expected_bolt_centers_mm':expected_mount,'actual_circle_centers_mm':mount_centers})
            raise ValueError('Actual TM bolt-circle centers do not agree with source body mount X/Y/Z')
        wrong_xy=circles_at_face(shapes['turret.pan_base'].translate((5,-7,0)))
        xy_negative=any(e>.02 for e in nearest_errors(expected_mount,wrong_xy))
        if not xy_negative:raise ValueError('Wrong-X/Y native mount negative was accepted')
        mount_reference={'expected_bolt_centers_mm':expected_mount,'actual_circle_centers_mm':mount_centers,
                         'bolt_center_errors_mm':mount_errors,'wrong_xy_native_shift_mm':[5,-7,0],
                         'wrong_xy_rejected':xy_negative,'tm_face_z_mm':tm['face_z'],'pan_x_mm':tm['pan_x'],
                         'riser_top_mm':riser_top,'pan_base_contact_vertices':len(set(contact)),'limit_mm':.02}
        save(out/'mount-reference.json',mount_reference)
        if abs(riser_top-tm['face_z'])>.02 or len(set(contact))<3:
            raise ValueError('Actual mounted turret does not share the body riser TM plane')
        origins={}
        for name,mod in list(sys.modules.items()):
            if name=='hardware' or name.startswith('hardware.'):
                paths=[mod.__file__] if getattr(mod,'__file__',None) else list(getattr(mod,'__path__',()))
                if not paths or any(not Path(p).resolve().is_relative_to(root) for p in paths):
                    raise ValueError('Project CAD imported outside owned checkout: '+name)
                origins[name]=[Path(p).resolve().relative_to(root).as_posix() for p in paths]
        native_libraries=[]
        for line in Path('/proc/self/maps').read_text().splitlines():
            if '.so' not in line:continue
            if line.endswith(' (deleted)'):raise ValueError('Mapped native library was unlinked during collection')
            path=line.split()[-1]
            if path.startswith('/'):
                entry={'name':Path(path).name,'sha256':sha(Path(path))}
                if entry not in native_libraries:native_libraries.append(entry)
        record={'runtime_package_origins':origins_runtime,'native_libraries':native_libraries,'schema':'gyropup.robot-assembly-parts/1','units':'mm','up':'z','frame':'robot: x forward,y left,z up; hip-axis origin',
                'source_commit':git(root,'rev-parse','HEAD'),'hardware_tree':git(root,'rev-parse','HEAD:hardware'),
                'inputs':inputs,'producer_inputs':{p:sha(root/p) for p in ('tools/site/assembly/collect_robot_parts.py','tools/site/assembly/robot_data.py','tools/site/assembly/robot_recipe.py','tools/site/assembly/robot_runtime.py','tools/site/assembly/run_robot_collection.py','tools/site/assembly/export_robot_guide.py','tools/site/assembly/robot_manufacturing.py','tools/engineering/robot/readme_design.py','tools/engineering/robot/readme-design.json')},'collector_sha256':sha(root/helper.SOURCE_CONTEXT),'runtime':runtime,
                'configuration':{'stage':'P3','stance_mm':robot.STANCE_MM,'tracked_j501':True,'bought_parts':'existing project envelopes'},
                'datums':{'y_off_mm':bp.y_off(),'tm':tm},'mount_reference':mount_reference,'parts':parts,'module_reference':references,'module_origins':origins}
        save(out/'collection.json',record)
        result.update(status='COLLECTED_CANDIDATE_ONLY',parts=len(parts),collection_sha256=sha(out/'collection.json'))
    except BaseException as exc:
        primary=exc;result['original_error']=type(exc).__name__+': '+str(exc)
        raise
    finally:
        errors=[]
        for label,check in [('tracked',lambda:helper.tracked(root)),('hardware',lambda:inventory(root/'hardware')),
                            ('toolkit',lambda:git(toolkit,'status','--porcelain'))]:
            try:
                actual=check();save(out/(label+'-after.json'),actual)
                if label=='tracked' and actual!=before or label=='hardware' and actual!=hardware_before or label=='toolkit' and actual:
                    raise ValueError('Final preservation guard failed: '+label)
            except BaseException as exc:errors.append(label+': '+str(exc))
        result['final_errors']=errors
        if errors:result['status']='FAILED'
        try:save(out/'worker-result.json',result)
        except BaseException:
            if primary is None:raise
        if errors and primary is None:raise RuntimeError('; '.join(errors))


if __name__=='__main__':
    main()
