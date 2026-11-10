from pathlib import Path
import hashlib,json,tarfile,subprocess,sys
import argparse
parser=argparse.ArgumentParser(description='Repeat the pure job261 archive/source/correspondence audit; no CAD execution.')
parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[4])
parser.add_argument('--fetched',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
parser.add_argument('--toolkit',type=Path,required=True)
parser.add_argument('--retained-reference',default='55572baa3b7f65dbe113e62447239cb0389f794e')
args=parser.parse_args()
ROOT=args.repo.resolve();PACKET=args.fetched.resolve();OUT=args.out.resolve()
assert not OUT.exists() and not OUT.is_relative_to(ROOT)
assert subprocess.check_output(['git','-C',str(args.toolkit),'rev-parse','HEAD'],text=True).strip()=='011a29b6fe1ddf4a6726fa01f59d710cbf1d6757'
assert not subprocess.check_output(['git','-C',str(args.toolkit),'status','--porcelain'],text=True).strip()
OUT.mkdir(mode=0o700,parents=True)
def recorded(file,revision):return subprocess.check_output(['git','-C',str(ROOT),'show',revision+':'+file])
sys.path.insert(0,str(ROOT/'tools/site/assembly'))
from robot_data import bounds,sha
from robot_native_playback import native_parts
sys.path.insert(0,str(args.toolkit.resolve()/'software'))
from cadagent.review.evidence import brep_content_hash
source='e5b3089277448e5ae3d546fc36c549a62949856b'
result=json.loads((PACKET/'out/final-result.json').read_text())
assert result['status']=='PASS_SCOPED_COLLECTION' and result['source']==source and result['adoption_approved'] is False
assert result['processes_quiescent'] and not result['errors'] and result['guards']=={k:True for k in ('runtime','toolkit','hardware','tracked','clean_source')}
archives={}
for kind in ('candidate','guides'):
 archive=PACKET/'out'/(kind+'-produced.tgz');expected=json.loads((PACKET/'out'/(kind+'-members.json')).read_text())
 assert sha(archive)==result[kind+'_archive_sha256']
 with tarfile.open(archive) as tar:
  members=tar.getmembers();assert len(members)==len(expected) and len({m.name for m in members})==len(members)
  assert all(m.isfile() and m.name in expected and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members)
  for member in members:
   raw=tar.extractfile(member).read();record=expected[member.name]
   assert len(raw)==record['bytes'] and hashlib.sha256(raw).hexdigest()==record['sha256']
   actual=PACKET/'out'/kind/member.name;assert sha(actual)==record['sha256']
   dest=OUT/kind/member.name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
 archives[kind]={'sha256':sha(archive),'bytes':archive.stat().st_size,'members':len(members)}
candidate=OUT/'candidate';c=json.loads((candidate/'collection.json').read_text());assert c['source_commit']==source
payloads=native_parts(c,candidate);assert len(payloads)==len(c['parts'])==233
for part in c['parts']:
 assert sha(candidate/part['file'])==part['sha256'] and bounds(candidate/part['file'])==part['bounds_mm']
 assert brep_content_hash(payloads[part['name']])==part['native_geometry']['shape_sha256']
 assert part['source_shape_valid'] is True
old=json.loads(recorded('.agents/plans/robot-assembly/collection-260.json',args.retained_reference));oldparts={p['name']:p for p in old['parts']}
assert c['inputs']==old['inputs'] and c['hardware_tree']==old['hardware_tree']
for file,value in c['inputs'].items():assert hashlib.sha256(recorded(file,source)).hexdigest()==value
same=[p['name'] for p in c['parts'] if p['sha256']==oldparts[p['name']]['sha256']]
different=[p['name'] for p in c['parts'] if p['name'] not in same]
entries=json.loads((OUT/'guides/index-entries.json').read_text());oldentries=json.loads(recorded('.agents/plans/robot-assembly/index-entries-260.json',args.retained_reference));guides=[]
for entry in entries:
 directory=OUT/'guides'/entry['id'];guide_raw=(directory/'guide.json').read_bytes();g=json.loads(guide_raw)
 assert hashlib.sha256(guide_raw).hexdigest()==entry['sha256'];assert g['snapshot']['source_commit']==source
 oldentry=next(e for e in oldentries if e['assembly']==entry['assembly']);oldguide=json.loads(recorded('software/site/assets/build-guides/'+oldentry['file'],args.retained_reference))
 modelraw=(directory/'view.json').read_bytes();m=json.loads(modelraw);assert hashlib.sha256(modelraw).hexdigest()==g['model']['sha256']
 for part in m['parts']:assert sha((directory/part['file']).resolve())==part['sha256']
 fields=('id','title','subassembly','parts','highlight','offsets_mm','camera','requires','text')
 trajectory=lambda guide:[{k:s[k] for k in fields if k in s} for s in guide['steps']]
 assert trajectory(g)==trajectory(oldguide) and g['source']['install_order_by_step']==oldguide['source']['install_order_by_step']
 guides.append({'assembly':entry['assembly'],'snapshot':g['snapshot']['id'],'guide_sha256':entry['sha256'],'model_sha256':g['model']['sha256'],'parts':len(m['parts']),'steps':len(g['steps']),'trajectory_equals_retained_guide':True,'retained_snapshot':oldentry['id'],'retained_guide_sha256':oldentry['sha256']})
assert c['mount_reference']['wrong_xy_rejected'] is True
errors=[e for ref in c['module_reference'].values() for side in ref['sides'].values() for e in side['errors_mm']]
summary={'schema':'gyropup.robot-native-collection-audit/1','status':'AUTHOR_AUDIT_PENDING_INDEPENDENT_REVIEW','job':261,'role':'cpu-b','native_source_commit':source,'retained_mesh_source_commit':old['source_commit'],'archives':archives,
 'collection_sha256':sha(candidate/'collection.json'),'parts':len(c['parts']),'original_brep_payloads':len(payloads),'original_brep_bytes':sum(map(len,payloads.values())),'source_shape_valid_count':sum(p['source_shape_valid'] for p in c['parts']),'compound_source_instances':sum(p['compound'] for p in c['parts']),
 'source_cad_inputs':len(c['inputs']),'cad_inputs_equal_retained':c['inputs']==old['inputs'],'hardware_tree':c['hardware_tree'],'hardware_tree_equal_retained':True,'exact_mesh_sha_matches_retained':len(same),'different_mesh_names':different,
 'original_brep_raw_and_content_hashes_checked':True,'identity_placements_checked':True,'actual_stl_bounds_checked':True,
 'independent_module_landmarks':len(errors),'max_module_landmark_error_mm':max(errors),'wrong_xy_mount_rejected':True,'runtime':c['runtime'],'producer_hash_platform':c['native_geometry']['hash_platform'],
 'phases':{k:{'exit':v['exit'],'seconds':v['seconds'],'owned_group_gone':v['process_cleanup']['group_gone']} for k,v in result['phases'].items()},'guards':result['guards'],'processes_quiescent':True,'guides':guides,
 'limits':'Fresh source identity and retained source identity remain separate. This audits collection/serialization/mesh correspondence only; no BREP readback/frame/path query, asset adoption, physical fit, support, compliance, fastening, strength or manufacturing acceptance.'}
(OUT/'audit.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
