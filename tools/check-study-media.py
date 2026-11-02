#!/usr/bin/env python3
"""Verify the shipped E1 visualization of the recorded study, without CAD or a solver."""
import array
import base64
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MEDIA = 'exports/leg/fea/hip-frame-e1-media/'
SUMMARY = 'exports/leg/fea/summary.json'
FINER = 'research/leg-preprint/evidence/hip-frame-print-ready.json'
# The recorded E1 gate (cad-agent v0.6.0, the print-ready rerun of #148, issue #29) and its solved surface; review the
# media when they change.
GATE_SF, VERTICES, TRIANGLES = 1.60, 25195, 50478


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


@lru_cache(maxsize=None)
def historical_hash(revision, path):
    return digest(subprocess.check_output(['git', 'show', f'{revision}:{path}'], cwd=ROOT))


def moving_model(first, loaded):
    require(len(first) == len(loaded) and len(first) > 0, 'Missing decoded model region')
    delta = [abs(a - b) for a, b in zip(first, loaded)]
    average = sum(delta) / len(delta)
    changed = sum(value > 20 for value in delta) / len(delta)
    require(average > 5 and changed > .05, 'Frozen model framebuffer: duration is not motion')
    return {'mean_channel_difference': average, 'channels_changed_over_20': changed}


def validate(root=ROOT, decode=True):
    root = Path(root)
    read = lambda path: json.loads((root / path).read_text())
    field_receipt = read(MEDIA + 'field-receipt.json')
    video_receipt = read(MEDIA + 'video-receipt.json')
    index = read('exports/leg/fea/media.json')['cases']['hip_frame/E1']
    baseline = next(row for row in read(SUMMARY)['results'] if (row['part'], row['case']) == ('hip_frame', 'E1'))
    require(baseline == field_receipt['baseline'], 'Published report differs from reproduced baseline')
    require(baseline['safety_factor'] == GATE_SF and baseline['target'] == 2 and baseline['ok'] is False,
            'E1 strength gate must remain below target')
    require(field_receipt['transient_simulation'] is False and field_receipt['qualified_for_manufacture'] is False,
            'Static evidence cannot qualify hardware')
    # Historical CAD is compared to the producer Git revision, not silently
    # reclassified as the current mechanical design after later CAD changes.
    for path, sha in field_receipt['source_hashes'].items():
        require(historical_hash(field_receipt['source_revision'], path) == sha, f'Producer input mismatch: {path}')
    require(digest((root / SUMMARY).read_bytes()) == field_receipt['source_hashes'][SUMMARY], 'Stale report binding')
    require(field_receipt['fields'] == MEDIA + 'hip_frame-E1.json', 'Unexpected field path')
    fields = read(field_receipt['fields'])
    require(digest((root / field_receipt['fields']).read_bytes()) == field_receipt['fields_sha256'], 'Field bytes changed')
    require(fields['units']['length'] == 'mm' and fields['units']['stress'] == 'MPa', 'Wrong field units')
    require(fields['name'] == 'hip_frame E1' and fields['result']['safety_factor'] == baseline['safety_factor'], 'Wrong solved case')
    surface = fields['surface']
    require((surface['vertices'], surface['triangles']) == (VERTICES, TRIANGLES), 'Surface topology changed')
    decoded = {}
    for key, dtype, shape, code in [('positions','float32',[VERTICES,3],'f'),('displacement','float32',[VERTICES,3],'f'),
                                   ('index','uint32',[TRIANGLES,3],'I'),('tri_von_mises','float32',[TRIANGLES],'f')]:
        item = surface[key]
        require(item['dtype'] == dtype and item['shape'] == shape, f'Invalid {key} layout')
        values = array.array(code, base64.b64decode(item['b64'], validate=True))
        if sys.byteorder != 'little': values.byteswap()
        require(len(values) == math.prod(shape) and all(math.isfinite(v) for v in values), f'Invalid {key} values')
        decoded[key] = values
    require(max(decoded['index']) < surface['vertices'], 'Triangle refers outside surface')
    displacements = decoded['displacement']
    maximum = max(math.sqrt(sum(value * value for value in displacements[i:i+3])) for i in range(0, len(displacements), 3))
    require(abs(maximum - baseline['max_displacement_mm']) < .0001, 'Displacement field differs from report')
    for key in ('max_displacement_mm', 'von_mises_design_mpa', 'safety_factor', 'target', 'ok'):
        require(field_receipt['reproduced'][key] == baseline[key], f'Reproduction differs: {key}')
    expected_inputs = {'tools/render-hip-frame-e1.py', MEDIA + 'field-receipt.json', field_receipt['fields'], SUMMARY, FINER}
    require(set(video_receipt['source_hashes']) == expected_inputs, 'Incomplete renderer inputs')
    for path, sha in video_receipt['source_hashes'].items():
        require(digest((root / path).read_bytes()) == sha, f'Stale animation source: {path}')
        require(historical_hash(video_receipt['source_revision'], path) == sha, f'Uncommitted animation source: {path}')
    expected_outputs = {MEDIA + 'hip-frame-e1.mp4', MEDIA + 'hip-frame-e1.webm', MEDIA + 'hip-frame-e1-poster.png'}
    require(set(video_receipt['outputs']) == expected_outputs, 'Incomplete rendered artifacts')
    for path, sha in video_receipt['outputs'].items():
        require(digest((root / path).read_bytes()) == sha, f'Rendered artifact changed: {path}')
    require(index['video'] == MEDIA + 'hip-frame-e1.mp4' and index['poster'] == MEDIA + 'hip-frame-e1-poster.png'
            and index['webm'] == MEDIA + 'hip-frame-e1.webm' and index['fields'] == field_receipt['fields']
            and index['receipt'] == MEDIA + 'video-receipt.json', 'Media index paths differ')
    require(index['kind'] == 'static-deformation' and index['transient_simulation'] is False
            and video_receipt['transient_simulation'] is False, 'Static evidence mislabeled')
    for key, value in index['recorded'].items(): require(value == baseline[key], f'Media index differs: {key}')
    require(set(index['recorded']) == {'safety_factor','target','max_displacement_mm','von_mises_design_mpa','load_from'}, 'Incomplete report identity')
    timeline = video_receipt['timeline']
    require(len(timeline) == 288 and index['duration_seconds'] == 12, 'Wrong presentation duration')
    for i, frame in enumerate(timeline):
        require(frame['frame'] == i and frame['presentation_seconds'] == i / 24, 'Broken presentation timeline')
        factor = frame['load_factor']
        require(0 <= factor <= 1 and abs(frame['max_physical_displacement_mm'] - maximum * factor) < .000001,
                'Presentation extrapolates the solved load or changes physical displacement')
    require(timeline[0]['load_factor'] == 0 and timeline[144]['load_factor'] == 1 and timeline[-1]['load_factor'] == 0, 'Missing load/unload loop')
    result = {'historical_source': field_receipt['source_revision'], 'safety_factor': GATE_SF, 'required': 2,
              'vertices': surface['vertices'], 'triangles': surface['triangles']}
    if decode:
        movie = root / index['video']
        probe = json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
            '-show_entries','stream=codec_name,width,height,pix_fmt,avg_frame_rate,nb_read_frames,duration','-of','json',str(movie)]))['streams'][0]
        require(probe == video_receipt['ffprobe'], 'Decoded movie differs from receipt')
        require(probe['codec_name'] == 'h264' and probe['pix_fmt'] == 'yuv420p' and probe['width'] == 960 and probe['height'] == 720
                and probe['avg_frame_rate'] == '24/1' and int(probe['nb_read_frames']) == 288 and float(probe['duration']) == 12, 'Movie is not the expected playable loop')
        codec = json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
            '-show_entries','stream=profile,level','-of','json',str(movie)]))['streams'][0]
        require(codec['profile'] == 'High' and codec['level'] == 31, 'Update the browser AVC capability string to match the encoded profile/level')
        subprocess.run(['ffmpeg','-v','error','-i',str(movie),'-f','null','-'],check=True)
        # Frames 0 and 144 have the same camera direction. Exclude all captions:
        # a changing timestamp or orbit alone must not rescue a frozen field.
        pixels = subprocess.check_output(['ffmpeg','-v','error','-i',str(movie),'-vf',
            "select='eq(n,0)+eq(n,144)',crop=590:360:200:130",'-fps_mode','vfr','-f','rawvideo','-pix_fmt','rgb24','-'])
        size = 590 * 360 * 3
        require(len(pixels) == size * 2, 'Missing independent decoded samples')
        result.update(moving_model(pixels[:size], pixels[size:])); result['decoded_frames'] = 288; result['seconds'] = 12
        webm = root / index['webm']
        webm_probe = json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
            '-show_entries','stream=codec_name,width,height,pix_fmt,avg_frame_rate,nb_read_frames:format=duration','-of','json',str(webm)]))
        require(webm_probe == video_receipt['webm_ffprobe'], 'VP9 companion differs from receipt')
        stream = webm_probe['streams'][0]
        require(stream['codec_name'] == 'vp9' and stream['pix_fmt'] == 'yuv420p' and stream['width'] == 960
                and stream['height'] == 720 and stream['avg_frame_rate'] == '24/1' and int(stream['nb_read_frames']) == 288
                and float(webm_probe['format']['duration']) == 12, 'VP9 companion is not the expected playable loop')
        subprocess.run(['ffmpeg','-v','error','-i',str(webm),'-f','null','-'],check=True)
        vp9_pixels = subprocess.check_output(['ffmpeg','-v','error','-i',str(webm),'-vf',
            "select='eq(n,0)+eq(n,144)',crop=590:360:200:130",'-fps_mode','vfr','-f','rawvideo','-pix_fmt','rgb24','-'])
        require(len(vp9_pixels) == size * 2, 'Missing VP9 decoded samples')
        result['vp9_motion'] = moving_model(vp9_pixels[:size], vp9_pixels[size:])
        mean_codec_difference = sum(abs(a-b) for a,b in zip(pixels,vp9_pixels)) / len(pixels)
        require(mean_codec_difference < 5, 'VP9 scene differs from H.264 companion')
        result['mean_codec_difference'] = mean_codec_difference
    return result


if __name__ == '__main__':
    print(json.dumps(validate(), indent=2))
