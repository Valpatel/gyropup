"""Source-bound, isolated BREP checks for the passive base-board carrier.

Run on a compute host for the complete check. This is deliberately independent of
the dossier's single-part sequence: a preassembled module moves as a rigid body.
Only project-authored geometry and numerical results may be exported.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

import cadquery as cq
from cadagent.gates import Assembly, Tolerances, PairCache
from cadagent.gates.assembly import AssemblySequenceWorld, AccessOptions, sweep_pair
from cadagent.gates.fasteners import FastenerSpec, fastener_gate
import turret as tu
import turret_base_board as bb

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['cad/turret.py','cad/turret_base_board.py','cad/turret_boards.py','cad/check_base_board_service.py',
           'catalog/hardware.json','catalog/turret.json']
PAIR_CACHE = PairCache(ROOT / '.cadagent-cache/base-board-service')
TOOL = {'segments': [{'d':6.,'length':60.},{'d':25.,'length':80.}]}


def shape(w):
    return w.val() if hasattr(w,'val') else w


def volume(a,b):
    return shape(a).intersect(shape(b)).Volume()


def compound(items):
    return cq.Compound.makeCompound([shape(x) for x in items])


def sweep(moving, obstacle, seat=True, direction=(-1.,0.,0.)):
    a = Assembly();a.add('module',shape(moving));a.add('obstacle',shape(obstacle))
    world = AssemblySequenceWorld(a)
    return sweep_pair(world,'module',direction,'obstacle',options=AccessOptions(max_step_mm=.25),seat=seat)


def hardware_gate(which, base=None, bumper=None, bad_length=None, missing_hole=False, manufacturer=False):
    """PCB screws tested on bench; carrier screws tested with the base present."""
    a = Assembly()
    carrier=bb.carrier(); pcb=bb.board()
    if missing_hole:
        y,z=bb.CARRIER_HOLES[0]
        carrier=carrier.union(bb.cx(bb.M3_CLEAR/2,53,56,y,z))
    a.add('base_board_carrier',shape(carrier));a.add('base_board',shape(pcb))
    hw=bb.hardware(available_private=manufacturer)
    for group in ('base_board_inserts','base_carrier_inserts'):
        a.add(group,compound([s for n,s in hw.items() if n.startswith(group+'#')]))
    specdata=bb.screw_specs()[which]
    spec=FastenerSpec(name=which,**{k:v for k,v in specdata.items() if k!='pn'},diameter_mm=3.,
                      thread_depth_mm=bb.INSERT_LENGTH,min_engagement_mm=3.,head_d_mm=5.5,head_h_mm=3.,tool='driver')
    for name,s in hw.items():
        if 'screws' not in name:
            continue
        if name.startswith(which+'#') and bad_length is not None:
            i=int(name.rsplit('#',1)[1]);o,d=spec.axes[i]
            s=bb.public_screw(bad_length).rotate((0,0,0),(0,1,0),-90*d[0]).translate(o)
        a.add(name,shape(s)).kind = 'fastener' if name.startswith(which+'#') else 'part'
    if base is not None:a.add('pan_base',shape(base))
    if bumper is not None:a.add('bumper_ring',shape(bumper))
    # Every obstacle is present before the selected fasteners are driven. PCB tools
    # are intentionally checked without the base; carrier tools with it.
    names=[n for n in a.names if not n.startswith(which+'#')]
    steps=[dict(order=i+1,fit=n) for i,n in enumerate(names)]
    steps.append(dict(order=len(steps)+1,fit=spec.clamps,fasteners=[which],tool='driver'))
    return fastener_gate(a,{which:spec},steps=steps,tools={'driver':TOOL},cache=PAIR_CACHE)


def run(out):
    started=time.time();checks=[]
    out.mkdir(parents=True,exist_ok=True)
    def check(name,ok,evidence):
        checks.append({'id':name,'pass':bool(ok),'evidence':evidence})
        (out/'progress.json').write_text(json.dumps({'complete':False,'checks':checks},indent=2)+'\n')
        print(name,'PASS' if ok else 'FAIL',flush=True)
    G=tu.Geo();original=tu.pan_base(G,board_service=False);base=tu.pan_base(G);carrier=bb.carrier();board=bb.board();hw=bb.hardware()
    for name,s in [('base',base),('carrier',carrier),('pcb',bb.pcb())]:
        check('valid:'+name,s.val().isValid() and len(s.val().Solids())==1,{'solids':len(s.val().Solids())})
    regions={'foot':bb.box(-120,120,-120,120,-1,5),'bearing_tube':cq.Solid.makeCylinder(35.5,38),
             'bearing_seat':bb.box(-43,43,-50,50,38,60),'servo_pocket':bb.box(-85,-25,-50,60,0,65)}
    for name,r in regions.items():
        old=original.val().intersect(shape(r));new=base.val().intersect(shape(r))
        delta=old.cut(new).Volume()+new.cut(old).Volume()
        check('protected:'+name,delta<1e-6,{'symmetric_difference_mm3':delta})
    check('board_seated',volume(board,base)<1e-6 and volume(board,carrier)<1e-6,
          {'base_overlap_mm3':volume(board,base),'carrier_overlap_mm3':volume(board,carrier)})
    module=shape(carrier).fuse(shape(board))
    for n,s in hw.items():
        if n.startswith(('base_board_screws#','base_board_inserts#')):
            module=module.fuse(shape(s))
    # The module includes hardware that actually remains attached during removal.
    fixed_base=shape(base).fuse(compound([s for n,s in hw.items() if n.startswith('base_carrier_inserts#')]))
    obstacles={'base':fixed_base,'pan_ring':tu.pan_ring(G),'pan_clamp':tu.pan_clamp(G),'pan_pinion':tu.pan_pinion(G)}
    for name,obstacle in obstacles.items():
        for service in (False,True):
            r=sweep(module,obstacle,seat=not service)
            check(('remove:' if service else 'install:')+name,r['state'] in ('clear','touching'),r)
    for name,obstacle in [('old_wall',original),('bumper_retained',tu.bumper_ring(G))]:
        r=sweep(module,obstacle,seat=False)
        check('negative:'+name,r['state'] in ('blocked','seat'),r)
    r=sweep(module,base,direction=(0,1,0));check('negative:wrong_direction',r['state'] in ('blocked','seat'),r)
    gates={}
    for name,kwargs in [('pcb_bench',dict(which='base_board_screws')),
                        ('carrier_installed',dict(which='base_carrier_screws',base=base)),
                        ('pcb_inside_base',dict(which='base_board_screws',base=base)),
                        ('bumper_tool',dict(which='base_carrier_screws',base=base,bumper=tu.bumper_ring(G))),
                        ('short_screw',dict(which='base_carrier_screws',base=base,bad_length=4)),
                        ('long_screw',dict(which='base_carrier_screws',base=base,bad_length=16)),
                        ('missing_hole',dict(which='base_carrier_screws',base=base,missing_hole=True)),
                        ('manufacturer_pcb',dict(which='base_board_screws',manufacturer=True)),
                        ('manufacturer_carrier',dict(which='base_carrier_screws',base=base,manufacturer=True))]:
        print('running fastener stage: '+name,flush=True)
        gates[name]=hardware_gate(**kwargs)
        (out/(name+'.json')).write_text(json.dumps(gates[name],indent=2)+'\n')
        expected=name in ('pcb_bench','carrier_installed','manufacturer_pcb','manufacturer_carrier')
        check(('fasteners:' if expected else 'negative:')+name,bool(gates[name]['pass'])==expected,
              {'counts':gates[name]['counts'],'findings':gates[name]['findings']})
    # Offline manufacturer coverage is audited independently. Missing models never
    # silently become a manufacturer's model and do not qualify hardware completeness.
    private={}
    for pn in ('91290A111','91290A113','94459A140'):
        p=ROOT/f'references/vendor/mcmaster/{pn}/{pn}.norm.step'
        private[pn]={'available':p.is_file(),'file':str(p.relative_to(ROOT))}
        if p.is_file():
            s=bb.normalized(pn,private=True).val();b=s.BoundingBox()
            private[pn].update(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bbox_mm=[b.xlen,b.ylen,b.zlen],valid=s.isValid())
    import cadagent.gates.assembly as ga
    sourcehash={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in SOURCES}
    result=dict(schema='gyropup.base-board-service/1',pass_model_checks=all(c['pass'] for c in checks),checks=checks,
                physical_fit_verified=False,release_ready=False,hardware_geometry='public module geometry; manufacturer STEP for fastener checks where locally available, explicitly audited below',
                manufacturer_models=private,commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                sources=sourcehash,toolkit_assembly_sha256=hashlib.sha256(Path(ga.__file__).read_bytes()).hexdigest(),
                seconds=round(time.time()-started,2),limits=['No physical fits or printed tolerances measured.',
                'Harness disconnect access and cable slack not represented; service sequence remains conditional.',
                'Changed pan base requires renewed structural qualification.',
                'Generic dossier single-part assembly cannot represent preassembled module motion.',
                'Manufacturer CAD remains private; numerical comparisons only.'])
    out.mkdir(parents=True,exist_ok=True)
    (out/'progress.json').write_text(json.dumps({'complete':True,'checks':checks},indent=2)+'\n')
    (out/'checks.json').write_text(json.dumps(result,indent=2)+'\n')
    for name,g in gates.items():(out/(name+'.json')).write_text(json.dumps(g,indent=2)+'\n')
    for name,s in [('pan_base',base),('base_board_carrier',carrier),('base_board',board)]:
        cq.exporters.export(s,str(out/(name+'.step')))
    return 0 if result['pass_model_checks'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'exports/turret/base-board-service')
    raise SystemExit(run(p.parse_args().out))
