#!/usr/bin/env python3
"""Export only current presentation attachments; never rebuild the archived rig.

The adapter is a rigid reframe of our pinned, published CAD solid. The screws
are the existing project-authored stock-dimension envelopes, not vendor CAD.
Run in an isolated CAD environment; no full robot build or simulation required.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = '31908a86a782c440e47beb0f502e3ef0fd944aa2'
ADAPTER = 'exports/sim/v2/rig/body__adapter_f_l.stl'
ADAPTER_SHA = '2cd56998c321be35f9f75a8191bbc33903bd75ce5f74bc5906e19b7085c666c3'
# Independently inspected legacy motor-axis x and AO interface plane y: the
# adapter's outer face is y=85.3, less its CAD 3 mm locating spigot = 82.3.
LEG_ORIGIN_MM = (75.0, 82.3, 0.0)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def generate(output):
    sys.path.insert(0, str(ROOT / 'cad'))
    import cadquery as cq
    import fivebar as fb
    import gmi

    raw = subprocess.check_output(['git', 'show', f'{SOURCE}:{ADAPTER}'], cwd=ROOT)
    if sha(raw) != ADAPTER_SHA:
        raise ValueError('Pinned adapter geometry changed')
    _, info = gmi.output_adapter(fb.MOTOR, 'L')
    if abs(info['z_face'] - 24.6) > 1e-9 or abs(gmi.STD['AO-L']['spigot_h'] - 3) > 1e-9:
        raise ValueError('Current screw seats no longer match the archived adapter; review the interface')
    output.mkdir(parents=True, exist_ok=True)
    data = bytearray(raw)
    for t in range(struct.unpack_from('<I', data, 80)[0]):
        for v in range(3):
            offset = 84 + t * 50 + 12 + v * 12
            point = struct.unpack_from('<3f', data, offset)
            struct.pack_into('<3f', data, offset, *[x - o for x, o in zip(point, LEG_ORIGIN_MM)])
    (output / 'output_adapter.stl').write_bytes(data)
    parts = [{'name': 'output_adapter', 'file': 'output_adapter.stl', 'color': '#c9ced6',
              'catalog_key': 'output_adapter', 'geometry': 'project CAD; rigid reframe only'}]
    screws = fb.upper_output_screws()
    if len(screws) != 9:
        raise ValueError('Expected nine output screws per RS-04 adapter')
    for name, shape in screws:
        cq.exporters.export(shape, str(output / f'{name}.stl'), tolerance=.1, angularTolerance=.2)
        parts.append({'name': name, 'file': f'{name}.stl', 'color': '#454952', 'catalog_key': 'screw_m5x25',
                      'geometry': 'project-authored cylindrical envelope; head/socket/thread detail omitted'})
    for part in parts:
        part['sha256'] = sha((output / part['file']).read_bytes())
    source_files = ['cad/fivebar.py', 'cad/gmi.py', 'cad/interfaces.json', 'catalog/interfaces.json', 'catalog/hardware.json']
    manifest = {'schema_version': 1, 'units': 'mm', 'frame': 'upper-link local; x along link, y outboard, z up',
                'source_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'source_hashes': {f: sha((ROOT / f).read_bytes()) for f in source_files},
                'adapter_source': {'revision': SOURCE, 'file': ADAPTER, 'sha256': ADAPTER_SHA, 'translation_mm': [-v for v in LEG_ORIGIN_MM]},
                'license_basis': 'Project-authored geometry only; no supplier STEP or derived supplier mesh is redistributed.',
                'limits': 'Presentation ownership only. Screw envelopes are not evidence of socket access, threads, fit, loads or hardware safety. Archived rig/physics remain unchanged.',
                'parts': parts}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Exported {len(parts)} local meshes: one adapter and nine screw envelopes; four upper-link instances each.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'exports/sim/v2/leg-attachments')
    generate(parser.parse_args().output)
