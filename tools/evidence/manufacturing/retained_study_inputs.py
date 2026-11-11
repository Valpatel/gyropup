"""Explicit captured inputs for dated carrier studies sharing the RS04 CAD closure."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path

from hardware.cad.manufacturing.print_provenance import source_files
from tools.evidence.manufacturing.retained_fit_history import ROOT, captured_inputs, sha

# Each report independently binds all 94 CAD/config files in the captured root.
STUDIES = {
    'carrier-interfaces': (
        'hardware/exports/turret/base-board-service/interfaces/interfaces.json',
        'ccca71a19e94f877a34b3691803abade7eac2fff50b659c0b2f62a917fa75d7f',
    ),
    'connector-inputs': (
        'docs/research/carrier-service-connectors/private-input-diagnosis.json',
        'd9b6fcec5849e686706efb54d8340444ab5dd53acbcb80d68db0629e99e1209a',
    ),
    'connector-pose': (
        'docs/research/carrier-service-connectors/external-pose.json',
        '9ae926fc0ba745984b777e72c2245ec41968e9ff79c9d1f24dca0bf79f121468',
    ),
    'connector-support': (
        'docs/research/carrier-service-connectors/support-candidate.json',
        'f255b6cee12716012b505f72a0a3b0c0b455827e473a553c63845c144789e7aa',
    ),
    'carrier-insert-fit': (
        'hardware/exports/turret/carrier-insert-fit/receipt.json',
        '17a1fbe2120199afb106738cd27caeb0ce14a6a8efe6d3f95bccbbd3677bff3c',
    ),
}


def bound_bytes(relative, digest):
    path = ROOT / relative
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(ROOT):
        raise ValueError(f'Expected regular retained study input: {relative}')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f'Retained study input changed: {relative}')
    return data


def copy_bound_inputs(destination, bindings):
    for relative, digest in bindings.items():
        target = destination / relative
        if not target.resolve().is_relative_to(destination):
            raise ValueError(f'Retained study path escapes captured inputs: {relative}')
        data = bound_bytes(relative, digest)
        if target.exists():
            if target.read_bytes() != data:
                raise ValueError(f'Retained study input disagrees with captured data: {relative}')
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(data)


@contextmanager
def study_inputs(study):
    """Supply verified data to the unchanged current validators."""
    relative, receipt_digest = STUDIES[study]
    receipt = json.loads(bound_bytes(relative, receipt_digest))
    with captured_inputs() as root:
        actual = {p.relative_to(root).as_posix(): sha(p) for p in source_files(root)}
        if len(actual) != 94 or receipt['inputs']['files'] != actual:
            raise ValueError(f'{study} CAD inputs differ from the captured input closure')
        bindings = dict(receipt.get('context_files', {}))
        bindings[relative] = receipt_digest
        if study == 'carrier-insert-fit':
            artifacts = receipt['files']
            directory = Path(relative).parent
        elif study == 'connector-support':
            artifacts = receipt['public_artifact_sha256']
            directory = Path('hardware/exports/turret/base-board-service/connectors')
        elif study == 'carrier-interfaces':
            artifacts = receipt['artifact_sha256']
            directory = Path(relative).parent
        else:
            artifacts = {}
        for name, digest in artifacts.items():
            bindings[(directory / name).as_posix()] = digest
        copy_bound_inputs(root, bindings)
        yield root
