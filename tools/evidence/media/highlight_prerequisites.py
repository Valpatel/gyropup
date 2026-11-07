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
