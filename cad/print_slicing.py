"""Capture and execute exact Bambu settings; no CAD imports or physical claims."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
import subprocess

from print_provenance import digest


def engine_identity(executable: str) -> dict:
    """Hash the executable, and the actual installed payload behind Snap's launcher.

    This identifies the slicer build, not every shared library/runtime dependency.
    Call again after slicing to reject an installation changed during the run.
    """
    exe = Path(executable)
    result = {'launcher': exe.name, 'executable_sha256': digest(exe.resolve())}
    if exe.parent == Path('/snap/bin'):
        if exe.name != 'bambu-studio':
            raise ValueError('Unsupported Snap slicer launcher')
        revision = Path('/snap/bambu-studio/current').resolve(strict=True)
        result.update(snap_revision=revision.name,
                      snap_manifest_sha256=digest(revision / 'meta/snap.yaml'),
                      slicer_payload_sha256=digest(revision / 'opt/bambu-studio/bin/bambu-studio'))
    return result


def _profile(root: Path, kind: str, name: str) -> tuple[dict, dict]:
    """Resolve Bambu parent → ordered includes → explicit child settings.

    P1S machine G-code lives in included templates in recent Bambu profiles.
    Following only ``inherits`` silently selects the generic 205°C startup.
    """
    index = {}
    for path in sorted((root / kind).glob('*.json')):
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f'Profile path escapes root: {path}')
        raw = path.read_bytes()
        data = json.loads(raw)
        key = data.get('name')
        if key in index:
            raise ValueError(f'Duplicate {kind} profile: {key}')
        if key:
            index[key] = (path, raw, data)
    active, files = set(), {}

    def resolve(current):
        if not isinstance(current, str) or not current or '/' in current or '\\' in current or current in ('.', '..'):
            raise ValueError(f'Invalid {kind} profile reference: {current!r}')
        if current in active:
            raise ValueError(f'Cyclic {kind} profile inheritance/include: {current}')
        if current not in index:
            raise ValueError(f'Missing {kind} profile: {current}')
        active.add(current)
        path, raw, data = index[current]
        files[path.relative_to(root).as_posix()] = hashlib.sha256(raw).hexdigest()
        flat = resolve(data['inherits']) if data.get('inherits') else {}
        includes = data.get('include', [])
        if isinstance(includes, str):
            includes = [includes]
        if not isinstance(includes, list):
            raise ValueError(f'Invalid {kind} include list: {current}')
        for included in includes:
            flat.update(resolve(included))
        flat.update({k: v for k, v in data.items() if k not in ('inherits', 'include')})
        active.remove(current)
        return flat

    flat = resolve(name)
    flat.update(name=name, **{'from': 'system'})
    sid = {'machine': 'printer_settings_id', 'process': 'print_settings_id', 'filament': 'filament_settings_id'}[kind]
    flat[sid] = [name] if kind == 'filament' else name
    return flat, files


def capture(printer: str, process: str, filament: str, overrides: dict) -> dict:
    from cadagent import slicer
    exe = slicer.executable()
    if not exe:
        raise RuntimeError('Bambu Studio is required for sliced estimates; use --no-slice for geometry only')
    root = slicer.profile_root()
    profiles, files = {}, {}
    for kind, name in [('machine', printer), ('process', process), ('filament', filament)]:
        profiles[kind], used = _profile(root, kind, name)
        files.update(used)
    proc = profiles['process']
    for key, value in overrides.items():
        proc[key] = value if isinstance(value, list) or not isinstance(proc.get(key), list) else [str(value)] * len(proc[key])
    return {'names': {'printer': printer, 'process': process, 'filament': filament},
            'overrides': overrides, 'profile_files_sha256': files, 'effective_profiles': profiles,
            'engine': engine_identity(exe)}


def current(identity: dict) -> bool:
    try:
        return capture(**identity['names'], overrides=identity['overrides']) == identity
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, ImportError):
        return False


def run(model: Path, work: Path, identity: dict) -> dict:
    """Run with the captured effective profiles, never re-read mutable named profiles."""
    from cadagent import slicer
    if not current(identity):
        raise ValueError('Slicer inputs changed before slicing')
    work.mkdir(parents=True, exist_ok=False)
    paths = {}
    for kind, profile in identity['effective_profiles'].items():
        paths[kind] = work / f'{kind}.json'
        paths[kind].write_text(json.dumps(profile, indent=1))
    output = work / 'out'
    output.mkdir()
    cmd = [slicer.executable(), '--slice', '0', '--arrange', '1', '--orient', '0',
           '--load-settings', f"{paths['machine']};{paths['process']}", '--load-filaments', str(paths['filament']),
           '--outputdir', str(output), '--export-3mf', 'sliced.3mf', str(model.resolve())]
    completed = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    (work / 'slicer.log').write_text(completed.stdout + completed.stderr)
    (work / 'exit-code.json').write_text(json.dumps({'exit_code': completed.returncode}))
    if not current(identity):
        raise ValueError('Slicer inputs changed during slicing')
    # The command consumes these exact files; retain their effective JSON in print.json.
    if any(json.loads(paths[k].read_text()) != v for k, v in identity['effective_profiles'].items()):
        raise ValueError('Captured slicer settings changed during slicing')
    result = slicer._read_result(output)
    error = result.get('error')
    error = None if not error or str(error).strip().rstrip('.').lower() == 'success' else error
    return {'grams': result.get('grams'), 'minutes': round(result.get('seconds', 0) / 60, 1),
            'filament_m': result.get('filament_m'), 'error': error,
            'exit_code': completed.returncode, 'return_code': result.get('return_code'),
            'log_tail': (completed.stdout + completed.stderr)[-400:] or None}
