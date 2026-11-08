"""Geometry-only hip study checks. Importing this module loads no CAD or FEA kernel."""
from pathlib import Path
import hashlib
import json
import os
import stat
import types


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inputs(study):
    rows = study.source_hashes()
    rows[Path(__file__).resolve().relative_to(study.ROOT).as_posix()] = digest(__file__)
    for name in ('.agents/plans/hip-study/accepted-topology/topology.json',
                 '.agents/plans/hip-study/accepted-topology/accepted-import-record.json',
                 '.agents/plans/hip-study/retained-foot-baseline.params.json'):
        rows[name] = digest(study.ROOT / name)
    return rows


def prepare(study, out):
    if any(name.startswith('GYROPUP_') for name in os.environ):
        raise ValueError('Geometry study rejects inherited product parameters')
    before = inputs(study)  # Before output creation or any CAD import.
    out = Path(out).resolve()
    if out.is_relative_to(study.ROOT) or out.exists():
        raise ValueError('Geometry output must be a fresh directory outside the checkout')
    out.mkdir(parents=True, mode=0o700)
    return out, before


def write(out, name, value):
    (out / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def measured_mounts(fb, shape):
    import cadquery as cq
    from hardware.cad.body import body_params as bp
    # Use the actual supplied solid, not another call to the default builder.
    owned = types.SimpleNamespace(Y=fb.Y, hip_frame=lambda: cq.Workplane(obj=shape))
    return bp._measure_frame(owned, 'geometry-study-actual-shape')


def mount_signature(row):
    return {name: row[name] for name in (
        'centre_plane_y', 'measured_holes', 'pilot_d', 'depth', 'face')}


def require_same_mounts(baseline, candidate):
    # These are the existing measured-interface fields/rounding, not copied catalogue counts.
    if mount_signature(baseline) != mount_signature(candidate):
        raise ValueError('Actual mounting faces or pilot geometry changed')


def preserve_construction_failure(out, error):
    """Keep only owned shape evidence; diagnostics must not replace the CAD error."""
    if not hasattr(error, 'foot_context') or not hasattr(error, 'foot_shapes'):
        return
    try:
        exports = {}
        for name in ('unfilleted-local', 'source-back', 'rounded-local', 'retained-base',
                     'rounded-addition', 'raw-finished', 'finished-local'):
            if name not in error.foot_shapes:
                continue
            target = out / (name + '.brep')
            if not error.foot_shapes[name].exportBrep(str(target)):
                raise ValueError('Failed construction BREP export failed')
            exports[name] = {'file': target.name, 'sha256': digest(target)}
        write(out, 'construction-failure.json', {
            'scope': 'Failed native construction only; no candidate/interfaces/FEA acceptance',
            'error': type(error.__cause__).__name__ + ': ' + str(error.__cause__),
            'context': error.foot_context, 'shapes': exports})
    except Exception as capture_error:
        error.add_note('Secondary diagnostic capture failure: ' + type(capture_error).__name__
                       + ': ' + str(capture_error))


def case(study, out, params):
    baseline_params = json.loads((study.ROOT / '.agents/plans/hip-study/retained-foot-baseline.params.json').read_text())
    if params is not None and params != baseline_params:
        raise ValueError('Geometry case accepts only the retained zero-radius override or the source default')
    out, before = prepare(study, out)
    try:
        fit = study.precheck(out / 'precheck', params)
        import hardware.cad.legs.fivebar as fb
        diagnostics = {}
        shape = fb.hip_frame(foot_diagnostics=diagnostics).val()
    except Exception as error:
        preserve_construction_failure(out, error)
        raise
    if not shape.isValid() or len(shape.Solids()) != 1:
        raise ValueError('Geometry case is not one valid solid')
    mounts = measured_mounts(fb, shape)
    declared = fb.frame_mounts()
    expected_holes = sorted([round(x, 3), round(z, 3)] for x, z in declared['inserts_xz'])
    if mounts['measured_holes'] != [tuple(row) for row in expected_holes]:
        raise ValueError('Actual pilot circles differ from the source mounting interface')
    brep = out / 'hip-frame.brep'
    if not shape.exportBrep(str(brep)):
        raise ValueError('Geometry BREP export failed')
    reference = None
    if params is not None:
        reference_path = study.ROOT / '.agents/plans/hip-study/accepted-topology/topology.json'
        reference = json.loads(reference_path.read_text())
        seal = json.loads((reference_path.parent / 'accepted-import-record.json').read_text())
        if digest(reference_path) != seal['sealed_members']['topology.json']['sha256']:
            raise ValueError('Accepted reference topology seal differs')
        bb = shape.BoundingBox()
        actual_bounds = [bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax]
        if (round(shape.Volume()/1000, 1) != round(reference['volume_mm3']/1000, 1)
                or [round(v, 2) for v in actual_bounds] != [round(v, 2) for v in reference['bounds_mm']]):
            raise ValueError('Retained-path geometry differs at the existing published volume/bounds precision')
        reference = {'source': seal['source'], 'topology_sha256': digest(reference_path),
                     'volume_mm3': reference['volume_mm3'], 'bounds_mm': reference['bounds_mm'],
                     'scope': 'Existing published precision only, not exact BREP or physical equivalence'}
    after = inputs(study)
    if before != after:
        raise ValueError('Geometry inputs changed during the build')
    bb = shape.BoundingBox()
    result = {'scope': 'geometry-only; no FEA or physical qualification',
              'units': 'mm', 'frame': 'Source left-leg frame: x forward, y outward, z up; unrotated',
              'status': 'BUILT_WITH_FAILED_INTERFACES' if not (fit['bed']['ok'] and fit['body']['ok']) else 'BUILT_ONLY',
              'inputs_sha256': before, 'params': params or {}, 'effective_hip': dict(fb.HIP),
              'interfaces': fit, 'measured_mounts': mounts, 'declared_mounts': declared,
              'foot_diagnostics': diagnostics, 'volume_mm3': shape.Volume(),
              'retained_reference': reference,
              'bounds_mm': [bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax],
              'brep': {'file': brep.name, 'sha256': digest(brep)},
              'source_builder_invoked': True, 'fea_run': False, 'physical_qualification': False}
    write(out, 'geometry.json', result)
    return result


def diagnostic_inputs(source, declared):
    source = Path(source).resolve()
    expected = {'construction-failure.json', 'unfilleted-local.brep', 'source-back.brep'}
    if set(declared) != expected:
        raise ValueError('Incomplete failed-construction input contract')
    for name, value in declared.items():
        path = source / name
        if not stat.S_ISREG(path.lstat().st_mode) or digest(path) != value:
            raise ValueError('Failed-construction input identity differs: ' + name)
    failure = json.loads((source / 'construction-failure.json').read_text())
    if failure['context']['radius_mm'] != 3.5 or not failure['context']['edges']:
        raise ValueError('Diagnostic must retain the failed 3.5 mm edge intent')
    for row in failure['shapes'].values():
        if declared[row['file']] != row['sha256']:
            raise ValueError('Failed-shape seal differs')
    return failure


def diagnose(study, out, source):
    """Inspect one sealed failed fillet at unchanged radius, never a design screen."""
    config = json.loads((study.ROOT / '.agents/plans/hip-study/foot-geometry-inputs.json').read_text())
    declared = config['fault_diagnostic']['inputs']
    failure = diagnostic_inputs(source, declared)
    out, before = prepare(study, out)
    import cadquery as cq
    from cadquery.occ_impl.shapes import TOLERANCE
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
    local = cq.Shape.importBrep(str(Path(source) / 'unfilleted-local.brep'))
    if not local.isValid() or len(local.Solids()) != 1:
        raise ValueError('Sealed failed local shape is not one valid solid')
    local = local.Solids()[0]
    def edge_row(edge):
        return {'type': edge.geomType(), 'length_mm': edge.Length(),
                **{name: list(edge.positionAt(t).toTuple()) for name, t in (
                    ('start_mm', 0), ('centre_mm', .5), ('end_mm', 1))}}
    def same_point(a, b):
        return sum((x-y)**2 for x, y in zip(a, b)) <= TOLERANCE**2
    selected = []
    all_edges = local.Edges()
    for record in failure['context']['edges']:
        matches = [edge for edge in all_edges if edge.geomType() == record['type']
                   and abs(edge.Length()-record['length_mm']) <= TOLERANCE
                   and same_point(edge_row(edge)['centre_mm'], record['centre_mm'])
                   and (all(same_point(edge_row(edge)[a], record[b]) for a, b in (
                       ('start_mm', 'start_mm'), ('end_mm', 'end_mm')))
                        or all(same_point(edge_row(edge)[a], record[b]) for a, b in (
                            ('start_mm', 'end_mm'), ('end_mm', 'start_mm'))))]
        if len(matches) != 1 or any(matches[0].isSame(e) for e in selected):
            raise ValueError('Failed edge cannot be uniquely rebound to actual sealed shape')
        selected.append(matches[0])
    builder = BRepFilletAPI_MakeFillet(local.wrapped)
    for edge in selected:
        builder.Add(failure['context']['radius_mm'], edge.wrapped)
    result = {'scope': 'Saved failed-shape kernel diagnosis only; no candidate or engineering acceptance',
              'input_sha256': declared, 'source_sha256': before, 'radius_mm': 3.5,
              'selected_edges': [edge_row(e) for e in selected], 'fea_run': False,
              'physical_qualification': False, 'queries': {}, 'query_errors': {}}
    # Keep native API differences/errors as evidence without guessing or changing parameters.
    def query(name, call):
        try:
            result['queries'][name] = call()
            return result['queries'][name]
        except Exception as error:
            result['query_errors'][name] = type(error).__name__ + ': ' + str(error)
            return None
    contours = query('contour_count', builder.NbContours)
    if contours is not None:
        for i in range(1, contours+1):
            query(f'contour_{i}', lambda i=i: {
                'closed': builder.Closed(i), 'edge_count': builder.NbEdges(i),
                'edges': [edge_row(cq.Edge(builder.Edge(i, j))) for j in range(1, builder.NbEdges(i)+1)]})
    try:
        builder.Build()
    except Exception as error:
        result['build_error'] = type(error).__name__ + ': ' + str(error)
    result['is_done'] = builder.IsDone()
    faulty = query('faulty_contour_count', builder.NbFaultyContours)
    if faulty is not None:
        for j in range(1, faulty+1):
            i = query(f'faulty_{j}_index', lambda j=j: builder.FaultyContour(j))
            if i is not None:
                query(f'faulty_{j}_status', lambda i=i: str(builder.StripeStatus(i)))
                query(f'faulty_{j}_computed_surfaces', lambda i=i: builder.NbComputedSurfaces(i))
    vertices = query('faulty_vertex_count', builder.NbFaultyVertices)
    if vertices is not None:
        for i in range(1, vertices+1):
            query(f'faulty_vertex_{i}', lambda i=i: list(cq.Vertex(builder.FaultyVertex(i)).toTuple()))
    query('has_partial_result', builder.HasResult)
    if before != inputs(study) or failure != diagnostic_inputs(source, declared):
        raise ValueError('Diagnostic source/failed inputs changed')
    result['status'] = 'COLLECTED_KERNEL_DIAGNOSTIC_ONLY'
    write(out, 'fillet-diagnostic.json', result)
    return result


def rejoin_inputs(source, declared):
    names = {'unfilleted-local', 'source-back', 'rounded-local', 'retained-base',
             'rounded-addition', 'raw-finished', 'finished-local'}
    expected = {'construction-failure.json', *(name + '.brep' for name in names)}
    if set(declared) != expected:
        raise ValueError('Incomplete failed-rejoin input contract')
    source = Path(source)
    for name, value in declared.items():
        path = source / name
        if not stat.S_ISREG(path.lstat().st_mode) or digest(path) != value:
            raise ValueError('Failed-rejoin input identity differs: ' + name)
    failure = json.loads((source / 'construction-failure.json').read_text())
    context = failure['context']
    if (set(failure['shapes']) != names or context['radius_mm'] != 3.5
            or context['shoulder_width_mm'] != 4 or context['shoulder_depth_mm'] != 3.5
            or context['join_state'] != {'before_refinement': {'valid': False, 'solids': 1},
                                         'after_refinement': {'valid': False, 'solids': 1}}):
        raise ValueError('Saved rejoin is not the declared failed single-solid case')
    for name, row in failure['shapes'].items():
        if row['file'] != name + '.brep' or declared[row['file']] != row['sha256']:
            raise ValueError('Failed-rejoin shape seal differs')
    return failure


def diagnose_rejoin(study, out, source):
    """Read failed operands and two finite same-geometry joins, never a candidate."""
    config = json.loads((study.ROOT / '.agents/plans/hip-study/foot-geometry-inputs.json').read_text())
    cfg = config['rejoin_diagnostic']; declared = cfg['inputs']
    failure = rejoin_inputs(source, declared)
    out, before = prepare(study, out)
    import cadquery as cq
    from OCP.BRepCheck import BRepCheck_Analyzer
    shapes = {name: cq.Shape.importBrep(str(Path(source) / row['file']))
              for name, row in failure['shapes'].items()}
    result = {'scope': 'Saved own-shape BRepCheck and finite Boolean diagnosis only; not finished CAD/FEA acceptance',
              'status': 'INCOMPLETE_DIAGNOSTIC', 'source_sha256': before,
              'failed_source': cfg['source'], 'failed_archive_sha256': cfg['archive_sha256'],
              'frame': 'Original left-leg source frame, unrotated, millimetres', 'datums': cfg['datums'],
              'input_sha256': declared, 'saved': {}, 'reconstructed_stages': {}, 'variants': {},
              'fea_run': False, 'physical_qualification': False}
    def inspect(shape):
        check = BRepCheck_Analyzer(shape.wrapped)
        bb = shape.BoundingBox()
        row = {'valid': check.IsValid(), 'solids': len(shape.Solids()), 'kernel_volume_mm3': shape.Volume(),
               'bounds_mm': [bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax],
               'invalid_components': [], 'query_errors': []}
        for kind in ('Solids', 'Shells', 'Faces', 'Wires', 'Edges'):
            for i, part in enumerate(getattr(shape, kind)()):
                try:
                    item = check.Result(part.wrapped)
                    direct = [str(v) for v in item.Status()]
                    contexts = []
                    item.InitContextIterator()
                    while item.MoreShapeInContext():
                        flags = [str(v) for v in item.StatusOnShape()]
                        if any(not flag.endswith('BRepCheck_NoError') for flag in flags):
                            contexts.append({'type': str(item.ContextualShape().ShapeType()), 'statuses': flags})
                        item.NextShapeInContext()
                    if (not check.IsValid(part.wrapped) or contexts
                            or any(not flag.endswith('BRepCheck_NoError') for flag in direct)):
                        b = part.BoundingBox()
                        row['invalid_components'].append({'kind': kind, 'index': i, 'statuses': direct,
                            'contexts': contexts, 'bounds_mm': [b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax]})
                except Exception as error:
                    row['query_errors'].append({'kind': kind, 'index': i,
                                                'error': type(error).__name__ + ': ' + str(error)})
        return row
    for name, shape in shapes.items():
        result['saved'][name] = inspect(shape)
        write(out, 'rejoin-diagnostic.json', result)
    d = cfg['datums']
    if d != {'motor_x_mm': 75.0, 'motor_cut_r_mm': 66.0, 'protected_r_mm': 62.5,
             'plane_y_mm': -25.1, 'width_mm': 4.0, 'depth_mm': 3.5}:
        raise ValueError('Diagnostic datums differ from the pinned first-foot source')
    base, rounded, added = (shapes[n] for n in ('retained-base', 'rounded-local', 'rounded-addition'))
    bb = rounded.BoundingBox();lo, hi = bb.ymin-1, bb.ymax+1
    cut = (cq.Workplane('XZ', origin=(d['motor_x_mm'], hi, 0)).circle(d['motor_cut_r_mm'])
           .extrude(hi-lo).val())
    protected = (cq.Workplane('XZ', origin=(d['motor_x_mm'], hi, 0)).circle(d['protected_r_mm'])
                 .extrude(hi-lo).val())
    b = shapes['source-back'].BoundingBox();w,depth,y = d['width_mm'],d['depth_mm'],d['plane_y_mm']
    envelope = cq.Solid.makeBox(b.xlen+2*w, 2*depth, b.zlen+2*w,
                               cq.Vector(b.xmin-w, y-depth, b.zmin-w))
    patch_cut = (cq.Workplane('XZ', origin=(d['motor_x_mm'], y+depth+1, 0))
                 .circle(d['motor_cut_r_mm']).extrude(2*depth+2).val())
    difference = None
    def stage(name, build):
        try:
            shape = build();row = inspect(shape)
            result['reconstructed_stages'][name] = row
            path = out / (name + '.brep')
            if not shape.exportBrep(str(path)):
                raise ValueError('Diagnostic stage BREP export failed')
            row['brep'] = {'file': path.name, 'sha256': digest(path)}
            return shape
        except Exception as error:
            result['reconstructed_stages'].setdefault(name, {})['operation_error'] = type(error).__name__ + ': ' + str(error)
        finally:
            write(out, 'rejoin-diagnostic.json', result)
        return None
    stage('fillet_minus_unfilleted', lambda: rounded.cut(shapes['unfilleted-local']))
    difference = stage('rounded_minus_original', lambda: rounded.cut(shapes['source-back']))
    if difference is not None:
        stage('rounded_minus_original_after_motor_cut', lambda: difference.cut(patch_cut))
    variants = [('clean_operands', lambda: base.clean().fuse(added.clean()).clean()),
                ('restore_complete_rounded_back', lambda: base.fuse(rounded.cut(cut).clean()).clean())]
    for name, build in variants:
        try:
            candidate = build();row = inspect(candidate)
            result['variants'][name] = row
            path = out / (name + '.brep')
            if not candidate.exportBrep(str(path)):
                raise ValueError('Diagnostic Boolean BREP export failed')
            row['brep'] = {'file': path.name, 'sha256': digest(path)}
            # Raw Boolean facts are diagnostic, not a substitute for the full
            # finished-shape/interface/manufacturer acceptance pipeline.
            loss = base.cut(candidate);new = candidate.cut(base)
            violation = new.intersect(protected);outside = new.cut(envelope)
            row['boolean_facts'] = {'retained_loss_solids': len(loss.Solids()), 'retained_loss_mm3': loss.Volume(),
                'new_volume_mm3': new.Volume(), 'protected_intrusion_solids': len(violation.Solids()),
                'protected_intrusion_mm3': violation.Volume(), 'outside_envelope_solids': len(outside.Solids()),
                'outside_envelope_mm3': outside.Volume(), 'valid_intermediate_only': row['valid'] and row['solids']==1}
            result['variants'][name] = row
        except Exception as error:
            result['variants'].setdefault(name, {})['operation_error'] = type(error).__name__ + ': ' + str(error)
        write(out, 'rejoin-diagnostic.json', result)
    if before != inputs(study) or failure != rejoin_inputs(source, declared):
        raise ValueError('Rejoin diagnostic source/failed inputs changed')
    result['status'] = 'COLLECTED_REJOIN_DIAGNOSTIC_ONLY'
    write(out, 'rejoin-diagnostic.json', result)
    return result


def require_empty(shape, message):
    count, volume = len(shape.Solids()), shape.Volume()
    if count or volume != 0:
        raise ValueError(message + f' (solids={count}, volume_mm3={volume})')
    return {'solids': count, 'volume_mm3': volume}


def foot_regions(fb, diagnostics):
    import cadquery as cq
    from cadquery.occ_impl.shapes import TOLERANCE
    radius = float(fb.HIP['stop_foot_r'])
    width = radius + float(fb.STOP_FOOT_LAND)
    if radius <= 0 or diagnostics['radius_mm'] != radius:
        raise ValueError('Candidate radius is not the source design radius')
    blocks = diagnostics['blocks']
    if len(blocks) != 2 or {row['side'] for row in blocks} != {-1, 1}:
        raise ValueError('Candidate diagnostics omit a source backing foot')
    yf0 = fb.Y['frame'][0]
    zf = fb.frame_ring_r() + fb.HIP['flange_dz']
    result = []
    for k, row in enumerate(blocks):
        side = 1 if k == 0 else -1
        if row['side'] != side:
            raise ValueError('Backing-foot order differs from source stop ownership')
        px, pz = fb.stop_posts()[k]
        r = fb.STOP_BOSS_R + 0.3
        anchor = side * (fb.FLANGE_X - 1.0)
        # Independent source-parameter envelope of this backing block's footprint.
        xs = (px-r, px+r, anchor)
        zs = (pz-r, pz+r, zf+0.5, zf+fb.HIP['top_t']-1.0)
        if (row['shoulder_width_mm'] != width or row['shoulder_depth_mm'] != radius
                or row['shoulder_land_mm'] != fb.STOP_FOOT_LAND):
            raise ValueError('Candidate shoulder dimensions differ from the source design')
        # Explicitly allow the real 4 mm footprint and 3.5 mm depth shoulder;
        # this is a changed design region, never a tolerance/threshold waiver.
        lo = (min(xs)-width, yf0-radius, min(zs)-width)
        hi = (max(xs)+width, yf0+radius, max(zs)+width)
        envelope = cq.Solid.makeBox(*(b-a for a,b in zip(lo,hi)), cq.Vector(*lo))
        halos = []
        for edge in row['edges']:
            points = [edge[name] for name in ('start_mm', 'centre_mm', 'end_mm')]
            if edge['source_owner'] != 'backing-block outer side' or edge['type'] != 'LINE':
                raise ValueError('Foreign backing-foot contact record')
            if any(abs(point[1]-yf0) > TOLERANCE for point in points):
                raise ValueError('Backing-foot contact left the source web datum')
            a = [min(point[j] for point in points)-width-TOLERANCE for j in range(3)]
            b = [max(point[j] for point in points)+width+TOLERANCE for j in range(3)]
            halos.append(cq.Solid.makeBox(*(y-x for x,y in zip(a,b)), cq.Vector(*a)))
        if not halos:
            raise ValueError('Empty backing-foot contact region')
        region = halos[0].fuse(*halos[1:]).intersect(envelope)
        result.append(region)
    return result


def final_checks(baseline, candidate, fb, diagnostics):
    if not all(shape.isValid() and len(shape.Solids()) == 1 for shape in (baseline, candidate)):
        raise ValueError('Finished baseline/candidate must each be one valid solid')
    removed, added = baseline.cut(candidate), candidate.cut(baseline)
    retained = require_empty(removed, 'Finished candidate removed retained material')
    if added.Volume() <= 0:
        raise ValueError('Finished candidate made no actual addition')
    regions = foot_regions(fb, diagnostics)
    location = require_empty(added.cut(regions[0].fuse(regions[1])),
                             'Finished candidate added material outside the backing feet')
    voids = []
    for mx, _ in fb.motors():
        void = fb.ycyl(fb.STOP_EAR_CLEAR-fb.STOP_EAR_FILLET,
                      fb.Y['frame'][0]-fb.STOP_EAR_BACK-1, fb.Y['frame'][0]+1, mx).val()
        voids.append(require_empty(added.intersect(void), 'Finished candidate enters retained motor void'))
    return added, {'retained_material': retained, 'added_volume_mm3': added.Volume(),
                   'added_location': location, 'motor_voids': voids}


def negative_controls(baseline, candidate, fb, diagnostics):
    """Real finished-shape faults through the same acceptance functions; no source mutation."""
    import cadquery as cq
    from cadquery.occ_impl.shapes import TOLERANCE
    results = {}

    def rejected(name, function, expected):
        try:
            function()
        except ValueError as error:
            if expected not in str(error):
                raise ValueError(name + ' failed for an unrelated reason: ' + str(error)) from error
            results[name] = str(error)
        else:
            raise ValueError(name + ' fault was accepted')

    yf0 = fb.Y['frame'][0]
    outside = candidate.fuse(cq.Solid.makeBox(1, 2, 1, cq.Vector(30, yf0-1, 0)))
    if not outside.isValid() or len(outside.Solids()) != 1 or outside.Volume() <= candidate.Volume():
        raise ValueError('Out-of-region fault did not create a connected valid addition')
    rejected('connected_outside_foot', lambda: final_checks(baseline, outside, fb, diagnostics),
             'outside the backing feet')
    removed = candidate.cut(cq.Solid.makeBox(1, 1, 1, cq.Vector(30, yf0+1, 0)))
    if not removed.isValid() or len(removed.Solids()) != 1 or removed.Volume() >= candidate.Volume():
        raise ValueError('Old-material fault did not remove actual retained material')
    rejected('removed_retained_material', lambda: final_checks(baseline, removed, fb, diagnostics),
             'removed retained material')
    import hardware.cad.robot.gmi as gmi
    mount = fb.frame_mounts()
    x, z = mount['inserts_xz'][0]
    plug = fb.ycyl(gmi.FAST['M5']['insert_pilot']/2 + 10*TOLERANCE,
                  mount['plane_y']-0.5, mount['plane_y']+mount['pilot_depth']+0.5, x, z).val()
    filled = candidate.fuse(plug)
    if not filled.isValid() or len(filled.Solids()) != 1:
        raise ValueError('Filled-pilot fault is not one valid solid')
    rejected('filled_actual_pilot', lambda: require_same_mounts(
        measured_mounts(fb, candidate), measured_mounts(fb, filled)), 'pilot geometry changed')
    return results


def compare(study, out, baseline_dir, candidate_dir, motor_step):
    # Verify immutable case payloads and the actual manufacturer model before CAD import.
    if any(name.startswith('GYROPUP_') for name in os.environ):
        raise ValueError('Geometry study rejects inherited product parameters')
    before_compare = inputs(study)
    raw = []
    for directory in map(Path, (baseline_dir, candidate_dir)):
        row = json.loads((directory / 'geometry.json').read_text())
        brep = directory / row['brep']['file']
        if row['brep']['file'] != 'hip-frame.brep' or brep.parent.resolve() != directory.resolve() or digest(brep) != row['brep']['sha256']:
            raise ValueError('Geometry case BREP binding differs')
        raw.append((row, brep))
    from hardware.cad.legs.rs04_lug_checks import PRIVATE_HASHES
    if digest(motor_step) != PRIVATE_HASHES['robstride-rs-04/RS04.stp']:
        raise ValueError('Manufacturer RS04 STEP identity differs; no envelope fallback')
    out, before = prepare(study, out)
    if before_compare != before:
        raise ValueError('Geometry inputs changed during comparison preflight')
    import cadquery as cq
    import hardware.cad.legs.fivebar as fb
    import hardware.cad.robot.gmi as gmi
    old, new = [row for row, _ in raw]
    for row in (old, new):
        if row['units'] != 'mm':
            raise ValueError('Geometry case is not in the source millimetre frame')
        if row['inputs_sha256'] != before:
            raise ValueError('Case inputs are not this exact geometry source')
        if not (row['interfaces']['body']['ok'] and row['interfaces']['bed']['ok']):
            raise ValueError('Existing baseline/candidate body or bed check failed')
    old_hip, new_hip = dict(old['effective_hip']), dict(new['effective_hip'])
    baseline_params = json.loads((study.ROOT / '.agents/plans/hip-study/retained-foot-baseline.params.json').read_text())
    if new_hip != dict(fb.HIP) or old['params'] != baseline_params or old_hip != baseline_params or new['params']:
        raise ValueError('Geometry case parameters differ from the exact source/baseline choices')
    if old_hip.pop('stop_foot_r') != 0 or new_hip.pop('stop_foot_r') != fb.HIP['stop_foot_r'] or old_hip != new_hip:
        raise ValueError('Geometry study changed more than the single reviewed foot radius')
    baseline, candidate = [cq.Shape.importBrep(str(brep)) for _, brep in raw]
    require_same_mounts(measured_mounts(fb, baseline), measured_mounts(fb, candidate))
    added, checks = final_checks(baseline, candidate, fb, new['foot_diagnostics'])
    controls = negative_controls(baseline, candidate, fb, new['foot_diagnostics'])
    imported = cq.Compound.makeCompound(cq.importers.importStep(str(motor_step)).solids().vals())
    if len(imported.Solids()) != 43 or not imported.isValid():
        raise ValueError('Pinned manufacturer assembly must retain 43 valid solids')
    motor = imported.translate((0, 0, -gmi.STEP_FRAMES[fb.MOTOR]['output_z']))
    actual_motors = []
    from cadquery.occ_impl.shapes import TOLERANCE
    for (mx, _), front in zip(fb.motors(), (True, False)):
        placed = gmi.place(motor.rotate((0, 0, 0), (0, 0, 1), fb.step_turn(front)),
                           (mx, fb.Y['motor_out'], 0), (0, 1, 0))
        clearance = added.distance(placed)
        if clearance <= TOLERANCE:
            raise ValueError('Added material has no positive manufacturer-model clearance')
        actual_motors.append({'motor_x_mm': mx,
                             'new_intersection': require_empty(added.intersect(placed), 'New material intersects manufacturer motor'),
                             'added_clearance_mm': clearance,
                             'baseline_intersection_mm3': baseline.intersect(placed).Volume(),
                             'candidate_intersection_mm3': candidate.intersect(placed).Volume()})
    if inputs(study) != before:
        raise ValueError('Geometry inputs changed during final comparison')
    result = {'status': 'PASS_GEOMETRY_INTERFACE_SCREEN_ONLY', 'inputs_sha256': before,
              'units': 'mm',
              'baseline_brep_sha256': old['brep']['sha256'], 'candidate_brep_sha256': new['brep']['sha256'],
              'checks': checks, 'actual_motor_step_sha256': digest(motor_step), 'manufacturer_solids': 43,
              'actual_finished_shape_negative_controls': controls,
              'actual_motor_comparisons': actual_motors, 'fea_run': False, 'physical_qualification': False,
              'limits': ['Nominal model screen only; no manufacturing tolerance or physical fit qualification.',
                         'Baseline manufacturer-model intersections are reported, not silently qualified.',
                         'Existing source-bound engineering failures remain; no new FEA or strength result.']}
    write(out, 'geometry-comparison.json', result)
    return result
