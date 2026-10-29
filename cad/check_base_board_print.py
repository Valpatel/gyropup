"""Independent wall/print-orientation check for the new passive carrier only.

No fit or strength claim: actual coupons and a renewed pan-base structural check
remain required. The thin-plate control demonstrates this probe can reject a wall.
"""
import hashlib
import json
from pathlib import Path
import cadquery as cq
from cadagent.gates.wall import wall_gate
import turret_base_board as bb

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'exports/turret/base-board-service'


def main():
    carrier=bb.carrier().val()
    positive=wall_gate({'base_board_carrier':{'wall_mm':1.2,'mesh':carrier,'shape':carrier}})
    thin=cq.Workplane('XY').box(12,12,.6).val()
    negative=wall_gate({'thin_control':{'wall_mm':1.2,'mesh':thin,'shape':thin}})
    printed=carrier.rotate((0,0,0),(0,1,0),90)
    bounds=printed.BoundingBox()
    result={'schema':'gyropup.base-board-print/1','pass_model_checks':positive['pass'] and not negative['pass'],
            'physical_fit_verified':False,'release_ready':False,'carrier':positive,'thin_control':negative,
            'rotation':{'axis':[0,1,0],'degrees':90},'print_bounds_mm':[bounds.xlen,bounds.ylen,bounds.zlen],
            'sources':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
                       ('cad/check_base_board_print.py','cad/turret_base_board.py','cad/turret_boards.py')},
            'limits':['Sampled wall thickness, not a print or load test.','Clearance and insert fit require measured coupons.',
                      'Pan-base wall/structure qualification is outside this isolated carrier check.']}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'print-checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print('carrier',positive['counts'],'thin control',negative['counts'],'bounds',result['print_bounds_mm'])
    return 0 if result['pass_model_checks'] else 1


if __name__=='__main__':
    raise SystemExit(main())
