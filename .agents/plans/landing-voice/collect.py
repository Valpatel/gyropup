"""One bounded genuine refresh of the existing seven name-bearing voice clips."""
import ctypes,hashlib,json,os,pathlib,resource,runpy,shutil,signal,stat,subprocess,sys,tarfile,time
ROOT=pathlib.Path.cwd().resolve();OUT=pathlib.Path(os.environ['FLEET_RUN_OUT']).resolve();VOICE=ROOT/'software/site/designer/character/voice'
assert not OUT.is_relative_to(ROOT)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,obj):(OUT/name).write_text(json.dumps(obj,indent=2)+'\n')
def tracked():
 result={}
 for name in subprocess.check_output(['git','ls-files','-z'],text=True).split('\0'):
  if not name:continue
  p=ROOT/name;s=p.lstat();assert stat.S_ISREG(s.st_mode)
  result[name]={'sha256':sha(p),'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'inode':s.st_ino}
 return result
def inventory(directory):
 result={}
 for p in sorted(directory.rglob('*')):
  s=p.lstat()
  if stat.S_ISDIR(s.st_mode):continue
  assert stat.S_ISREG(s.st_mode),'nonregular voice output'
  result[p.relative_to(directory).as_posix()]={'sha256':sha(p),'bytes':s.st_size}
 return result
def archive(directory,name):
 rows=inventory(directory);write(name+'-files.json',rows)
 def anon(t):t.uid=t.gid=0;t.uname=t.gname='';t.mtime=0;return t
 with tarfile.open(OUT/(name+'.tgz'),'w:gz')as t:
  for n in rows:t.add(directory/n,arcname=n,recursive=False,filter=anon)
 return {'sha256':sha(OUT/(name+'.tgz')),'members':len(rows)}
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
before=tracked();write('source-before.json',before)
original={n:p.read_bytes()for n,p in ((p.name,p)for p in VOICE.iterdir())};assert all(p.is_file()and not p.is_symlink()for p in VOICE.iterdir())
backup=OUT/'original-voice';backup.mkdir(exist_ok=False)
for n,b in original.items():(backup/n).write_bytes(b)
original_manifest=json.loads(original['manifest.json']);m=runpy.run_path(str(ROOT/'tools/audio/render-voice.py'));_,want=m['plan']();old=original_manifest['lines'];affected=[line for line in want if want[line]['clip']!=old[line]['clip']];assert len(affected)==7 and all('Gyropup'in line for line in affected);write('affected-lines.json',[{'written':l,'before':old[l],'planned':want[l]}for l in affected])
blocked=None;processes_quiescent=True
libc=ctypes.CDLL(None,use_errno=True);assert libc.prctl(36,1,0,0,0)==0
def interrupted(signum,frame):raise KeyboardInterrupt('signal '+str(signum))
for sig in(signal.SIGINT,signal.SIGTERM):signal.signal(sig,interrupted)
def limits():
 if blocked is not None:signal.pthread_sigmask(signal.SIG_SETMASK,blocked)
 resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3));resource.setrlimit(resource.RLIMIT_CPU,(180,180))
def settle_owned_group(proc):
 signalled=False;reaped=[]
 try:os.killpg(proc.pid,signal.SIGKILL);signalled=True
 except ProcessLookupError:pass
 proc.wait(timeout=5);deadline=time.monotonic()+3
 while True:
  while True:
   try:pid,status=os.waitpid(-proc.pid,os.WNOHANG)
   except ChildProcessError:break
   if pid==0:break
   reaped.append({'pid':pid,'status':status})
  try:os.killpg(proc.pid,0)
  except ProcessLookupError:return {'group_gone':True,'signalled':signalled,'reaped':reaped}
  if time.monotonic()>=deadline:return {'group_gone':False,'signalled':signalled,'reaped':reaped}
  time.sleep(.02)
phases=[]
def phase(name,args,expected=0,seconds=180):
 global blocked,processes_quiescent
 proc=None;row={'name':name,'args':args,'expected':expected};started=time.monotonic()
 try:
  with(OUT/(name+'.log')).open('w')as log:
   blocked=signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGINT,signal.SIGTERM})
   try:
    processes_quiescent=False;proc=subprocess.Popen(args,cwd=ROOT,env=os.environ.copy(),stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limits)
   finally:signal.pthread_sigmask(signal.SIG_SETMASK,blocked)
   row['exit']=proc.wait(timeout=seconds)
 finally:
  cleanup=settle_owned_group(proc)if proc is not None else {'group_gone':processes_quiescent,'not_started':True}
  processes_quiescent=cleanup['group_gone'];row.update(cleanup=cleanup,seconds=time.monotonic()-started);phases.append(row);write('phases.json',phases)
 assert processes_quiescent and row['exit']==expected,row
result={'collection_pass':False,'adoption_approved':False,'source_revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()}
try:
 result['original_archive']=archive(backup,'original-voice')
 phase('stale-check',[sys.executable,'-B','tools/audio/render-voice.py','--check'],expected=1)
 phase('render',[sys.executable,'-B','tools/audio/render-voice.py'])
 candidate=OUT/'candidate-voice';shutil.copytree(VOICE,candidate);result['candidate_archive']=archive(candidate,'candidate-voice');write('result.json',result)
 new=json.loads((candidate/'manifest.json').read_text());assert new['key_version']==original_manifest['key_version'] and new['voice_tag']==original_manifest['voice_tag'] and new['voice']==original_manifest['voice'] and new['engine']=='piper-tts 1.4.2';assert set(new['lines'])==set(old)
 for line,entry in old.items():
  if line not in affected:assert new['lines'][line]==entry and (candidate/entry['clip']).read_bytes()==original[entry['clip']]
  else:assert new['lines'][line]['spoken']==want[line]['spoken'] and 'gyro, pup'in new['lines'][line]['spoken']
 phase('current-check',[sys.executable,'-B','tools/audio/render-voice.py','--check'])
 phase('python-controls',[sys.executable,'-B','tests/software/audio/test-pronunciation.py'])
 phase('javascript-controls',['node','--test','tests/site/content/test-pronunciation.mjs'])
 for label,directory,manifest in [('before',backup,original_manifest),('after',candidate,new)]:
  line='Hi! I’m Gyropup. Ready for a backyard adventure?';shutil.copyfile(directory/manifest['lines'][line]['clip'],OUT/(label+'-landing.mp3'))
  phase(label+'-decode',['ffmpeg','-v','error','-i',str(OUT/(label+'-landing.mp3')),'-f','null','-'])
 result.update(collection_pass=True,affected=len(affected),unchanged_lines=len(old)-len(affected),source_bindings_unchanged_outside_voice=True)
finally:
 result['processes_quiescent']=processes_quiescent
 try:
  if processes_quiescent:
   errors=[]
   for p in list(VOICE.iterdir()):
    try:
     if p.name not in original:p.unlink()
    except BaseException as e:errors.append(str(e))
   for n,b in original.items():
    try:
     p=VOICE/n
     if not p.exists()or p.read_bytes()!=b:p.write_bytes(b)
     rec=before['software/site/designer/character/voice/'+n];os.utime(p,ns=(p.stat().st_atime_ns,rec['mtime_ns']))
    except BaseException as e:errors.append(str(e))
   # Genuine producer overwrites existing files in place, preserving inode.
   after=tracked();write('source-after.json',after);result['source_restored']=after==before;result['voice_restored']=inventory(VOICE)==inventory(backup);result['restore_errors']=errors
   assert not errors and result['source_restored'] and result['voice_restored'];assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
  else:result['source_restored']=False
 finally:write('result.json',result)
assert result['collection_pass']and result['source_restored']and result['processes_quiescent'];print(json.dumps(result))
