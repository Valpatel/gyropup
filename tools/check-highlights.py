#!/usr/bin/env python3
"""Check source-bound highlights, decoded motion and fault controls without CAD."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'web/highlights'
WIDTH, HEIGHT, FPS, FRAMES = 1280, 720, 30, 660
LEG_REVISION = 'ae919f7211f236f398ff77cc25d00c2017c1ab9c'
LEG = 'exports/leg/rig_jump.mp4'
E1 = 'exports/leg/fea/hip-frame-e1-media/'
MOVIES = ['gyropup-highlights.mp4', 'gyropup-highlights.webm']
POSTER = 'gyropup-highlights.webp'
CAPTURE_COUNTS = {'turret': 120, 'mechanism': 90, 'battle': 180, 'character': 90}
TURRET_GROUPS = {'base', 'pan', 'tilt', 'pinion', 'dial', 'wheel_l', 'wheel_r', 'flap'}
# Pixel regions exclude all added lower thirds and the original E1 captions.
SEGMENTS = [
    dict(id='turret', start=0, frames=120, samples=[5, 110], crop=[280, 120, 720, 430],
         title='Current turret', subtitle='Explore the public CAD'),
    dict(id='mechanism', start=120, frames=90, samples=[125, 200], crop=[280, 120, 720, 430],
         title='Inside the mechanism', subtitle='Illustrative feed and flywheel motion'),
    dict(id='battle', start=210, frames=180, samples=[220, 370], crop=[130, 100, 1020, 450],
         title='Target practice', subtitle='Interactive play simulation'),
    dict(id='leg', start=390, frames=90, samples=[393, 414], crop=[300, 100, 680, 450],
         title='Archived MuJoCo', subtitle='16.25 kg leg-rig jump study'),
    dict(id='e1', start=480, frames=90, samples=[482, 567], crop=[360, 140, 590, 360],
         source_start_seconds=1, layout='Native 960 x 720, centered with 160 px side bars; all original labels retained'),
    dict(id='character', start=570, frames=90, samples=[575, 650], crop=[280, 100, 720, 450]),
]


def require(test, message):
    if not test:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    return sha(Path(path).read_bytes())


def read(path):
    return json.loads(Path(path).read_text())


def command(args):
    return subprocess.check_output([str(x) for x in args], cwd=ROOT)


def git_bytes(revision, path):
    return command(['git', 'show', f'{revision}:{path}'])


def png_size(path):
    data = Path(path).read_bytes()
    require(data[:8] == b'\x89PNG\r\n\x1a\n', f'Not a PNG: {path}')
    return struct.unpack('>II', data[16:24])


def safe_path(root, name):
    path = (root / name).resolve()
    require(path.is_relative_to(root.resolve()), f'Path escapes its source directory: {name}')
    return path


def required_capture_inputs():
    """Derive geometry closure independently of the capture's optional inputs map."""
    paths = {
        '/designer/' + name for name in (
            'sim.js', 'robot_v2.js', 'current_turret.js', 'turret_bench.js', 'turret_reload.js',
            'robot3d.js', 'cadrig.js', 'turret3d.js', 'model.js', 'sfx.js', 'robot_actions.js',
            'character/eyes.js', 'character/talk.js', 'kit/stage.js', 'kit/portal-data.js',
            'kit/smooth_zoom.js', 'kit/panel.js', 'kit/loading.js',
            'kit/vendor/three/three.module.min.js', 'kit/vendor/three/addons/loaders/STLLoader.js',
            'kit/vendor/three/addons/controls/OrbitControls.js',
            'kit/vendor/three/addons/geometries/RoundedBoxGeometry.js')
    }
    for directory in ('exports/sim/turret_box', 'exports/sim/v2/rig', 'exports/sim/v2/leg-attachments'):
        paths.add('/' + directory + '/manifest.json')
        manifest = read(ROOT / directory / 'manifest.json')
        if directory.endswith('/rig'):
            # Current presentation deliberately excludes the archived turret's
            # fixed meshes; recorded modes own those meshes and their old frames.
            parts = [p for p in manifest['body'] if not p['name'].startswith('turret_')]
            parts += [p for group in manifest['links'].values() for p in group]
        else:
            parts = manifest['parts']
        paths.update('/' + directory + '/' + part['file'] for part in parts)
    return paths


def expected_sources(capture):
    paths = {name.lstrip('/') for name, item in capture['inputs'].items() if item.get('repoSha256')}
    paths.update({'tools/capture-highlights.mjs', 'tools/encode-highlights.py', 'tools/check-highlights.py',
                  'designer/kit/vendor/fonts/inter.woff2', LEG, E1 + 'hip-frame-e1.mp4',
                  E1 + 'field-receipt.json', E1 + 'video-receipt.json', E1 + 'hip_frame-E1.json',
                  'exports/leg/fea/summary.json', 'exports/leg/fea/media.json'})
    return paths


def historical_leg():
    data = git_bytes(LEG_REVISION, 'exports/leg/rig-results.json')
    report = json.loads(data)
    run = {key: value for key, value in report['scenarios']['jump'].items() if key != 'series'}
    return dict(revision=LEG_REVISION, report='exports/leg/rig-results.json', report_sha256=sha(data),
                video=LEG, video_sha256=sha(git_bytes(LEG_REVISION, LEG)),
                half_mass_kg=report['half_mass_kg'], bus_v=report['bus_v'], wheel='odrive-botwheel',
                scenario=run, status='Historical simulated single-leg rig; not a current full-robot or hardware test')


def validate_bindings(receipt, capture, frame_manifest, out=OUT, raw_frames=None):
    require(receipt['schema'] == 1, 'Unknown highlights receipt schema')
    require(receipt['format'] == dict(width=WIDTH, height=HEIGHT, fps=FPS, frames=FRAMES, seconds=22, audio=False),
            'Wrong highlights format')
    require(receipt['segments'] == SEGMENTS, 'Edit timeline or factual captions changed')
    required = required_capture_inputs()
    require(required <= set(capture['inputs']), 'Required renderer or manifest-derived mesh missing from capture')
    require(all(capture['inputs'][name].get('repoSha256') for name in required), 'Required capture input has no repository identity')
    require(set(receipt['source_hashes']) == expected_sources(capture), 'Incomplete source closure')
    for name, digest in receipt['source_hashes'].items():
        require(file_sha(safe_path(ROOT, name)) == digest, f'Source changed: {name}')
    require(capture['recipeSha256'] == receipt['source_hashes']['tools/capture-highlights.mjs'], 'Capture recipe changed')
    require((capture['width'], capture['height'], capture['fps']) == (WIDTH, HEIGHT, FPS), 'Capture size/rate changed')
    for name, item in capture['inputs'].items():
        if item.get('repoSha256'):
            require(receipt['source_hashes'][name.lstrip('/')] == item['repoSha256'], f'Captured source differs: {name}')
        # Model data and simulator modules have no static-build rewriting. Only the
        # instrumented stage gets the narrowly specified callback exposure below.
        if item.get('repoSha256') and (name.endswith(('.js', '.stl')) or name.startswith('/exports/sim/')):
            if name == '/designer/kit/stage.js':
                data = safe_path(ROOT, name.lstrip('/')).read_bytes()
                needle = b'const callbacks = [];'
                require(data.count(needle) == 1, 'Stage capture seam is no longer unique')
                data = data.replace(needle, needle + b' window.__captureCallbacks = callbacks;')
                require(sha(data) == item['servedSha256'], 'Stage instrumentation changed beyond callback exposure')
            else:
                require(item['servedSha256'] == item['repoSha256'], f'Served simulation differs: {name}')
    shots = {shot['id']: shot for shot in capture['shots']}
    require(set(shots) == set(CAPTURE_COUNTS), 'Incomplete current-model capture')
    require(set(frame_manifest['shots']) == set(CAPTURE_COUNTS), 'Incomplete captured frame manifest')
    turret_manifest = read(ROOT / 'exports/sim/turret_box/manifest.json')
    bench_names = sorted(p['name'] for p in turret_manifest['parts'])
    current_names = sorted(p['name'] for p in turret_manifest['parts'] if p['group'] in TURRET_GROUPS)
    require(len(bench_names) == 66 and len(current_names) == 48, 'Review reel against the changed public turret snapshot')
    for name, count in CAPTURE_COUNTS.items():
        shot = shots[name]
        require(shot['frames'] == count and len(shot['observations']) == count, f'Wrong capture count: {name}')
        require(sorted(shot['info']['parts']) == (bench_names if name in ('turret', 'mechanism') else current_names), f'Wrong model snapshot: {name}')
        require(all(not row['error'] for row in shot['observations']), f'Capture stage error: {name}')
        rows = frame_manifest['shots'][name]
        require(len(rows) == count, f'Wrong frame manifest count: {name}')
        for index, row in enumerate(rows):
            require(row['file'] == f'{name}/{index:05}.png' and row['width'] == WIDTH and row['height'] == HEIGHT,
                    f'Wrong frame layout: {name}/{index}')
            require(len(row['sha256']) == 64 and row['bytes'] > 1000, 'Invalid captured frame identity')
            if raw_frames:
                path = safe_path(raw_frames, row['file'])
                require(file_sha(path) == row['sha256'] and path.stat().st_size == row['bytes'], f'Captured frame changed: {row["file"]}')
                require(png_size(path) == (WIDTH, HEIGHT), 'Actual PNG dimensions differ from receipt')
    require(shots['mechanism']['observations'][-1]['shots'] > 0, 'Mechanism did not emit a shot')
    battle = shots['battle']['observations'][-1]
    require(battle['shots'] >= 3 and battle['hits'] >= 2 and battle['targetsDown'] >= 2, 'Target play did not produce actual impacts')
    require(receipt['historical_leg'] == historical_leg(), 'Historical leg baseline differs from the matching video revision')
    require(receipt['historical_leg']['video_sha256'] == receipt['source_hashes'][LEG], 'Leg clip is not its historical Git blob')
    require(receipt['e1'] == dict(source_start_seconds=1, source_duration_seconds=3, transient_simulation=False,
                                deformation_exaggeration=16, safety_factor=1.63, required=2, baseline_kg=37.5),
            'Static E1 evidence mislabeled')
    # Reuse the independent field/report closure check; no solver is imported.
    spec = importlib.util.spec_from_file_location('study_check', ROOT / 'tools/check-study-media.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.validate(decode=False)
    require(set(receipt['outputs']) == set(MOVIES + [POSTER, 'capture-receipt.json', 'capture-frames.json']), 'Incomplete highlights outputs')
    for name, item in receipt['outputs'].items():
        path = safe_path(out, name)
        require(path.stat().st_size == item['bytes'] and file_sha(path) == item['sha256'], f'Output changed: {name}')


def moving_pixels(first, second):
    require(len(first) == len(second) and len(first) > 0, 'Missing decoded model pixels')
    delta = [abs(a - b) for a, b in zip(first, second)]
    mean = sum(delta) / len(delta)
    changed = sum(value > 12 for value in delta) / len(delta)
    require(mean > 1 and changed > .01, f'Frozen or imperceptible model motion: mean={mean:.4f}, changed={changed:.4f}')
    return dict(mean_channel_difference=mean, fraction_changed_over_12=changed)


def matching_pixels(reference, sample, limit, message):
    require(len(reference) == len(sample) and len(reference) > 0, 'Missing image comparison pixels')
    error = sum(abs(x-y) for x,y in zip(reference, sample)) / len(reference)
    require(error < limit, message)
    return error


def sample_pixels(movie, segment):
    first, second = segment['samples']
    x, y, w, h = segment['crop']
    data = command(['ffmpeg', '-v', 'error', '-i', movie, '-vf',
                    f"select='eq(n,{first})+eq(n,{second})',crop={w}:{h}:{x}:{y},scale=160:100",
                    '-fps_mode', 'vfr', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    size = 160 * 100 * 3
    require(len(data) == size * 2, f'Missing decoded samples: {segment["id"]}')
    return data[:size], data[size:]


def mp4_atoms(path):
    data = path.read_bytes(); offset = 0; atoms = []
    while offset + 8 <= len(data):
        size, kind = struct.unpack('>I4s', data[offset:offset + 8])
        if size == 1:
            require(offset + 16 <= len(data), 'Truncated MP4 atom')
            size = struct.unpack('>Q', data[offset + 8:offset + 16])[0]
        if size == 0: size = len(data) - offset
        require(size >= 8 and offset + size <= len(data), 'Invalid MP4 atom size')
        atoms.append(kind.decode('ascii')); offset += size
    require(offset == len(data), 'Unparsed MP4 bytes')
    return atoms


def validate_media(out=OUT):
    result = {}; decoded = {}
    for name in MOVIES:
        movie = out / name
        probe = json.loads(command(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', movie]))
        require(len(probe['streams']) == 1, 'Highlights must contain only silent video')
        stream = probe['streams'][0]
        require(stream['codec_type'] == 'video' and stream['width'] == WIDTH and stream['height'] == HEIGHT
                and stream['pix_fmt'] == 'yuv420p' and stream['avg_frame_rate'] == '30/1'
                and int(stream['nb_read_frames']) == FRAMES and abs(float(probe['format']['duration']) - 22) < .001,
                f'Wrong decoded media format: {name}')
        if name.endswith('.mp4'):
            require(stream['codec_name'] == 'h264' and stream['profile'] == 'High' and stream['level'] == 31, 'H.264 profile differs from player capability query')
            atoms = mp4_atoms(movie)
            require('moov' in atoms and 'mdat' in atoms and atoms.index('moov') < atoms.index('mdat'), 'MP4 is not faststart')
        else:
            require(stream['codec_name'] == 'vp9' and stream['profile'] == 'Profile 0', 'Wrong WebM companion codec')
        require(20_000 < movie.stat().st_size < 6_000_000, 'Movie exceeds landing-page transfer budget')
        command(['ffmpeg', '-v', 'error', '-xerror', '-i', movie, '-f', 'null', '-'])
        motion = {}; decoded[name] = {}
        for segment in SEGMENTS:
            first, second = sample_pixels(movie, segment)
            motion[segment['id']] = moving_pixels(first, second)
            decoded[name][segment['id']] = first + second
        result[name] = dict(bytes=movie.stat().st_size, frames=FRAMES, seconds=22, motion=motion)
    for segment in SEGMENTS:
        a = decoded[MOVIES[0]][segment['id']]; b = decoded[MOVIES[1]][segment['id']]
        error = sum(abs(x - y) for x, y in zip(a, b)) / len(a)
        require(error < 7, f'Codec companions show different scenes: {segment["id"]}')
        result.setdefault('codec_mean_difference', {})[segment['id']] = error
    # Independently compare the entire first E1 frame, including every original
    # caption, with its solved-field presentation source. A moving cropped model
    # alone would miss erased failure/baseline/exaggeration labels.
    original_e1 = command(['ffmpeg', '-v', 'error', '-ss', '1', '-i', ROOT / E1 / 'hip-frame-e1.mp4',
                           '-vf', 'fps=30,scale=240:180', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    original_labels = command(['ffmpeg', '-v', 'error', '-ss', '1', '-i', ROOT / E1 / 'hip-frame-e1.mp4',
                               '-vf', 'fps=30,crop=960:195:0:525,scale=240:49', '-frames:v', '1',
                               '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    for name in MOVIES:
        e1_frame = command(['ffmpeg', '-v', 'error', '-i', out / name, '-vf',
                           "select='eq(n,480)',crop=960:720:160:0,scale=240:180", '-frames:v', '1',
                           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
        require(len(original_e1) == len(e1_frame) == 240 * 180 * 3, 'Missing original E1 frame/labels')
        error = matching_pixels(original_e1, e1_frame, 3, 'E1 full-frame presentation/labels were altered')
        result.setdefault('e1_original_frame_mean_difference', {})[name] = error
        labels = command(['ffmpeg', '-v', 'error', '-i', out / name, '-vf',
                          "select='eq(n,480)',crop=960:195:160:525,scale=240:49", '-frames:v', '1',
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
        result.setdefault('e1_original_labels_mean_difference', {})[name] = matching_pixels(
            original_labels, labels, 3, 'E1 strength failure, displacement, exaggeration or baseline labels were altered')
    try: matching_pixels(original_labels, bytes(len(original_labels)), 3, 'Erased E1 labels')
    except ValueError: result['erased_e1_labels_rejected'] = True
    else: raise ValueError('Erased-label negative control escaped')
    poster_probe = json.loads(command(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', out / POSTER]))['streams'][0]
    require(poster_probe['codec_name'] == 'webp' and (poster_probe['width'], poster_probe['height']) == (WIDTH, HEIGHT), 'Wrong poster format')
    require((out / POSTER).stat().st_size < 250_000, 'Poster exceeds transfer budget')
    movie_pixels = command(['ffmpeg', '-v', 'error', '-i', out / MOVIES[0], '-vf', "select='eq(n,30)',scale=160:90", '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    poster_pixels = command(['ffmpeg', '-v', 'error', '-i', out / POSTER, '-vf', 'scale=160:90', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    require(len(movie_pixels) == len(poster_pixels) == 160 * 90 * 3, 'Missing poster comparison pixels')
    poster_error = sum(abs(x-y) for x,y in zip(movie_pixels, poster_pixels)) / len(movie_pixels)
    require(poster_error < 5, 'Poster does not match reel frame 30')
    result['poster_mean_difference'] = poster_error
    return result, decoded


def negative_controls(receipt, capture, frames, out, decoded):
    rejected = []
    def fault(label, mutate):
        r, c, f = copy.deepcopy(receipt), copy.deepcopy(capture), copy.deepcopy(frames)
        mutate(r, c, f)
        try: validate_bindings(r, c, f, out)
        except (ValueError, KeyError): rejected.append(label)
        else: raise ValueError('Negative control escaped: ' + label)
    fault('source hash', lambda r,c,f: r['source_hashes'].__setitem__('designer/current_turret.js', '0'*64))
    fault('source omission', lambda r,c,f: r['source_hashes'].pop(LEG))
    def omit_required(r, c, f):
        path = '/exports/sim/turret_box/' + read(ROOT / 'exports/sim/turret_box/manifest.json')['parts'][0]['file']
        c['inputs'].pop(path)
        r['source_hashes'].pop(path.lstrip('/'))
    fault('self-consistent required mesh omission', omit_required)
    def omit_module(r, c, f):
        c['inputs'].pop('/designer/current_turret.js')
        r['source_hashes'].pop('designer/current_turret.js')
    fault('self-consistent required renderer omission', omit_module)
    fault('capture recipe', lambda r,c,f: c.__setitem__('recipeSha256', '0'*64))
    fault('served simulator', lambda r,c,f: c['inputs']['/designer/sim.js'].__setitem__('servedSha256', '0'*64))
    fault('stage instrumentation', lambda r,c,f: c['inputs']['/designer/kit/stage.js'].__setitem__('servedSha256', '0'*64))
    fault('frame count', lambda r,c,f: f['shots']['battle'].pop())
    fault('wrong turret name with unchanged part count', lambda r,c,f: next(s for s in c['shots'] if s['id']=='battle')['info']['parts'].__setitem__(0, 'older_turret'))
    fault('historical load baseline', lambda r,c,f: r['historical_leg'].__setitem__('half_mass_kg', 18.75))
    fault('static animation label', lambda r,c,f: r['e1'].__setitem__('transient_simulation', True))
    fault('media bytes', lambda r,c,f: r['outputs'][MOVIES[0]].__setitem__('sha256', '0'*64))
    for segment in SEGMENTS:
        first = decoded[MOVIES[0]][segment['id']][:160*100*3]
        try: moving_pixels(first, first)
        except ValueError: rejected.append('frozen ' + segment['id'])
        else: raise ValueError('Frozen-frame negative control escaped')
    return rejected


def validate(out=OUT, raw_frames=None, faults=True):
    receipt = read(out / 'receipt.json'); capture = read(out / 'capture-receipt.json'); frames = read(out / 'capture-frames.json')
    validate_bindings(receipt, capture, frames, out, raw_frames)
    result, decoded = validate_media(out)
    if faults: result['rejected_negative_controls'] = negative_controls(receipt, capture, frames, out, decoded)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--frames', type=Path, help='Also verify the original PNGs when locally available')
    args = parser.parse_args()
    print(json.dumps(validate(args.output.resolve(), args.frames), indent=2))
