"""A source-bound README figure using the existing shared CAD motif tools.

Extraction is CAD work for a reviewed fleet run. Checking and presentation-only
rendering use the standard library. This never updates engineering exports.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
from pathlib import Path
import re
import runpy
import subprocess
import sys
from xml.sax.saxutils import escape

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
CONFIG = 'tools/engineering/robot/readme-design.json'
SOURCE_CONTEXT = 'tools/engineering/robot/robot_view.py'
NAMES = ('current-design.scene.json', 'current-design.svg', 'current-design.receipt.json')
DECODER = 'tools/site/assembly/robot_data.py'
LEG_BASELINE = '.agents/plans/end-packs/baseline.json'
GROUPS = ('far_leg', 'body', 'turret', 'near_leg')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs(root):
    """Reuse the complete conservative CAD closure, including moved CAD tests."""
    collect = runpy.run_path(str(root / 'hardware/cad/manufacturing/print_provenance.py'))['source_files']
    paths = set(collect(root)) | {root / SOURCE_CONTEXT}
    if not paths:
        raise ValueError('No current CAD inputs')
    for p in paths:
        if p.is_symlink() or not p.is_file():
            raise ValueError(f'Missing or nonregular current input: {p.relative_to(root)}')
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(paths)}


def verify_inputs(root, cfg):
    if any(k.startswith('GYROPUP_') for k in os.environ):
        raise ValueError('A published-design illustration cannot use GYROPUP_* overrides')
    actual = inputs(root)
    if actual != cfg['source']['files']:
        raise ValueError('Recorded CAD inputs changed; refresh from a reviewed source revision')
    return actual


def verify_public_tree(root, cfg):
    # Whole-hardware identity covers the full-body constructor's supplemental
    # board, mount and exported JSON inputs as well as the conservative CAD list.
    if git(root, 'rev-parse', 'HEAD:hardware') != cfg['source']['hardware_tree']:
        raise ValueError('Recorded hardware tree changed; refresh the illustration')
    if git(root, 'status', '--porcelain', '--untracked-files=all', '--', 'hardware'):
        raise ValueError('Unpublished hardware edits cannot describe the published design')


def profile_module(profile, cfg, filename):
    if git(profile, 'rev-parse', 'HEAD') != cfg['profile']['revision']:
        raise ValueError('Shared profile-tool revision differs')
    if git(profile, 'status', '--porcelain'):
        raise ValueError('Shared profile-tool checkout is not clean')
    path = profile / 'tools/hero' / filename
    if digest(path) != cfg['profile']['files'][filename]:
        raise ValueError(f'Shared tool bytes differ: {filename}')
    return load_module('readme_' + filename.removesuffix('.py'), path)


def extract_key(cfg):
    return fingerprint({'source': cfg['source'], 'projection': cfg['projection'],
                        'toolkit': cfg['toolkit'], 'runtime': cfg['runtime'],
                        'producer': digest(__file__), 'profile': cfg['profile'],
                        'collection': cfg.get('collection'),
                        'projection_runtime': cfg.get('projection_runtime')})


def regular_member(directory, relative):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Nonregular collection directory')
    if not isinstance(relative, str):
        raise ValueError('Unsafe collection member')
    path = Path(relative)
    if path.as_posix() != relative or path.is_absolute() or not path.parts or '..' in path.parts:
        raise ValueError('Unsafe collection member')
    result = directory
    for part in path.parts:
        result = result / part
        if result.is_symlink():
            raise ValueError('Symlink collection member')
    if not result.is_file():
        raise ValueError('Missing collection member')
    return result


def collection_binding(root, cfg, directory, expected_sha):
    """Validate immutable cached input bytes, without importing CAD or projection code."""
    manifest = regular_member(directory, 'collection.json')
    if digest(manifest) != expected_sha:
        raise ValueError('Collection byte identity differs')
    data = json.loads(manifest.read_text())
    if (data['schema'] != 'gyropup.robot-assembly-parts/1' or data['units'] != 'mm'
            or data['up'] != 'z' or data['frame'] != 'robot: x forward,y left,z up; hip-axis origin'
            or data['inputs'] != cfg['source']['files']
            or data['hardware_tree'] != cfg['source']['hardware_tree']
            or data['runtime'] != cfg['runtime']):
        raise ValueError('Collection source/runtime/frame differs')
    if not re.fullmatch('[0-9a-f]{40}', data['source_commit']):
        raise ValueError('Invalid original source revision')
    if (data['native_geometry']['units'] != 'mm' or data['native_geometry']['up'] != 'z'
            or data['native_geometry']['frame'] != 'assembled robot CAD mm/Z-up'):
        raise ValueError('Native source frame differs')
    baseline_file = regular_member(root, LEG_BASELINE)
    baseline = json.loads(baseline_file.read_text())
    parts = data['parts']
    names = [p['name'] for p in parts]
    files = [p['file'] for p in parts]
    if not names or any(not isinstance(n, str) or not n for n in names) or len(names) != len(set(names)) or len(files) != len(set(files)):
        raise ValueError('Empty or duplicate collection parts')
    mesh_directory = directory / 'meshes'
    if mesh_directory.is_symlink() or not mesh_directory.is_dir() or {p.name for p in mesh_directory.iterdir()} != {Path(f).name for f in files}:
        raise ValueError('Collection mesh membership differs')
    decoder_file = regular_member(root, DECODER)
    # This is the new consumer's decoder, not the original native producer.
    # Its bytes are bound separately; original producer inputs stay unchanged.
    decoder = load_module('readme_collection_input_decoder', decoder_file)
    triangle_counts = {g: 0 for g in GROUPS}
    for part in parts:
        path = regular_member(directory, part['file'])
        if Path(part['file']).parent.as_posix() != 'meshes' or digest(path) != part['sha256']:
            raise ValueError('Collection mesh byte identity differs')
        triangle_counts[anatomy(part['name'])] += len(decoder.vertices(path)) // 3
    legs = {p['name']: p['sha256'] for p in parts if p['name'].startswith(('L.', 'R.'))}
    if (legs != baseline['collection261_leg_mesh_sha256']
            or any(data['inputs'].get(n) != h for n, h in baseline['protected_leg_sources_sha256'].items())):
        raise ValueError('Protected leg identity differs')
    binding = {'sha256': expected_sha, 'source_commit': data['source_commit'],
               'hardware_tree': data['hardware_tree'], 'inputs_sha256': fingerprint(data['inputs']),
               'parts': len(parts), 'meshes_sha256': fingerprint({p['name']: {'file': p['file'], 'sha256': p['sha256']} for p in parts}),
               'groups': {g: [p['name'] for p in parts if anatomy(p['name']) == g] for g in GROUPS},
               'triangles': triangle_counts,
               'declared_tessellation': {'tol': 0.25, 'ang': 0.3},
               'native_geometry': data['native_geometry'],
               'native_producer_inputs_sha256': fingerprint(data['producer_inputs']),
               'protected_legs': {'file': LEG_BASELINE, 'sha256': digest(baseline_file), 'parts': len(legs)},
               'decoder': {'file': DECODER, 'sha256': digest(decoder_file)}}
    return data, binding


def anatomy(name):
    return 'far_leg' if name.startswith('L.') else 'near_leg' if name.startswith('R.') else 'turret' if name.startswith('turret.') else 'body'


def drawing_role(group):
    return 'glass' if 'hopper' in group else 'dark' if any(x in group for x in ('hardware', 'motor', 'tyre', 'hub', 'bought')) else 'accent' if any(x in group for x in ('link', 'barrel', 'battery')) else 'plate'


def project_groups(groups, cfg, shared, np, out, *, cached=False):
    """Use only the existing shared topology and projection implementation."""
    parts, counts = [], {}
    for group, members in groups.items():
        if not members:
            raise ValueError(f'Missing expected anatomical group: {group}')
        instances = []
        for name, role, value in members:
            triangles = value if cached else shared.tessellate(value, **cfg['projection']['mesh'])
            if not len(triangles) or not np.isfinite(triangles).all():
                raise ValueError(f'Undrawable CAD part: {name}')
            instances.append({'role': role, 'tris': triangles, 'topo': shared.mesh_topology(triangles)})
        regions, lines, depth = shared.group_drawing(instances, cfg['projection']['view'], cfg['projection'])
        if not regions:
            raise ValueError(f'No visible regions for {group}')
        parts.append({'name': group, 'group': group, 'from': [0, 0], 'regions': regions, 'lines': lines, 'depth': round(depth, 3)})
        counts[group] = {'parts': [n for n, _, _ in members], 'triangles': sum(len(i['tris']) for i in instances)}
        print(f'{group}: {len(members)} parts, {counts[group]["triangles"]} triangles', flush=True)
        (out / 'scene.partial.json').write_text(json.dumps({'parts': parts, 'counts': counts}) + '\n')
    return parts, counts


def extract_collection(root, cfg, profile, directory, out):
    """Project original accepted STL bytes; never construct or re-tessellate CAD."""
    if git(root, 'status', '--porcelain'):
        raise ValueError('Extraction requires a clean isolated checkout')
    verify_inputs(root, cfg)
    verify_public_tree(root, cfg)
    data, binding = collection_binding(root, cfg, directory, cfg['collection']['sha256'])
    if binding != cfg['collection'] or cfg['source']['revision'] != data['source_commit']:
        raise ValueError('Recorded collection binding differs')
    if cfg['projection']['mesh'] != binding['declared_tessellation']:
        raise ValueError('Cached tessellation cannot be regenerated at a different tolerance')
    forbidden = lambda: [n for n in sys.modules if n.split('.')[0] in ('hardware', 'cadquery', 'OCP', 'vtk', 'cadagent')]
    if forbidden():
        raise ValueError('Collection projection requires a fresh process without CAD modules')
    import numpy as np
    runtime = {'python': f'{sys.version_info.major}.{sys.version_info.minor}', 'numpy': np.__version__}
    if runtime != cfg['projection_runtime']:
        raise ValueError('Projection runtime differs; native runtime is not a substitute')
    shared = profile_module(profile, cfg, 'extract_mesh.py')
    decoder = load_module('readme_collection_decoder', root / DECODER)
    before, input_before = tracked(root), decoder.inventory(directory)
    (out / 'source-before.json').write_text(json.dumps(before, indent=1) + '\n')
    (out / 'collection-before.json').write_text(json.dumps(input_before, indent=1) + '\n')
    failed = False
    try:
        groups = {g: [] for g in GROUPS}
        for row in data['parts']:
            triangles = np.asarray(decoder.vertices(regular_member(directory, row['file'])), dtype=float).reshape(-1, 3, 3)
            groups[anatomy(row['name'])].append((row['name'], drawing_role(row['source_group']), triangles))
        parts, counts = project_groups(groups, cfg, shared, np, out, cached=True)
        return {'schema': 'gyropup.readme-design-collection/1', 'kind': 'cad', 'source': cfg['source'],
                'extract_key': extract_key(cfg), 'executed_checkout': git(root, 'rev-parse', 'HEAD'),
                'runtime': runtime, 'native_runtime': data['runtime'], 'collection': binding,
                'projection_environment': {'python': sys.version, 'machine': platform.machine(), 'system': platform.system()},
                'groups': list(groups), 'parts': parts, 'counts': counts,
                'source_policy': {'parameter_overrides': False, 'native_construction': False, 'input': 'original collected world-STL bytes'},
                'limits': 'Cached tessellation and group painter order are illustration approximations, not engineering gates.'}
    except BaseException:
        failed = True
        raise
    finally:
        try:
            after, input_after = tracked(root), decoder.inventory(directory)
            (out / 'source-after.json').write_text(json.dumps(after, indent=1) + '\n')
            (out / 'collection-after.json').write_text(json.dumps(input_after, indent=1) + '\n')
            if after != before or input_after != input_before or forbidden() or git(root, 'status', '--porcelain'):
                raise ValueError('Source, collection or CAD-import preservation guard failed')
            verify_inputs(root, cfg)
            verify_public_tree(root, cfg)
            profile_module(profile, cfg, 'extract_mesh.py')
        except BaseException as error:
            (out / 'source-guard-error.txt').write_text(str(error) + '\n')
            if not failed:
                raise


def render_svg(scene, cfg, profile):
    schema = 'gyropup.readme-design-collection/1' if cfg.get('collection') else 'gyropup.readme-design/1'
    if scene.get('schema') != schema or scene['extract_key'] != extract_key(cfg) or scene['source'] != cfg['source']:
        raise ValueError('Stale extracted scene; rendering cannot rebind CAD inputs')
    expected_runtime = cfg.get('projection_runtime', cfg['runtime'])
    if cfg.get('collection') and (scene.get('collection') != cfg['collection'] or scene.get('native_runtime') != cfg['runtime']):
        raise ValueError('Collection/native provenance differs')
    if cfg.get('collection') and any(scene['counts'].get(g, {}).get('parts') != names for g, names in cfg['collection']['groups'].items()):
        raise ValueError('Collection scene membership differs')
    if cfg.get('collection') and (scene.get('groups') != list(GROUPS)
            or [p['name'] for p in scene['parts']] != list(GROUPS)
            or {g: c['triangles'] for g, c in scene['counts'].items()} != cfg['collection']['triangles']):
        raise ValueError('Collection scene topology coverage differs')
    expected = {'far_leg', 'body', 'turret', 'near_leg'}
    if (scene.get('checks') or scene.get('marks') or scene['runtime'] != expected_runtime
            or len(scene['parts']) != 4 or {p['name'] for p in scene['parts']} != expected
            or set(scene['counts']) != expected
            or any(not c['parts'] or c['triangles'] <= 0 for c in scene['counts'].values())):
        raise ValueError('Incomplete scene or unsupported engineering-verdict decorations')
    renderer = profile_module(profile, cfg, 'heroes.py')
    doc = renderer.Doc()
    width, height = cfg['presentation']['size']
    # The shared motif owns the geometric drawing. This project supplies a small,
    # static frame, with no checkmarks or implied fit/FEA/operating verdict.
    drawing = renderer.motif_cad(doc, scene, (8, 5, width - 16, height - 10), cfg['presentation']['mini'], 0)
    css = ('.cad .ed{fill:none;stroke:var(--edge);stroke-width:.85;stroke-linecap:round;stroke-linejoin:round}'
           '.cad .sil{stroke:var(--edge);stroke-width:1.3;stroke-linejoin:round}'
           '.cad .glass{fill-opacity:.35}.scan{display:none}' + renderer.REDUCED_MOTION)
    title = 'Gyropup CAD illustration'
    description = (f"CAD inputs from source revision {cfg['source']['revision']}; "
                   f"published baseline {cfg['source']['published_baseline']}. "
                   'Bought parts include envelopes. Tessellated vector illustration, not physical qualification.')
    if cfg.get('collection'):
        description += f" Original cached collection {cfg['collection']['sha256']}; no new CAD construction."
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" style="max-width:100%;height:auto" role="img" aria-label="{title}">'
           f'<title>{title}</title><desc>{escape(description)}</desc><style>{css}</style>'
           f'<rect width="{width}" height="{height}" rx="8" fill="var(--bg2)"/>{drawing}</svg>\n')
    svg = renderer._colour(svg, cfg['presentation']['palette'], 'auto')
    problems = renderer.problems(svg)
    if problems or '<use' in svg:
        raise ValueError(f'Unsafe or oversized figure: {problems}')
    return svg


def tracked(root):
    paths = git(root, 'ls-files', '-z').split('\0')
    return {p: digest(root / p) for p in paths if p}


def extract(root, cfg, profile, toolkit, out):
    """Construct current CAD in memory; use unchanged shared extraction math."""
    if git(root, 'status', '--porcelain'):
        raise ValueError('Extraction requires a clean isolated checkout')
    source = verify_inputs(root, cfg)
    verify_public_tree(root, cfg)
    if (git(toolkit, 'rev-parse', 'HEAD') != cfg['toolkit']['revision']
            or git(toolkit, 'status', '--porcelain')):
        raise ValueError('CAD toolkit revision differs')
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(root), str(toolkit / 'software')]
    import cadagent
    import cadquery
    import numpy as np
    if not Path(cadagent.__file__).resolve().is_relative_to((toolkit / 'software/cadagent').resolve()):
        raise ValueError('CAD toolkit imported from another checkout or wheel')
    runtime = {'cadquery': cadquery.__version__, 'numpy': np.__version__,
               'cadquery-ocp': importlib.metadata.version('cadquery-ocp'),
               'vtk': importlib.metadata.version('vtk'),
               'cad_agent_revision': git(toolkit, 'rev-parse', 'HEAD')}
    if runtime != cfg['runtime']:
        raise ValueError(f'CAD runtime differs: {runtime}')
    shared = profile_module(profile, cfg, 'extract_mesh.py')
    before = tracked(root)
    (out / 'source-before.json').write_text(json.dumps(before, indent=1) + '\n')
    failed = False
    previous_j501 = os.environ.get('J501_DIR')
    no_live_j501 = out / 'no-live-j501'
    if no_live_j501.exists():
        raise ValueError('The public snapshot selector must not contain a live J501 project')
    os.environ['J501_DIR'] = str(no_live_j501)
    try:
        if any(n == 'hardware' or n.startswith('hardware.') for n in sys.modules):
            raise ValueError('Start extraction in a fresh process without cached project CAD')
        params = importlib.import_module('hardware.cad.body.body_params')
        params.CACHE = out / 'body-measurement-cache'  # Derived cache only, never an engineering export.
        print('Building recorded CAD in memory; using tracked J501 snapshot and fresh output cache', flush=True)
        robot = load_module('readme_robot_source', root / SOURCE_CONTEXT)
        rows = robot.collect()  # Deliberately never call export() or render().
        if params.j501_params().get('_source') != 'hardware/vendor/j501/parameters-0.9-g48r.json':
            raise ValueError('The CAD did not use the published J501 parameter snapshot')
        names = [n for _, _, n, _, _ in rows]
        if not rows or len(names) != len(set(names)):
            raise ValueError('Empty or duplicate CAD part names')
        for name, module in list(sys.modules.items()):
            if name == 'hardware' or name.startswith('hardware.'):
                origin = getattr(module, '__file__', None)
                locations = [origin] if origin else list(getattr(module, '__path__', ()))
                if not locations or any(not Path(p).resolve().is_relative_to(root.resolve()) for p in locations):
                    raise ValueError('Project CAD imported from another checkout')
        groups = {g: [] for g in GROUPS}
        for group, colour, name, shape, _ in rows:
            groups[anatomy(name)].append((name, drawing_role(group), shape))
        parts, counts = project_groups(groups, cfg, shared, np, out)
        scene = {'schema': 'gyropup.readme-design/1', 'kind': 'cad', 'source': cfg['source'],
                 'extract_key': extract_key(cfg), 'executed_checkout': git(root, 'rev-parse', 'HEAD'),
                 'runtime': runtime, 'groups': list(groups), 'parts': parts, 'counts': counts,
                 'source_policy': {'parameter_overrides': False, 'j501': 'tracked snapshot', 'measurement_cache': 'fresh run output'},
                 'limits': 'Sampled tessellation and group painter order are illustration approximations, not engineering gates.'}
        return scene
    except BaseException:
        failed = True
        raise
    finally:
        if previous_j501 is None:
            os.environ.pop('J501_DIR', None)
        else:
            os.environ['J501_DIR'] = previous_j501
        try:
            after = tracked(root)
            (out / 'source-after.json').write_text(json.dumps(after, indent=1) + '\n')
            if after != before or git(root, 'status', '--porcelain') or inputs(root) != source:
                raise ValueError('Source changed during read-only CAD extraction')
            verify_public_tree(root, cfg)
            if git(toolkit, 'status', '--porcelain') or git(profile, 'status', '--porcelain'):
                raise ValueError('A pinned tooling checkout changed during extraction')
        except BaseException as error:
            (out / 'source-guard-error.txt').write_text(str(error) + '\n')
            if not failed:
                raise


def bundle(scene, cfg, profile, out):
    scene_bytes = (json.dumps(scene, sort_keys=True, separators=(',', ':')) + '\n').encode()
    # The shared motif paints role dictionaries in iteration order. Render the
    # exact persisted representation so extraction and later parity agree.
    svg = render_svg(json.loads(scene_bytes), cfg, profile)
    receipt = {'schema': 'gyropup.readme-design-receipt/1', 'extract_key': extract_key(cfg),
               'source_revision': cfg['source']['revision'], 'source_inputs': fingerprint(cfg['source']['files']),
               'hardware_tree': cfg['source']['hardware_tree'],
               'profile': cfg['profile'], 'toolkit': cfg['toolkit'],
               'projection': cfg['projection'], 'presentation': cfg['presentation'],
               'render_key': fingerprint({'presentation': cfg['presentation'], 'renderer': cfg['profile']['files']['heroes.py']}),
               'scene_sha256': hashlib.sha256(scene_bytes).hexdigest(), 'svg_sha256': hashlib.sha256(svg.encode()).hexdigest()}
    if cfg.get('collection'):
        receipt.update(schema='gyropup.readme-design-receipt/2', collection=cfg['collection'],
                       native_runtime=cfg['runtime'], projection_runtime=scene['runtime'],
                       projection_environment=scene['projection_environment'],
                       toolkit_usage='Original native collection provenance only; no CAD toolkit imported by projection')
    return scene_bytes, svg.encode(), (json.dumps(receipt, sort_keys=True, indent=2) + '\n').encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('bind-source', 'bind-collection', 'check', 'extract', 'extract-collection', 'render'))
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--collection', type=Path)
    parser.add_argument('--collection-sha', help='Reviewed immutable collection byte seal for binding only')
    parser.add_argument('--revision')
    parser.add_argument('--candidate-source', action='store_true',
                        help='record clean current HEAD for review before its normal main publication')
    parser.add_argument('--toolkit', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--scene', type=Path)
    parser.add_argument('--candidate', type=Path, help='check a genuine unadopted candidate without changing source')
    args = parser.parse_args()
    cfg = json.loads((ROOT / CONFIG).read_text())
    if args.command == 'bind-source':
        if cfg.get('collection'):
            raise ValueError('Use bind-collection for cached native input; never rebind an old scene')
        if not args.revision:
            raise ValueError('Choose an immutable source revision')
        revision = git(ROOT, 'rev-parse', args.revision + '^{commit}')
        published = git(ROOT, 'rev-parse', 'origin/main')
        if args.candidate_source:
            if revision != git(ROOT, 'rev-parse', 'HEAD') or git(ROOT, 'status', '--porcelain', '--', 'hardware'):
                raise ValueError('Candidate source must be committed current HEAD with unchanged hardware')
        elif revision != published:
            raise ValueError('Requested source is not the fetched published main revision')
        files = inputs(ROOT)
        for name, expected in files.items():
            raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', revision + ':' + name])
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError(f'Current input is not the recorded source byte sequence: {name}')
        cfg['source'] = {'repository': 'Valpatel/gyropup', 'revision': revision,
                         'published_baseline': published,
                         'hardware_tree': git(ROOT, 'rev-parse', revision + ':hardware'), 'files': files}
        verify_public_tree(ROOT, cfg)
        (ROOT / CONFIG).write_text(json.dumps(cfg, indent=2) + '\n')
        print('Recorded requested source inputs only; no scene, SVG or receipt was refreshed; publication is checked separately')
        return
    if args.command == 'bind-collection':
        if not args.collection or not args.collection_sha or not re.fullmatch('[0-9a-f]{64}', args.collection_sha):
            raise ValueError('Choose a collection directory and reviewed byte seal')
        verify_inputs(ROOT, cfg)
        verify_public_tree(ROOT, cfg)
        data, binding = collection_binding(ROOT, cfg, args.collection, args.collection_sha)
        if git(ROOT, 'rev-parse', data['source_commit'] + ':hardware') != data['hardware_tree']:
            raise ValueError('Original native source hardware differs')
        for name, expected in data['inputs'].items():
            raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', data['source_commit'] + ':' + name])
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError('Original native source input differs: ' + name)
        cfg['schema'] = 'gyropup.readme-design-config/2'
        cfg['source'] = {'repository': 'Valpatel/gyropup', 'revision': data['source_commit'],
                         'published_baseline': git(ROOT, 'rev-parse', 'origin/main'),
                         'hardware_tree': data['hardware_tree'], 'files': data['inputs']}
        cfg['collection'] = binding
        # A declared target, checked against the actual projection process before work.
        cfg['projection_runtime'] = {'python': f'{sys.version_info.major}.{sys.version_info.minor}', 'numpy': data['runtime']['numpy']}
        (ROOT / CONFIG).write_text(json.dumps(cfg, indent=2) + '\n')
        print('Bound original collection/source and planned projection runtime only; no scene, SVG or receipt changed')
        return
    if args.command == 'extract' and cfg.get('collection'):
        raise ValueError('Cached collection mode requires extract-collection, not new CAD construction')
    if args.command == 'extract-collection' and (not args.collection or not cfg.get('collection')):
        raise ValueError('Bind a reviewed collection before extract-collection')
    if not args.profile:
        raise ValueError('Provide the pinned shared profile-tool checkout')
    verify_inputs(ROOT, cfg)
    verify_public_tree(ROOT, cfg)
    if args.command == 'check':
        directory = args.candidate or ROOT / cfg['artifacts']['scene_directory']
        scene = json.loads((directory / NAMES[0]).read_text())
        actual = ([directory / n for n in NAMES] if args.candidate else
                  [directory / NAMES[0], ROOT / cfg['artifacts']['svg'], directory / NAMES[2]])
        if [p.read_bytes() for p in actual] != list(bundle(scene, cfg, args.profile, None)):
            raise ValueError('Figure/scene/receipt differ from the real renderer')
        print(f"Current CAD illustration: {len(cfg['source']['files'])} inputs; pure SVG parity passed")
        return
    if not args.out or args.out.resolve().is_relative_to(ROOT):
        raise ValueError('Generate into an owned output directory outside the source checkout')
    args.out.mkdir(parents=True, exist_ok=False)
    if args.command in ('extract', 'extract-collection'):
        if args.command == 'extract' and not args.toolkit:
            raise ValueError('Extraction requires the pinned CAD toolkit checkout')
        scene = (extract_collection(ROOT, cfg, args.profile, args.collection, args.out)
                 if args.command == 'extract-collection' else extract(ROOT, cfg, args.profile, args.toolkit, args.out))
        # Preserve a fully bound successful extraction before any presentation
        # or SVG-budget assertion. A failed render never forces a fake rebind.
        (args.out / 'extracted.scene.json').write_text(json.dumps(scene, sort_keys=True, separators=(',', ':')) + '\n')
    else:
        scene = json.loads((args.scene or ROOT / cfg['artifacts']['scene_directory'] / NAMES[0]).read_text())
    before_render = tracked(ROOT)
    status_before_render = git(ROOT, 'status', '--porcelain')
    values = bundle(scene, cfg, args.profile, args.out)
    after_render = tracked(ROOT)
    (args.out / 'source-after-render.json').write_text(json.dumps(after_render, indent=1) + '\n')
    if after_render != before_render or git(ROOT, 'status', '--porcelain') != status_before_render:
        raise ValueError('Source changed during SVG presentation rendering')
    candidate = args.out / 'candidate'
    candidate.mkdir()
    for name, value in zip(NAMES, values):
        (candidate / name).write_bytes(value)
    (args.out / 'scene.partial.json').unlink(missing_ok=True)
    print('Generated candidate only; independent review and guarded adoption remain required')


if __name__ == '__main__':
    main()
