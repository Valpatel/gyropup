"""The design gates' fingerprint (cad/turret_gates.py geometry_fingerprint) covers every file the turret's geometry is
built from: cad/turret.py, each cad/ module it imports, the modules those import, and the data files they read when
imported. A module left out means a stored gate result reads as current after that module changed the geometry
(cad/turret_snaps.py was left out from #131 until the review of PR #181). Kernel-free: it reads the sources.

    .venv/bin/python -m pytest cad/test_turret_gate_sources.py -q
"""
from __future__ import annotations

import ast
import shutil
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
# Imported by a module of the turret but not into its geometry: (module, the function that imports it) and why
NOT_GEOMETRY = {('turret.py', 'main', 'print_provenance'): 'the exported STLs\' provenance record, read after the parts are built'}


def _imports(path: Path):
    """(name, enclosing top-level function or None) for every import in the file."""
    out = []
    for node in ast.parse(path.read_text()).body:
        where = node.name if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else None
        for n in ast.walk(node):
            if isinstance(n, ast.Import):
                out += [(a.name.split('.')[0], where) for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
                out.append((n.module.split('.')[0], where))
    return out


def _data_files(path: Path):
    """Repository-relative .json paths named in the module's top-level statements (read when it is imported)."""
    out = set()
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            continue
        for n in ast.walk(node):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.endswith('.json') and '/' in n.value:
                out.add(n.value)
    return out


def geometry_files(cad: Path, entry='turret.py'):
    """Every cad/ module reached from entry by its imports (NOT_GEOMETRY's skipped), and the data files they read."""
    seen, todo, data = set(), [entry], set()
    while todo:
        m = todo.pop()
        if m in seen:
            continue
        seen.add(m)
        data |= _data_files(cad / m)
        for name, where in _imports(cad / m):
            if (cad / f'{name}.py').exists() and (m, where, name) not in NOT_GEOMETRY:
                todo.append(f'{name}.py')
    return {f'cad/{m}' for m in seen} | data


def uncovered(sources, cad: Path = HERE):
    return sorted(geometry_files(cad) - set(sources))


@pytest.fixture(scope='module')
def tg():
    import turret_gates
    return turret_gates


def test_fingerprint_covers_the_geometry(tg):
    assert uncovered(tg.GEOMETRY_SOURCES) == []
    for s in tg.GEOMETRY_SOURCES:
        assert (ROOT / s).exists(), s
    assert {'cad/turret_snaps.py', 'cad/gmi.py', 'cad/interfaces.json'} <= set(tg.GEOMETRY_SOURCES)


def test_not_geometry_is_still_imported_where_it_says():
    for (mod, fn, name) in NOT_GEOMETRY:
        assert (name, fn) in _imports(HERE / mod), (mod, fn, name)


def test_fingerprint_reads_every_source(tg, monkeypatch, tmp_path):
    """Each listed file changes the fingerprint: turret_snaps.py edited, the hash moves."""
    before = tg.geometry_fingerprint()
    copy = tmp_path / 'repo'
    for s in tg.GEOMETRY_SOURCES:
        (copy / s).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / s, copy / s)
    monkeypatch.setattr(tg, 'R', copy)
    assert tg.geometry_fingerprint() == before
    (copy / 'cad' / 'turret_snaps.py').write_text((copy / 'cad' / 'turret_snaps.py').read_text() + '\n# edited\n')
    assert tg.geometry_fingerprint() != before


# ------------------------------------------------------------------------------------------------ controls

def test_control_the_old_list_misses_the_snaps(tg):
    """The list as it was before the review of PR #181 leaves out the lids' snap constants (and gmi and its data)."""
    old = ('cad/turret.py', 'cad/turret_base_board.py', 'cad/turret_boards.py')
    assert 'cad/turret_snaps.py' in uncovered(old)


def test_control_a_new_import_is_caught(tg, tmp_path):
    """A cad/ module newly imported by turret.py (here turret_studies) is reported until it is listed."""
    cad = tmp_path / 'cad'
    shutil.copytree(HERE, cad, ignore=shutil.ignore_patterns('__pycache__', '*.stl', '*.step'))
    src = (cad / 'turret.py').read_text()
    (cad / 'turret.py').write_text(src.replace('import turret_snaps as snaps', 'import turret_snaps as snaps\nimport turret_studies', 1))
    assert 'cad/turret_studies.py' in uncovered(tg.GEOMETRY_SOURCES, cad)
