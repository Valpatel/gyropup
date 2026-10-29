#!/usr/bin/env python3
"""Regenerate the published legacy scene in corrected joint frames, without a CAD kernel.

This is a rigid coordinate change, not a shape/design change. Source meshes come
from the pinned Git snapshot; reruns never translate already-corrected meshes.
The full CAD exporter implements the same corrected frame convention for future
design builds. Manufacturing exports and historical physical reports are untouched.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = '3eb32ba649a2b0b66dd80c4a2dfb3179b0697f20'
PREFIX = 'exports/sim/turret_box/'
MANIFEST_SHA = '3500d030746bd3015e5327c00ec7ac0756189d6dfe7585afe29fef35f9c8e19f'
# Independent datum from cad/turret.py Geometry.tilt_x and pose_shape at SOURCE.
TILT_X = 48.0


def original(name):
    return subprocess.check_output(['git', 'show', f'{SOURCE}:{PREFIX}{name}'], cwd=ROOT)


def regenerate(output):
    raw = original('manifest.json')
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA:
        raise ValueError('Unexpected legacy manifest; do not infer a datum from mesh bounds')
    man = json.loads(raw)
    output.mkdir(parents=True, exist_ok=True)
    rotating = {'dial', 'wheel_l', 'wheel_r', 'flap'}
    for part in man['parts']:
        data = bytearray(original(part['file']))
        if part['group'] in rotating:
            count, = struct.unpack_from('<I', data, 80)
            if len(data) != 84 + 50 * count:
                raise ValueError(f'Invalid binary STL: {part["file"]}')
            for triangle in range(count):
                for vertex in range(3):
                    pos = 84 + triangle * 50 + 12 + vertex * 12
                    x, = struct.unpack_from('<f', data, pos)
                    struct.pack_into('<f', data, pos, x + TILT_X)
            for i in (0, 3):
                part['bbox'][i] = round(part['bbox'][i] + TILT_X, 1)
        if part['part'] in {'feed_motor', 'cartridge_body', 'barrel', 'laser', 'cradle'} and 'anchor' in part:
            part['anchor'][0] = round(part['anchor'][0] - TILT_X, 1)
        part['sha256'] = hashlib.sha256(data).hexdigest()
        (output / part['file']).write_bytes(data)
    for group in rotating:
        man['pivots'][group][0] -= TILT_X
    for point in [*man['ball_path'], *man['pile'], man['muzzle'], man['laser']]:
        point[0] = round(point[0] - TILT_X, 2)
    # CAD GATES.x=(22,82) from the barrel shoulder, not the old display's (30,80).
    man['ball_path'][17][0] -= 8
    man['ball_path'][18][0] += 2
    for step in man['journey']:
        if step['focus'] is not None:
            step['focus'][0] = round(step['focus'][0] - TILT_X, 1)
    man['scene_frame_version'] = 2
    (output / 'manifest.json').write_text(json.dumps(man, indent=1) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / PREFIX)
    regenerate(parser.parse_args().output)
