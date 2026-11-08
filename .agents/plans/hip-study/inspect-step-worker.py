"""Import one pinned retained STEP; no product builder, FEA or output adoption."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def baseline_environment():
    if any(name.startswith('GYROPUP_') for name in os.environ):
        raise ValueError('Inherited product parameters are forbidden in this baseline inspection')


def owned(root, name):
    path = Path(name)
    if path.is_absolute() or '..' in path.parts or path.as_posix() != name:
        raise ValueError('Input must be an owned canonical relative path')
    target = root / path
    if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Required current regular input is missing')
    return target


def bound_inputs(root, cfg):
    baseline_environment()
    assert len(cfg['cad_sources']) == 94
    for name, value in cfg['cad_sources'].items():
        assert sha(owned(root, name)) == value, 'Current CAD source changed: ' + name
    receipt = owned(root, cfg['receipt']['path'])
    step = owned(root, cfg['step']['path'])
    assert sha(receipt) == cfg['receipt']['sha256'], 'Receipt changed'
    assert sha(step) == cfg['step']['sha256'], 'STEP changed'
    record = json.loads(receipt.read_text())
    assert record['source_inputs']['project']['files'] == cfg['cad_sources']
    assert record['artifacts']['hip_frame']['files']['step'] == cfg['step']['sha256']
    assert b'SI_UNIT(.MILLI.,.METRE.)' in step.read_bytes(), 'STEP length unit differs'
    return step, record


def declared_module_file(venv, declared):
    """A pre-recorded regular file or file symlink; never a broad external prefix."""
    rel = declared['venv_path']
    path = Path(rel)
    if path.is_absolute() or '..' in path.parts or path.as_posix() != rel:
        raise ValueError('Module input must be an exact venv-relative file')
    logical = venv / path
    if not logical.is_file(): raise ValueError('Declared module file is missing')
    kind = 'file-symlink' if logical.is_symlink() else 'regular'
    if kind != declared['kind']: raise ValueError('Declared module file kind changed')
    if kind == 'file-symlink':
        target = hashlib.sha256(os.readlink(logical).encode()).hexdigest()
        if target != declared['link_target_sha256']: raise ValueError('Declared module link target changed')
    resolved = hashlib.sha256(str(logical.resolve(strict=True)).encode()).hexdigest()
    if resolved != declared['resolved_path_sha256']: raise ValueError('Resolved module target path changed')
    if sha(logical) != declared['sha256']: raise ValueError('Declared module target bytes changed')
    return logical


def module_identity(name, actual_file, venv, declared):
    logical = declared_module_file(venv, declared)
    actual = Path(actual_file).resolve(strict=True)
    if actual != logical.resolve(strict=True):
        raise ValueError(name + ': imported source differs from the exact declared file target')
    if sha(actual) != declared['sha256']: raise ValueError(name + ': imported bytes changed')
    return {'path': declared['venv_path'], 'sha256': sha(actual), 'kind': declared['kind'],
            'actual_declared_target_match': True, 'resolved_inside_venv': actual.is_relative_to(venv.resolve()),
            'resolved_path_sha256': declared['resolved_path_sha256']}


def runtime_identity(contract, runtime, module_inputs):
    # The identity and import execute in the SAME process as the STEP inspection.
    venv = Path(runtime['venv']).resolve()
    assert set(module_inputs) == {'cadquery', 'gmsh'}
    for declared in module_inputs.values(): declared_module_file(venv, declared)
    from importlib.metadata import version
    import cadagent
    import cadquery
    import gmsh
    assert platform.machine() == contract['platform']
    assert platform.python_version() == contract['python_version']
    assert Path(cadagent.__file__).resolve().is_relative_to(Path(runtime['toolkit']).resolve() / 'src/cadagent')
    versions = {name: (gmsh.__version__ if name == 'gmsh' else version(name)) for name in contract['versions']}
    assert versions == contract['versions']
    origins = {}
    for name, module in (('cadquery', cadquery), ('gmsh', gmsh)):
        origins[name] = module_identity(name, module.__file__, venv, module_inputs[name])
    mapped = {}; managed = {}
    for line in Path('/proc/self/maps').read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) != 6: continue
        raw = fields[-1]
        if '.so' in raw and raw.endswith(' (deleted)'): raise ValueError('Mapped library was deleted')
        path = Path(raw)
        if path.name in contract['mapped_libraries']:
            assert path.resolve() == Path(runtime['libraries'][path.name]).resolve()
            mapped.setdefault(path.name, set()).add(sha(path))
        if path.is_absolute() and '.so' in path.name and path.resolve().is_relative_to(venv):
            managed[path.resolve().relative_to(venv).as_posix()] = sha(path)
    assert mapped == {name: {value} for name, value in contract['mapped_libraries'].items()}
    assert any('/OCP/' in name for name in managed), 'Actual OCP kernel mapping is required'
    return cadquery, {'versions': versions, 'mapped_libraries': {n: list(v)[0] for n, v in mapped.items()},
                      'python_version': platform.python_version(), 'architecture': platform.machine(),
                      'toolkit_origin_verified': True, 'module_origins': origins, 'mapped_venv_libraries': managed}


def inspect(cq, step):
    shape = cq.importers.importStep(str(step)).val()
    edges = shape.Edges()
    buckets = {}
    for i, edge in enumerate(edges):
        buckets.setdefault(edge.hashCode(), []).append(i)

    def edge_id(edge):
        matches = [j for j in buckets.get(edge.hashCode(), []) if edge.isSame(edges[j])]
        assert len(matches) == 1, 'Face edge cannot be unambiguously matched'
        return matches[0]

    def point(value):
        return list(value.toTuple())

    def bounds(value):
        b = value.BoundingBox()
        return [b.xmin, b.ymin, b.zmin, b.xmax, b.ymax, b.zmax]

    rows = []
    for i, edge in enumerate(edges):
        kind = edge.geomType()
        rows.append({'id': i, 'type': kind, 'length_mm': edge.Length(), 'bounds_mm': bounds(edge),
                     'centre_mm': point(edge.Center()), 'vertices_mm': [point(v.Center()) for v in edge.Vertices()],
                     'start_mm': point(edge.startPoint()), 'end_mm': point(edge.endPoint()),
                     'circle_centre_mm': point(edge.arcCenter()) if kind == 'CIRCLE' else None,
                     'radius_mm': edge.radius() if kind == 'CIRCLE' else None, 'faces': []})
    faces = []
    for i, face in enumerate(shape.Faces()):
        ids = []
        for edge in face.Edges():
            j = edge_id(edge)
            ids.append(j); rows[j]['faces'].append(i)
        wires = [[edge_id(edge) for edge in wire.Edges()] for wire in face.Wires()]
        assert set(ids) == {j for wire in wires for j in wire}
        faces.append({'id': i, 'type': face.geomType(), 'area_mm2': face.Area(),
                      'bounds_mm': bounds(face), 'centre_mm': point(face.Center()), 'edges': ids, 'wires': wires,
                      'plane_normal': point(face.normalAt()) if face.geomType() == 'PLANE' else None})
    return {'units': 'mm', 'frame': 'Retained unrotated STEP export; no world transform applied',
            'valid': shape.isValid(), 'solid_count': len(shape.Solids()), 'volume_mm3': shape.Volume(),
            'bounds_mm': bounds(shape), 'edges': rows, 'faces': faces,
            'index_scope': 'IDs are local to this import, not stable parametric edge selectors',
            'source_builder_invoked': False, 'interfaces_validated': False, 'fea_run': False,
            'physical_qualification': False}


def final_record(result, write):
    try:
        write('worker-result.json', result)
    except BaseException as exc:
        result.update(status='FAILED', final_write_error=type(exc).__name__ + ': ' + str(exc))
        try: print(json.dumps(result), file=sys.stderr)
        except BaseException: pass
        if 'original_error' not in result:
            raise


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'config', 'runtime', 'contract', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    args = p.parse_args(argv)
    baseline_environment()  # Before output creation, any CAD import or parameter evaluation.
    root = args.root.resolve(); out = args.out.resolve()
    assert not out.is_relative_to(root) and not out.exists()
    cfg = json.loads(args.config.read_text()); step, receipt = bound_inputs(root, cfg)
    out.mkdir(mode=0o700)
    result = {'status': 'FAILED', 'step_sha256': sha(step), 'adoption_approved': False}
    def save(name, value):
        (out / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    try:
        cq, identity = runtime_identity(json.loads(args.contract.read_text()), json.loads(args.runtime.read_text()), cfg['module_inputs'])
        save('worker-runtime.json', identity)
        report = inspect(cq, step)
        report['retained_engineering_receipt'] = {
            'sha256': cfg['receipt']['sha256'], 'status': receipt['status'],
            'pass': receipt['pass'], 'counts': receipt['counts'],
            'meaning': 'Retained source-bound result, not a new fit or strength evaluation'}
        save('topology.json', report)
        assert report['valid'] and report['solid_count'] == 1
        assert round(report['volume_mm3'] / 1000, 1) == receipt['artifacts']['hip_frame']['stl_check']['volume_cm3']
        assert sha(step) == cfg['step']['sha256']
        assert not any(name == 'hardware.cad' or name.startswith('hardware.cad.') for name in sys.modules)
        _, after = runtime_identity(json.loads(args.contract.read_text()), json.loads(args.runtime.read_text()), cfg['module_inputs'])
        save('worker-runtime.json', {'before': identity, 'after': after})
        result.update(status='PASS_IMPORT_TOPOLOGY_ONLY', edges=len(report['edges']), faces=len(report['faces']))
    except BaseException as exc:
        result['original_error'] = type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        final_record(result, save)  # Nonzero on final-write failure; retain an active primary exception.


if __name__ == '__main__':
    main()
