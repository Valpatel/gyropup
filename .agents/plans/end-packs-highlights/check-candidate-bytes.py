"""Scratch-only byte preflight; never bind public assets, construct CAD or capture media."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[3]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--candidate', required=True, type=Path)
a = p.parse_args()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
helper = ROOT/'tools/evidence/media/check-highlights.py'
spec = importlib.util.spec_from_file_location('candidate_byte_preflight', helper)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
data = a.candidate
assert data.is_dir() and not data.is_symlink()
files = {}
for path in data.rglob('*'):
    assert not path.is_symlink(), 'Nonregular candidate input'
    if path.is_dir():
        continue
    assert path.is_file()
    files[path.relative_to(data).as_posix()] = path.stat().st_size
assert len(files) == 226 and sum(files.values()) <= 32*1024*1024
assert sha(data/'manifest.json') == m.CURRENT_SOURCE['sha256']
model = json.loads((data/'manifest.json').read_text())
assert set(files) == {'manifest.json', 'collection.json', *(part['file'] for part in model['parts'])}
sources = set(model['current_inputs']) | set(model['conversion']['inputs'])
before = {name: sha(ROOT/name) for name in sources}
with tempfile.TemporaryDirectory(prefix='current-highlight-byte-preflight-') as folder:
    root = Path(folder)
    shutil.copytree(data, root/'software/site/assets/robot-current', symlinks=True)
    for name in sources:
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, path)
    authority = root/'software/site/designer/robot_current_source.js'
    authority.parent.mkdir(parents=True)
    authority.write_text('export const CURRENT_ROBOT_SOURCE = '+json.dumps(m.CURRENT_SOURCE)+';\n')
    m.ROOT = root
    contract = m.current_robot_contract()
assert before == {name: sha(ROOT/name) for name in sources}
print(json.dumps(dict(schema='gyropup.current-highlights-byte-preflight/1',
    scope='Scratch-only accepted bytes/source check; authority exists only in deleted scratch. No public binding, browser, capture, encode, native work or adoption.',
    manifest=contract['source'], native_source=contract['native_source'], collection_sha256=contract['collection_sha256'],
    originals=len(contract['parts']), turret_names=len(contract['turret_parts']), browser_assets=len(contract['asset_hashes']),
    local_provenance_sources=len(contract['source_hashes']), source_inputs=len(model['current_inputs']),
    conversion_inputs=len(model['conversion']['inputs']), source_preserved=True,
    checker_sha256=sha(helper), harness_sha256=sha(Path(__file__))), indent=2))
