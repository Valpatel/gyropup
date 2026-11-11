#!/usr/bin/env python3
"""One reviewed bounded execution; THIS PREPARED PACKET REFUSES TO RUN."""
import hashlib,json,os,re,subprocess,sys,time
from pathlib import Path
if not __debug__:
    raise SystemExit('Refusing Python optimization: assertion-based admission must remain enabled')
P=Path(__file__).resolve().parent
assert sys.argv[1:]==['--execute-reviewed'], 'Only the explicit reviewed invocation is accepted'
c=json.loads((P/'contract.json').read_text())
assert c['approved_for_execution'] is True, 'Prepared packet is not approved'
assert 'TODO' not in json.dumps(c) and 'UNBOUND' not in json.dumps(c), 'Unbound future identities'
seal=json.loads((P/'review-seal.json').read_text()) # deliberately absent until final GPT-6 review
assert seal['review_url'].startswith('https://github.com/Valpatel/gyropup/pull/')
for f in ['run.py','public-checklists.mjs','audit-pdfs.py','pdf-id-extractor.py','capture-diagnostics.mjs','clip-geometry.mjs','position-header.mjs','deployment-html.mjs','cleanup-observer.mjs','panel-selection.mjs','contract.json','provider-reference.json','release-binding.json','compiled-build.html','served-build.html','deployment-beacon.html']:
    assert hashlib.sha256((P/f).read_bytes()).hexdigest()==seal['files_sha256'][f], f+' differs from reviewed bytes'
unit=c['unit']+'.service'
assert re.fullmatch(r'gy318-public-acceptance-[a-z0-9-]+\.service',unit)
assert not Path(c['out']).exists(), 'Output namespace is spent'
# Deterministic admission before consuming the attempt marker or starting any unit.
def digest(file):return hashlib.sha256(Path(file).read_bytes()).hexdigest()
def git(repo,*args):return subprocess.check_output(['git','-C',repo,*args],timeout=10)
assert re.fullmatch('[a-f0-9]{40}',c['main']) and re.fullmatch('[a-f0-9]{40}',c['tree'])
assert re.fullmatch('[a-f0-9]{20}',c['assets']) and re.fullmatch('[a-f0-9]{40}',c['toolkit_commit'])
assert re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+',c['toolkit_release'])
assert git(c['repo'],'rev-parse',c['main']+'^{tree}').decode().strip()==c['tree']
assert git(c['repo'],'rev-parse','origin/main').decode().strip()==c['main']
assert git(c['toolkit_repo'],'rev-parse','refs/tags/'+c['toolkit_release']+'^{commit}').decode().strip()==c['toolkit_commit']
release=json.loads((P/'release-binding.json').read_text())
for key,value in [('tag',c['toolkit_release']),('commit',c['toolkit_commit']),('part_table_sha256',c['toolkit_part_table_sha256'])]:assert release[key]==value
assert release['release_url']=='https://github.com/Valpatel/cad-agent/releases/tag/'+c['toolkit_release']
assert hashlib.sha256(git(c['toolkit_repo'],'show',c['toolkit_commit']+':software/cadagent/webkit/part-table.js')).hexdigest()==c['toolkit_part_table_sha256']
expected_js={'/designer/build.js','/designer/portal-parts.js','/designer/kit/part-table.js','/designer/assembly/build-guide.js'}
assert set(c['sources'])==expected_js
for url,expected in c['sources'].items():
    assert re.fullmatch('[a-f0-9]{64}',expected)
    assert hashlib.sha256(git(c['repo'],'show',c['main']+':software/site'+url)).hexdigest()==expected
assert c['sources']['/designer/kit/part-table.js']==c['toolkit_part_table_sha256']
assert set(c['built'])=={'/designer/build.html','/designer/kit/part-table.css','/designer/portal-parts.css'}
for url,expected in c['built'].items():
    assert re.fullmatch('[a-f0-9]{64}',expected)
    assert digest(Path(c['final_build_root'])/url.lstrip('/'))==expected
built_version=json.loads((Path(c['final_build_root'])/'version.json').read_text())
assert built_version['revision']==c['main'] and built_version['assets']==c['assets']
h=c['deployed_html']
assert h['artifact']=='/designer/build.html' and h['request_path']=='/designer/build'
assert h['transformation']=='one exact byte insertion'
assert h['compiled_sha256']==c['built']['/designer/build.html']
assert h['compiled_fixture']=='compiled-build.html' and h['served_fixture']=='served-build.html' and h['insertion_file']=='deployment-beacon.html'
compiled=(Path(c['final_build_root'])/'designer/build.html').read_bytes()
assert (P/h['compiled_fixture']).read_bytes()==compiled
served=(P/h['served_fixture']).read_bytes();insertion=(P/h['insertion_file']).read_bytes()
assert digest(P/h['served_fixture'])==h['served_sha256'] and digest(P/h['insertion_file'])==h['insertion_sha256']
assert len(insertion)==h['insertion_bytes'] and isinstance(h['insertion_offset'],int) and 0<=h['insertion_offset']<=len(compiled)
assert served==compiled[:h['insertion_offset']]+insertion+compiled[h['insertion_offset']:], 'Unexpected compiled-to-served HTML difference'
assert c['schema']=='gyropup.public-checklists/2' and c['work_timeout_ms']==420000 and c['unit_runtime_seconds']==480
assert git(c['repo'],'rev-parse','HEAD').decode().strip()==c['main'] and not git(c['repo'],'status','--porcelain').strip(), 'Final source checkout changed'
assert c['helper']['source']=='tests/site/assembly/capture-diagnostics.mjs'
assert hashlib.sha256(git(c['repo'],'show',c['main']+':'+c['helper']['source'])).hexdigest()==c['helper']['sha256']
assert digest(P/'capture-diagnostics.mjs')==c['helper']['sha256']
assert c['framing_profile']=={'documentMode':'CSS1Compat','scrollingElement':'HTML','rootOverflowX':'hidden','rootOverflowY':'auto','visualScale':1,'visualOffsetLeft':0,'visualOffsetTop':0,'position_total_ms':5000,'sample_gap_ms':100,'geometry_tolerance_px':1,'scroll':{'behavior':'instant','block':'center','inline':'nearest'}}
assert {t['name'] for t in c['tables']}=={'queue','orders','made','pending'} and len(c['tables'])==4
for table in c['tables']:
    assert isinstance(table['count'],int) and table['count']>0 and isinstance(table['index'],int) and table['index']>=0
    assert len(table['ids'])==table['count'] and len(set(table['ids']))==table['count'] and table['requiredId'] in table['ids']
    assert all(isinstance(value,str) and value and not any(ch.isspace() for ch in value) for value in table['ids'])
    if table['name'] in ['queue','orders']:assert table['matchingIds'] and len(table['matchingIds'])==len(set(table['matchingIds'])) and set(table['matchingIds'])<=set(table['ids']) and table['requiredId'] in table['matchingIds']
    assert set(table['longNotes'])<=set(table['ids'])
    for notes in table['longNotes'].values():assert notes and all(isinstance(value,str) and len(value.encode('utf-16-le'))//2>240 for value in notes.values())
    if table['name']=='orders':assert table['longNotes'], 'Bind independently reviewed long-note groups'
    assert set(table['pdfPages'])=={'A4','Letter'} and all(isinstance(n,int) and n>0 for n in table['pdfPages'].values())
    assert table['requiredFields'] and set(table['requiredFields'])<=set(table['ids'])
    for fields in table['requiredFields'].values():
        assert fields and all(isinstance(column,str) and column for column in fields)
        for fragments in fields.values():assert isinstance(fragments,list) and fragments and all(isinstance(value,str) and value.strip() for value in fragments)
provider=json.loads((P/'provider-reference.json').read_text())
for key in ['node','playwright','chrome','capture_protocol']:assert digest(provider[key]['path'])==provider[key]['sha256']
assert subprocess.check_output([provider['node']['path'],'--version'],text=True,timeout=5).strip()==provider['node']['version']
assert json.loads((Path(provider['playwright']['path']).parent/'package.json').read_text())['version']==provider['playwright']['version']
def show():
    r=subprocess.run(['systemctl','--user','show',unit,'-p','LoadState','-p','ActiveState','-p','SubState','-p','MainPID','-p','Result','-p','ExecMainStatus','-p','InvocationID','-p','ControlGroup'],text=True,capture_output=True,timeout=5)
    return {'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'properties':dict(line.split('=',1) for line in r.stdout.splitlines() if '=' in line)}
assert show()['properties'].get('LoadState')=='not-found', 'Do not use an already existing unit'
with (P/'execution-attempt.json').open('x') as attempt:
    json.dump({'started':time.time(),'unit':unit,'review':seal['review_url']},attempt,indent=2)
provider=json.loads((P/'provider-reference.json').read_text())
command=['systemd-run','--user','--unit='+unit,'--wait','--pipe',
'--property=CPUQuota=200%','--property=MemoryMax=3G','--property=MemorySwapMax=0',
'--property=TasksMax=512','--property=RuntimeMaxSec=480','--property=TimeoutStopSec=5','--property=KillMode=control-group',provider['node']['path'],str(P/'public-checklists.mjs')]
def execute_owned_unit():
    """Attempt once and retain collector failures even when launch/stop fails."""
    rc=1;exception=None;collector_errors=[]
    def collector_error(stage,error):
        collector_errors.append({'stage':stage,'type':type(error).__name__,'message':str(error)})
    try:
        with (P/'run.log').open('x') as log:
            try:
                rc=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=495).returncode
            except (subprocess.TimeoutExpired,KeyboardInterrupt) as exc:
                exception=type(exc).__name__
                try:
                    stopped=subprocess.run(['systemctl','--user','stop',unit],stdout=log,stderr=subprocess.STDOUT,timeout=10)
                    if stopped.returncode:collector_error('stop',RuntimeError('exact-unit stop exited '+str(stopped.returncode)))
                except (OSError,subprocess.SubprocessError,KeyboardInterrupt) as stop_error:
                    collector_error('stop',stop_error)
    except (OSError,subprocess.SubprocessError,KeyboardInterrupt) as launch_error:
        exception=type(launch_error).__name__
        collector_error('launch-or-log',launch_error)
    finally:
        # A collected unit's defaults never establish its historical limits.
        terminal={'properties':{}};live=None;cg=None;processes=[];cgroup_checked=False
        try:terminal=show()
        except (OSError,subprocess.SubprocessError,KeyboardInterrupt) as query_error:
            collector_error('terminal-query',query_error)
        try:
            live_path=Path(c['out'])/'live-unit.json'
            live=json.loads(live_path.read_text()) if live_path.exists() else None
            cg=live['properties']['ControlGroup'] if live else None
            if cg:
                assert isinstance(cg,str) and cg.startswith('/') and cg.endswith('/'+unit) and '..' not in Path(cg).parts
                cgroup_root=Path('/sys/fs/cgroup')/cg.lstrip('/')
                if cgroup_root.exists():
                    assert (cgroup_root/'cgroup.procs').is_file()
                    processes=[v for f in cgroup_root.rglob('cgroup.procs') for v in f.read_text().splitlines() if v]
                cgroup_checked=True
        except (OSError,ValueError,KeyError,TypeError,AssertionError) as receipt_error:
            collector_error('live-receipt-or-cgroup',receipt_error)
        props=terminal['properties'];absent=props.get('LoadState')=='not-found'
        terminal_ok=absent or (props.get('MainPID')=='0' and (props.get('ActiveState'),props.get('SubState')) in [('inactive','dead'),('failed','failed')])
        receipt={'returncode':rc,'exception':exception,'collector_errors':collector_errors,'live_unit_captured':bool(live),'terminal':terminal,'owned_cgroup':cg,'owned_cgroup_checked':cgroup_checked,'owned_cgroup_processes':processes,'terminal_empty_or_absent':terminal_ok and cgroup_checked and not processes}
        try:(P/'terminal-cleanup.json').write_text(json.dumps(receipt,indent=2))
        except OSError as write_error:
            collector_error('receipt-write',write_error)
            print(json.dumps(receipt),file=sys.stderr)
            raise
    return receipt
receipt=execute_owned_unit()
assert receipt['terminal_empty_or_absent'], 'Owned cgroup terminal state is not established; do not rerun browser work'
assert not receipt['collector_errors'], 'Collector failed; preserve the receipt and recover read-only, never rerun browser work'
assert receipt['returncode']==0, 'Browser execution failed; preserve its report and logs'
report=json.loads((Path(c['out'])/'report.json').read_text());assert report['pass'] is True
subprocess.run([sys.executable,str(P/'audit-pdfs.py'),c['out']],check=True,timeout=90)
print('Browser, live-unit and terminal cleanup checks passed; inspect PDF audit and screenshots before acceptance.')
