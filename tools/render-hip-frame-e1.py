#!/usr/bin/env python3
"""Render a loop from the reproduced linear-static field; never run a solver."""
import base64
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'exports/leg/fea/hip-frame-e1-media'
FPS, SECONDS, WIDTH, HEIGHT = 24, 12, 960, 720


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_factor(t):
    if t < 1: return 0.
    if t < 4: return .5 - .5 * math.cos(math.pi * (t - 1) / 3)
    if t < 8: return 1.
    if t < 11: return .5 + .5 * math.cos(math.pi * (t - 8) / 3)
    return 0.


def main():
    import numpy as np
    import pyvista as pv
    from matplotlib import colormaps
    receipt = json.loads((OUT / 'field-receipt.json').read_text())
    fields = ROOT / receipt['fields']
    if digest(fields) != receipt['fields_sha256']:
        raise ValueError('Solved surface differs from its source receipt')
    if digest(ROOT / 'exports/leg/fea/summary.json') != receipt['source_hashes']['exports/leg/fea/summary.json']:
        raise ValueError('Published structural report changed; review the animation baseline')
    source_hashes = {str(p.relative_to(ROOT)): digest(p) for p in
                     (Path(__file__), OUT / 'field-receipt.json', fields, ROOT / 'exports/leg/fea/summary.json')}
    data = json.loads(fields.read_text())
    def array(key):
        item = data['surface'][key]
        return np.frombuffer(base64.b64decode(item['b64']), dtype=item['dtype']).reshape(item['shape']).copy()
    points, displacement, triangles = array('positions'), array('displacement'), array('index')
    stress, excluded = array('tri_von_mises').ravel(), array('tri_flags').ravel().astype(bool)
    if not all(np.isfinite(a).all() for a in (points, displacement, stress)) or len(triangles) != len(stress):
        raise ValueError('Invalid static surface fields')
    baseline = receipt['baseline']
    if baseline['ok'] is not False or baseline['safety_factor'] != 1.65 or baseline['target'] != 2.0:
        raise ValueError('Expected below-target E1 baseline')
    maximum = float(data['max_displacement_mm'])
    extent = float(np.ptp(points, axis=0).max())
    exaggeration = max(1, round(.075 * extent / maximum))
    faces = np.column_stack([np.full(len(triangles), 3), triangles]).ravel()
    mesh = pv.PolyData(points.copy(), faces)
    mesh.cell_data['stress_rgb'] = np.zeros((len(triangles), 3), dtype=np.uint8)
    plot = pv.Plotter(off_screen=True, window_size=(WIDTH, HEIGHT), lighting='three lights')
    plot.set_background('#102130')
    plot.enable_parallel_projection()
    plot.enable_anti_aliasing('ssaa')
    plot.add_mesh(mesh, scalars='stress_rgb', rgb=True, show_scalar_bar=False,
                  smooth_shading=False, ambient=.45, diffuse=.6, specular=.2)
    ghost = pv.PolyData(points.copy(), faces).extract_feature_edges(feature_angle=45,
        boundary_edges=False, non_manifold_edges=False, manifold_edges=False)
    plot.add_mesh(ghost, color='#a7bdc9', opacity=.22, line_width=1)
    centre = (points.min(axis=0) + points.max(axis=0)) / 2
    force_actors = []
    for force in (load for load in data['loads'] if load['kind'] == 'force'):
        actor = plot.add_mesh(pv.Arrow(direction=force['dir'], tip_length=.23, tip_radius=.10,
                                      shaft_radius=.035, scale=1), color='#75f4e8', ambient=.6)
        force_actors.append((actor, force))
    plot.add_text('GYROPUP / STRUCTURAL LAB', position=(28, 680), font_size=12, color='#83b8ce', font='arial')
    plot.add_text('HIP FRAME  /  E1', position=(28, 625), font_size=28, color='#f6f8ff', font='arial')
    plot.add_text('STATIC DEFORMATION', position=(570, 635), font_size=14, color='#75f4e8', font='arial')
    plot.add_text('SF 1.65 / REQUIRED 2.00  —  BELOW TARGET', position=(28, 146), font_size=15,
                  color='#ffbf69', font='arial')
    readout = plot.add_text('', position=(28, 92), font_size=14, color='#f6f8ff', font='arial')
    plot.add_text(f'Deformation ×{exaggeration}  •  gray ghost = unloaded shape', position=(28, 56),
                  font_size=13, color='#c1d3e0', font='arial')
    plot.add_text('37.5 kg recorded baseline  •  static load scaling, not physical elapsed time',
                  position=(28, 22), font_size=12, color='#c1d3e0', font='arial')
    movie = OUT / 'hip-frame-e1.mp4'
    command = ['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{WIDTH}x{HEIGHT}',
               '-r', str(FPS), '-i', '-', '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
               '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(movie)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    timeline = []
    try:
        for frame in range(FPS * SECONDS):
            t = frame / FPS
            factor = load_factor(t)
            moved = points + displacement * factor * exaggeration
            mesh.points = moved
            colour = (colormaps['turbo'](np.clip(stress * factor / baseline['von_mises_design_mpa'], 0, 1))[:, :3] * 255).astype(np.uint8)
            colour[excluded] = [126, 145, 161]
            mesh.cell_data['stress_rgb'] = colour
            angle = math.radians(-60 + 18 * math.sin(2 * math.pi * t / SECONDS))
            elevation = math.radians(22 + 4 * math.sin(2 * math.pi * t / SECONDS))
            direction = np.array([math.cos(elevation) * math.cos(angle), math.cos(elevation) * math.sin(angle), math.sin(elevation)])
            # Fixed fit and gentle closed camera loop; no simulated camera physics.
            plot.camera_position = [centre + direction * extent * 3, centre, (0, 0, 1)]
            plot.camera.parallel_scale = extent * .76
            plot.camera.SetWindowCenter(0, -.13)
            for actor, force in force_actors:
                origin = np.array(force['origin']) + np.array(force['disp']) * factor * exaggeration
                length = extent * .15 * factor
                actor.SetPosition(*(origin - np.array(force['dir']) * length))
                actor.SetScale(max(length, .00001)); actor.SetVisibility(factor > .01)
            readout.SetInput(f'LOAD {factor:4.0%}    DEFLECTION {maximum * factor:.3f} mm\nPEAK STRESS {baseline["von_mises_design_mpa"] * factor:.2f} MPa')
            plot.reset_camera_clipping_range()
            # screenshot() only renders the first time; explicitly redraw every
            # updated mesh, camera and text actor before reading the framebuffer.
            plot.render()
            image = plot.screenshot(return_img=True)
            process.stdin.write(np.ascontiguousarray(image[:, :, :3]).tobytes())
            if frame == 6 * FPS:
                plot.screenshot(str(OUT / 'hip-frame-e1-poster.png'))
            timeline.append({'frame': frame, 'presentation_seconds': t, 'load_factor': factor,
                             'max_physical_displacement_mm': maximum * factor})
        process.stdin.close()
        if process.wait() != 0: raise RuntimeError('Video encoder failed')
    finally:
        plot.close()
        if process.poll() is None:
            process.stdin.close(); process.terminate(); process.wait()
    if source_hashes != {name: digest(ROOT / name) for name in source_hashes}:
        raise ValueError('Animation source changed during rendering')
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
        '-show_entries', 'stream=codec_name,width,height,pix_fmt,avg_frame_rate,nb_read_frames,duration', '-of', 'json', str(movie)], text=True))['streams'][0]
    if abs(float(probe['duration']) - SECONDS) > .05 or int(probe['nb_read_frames']) != FPS * SECONDS:
        raise ValueError('Encoded movie duration/frame count differs from its timeline')
    # The pinned open-source Chromium build cannot decode H.264. Preserve the
    # same presentation in VP9, without a second solve or altered load history.
    webm = OUT / 'hip-frame-e1.webm'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(movie), '-an', '-c:v', 'libvpx-vp9',
                    '-b:v', '0', '-crf', '30', '-cpu-used', '4', '-row-mt', '1', str(webm)], check=True)
    webm_probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
        '-show_entries', 'stream=codec_name,width,height,pix_fmt,avg_frame_rate,nb_read_frames:format=duration', '-of', 'json', str(webm)], text=True))
    if abs(float(webm_probe['format']['duration']) - SECONDS) > .05 or int(webm_probe['streams'][0]['nb_read_frames']) != FPS * SECONDS:
        raise ValueError('VP9 companion differs from the presentation timeline')
    # Decode both encodings completely before publishing.
    for video in (movie, webm):
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'null', '-'], check=True)
    files = {p.relative_to(ROOT).as_posix(): digest(p) for p in (movie, webm, OUT / 'hip-frame-e1-poster.png')}
    result = {'schema': 1, 'source_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source_hashes': source_hashes, 'outputs': files, 'ffprobe': probe, 'webm_ffprobe': webm_probe, 'decoded_all_frames': True,
        'renderer': {'pyvista': pv.__version__, 'numpy': np.__version__, 'fps': FPS, 'duration_seconds': SECONDS,
                     'deformation_exaggeration': exaggeration, 'load_factor_range': [0, 1]},
        'timeline': timeline, 'transient_simulation': False, 'qualification': 'Presentation of the reproduced static E1 field; strength gate remains failed.'}
    (OUT / 'video-receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    index = {'schema': 1, 'cases': {'hip_frame/E1': {'kind': 'static-deformation', 'transient_simulation': False,
        'video': movie.relative_to(ROOT).as_posix(), 'webm': webm.relative_to(ROOT).as_posix(),
        'poster': (OUT / 'hip-frame-e1-poster.png').relative_to(ROOT).as_posix(),
        'fields': receipt['fields'], 'duration_seconds': SECONDS,
        'receipt': (OUT / 'video-receipt.json').relative_to(ROOT).as_posix(),
        'recorded': {k: baseline[k] for k in ('safety_factor', 'target', 'max_displacement_mm', 'von_mises_design_mpa', 'load_from')}}}}
    (ROOT / 'exports/leg/fea/media.json').write_text(json.dumps(index, indent=2) + '\n')
    print(f'PASS: {SECONDS}s / {FPS * SECONDS} decoded frames; static field scaling only, E1 gate remains below target.')


if __name__ == '__main__':
    main()
