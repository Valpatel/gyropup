/** The real Progress page must surface current evidence without a wall of logs. */
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,readFile,mkdir,rm} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium,webkit} from '@playwright/test';
import {prepareRigMedia} from '../designer/rig-media.js';
import {recordRigMedia,verifyRigFiles} from './rig-media.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const reportBytes=await readFile(path.join(root,'exports/leg/rig-results.json'));
const rigRecord=JSON.parse(await readFile(path.join(root,'exports/leg/rig-media.json'),'utf8'));
const rigReport=JSON.parse(reportBytes);
assert.equal(rigRecord.producer_revision,'e7b512870a39259a04a4930e2908af84001bc84e','Known producer of all seven retained clips');
assert.equal((await verifyRigFiles(root,{historical:true})).clips.length,7,'Every report/movie byte matches its actual producer');
for(const mutate of [r=>r.clips.pop(),r=>r.clips[0].path='../private.mp4',r=>r.clips[0].path=r.clips[1].path,
 r=>r.clips[0].scenario=r.clips[1].scenario,r=>r.report.path='elsewhere.json',r=>r.producer_revision='main']){
 const altered=structuredClone(rigRecord);mutate(altered);let reads=0;
 await assert.rejects(prepareRigMedia(reportBytes,altered,async()=>{reads++;return new ArrayBuffer(0);}));
 assert.equal(reads,0,'Invalid membership/paths cannot initiate clip reads');
}
// A recording command cannot bless changed working pixels merely by recomputing their hashes.
const fixture=await mkdtemp('/tmp/gyropup-rig-record-control-');
try{
 await mkdir(path.join(fixture,'exports/leg'),{recursive:true});
 for(const file of [rigRecord.report.path,...rigRecord.clips.map(c=>c.path)])await writeFile(path.join(fixture,file),await readFile(path.join(root,file)));
 const git=(...args)=>execFileSync('git',args,{cwd:fixture,encoding:'utf8'}).trim();
 git('init','-q');git('add','exports');git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','Recorded fixture');
 const revision=git('rev-parse','HEAD');await recordRigMedia(fixture,revision);
 const before=await readFile(path.join(fixture,'exports/leg/rig-media.json'));
 await writeFile(path.join(fixture,rigRecord.clips[0].path),'different pixels');
 await assert.rejects(recordRigMedia(fixture,revision),/movie identity/);
 assert.deepEqual(await readFile(path.join(fixture,'exports/leg/rig-media.json')),before,'Failed recording leaves the previous receipt unchanged');
}finally{await rm(fixture,{recursive:true,force:true});}
const base=(process.env.SITE_URL||'http://127.0.0.1:8982').replace(/\/$/,'');
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const out=await mkdtemp('/tmp/gyropup-progress-'+engine.name()+'-');
const browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox']}:{headless:true});
const context=await browser.newContext({viewport:{width:390,height:844},reducedMotion:'reduce'});
await context.addInitScript(()=>{sessionStorage.setItem('gyropup.prototype-notice','2026-10-29-v1');localStorage.setItem('gyropup.probe','off');});
const errors=[],cases=[],page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
const json=async path=>{const r=await context.request.get(base+path);assert.ok(r.ok());return r.json();};
const version=await json('/version.json'),progress=await json('/docs/progress.json');
const ready=()=>page.waitForFunction(()=>document.body.dataset.ready==='1');
const allOpen=async id=>page.locator('#'+id).evaluate(el=>{for(let node=el;node;node=node.parentElement)if(node.tagName==='DETAILS'&&!node.open)return false;return true;});
try {
 await page.goto(base+'/designer/progress.html');await ready();
 assert.equal(await page.locator('#rig video').count(),7);
 assert.match(await page.locator('#rig [data-rig-media-state]').innerText(),/Recorded leg simulation · 18\.75 kg · 36 V/);
 assert.ok((await page.locator('#rig video').evaluateAll(videos=>videos.map(v=>v.src))).every(src=>src.startsWith('blob:')),'Playback uses the bytes whose hashes were checked');
 const rigVideo=page.locator('#rig video').first();await rigVideo.evaluate(video=>video.play());
 await page.waitForFunction(()=>document.querySelector('#rig video').currentTime>0.05);await rigVideo.evaluate(video=>video.pause());
 await page.waitForFunction(()=>document.querySelector('#fea-media').dataset.state==='ready');
 assert.match(await page.locator('#updated').innerText(),new RegExp(progress.updated));
 assert.equal(await page.locator('#current-focus').innerText(),progress.focus);
 assert.deepEqual(await page.locator('#log li>b').allTextContents(),progress.log.slice(-3).reverse().map(e=>e.title));
 assert.equal(await page.locator('#history li').count(),progress.log.length-3);
 assert.equal(await page.locator('details.progress-fold[open]').count(),0,'Detailed reports and history start collapsed');
 assert.ok(await page.locator('#fea-media').isVisible());
 assert.match(await page.locator('#feanote').innerText(),/hip_frame E1[\s\S]*1\.6 \/ required 2 — below target/);
 const feature=await page.locator('#fea-media').boundingBox(),contextBox=await page.locator('.study-context').boundingBox();
 assert.ok(feature.y<contextBox.y,'On a phone the movie precedes its explanation');
 const portraits=[[320,568],[360,640],[375,667],[390,844],[393,852],[412,915],[414,896],[430,932],[480,960]];
 for(const [width,height] of [...portraits,...portraits.map(([w,h])=>[h,w]),[768,1024],[1024,768],[1440,1000]]){
  await page.setViewportSize({width,height});await page.evaluate(()=>scrollTo(0,0));
  const metrics=await page.evaluate(()=>{const media=document.querySelector('#fea-media').getBoundingClientRect(),context=document.querySelector('.study-context').getBoundingClientRect();return {width:innerWidth,scroll:document.documentElement.scrollWidth,media:{x:media.x,y:media.y,width:media.width},context:{x:context.x,y:context.y,width:context.width}};});
  assert.ok(metrics.scroll<=width+1,`${width}×${height} has no page overflow`);
  assert.ok(metrics.media.x>=0&&metrics.media.x+metrics.media.width<=width+1,'Player fits the viewport');
  assert.ok(metrics.media.y<1100,'Deformation is near the top, before long history/tables');
  if(width>900){assert.ok(Math.abs(metrics.media.y-metrics.context.y)<150,'Desktop player and explanation share a row');assert.ok(metrics.media.x<metrics.context.x,'Player occupies the first desktop column');}
  assert.ok(await page.locator('#history').isHidden());
  cases.push({width,height,mediaTop:metrics.media.y});
  if([320,390,1440].includes(width))await page.screenshot({path:`${out}/${width}x${height}.png`,fullPage:true});
 }
 // Native keyboard activation and media continuity across disclosure changes.
 await page.setViewportSize({width:390,height:844});
 const movie=await page.locator('#feavid').elementHandle();
 const archive=page.locator('#archive > summary');await archive.focus();await archive.press('Enter');assert.equal(await page.locator('#archive').evaluate(e=>e.open),true);
 const day=page.locator('#history details').first(),summary=day.locator(':scope > summary');await summary.focus();await summary.press('Space');assert.ok(await day.locator('li').first().isVisible());
 const dayId=await day.getAttribute('id');await page.evaluate(()=>window.__portalLoads.progress.retry());await ready();assert.ok(await page.locator('#'+dayId).evaluate(e=>e.open),'Retry retains opened history dates');
 await archive.focus();await archive.press('Space');assert.equal(await page.locator('#archive').evaluate(e=>e.open),false);
 assert.ok(await movie.evaluate(el=>el===document.querySelector('#feavid')),'Toggling logs never remounts the study');
 // A selected case above the table must become visible, including native keyboard use.
 for(const [width,height] of [[390,844],[1440,1000]]){
  await page.setViewportSize({width,height});
  if(!await page.locator('#load-cases').evaluate(el=>el.open))await page.locator('#load-cases > summary').click();
  const choice=page.locator('#fea .case-choice').first();await choice.focus();await choice.press('Enter');
  assert.equal(await page.locator('#fea-media').evaluate(el=>el===document.activeElement),true,'Focus follows an explicit case selection');
  const box=await page.locator('#fea-media').boundingBox();assert.ok(box.y>=0&&box.y<height/2&&box.y+box.height>0,'Selected result is visible above the results table');
 }
 // Cold deep links, nested procurement and links to an already selected hash.
 for(const id of ['fea','print','turretbuy','rigtable',dayId]){
  await page.goto(base+'/designer/progress.html#'+id);await ready();await page.waitForFunction(id=>{const el=document.getElementById(id);return el&&el.getBoundingClientRect().height>0;},id);
  assert.ok(await allOpen(id),'Deep link reveals enclosing sections: '+id);
  assert.ok(await page.locator('#'+id).isVisible());
 }
 await page.goto(base+'/designer/progress.html#archive');await ready();await page.locator('#archive > summary').click();assert.equal(await page.locator('#archive').evaluate(e=>e.open),false);
 await page.getByRole('navigation',{name:'Progress sections'}).getByRole('link',{name:'History',exact:true}).click();assert.equal(await page.locator('#archive').evaluate(e=>e.open),true,'The current hash can reopen a collapsed section');
 // Every entry survives in the agent route, including collapsed day groups.
 const md=await context.request.get(base+'/designer/progress.md');assert.ok(md.ok());const text=await md.text();
 for(const entry of progress.log)assert.ok(text.includes(entry.title),entry.title+' retained in Markdown');
 assert.ok(text.includes(progress.updated));assert.ok(/static load scaling, not elapsed physical time/i.test(text),'Markdown preserves static-analysis meaning');
 assert.match(text,/Recorded leg simulation/);assert.match(text,/18\.75 kg/);assert.match(text,/36 V/);
 assert.ok(text.includes(rigRecord.producer_revision),'Markdown identifies the actual recorded report');
 for(const clip of rigRecord.clips)assert.ok(text.includes(clip.path),'Markdown retains original movie downloads: '+clip.scenario);
 assert.doesNotMatch(text,/blob:/,'Static Markdown never publishes ephemeral browser URLs');
 // The real consumer must retain numerical evidence while refusing mismatched or missing movie identities.
 for(const fault of ['report','receipt','movie']){
  const probe=await context.newPage();
  await probe.addInitScript(()=>{window.__rigBlobs=[];const create=URL.createObjectURL.bind(URL);URL.createObjectURL=value=>{const url=create(value);window.__rigBlobs.push(url);return url;};});
  if(fault==='report')await probe.route('**/exports/leg/rig-results.json*',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({...rigReport,half_mass_kg:20})}));
  if(fault==='receipt')await probe.route('**/exports/leg/rig-media.json*',route=>route.fulfill({status:404,body:'not recorded'}));
  if(fault==='movie')await probe.route('**/exports/leg/rig_jump.mp4*',route=>route.fulfill({contentType:'video/mp4',body:Buffer.from('wrong movie bytes')}));
  await probe.goto(base+'/designer/progress.html');await probe.waitForFunction(()=>document.body.dataset.ready==='1');
  const note=await probe.locator('#rig [data-rig-media-state="unavailable"]').innerText();
  assert.match(note,/Recorded movies unavailable/);
  assert.match(note,fault==='report'?/different report/:fault==='receipt'?/provenance is unavailable/:/movie identity does not match/);
  assert.equal(await probe.locator('#rig video').count(),0,'Unverified media cannot receive a source');
  assert.equal(await probe.locator('#rigtable tbody tr').count(),7,'Numerical evidence remains usable');
  if(fault==='report')assert.match(await probe.locator('#riglede').innerText(),/20 kg/);
  assert.equal(await probe.evaluate(()=>window.__rigBlobs.length),0,'No unverified playback bytes were exposed');
  await probe.close();
 }
 // A completed retry revokes old Blob URLs. A late older request cannot replace the newer unavailable state.
 await page.addInitScript(()=>{window.__rigRevoked=[];const revoke=URL.revokeObjectURL.bind(URL);URL.revokeObjectURL=url=>{window.__rigRevoked.push(url);revoke(url);};});
 await page.goto(base+'/designer/progress.html');await ready();
 const originalBlobs=await page.locator('#rig video').evaluateAll(videos=>videos.map(v=>v.src));
 await page.evaluate(()=>window.__portalLoads.rig.retry());
 assert.deepEqual((await page.evaluate(()=>window.__rigRevoked)).sort(),originalBlobs.sort());
 let held,requests=0;const intercepted=new Promise(resolve=>held={resolve});
 await page.route('**/exports/leg/rig-media.json*',route=>{if(++requests===1){held.route=route;held.resolve();return;}return route.fulfill({status:404,body:'newer unavailable record'});});
 await page.evaluate(()=>{window.__olderRigRetry=window.__portalLoads.rig.retry();});await intercepted;
 await page.evaluate(()=>window.__portalLoads.rig.retry());
 assert.equal(await page.locator('#rig [data-rig-media-state="unavailable"]').count(),1);
 await held.route.fulfill({contentType:'application/json',body:JSON.stringify(rigRecord)});
 await page.evaluate(()=>window.__olderRigRetry);
 assert.equal(await page.locator('#rig video').count(),0,'Late old receipt cannot replace newer unavailable media');
 await page.unroute('**/exports/leg/rig-media.json*');
 assert.deepEqual(errors,[]);assert.deepEqual(await json('/version.json'),version,'One published revision throughout');
 await writeFile(out+'/report.json',JSON.stringify({base,version,cases,entries:progress.log.length,errors},null,2));
 console.log(`PASS ${engine.name()}: ${cases.length} layouts; featured real E1; three latest entries; dated archive; keyboard/retry/deep links; complete Markdown. ${out}`);
}finally{await browser.close();}
