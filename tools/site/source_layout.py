"""Locate stable published file identities in the owning source checkout.

This is a filesystem lookup only: it neither rewrites receipt keys/hashes nor
qualifies a historical artifact as current. Publication remains the JS builder's
tracked-source allowlist. No obsolete source copy is used as a fallback.
"""
from __future__ import annotations
import json
from pathlib import Path, PurePosixPath

CONTRACT_FILE = Path(__file__).with_name('source-layout.json')
_LAYOUT = json.loads(CONTRACT_FILE.read_text())
if _LAYOUT['version'] != 1:
    raise ValueError('Unsupported source-layout contract')
_EXACT = {row['public']: row['source'] for row in _LAYOUT['files']}
if len(_EXACT) != len(_LAYOUT['files']):
    raise ValueError('Duplicate published source identity')


def source_for_public(identity: str) -> str:
    value = str(identity)
    normalized = PurePosixPath(value)
    if (normalized.is_absolute() or '..' in normalized.parts or '\\' in value
            or '\0' in value or str(normalized) != value):
        raise ValueError('Source identity is not a canonical project-relative path')
    if value in _EXACT:
        return _EXACT[value]
    for rule in _LAYOUT['prefixes']:
        if value == rule['public'] or value.startswith(rule['public'] + '/'):
            return rule['source'] + value[len(rule['public']):]
    return value  # Explicit current paths may be unpublished; no old-copy search.


def source_file(root: Path, identity: str) -> Path:
    return Path(root) / source_for_public(identity)
