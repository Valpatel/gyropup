from pathlib import Path
import collections, hashlib, json, stat, sys, tarfile

# Fixed historical identities from native-264/members.json and the sealed full plan.
PRIOR_REPORT_SHA256 = '0cfa0ef2f07ed9278855ac1579d911a246a01d9e134d7bad3b69f7d74c99d49d'
PRIOR_REPORT_BYTES = 17899
FULL_PLAN_SHA256 = '1316f2e4e315ee2cd45ed805d92ee219699a311bf09bb8d106148145fb8a96cc'


def validate_prior_queries(prior, full):
    """Check the recorded prefix against the independently sealed plan, not counts alone."""
    expected = full['queries'][:42]
    rows = prior['queries']
    assert len(full['queries']) == 90 and len({q['id'] for q in full['queries']}) == 90
    assert [q['id'] for q in rows] == [q['id'] for q in expected], 'Prior report query prefix differs from plan'
    assert prior['complete'] is False and prior['pass'] is False
    assert all(prior[k] is False for k in ('all_assembly_paths_checked', 'support_stability_verified', 'physical_assembly_verified'))
    assert prior['inputs']['plan_sha256'] == FULL_PLAN_SHA256
    assert prior['inputs']['core_revision'] == '5c29c9e2abf2562baa72a05248f23de054b8241e'
    assert dict(collections.Counter(q['result']['state'] for q in rows)) == {'clear': 36, 'seat': 6}, 'Prior report states differ'
    for row, query in zip(rows, expected):
        state = row['result']['state']
        assert row['result']['part'] == query['fixed'] and row['result']['travel_mm'] == query['travel_mm']
        assert row['terminal_only'] is (state == 'seat')
        assert row['transient_path_complete'] is (state == 'clear')
    return prior


def validate_prior_report(path, full):
    raw = path.read_bytes()
    assert len(raw) == PRIOR_REPORT_BYTES and hashlib.sha256(raw).hexdigest() == PRIOR_REPORT_SHA256, 'Prior report byte seal differs from retained264'
    return validate_prior_queries(json.loads(raw), full)


def main():
    full_raw = Path(sys.argv[3]).read_bytes()
    assert hashlib.sha256(full_raw).hexdigest() == FULL_PLAN_SHA256, 'Full plan byte seal differs'
    prior = validate_prior_report(Path(sys.argv[4]), json.loads(full_raw))
    p = Path(sys.argv[1]) / 'out'
    b = p / 'control-pair-study'
    load = lambda f: json.loads(f.read_bytes())
    sha = lambda data: hashlib.sha256(data).hexdigest()
    f = load(p / 'final-result.json')
    manifest = load(p / 'control-pair-study-members.json')
    assert f['status'] == 'COMPLETE_SCOPED_NATIVE_CONTROL_STUDY'
    assert f['source'] == '05bf810d245ca1b938f9283a10dde624ed2104ba'
    assert f['core'] == '5c29c9e2abf2562baa72a05248f23de054b8241e'
    assert f['recipe_sha256'] == 'd73266cd45159c4b9433ccb37c18e00c65b6f09c7b14af751e4c31ec324777f9'
    assert not f['adoption_approved'] and not f['errors'] and f['processes_quiescent']
    assert len(f['guards']) == 10 and all(f['guards'].values())
    assert f['phases']['native-controls']['timeout_seconds'] == 120
    assert f['phases']['native-controls']['exit'] == 0
    assert all(v['exit'] == 0 and v['process_cleanup']['group_gone'] for v in f['phases'].values())
    for role in ('runtime', 'toolkit', 'candidate', 'guides', 'frame-input', 'input-seals', 'hardware', 'tracked', 'playback-core'):
        assert load(p / f'{role}-before.json') == load(p / f'{role}-after.json'), role
    archive = p / 'control-pair-study-produced.tgz'
    assert sha(archive.read_bytes()) == f['control_archive_sha256'] == '17488f0972a382f3658bf6d51bf47444b9d9a984e471741634c315e433448dac'
    seen = set()
    with tarfile.open(archive) as t:
        for m in t:
            assert m.isfile() and m.name not in seen and not m.name.startswith('/') and '..' not in Path(m.name).parts
            data = t.extractfile(m).read()
            local = b / m.name
            assert manifest[m.name] == dict(sha256=sha(data), bytes=len(data), mode=m.mode)
            assert m.mode == 0o600 and local.is_file() and not local.is_symlink()
            assert stat.S_IMODE(local.stat().st_mode) == 0o640 and data == local.read_bytes()
            seen.add(m.name)
    assert seen == set(manifest) == {x.relative_to(b).as_posix() for x in b.rglob('*') if x.is_file()}
    original_manifest = Path(sys.argv[2])
    assert sha(original_manifest.read_bytes()) == 'd0dc620a44bd8cf806abf80c6483b8620cc0161b18052adde756f42970954755'
    original = load(original_manifest)
    for name, row in original.items():
        data = (b / 'inputs' / name).read_bytes()
        assert sha(data) == row['sha256'] and len(data) == row['bytes']
    full = load(b / 'plan.json')
    plan = load(b / 'query-plan.json')
    selection = load(b / 'selection.json')
    source = load(b / 'source.json')
    report = load(b / 'report.json')
    phase = load(b / 'phase.json')
    expected_ids = ['f2bd165061ce41d9e225a5d2ed0b42fcf4b882e7fbe393f474089ff75afd519e', '6b8e90982dd9f33b2bef4654d5d234c1d9d2a825198245b14d86df7a52bac254']
    for file, key, expected in (
        ('plan.json', 'plan_sha256', '1316f2e4e315ee2cd45ed805d92ee219699a311bf09bb8d106148145fb8a96cc'),
        ('query-plan.json', 'query_plan_sha256', 'c8c2f01464bd49f5cd464637b277032efe761fb3e76cd216e8c146ded25d3cc6'),
        ('selection.json', 'selection_sha256', 'ecb26e9ddd47a023664447e4078dbc34bd960e5b19c0194dfcf631503ec2a945')):
        assert sha((b / file).read_bytes()) == source[key] == expected
    assert (b / 'plan.json').read_bytes() == Path(sys.argv[3]).read_bytes()
    assert source['adapter_sha256'] == '68712d70f24061fa65e433576619318eec201d1cb6c3d4632d911a3f4295c712'
    assert source['core_revision'] == f['core'] and source['max_samples'] == 256 and source['max_step_mm'] == 1.0
    assert source == report['inputs']
    assert len(full['queries']) == 90 and len(full['predecessor_rows']) == 1126
    assert full['candidate_rows'] == 74 and full['excluded_rows'] == 1052 and len(full['controls']) == 22
    by_id = {q['id']: q for q in full['queries']}
    assert selection['query_ids'] == source['selected_query_ids'] == expected_ids
    assert plan['queries'] == [by_id[i] for i in expected_ids]
    assert report['selection'] == plan['selection']
    assert set(plan['selection']['unselected_query_ids']) == set(by_id) - set(expected_ids)
    assert len(plan['selection']['unselected_query_ids']) == 88
    assert report['complete'] and not report['pass'] and report['unchecked_queries'] == []
    assert phase['state'] == 'complete' and phase['total_pairs'] == phase['completed_pairs'] == 2 and not phase['gate_pass']
    assert all(report[key] is False for key in ('all_assembly_paths_checked', 'physical_assembly_verified', 'support_stability_verified'))
    assert load(b / 'native-cli-exit.json')['actual_native_exit'] == 1
    raw = (b / 'progress.jsonl').read_bytes()
    assert raw.endswith(b'\n')
    events = [json.loads(line) for line in raw.splitlines()]
    assert len(events) == 472 and [e['sequence'] for e in events] == list(range(1, 473))
    assert phase['progress_flushed_records'] == phase['progress_fsync_acknowledged_records'] == len(events)
    assert not phase['progress_tail_uncertain'] and all(e['inputs'] == source for e in events)
    pairs = [e['core_event'] for e in events if e['core_event']['event'] == 'pair']
    assert len(pairs) == 4 and not any(e['core_event']['event'] == 'operation' for e in events)
    for i, q in enumerate(plan['queries']):
        start, end = pairs[i * 2:i * 2 + 2]
        assert start['state'] == 'starting' and end['state'] == 'complete'
        for event in (start, end):
            assert event['pair_index'] == i and event['instance'] == q['moving'] and event['obstacle'] == q['fixed']
            assert event['project_study'] == dict(query_id=q['id'], contexts=q['contexts'])
        result = report['queries'][i]
        assert result['id'] == q['id'] and result['result'] == end['result']
        assert not result['terminal_only'] and not result['transient_path_complete']
        hit = result['result']
        assert hit['state'] == 'blocked' and hit['samples'] == 2 and hit['travel_mm'] == 60
        assert hit['first_contact_mm'] == [None, 60.0] and hit['overlap_mm3'] > 0
    assert report['counts'] == dict(collections.Counter(q['result']['state'] for q in report['queries'])) == {'blocked': 2}
    assert report['world_stats'] == dict(kernel_queries=4, memo_hits=0, cache_hits=0, tool_sweeps=0)
    prior_ids = {q['id'] for q in prior['queries']}
    assert len(prior_ids) == 42 and not prior_ids.intersection(expected_ids)
    combined = {q['id']: q['result']['state'] for q in prior['queries'] + report['queries']}
    assert len(combined) == 44
    summary = dict(artifact_audit_pass=True, scoped_execution_complete=True, actual_native_exit=1,
        source=f['source'], core=f['core'], archive_sha256=f['control_archive_sha256'],
        files=len(seen), original_input_files=len(original), selected_counts=report['counts'],
        hits=report['queries'], prior_completed=42, distinct_completed_across_both=44,
        uncompleted_full_plan=46, unselected_this_job=88, progress_records=len(events),
        tail_uncertain=False, assembly_qualified=False, all_assembly_paths_checked=False,
        support_stability_verified=False, physical_assembly_verified=False)
    if len(sys.argv) > 5:
        with Path(sys.argv[5]).open('x') as receipt:
            receipt.write(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
