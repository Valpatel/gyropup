#!/usr/bin/env python3
"""Export the four authored cut parts for BOM inspection; no full turret solve.

These WIP part models are not a manufacturing release or current robot assembly.
They contain no vendor CAD. Run on the CAD compute host at a pushed revision.
"""
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'exports/turret/component-preview'
SOURCES = ('cad/turret.py', 'cad/gmi.py', 'cad/interfaces.json', 'catalog/interfaces.json',
           'catalog/materials.json', 'tools/export-turret-cut-previews.py')
sys.path.insert(0, str(ROOT / 'cad'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if os.environ.get('GYROPUP_CAD_PARAMS'):
        raise ValueError('Cut-part preview export requires the committed default configuration')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    hashes = {name: digest(ROOT / name) for name in SOURCES}
    for name, sha in hashes.items():
        committed = subprocess.check_output(['git', 'show', f'{revision}:{name}'], cwd=ROOT)
        if hashlib.sha256(committed).hexdigest() != sha:
            raise ValueError(f'Preview input is not committed at {revision}: {name}')
    # Capture inputs before imports: turret and gmi read catalogue files at import time.
    import cadquery as cq
    import turret as tu
    G = tu.Geo()
    parts = {'pan_clamp': tu.pan_clamp(G), 'cradle_plate_l': tu.cradle_plate(G, 1),
             'cradle_plate_r': tu.cradle_plate(G, -1), 'stop_lug': tu.stop_lug(G)}
    if set(parts) != set(tu.SHEET_PARTS):
        raise ValueError('Update preview coverage for the complete cut-part set')
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, shape in parts.items():
        solid = shape.val()
        if not solid.isValid() or len(shape.solids().vals()) != 1:
            raise ValueError(f'{name}: invalid or disconnected geometry')
        stl, step = OUT / f'{name}.stl', OUT / f'{name}.step'
        cq.exporters.export(shape, str(stl), tolerance=.08, angularTolerance=.1)
        cq.exporters.export(shape, str(step))
        bb = solid.BoundingBox()
        rows.append({'name': name, 'stl': stl.relative_to(ROOT).as_posix(), 'stl_sha256': digest(stl),
                     'step': step.relative_to(ROOT).as_posix(), 'step_sha256': digest(step),
                     'bounds_mm': [bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax],
                     'volume_mm3': solid.Volume(), 'valid_single_solid': True,
                     'stock': tu.SHEET[tu.SHEET_PARTS[name]]})
    if hashes != {name: digest(ROOT / name) for name in SOURCES}:
        raise ValueError('Source changed during preview generation')
    result = {'schema': 1, 'source_revision': revision,
              'source_hashes': hashes, 'cadquery_version': cq.__version__,
              'cadquery_ocp_version': version('cadquery-ocp'), 'units': 'mm', 'parts': rows,
              'physical_fit_verified': False, 'qualified_for_manufacture': False,
              'purpose': 'Current authored cut-part inspection and BOM imagery; not a released full assembly.',
              'license_basis': 'Project-authored geometry; no supplier CAD or derived supplier mesh.'}
    manifest = OUT / 'manifest.json'
    pending = manifest.with_suffix('.pending')
    pending.write_text(json.dumps(result, indent=2) + '\n')
    pending.replace(manifest)
    print('Exported four WIP cut-part inspection models; no assembly, load or manufacturing acceptance implied.')


if __name__ == '__main__':
    main()
