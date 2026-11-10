"""Adapt the existing authored turret recipe and accepted meshes; no CAD imports.

Neutral-pose reframe only: original triangle topology/normals are retained. Outputs
are educational WIP instructions, never a fabrication or operating release.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import html
import json
import math
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[3]
SOURCE_COMMIT = '4866459e2abdb6c7f5f25e9448156b6615593499'
SCENE = 'hardware/exports/sim/turret_box/manifest.json'
RECIPE = 'hardware/cad/turret/turret_assembly.py'
BOM = 'hardware/exports/turret/bench/bom.json'
EXCLUDED = {'hopper_flap': 'Dock refill flap is deferred by the authored recipe.',
            'bumper_ring': 'Robot-only bumper; not the bench turret sequence.',
            'board_bay_lid': 'No explicit lid installation action in the authored sequence; unplaced context.',
            'laser_screws': 'Named only in prose, not an authored mesh addition; unplaced context.',
            'laser_inserts': 'No explicit mesh installation action in the authored sequence; unplaced context.',
            'hopper_inserts': 'No explicit mesh installation action in the authored sequence; unplaced context.',
            'dt_plug': 'Connection is discussed in prose but has no authored mesh placement; unplaced context.'}
JOINTS = {'base', 'pan', 'tilt', 'pinion', 'dial', 'wheel_l', 'wheel_r', 'flap'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def valid_digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def source_bytes(root, name, revision=SOURCE_COMMIT):
    data = (root / name).read_bytes()
    recorded = subprocess.check_output(['git', 'show', revision + ':' + name], cwd=root)
    if data != recorded:
        raise ValueError('Source differs from pinned snapshot: ' + name)
    return data


def recipe_rows(data):
    tree = ast.parse(data)
    assignments = [n.value for n in tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'STEPS' for t in n.targets)]
    if len(assignments) != 1:
        raise ValueError('Expected one literal authored STEPS recipe')
    rows = ast.literal_eval(assignments[0])
    if len(rows) != 12 or any(len(row) != 5 for row in rows):
        raise ValueError('Unexpected authored sequence')
    return rows


def neutral_offset(entry, pivots):
    """Exact zero-angle bench hierarchy, then place TM face at z=0.

    Source builder leaves base/pinion vertices absolute, pan vertices relative to
    pan, tilt relative to pan+tilt, and wheel/dial/flap nested below tilt.
    Pinion's viewer-only subtract/add pivot cancels at the neutral pose.
    """
    group = entry['group']
    if group not in JOINTS:
        raise ValueError('Unexpected guide group: ' + group)
    pan, tilt = pivots['pan'], pivots['tilt']
    if group in ('base', 'pinion'):
        return [-v for v in pan]
    if group == 'pan':
        return [0., 0., 0.]
    if group == 'tilt':
        return list(tilt)
    return [a + b for a, b in zip(tilt, pivots[group])]


def reframe_stl(data, offset):
    if len(data) < 84 or len(data) != 84 + 50 * struct.unpack_from('<I', data, 80)[0]:
        raise ValueError('Expected exact-length binary STL')
    if len(offset) != 3 or not all(math.isfinite(v) for v in offset):
        raise ValueError('Invalid translation')
    result = bytearray(data)
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    for start in range(84, len(data), 50):
        values = struct.unpack_from('<12f', data, start)
        if not all(math.isfinite(v) for v in values):
            raise ValueError('Non-finite STL value')
        for vertex in range(3):
            point = [values[3 + vertex * 3 + axis] + offset[axis] for axis in range(3)]
            struct.pack_into('<3f', result, start + 12 + vertex * 12, *point)
            for axis, value in enumerate(struct.unpack_from('<3f', result, start + 12 + vertex * 12)):
                lo[axis], hi[axis] = min(lo[axis], value), max(hi[axis], value)
    if not all(math.isfinite(v) for v in lo + hi):
        raise ValueError('Empty STL')
    return bytes(result), lo + hi


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()


def plain_instructions(guide):
    """No-script fallback from the exact same authored guide, not historical prose."""
    esc = html.escape
    body = ''.join(f'<section id="{esc(step["id"])}"><h2>{i+1}. {esc(step["title"])}</h2>' +
                   (f'<img src="{esc(step["poster"]["file"])}" alt="{esc(step["title"])}" style="max-width:100%;height:auto">' if step.get('poster') else '') +
                   f'<p>{esc(step["text"])}</p><ul>' + ''.join(
                       f'<li>{esc(row["title"])} ×{row["quantity"]} modeled instances</li>'
                       for row in guide['source']['requirements_by_step'][step['id']]) + '</ul></section>'
                   for i, step in enumerate(guide['steps']))
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<script src="/web/theme.js"></script><link rel="stylesheet" href="/web/theme.css">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Turret assembly · WIP instructions</title>'
            '<style>main{max-width:75ch;margin:auto;padding:24px;line-height:1.6}section{margin:32px 0}</style>'
            '</head><body><main><a href="/designer/build.html">← Interactive Build guide</a>'
            '<h1>Turret bench assembly · WIP</h1><p>' + esc(guide['source']['qualification']) +
            '</p><p>Source ' + esc(guide['snapshot']['source_commit']) +
            '. The same authored sequence feeds interactive and plain instructions.</p>' +
            body + '</main></body></html>\n').encode()


def snapshot_index(guide_bytes, directory):
    guide = json.loads(guide_bytes)
    return encode({'schema': 'gyropup.build-guides/1', 'snapshots': [
        {'id': guide['snapshot']['id'], 'title': 'Turret bench · ' + guide['snapshot']['revision'],
         'status': 'wip', 'file': directory + '/guide.json', 'sha256': digest(guide_bytes)}],
        'unavailable': [{'id': 'released', 'reason': 'No named product build releases have been published.'},
                        {'id': 'rig', 'reason': 'Historical assembly illustrations contain withdrawn instructions; current guide is unavailable.'}]})


def generate(root=ROOT, posters=None):
    scene_data, recipe_data, bom_data = [source_bytes(root, f) for f in (SCENE, RECIPE, BOM)]
    scene, rows, bom = json.loads(scene_data), recipe_rows(recipe_data), json.loads(bom_data)
    outputs, parts, inputs = {}, [], {f: digest(d) for f, d in zip((SCENE, RECIPE, BOM), (scene_data, recipe_data, bom_data))}
    logical = {n for row in rows for n in row[1]}
    entries = [p for p in scene['parts'] if p['group'] in JOINTS]
    if len({p['name'] for p in entries}) != len(entries):
        raise ValueError('Duplicate mesh instance')
    if {p['part'] for p in entries} - logical != set(EXCLUDED):
        raise ValueError('Unaccounted modeled part; review recipe coverage')
    for entry in entries:
        if entry['part'] not in logical:
            continue
        name = 'hardware/exports/sim/turret_box/' + entry['file']
        data = source_bytes(root, name)
        if digest(data) != entry['sha256']:
            raise ValueError('Original manifest mesh digest mismatch: ' + name)
        offset = neutral_offset(entry, scene['pivots'])
        result, bounds = reframe_stl(data, offset)
        file = 'meshes/' + entry['file']
        outputs[file] = result
        inputs[name] = digest(data)
        parts.append({'name': entry['name'], 'file': file, 'color': entry['color'],
                      'sha256': digest(result), 'bounds_mm': bounds,
                      'logical_part': entry['part'], 'title': entry['title'],
                      'original_group': entry['group'], 'neutral_translation_mm': offset})
    manifest = {'title': 'Turret bench assembly · WIP', 'units': 'mm', 'up': 'z',
                'frame': 'Neutral assembled turret; TM face origin, x forward, y left, z up.', 'parts': parts}
    outputs['view.json'] = encode(manifest)
    chapters = [('pan-base', 'Pan base and drive', 1, 6), ('tilt-cradle', 'Tilt cradle', 7, 9),
                ('cartridge', 'Cartridge and final mounting', 10, 12)]
    subassemblies = []
    steps, installed, requirements_by_step = [], [], {}
    for number, (title, adds, lifts, camera, text) in enumerate(rows, 1):
        required = adds
        missing = set(required) - {p['logical_part'] for p in parts}
        if missing:
            raise ValueError('Recipe has missing meshes: ' + repr(sorted(missing)))
        highlight = [p['name'] for p in parts if p['logical_part'] in required]
        if set(highlight) & set(installed):
            raise ValueError('Instance added twice')
        installed += highlight
        offsets = {}
        for part in parts:
            if part['name'] in highlight:
                value = lifts.get(part['logical_part'], 0)
                offsets[part['name']] = [0, 0, value] if isinstance(value, (int, float)) else list(value)
        chapter = next(c[0] for c in chapters if c[2] <= number <= c[3])
        requirements = []
        for logical_part in required:
            instances = [p for p in parts if p['logical_part'] == logical_part]
            catalogue = [r for r in bom['bench_turret'] if r.get('for') == logical_part and r.get('qty', 0) > 0]
            requirements.append({'part': logical_part, 'title': instances[0]['title'],
                                 'instances': [p['name'] for p in instances],
                                 'quantity': len(instances), 'catalogue': [
                                     {k: r.get(k) for k in ('key', 'item', 'part_number', 'qty')} for r in catalogue]})
        requirements_by_step[f'step-{number:02d}'] = requirements
        steps.append({'id': f'step-{number:02d}', 'title': title, 'subassembly': chapter,
                      'parts': list(installed), 'highlight': highlight, 'offsets_mm': offsets,
                      'text': text, 'camera': {'direction': list(camera)},
                      'requires': [f'step-{number-1:02d}'] if number > 1 else []})
    for id_, title, start, end in chapters:
        subassemblies.append({'id': id_, 'title': title,
                              'parts': [p['name'] for p in parts if any(p['name'] in s['highlight'] for s in steps[start-1:end])]})
    source = {'inputs': inputs, 'converter_sha256': digest(Path(__file__).read_bytes()),
              'requirements_by_step': requirements_by_step,
              'original_scene_producer': '227afbcca70ab616f412ee7a00b119cfff3a0d20',
              'qualification': 'Educational WIP walkthrough. Fit, tightening, feed, laser class and safe operation remain unqualified. No print or fabrication release.',
              'assembly_pose': 'Neutral zero joint angles. Original triangle topology/normals retained; translation only.',
              'excluded': EXCLUDED,
              'bom': {'file': '../../../exports/turret/bench/bom.json', 'sha256': digest(bom_data)},
              'limits': scene['limits'],
              'instruction_items': 'Fastener quantities/tools/checks are authored in each step text. Mesh envelopes are not proof of fit, thread engagement or tool access.'}
    guide = {'schema': 'cad-agent.assembly-guide/1',
             'snapshot': {'id': 'turret-wip-' + SOURCE_COMMIT[:12], 'revision': SOURCE_COMMIT[:12], 'status': 'wip', 'source_commit': SOURCE_COMMIT},
             'model': {'file': 'view.json', 'sha256': digest(outputs['view.json'])},
             'source': source, 'subassemblies': subassemblies, 'steps': steps}
    if posters is not None:
        if not isinstance(posters, dict) or not valid_digest(posters.get('visual_sha256')):
            raise ValueError('Invalid poster visual binding')
        if set(posters.get('frames', {})) != {step['id'] for step in steps}:
            raise ValueError('Posters must cover exactly the twelve actual steps')
        for step in steps:
            frame = posters['frames'][step['id']]
            if frame.get('file') != 'posters/' + step['id'] + '.png' or not valid_digest(frame.get('sha256')):
                raise ValueError('Invalid step poster identity')
            step['poster'] = {'file': frame['file'], 'sha256': frame['sha256']}
        source['poster_visual_sha256'] = posters['visual_sha256']
    outputs['instructions.html'] = plain_instructions(guide)
    outputs['instructions.json'] = encode({'snapshot': guide['snapshot'], 'qualification': source['qualification'],
        'steps': [{k: step[k] for k in ('id', 'title', 'text')} | {'requirements': requirements_by_step[step['id']]}
                  for step in steps]})
    source['instructions'] = {'file': 'instructions.json', 'sha256': digest(outputs['instructions.json'])}
    outputs['guide.json'] = encode(guide)
    outputs['README.md'] = b'# Turret assembly guide snapshot\n\nEducational WIP only. Generated from the authored recipe and exact committed scene.\nExisting legacy assembly illustrations remain historical; none are reused as fresh posters.\n'
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'software/site/assets/build-guides/turret-wip-4866459e2abd')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    poster_record = args.out / 'posters.json'
    posters = json.loads(poster_record.read_text()) if poster_record.exists() else None
    outputs = generate(posters=posters)
    if posters:
        for frame in posters['frames'].values():
            if digest((args.out / frame['file']).read_bytes()) != frame['sha256']:
                raise SystemExit('Stale actual poster bytes: ' + frame['file'])
    index_bytes = snapshot_index(outputs['guide.json'], args.out.name)
    if args.check:
        for name, data in outputs.items():
            if (args.out / name).read_bytes() != data:
                raise SystemExit('Stale guide output: ' + name)
        if (args.out.parent / 'index.json').read_bytes() != index_bytes:
            raise SystemExit('Stale guide snapshot index')
        print(f'PASS {len(outputs)} source-bound guide outputs')
    else:
        for name, data in outputs.items():
            path = args.out / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (args.out.parent / 'index.json').write_bytes(index_bytes)
        print(f'Generated {len(outputs)} neutral guide outputs; no CAD or physical qualification')


if __name__ == '__main__':
    main()
