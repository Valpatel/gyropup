"""Pure guide/original binding controls; fresh CAD collection is still separate."""
import hashlib
import json
from pathlib import Path
import struct
import shutil
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/site/assembly'))
from robot_data import bounds,sha
from robot_manufacturing import mapping
from export_robot_guide import generate,verified_parts
from robot_recipe import robot_operations


class DataGuide(unittest.TestCase):
    def test_collected_wheel_cannot_inherit_the_historical_botwheel_sku(self):
        names=[side+'.'+part for side in ('L','R') for part in ('wheel_hub','wheel_tyre')]
        historical=mapping(ROOT,names)
        self.assertTrue(all(row['part_key']=='buy/odrive-botwheel' for row in historical.values()))
        for collection in ({'source_commit':'3a40891962b0b0a04625e070700f1d130bea3c7b'},
                           {'source_commit':'unknown'}):
            current=mapping(ROOT,names,collection)
            for name,row in current.items():
                self.assertEqual(row['kind'],'unresolved')
                self.assertEqual(row['component_of'],name[0]+'.wheel')
                self.assertEqual(row['originals'],[])
                for field in ('key','part_key','source','recorded_quantities'):
                    self.assertNotIn(field,row)
                self.assertNotIn('odrive-botwheel',json.dumps(row))
                self.assertNotIn('BW0124',json.dumps(row))
                if collection['source_commit'].startswith('3a408919'):
                    ref=row['design_reference']
                    self.assertEqual((ref['nominal_diameter_mm'],ref['tyre_band_width_mm']),(254,64))
                    self.assertFalse(ref['ordered_sku_verified']);self.assertFalse(ref['physical_measurements_verified'])
                    self.assertEqual(ref['sha256'],sha(ROOT/ref['source_file']))

    def test_manufacturing_links_are_originals_and_handed_modules_share_parts(self):
        names=['L.hip_frame','R.hip_frame','L.upper_link_front','R.upper_link_front','L.wheel_hub','L.wheel_tyre',
               'L.knee_bearing_front_in','cheek_left','cheek_right','item.battery_adapter_front','turret.pan_base']
        m=mapping(ROOT,names)
        self.assertEqual(m['L.upper_link_front']['originals'],m['R.upper_link_front']['originals'])
        self.assertEqual(m['cheek_left']['originals'],m['cheek_right']['originals'])
        self.assertEqual(m['L.wheel_hub']['component_of'],m['L.wheel_tyre']['component_of'])
        self.assertEqual(m['L.knee_bearing_front_in']['key'],'bearing_6301')
        self.assertEqual(m['item.battery_adapter_front']['kind'],'unresolved')
        self.assertEqual(m['turret.pan_base']['originals'],[])
        for row in m.values():
            for original in row['originals']:
                self.assertTrue(original['source_file'].startswith('hardware/exports/'))
                self.assertNotIn('build-guides',original['public_file'])
                self.assertEqual(sha(ROOT/original['source_file']),original['sha256'])
        self.assertTrue(m['L.hip_frame']['originals'][0]['public_file'].endswith('/exports/leg/hip_frame.stl'))
        self.assertEqual(m['L.hip_frame']['geometry_match']['status'],'pending')

    def test_named_and_rehashed_stale_original_does_not_enable_current_print(self):
        # The original's filename, plan key and digest all look legitimate even
        # after a stale/replacement file is rebound. That is identity, not shape
        # correspondence; neither original may claim a current geometry match.
        files=['hardware/exports/'+p for p in ('leg/print-plan.json','body/print-plan.json',
               'body/shell/print-plan.json','body/body.json','leg/leg.json',
               'leg/bom.json','body/bom.json','leg/hip_frame.stl')]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for file in files:
                dest=root/file;dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/file,dest)
            old=mapping(root,['L.hip_frame'])['L.hip_frame']
            original=root/'hardware/exports/leg/hip_frame.stl'
            original.write_bytes(b'not the current hip geometry')
            stale=mapping(root,['L.hip_frame'])['L.hip_frame']
            self.assertNotEqual(old['originals'][0]['sha256'],stale['originals'][0]['sha256'])
            self.assertEqual(stale['originals'][0]['sha256'],sha(original))
            self.assertEqual(stale['kind'],'print')
            self.assertEqual(stale['geometry_match']['status'],'pending')
            self.assertEqual(old['geometry_match']['status'],'pending')

    def fixture(self,folder):
        # Explicit synthetic triangles exercise serializer integrity, never CAD validity.
        inventory=json.loads((ROOT/'hardware/exports/robot/robot.json').read_text())
        # This is a serializer fixture for the current recipe, not an asserted
        # native collection. Preserve the recorded turret inventory while using
        # the current end-support body names instead of the retired belly bay.
        names=[n for op in robot_operations() for n in op['additions']]
        names += [n for group in inventory['groups'].values() for n in group['members'] if n.startswith('turret.')]
        p=folder/'meshes';p.mkdir()
        blob=b'\0'*80+struct.pack('<I',1)+struct.pack('<12fH',0,0,1,0,0,0,2,0,0,0,3,0,0)
        parts=[]
        for i,name in enumerate(names):
            file=f'meshes/fixture-{i}.stl';(folder/file).write_bytes(blob)
            parts.append({'name':name,'file':file,'sha256':sha(folder/file),'bounds_mm':bounds(folder/file),
                          'source_group':'synthetic fixture','color':'#223344','visible':True})
        return {'schema':'gyropup.robot-assembly-parts/1','units':'mm','up':'z','source_commit':'1'*40,'hardware_tree':'2'*40,
                'parts':parts,'configuration':{'fixture':True},'inputs':{},'collector_sha256':'3'*64,'datums':{},
                'mount_reference':{'tm_face_z_mm':246,'riser_top_mm':246,'pan_base_contact_vertices':12,'wrong_xy_rejected':True,
                                   'expected_bolt_centers_mm':[[-80,-40,246],[0,-40,246],[-80,40,246],[0,40,246]],
                                   'bolt_center_errors_mm':{'riser':[0]*4,'turret.pan_base':[0]*4}}}

    def test_two_coherent_snapshots_overview_stage_order_and_static_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);record=self.fixture(folder)
            m=mapping(ROOT,[p['name'] for p in record['parts']],record)
            outputs=generate(record,folder,'4'*64,{},'5'*64,m)
            entries=json.loads(outputs['index-entries.json']);self.assertEqual([r['assembly'] for r in entries],['robot','combined'])
            for row in entries:
                raw=outputs[row['file']];self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
                g=json.loads(raw);prefix=row['file'].rsplit('/',1)[0]+'/'
                model=json.loads(outputs[prefix+'view.json'])
                self.assertEqual(g['model']['sha256'],hashlib.sha256(outputs[prefix+'view.json']).hexdigest())
                self.assertEqual(g['source']['overview_step_id'],'overview');self.assertEqual(g['source']['install_order_by_step']['overview'],[])
                self.assertEqual(set(g['steps'][0]['parts']),{p['name'] for p in model['parts']})
                seen=[]
                for step in g['steps'][1:]:
                    order=g['source']['install_order_by_step'][step['id']]
                    self.assertEqual(order,step['highlight']);seen+=order
                    self.assertEqual(step['parts'],seen)
                self.assertEqual(len(seen),len(set(seen)))
                self.assertEqual(set(seen),set(g['steps'][0]['parts']))
                text=outputs[prefix+'instructions.html'].decode()
                self.assertEqual(text.count('<section '),len(g['steps']))
                self.assertEqual(g['snapshot']['status'],'wip')
                self.assertTrue(g['source']['qualification'])
                for side in ('L','R'):
                    for suffix in ('wheel_hub','wheel_tyre'):
                        current=g['source']['manufacturing_by_part'][side+'.'+suffix]
                        self.assertEqual(current['kind'],'unresolved')
                        self.assertNotIn('buy/odrive-botwheel',json.dumps(current))
                self.assertNotIn('BotWheel',text)
                if row['assembly']=='robot':self.assertFalse(any(n.startswith('turret.') for n in seen))
                else:self.assertEqual(g['source']['step_kinds']['turret-module'],'subassembly-placement')

    def test_changed_mesh_units_duplicate_and_mount_evidence_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);record=self.fixture(folder)
            for change in ('units','duplicate','digest','mount','xy'):
                r=json.loads(json.dumps(record))
                if change=='units':r['units']='m'
                elif change=='duplicate':r['parts'].append(r['parts'][0])
                elif change=='digest':r['parts'][0]['sha256']='0'*64
                elif change=='mount':r['mount_reference']['riser_top_mm']+=5
                else:r['mount_reference']['wrong_xy_rejected']=False
                with self.subTest(change=change),self.assertRaises(ValueError):verified_parts(r,folder)


if __name__=='__main__':unittest.main()
