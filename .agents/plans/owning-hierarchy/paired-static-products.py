#!/usr/bin/env python3
"""Retain two full-history builds; output comparison remains a separate review.

Run only on the fleet at a pushed SHA. No CAD, media encoding or receipt writes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(directory):
    return {p.relative_to(directory).as_posix(): {'bytes': p.stat().st_size, 'sha256': digest(p)}
            for p in sorted(directory.rglob('*')) if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', required=True)
    parser.add_argument('--head', required=True)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    out = Path(os.environ['FLEET_RUN_OUT']).resolve()
    out.mkdir(exist_ok=True)
    phases = []
    baseline = None
    source_before = {}
    products = {}
    result = {'scope': 'paired static builds/Markdown/privacy only; output classification and remaining migration checks required',
              'before': args.before, 'head': args.head, 'status': 'FAILED', 'phases': phases, 'products': products}

    def git(*argv, cwd=root):
        return subprocess.check_output(['git', *argv], cwd=cwd, text=True).strip()

    def save():
        (out / 'paired-static-result.json').write_text(json.dumps(result, indent=2) + '\n')

    def run(label, argv, cwd=root):
        row = {'phase': label, 'argv': argv, 'started_unix': time.time()}
        phases.append(row)
        save()
        with (out / (label + '.log')).open('w') as log:
            completed = subprocess.run(argv, cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
        row.update(exit=completed.returncode, ended_unix=time.time())
        save()
        if completed.returncode:
            raise RuntimeError(f'{label} exited {completed.returncode}; see retained phase log')

    def retain(label, checkout):
        product = checkout / 'dist'
        if not product.is_dir():
            return
        files = inventory(product)
        (out / (label + '-inventory.json')).write_text(json.dumps(files, indent=2) + '\n')
        archive = out / (label + '-dist.tgz')
        with tarfile.open(archive, 'w:gz') as stream:
            stream.add(product, arcname='dist')
        products[label] = {'build_completed': any(row['phase'] == ('before-build' if label == 'before' else 'after-build') and row.get('exit') == 0 for row in phases),
                           'revision': git('rev-parse', 'HEAD', cwd=checkout),
                           'history_complete': git('rev-parse', '--is-shallow-repository', cwd=checkout) == 'false',
                           'files': len(files), 'archive_sha256': digest(archive),
                           'inventory_sha256': digest(out / (label + '-inventory.json'))}
        save()

    try:
        assert len(args.head) == len(args.before) == 40
        assert git('rev-parse', 'HEAD') == args.head
        assert git('rev-parse', '--is-shallow-repository') == 'false', 'Complete history is required before dependency setup'
        subprocess.run(['git', 'merge-base', '--is-ancestor', args.before, args.head], cwd=root, check=True)
        assert not git('status', '--porcelain')
        source_before = {name: digest(root / name) for name in git('ls-files').splitlines()}
        assert (root / 'tools/site/build-site.mjs').is_file()
        assert (root / 'tools/site/source-layout.json').is_file()
        assert shutil.which('npm') and shutil.which('node')
        result['node'] = subprocess.check_output(['node', '--version'], text=True).strip()
        result['python'] = subprocess.check_output(['python', '--version'], text=True).strip()
        run('dependencies', ['npm', 'ci', '--ignore-scripts'])
        baseline = Path(tempfile.mkdtemp(prefix='gyropup-owning-before-'))
        assert not baseline.is_relative_to(Path(os.environ['FLEET_RUN_DIR']).resolve())
        run('before-checkout', ['git', 'worktree', 'add', '--detach', str(baseline), args.before])
        (baseline / 'node_modules').symlink_to(root / 'node_modules', target_is_directory=True)
        try:
            run('before-build', ['npm', 'run', 'build'], cwd=baseline)
        finally:
            retain('before', baseline)
        try:
            run('after-build', ['npm', 'run', 'build'])
        finally:
            retain('after', root)
        run('after-markdown', ['npm', 'run', 'test:markdown'])
        run('after-privacy', ['npm', 'run', 'test:privacy'])
        for label, checkout in (('before', baseline), ('after', root)):
            assert inventory(checkout / 'dist') == json.loads((out / (label + '-inventory.json')).read_text())
        assert {name: digest(root / name) for name in git('ls-files').splitlines()} == source_before
        assert not git('status', '--porcelain')
        result.update(status='PASS_SCOPED', source_unchanged=True, products_unchanged_after_checks=True,
                      classification='NOT_YET_PERFORMED; retain all changed paths and inspect actual fields/bytes')
    except BaseException as error:
        result['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        if baseline is not None:
            cleanup = subprocess.run(['git', 'worktree', 'remove', '--force', str(baseline)], cwd=root,
                                     capture_output=True, text=True)
            # A checkout-creation failure may leave only the owned empty directory.
            if baseline.exists() and cleanup.returncode and not any(baseline.iterdir()):
                baseline.rmdir()
            result['owned_baseline_removed'] = not baseline.exists()
            result['cleanup_exit'] = cleanup.returncode
            if not result['owned_baseline_removed'] and result['status'] == 'PASS_SCOPED':
                result['status'] = 'FAILED_CLEANUP'
        save()
        if result['status'] == 'FAILED_CLEANUP':
            raise RuntimeError('Owned baseline checkout cleanup failed')


if __name__ == '__main__':
    main()
