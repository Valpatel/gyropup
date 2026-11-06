"""Bounded, output-preserving lug/support regeneration; no adoption or qualification."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, shutil, stat, subprocess, sys, tarfile, time

ROOT = Path.cwd().resolve()
sys.path.insert(0, str(ROOT))
os.environ['PYTHONPATH'] = str(ROOT)
OUT = Path(os.environ['FLEET_RUN_OUT']).resolve()
PRIVATE = Path(os.environ['FLEET_RUN_IN']) / 'vendor'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')

def tracked():
    names = subprocess.check_output(['git','ls-files','-z'], text=True).split('\0')
    return {n: sha(ROOT/n) for n in names if n}

def inventory(directory):
    rows = {}
    for p in sorted(directory.rglob('*')):
        mode = p.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError('Nonregular output: '+p.relative_to(directory).as_posix())
        rows[p.relative_to(directory).as_posix()] = {'bytes':p.stat().st_size,'sha256':sha(p)}
    return rows

def preserve(label, directory):
    if not directory.exists():
        return
    rows = inventory(directory)
    save(label+'-inventory.json', rows)
    with tarfile.open(OUT/(label+'.tgz'),'w:gz') as archive:
        for n in rows:
            archive.add(directory/n, arcname=n, recursive=False)
    save(label+'-archive.json', {'sha256':sha(OUT/(label+'.tgz')),'files':len(rows)})

def phase(name, command, expected=0, timeout=3600):
    started = time.monotonic()
    with (OUT/(name+'.log')).open('w') as stream:
        try:
            run = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                 timeout=timeout, check=False)
            result = {'command':command,'exit':run.returncode,'seconds':time.monotonic()-started,
                      'expected_exit':expected}
        except subprocess.TimeoutExpired:
            result = {'command':command,'timed_out':True,'seconds':time.monotonic()-started,
                      'expected_exit':expected}
    results['phases'][name] = result
    save('result.json', results)
    assert result.get('exit') == expected, name+': incomplete or unexpected exit; inspect retained log'

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--head', required=True)
args = parser.parse_args()
results = {'source':args.head,'status':'FAILED','phases':{},'scope':'actual bounded geometry generation only; no adoption/physical qualification'}
initial = None
protected_before = None
lug = OUT/'lug-candidate'
support = OUT/'support-candidate'
replacement = {}
try:
    assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip() == args.head
    assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip()
    assert 'GYROPUP_CAD_PARAMS' not in os.environ
    initial = tracked()
    save('tracked-before.json', initial)
    protected_before = inventory(ROOT/'hardware')
    save('hardware-before.json',protected_before)
    from hardware.cad.manufacturing import print_provenance as provenance
    from hardware.cad.legs import rs04_lug_checks as lugs
    before = provenance.snapshot(ROOT)
    save('cad-inputs-before.json', before)
    assert len(before['files']) == 92
    assert before['versions'] == {'cad-agent':'0.4.2','cadquery':'2.8.0','cadquery-ocp':'7.9.3.1.1','numpy':'2.5.4'}
    assert before['toolkit_sources_sha256'] == lugs.TOOLKIT_SOURCES
    assert before['GYROPUP_CAD_PARAMS_sha256'] is None
    assert lugs.private_inputs(PRIVATE) == lugs.PRIVATE_HASHES
    save('private-inputs.json', lugs.PRIVATE_HASHES)
    phase('lug-controls-before', [sys.executable,'-B','tests/hardware/interfaces/test-rs04-lug-stacks.py','--pure'], timeout=120)
    phase('support-controls-before', [sys.executable,'-B','tests/hardware/interfaces/test-rs04-support-probe.py','--pure'], timeout=120)
    # Exit1 is expected only for the independently verified complete known-failing verdict below.
    try:
        phase('lug-generate',[sys.executable,'-B','hardware/cad/legs/rs04_lug_checks.py','--vendor-root',str(PRIVATE),'--out',str(lug),'--export'],expected=1,timeout=5400)
    finally:
        preserve('lug-candidate',lug)
    data = json.loads((lug/'checks.json').read_text())
    assert lugs.validate_receipt(data,lug,ROOT)
    assert data['counts'] == {'pass':322,'warn':40,'fail':8}
    phase('lug-real-consumer',[sys.executable,'-B','tests/hardware/interfaces/test-rs04-lug-stacks.py','--receipt',str(lug/'checks.json')],timeout=120)
    expected = {'checks.json',*(p+'.'+ext for p in lugs.OUTPUT_PARTS for ext in ('step','stl'))}
    assert set(inventory(lug)) == expected
    # Feed the REAL completed failing lug receipt to its unchanged support consumer.
    # This temporary clone replacement is explicitly recorded, not a repository adoption.
    target = ROOT/'hardware/exports/leg/rs04-mounting-fit'
    original = OUT/'original-lug-inputs'
    original.mkdir()
    for n in sorted(expected):
        assert (target/n).is_file()
        shutil.copyfile(target/n,original/n)
        replacement[(target/n).relative_to(ROOT).as_posix()] = sha(lug/n)
        shutil.copyfile(lug/n,target/n)
    preserve('original-lug-inputs',original)
    save('temporary-real-lug-inputs.json',replacement)
    try:
        phase('support-generate',[sys.executable,'-B','docs/research/rs04-support/probe.py','--vendor-root',str(PRIVATE),'--out',str(support)],timeout=3600)
    finally:
        preserve('support-candidate',support)
    probe = json.loads((support/'probe.json').read_text())
    assert probe['probe_complete'] is True and probe['engineering_pass'] is False
    assert probe['source_inputs'] == probe['source_inputs_after']
    assert probe['source_inputs']['project'] == before
    assert set(inventory(support)) == {'probe.json',*(name+'.step' for name in probe['candidate_rings'])}
    assert len(probe['candidate_rings']) == 8
    # Actual pinned inventory consumer: a changed content identity is a failure pending review.
    phase('support-real-consumer',[sys.executable,'-B','tests/hardware/interfaces/test-rs04-support-probe.py','--receipt',str(support/'probe.json')],timeout=120)
    assert provenance.snapshot(ROOT) == before
    results['status'] = 'PASS_SCOPED'
except BaseException as exc:
    results['error'] = type(exc).__name__+': '+str(exc)
    raise
finally:
    try:
        if initial is not None:
            current = tracked()
            save('tracked-after-with-temporary-lug-input.json',current)
            expected_current = initial | replacement
            unchanged = current == expected_current
            if replacement:
                for n in replacement:
                    shutil.copyfile(OUT/'original-lug-inputs'/Path(n).name,ROOT/n)
            final = tracked()
            save('tracked-final-restored.json',final)
            assert final == initial, 'Final tracked bytes not restored'
            assert unchanged, 'Unexpected source/output mutation (declared lug input was restored)'
            protected_after = inventory(ROOT/'hardware')
            save('hardware-final-restored.json',protected_after)
            assert protected_after == protected_before, 'Complete hardware path/byte set changed'
            results['final_tracked_identity_restored'] = True
            results['complete_hardware_identity_restored'] = True
    except BaseException as exc:
        results['status'] = 'FAILED'
        results['final_guard_error'] = type(exc).__name__+': '+str(exc)
        save('result.json',results)
        raise
    save('result.json',results)
