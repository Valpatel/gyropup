#!/usr/bin/env python3
"""Kernel-free freshness/coverage guard; it does not repeat a CAD or physical test."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
NAMES = ('carrier-boss', 'base-anchor')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(root=ROOT, package=None):
    root = Path(root)
    package = Path(package) if package else root/'exports/turret/carrier-insert-fit'
    report = json.loads((package/'receipt.json').read_text())
    if report.get('schema') != 'gyropup.carrier-insert-fit/1' or report.get('relation_engine') != '4':
        raise ValueError('Unsupported specimen evidence')
    if (report.get('physical_measurements') is not None or report.get('physical_fit_verified') is not False
            or report.get('release_ready') is not False):
        raise ValueError('Generated geometry cannot claim physical qualification')
    override = os.environ.get('GYROPUP_CAD_PARAMS')
    parameter_hash = digest(Path(override)) if override else None
    if report.get('inputs', {}).get('GYROPUP_CAD_PARAMS_sha256') != parameter_hash:
        raise ValueError('Optional CAD parameter input changed; regenerate specimens')
    actual_inputs = {p.relative_to(root).as_posix(): digest(p) for folder in ('cad','catalog','designs')
                     for p in (root/folder).rglob('*') if p.is_file() and p.suffix in ('.py','.json')}
    if report.get('inputs', {}).get('files') != actual_inputs:
        raise ValueError('CAD/config/catalog inputs changed; regenerate specimens')
    context = {p.relative_to(root).as_posix(): digest(p) for p in (root/'research/carrier-insert-fit').glob('*.py')}
    if report.get('context_files') != context:
        raise ValueError('Specimen generation/validation sources changed')
    expected = {f'{name}.{ext}' for name in NAMES for ext in ('step','stl','3mf')} | {'measurements.csv'}
    if set(report.get('files', {})) != expected:
        raise ValueError('Incomplete or extra package file identities')
    if set(p.name for p in package.iterdir()) != expected | {'receipt.json'}:
        raise ValueError('Package directory membership differs from receipt')
    for name, wanted in report['files'].items():
        if digest(package/name) != wanted:
            raise ValueError(f'Changed specimen artifact: {name}')
    if set(report.get('specimens', {})) != set(NAMES):
        raise ValueError('Wrong specimen identities')
    for name, row in report['specimens'].items():
        if not all(v.get('rejected') is True for v in row['negative_controls'].values()) or set(row['negative_controls']) != {'filled_pilot','drilled_through','wrong_orientation'}:
            raise ValueError(f'{name}: incomplete negative controls')
        if row['requested_recipe']['sliced'] is not False or row['requested_recipe']['package_contains_settings'] is not False:
            raise ValueError('Geometry-only package misrepresented as sliced/settings-bound')
        if row['mesh']['watertight'] is not True or row['mesh']['connected_components'] != 1 or row['geometry_only_3mf']['ok'] is not True:
            raise ValueError('Invalid export receipt')
    return report


if __name__ == '__main__':
    result = check(package=sys.argv[1] if len(sys.argv)>1 else None)
    print(f"Fresh geometry package: {len(result['specimens'])} specimens; no physical qualification")
