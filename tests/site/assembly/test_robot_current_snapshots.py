"""Mandatory adopted266 actual-data/current exporter checks; historical data is separate."""
import hashlib
import json
from pathlib import Path
import re
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/site/assembly'))
from export_robot_guide import generate
from robot_manufacturing import mapping
from robot_data import sha

ASSETS=ROOT/'software/site/assets/build-guides'
CURRENT=ROOT/'software/site/assets/robot-current'
RECORDS=ROOT/'.agents/plans/end-packs/guide-adoption'
SOURCE='3a40891962b0b0a04625e070700f1d130bea3c7b'
MANIFEST='3183870617a7ca3182c4a79a2afd8890a546ac2a3353cacc98e5295a63e64fe3'
COLLECTION='7c2f1905474a8c89bdc477ea472f5c826e57c674aa222f2134f6a0a4138d5a67'
INDEX='16af1475fb58fdcc1eb6db939a6539044fea632916ce8fad6e6741df952e3244'
ACCEPTED_INDEX='7e8a51f3743e154230e0882e8ac20641b79e74e657773acd22b13d0548231016'

class AdoptedCurrentSnapshots(unittest.TestCase):
    def test_bound_current_cache_has_exact224_originals_and95_current_sources(self):
        self.assertEqual(sha(CURRENT/'manifest.json'),MANIFEST)
        self.assertEqual(sha(CURRENT/'collection.json'),COLLECTION)
        manifest=json.loads((CURRENT/'manifest.json').read_bytes());c=json.loads((CURRENT/'collection.json').read_bytes())
        self.assertEqual(c['source_commit'],SOURCE);self.assertEqual(len(c['parts']),224);self.assertEqual(len(c['inputs']),95)
        self.assertEqual(len([p for p in CURRENT.rglob('*')if p.is_file()]),226)
        self.assertFalse(any(p.is_symlink()for p in CURRENT.rglob('*')))
        for file,digest in c['inputs'].items():self.assertEqual(sha(ROOT/file),digest,file)
        for part in c['parts']:self.assertEqual(sha(CURRENT/part['file']),part['sha256'],part['name'])
        binding=(ROOT/'software/site/designer/robot_current_source.js').read_text()
        literal=re.fullmatch(r'.*?export const CURRENT_ROBOT_SOURCE = (\{.*\});\s*',binding,re.S)
        self.assertIsNotNone(literal)
        self.assertEqual(json.loads(literal[1]),{'file':'web/robot-current/manifest.json','sha256':MANIFEST})
        self.assertIsNone(manifest['engineering']['mass_kg']);self.assertIsNone(manifest['engineering']['com_mm'])
        for flag in ['physics_current','manufacturing_released','physical_qualified']:self.assertIs(manifest['engineering'][flag],False)

    def test_five_row_index_preserves_old_three_and_has_explicit_current_defaults(self):
        self.assertEqual(sha(ASSETS/'index.json'),INDEX)
        self.assertEqual(sha(RECORDS/'final-index.json'),ACCEPTED_INDEX)
        self.assertEqual(json.loads((ASSETS/'index.json').read_bytes()),json.loads((RECORDS/'final-index.json').read_bytes()))
        index=json.loads((ASSETS/'index.json').read_bytes());old=json.loads((ROOT/'.agents/plans/robot-assembly/index-entries-260.json').read_bytes())
        self.assertEqual(len(index['snapshots']),5);self.assertEqual(index['snapshots'][0]['id'],'turret-wip-4866459e2abd')
        for assembly in ['robot','combined']:
            rows=[r for r in index['snapshots']if r['assembly']==assembly]
            self.assertEqual(rows[0]['id'],assembly+'-wip-3a40891962b0')
            self.assertEqual(rows[1],next(r for r in old if r['assembly']==assembly))
        self.assertEqual([r['id']for r in index['unavailable']],['released','rig'])

    def test_current233_outputs_reproduce_without_regenerating_archives(self):
        c=json.loads((CURRENT/'collection.json').read_bytes())
        manufacturing=mapping(ROOT,[p['name']for p in c['parts']],c,collection_folder=CURRENT)
        boms={f:sha(ROOT/f)for f in ['hardware/exports/body/bom.json','hardware/exports/leg/bom.json','hardware/exports/turret/bench/bom.json']}
        outputs=generate(c,CURRENT,sha(ROOT/'tools/site/assembly/robot_recipe.py'),boms,COLLECTION,manufacturing)
        self.assertEqual(len(outputs),233)
        for name,data in outputs.items():
            if name=='index-entries.json':
                self.assertEqual(json.loads(data),[r for r in json.loads((ASSETS/'index.json').read_bytes())['snapshots']if r['id'].endswith('3a40891962b0')])
            else:self.assertEqual((ASSETS/name).read_bytes(),data,name)
        for assembly,count in [('robot',162),('combined',224)]:
            guide=json.loads(outputs[assembly+'-wip-3a40891962b0/guide.json']);parts=guide['source']['manufacturing_by_part']
            self.assertEqual(len(parts),count)
            self.assertEqual(sorted(n for n,p in parts.items()if p['geometry_match']['status']=='matched'),['L.hip_frame','R.hip_frame'])
            for side in ['L','R']:
                for name in ['wheel_hub','wheel_tyre']:
                    row=parts[side+'.'+name];self.assertEqual(row['kind'],'unresolved');self.assertNotIn('part_key',row)
                    self.assertNotIn('odrive-botwheel',json.dumps(row));self.assertNotIn('BW0124',json.dumps(row))
                    self.assertEqual(row['design_reference']['tyre_band_width_mm'],64)
                    self.assertFalse(row['design_reference']['ordered_sku_verified'])

if __name__=='__main__':unittest.main()
