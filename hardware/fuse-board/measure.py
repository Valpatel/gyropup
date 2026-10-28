"""The filled board's facts for analysis.py and cad/body_fuse_board.py: copper area per layer, the narrowest section of
every branch's output copper, the hole count. Run with KiCad's Python after DRC has filled the zones (build.sh):

    nice -n 15 ~/.local/share/kicad-10.0.1/bin/python3.11 hardware/fuse-board/measure.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pcbnew as P

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import design as D  # noqa: E402


def main():
    b = P.LoadBoard(str(HERE / f'{D.NAME}.kicad_pcb'))
    mm2 = lambda a: a / 1e12                                 # nm^2 -> mm^2
    copper = {}
    for layer, name in ((P.F_Cu, 'top'), (P.B_Cu, 'bottom')):
        poly = P.SHAPE_POLY_SET()
        for z in b.Zones():
            if z.IsOnLayer(layer) and z.IsFilled():
                poly.BooleanAdd(z.GetFilledPolysList(layer))
        for t in b.GetTracks():
            if t.IsOnLayer(layer):
                t.TransformShapeToPolygon(poly, layer, 0, P.FromMM(0.005), P.ERROR_INSIDE)
        for fp in b.GetFootprints():
            for pad in fp.Pads():
                if pad.IsOnLayer(layer):
                    pad.TransformShapeToPolygon(poly, layer, 0, P.FromMM(0.005), P.ERROR_INSIDE)
        poly.Simplify()
        copper[name] = round(mm2(poly.Area()), 1)
    holes = sum(1 for fp in b.GetFootprints() for pad in fp.Pads() if pad.HasHole()) + sum(1 for t in b.GetTracks() if t.Type() == P.PCB_VIA_T)
    hole_area = sum(3.14159 / 4 * P.ToMM(pad.GetDrillSize().x) * P.ToMM(pad.GetDrillSize().y) for fp in b.GetFootprints()
                    for pad in fp.Pads() if pad.HasHole())
    outline = P.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(outline, False)
    facts = {'board_area_mm2': round(mm2(outline.Area()), 1), 'copper_area_mm2': copper, 'holes': holes,
             'hole_area_mm2': round(hole_area, 1), 'thickness_mm': D.THICKNESS, 'copper_um': D.COPPER_UM,
             'zones_filled': all(z.IsFilled() for z in b.Zones())}
    (HERE / 'reports').mkdir(exist_ok=True)
    (HERE / 'reports' / 'board-facts.json').write_text(json.dumps(facts, indent=1) + '\n')
    print(facts)


if __name__ == '__main__':
    main()
