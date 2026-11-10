"""Fresh current hip tessellation correspondence plus explicit historical evidence.

Uses the existing sampler and unchanged strict historical receipt validator.
No CAD, slicing, network, source-history lookup, or automatic evidence acceptance.
"""
from __future__ import annotations

import json
import hashlib
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.evidence.manufacturing import retained_fit_history as history
from robot_data import sha
import robot_print_match as sampler
import robot_current_print_acceptance as accepted

SOURCE = '3a40891962b0b0a04625e070700f1d130bea3c7b'
COLLECTION_SHA = '7c2f1905474a8c89bdc477ea472f5c826e57c674aa222f2134f6a0a4138d5a67'
INPUTS = history.PLAN / 'current-cad-inputs.json'
INPUTS_SHA = '885545309f1087e267a75cdd89920ec559ef4a6af603d941698b4e82eea80a43'
ORIGINAL = Path('hardware/exports/leg/hip_frame.stl')
ORIGINAL_SHA = 'f15c00497974e3f78d3fdc9ca60ef958ebff4d3537556d98c7c6828e6ec103de'
SAMPLER = Path('tools/site/assembly/robot_print_match.py')
SAMPLER_SHA = '917b5324611657b50118ac2fd125d9fb58d735d0260c3e578f93929d64fa7b1f'
HISTORY_SHA = '47b05f0211f49aadd244f4670157df8f2b01288968d2a6f0dd0eee4791e69709'
INSTANCES = ('L.hip_frame', 'R.hip_frame')
LIMIT = .3011
Y_OFF = 102.5498
PROOF = history.PLAN / 'current-hip-print-match.json'
ACCEPTANCE = history.PLAN / 'current-hip-print-match-acceptance.json'
SCOPE = ('Current sampled tessellation-to-original correspondence; historical engineering '
         'evidence remains 322 pass / 40 warn / 8 fail. Geometry-only WIP preparation; '
         'generic bed, unsliced, no physical fit, support, strength or print release.')


def binding(root, collection, folder):
    """Validate exact current membership/bytes and both actual mesh frames."""
    root, folder = Path(root), Path(folder)
    if sha(root/INPUTS) != INPUTS_SHA or sha(root/ORIGINAL) != ORIGINAL_SHA:
        raise ValueError('Current input inventory or original print anchor differs')
    expected = json.loads((root/INPUTS).read_text())
    from hardware.cad.manufacturing.print_provenance import source_files
    current = {p.relative_to(root).as_posix(): sha(p) for p in source_files(root)}
    context = 'tools/engineering/robot/robot_view.py'
    current[context] = sha(root/context)
    if len(expected) != 95 or current != expected or collection['inputs'] != expected:
        raise ValueError('Current complete 95-input membership or bytes differ')
    encoded=(json.dumps(collection,indent=2,allow_nan=False)+'\n').encode()
    if (hashlib.sha256(encoded).hexdigest() != COLLECTION_SHA
            or collection['source_commit'] != SOURCE
            or collection['hardware_tree'] != '346f5a5623560177390ad8cf207e5b8331ab5bae'
            or collection['runtime'] != {'cadquery':'2.8.0','numpy':'2.5.4','cadquery-ocp':'7.9.3.1.1',
                                         'vtk':'9.6.2','cad_agent_revision':'e662a1ce79b4f63f7352b9d065c5027f77d53a81'}
            or collection['datums']['y_off_mm'] != Y_OFF):
        raise ValueError('Accepted current collection/runtime/frame anchor differs')
    if (Path(sampler.__file__).resolve() != ROOT/SAMPLER or sha(sampler.__file__) != SAMPLER_SHA
            or sha(root/SAMPLER) != SAMPLER_SHA or sha(history.__file__) != HISTORY_SHA):
        raise ValueError('Current sampler/historical validator executed bytes differ')
    parts = {p['name']:p for p in collection['parts']}
    baseline = json.loads((root/history.PLAN/'baseline.json').read_text())['collection261_leg_mesh_sha256']
    actual = {n:p['sha256'] for n,p in parts.items() if n.startswith(('L.','R.'))}
    if len(parts) != 224 or len(actual) != 80 or actual != baseline:
        raise ValueError('Protected actual leg mesh membership differs')
    for name in actual:
        p = parts[name]; path = folder/p['file']
        if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()) or sha(path) != p['sha256']:
            raise ValueError('Actual collected leg mesh byte identity differs')
    with history.captured_inputs(root):
        pass  # Full unchanged historical guard, against actual current originals.
    return {'schema':'gyropup.current-hip-correspondence/1','native_source':SOURCE,
            'collection_sha256':COLLECTION_SHA,'current_inputs':expected,'input_inventory_sha256':INPUTS_SHA,
            'original_sha256':ORIGINAL_SHA,'sampler_sha256':SAMPLER_SHA,
            'producer_sha256':sha(Path(__file__)),'historical_validator_sha256':HISTORY_SHA,
            'historical':{'matching_input_snapshot':history.SNAPSHOT,'recorded_slice_producer':history.PRODUCER,
                          'archive_sha256':history.ARCHIVE_SHA,'manifest_sha256':history.MANIFEST_SHA,
                          'receipt_sha256':history.RECEIPT_SHA,'job_sha256':history.JOB_SHA,
                          'engineering_pass':False,'engineering_counts':history.COUNTS},
            'frame':{'y_off_mm':Y_OFF,'print_transform':'print=(x+137,z+81.5,-y-1)',
                     'left_module':'(x,y-y_off,z)','right_module':'(-x,-y-y_off,z)'},
            'protected_leg_mesh_sha256':actual,'tessellation_allowance_mm':LIMIT,
            'physical_fit_verified':False,'strength_verified':False,'manufacturing_released':False,
            'scope':SCOPE}


def measure(folder, output):
    """Explicitly invoked bounded pure-mesh measurement; never auto-accept."""
    folder, output = Path(folder).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(ROOT):
        raise ValueError('Use a fresh measurement directory outside source')
    if sha(folder/'collection.json') != COLLECTION_SHA:
        raise ValueError('Actual measurement collection byte anchor differs')
    collection = json.loads((folder/'collection.json').read_text())
    proof = binding(ROOT, collection, folder)
    output.mkdir(mode=0o700,parents=True)
    proof.update(status='INCOMPLETE',sides={},negative_controls={})
    def checkpoint():
        temp=output/'checkpoint.tmp'
        temp.write_text(json.dumps(proof,indent=2,allow_nan=False)+'\n')
        temp.replace(output/'measurement.json')
    checkpoint(); started=time.monotonic()
    original=sampler.triangles(ROOT/ORIGINAL)
    parts={p['name']:p for p in collection['parts']}
    for name in INSTANCES:
        side=name[0]
        def transform(point):
            x,y,z=point
            return sampler.hip_to_print((x,y-Y_OFF,z) if side=='L' else (-x,-y-Y_OFF,z))
        actual=sampler.triangles(folder/parts[name]['file'],transform)
        result=sampler.correspondence(original,actual,LIMIT)
        result['mesh_sha256']=parts[name]['sha256'];proof['sides'][side]=result
        checkpoint();print('COMPLETED '+name,flush=True)
        if side=='L':
            shifted=[tuple((p[0]+3,p[1],p[2]) for p in triangle) for triangle in actual]
            try:sampler.correspondence(original,shifted,LIMIT)
            except ValueError:proof['negative_controls']['actual_mesh_shift_3mm']=True
            else:raise ValueError('Actual wrong-frame mesh negative was accepted')
            checkpoint()
    # Revalidate every identity after computation; preserve incomplete output if changed.
    if binding(ROOT,collection,folder) != {k:v for k,v in proof.items() if k not in ('status','sides','negative_controls')}:
        raise ValueError('Measurement input changed during comparison')
    proof.update(status='CURRENT_MESH_CORRESPONDENCE_MEASURED',elapsed_seconds=time.monotonic()-started)
    checkpoint()


def matched(root, collection, folder, name):
    """Accepted current evidence only; no fallback from a failed current guard."""
    if Path(accepted.__file__).resolve() != ROOT/'tools/site/assembly/robot_current_print_acceptance.py':
        raise ValueError('Current acceptance authority module origin differs')
    proof_sha, acceptance_sha = accepted.PROOF_SHA256, accepted.ACCEPTANCE_SHA256
    if name not in INSTANCES or folder is None or proof_sha is None or acceptance_sha is None:
        return None
    root=Path(root)
    if sha(root/PROOF) != proof_sha or sha(root/ACCEPTANCE) != acceptance_sha:
        raise ValueError('Independently accepted current proof/acceptance bytes differ')
    proof=json.loads((root/PROOF).read_text());acceptance=json.loads((root/ACCEPTANCE).read_text())
    expected=binding(root,collection,folder)
    if any(proof.get(k) != v for k,v in expected.items()):
        raise ValueError('Accepted current proof input/frame identity differs')
    if (proof.get('status') != 'CURRENT_MESH_CORRESPONDENCE_MEASURED'
            or proof.get('negative_controls') != {'actual_mesh_shift_3mm':True}
            or set(proof.get('sides',{})) != {'L','R'}
            or acceptance.get('measurement_sha256') != proof_sha
            or acceptance.get('collection_sha256') != COLLECTION_SHA
            or acceptance.get('instances') != list(INSTANCES)
            or acceptance.get('physical_qualification') is not False
            or acceptance.get('bindings') != {k:expected[k] for k in
                ('collection_sha256','input_inventory_sha256','original_sha256','sampler_sha256',
                 'producer_sha256','historical_validator_sha256','historical')}
            or not acceptance.get('review_url','').startswith('https://github.com/Valpatel/gyropup/')):
        raise ValueError('Accepted current proof outcome/scope differs')
    for side in ('L','R'):
        result=proof['sides'][side]
        if result['mesh_sha256'] != expected['protected_leg_mesh_sha256'][side+'.hip_frame'] or result['limit_mm'] != LIMIT:
            raise ValueError('Accepted current mesh result differs')
        for direction in ('a_to_b','b_to_a'):
            row=result[direction];distance=row['max_distance_mm']
            if (not isinstance(row['samples'],int) or isinstance(row['samples'],bool) or row['samples']<=0
                    or not isinstance(distance,(int,float)) or isinstance(distance,bool)
                    or not math.isfinite(distance) or not 0<=distance<=LIMIT):
                raise ValueError('Accepted current measured sample/distance differs')
    return {'status':'matched','geometry_source_match':True,
            'evidence':{'source_file':str(PROOF),'sha256':proof_sha},
            'acceptance':{'source_file':str(ACCEPTANCE),'sha256':acceptance_sha},
            'basis':SCOPE,'qualification':SCOPE}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection-folder',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();measure(args.collection_folder,args.out)
