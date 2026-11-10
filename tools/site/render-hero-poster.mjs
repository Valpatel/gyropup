import { acknowledgePrototypeNotice } from '../../tests/site/content/test-prototype-session.mjs';
/** Capture the actual current hero hook into fresh candidate output; never adopt it here. */
import assert from 'node:assert/strict';
import {open,realpath} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {parseArgs} from 'node:util';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const ROOT=fileURLToPath(new URL('../../',import.meta.url));

export async function reservePosterOutput(args,sourceRoot=ROOT){
 const {values}=parseArgs({args,options:{output:{type:'string'}},allowPositionals:false});
 assert.ok(values.output,'Provide --output for a fresh PNG outside the source checkout');
 assert.equal(path.extname(values.output),'.png','Poster output must be a PNG');
 const requested=path.resolve(values.output),source=await realpath(sourceRoot),parent=await realpath(path.dirname(requested));
 const output=path.join(parent,path.basename(requested));
 const inside=p=>p===source||p.startsWith(source+path.sep);
 assert.ok(!inside(requested)&&!inside(output),'Poster output must be outside the source checkout');
 // O_EXCL also rejects existing files, directories and dangling symlinks.
 const handle=await open(output,'wx',0o600);
 return {output,handle};
}

export function assertPosterIdentity(observed,current){
 assert.equal(observed.presentation.mode,'current');
 assert.equal(observed.presentation.robotId,'collection266');
 assert.equal(observed.presentation.nativeSource,current.native_source);
 assert.equal(observed.presentation.collectionSha256,current.collection_sha256);
 for(const name of ['bodySource','legSource','turretSource'])assert.equal(new URL(observed.presentation[name]).pathname,'/'+current.source.file);
 assert.deepEqual([...observed.parts].sort(),current.parts);
 assert.equal(observed.homeLegMM,300);
 assert.deepEqual([observed.hMin,observed.hMax,observed.wheelR],[185,375,127]);
 assert.ok(Math.abs(observed.hMin+(observed.hMax-observed.hMin)*observed.homeHeight-300)<1e-9,'Poster must use the source300mm home');
 const expected=[0,(300+observed.wheelR)/1000,0];
 assert.ok(observed.basePositionM.length===3&&observed.basePositionM.every((v,i)=>Number.isFinite(v)&&Math.abs(v-expected[i])<1e-9),'Actual hero base must be at its applied home pose');
 assert.ok(observed.baseQuaternion.length===4&&observed.baseQuaternion.every((v,i)=>Number.isFinite(v)&&Math.abs(v-[0,0,0,1][i])<1e-9),'Actual hero base must have the source home orientation');
}

async function main(args){
 const {output,handle}=await reservePosterOutput(args);
 let browser,receipt,primary,cleanup;
 try{
  const current=JSON.parse(execFileSync('python3',['-B',path.join(ROOT,'tools/evidence/media/check-highlights.py'),'--capture-contract'],{cwd:ROOT,encoding:'utf8'}));
  const source=execFileSync('git',['rev-parse','HEAD'],{cwd:ROOT,encoding:'utf8'}).trim();
  const base=(process.env.SITE_URL||'http://127.0.0.1:8890').replace(/\/$/,'');
  const served=await(await fetch(base+'/version.json')).json();assert.equal(served.revision,source,'Served poster source must be the frozen checkout');
  const {chromium}=await import('@playwright/test');
  browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  await acknowledgePrototypeNotice(page);
  await page.addInitScript(()=>{localStorage.setItem('gyropup.probe','off');localStorage.setItem('gyropup-sfx','0');});
  await page.goto(base+'/',{waitUntil:'networkidle'});
  await page.waitForFunction(()=>window.__heroPreview?.capturePoster);
  const {image,...observed}=await page.evaluate(()=>{
   const h=window.__heroPreview,image=h.capturePoster(1024),r=h.robot;
   return {image,presentation:r.presentation,parts:[...new Set(r.parts?.map(p=>p.entry.name)??[])],homeLegMM:r.info.homeLegMM,
    homeHeight:r.info.homeHeight,hMin:r.info.hMin,hMax:r.info.hMax,wheelR:r.info.wheelR,basePositionM:r.base.position.toArray(),baseQuaternion:r.base.quaternion.toArray()};
  });
  assertPosterIdentity(observed,current);
  assert.ok(image.startsWith('data:image/png;base64,'));const bytes=Buffer.from(image.split(',')[1],'base64');
  assert.equal(bytes.subarray(0,8).toString('hex'),'89504e470d0a1a0a');assert.equal(bytes.readUInt32BE(16),1024);assert.equal(bytes.readUInt32BE(20),1024);
  await handle.writeFile(bytes);await handle.sync();
  receipt={schema:'gyropup.hero-poster-candidate/1',source,served,browser:browser.version(),currentSource:current.source,
   observed,sha256:createHash('sha256').update(bytes).digest('hex'),bytes:bytes.length,width:1024,height:1024,adoption:false};
 }catch(error){primary=error;}
 finally{
  try{await browser?.close();}catch(error){cleanup=error;}
  try{await handle.close();}catch(error){cleanup??=error;}
 }
 if(primary){if(cleanup)console.error('Poster cleanup also failed:',cleanup.message);throw primary;}
 if(cleanup)throw cleanup;
 console.log(JSON.stringify(receipt));
}
const entry=process.argv[1]&&process.argv[1]!=='-'?await realpath(process.argv[1]).catch(error=>{if(error.code==='ENOENT')return null;throw error;}):null;
if(entry===fileURLToPath(import.meta.url))await main(process.argv.slice(2));
