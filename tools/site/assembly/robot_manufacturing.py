"""Grounded links to existing manufacturing originals; posed meshes are never printable."""
from __future__ import annotations
import json
from pathlib import Path
from robot_data import sha

QUALIFICATION='Recorded WIP source only; printability, fits and physical qualification remain separate.'
LEG_KEYS={
 'motor_front':'robstride-rs-04','motor_rear':'robstride-rs-04',
 'wheel_hub':'odrive-botwheel','wheel_tyre':'odrive-botwheel',
 'bearing_61812_front':'bearing_61812','bearing_61812_rear':'bearing_61812','apex_61812':'bearing_61812',
 'knee_pin_front':'knee_pin','knee_pin_rear':'knee_pin','knee_spacer_front':'knee_spacer','knee_spacer_rear':'knee_spacer',
 'knee_washer_front':'washer_m12_thin','knee_washer_rear':'washer_m12_thin',
 'knee_nut_upper_front':'nut_m10_nyloc','knee_nut_upper_rear':'nut_m10_nyloc',
 'eye_sleeve_front':'eye_sleeve','eye_sleeve_rear':'eye_sleeve','apex_circlip':'circlip_60','stop_posts':'stop_pin',
 'screws_lugs':'screw_m4x20','screws_links':'screw_m5x40','screws_outputs':'screw_m5x25',
 'screws_wheel':'screw_m6x30','washers_wheel':'washer_m6_din433',
 **{'knee_bearing_'+end+'_'+which:'bearing_6301' for end in ('front','rear') for which in ('in','out')},
}
BODY_KEYS={'item.battery_front':'dewalt-dcb609','item.battery_rear':'dewalt-dcb609',
 'item.plate_vesc_l':'flipsky-75100','item.plate_vesc_r':'flipsky-75100','item.vn100':'vectornav-vn-100-rugged',
 'item.plate_main_switch':'main_switch','item.plate_shunt':'shunt_150a','item.power_dcdc':'traco-tep-150-4812wi',
 'item.plate_mrbf_block':'blue-sea-5191-mrbf-terminal-fuse-block','item.plate_mcu_board':'nucleo_g474re',
 'item.plate_buck_5v':'buck_5v','spacers':'standoff_m4x31_ff','spacer_screws':'screw_m4x10_flat',
 'frame_screws_left':'screw_m5x12_button','frame_screws_right':'screw_m5x12_button'}
BODY_FAMILIES={'cheek_left':'cheek','cheek_right':'cheek','bay_side_l':'bay_side','bay_side_r':'bay_side',
 **{f'{name}_{i}':name for name in ('post','plate_post','isolator','bay_skid') for i in range(1,5)},
 'bus_bar_1':'bus_bar','bus_bar_2':'bus_bar','bus_insulator_1':'bus_insulator','bus_insulator_2':'bus_insulator'}


def hip_geometry_match(root,collection,name):
    """Only the independently reviewed hip correspondence may enable WIP prep."""
    if collection is None or name not in ('L.hip_frame','R.hip_frame'):return None
    file='.agents/plans/robot-assembly/hip-print-match.json';root=Path(root)
    if not (root/file).is_file():return None
    from robot_print_match import source_guard
    try:
        proof=json.loads((root/file).read_text())
        if not proof.get('review_url','').startswith('https://github.com/Valpatel/gyropup/pull/270#'):return None
        receipt=source_guard(root,collection)
        part=next(p for p in collection['parts'] if p['name']==name);side=name[0]
        if (proof.get('status')!='SOURCE_MATCH_CORROBORATED' or proof['native_source']!=collection['source_commit']
            or proof['cad_inputs']!=collection['inputs']
            or proof['receipt_sha256']!=sha(root/'hardware/exports/leg/rs04-mounting-fit/checks.json')
            or proof['original_sha256']!=sha(root/'hardware/exports/leg/hip_frame.stl')
            or proof['sampler_sha256']!=sha(root/'tools/site/assembly/robot_print_match.py')
            or proof['sides'][side]['mesh_sha256']!=part['sha256']
            or proof['tessellation_allowance_mm']!=.3011
            or proof['negative_controls'].get('actual_mesh_shift_3mm') is not True
            or proof['engineering_counts']!=receipt['counts']
            or any(proof.get(flag) is not False for flag in ('physical_fit_verified','strength_verified','manufacturing_released'))):
            return None
        for direction in ('a_to_b','b_to_a'):
            sample=proof['sides'][side][direction]
            if sample['samples']<=0 or not 0<=sample['max_distance_mm']<=.3011:return None
        return {'status':'matched','geometry_source_match':True,'evidence':{'source_file':file,'sha256':sha(root/file)},
                'basis':'Same source hip model through a current full producer receipt, exact original bytes and sampled bidirectional tessellation correspondence in the authored print frame.',
                'qualification':'WIP geometry-file preparation only; physical fit, support failures, printer/filament/slice choices and strength remain unresolved.'}
    except (ValueError,KeyError,StopIteration,FileNotFoundError,TypeError):return None


def mapping(root,names,collection=None):
    root=Path(root)
    def read(file):return json.loads((root/file).read_text())
    def binding(file):return {'source_file':file,'sha256':sha(root/file)}
    def original(file):
        path=root/file
        if path.is_symlink() or not path.is_file() or not file.startswith('hardware/exports/') or '/build-guides/' in file:
            raise ValueError('Manufacturing original is missing or is a posed guide mesh')
        return {**binding(file),'public_file':'/'+file.removeprefix('hardware/')}
    plans={
      'leg':('hardware/exports/leg/print-plan.json',read('hardware/exports/leg/print-plan.json')['parts']),
      'body':('hardware/exports/body/print-plan.json',read('hardware/exports/body/print-plan.json')['parts']),
      'shell':('hardware/exports/body/shell/print-plan.json',read('hardware/exports/body/shell/print-plan.json')['parts'])}
    body=read('hardware/exports/body/body.json');leg=read('hardware/exports/leg/leg.json')
    boms={key:('hardware/exports/'+key+'/bom.json',read('hardware/exports/'+key+'/bom.json')) for key in ('leg','body')}
    result={}
    for name in names:
        row={'kind':'unresolved','originals':[],'qualification':QUALIFICATION,
             'geometry_match':{'status':'pending','basis':'No current collected-part to manufacturing-original correspondence has been accepted.'},
             'reason':'No verified manufacturing/catalogue mapping for this modeled instance.'}
        result[name]=row
        if name.startswith('turret.'):
            row['reason']='Use the separately bound Turret guide mapping; module placement does not invent internal manufacturing links.';continue
        physical_leg=name.startswith(('L.','R.'));logical=name.split('.',1)[1] if physical_leg else name
        family=('upper_link' if logical.startswith('upper_link_') else 'output_adapter' if logical.startswith('output_adapter_')
                else 'stop_sleeve' if logical.startswith('stop_sleeve_') else logical) if physical_leg else BODY_FAMILIES.get(name,name)
        plan_key='leg' if physical_leg else 'body' if family in plans['body'][1] else 'shell'
        plan_file,printed=plans[plan_key]
        if family in printed:
            value=printed[family];stream='leg' if physical_leg else 'body'
            folder='leg' if physical_leg else 'body/shell' if plan_key=='shell' else 'body'
            row.update(kind='print',key=family,stream=stream,part_key='print/'+stream+'/'+family,
                originals=[original('hardware/exports/'+folder+'/'+family+'.stl')],
                plan={**binding(plan_file),'material':value['material'],'qty':value['qty'],
                      'qty_scope':'per_leg' if physical_leg else 'body','infill':value.get('infill')})
            row['geometry_match']['basis']='Identified retained manufacturing original only. File identity and plan membership do not prove a match to the collected CAD instance.'
            match=hip_geometry_match(root,collection,name)
            if match:row['geometry_match']=match
            row.pop('reason');continue
        if physical_leg and family in leg.get('made_to_order',{}):
            file='hardware/'+leg['made_to_order'][family]
            row.update(kind='machine',stream='leg',key=family,part_key='made/leg/'+family,
                       originals=[original(file)],source=binding('hardware/exports/leg/leg.json'))
            row.pop('reason');continue
        if not physical_leg and family in body['sheet']:
            value=body['sheet'][family]
            row.update(kind='sheet',stream='body',key=family,part_key='made/body/'+family,
                       originals=[original('hardware/'+value[k]) for k in ('step','dxf') if value.get(k)],
                       plan={**binding('hardware/exports/body/body.json'),'material':value['material'],'qty':value['qty'],'qty_scope':'body'})
            row.pop('reason');continue
        key=LEG_KEYS.get(logical) if physical_leg else BODY_KEYS.get(name)
        if key:
            bom_file,bom=boms['leg' if physical_leg else 'body']
            records=[{'list':section,'row':r} for section,values in bom.items() if isinstance(values,list)
                     for r in values if isinstance(r,dict) and r.get('key')==key]
            if not records:raise ValueError('Declared catalogue key is absent from the actual BOM: '+name)
            row.update(kind='bought',key=key,part_key='buy/'+key,source=binding(bom_file),
                       recorded_quantities=[{'list':r['list'],'qty':r['row'].get('qty'),'qty_scope':'per_leg' if physical_leg else 'body'} for r in records])
            if logical in ('wheel_hub','wheel_tyre'):
                row['component_of']=name[0]+'.wheel';row['reason']='Hub and tyre are components of the same bought wheel, not two independently ordered wheels.'
            else:row.pop('reason')
    return result
