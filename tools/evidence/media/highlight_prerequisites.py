"""Pure receipt and output prerequisites; no encoder or operational entrypoint."""


def historical_revisions(check, capture_revision):
    """Include the independently recorded field and video producer revisions."""
    recorded = [check.read(check.project_path(check.E1 + name))['source_revision']
                for name in ('field-receipt.json', 'video-receipt.json')]
    revisions = (capture_revision, *recorded, check.LEG_REVISION,
                 'e93b3bbce57ee36fc966e8ba4513f05273a75967')
    if not all(check.full_revision(revision) for revision in revisions):
        raise ValueError('Use immutable capture, field and video source revisions')
    return tuple(dict.fromkeys(revisions))


def candidate_names(check):
    return set(check.MOVIES + [check.POSTER, 'capture-receipt.json',
                              'capture-frames.json', 'receipt.json'])


def validate_recorded_stage(check, declared, current_sources, capture_revision):
    """Preserve the sealed capture-era bindings while refreshing only E1 inserts.

    The caller must first run the full current validate_source_bindings guard.
    Capture metadata is never rewritten to attribute a new insert to old frames.
    """
    if declared.get('source') != capture_revision or not check.full_revision(capture_revision):
        raise ValueError('Stage must retain its immutable capture source')
    recorded = declared.get('source_hashes')
    if not isinstance(recorded, dict) or set(recorded) != set(current_sources):
        raise ValueError('Incomplete historical stage source closure')
    for name, digest in recorded.items():
        if check.git_sha(capture_revision, name) != digest:
            raise ValueError('Historical stage source differs: ' + name)
    changed = {name for name in recorded if recorded[name] != current_sources[name]}
    allowed = {check.source_for_public(check.E1 + name) for name in
               ('field-receipt.json', 'hip_frame-E1.json', 'video-receipt.json', 'hip-frame-e1.mp4')}
    allowed.add(check.source_for_public('exports/leg/fea/media.json'))
    if not changed <= allowed:
        raise ValueError('Non-E1 source changed since the accepted stage')
    return sorted(changed)
