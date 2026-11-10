"""One offline integrity contract for dated RS04 evidence, never current fit.

Captured public source is inert data. Only current checker/helper code executes.
The fixed anchors below implement the independently reviewed issue193 boundary.
"""
from __future__ import annotations

from contextlib import contextmanager
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT = 'f77fcde00880d4cedf8ca1a7edabd993714deaca'
PRODUCER = '017e1e03eacdfaec7eda891a14143a2f9254581a'
PLAN = Path('.agents/plans/end-packs')
ARCHIVE = PLAN / 'retained-fit-inputs.tar.gz'
MANIFEST = PLAN / 'retained-fit-inputs.json'
ARCHIVE_SHA = 'cca45e96a203729279449f9089eb938b2b0adf5d1a7d9472d735a60753971515'
MANIFEST_SHA = '2158d0e0b216069d3a5ac0b7bffa63e82943efcbadf96118330c070da35d1f18'
ENGINEERING = Path('hardware/exports/leg/rs04-mounting-fit')
RECEIPT_SHA = '613e9ff07406145c3e7821a75f964dd8b569764385e840ff448d06c2b62dcfc4'
JOB = Path('hardware/exports/leg/rs04-fit-job')
JOB_SHA = 'b94cfb11d2da264069c4d0e7c9fb784ee44f6620032fa3030bf4461865a18605'
COUNTS = {'pass': 322, 'warn': 40, 'fail': 8}
MAX_INPUT = 1024 * 1024
MAX_RAW = 4 * 1024 * 1024
MAX_MEMBER = 512 * 1024


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _bounded_bytes(path, limit):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError('Historical evidence must be a bounded regular file')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Historical evidence exceeds input bound')
    return raw


def _unpack(raw, members, destination):
    """Parse only an exact bounded USTAR inventory; never extract/import code."""
    if len(raw) > MAX_INPUT or len(members) != 96:
        raise ValueError('Historical snapshot input/member bound differs')
    if sum(row['bytes'] for row in members.values()) > MAX_RAW:
        raise ValueError('Historical snapshot declared size exceeds bound')
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        expanded = stream.read(MAX_RAW + 1)
    if len(expanded) > MAX_RAW:
        raise ValueError('Historical snapshot expansion exceeds bound')
    seen = set()
    with tarfile.open(fileobj=io.BytesIO(expanded), mode='r:') as archive:
        for member in archive:
            name = member.name
            canonical = PurePosixPath(name)
            if (len(seen) >= 96 or name in seen or name not in members
                    or canonical.is_absolute() or '..' in canonical.parts
                    or str(canonical) != name or '\\' in name or len(name) > 256
                    or member.type != tarfile.REGTYPE or member.pax_headers
                    or archive.pax_headers or member.linkname or member.sparse
                    or member.uid != 0 or member.gid != 0 or member.uname or member.gname
                    or member.mtime != 0 or member.mode != 0o600):
                raise ValueError('Historical snapshot membership or metadata differs')
            expected = members[name]
            if not 0 < member.size <= MAX_MEMBER or member.size != expected['bytes']:
                raise ValueError('Historical snapshot member size differs')
            stream = archive.extractfile(member)
            payload = stream.read(MAX_MEMBER + 1)
            if len(payload) != member.size or hashlib.sha256(payload).hexdigest() != expected['sha256']:
                raise ValueError('Historical snapshot member digest differs')
            path = Path(destination) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as target:
                target.write(payload)
            seen.add(name)
    if seen != set(members):
        raise ValueError('Historical snapshot required membership incomplete')


def _current_modules(root):
    """Reject old-root imports and changed actual execution helper bytes."""
    from hardware.cad.legs import rs04_lug_checks as checks
    from hardware.cad.manufacturing import print_provenance
    report = json.loads((root / JOB / 'job.json').read_text())
    for module, file in ((checks, 'hardware/cad/legs/rs04_lug_checks.py'),
                         (print_provenance, 'hardware/cad/manufacturing/print_provenance.py')):
        if (Path(module.__file__).resolve() != ROOT / file
                or sha(module.__file__) != report['inputs']['files'][file]
                or sha(root / file) != report['inputs']['files'][file]):
            raise ValueError('Historical validator executed helper origin/bytes differ')
    return checks


@contextmanager
def captured_inputs(root=ROOT):
    """Yield verified public captured data after the actual strict receipt check.

    Artifact bytes come from the current archive owner. Its engineering receipt
    is checked against its full historical input closure, never today's closure.
    No Git process, network, vendor geometry or historical code execution.
    """
    root = Path(root)
    if sha(root / JOB / 'job.json') != JOB_SHA or sha(root / ENGINEERING / 'checks.json') != RECEIPT_SHA:
        raise ValueError('Reviewed historical job/engineering receipt anchor differs')
    raw = _bounded_bytes(root / ARCHIVE, MAX_INPUT)
    manifest_raw = _bounded_bytes(root / MANIFEST, 64 * 1024)
    if hashlib.sha256(raw).hexdigest() != ARCHIVE_SHA or hashlib.sha256(manifest_raw).hexdigest() != MANIFEST_SHA:
        raise ValueError('Reviewed historical snapshot anchor differs')
    manifest = json.loads(manifest_raw)
    data = json.loads((root / ENGINEERING / 'checks.json').read_text())
    expected = data['source_inputs']['project']['files'] | data['source_inputs']['context_files']
    if (manifest['schema'] != 'gyropup.retained-fit-input-snapshot/1'
            or manifest['matching_input_snapshot'] != SNAPSHOT or manifest['recorded_slice_producer'] != PRODUCER
            or {name: row['sha256'] for name, row in manifest['members'].items()} != expected):
        raise ValueError('Historical snapshot full input identity differs')
    checks = _current_modules(root)
    with tempfile.TemporaryDirectory(prefix='retained-fit-inputs-') as temporary:
        temporary = Path(temporary)
        _unpack(raw, manifest['members'], temporary)
        checks.validate_receipt(data, root / ENGINEERING, temporary)
        yield temporary


def verify_archive(root=ROOT):
    """Run the full unchanged current packager against this fixed old archive."""
    root = Path(root)
    with captured_inputs(root) as inputs:
        report = json.loads((root / JOB / 'job.json').read_text())
        # The recorded files are read as data under the captured root; current
        # modules below execute from ROOT. Preserve all original verifier code.
        for relative, digest in report['inputs']['files'].items():
            if sha(root / relative) != digest:
                raise ValueError('Historical archive current input byte identity differs')
            path = inputs / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((root / relative).read_bytes())
        for part in ('hip_frame', 'dyno_lug_plate', 'coupon_frame_ring_nom'):
            for ext in ('step', 'stl'):
                relative = ENGINEERING / (part + '.' + ext)
                (inputs / relative).write_bytes((root / relative).read_bytes())
        source = ROOT / 'tools/evidence/manufacturing/package-fit-job.py'
        spec = importlib.util.spec_from_file_location('current_retained_fit_packager', source)
        fit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fit)
        for module, relative in ((fit, 'tools/evidence/manufacturing/package-fit-job.py'),
                                 (fit.print_slicing, 'hardware/cad/manufacturing/print_slicing.py')):
            if (Path(module.__file__).resolve() != ROOT / relative
                    or sha(module.__file__) != report['inputs']['files'][relative]):
                raise ValueError('Full archive executed helper origin/bytes differ')
        result = fit.verify(root / JOB, root=inputs)
        if result['source_commit'] != PRODUCER or result['inputs']['engineering_counts'] != COUNTS:
            raise ValueError('Historical producer/outcome differs')
    return {'historical_archive_integrity': True, 'matching_input_snapshot': SNAPSHOT,
            'recorded_slice_producer': PRODUCER, 'job_sha256': JOB_SHA,
            'engineering_receipt_sha256': RECEIPT_SHA, 'engineering_pass': False,
            'engineering_counts': COUNTS, 'scope': 'Historical archive integrity only; no current-body or physical qualification.'}
