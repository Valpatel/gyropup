#!/usr/bin/env python3
"""Reproduce only the recorded hip-frame E1 static field on the CAD compute host.

No redesign, transient dynamics, other-part solve, or manufacturing qualification.
The published baseline summary remains unchanged. Its load-sharing result is an
explicit input to the same individual-part setup used by cad/leg_studies.py.
"""
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'exports/leg/fea/hip-frame-e1-media'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes():
    paths = {p for directory in ('cad', 'catalog', 'designs') for p in (ROOT / directory).rglob('*')
             if p.is_file() and p.suffix in ('.py', '.json')}
    paths.update(ROOT / p for p in ('sim/leg_rig.py', 'sim/leg_control.py',
        'exports/leg/rig-results.json', 'exports/leg/fea/summary.json', 'tools/export-hip-frame-e1.py'))
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(paths)}


def main():
    if os.environ.get('GYROPUP_CAD_PARAMS'):
        raise ValueError('This reproduction requires the committed default parameters')
    before = source_hashes()
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    for path, sha in before.items():
        committed = subprocess.check_output(['git', 'show', f'{revision}:{path}'], cwd=ROOT)
        if hashlib.sha256(committed).hexdigest() != sha:
            raise ValueError(f'Input differs from committed revision: {path}')
    baseline = json.loads((ROOT / 'exports/leg/fea/summary.json').read_text())
    original = next(r for r in baseline['results'] if r['part'] == 'hip_frame' and r['case'] == 'E1')
    if original['safety_factor'] != 1.65 or original['target'] != 2.0 or original['ok'] is not False:
        raise ValueError('Recorded E1 case changed; review the visualization baseline explicitly')
    OUT.mkdir(parents=True, exist_ok=True)
    # leg_studies reads load-sharing coefficients from OUT/summary.json. Preserve
    # that input in the isolated output directory without replacing the baseline.
    shutil.copyfile(ROOT / 'exports/leg/fea/summary.json', OUT / 'summary.json')
    sys.path[:0] = [str(ROOT / 'cad'), str(ROOT)]
    # The isolated ARM runner also requires matching libcrypto/libssl in its
    # process-local LD_PRELOAD. Import order alone is insufficient: hashlib can
    # load system OpenSSL before this point. Record actual mapped binary hashes.
    import gmsh  # noqa: F401
    import leg_studies
    import cadagent
    runtime = sorted({Path(line.split()[-1]) for line in Path('/proc/self/maps').read_text().splitlines()
                      if any(name in line for name in ('libgmsh', 'libcrypto.so', 'libssl.so', 'libs2n'))})
    runtime_hashes = [{'name': p.name, 'sha256': digest(p)} for p in runtime]
    toolkit_root = Path(cadagent.__file__).parent
    toolkit = {p.relative_to(toolkit_root).as_posix(): digest(p) for p in sorted(toolkit_root.rglob('*.py'))}
    leg_studies.OUT = OUT
    result = leg_studies.run(4.0, anim=False, only=['hip_frame'], only_cases=['E1'], viewer=True)
    if len(result['results']) != 1:
        raise ValueError('Bounded run must produce exactly one recorded part/case')
    solved = result['results'][0]
    if solved['safety_factor'] != original['safety_factor'] or solved['target'] != original['target'] or solved['ok'] is not False:
        raise ValueError(f'Reproduced E1 gate differs: {solved["safety_factor"]}; do not relabel it as the recorded case')
    for key in ('max_displacement_mm', 'von_mises_design_mpa'):
        if abs(solved[key] - original[key]) > max(abs(original[key]) * .01, .0001):
            raise ValueError(f'Reproduced {key} differs by more than 1 percent')
    if source_hashes() != before:
        raise ValueError('Source inputs changed during the solve')
    if toolkit != {p.relative_to(toolkit_root).as_posix(): digest(p) for p in sorted(toolkit_root.rglob('*.py'))}:
        raise ValueError('Toolkit sources changed during the solve')
    fields = OUT / 'hip_frame-E1.json'
    receipt = {'schema': 1, 'purpose': 'Reproduced static E1 field for an explanatory deformation animation',
        'source_revision': revision, 'source_hashes': before, 'toolkit_sources_sha256': toolkit,
        'versions': {name: version(name) for name in ('cad-agent', 'cadquery', 'cadquery-ocp', 'numpy', 'scikit-fem', 'gmsh')},
        'mapped_runtime_libraries': runtime_hashes,
        'baseline': original, 'reproduced': solved, 'fields': fields.relative_to(ROOT).as_posix(),
        'fields_sha256': digest(fields), 'transient_simulation': False, 'qualified_for_manufacture': False,
        'limitations': 'Linear elastic, small deflection, isotropic weak-direction material; recorded 37.5 kg robot load case. '
                       'No contact, preload, buckling, crack propagation or validation of the future 100 lb target.'}
    (OUT / 'field-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    # The copied summary was only an input to the narrow solve, not a new report.
    (OUT / 'summary.json').unlink()
    print('PASS: one static E1 field reproduced; SF1.65 remains below target2.0.', flush=True)


if __name__ == '__main__':
    main()
