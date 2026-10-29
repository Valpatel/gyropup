"""Dimensioned custom drilling plan from the actual PCB CAD parameters; no full build."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cad'))
import turret_base_board as board


def main():
    w,h = board.BOARD_SIZE
    holes = [(y+w/2,z-board.BOARD_Z0) for y,z in board.BOARD_HOLES]
    margin = min(min(x,y,w-x,h-y)-board.PCB_MOUNT_CLEAR/2 for x,y in holes)
    out = ROOT / 'exports/turret/base-board-service'
    drawing = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 660 460">',
               '<rect width="660" height="460" fill="#fffdf5"/>',
               '<g font-family="sans-serif" fill="#173d3c">',
               '<text x="28" y="32" font-size="20">Base PCB — custom cut and drilling plan</text>',
               f'<text x="28" y="60" font-size="14">{w:g} × {h:g} mm; four Ø{board.PCB_MOUNT_CLEAR:g} drilled mounting holes</text>',
               '<g transform="translate(76 95) scale(9)">',
               f'<rect width="{w}" height="{h}" fill="#d9edf3" stroke="#173d3c" stroke-width=".18"/>']
    for x,y in holes:
        drawing += [f'<circle cx="{x}" cy="{h-y}" r="{board.PCB_MOUNT_CLEAR/2}" fill="#fffdf5" stroke="#173d3c" stroke-width=".12"/>',
                    f'<path d="M{x-2.3},{h-y}h4.6 M{x},{h-y-2.3}v4.6" stroke="#bd3a12" stroke-width=".09"/>']
    drawing += ['</g>', '<text x="28" y="390" font-size="14">Hole centres from the cut board’s lower-left corner (mm):</text>',
                f'<text x="28" y="414" font-size="14">{", ".join(f"({x:g}, {y:g})" for x,y in holes)}; edge ligament {margin:g} mm nominal</text>',
                '<text x="28" y="441" font-size="12">Research drawing: verify stock, drill, copper clearance and physical fit before assembly.</text>', '</g></svg>']
    (out/'pcb-drill-pattern.svg').write_text('\n'.join(drawing)+'\n')
    receipt = {'schema':'gyropup.base-pcb-drill/1', 'size_mm':[w,h], 'hole_diameter_mm':board.PCB_MOUNT_CLEAR,
               'centres_from_cut_lower_left_mm':holes, 'minimum_nominal_edge_ligament_mm':margin,
               'plastic_retainer_hole_diameter_mm':board.M3_CLEAR,
               'factory_pattern_reused':False,'physical_fit_verified':False,
               'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                          ('cad/turret_base_board.py','cad/turret_boards.py','tools/export-base-board-drill.py')},
               'limits':['Not a drill template at printed page scale; use the stated dimensions.',
                         'Cut Wombat stock and drill the custom pattern; original factory mounting holes are elsewhere.',
                         'Remove burrs and inspect copper/insulation around mounting screws; electrical clearance remains to validate.',
                         'Board thickness1.6mm remains a design assumption to measure on received stock.']}
    (out/'pcb-drill-pattern.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='sources'}))


if __name__ == '__main__':
    main()
