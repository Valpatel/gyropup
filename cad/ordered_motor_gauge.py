#!/usr/bin/env python3
"""Authored, unpowered shaft-clearance survey gauge; not a motor, mount or hub.

Run on the assigned CAD host. Eight open slots bracket the seller's nominal
5 mm shaft claim. They are experimental gauge dimensions, not measured motor
interfaces. Use only on a safely accessible smooth shoulder; never force a fit.
"""
from __future__ import annotations
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WIDTHS = (4.8, 4.9, 5.0, 5.1, 5.2, 5.3, 5.4, 5.5)
SIZE = (100., 32., 3.)
SLOT_Y = 20.
LABEL_HEIGHT = .5
FONT = 'DejaVu Sans'
NAME = 'shaft-clearance-survey'
SOURCES = ('cad/ordered_motor_gauge.py', 'research/ordered-turret-motor/seller-claims.json')
TOOLKIT = ('geometry.py', 'evidence.py', 'gates/verdict.py')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_gauge(widths=WIDTHS, labels=True):
    import cadquery as cq
    plate = cq.Workplane('XY').box(*SIZE, centered=(False, False, False)).edges('|Z').fillet(2.)
    for i, width in enumerate(widths):
        x = 11. + 11. * i
        circle = cq.Workplane('XY').center(x, SLOT_Y).circle(width / 2).extrude(5).translate((0, 0, -1))
        opening = cq.Workplane('XY').center(x, 27).rect(width, 14).extrude(5).translate((0, 0, -1))
        plate = plate.cut(circle.union(opening))
        if labels:
            text = cq.Workplane('XY').text(f'{WIDTHS[i]:.1f}', 2.8, LABEL_HEIGHT, font=FONT,
                                           halign='center', valign='center').translate((x, 11., SIZE[2]))
            plate = plate.union(text)
    if labels:
        text = cq.Workplane('XY').text('SURVEY ONLY', 3.2, LABEL_HEIGHT, font=FONT,
                                       halign='center', valign='center').translate((50., 4.5, SIZE[2]))
        plate = plate.union(text)
    return plate.val()


def measure_slots(shape):
    """Read actual cylinder geometry and sample open mouths, independent of labels."""
    import cadquery as cq
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    measured = []
    for i, expected in enumerate(WIDTHS):
        x = 11. + 11. * i
        arcs = []
        for face in shape.Faces():
            surface = BRepAdaptor_Surface(face.wrapped)
            if surface.GetType() != GeomAbs_Cylinder:
                continue
            cylinder = surface.Cylinder()
            centre = cylinder.Location()
            if abs(centre.X() - x) < 1e-5 and abs(centre.Y() - SLOT_Y) < 1e-5:
                arcs.append(round(cylinder.Radius() * 2, 6))
        # A slot must stay open through the top edge and through the plate. Two
        # outside probes must still meet material, so a completely missing land
        # cannot count as a valid open slot.
        empty_points = [(x, y, z) for y in (SLOT_Y, 26., 31.9) for z in (.1, 1.5, 2.9)]
        solid_points = [(x + side * (expected / 2 + .2), 26., 1.5) for side in (-1, 1)]
        empty = all(not shape.isInside(cq.Vector(*p), 1e-6) for p in empty_points)
        lands = all(shape.isInside(cq.Vector(*p), 1e-6) for p in solid_points)
        measured.append({'index': i, 'x_mm': x, 'y_mm': SLOT_Y, 'expected_width_mm': expected,
                         'cylinder_diameters_mm': arcs, 'open_through_plate_and_edge': empty,
                         'lands_present': lands,
                         'pass': len(arcs) == 1 and abs(arcs[0] - expected) < 1e-5 and empty and lands})
    return measured


def build(out):
    import cadquery as cq
    import cadagent
    from cadagent.evidence import shape_content_hash
    from cadagent.geometry import solid_report, export_print_stl
    from cadagent.gates.verdict import Check, verdict, write_verdict
    import trimesh

    out.mkdir(parents=True, exist_ok=True)
    shape = make_gauge()
    solid = solid_report(shape)
    slots = measure_slots(shape)
    step, stl = out / f'{NAME}.step', out / f'{NAME}.stl'
    cq.exporters.export(shape, str(step))
    mesh_report = export_print_stl(shape, stl, tolerance=.01, angular=.08)
    reopened = cq.importers.importStep(str(step)).val()
    reopened_slots = measure_slots(reopened)
    mesh = trimesh.load_mesh(stl)
    components = len(mesh.split(only_watertight=False))
    mesh_volume_error = abs(float(mesh.volume) - shape.Volume()) / shape.Volume()
    wrong_width = list(WIDTHS)
    wrong_width[0] += .3
    wrong = measure_slots(make_gauge(wrong_width, labels=False))
    blocker = cq.Workplane('XY').box(100., 2., 3., centered=(False, False, False)).translate((0, 30, 0)).val()
    closed = measure_slots(shape.fuse(blocker))
    controls = {'wrong_first_slot_width_caught': not wrong[0]['pass'],
                'blocked_mouths_caught': all(not row['pass'] for row in closed)}
    checks = [Check('solid', 'pass' if solid['cad_valid'] and solid['solid_count'] == 1 else 'fail',
                    'Authored gauge is one valid connected CAD solid.', evidence=solid),
              Check('mesh', 'pass' if mesh_report['watertight'] and components == 1 and mesh_volume_error < .002 else 'fail',
                    'Actual exported STL is watertight, connected and tracks CAD volume.',
                    evidence={**mesh_report, 'connected_components': components, 'relative_volume_error': mesh_volume_error}),
              Check('step-roundtrip', 'pass' if reopened.isValid() and all(r['pass'] for r in reopened_slots) else 'fail',
                    'Reopened STEP retains all slot dimensions and open mouths.', evidence={'slots': reopened_slots}),
              Check('negative-controls', 'pass' if all(controls.values()) else 'fail',
                    'Geometry probes reject the wrong slot and blocked mouths.', evidence=controls)]
    checks += [Check(f'slot:{r["index"]}', 'pass' if r['pass'] else 'fail',
                     'Actual slot cylinder diameter and opening match the experimental gauge specification.', evidence=r)
               for r in slots]
    toolkit_root = Path(cadagent.__file__).resolve().parent
    font_path = Path(subprocess.check_output(['fc-match', '-f', '%{file}', FONT], text=True))
    report = verdict('ordered-motor-shaft-survey-gauge', checks,
                     assumptions=['Experimental clearance survey tool; no exact motor CAD is represented.',
                                  'Seller nominal 5 mm claim only chooses the survey range; it is not a measured fit.',
                                  'Use unpowered on an accessible smooth shoulder only. No force, threading, clamping or retention.',
                                  'Printed slot sizes need measurement; CAD checks do not prove slicer or printer accuracy.',
                                  'No mount, hub, screw stack, material strength or powered operation is qualified.'],
                     extra={'source_sha256': {p: digest(ROOT / p) for p in SOURCES},
                            'artifact_sha256': {p.name: digest(p) for p in (step, stl)},
                            'toolkit_sha256': {p: digest(toolkit_root / p) for p in TOOLKIT},
                            'toolkit_revision': subprocess.check_output(['git', '-C', str(toolkit_root), 'rev-parse', 'HEAD'], text=True).strip(),
                            'project_revision': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
                            'dependencies': {p: version(p) for p in ('cad-agent', 'cadquery', 'cadquery-ocp', 'trimesh')},
                            'font': {'family': FONT, 'file': font_path.name, 'sha256': digest(font_path)},
                            'shape_digest': shape_content_hash(shape), 'slots': slots, 'negative_controls': controls,
                            'geometry_screen_passed': all(c.status == 'pass' for c in checks),
                            'slicer_run': False, 'print_release': False, 'mount_design_released': False,
                            'hub_design_released': False, 'powered_operation_qualified': False})
    write_verdict(out / 'checks.json', report)
    print(json.dumps({'pass': report['pass'], 'counts': report['counts'], 'output': str(out)}), flush=True)
    return 0 if report['pass'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'exports/turret/ordered-motor-fit')
    raise SystemExit(build(parser.parse_args().out))
