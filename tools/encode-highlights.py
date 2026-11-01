#!/usr/bin/env python3
"""Edit captured model frames and explicitly historical studies into the 22 s reel.

Requires FFmpeg with libx264, libvpx-vp9, libwebp and FreeType. No solver runs.
Pixel/codec identity is checked; cross-host byte-identical rendering is not promised.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('highlights_check', ROOT / 'tools/check-highlights.py')
check = importlib.util.module_from_spec(spec); spec.loader.exec_module(check)


def run(args):
    subprocess.run([str(x) for x in args], cwd=ROOT, check=True)


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def frame_manifest(frames):
    report = dict(schema=1, shots={})
    for name, count in check.CAPTURE_COUNTS.items():
        paths = sorted((frames / name).glob('*.png'))
        check.require([p.name for p in paths] == [f'{i:05}.png' for i in range(count)], f'Expected exactly {count} complete {name} frames')
        rows = []
        for path in paths:
            width, height = check.png_size(path)
            check.require((width, height) == (check.WIDTH, check.HEIGHT), f'Actual PNG size is {width} x {height}: {path}')
            rows.append(dict(file=f'{name}/{path.name}', sha256=check.file_sha(path), bytes=path.stat().st_size, width=width, height=height))
        report['shots'][name] = rows
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames', type=Path, default=Path('/tmp/gyropup-highlights-frames'))
    parser.add_argument('--output', type=Path, default=check.OUT)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--crf', type=int, default=21, help='H.264 constant quality (default 21)')
    parser.add_argument('--vp9-crf', type=int, default=31)
    args = parser.parse_args()
    frames, out = args.frames.resolve(), args.output.resolve()
    capture = check.read(frames / 'capture-receipt.json')
    manifest = frame_manifest(frames)
    check.require(capture['recipeSha256'] == check.file_sha(ROOT / 'tools/capture-highlights.mjs'), 'Capture recipe changed since frames were made')
    out.mkdir(parents=True, exist_ok=True)
    source_hashes = {name: check.file_sha(check.safe_path(ROOT, name)) for name in sorted(check.expected_sources(capture))}
    historical = check.historical_leg()
    check.require(source_hashes[check.LEG] == historical['video_sha256'], 'Leg footage differs from archived source')
    # Temporary normalized lossless segments avoid re-encoding the two companions
    # from one another. FFmpeg decodes both final outputs in the independent check.
    with tempfile.TemporaryDirectory(prefix='gyropup-highlights-edit-') as temp:
        tmp = Path(temp); segments = []
        font = ROOT / 'designer/kit/vendor/fonts/inter.woff2'
        for segment in check.SEGMENTS:
            name = segment['id']; movie = tmp / f'{name}.mkv'; segments.append(movie)
            command = ['ffmpeg', '-y', '-v', 'error', '-threads', str(args.threads), '-filter_threads', '1']
            if name in check.CAPTURE_COUNTS:
                command += ['-framerate', '30', '-start_number', '0', '-i', str(frames / name / '%05d.png')]
                filters = ['setsar=1']
            elif name == 'leg':
                command += ['-i', str(ROOT / check.LEG)]
                filters = ['scale=1280:720:flags=lanczos', 'setsar=1']
            else:
                command += ['-ss', '1', '-i', str(ROOT / check.E1 / 'hip-frame-e1.mp4')]
                filters = ['fps=30', 'pad=1280:720:160:0:color=0x102130', 'setsar=1']
            if segment.get('title'):
                title = tmp / f'{name}-title.txt'; subtitle = tmp / f'{name}-subtitle.txt'
                title.write_text(segment['title']); subtitle.write_text(segment['subtitle'])
                filters += [
                    'drawbox=x=36:y=580:w=870:h=108:color=0x102130@0.94:t=fill',
                    'drawbox=x=36:y=580:w=870:h=1:color=0x698a98@0.65:t=fill',
                    'drawbox=x=36:y=580:w=4:h=108:color=0xf5b82e:t=fill',
                    f'drawtext=fontfile={font}:textfile={title}:expansion=none:fontsize=36:fontcolor=0xf6f8ff:x=60:y=593',
                    f'drawtext=fontfile={font}:textfile={subtitle}:expansion=none:fontsize=27:fontcolor=0xc1d3e0:x=60:y=642',
                ]
            command += ['-vf', ','.join(filters), '-frames:v', str(segment['frames']), '-r', '30', '-an',
                        '-c:v', 'ffv1', '-level', '3', '-pix_fmt', 'yuv420p', '-threads', str(args.threads), str(movie)]
            print(f'Prepare {name}: {segment["frames"]} frames', flush=True); run(command)
        concat = tmp / 'segments.txt'
        # These names are internal fixed IDs, never shell or user-supplied text.
        concat.write_text(''.join(f"file '{path}'\n" for path in segments))
        common = ['ffmpeg', '-y', '-v', 'error', '-threads', str(args.threads), '-f', 'concat', '-safe', '0', '-i', str(concat),
                  '-an', '-frames:v', '660', '-r', '30', '-pix_fmt', 'yuv420p', '-threads', str(args.threads)]
        h264 = ['-c:v', 'libx264', '-preset', 'slow', '-crf', str(args.crf), '-profile:v', 'high', '-level:v', '3.1',
                '-maxrate', '8M', '-bufsize', '16M', '-g', '60', '-movflags', '+faststart']
        vp9 = ['-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', str(args.vp9_crf), '-deadline', 'good', '-cpu-used', '2',
               '-row-mt', '1', '-tile-columns', '2', '-g', '60']
        print('Encode H.264 and VP9 companions', flush=True)
        run(common + h264 + [str(out / check.MOVIES[0])])
        run(common + vp9 + [str(out / check.MOVIES[1])])
        run(['ffmpeg', '-y', '-v', 'error', '-i', out / check.MOVIES[0], '-vf', "select='eq(n,30)'", '-frames:v', '1',
             '-c:v', 'libwebp', '-quality', '90', '-compression_level', '6', out / check.POSTER])
    shutil.copyfile(frames / 'capture-receipt.json', out / 'capture-receipt.json')
    write(out / 'capture-frames.json', manifest)
    check.require(source_hashes == {name: check.file_sha(ROOT / name) for name in source_hashes}, 'A rendering source changed while encoding')
    outputs = {name: dict(sha256=check.file_sha(out / name), bytes=(out / name).stat().st_size)
               for name in check.MOVIES + [check.POSTER, 'capture-receipt.json', 'capture-frames.json']}
    receipt = dict(schema=1, format=dict(width=1280, height=720, fps=30, frames=660, seconds=22, audio=False),
                   source_revision=check.command(['git', 'rev-parse', 'HEAD']).decode().strip(),
                   source_hashes=source_hashes, segments=check.SEGMENTS, historical_leg=historical,
                   e1=dict(source_start_seconds=1, source_duration_seconds=3, transient_simulation=False,
                           deformation_exaggeration=16, safety_factor=1.63, required=2, baseline_kg=37.5),
                   capture=dict(recipe='tools/capture-highlights.mjs', receipt='capture-receipt.json', frames='capture-frames.json',
                                raw_frames_committed=False, current_model='48-part current turret; interim full-robot body'),
                   encoding=dict(ffmpeg=check.command(['ffmpeg', '-version']).decode().splitlines()[0],
                                 h264=h264, vp9=vp9, intermediate='FFV1 yuv420p; both encodings from identical segments',
                                 poster_frame=30, font='designer/kit/vendor/fonts/inter.woff2'),
                   limitations=['Browser motion is illustrative, with integrated live projectiles; not a new full-robot physics result.',
                                'Leg footage retains its historical 16.25 kg / 48.1 V / BotWheel / 60 N m baseline.',
                                'E1 is static load scaling of the recorded study (cad-agent v0.6.0 record), with a failed strength target; not transient dynamics.',
                                'No new solver runs. Reproducible recipe and source identity, not a promise of cross-host identical encoded bytes.'],
                   outputs=outputs)
    write(out / 'receipt.json', receipt)
    print(json.dumps(check.validate(out, frames), indent=2))


if __name__ == '__main__':
    main()
