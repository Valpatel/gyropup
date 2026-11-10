"""Reproduce bounded triangle witnesses; no native CAD or planner."""
from pathlib import Path
import hashlib
import json
import sys
import subprocess
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/site/assembly'))
from recipe_path_screen import screen, triangles, topology
from robot_data import sha
from robot_recipe import robot_operations
ASSETS=ROOT/'software/site/assets/build-guides'
FOLDER=ASSETS/'robot-wip-540056ba4e59'
MODEL=FOLDER/'view.json'
PARTS={p['name']:p for p in json.loads(MODEL.read_text())['parts']}
CASES=[
 ('motor-through-installed-hip','L.motor_front','L.hip_frame',60),
 ('motor-wrong-inward-through-cheek','L.motor_front','cheek_left',-60),
 ('hip-after-motor-outward','L.hip_frame','L.motor_front',60),
 ('hip-wrong-inward-through-motor','L.hip_frame','L.motor_front',-60),
 ('inboard-bearing-outward-through-shoulder','L.knee_bearing_front_in','L.front_link',60),
 ('inboard-bearing-inward-through-upper-eye','L.knee_bearing_front_in','L.upper_link_front',-60),
 ('output-screws-after-upper','L.screws_outputs','L.upper_link_front',60),
 ('upper-after-output-screws','L.upper_link_front','L.screws_outputs',60),
 ('wheel-washers-outward-through-hub','L.washers_wheel','L.wheel_hub',60),
 ('wheel-washers-inward','L.washers_wheel','L.wheel_hub',-60),
 ('circlip-outward-and-final-overlap','L.apex_circlip','L.wheel_link',60),
]

def produce():
 cache={};topologies={}
 def mesh(n):
  if n not in cache:
   p=PARTS[n];f=FOLDER/p['file']
   if sha(f)!=p['sha256']:raise ValueError('Changed actual mesh '+n)
   cache[n]=triangles(f)
   topologies[n]={'mesh_sha256':p['sha256'],**topology(cache[n])}
   if not topologies[n]['closed_oriented_edges']:raise ValueError('Ray-parity input is not a closed oriented mesh: '+n)
  return cache[n]
 baseline=subprocess.check_output(['git','show','33c4464b710341dc45b0ba43fb1006ddbab13f95:software/site/assets/build-guides/robot-wip-540056ba4e59/guide.json'],cwd=ROOT)
 cases=[]
 for label,moving,fixed,offset in CASES:
  for side in ('L','R'):
   m=moving.replace('L.',side+'.');f=fixed.replace('L.',side+'.')
   if fixed=='cheek_left' and side=='R':f='cheek_right'
   signed=offset if side=='L' else -offset
   cases.append({'id':label+'-'+side,'moving':m,'fixed':f,'offset_mm':[0,signed,0],
                 'mesh_sha256':{n:PARTS[n]['sha256'] for n in (m,f)},
                 **screen(mesh(m),mesh(f),signed)})
 candidate=[];installed=[]
 # Broad phase only selects pairs; it never provides the penetration verdict.
 for operation in robot_operations():
  for moving in operation['additions']:
   if moving.startswith(('L.','R.')) and moving[2:] in ('motor_front','motor_rear','hip_frame',
        'screws_outputs','upper_link_front','upper_link_rear','washers_wheel','screws_wheel'):
    offset=operation['offsets'].get(moving,operation['offset'])[1]
    swept=list(PARTS[moving]['bounds_mm']);swept[1]+=min(offset,0);swept[4]+=max(offset,0)
    for fixed in installed:
     bound=PARTS[fixed]['bounds_mm']
     if not all(min(swept[k+3],bound[k+3])-max(swept[k],bound[k])>.05 for k in range(3)):continue
     result=screen(mesh(moving),mesh(fixed),offset);result.pop('samples')
     candidate.append({'moving':moving,'fixed':fixed,'offset_mm':[0,offset,0],
                       'mesh_sha256':{n:PARTS[n]['sha256'] for n in (moving,fixed)},**result})
   installed.append(moving)
 return {'date':'2026-11-10','schema':'gyropup.arrival-witness-screen/1',
  'source_commit':'540056ba4e59b197859236cb693463e10c9c8901',
  'baseline_guide_commit':'33c4464b710341dc45b0ba43fb1006ddbab13f95',
  'baseline_guide_sha256':hashlib.sha256(baseline).hexdigest(),
  'model_sha256':sha(MODEL),'screen_sha256':sha(ROOT/'tools/site/assembly/recipe_path_screen.py'),
  'procedure':'128 deterministic moving-triangle centroids; 21 equally spaced translation poses; axial ray parity against fixed triangles; 0.05 mm interior margin; odd/edge rays unknown.',
  'scope':'Robot and Combined share these exact body/leg meshes and operations. Turret bench retains its separately authored sequence; mounted turret remains a placement illustration, not a rigid-insertion qualification.',
  'limits':'Interior witnesses demonstrate sampled surface penetration. Zero witnesses do not prove collision-free paths. No full-mesh continuous collision, BREP, contact, support, tool access, compliance, press fit, wiring, strength or dynamic simulation. The circlip/grouped source envelopes are not faithful individual installation bodies.',
  'recipe_sha256':sha(ROOT/'tools/site/assembly/robot_recipe.py'),
  'candidate_scope':'All installed-obstacle broad-phase candidates for changed motor/hip, output-screw/upper-link and wheel-fastener arrivals; all other arrivals remain unqualified.',
  'mesh_topology':topologies,'candidate_pairs':candidate,'cases':cases}

if __name__=='__main__':
 result=produce()
 print(json.dumps(result,indent=2))
