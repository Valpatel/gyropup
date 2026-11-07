#!/usr/bin/env python3
"""One reviewed detached STEP inspection; no auto-repeat on uncertainty."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,shlex,subprocess
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def command(argv,timeout=30,cwd=None):
 r=subprocess.run(argv,text=True,capture_output=True,timeout=timeout,cwd=cwd)
 assert r.returncode==0,(argv[0],r.returncode,r.stderr[-1000:])
 return r.stdout
SOURCE_FILES={'.agents/plans/hip-study/collect-step-topology.py',
              '.agents/plans/hip-study/inspect-step-worker.py',
              '.agents/plans/hip-study/topology-inputs.json',
              '.agents/plans/hip-study/launch-step-topology.sh',
              '.agents/plans/hip-study/submit-topology-once.py',
              '.agents/plans/leg-control/e1-runtime-contract.json',
              'tests/evidence/test-study-media.py'}
REMOTE=r'''
from pathlib import Path
import hashlib,json,os,shutil,stat,subprocess,sys,time
c=json.load(sys.stdin);home=Path.home();run=home/'gyropup-mechanical-runs'/c['run_name']
assert not run.exists(),'Exclusive run already exists; no repeat'
prior=home/'gyropup-mechanical-runs'/c['prior_complete_run_name']
assert (prior/'exit.done').read_text().strip()=='0'
assert json.loads((prior/'outer-group-state.json').read_text())['group_gone']is True
old=json.loads((prior/'out/result.json').read_text());assert old['status']=='PASS_FIELD_CANDIDATE_ONLY' and old['source']==c['prior_source']
assert all(v.get('process_cleanup',{}).get('group_gone')is True for v in old['phases'].values())
oldpid=int((prior/'launcher.pid').read_text())
oldcmd=Path('/proc')/str(oldpid)/'cmdline'
if oldcmd.exists():
 assert c['prior_complete_run_name'].encode() not in oldcmd.read_bytes(),'Prior owned launcher remains active'
assert len(os.sched_getaffinity(0))>=4
cpus=sorted(os.sched_getaffinity(0))[:4];assert len(cpus)==4 and len(set(cpus))==4
assert os.getloadavg()[0]<=8
mem={k:int(v.split()[0])for k,v in (x.split(':',1)for x in Path('/proc/meminfo').read_text().splitlines())}
assert mem['MemAvailable']>=32*1024*1024
assert shutil.disk_usage(home).free>=20*1024**3
assert c['run_name'].startswith('20261107-hip-step-topology-') and '/'not in c['run_name']
assert hashlib.sha256(json.dumps(c['runtime'],sort_keys=True).encode()).hexdigest()==c['runtime_sha256']
# Read-only original runtime identity before any source checkout/dependencies.
rt=c['runtime'];assert (Path(rt['venv'])/'bin/python').is_file()
for n,path in rt['libraries'].items():assert Path(path).is_file()
assert subprocess.check_output(['git','-C',rt['toolkit'],'rev-parse','HEAD'],text=True).strip()=='50d4921a5ab26c7750a869ed41c9a4346ef1379c'
assert not subprocess.check_output(['git','-C',rt['toolkit'],'status','--porcelain'],text=True).strip()
os.umask(0o077);run.mkdir(mode=0o700)
for n in ['home','out','tmp']: (run/n).mkdir(mode=0o700)
preflight={'load':os.getloadavg(),'available_kib':mem['MemAvailable'],'cpus':cpus,'runtime_sha256':c['runtime_sha256'],'head':c['head']}
(run/'host-preflight.json').write_text(json.dumps(preflight,indent=2)+'\n')
(run/'runtime.json').write_text(json.dumps(rt,indent=2)+'\n')
env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_COUNT':'0','GIT_ASKPASS':'/bin/false','GIT_OPTIONAL_LOCKS':'0'}
for name in ('GIT_DIR','GIT_WORK_TREE','GIT_COMMON_DIR','GIT_INDEX_FILE','GIT_NAMESPACE'):env.pop(name,None)
with (run/'bootstrap.log').open('x')as log:
 for argv,limit in [(['git','init','-q',str(run/'src')],30),(['git','-C',str(run/'src'),'remote','add','origin','https://github.com/Valpatel/gyropup.git'],30),(['git','-C',str(run/'src'),'-c','credential.helper=','fetch','-q','--depth','1','origin',c['head']],600),(['git','-C',str(run/'src'),'checkout','-q','--detach','FETCH_HEAD'],30)]:
  subprocess.run(['timeout','--signal=TERM','--kill-after=10s',str(limit)+'s',*argv],env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=limit+15)
 root=run/'src'
 assert subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()==c['head']
 assert not subprocess.check_output(['git','-C',str(root),'status','--porcelain'],text=True).strip()
 for n,h in c['files'].items():assert hashlib.sha256((root/n).read_bytes()).hexdigest()==h
 launcher=root/'.agents/plans/hip-study/launch-step-topology.sh'
 clean={'PATH':'/usr/local/bin:/usr/bin:/bin','LANG':'C.UTF-8','HOME':str(run/'home'),'TMPDIR':str(run/'tmp'),'TOPOLOGY_RUN':str(run),'TOPOLOGY_HEAD':c['head'],'TOPOLOGY_CPUS':','.join(map(str,cpus)),'TOPOLOGY_RUNTIME':str(run/'runtime.json'),'GIT_OPTIONAL_LOCKS':'0','GIT_TERMINAL_PROMPT':'0','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_COUNT':'0','GIT_ASKPASS':'/bin/false'}
 # Recheck host headroom after source bootstrap, immediately before launch.
 assert os.getloadavg()[0]<=8
 fresh_mem={k:int(v.split()[0])for k,v in (x.split(':',1)for x in Path('/proc/meminfo').read_text().splitlines())}
 assert fresh_mem['MemAvailable']>=32*1024*1024
 assert shutil.disk_usage(home).free>=20*1024**3
 (run/'host-before-launch.json').write_text(json.dumps({'load':os.getloadavg(),'available_kib':fresh_mem['MemAvailable'],'cpus':cpus},indent=2)+'\n')
 with (run/'launcher.log').open('x')as output:
  proc=subprocess.Popen(['/usr/bin/nohup','/usr/bin/nice','-n','10','/bin/bash',str(launcher)],env=clean,cwd=root,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
 (run/'launcher.pid').write_text(str(proc.pid)+'\n')
 started={'head':c['head'],'run':str(run),'launcher_pid':proc.pid,'cpus':cpus,'command':['bash',str(launcher)],'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'adoption_approved':False}
 (run/'started.json').write_text(json.dumps(started,indent=2)+'\n')
 print(json.dumps(started))
'''

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--execute',action='store_true');p.add_argument('--review-url',required=True)
 p.add_argument('--operator-sha256',required=True);p.add_argument('--config-sha256',required=True)
 p.add_argument('--private-config',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True)
 args=p.parse_args(argv);assert args.execute,'Explicit execution required'
 CONFIG=args.private_config.resolve();RECEIPT=args.receipt.resolve()
 assert sha(__file__)==args.operator_sha256 and sha(CONFIG)==args.config_sha256
 assert args.review_url.startswith('https://github.com/Valpatel/gyropup/')
 assert not RECEIPT.exists()
 cfg=json.loads(CONFIG.read_text());root=Path(cfg['repo']).resolve()
 assert not RECEIPT.is_relative_to(root) and RECEIPT.parent.is_dir()
 assert set(cfg['files'])==SOURCE_FILES
 assert command(['git','rev-parse','HEAD'],cwd=root).strip()==cfg['head']
 assert not command(['git','status','--porcelain'],cwd=root).strip()
 for name,value in cfg['files'].items():assert sha(root/name)==value
 assert sha(cfg['fleet_cli'])==cfg['fleet_cli_sha256']
 pr=json.loads(command(['gh','api','--method','GET','repos/Valpatel/gyropup/pulls/'+str(cfg['pr'])]))
 assert pr['state']=='open' and not pr['merged'] and pr['draft']
 assert pr['head']['sha']==cfg['head'] and pr['head']['ref']==cfg['branch']
 assert pr['base']['ref']=='dev' and pr['base']['sha']==cfg['base']
 assert json.loads(command(['gh','api','--method','GET','repos/Valpatel/gyropup/issues/8']))['state']=='open'
 nodes=command([cfg['fleet_cli'],'nodes']);queue=command([cfg['fleet_cli'],'queue'])
 rows=[n.split()for n in nodes.splitlines()[1:]if n.strip()];selected=[r for r in rows if r[-1]==cfg['role']]
 assert len(selected)==1 and selected[0][0]==cfg['node']
 row=selected[0];assert row[1]=='IDLE' and row[2]=='0/12' and row[3]=='0/32768' and float(row[4])<=8
 assert len([n for n in queue.splitlines()if n.strip()])==1,'Unexpected scheduler work; coordinate first'
 raw=command(['bash','-c','source "$1"; printf "%s" "$NODES"','fleet-config',cfg['fleet_environment_file']])
 target={p[0]:p[1]for p in (n.split(':')for n in raw.split())}[cfg['node']]
 record={'status':'INTENT_WRITTEN','review':args.review_url,'head':cfg['head'],'operator_sha256':sha(__file__),
         'config_sha256':sha(CONFIG),'source_files':cfg['files'],'runtime_path_identity_sha256':cfg['runtime_sha256'],
         'nodes':nodes,'queue':queue,'one_remote_invocation':True,'no_auto_retry':True,
         'requested_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 fd=os.open(RECEIPT,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 def write():
  with os.fdopen(os.dup(fd),'w')as f:f.seek(0);json.dump(record,f,indent=2);f.truncate();f.flush();os.fsync(f.fileno())
 write();directory=os.open(RECEIPT.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(directory)
 finally:os.close(directory)
 try:
  result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',target,'python3 -I -S -B -c '+shlex.quote(REMOTE)],
                        input=json.dumps(cfg),text=True,capture_output=True,timeout=700)
  record.update(status='RETURNED',returncode=result.returncode,stdout=result.stdout,stderr=result.stderr);write()
  assert result.returncode==0,'Remote bootstrap failed; inspect exclusive run, never auto-repeat'
  started=json.loads(result.stdout)
  assert started['head']==cfg['head'] and len(started['cpus'])==4 and len(set(started['cpus']))==4
  assert all(isinstance(n,int)and n>=0 for n in started['cpus'])
  assert isinstance(started['launcher_pid'],int)and started['launcher_pid']>1
  assert Path(started['run']).name==cfg['run_name']
  assert started['command'][0]=='bash' and started['command'][1].endswith('/src/.agents/plans/hip-study/launch-step-topology.sh')
  print(json.dumps({'head':cfg['head'],'role':cfg['role'],'launcher_pid':started['launcher_pid'],
                    'started_utc':started['started_utc'],'receipt':str(RECEIPT),'status':'STARTED_NOT_ACCEPTED'}))
 except BaseException as exc:
  record['local_error']=type(exc).__name__+': '+str(exc);write();raise
 finally:os.close(fd)
if __name__=='__main__':main()
