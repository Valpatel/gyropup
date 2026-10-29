"""Reproduce detailed-thread Boolean failures without distributing vendor geometry.

Requires privately cached normalized McMaster 91290A111 and 94459A140 STEP files.
The canonical-frame option applies ONE identical rigid transform to BOTH already
placed solids; rebuilding the insert with a different flip would change thread
clocking and would not be a coordinate-invariance experiment.
"""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from pathlib import Path
import cadquery as cq
import cadagent.gates.relations as relations

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vendor-root',type=Path,default=ROOT/'references/vendor/mcmaster')
    p.add_argument('--frame',choices=('world','canonical'),default='world')
    p.add_argument('--out',type=Path,default=ROOT/'exports/turret/base-board-service/thread-probe.json')
    a=p.parse_args();files={pn:a.vendor_root/pn/(pn+'.norm.step') for pn in ('91290A111','94459A140')}
    for f in files.values():
        if not f.is_file():raise FileNotFoundError(f'private model required, no fallback: {f.name}')
    screw=cq.importers.importStep(str(files['91290A111'])).rotate((0,0,0),(0,1,0),-90).translate((46.4,-22.4,9)).val()
    insert=cq.importers.importStep(str(files['94459A140'])).rotate((0,0,0),(0,1,0),90).translate((48,-22.4,9)).val()
    if a.frame=='canonical':
        screw=screw.translate((-46.4,22.4,-9)).rotate((0,0,0),(0,1,0),90)
        insert=insert.translate((-46.4,22.4,-9)).rotate((0,0,0),(0,1,0),90)
    started=time.time();tol=relations.Tolerances()
    result=relations.relate(screw,insert,tol,names=('91290A111','94459A140')).to_dict()
    receipt={'schema':'gyropup.thread-boolean-probe/1','frame':a.frame,'grip_mm':1.6,'result':result,
             'seconds':round(time.time()-started,3),'python':sys.version.split()[0],'machine':platform.machine(),
             'cadquery':cq.__version__,'cadagent':importlib.metadata.version('cad-agent'),
             'toolkit_relations_sha256':hashlib.sha256(Path(relations.__file__).read_bytes()).hexdigest(),
             'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'private_models':{pn:{'reference':f'https://www.mcmaster.com/{pn}/','sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
                               for pn,f in files.items()},
             'solid_volumes_mm3':{'screw':screw.Volume(),'insert':insert.Volume()},
             'physical_fit_verified':False,'note':'An unknown kernel result is unresolved, never a pass. No tolerance is enlarged.'}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))
    return 1 if result['state']=='unknown' else 0


if __name__=='__main__':raise SystemExit(main())
