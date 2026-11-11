/** Pure output/identity controls; synthetic metadata is not rendered-geometry evidence. */
import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import {acknowledgePrototypeNotice} from '../../site/assembly/build-prototype-session.mjs';
import {mkdtemp,mkdir,readFile,writeFile,symlink,rm,stat} from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {reservePosterOutput,assertPosterIdentity} from '../../../tools/site/render-hero-poster.mjs';
const ROOT=fileURLToPath(new URL('../../../',import.meta.url));
async function fixture(t){
 const directory=await mkdtemp(path.join(os.tmpdir(),'hero-poster-output-')),source=path.join(directory,'source'),output=path.join(directory,'output');
 t.after(()=>rm(directory,{recursive:true,force:true}));await mkdir(source);await mkdir(output);return{directory,source,output};
}
test('missing, unknown and non-PNG arguments reject before output or browser',async t=>{
 const f=await fixture(t);
 for(const args of [[],['--unknown','x'],['--output',path.join(f.output,'image.jpg')]])await assert.rejects(reservePosterOutput(args,f.source));
});
test('fresh outside output is exclusive, private and never truncates an original',async t=>{
 const f=await fixture(t),name=path.join(f.output,'candidate.png'),first=await reservePosterOutput(['--output',name],f.source);
 try{await first.handle.writeFile('SYNTHETIC reservation, not a PNG');await assert.rejects(reservePosterOutput(['--output',name],f.source),{code:'EEXIST'});}
 finally{await first.handle.close();}
 assert.equal(await readFile(name,'utf8'),'SYNTHETIC reservation, not a PNG');assert.equal((await stat(name)).mode&0o777,0o600);
});
test('source paths and parent aliases into source reject',async t=>{
 const f=await fixture(t),alias=path.join(f.directory,'source-alias');await symlink(f.source,alias,'dir');
 for(const name of [path.join(f.source,'public.png'),path.join(alias,'public.png')])await assert.rejects(reservePosterOutput(['--output',name],f.source),/outside the source checkout/);
});
test('existing file and dangling symlinks cannot become poster output',async t=>{
 const f=await fixture(t),original=path.join(f.output,'original.png'),link=path.join(f.output,'link.png'),dangling=path.join(f.output,'dangling.png');
 await writeFile(original,'original bytes');await symlink(original,link);await symlink(path.join(f.output,'not-created.png'),dangling);
 for(const name of [original,link,dangling])await assert.rejects(reservePosterOutput(['--output',name],f.source),{code:'EEXIST'});
 assert.equal(await readFile(original,'utf8'),'original bytes');
});
test('competing reservations have one winner and preserve its bytes',async t=>{
 const f=await fixture(t),name=path.join(f.output,'once.png'),results=await Promise.allSettled([reservePosterOutput(['--output',name],f.source),reservePosterOutput(['--output',name],f.source)]);
 assert.equal(results.filter(r=>r.status==='fulfilled').length,1);assert.equal(results.find(r=>r.status==='rejected').reason.code,'EEXIST');
 const winner=results.find(r=>r.status==='fulfilled').value;try{await winner.handle.writeFile('only owner');}finally{await winner.handle.close();}assert.equal(await readFile(name,'utf8'),'only owner');
});
test('actual CLI rejects missing output and public target without browser dependencies',async()=>{
 const script=path.join(ROOT,'tools/site/render-hero-poster.mjs'),image=path.join(ROOT,'software/site/assets/robot-poster.png'),hash=bytes=>createHash('sha256').update(bytes).digest('hex'),before=hash(await readFile(image));
 for(const [args,error]of [[[],/Provide --output/],[['--output',image],/outside the source checkout/]]){
  const result=spawnSync(process.execPath,[script,...args],{encoding:'utf8',timeout:5000});assert.equal(result.status,1);assert.match(result.stderr,error);assert.doesNotMatch(result.stderr,/ERR_MODULE_NOT_FOUND|browserType\.launch/);assert.equal(result.stdout,'');
 }
 assert.equal(hash(await readFile(image)),before);
});
test('symlinked actual entry point still rejects missing output instead of a false zero exit',async t=>{
 const f=await fixture(t),alias=path.join(f.directory,'poster-entry.mjs');await symlink(path.join(ROOT,'tools/site/render-hero-poster.mjs'),alias);
 const result=spawnSync(process.execPath,[alias],{encoding:'utf8',timeout:5000});assert.equal(result.status,1);assert.match(result.stderr,/Provide --output/);assert.equal(result.stdout,'');
});
test('stdin module import exposes pure guards without running the producer',()=>{
 const module=new URL('../../../tools/site/render-hero-poster.mjs',import.meta.url).href;
 const result=spawnSync(process.execPath,['--input-type=module','-'],{input:`const m=await import(${JSON.stringify(module)});if(typeof m.reservePosterOutput!=='function')throw Error('missing guard');`,encoding:'utf8',timeout:5000});
 assert.equal(result.status,0,result.stderr);assert.equal(result.stdout,'');
});
function identity(){
 const current={source:{file:'web/robot-current/manifest.json'},native_source:'SYNTHETIC native identity',collection_sha256:'SYNTHETIC collection identity',parts:Array.from({length:224},(_,i)=>`fixture-${String(i).padStart(3,'0')}`)};
 const observed={presentation:{mode:'current',robotId:'collection266',nativeSource:current.native_source,collectionSha256:current.collection_sha256,...Object.fromEntries(['bodySource','legSource','turretSource'].map(k=>[k,'https://site.fixture.test/'+current.source.file]))},parts:[...current.parts],homeLegMM:300,hMin:185,hMax:375,wheelR:127,homeHeight:115/190,basePositionM:[0,.427,0],baseQuaternion:[0,0,0,1]};
 return{current,observed};
}
test('synthetic matching current identity and applied source-home observation passes',()=>{const f=identity();assert.doesNotThrow(()=>assertPosterIdentity(f.observed,f.current));});
test('legacy identity, wrong original,1mm home drift and wrong actual pose reject',()=>{
 for(const fault of ['native','collection','recorded','wrong-path','missing-original','home-leg','height299','wrong-wheel','applied299','base-rotation']){
  const f=identity(),o=f.observed;
  if(fault==='native')o.presentation.nativeSource='old';else if(fault==='collection')o.presentation.collectionSha256='old';else if(fault==='recorded')o.presentation.robotId='gyropup-v2-rig';else if(fault==='wrong-path')o.presentation.bodySource='https://site.fixture.test/web/old/manifest.json';else if(fault==='missing-original')o.parts.pop();else if(fault==='home-leg')o.homeLegMM=299;else if(fault==='height299')o.homeHeight=.6;else if(fault==='wrong-wheel')o.wheelR=128;else if(fault==='applied299')o.basePositionM[1]=.426;else o.baseQuaternion=[0,.1,0,.99];
  assert.throws(()=>assertPosterIdentity(o,f.current),undefined,fault);
 }
});

// Extract only each named transported function, never execute a producer's top-level module.
async function captureFixture(file,name){
 const source=await readFile(path.join(ROOT,file),'utf8');
 const match=source.match(new RegExp('^function '+name+'\\([^]*?^}', 'm'));
 assert.ok(match,`Missing actual ${name} init callback`);
 return {source,run:(state,arg)=>{
  const scope={argument:arg};Object.defineProperties(scope,Object.getOwnPropertyDescriptors(state));
  return vm.runInNewContext('('+match[0]+')(argument)',scope);
 }};
}
async function initFixtures(){
 const hero=await captureFixture('tests/site/media/test-hero-preview.mjs','prefs');
 const recorder=await captureFixture('tools/evidence/media/capture-highlights.mjs','seedCapture');
 assert.equal((hero.source.match(/addInitScript\(prefs,new URL\(base\).origin\)/g)||[]).length,4);
 assert.match(recorder.source,/addInitScript\(seedCapture,\{seed,expectedOrigin:new URL\(base\).origin\}\)/);
 for(const {source}of[hero,recorder]){
  assert.match(source,/assembly\/build-prototype-session.mjs/);
  assert.doesNotMatch(source,/content\/test-prototype-session.mjs/);
  assert.match(source,/acknowledgePrototypeNotice\(context,base\)/);
 }
 let script,arg;await acknowledgePrototypeNotice({addInitScript(fn,value){script=fn;arg=value;}},'https://site.fixture.test/path');
 const notice={run(state){const scope={argument:arg};Object.defineProperties(scope,Object.getOwnPropertyDescriptors(state));return vm.runInNewContext('('+script.toString()+')(argument)',scope);}};
 return [{name:'hero',...hero,arg:'https://site.fixture.test'},{name:'recorder',...recorder,arg:{seed:1042026,expectedOrigin:'https://site.fixture.test'}},{name:'notice',...notice}];
}
test('actual media init callbacks avoid storage, random and live hooks on opaque or wrong origins',async()=>{
 for(const f of await initFixtures())for(const origin of [{protocol:'about:',origin:'null'},{protocol:'https:',origin:'null'},{protocol:'https:',origin:'https://other.fixture.test'},{protocol:'file:',origin:'file://'}]){
  const state={location:{protocol:origin.protocol},origin:origin.origin};
  for(const key of ['localStorage','sessionStorage','Math','window'])Object.defineProperty(state,key,{enumerable:true,get(){throw Error('must not access '+key);}});
  assert.doesNotThrow(()=>f.run(state,f.arg),f.name);
 }
});
test('actual matching media init writes exact preferences and retains the seeded sequence/live hook',async()=>{
 for(const f of await initFixtures()){
  const writes=[],math={imul:Math.imul,random:()=>-1},state={location:{protocol:'https:'},origin:'https://site.fixture.test',window:{},Math:math};
  for(const key of ['localStorage','sessionStorage'])state[key]={setItem(...args){writes.push([key,...args]);}};
  f.run(state,f.arg);
  assert.deepEqual(writes,f.name==='notice'?[['sessionStorage','gyropup.prototype-notice','2026-10-29-v1']]:[['localStorage','gyropup.probe','off'],['localStorage','gyropup-sfx','0']]);
  if(f.name==='recorder'){
   let seed=1042026;for(let i=0;i<3;i++){seed=(Math.imul(seed,1664525)+1013904223)>>>0;assert.equal(math.random(),seed/4294967296);}
   assert.equal(state.window.__cadagentLive,true);
  }else{assert.equal(math.random(),-1);assert.equal(state.window.__cadagentLive,undefined);}
 }
});
test('matching-origin media storage denial still propagates with the original error',async()=>{
 for(const f of await initFixtures()){
  const state={location:{protocol:'https:'},origin:'https://site.fixture.test',window:{},Math:{imul:Math.imul}},failure=Error('matching-origin denied fixture');
  for(const key of ['localStorage','sessionStorage'])state[key]={setItem(){throw failure;}};
  assert.throws(()=>f.run(state,f.arg),error=>error===failure,f.name);
  // Node's VM converts a throwing global getter into ReferenceError; still prove
  // the matching-origin accessor is attempted and failure escapes the callback.
  let accessed=false;
  for(const key of ['localStorage','sessionStorage'])Object.defineProperty(state,key,{enumerable:true,get(){accessed=true;throw failure;}});
  assert.throws(()=>f.run(state,f.arg));assert.equal(accessed,true,f.name);
 }
});
