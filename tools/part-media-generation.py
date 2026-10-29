#!/usr/bin/env python3
"""Render designed-part thumbnails from exact committed geometry, or verify their receipts.

No CAD generation, network requests, adjacent-checkout discovery, or vendor image copying.
Run with the CAD environment for --render; --check uses only the Python standard library.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'catalog/images.json'
RECEIPT = ROOT / 'catalog/designed-media-validation.json'
SIZE = 480
COLOURS = {'pa6-cf': '#667384', 'petg': '#4b8fba', 'tpu95': '#424c58',
           'tpu95-gyroid': '#424c58', 'aluminium': '#aab9c9', 'copper': '#be794b'}


def read(path):
    return json.loads((ROOT / path).read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    result = {}
    for key, part in read('exports/body/print-plan.json')['parts'].items():
        result['body/' + key] = {'source': f'exports/body/{key}.stl', 'material': part['material'],
                                'group': 'body-first-frame', 'bom': 'body'}
    for stream in ['body', 'leg', 'rig']:
        for part in read(f'exports/{stream}/bom.json').get('made_to_order', []):
            # STEP is the made-to-order original, including its drilled/counterbored faces.
            result[stream + '/' + part['key']] = {'source': part['step'],
                'material': 'copper' if 'copper' in part['material'].lower() else 'aluminium',
                'group': 'machined-and-cut', 'bom': stream}
    # Cut parts have their own source-bound inspection export. The historical
    # whole-robot snapshot may predate new cheek plates and is not their geometry.
    turret_manifest = 'exports/turret/component-preview/manifest.json'
    turret = read(turret_manifest)
    expected_sources = {'cad/turret.py', 'cad/gmi.py', 'cad/interfaces.json', 'catalog/interfaces.json',
                        'catalog/materials.json', 'tools/export-turret-cut-previews.py'}
    expected_parts = {'pan_clamp', 'cradle_plate_l', 'cradle_plate_r', 'stop_lug'}
    if turret.get('schema') != 1 or turret.get('units') != 'mm' or set(turret['source_hashes']) != expected_sources:
        raise ValueError('Cut-part preview has incomplete input provenance')
    names = [part['name'] for part in turret['parts']]
    if len(names) != len(expected_parts) or set(names) != expected_parts:
        raise ValueError('Cut-part preview must contain exactly the four unique current cut parts')
    for source, expected in turret['source_hashes'].items():
        if digest(ROOT / source) != expected:
            raise ValueError(f'Cut-part preview source changed: {source}; regenerate its inspection export')
    for key in read('exports/turret/bench/bom.json')['ordered_to_drawing']:
        entries = [part for part in turret['parts'] if part['name'] == key]
        if len(entries) != 1:
            raise ValueError(f'No unique current turret geometry for {key}')
        entry = entries[0]
        for extension in ('stl', 'step'):
            expected_path = f'exports/turret/component-preview/{key}.{extension}'
            if entry[extension] != expected_path or digest(ROOT / expected_path) != entry[extension + '_sha256']:
                raise ValueError(f'{key}: cut-part preview {extension} identity mismatch')
        if entry.get('valid_single_solid') is not True:
            raise ValueError(f'{key}: cut-part preview is not a validated single solid')
        result['turret/' + key] = {'source': entry['step'],
            'expected_sha256': entry['step_sha256'], 'material': 'aluminium', 'group': 'machined-and-cut',
            'bom': 'turret', 'geometry_manifest': turret_manifest,
            'note': 'Authored current cut-part inspection STEP; mechanical qualification remains open.'}
    return result


def check_source(key, source):
    path = ROOT / source['source']
    if not path.is_file() or not path.resolve().is_relative_to(ROOT):
        raise ValueError(f'{key}: missing or outside-repository geometry: {path}')
    subprocess.run(['git', 'ls-files', '--error-unmatch', source['source']], cwd=ROOT,
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sha = digest(path)
    if source.get('expected_sha256', sha) != sha:
        raise ValueError(f'{key}: geometry differs from current turret manifest')
    return path, sha


def render(path, output, colour):
    import numpy as np
    import pyvista as pv
    import cadquery as cq
    if path.suffix.lower() in ['.step', '.stp']:
        shape = cq.importers.importStep(str(path)).val()
        vertices, triangles = shape.tessellate(0.08, 0.10)
        points = np.array([v.toTuple() for v in vertices], dtype=float)
        faces = np.column_stack((np.full(len(triangles), 3), np.array(triangles))).ravel()
        mesh = pv.PolyData(points, faces).clean()
    else:
        mesh = pv.read(str(path)).clean()
    if mesh.n_cells < 1 or not np.isfinite(mesh.points).all():
        raise ValueError(f'Invalid geometry in {path}')
    bounds = list(mesh.bounds)
    sizes = [bounds[2*i+1] - bounds[2*i] for i in range(3)]
    if min(sizes) <= 0:
        raise ValueError(f'Degenerate geometry in {path}')
    edges = mesh.extract_feature_edges(feature_angle=35, boundary_edges=False,
        non_manifold_edges=False, manifold_edges=False)
    smooth = mesh.compute_normals(split_vertices=True, feature_angle=35)
    plot = pv.Plotter(off_screen=True, window_size=(SIZE, SIZE), lighting='three lights')
    try:
        plot.set_background('#f5f8fb')
        plot.add_mesh(smooth, color=colour, smooth_shading=True, specular=.3,
            specular_power=18, ambient=.3, diffuse=.8)
        if edges.n_points:
            plot.add_mesh(edges, color='#293c50', line_width=1.5)
        plot.enable_parallel_projection()
        centre = np.array(mesh.center)
        direction = np.array([1., -1.25, .9]); direction /= np.linalg.norm(direction)
        plot.camera_position = [tuple(centre + direction * max(sizes) * 4), tuple(centre), (0, 0, 1)]
        # Fit actual projected vertices, not an assembly-aligned bounding sphere followed by arbitrary zoom.
        right = np.cross([0., 0., 1.], direction); right /= np.linalg.norm(right)
        up = np.cross(direction, right)
        relative = mesh.points - centre
        half_extent = max(float(np.max(np.abs(relative @ right))), float(np.max(np.abs(relative @ up))))
        plot.camera.parallel_scale = half_extent * 1.12
        plot.reset_camera_clipping_range()
        plot.enable_anti_aliasing('ssaa')
        output.parent.mkdir(parents=True, exist_ok=True)
        plot.screenshot(str(output))
    finally:
        plot.close()
    return {'bounds_mm': [round(v, 6) for v in bounds], 'triangles': mesh.n_cells,
            'size_px': [SIZE, SIZE], 'sha256': digest(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render', action='store_true', help='Render actual source geometry and update only the scoped catalog records')
    parser.add_argument('--check', action='store_true', help='Verify coverage, geometry/output hashes and PNG dimensions without CAD dependencies')
    parser.add_argument('--date', default=datetime.now(timezone.utc).date().isoformat(), help='Date for generated evidence (YYYY-MM-DD)')
    parser.add_argument('--only', help='Limit rendering to a scoped key for diagnostics; does not write the catalog/receipt')
    args = parser.parse_args()
    wanted = sources()
    if args.render:
        import cadquery, pyvista
        items = read('catalog/images.json')
        records = {}
        for key, source in wanted.items():
            if args.only and key != args.only:
                continue
            path, sha = check_source(key, source)
            target = 'exports/thumbs/' + key.replace('/', '--') + '.png'
            output = render(path, ROOT / target, COLOURS[source['material']])
            print(f'{key}: {output["triangles"]} triangles, {target}', flush=True)
            record = {'kind': 'render', 'source_url': source['source'], 'geometry_sha256': sha,
                'image_url': None, 'path': target, 'fetched': args.date, 'material': source['material'],
                'bom': source['bom'], 'group': source['group'], 'render': output}
            for field in ['geometry_manifest', 'note']:
                if field in source:
                    record[field] = source[field]
            records[key] = record
        if args.only:
            if not records:
                raise ValueError(f'Unknown scoped key: {args.only}')
            return
        items.update(records)
        # Old unscoped names must not continue showing stale PA6-CF turret/clashing assembly renders.
        for key in ['leg/output_adapter', 'rig/carriage_plate', 'turret/pan_clamp']:
            items[key.split('/')[1]] = {**records[key], 'alias_of': key}
        CATALOG.write_text(json.dumps({k: items[k] for k in sorted(items)}, indent=1) + '\n')
        receipt = {'schema': 1, 'date': args.date, 'command': 'python tools/part-media-generation.py --render --check',
            'generator_sha256': digest(Path(__file__)), 'renderer': {'cadquery': cadquery.__version__,
            'pyvista': pyvista.__version__, 'vtk': pyvista.vtk_version_info, 'projection': 'orthographic',
            'camera_direction': [1, -1.25, .9], 'up': [0, 0, 1], 'projected_fit_padding': 1.12, 'step_tolerance_mm': .08,
            'step_angular_tolerance_rad': .10},
            'counts': {'body_first_frame': sum(s['group']=='body-first-frame' for s in wanted.values()),
                       'machined_and_cut': sum(s['group']=='machined-and-cut' for s in wanted.values())},
            'parts': {k: {'geometry': v['source_url'], 'geometry_sha256': v['geometry_sha256'],
                          'image': v['path'], 'image_sha256': v['render']['sha256']} for k, v in records.items()}}
        RECEIPT.write_text(json.dumps(receipt, indent=2) + '\n')
    if args.check:
        items = read('catalog/images.json'); receipt = read('catalog/designed-media-validation.json')
        if set(receipt['parts']) != set(wanted):
            raise ValueError('Receipt does not cover exactly the current body print and made-to-order requirements')
        if receipt['generator_sha256'] != digest(Path(__file__)):
            raise ValueError('Generator changed: rerender before publishing its receipt')
        for key, source in wanted.items():
            path, sha = check_source(key, source); item = items.get(key, {})
            if item.get('source_url') != source['source'] or item.get('geometry_sha256') != sha:
                raise ValueError(f'{key}: catalog source/geometry hash is stale')
            target = ROOT / item['path']; data = target.read_bytes()
            if data[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack('>II', data[16:24]) != (SIZE, SIZE):
                raise ValueError(f'{key}: thumbnail is not a {SIZE}px square PNG')
            expected = receipt['parts'][key]
            if digest(target) != item['render']['sha256'] or expected != {
                'geometry': source['source'], 'geometry_sha256': sha,
                'image': item['path'], 'image_sha256': digest(target)}:
                raise ValueError(f'{key}: output/receipt hash mismatch')
        for key in ['leg/output_adapter', 'rig/carriage_plate', 'turret/pan_clamp']:
            alias = items[key.split('/')[1]]
            if alias != {**items[key], 'alias_of': key}:
                raise ValueError(f'{key}: legacy alias differs from its scoped source')
        counts = {group: sum(s['group'] == group for s in wanted.values()) for group in ['body-first-frame', 'machined-and-cut']}
        print(f'PASS: {len(wanted)} exact-source thumbnails; {counts["body-first-frame"]} body prints and {counts["machined-and-cut"]} machined/cut parts.', flush=True)
    if not args.render and not args.check:
        parser.error('Choose --render or --check')


if __name__ == '__main__':
    main()
