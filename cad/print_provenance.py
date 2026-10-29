"""Bind print meshes to their generating inputs; identity is not fabrication approval.

Conservatively invalidate on any CAD/config/catalogue change. Reports and website
edits do not invalidate geometry. Keep this module free of CAD-kernel imports so
packaging can reject stale input before loading a mesh or touching output files.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def snapshot(root: Path) -> dict:
    files = sorted({p for folder in ('cad', 'catalog', 'designs')
                    for p in (root / folder).rglob('*') if p.is_file() and p.suffix in ('.py', '.json')})
    inputs = {p.relative_to(root).as_posix(): digest(p) for p in files}
    override = os.environ.get('GYROPUP_CAD_PARAMS')
    # Record the effective optional parameter file, never its private absolute path.
    parameters = digest(Path(override)) if override else None
    versions = {}
    for name in ('cad-agent', 'cadquery', 'cadquery-ocp', 'numpy'):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    toolkit = {}
    spec = importlib.util.find_spec('cadagent')
    if spec and spec.origin:
        package = Path(spec.origin).parent
        toolkit = {p.relative_to(package).as_posix(): digest(p) for p in sorted(package.rglob('*.py'))}
    return {'files': inputs, 'GYROPUP_CAD_PARAMS_sha256': parameters, 'versions': versions,
            'toolkit_sources_sha256': fingerprint(toolkit)}


def context_snapshot(root: Path, paths: list[Path]) -> dict:
    result = {}
    for path in paths:
        path = path.resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError('Store the selected design inside the project so its print inputs can be verified')
        result[path.relative_to(root.resolve()).as_posix()] = digest(path)
    return result


def write_receipt(root: Path, directory: Path, meshes: list[Path], inputs: dict, *, context: dict | None = None) -> None:
    """Call only after a successful export; callers capture inputs before building."""
    if snapshot(root) != inputs:
        raise ValueError('CAD inputs changed during export; discard these meshes and rebuild')
    context = context or {}
    if context_snapshot(root, [root / p for p in context]) != context:
        raise ValueError('Selected design changed during export; discard these meshes and rebuild')
    if len({p.name for p in meshes}) != len(meshes):
        raise ValueError('Duplicate print-mesh identity')
    for p in meshes:
        if p.parent.resolve() != directory.resolve() or p.suffix.lower() != '.stl':
            raise ValueError(f'Print mesh must be an STL inside its receipt directory: {p.name}')
    try:
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True,
                                           stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    result = {'schema': 1, 'source_revision': revision, 'inputs': inputs, 'fingerprint': fingerprint(inputs),
              'context_files': context,
              'meshes': {p.name: {'sha256': digest(p)} for p in meshes},
              'qualification': 'Geometry identity only; no print, fit, strength or physical acceptance implied.'}
    target = directory / 'print-meshes.json'
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(result, indent=2) + '\n')
    temporary.replace(target)


def validate_mesh(root: Path, mesh: Path, inputs: dict) -> dict:
    """Reject absent, mixed or stale exports before packaging a 3MF."""
    if not mesh.resolve().is_relative_to((root / 'exports/turret').resolve()):
        raise ValueError('Print mesh is outside the turret export tree')
    receipt = mesh.parent / 'print-meshes.json'
    if not receipt.is_file():
        raise ValueError(f'{mesh.name}: missing source receipt; regenerate CAD before packaging')
    data = json.loads(receipt.read_text())
    if data.get('schema') != 1 or data.get('inputs') != inputs or data.get('fingerprint') != fingerprint(inputs):
        raise ValueError(f'{mesh.name}: CAD/config/toolkit inputs differ; regenerate CAD before packaging')
    context = data.get('context_files')
    if not isinstance(context, dict) or context_snapshot(root, [root / p for p in context]) != context:
        raise ValueError(f'{mesh.name}: selected design differs; regenerate CAD before packaging')
    expected = data.get('meshes', {}).get(mesh.name, {}).get('sha256')
    if not mesh.is_file() or expected != digest(mesh):
        raise ValueError(f'{mesh.name}: missing or changed mesh; regenerate CAD before packaging')
    return {'file': mesh.relative_to(root).as_posix(), 'sha256': expected,
            'fingerprint': data['fingerprint'], 'source_revision': data.get('source_revision'), 'context_files': context}


def current_slice_rows(root: Path, rows: dict, inputs: dict) -> dict:
    """Old slicer grams/time must not migrate into a newly generated bench BOM."""
    current = {}
    for name, row in rows.items():
        source = row.get('source', {})
        try:
            context = source.get('context_files')
            if not isinstance(context, dict) or context_snapshot(root, [root / p for p in context]) != context:
                continue
        except (OSError, ValueError, TypeError):
            continue
        mesh = root / source.get('file', '')
        output = root / 'exports/turret/print' / f'{name}.3mf'
        if (source.get('fingerprint') != fingerprint(inputs)
                or not mesh.resolve().is_relative_to((root / 'exports/turret').resolve())
                or not output.resolve().is_relative_to((root / 'exports/turret/print').resolve())
                or row.get('file') != output.relative_to(root).as_posix()
                or not mesh.is_file() or source.get('sha256') != digest(mesh)
                or not output.is_file() or row.get('sha256') != digest(output)
                or row.get('error') or not row.get('ok') or not row.get('grams') or not row.get('minutes')):
            continue
        current[name] = row
    return current
