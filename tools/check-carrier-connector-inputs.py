#!/usr/bin/env python3
"""Bounded private connector-input diagnosis; never a service/fit acceptance.

No supplier geometry is exported. The receipt preserves exact input hashes,
validity and contradictory mated-volume evidence instead of waiving overlap.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'research/carrier-service-connectors/private-inputs.json'
sys.path.insert(0, str(ROOT / 'cad'))
import print_provenance as provenance


def private_path(entry, root=ROOT):
    path = (root / entry['private_file']).resolve()
    if not path.is_relative_to((root / 'references/vendor').resolve()):
        raise ValueError('Private model must remain in the vendor cache')
    if not path.is_file():
        raise FileNotFoundError('Exact private connector input missing: ' + entry['part'])
    if provenance.digest(path) != entry['sha256']:
        raise ValueError('Private connector model identity changed: ' + entry['part'])
    return path


def validate_receipt(receipt, root=ROOT):
    """Verify the full geometry closure without requiring a CAD runtime in CI."""
    recorded=receipt['inputs']
    if receipt['input_fingerprint']!=provenance.fingerprint(recorded):
        raise ValueError('Recorded connector input fingerprint is inconsistent')
    current=provenance.snapshot(root)
    for field in ('files','GYROPUP_CAD_PARAMS_sha256'):
        if recorded.get(field)!=current[field]:
            raise ValueError('Connector input closure changed: '+field)
    paths=[root/'tools/check-carrier-connector-inputs.py',root/'research/carrier-service-connectors/private-inputs.json']
    if receipt['context_files']!=provenance.context_snapshot(root,paths):
        raise ValueError('Connector probe or manifest changed')
    manifest=json.loads(paths[1].read_text())
    expected={e['part']:e['sha256'] for e in manifest['parts']}
    if len(expected)!=len(manifest['parts']) or expected!={k:v['sha256'] for k,v in receipt['inventory'].items()}:
        raise ValueError('Connector private identity inventory differs')
    if receipt.get('readiness') is not False:
        raise ValueError('This input diagnosis cannot claim service readiness')
    return True


def run(output):
    started = time.monotonic()
    inputs = provenance.snapshot(ROOT)
    context = provenance.context_snapshot(ROOT, [Path(__file__), MANIFEST])
    manifest = json.loads(MANIFEST.read_text())
    # Check every exact private input before importing geometry. No cache fallback.
    paths = {e['part']: private_path(e) for e in manifest['parts']}
    import cadquery as cq
    from OCP.BRepBndLib import BRepBndLib
    from OCP.Bnd import Bnd_Box
    from cadagent.gates import Tolerances, relate
    from cadagent.gates.relations import RELATIONS_VERSION
    if RELATIONS_VERSION != '4':
        raise ValueError('Requires reviewed v0.4.2 relations engine4')
    expected = {
        '43020-1200': [-13.04,-8.445,-4.825,13.04,8.445,4.125],
        '43025-1200': [-9.43,-4.,-6.71,9.42,10.,4.14],
        '43030-0010': [32.68771516158,33.0252609,-7.740100185656,34.802712206374,44.025260965345,-5.582193804125],
    }
    shapes = {}; inventory = {}
    for part, path in paths.items():
        shape = cq.importers.importStep(str(path)).val()
        box = Bnd_Box(); BRepBndLib.AddOptimal_s(shape.wrapped,box,False,False)
        bounds = list(box.Get())
        valid = shape.isValid() and len(shape.Solids()) == 1
        if not valid or any(abs(a-b)>1e-6 for a,b in zip(bounds,expected[part])):
            raise ValueError('Private connector topology/dimensions changed: '+part)
        shapes[part] = shape
        inventory[part] = {'sha256':provenance.digest(path),'valid_one_solid':valid,
                           'faces':len(shape.Faces()),'exact_bounds_mm':bounds}
    plug = shapes['43020-1200']
    receptacle = shapes['43025-1200']
    # Both supplied raw mating ends face +Y and their latch side is -Z.
    # Keep the plug in its raw frame. Reverse receptacle X/Y, preserve latch Z.
    # 16.89+14-24.77=6.12 mm nose overlap; plug front Y8.445, rec front Y10.
    # Therefore rec final front=2.325 and translation=12.325. No fitted shift.
    nominal = receptacle.rotate((0,0,0),(0,0,1),180).translate((0,12.325,0))
    wrong_clock = receptacle.rotate((0,0,0),(1,0,0),180).translate((0,12.325,0))
    tolerance = Tolerances(overlap_mm3=1e-6)
    queries = {}
    for name, other in [('drawing_nominal',nominal),('latch_reversed_control',wrong_clock),
                        ('separated_16mm_control',nominal.translate((0,16,0)))]:
        result = relate(plug,other,tolerance,contact_area=False)
        if result.state not in ('apart','touching','overlapping','contains'):
            raise ValueError('Undecidable connector BREP relation: '+str(result.error))
        queries[name] = result.to_dict()
    if queries['separated_16mm_control']['state'] != 'apart':
        raise ValueError('Separated-housing control did not clear')
    # Point samples diagnose simplified blind cavities, not their whole extent.
    samples = []
    for x in (-7.5,7.5):
        for z in (-1.5,1.5):
            for y in (6.,3.,-8.):
                point=(x,y,z)
                samples.append({'raw_point_mm':point,'inside_plug_material':plug.isInside(point,1e-7)})
    if provenance.snapshot(ROOT)!=inputs or provenance.context_snapshot(ROOT,[Path(__file__),MANIFEST])!=context:
        raise ValueError('Inputs changed during private connector diagnosis')
    result = {'schema':1,'qualification':'Private-input diagnosis only; no mated fit, harness or service acceptance.',
              'readiness':False,'inputs':inputs,'input_fingerprint':provenance.fingerprint(inputs),
              'context_files':context,'inventory':inventory,'mating_relations':queries,
              'point_samples':samples,'mating_basis':{'plug_length_mm':16.89,'receptacle_length_mm':14.,
              'mated_overall_mm':24.77,'nose_overlap_mm':6.12,'receptacle_raw_rotation':'180 degrees about +Z',
              'receptacle_raw_translation_mm':[0.,12.325,0.]},
              'limits':['Supplier housings have simplified internal cavities/closed wire-entry ends.',
                        'Nominal mated overlap is retained as unresolved representation/fit evidence, not waived.',
                        'No latch flexure, crimped terminal, lead diameter/bend or physical-fit qualification.',
                        'Exact male terminal and servo mating connector CAD remain missing.'],
              'elapsed_seconds':round(time.monotonic()-started,3)}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'readiness':False,'parts':len(inventory),'relations':{k:v['state'] for k,v in queries.items()},
                      'receipt':str(output),'seconds':result['elapsed_seconds']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args().out)
