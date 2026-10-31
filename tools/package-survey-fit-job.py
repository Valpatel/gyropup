#!/usr/bin/env python3
"""One unpowered shaft-survey gauge slice; reuse the reviewed fit-job inspectors.

No CAD generation, printer connection, repair, motor measurement or qualification.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fit_job_helpers', ROOT / 'tools/package-fit-job.py')
fit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fit)
SOURCE = Path('exports/turret/ordered-motor-fit')
PART = 'shaft-clearance-survey'
# Reviewed actual 12-check geometry receipt; a changed gauge needs a new review.
GAUGE_RECEIPT_SHA256 = 'bc7305efafa8e0cb62d68d56d276b2111803ab47ca77404efbe204650722716f'
SCOPE = 'UNPOWERED DIMENSIONAL SURVEY ONLY; uncalibrated; no motor mounting, retention, thread gauging or powered-operation approval'
RECIPE = {'id': 'shaft-survey-pa6cf-trial-2', 'profiles': fit.PROFILES, 'overrides': fit.OVERRIDES,
          'process_source': fit.RECIPE['id'], 'copies': 1, 'scope': SCOPE,
          'orientation': 'source flat base down; +Z layer normal preserved; in-plane rigid placement allowed',
          'status': 'new declared trial; not a calibrated measuring tool'}
QUALIFICATION = {name: False for name in ('physical_fit_verified', 'slot_widths_calibrated', 'print_release',
                 'printer_calibration_verified', 'mount_design_released', 'hub_design_released', 'powered_operation_qualified')}


def input_identity(root=ROOT):
    receipt = root / SOURCE / 'checks.json'
    if fit.sha(receipt) != GAUGE_RECEIPT_SHA256:
        raise ValueError('Gauge geometry receipt differs from the reviewed 12-check result')
    data = json.loads(receipt.read_text())
    # Pinning the reviewed receipt preserves full check membership and negative controls;
    # current source/artifact identities below reject stale or replaced geometry.
    for prefix, entries in ((root, data['source_sha256']), (root / SOURCE, data['artifact_sha256'])):
        if any(fit.sha(prefix / name) != digest for name, digest in entries.items()):
            raise ValueError('Gauge source or artifact identity changed')
    from cadagent import mesh3mf, slicer, _deps
    helpers = {m.__name__: fit.sha(m.__file__) for m in (mesh3mf, slicer, _deps)}
    if helpers != fit.TOOLKIT_HELPERS:
        raise ValueError('Use the reviewed released cad-agent helpers')
    versions = {}
    for line in (root / 'tools/fit-job-requirements.txt').read_text().splitlines():
        if not line.strip() or line.startswith('#'): continue
        package, expected = line.split('==')
        versions[package] = importlib.metadata.version(package)
        if versions[package] != expected: raise ValueError('Runtime version differs: ' + package)
    files = ['tools/package-survey-fit-job.py', 'tools/package-fit-job.py', 'tools/fit-job-requirements.txt',
             'cad/print_slicing.py', 'cad/print_provenance.py', str(SOURCE / 'checks.json'),
             *data['source_sha256'], *(str(SOURCE / p) for p in data['artifact_sha256'])]
    return {'files': {p: fit.sha(root / p) for p in files}, 'toolkit_helpers': helpers,
            'toolkit_commit': fit.TOOLKIT_COMMIT, 'runtime_packages': versions,
            'source_geometry_counts': data['counts'], 'source_geometry_screen_passed': True}


def record_bytes(job):
    def rows(values):
        stream = io.StringIO(newline='')
        csv.writer(stream).writerows(values)
        return stream.getvalue().encode()
    fields = ['slot', 'cad_nominal_width_mm', 'actual_mouth_width_mm', 'actual_round_end_width_mm',
              'measurement_uncertainty_mm', 'instrument_and_method', 'conditioning_and_humidity',
              'surface_or_elephant_foot_notes', 'sample_id', 'smooth_shoulder_observation', 'photo', 'notes']
    measurements = [fields] + [[str(i+1), f'{4.8+i/10:.1f}'] + ['']*(len(fields)-2) for i in range(8)]
    process = ['source_mesh_sha256', 'recipe', 'job_receipt_sha256', 'date_operator', 'printer', 'nozzle',
               'nozzle_wear_condition', 'extruder_gears_material_and_wear', 'filament_path_condition',
               'plate_and_glue', 'filament_brand_lot', 'drying_temperature_time', 'dry_feed_relative_humidity',
               'time_since_drying', 'measurement_conditioning', 'calibration', 'notes']
    return {'measurements.csv': rows(measurements), 'process-record.csv': rows([
        process, [fit.sha(job / 'source.stl'), RECIPE['id']] + ['']*(len(process)-2)])}


def layer_witness(job, identity, render=False):
    text = (job / 'slice/out/plate_1.gcode').read_text()
    layers = sorted({float(z) for z in re.findall(r'^; Z_HEIGHT: ([0-9.]+)$', text, re.M)})
    if not layers or layers[0] != .2 or 3.0 not in layers or not 3.4 <= layers[-1] <= 3.8:
        raise ValueError('Missing expected base/slot/label layer coverage')
    chosen = [layers[0], 3.0, next(z for z in layers if z > 3.), layers[-1]]
    drawings = {z: [] for z in chosen}
    fit.toolpaths(text, identity['effective_profiles']['machine'], drawings=drawings)
    if len(drawings) != 4 or not all(drawings.values()): raise ValueError('Missing actual layer deposition')
    if render:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.collections import LineCollection
        import numpy as np
        all_points = np.concatenate([p for paths in drawings.values() for _, p in paths])
        lo, hi = all_points.min(axis=0), all_points.max(axis=0)
        fig, axes = plt.subplots(4, 1, figsize=(13, 10))
        for (z, paths), ax in zip(drawings.items(), axes):
            ax.add_collection(LineCollection([p for _, p in paths], linewidths=.45,
                colors=['#dc2626' if f == 'Bridge' else '#f97316' if f == 'Overhang wall' else '#315b73' for f, _ in paths]))
            ax.set(xlim=(lo[0]-3, hi[0]+3), ylim=(lo[1]-3, hi[1]+3), aspect='equal',
                   xlabel='X / mm', ylabel='Y / mm', title=f'Actual deposition at Z={z:g} mm')
        fig.suptitle('Unpowered shaft survey — actual G-code\nBase, slot walls/top and raised labels; printed widths remain uncalibrated.')
        fig.tight_layout(rect=(0, 0, 1, .94)); fig.savefig(job / 'critical-layers.png', dpi=140); plt.close(fig)
    return {'heights_mm': chosen, 'deposition_segments': [len(drawings[z]) for z in chosen],
            'limits': 'Visual deposition witness only; no calibrated slot width, label legibility or physical print quality claim.'}


def check_label_coverage(paths, labels):
    """Bounded per-glyph extent screen on source-frame deposition centerlines.

    A 0.30 mm edge allowance covers nominal half-bead width plus tessellation;
    it is not a measured bead width or an OCR/physical readability certificate.
    """
    import numpy as np
    results = []
    for label in labels:
        glyphs = []
        for box in label['glyph_bounds_mm']:
            lo, hi = np.array(box[:2]), np.array(box[3:5])
            selected = [np.asarray(p) for p in paths
                        if np.all(np.asarray(p) >= lo-.3) and np.all(np.asarray(p) <= hi+.3)]
            if not selected: raise ValueError('Missing deposited label glyph: ' + label['id'])
            points = np.concatenate(selected)
            lower, upper = points.min(axis=0), points.max(axis=0)
            length = sum(float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum()) for p in selected)
            if np.any(lower > lo+.3) or np.any(upper < hi-.3) or length < max(hi-lo)*.5:
                raise ValueError('Insufficient deposited label glyph extent: ' + label['id'])
            glyphs.append({'bounds_mm': box, 'deposition_centerline_bounds_xy_mm': [lower.tolist(), upper.tolist()],
                           'path_length_mm': length, 'segments': len(selected)})
        if not glyphs: raise ValueError('Missing source glyph inventory')
        results.append({'id': label['id'], 'text': label['text'], 'glyphs': glyphs})
    return results


def label_witness(job, identity, root=ROOT):
    """Map existing parser output back to the actual source glyph coordinates."""
    import numpy as np
    import trimesh
    from cadagent.mesh3mf import CORE_NS
    receipt = json.loads((root / SOURCE / 'checks.json').read_text())
    labels = receipt['labels']
    expected = {f'slot:{i}': f'{4.8+i/10:.1f}' for i in range(8)} | {'survey-only': 'SURVEY ONLY'}
    if {r['id']: r['text'] for r in labels} != expected or len(labels) != 9:
        raise ValueError('Incomplete source label inventory')
    if identity['effective_profiles']['machine'].get('extruder_offset') != ['0x2']:
        raise ValueError('Unsupported nozzle-to-model coordinate mapping')
    ns = {'m': CORE_NS, 'p': 'http://schemas.microsoft.com/3dmanufacturing/production/2015/06'}
    with zipfile.ZipFile(job / 'slice/out/sliced.3mf') as archive:
        model = fit.ET.fromstring(archive.read('3D/3dmodel.model'))
        component = model.find('m:resources/m:object/m:components/m:component', ns)
        part = fit.ET.fromstring(archive.read(component.get('{'+ns['p']+'}path').lstrip('/')))
        first = part.find('.//m:vertex', ns)
        vertex = np.array([float(first.get(k)) for k in 'xyz'])
        transform = np.array([float(v) for v in model.find('m:build/m:item', ns).get('transform').split()]).reshape(4, 3)
    source = trimesh.load_mesh(job / 'source.stl', process=True)
    shift = vertex - source.vertices[0]
    drawings = {3.2: [], 3.4: []}
    fit.toolpaths((job / 'slice/out/plate_1.gcode').read_text(), identity['effective_profiles']['machine'], drawings=drawings)
    results, controls = {}, {}
    for height, paths in drawings.items():
        mapped = []
        for _, points in paths:
            xyz = np.column_stack((np.array(points) + [0., 2.], np.full(len(points), height)))
            mapped.append(((xyz-transform[3]) @ transform[:3].T-shift)[:, :2])
        results[str(height)] = check_label_coverage(mapped, labels)
        for label in labels:
            b = label['bounds_mm']; lo, hi = np.array(b[:2])-.3, np.array(b[3:5])+.3
            removed = [p for p in mapped if not (np.all(p >= lo) and np.all(p <= hi))]
            try: check_label_coverage(removed, labels)
            except ValueError: controls[f'{height}:{label["id"]}'] = True
            else: raise ValueError('Missing-label negative control unexpectedly passed')
    return {'labels_by_layer': results, 'missing_label_deposition_controls': controls,
            'nozzle_to_model_xy_mm': [0., 2.], 'glyph_edge_allowance_mm': .3,
            'limits': 'Per-glyph deposited centerline extent screen, plus separate visual reading; no physical label or slot calibration.'}


def verify(job, root=ROOT):
    job = Path(job)
    report = json.loads((job / 'job.json').read_text())
    if (report.get('schema') != 'gyropup.shaft-survey-fit-job/1' or report.get('recipe') != RECIPE
            or report.get('qualification') != QUALIFICATION or report.get('slice_complete') is not True):
        raise ValueError('Recipe/scope/qualification changed')
    if report.get('inputs') != input_identity(root) or report.get('files_sha256') != fit.manifest(job):
        raise ValueError('Source or retained-output identity changed')
    required = {'source.stl', 'geometry.3mf', 'critical-layers.png', 'measurements.csv', 'process-record.csv',
                'slice/machine.json', 'slice/process.json', 'slice/filament.json', 'slice/slicer.log',
                'slice/exit-code.json', 'slice/out/result.json', 'slice/out/sliced.3mf', 'slice/out/plate_1.gcode'}
    if not required <= set(report['files_sha256']): raise ValueError('Incomplete retained job')
    if fit.sha(job / 'source.stl') != report['inputs']['files'][str(SOURCE / (PART + '.stl'))]:
        raise ValueError('Staged gauge mesh differs')
    for name, raw in record_bytes(job).items():
        if (job / name).read_bytes() != raw: raise ValueError('Blank measurement/process record changed')
    identity = report['slice_inputs']
    fit.verify_slice_identity(job, identity)
    for key, actual in (('geometry', fit.geometry_check(job, identity)),
                        ('archive_members', fit.sliced_members(job)), ('metrics', fit.measurements(job)),
                        ('sliced_inspection', fit.sliced_inspection(job, identity)),
                        ('critical_layers', layer_witness(job, identity)),
                        ('label_deposition', label_witness(job, identity, root))):
        if report.get(key) != actual: raise ValueError('Retained ' + key + ' differs')
    return report


def generate(job, root=ROOT):
    import trimesh
    from cadagent import mesh3mf, slicer
    job = Path(job).resolve()
    before = input_identity(root)
    identity = fit.print_slicing.capture(**fit.PROFILES, overrides=fit.OVERRIDES)
    job.mkdir(parents=True, exist_ok=False)
    # Preserve original bytes of every dependency of the existing resolver.
    for name, digest in identity['profile_files_sha256'].items():
        relative = Path(name)
        if len(relative.parts) != 2 or relative.parts[0] not in ('machine', 'process', 'filament') or relative.suffix != '.json':
            raise ValueError('Unexpected profile path')
        raw = (slicer.profile_root() / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest: raise ValueError('Profile changed before slicing')
        destination = job / 'profiles' / relative
        destination.parent.mkdir(parents=True, exist_ok=True); destination.write_bytes(raw)
    (job / 'source.stl').write_bytes((root / SOURCE / (PART + '.stl')).read_bytes())
    mesh = trimesh.load_mesh(job / 'source.stl', process=True)
    mesh3mf.write_3mf(job / 'geometry.3mf', mesh.vertices, mesh.faces, PART, (256., 256.))
    geometry = fit.geometry_check(job, identity)
    print('Slicing one unpowered survey gauge into ' + str(job), flush=True)
    fit.print_slicing.run(job / 'geometry.3mf', job / 'slice', identity)
    if before != input_identity(root): raise ValueError('Sources changed during slice; diagnostic only')
    inspection = fit.sliced_inspection(job, identity)
    layers = layer_witness(job, identity, render=True)
    labels = label_witness(job, identity, root)
    for name, raw in record_bytes(job).items(): (job / name).write_bytes(raw)
    report = {'schema': 'gyropup.shaft-survey-fit-job/1', 'recipe': RECIPE, 'qualification': QUALIFICATION,
              'slice_complete': True, 'inputs': before, 'slice_inputs': identity,
              'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
              'geometry': geometry, 'metrics': fit.measurements(job), 'archive_members': fit.sliced_members(job),
              'sliced_inspection': inspection, 'critical_layers': layers, 'label_deposition': labels,
              'files_sha256': fit.manifest(job)}
    fit.dump(job / 'job.json', report); verify(job, root)
    print(json.dumps({'job': str(job), 'metrics': report['metrics'], 'scope': SCOPE}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--out', type=Path); group.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.out: generate(args.out)
    else: print(json.dumps({'verified': str(args.verify), 'metrics': verify(args.verify)['metrics'], 'scope': SCOPE}))
