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
    import trimesh
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    import turret as tu

    def exact_bounds(solid):
        # CadQuery's default BoundingBox can include cached tessellation deflection.
        # Ask the BREP geometry, even after an STL export has populated that cache.
        bounds = Bnd_Box()
        BRepBndLib.AddOptimal_s(solid.wrapped, bounds, False, False)
        return list(bounds.Get())

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
        bounds = exact_bounds(solid)
        stock = tu.SHEET[tu.SHEET_PARTS[name]]
        if abs(min(bounds[i + 3] - bounds[i] for i in range(3)) - stock['thickness_mm']) > 1e-6:
            raise ValueError(f'{name}: BREP thickness differs from declared sheet stock')
        stl, step = OUT / f'{name}.stl', OUT / f'{name}.step'
        cq.exporters.export(shape, str(stl), tolerance=.08, angularTolerance=.1)
        cq.exporters.export(shape, str(step))
        restored = cq.importers.importStep(str(step)).val()
        step_error = max(abs(a - b) for a, b in zip(exact_bounds(restored), bounds))
        volume_error = abs(restored.Volume() - solid.Volume())
        if not restored.isValid() or len(restored.Solids()) != 1 or step_error > 1e-6 or volume_error > 1e-5:
            raise ValueError(f'{name}: STEP round trip changed the authored solid')
        mesh = trimesh.load(str(stl), force='mesh')
        stl_error = max(abs(a - b) for a, b in zip(mesh.bounds.ravel(), bounds))
        if not mesh.is_watertight or not mesh.is_winding_consistent or stl_error > .08 or len(mesh.split()) != 1:
            raise ValueError(f'{name}: STL topology or bounds differ from the authored solid')
        rows.append({'name': name, 'stl': stl.relative_to(ROOT).as_posix(), 'stl_sha256': digest(stl),
                     'step': step.relative_to(ROOT).as_posix(), 'step_sha256': digest(step),
                     'bounds_mm': bounds,
                     'volume_mm3': solid.Volume(), 'valid_single_solid': True,
                     'stock': stock, 'round_trip': {'step_bounds_max_error_mm': step_error,
                         'step_volume_error_mm3': volume_error, 'stl_bounds_max_error_mm': stl_error,
                         'stl_watertight': True, 'stl_winding_consistent': True, 'stl_components': 1}})
    if hashes != {name: digest(ROOT / name) for name in SOURCES}:
        raise ValueError('Source changed during preview generation')
    result = {'schema': 1, 'source_revision': revision,
              'source_hashes': hashes, 'cadquery_version': cq.__version__,
              'cadquery_ocp_version': version('cadquery-ocp'), 'trimesh_version': trimesh.__version__,
              'units': 'mm', 'bounds_basis': 'BREP AddOptimal; no triangulation or shape-tolerance expansion', 'parts': rows,
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
