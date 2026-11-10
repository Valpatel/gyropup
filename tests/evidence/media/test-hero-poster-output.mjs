/** Pure output/identity controls; synthetic metadata is not rendered-geometry evidence. */
import assert from 'node:assert/strict';
import test from 'node:test';
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
