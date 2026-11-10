/** Hold actual source-bound mesh responses: progress must follow validated parts, not time. */
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {chromium,webkit} from '@playwright/test';
import {createSiteServer} from '../../../tools/site/serve-site.mjs';
const root=path.resolve(import.meta.dirname,'../../..'),out=process.env.TEST_OUTPUT||'/tmp/gyropup-build-loading';
await mkdir(out,{recursive:true});
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const server=process.env.SITE_URL?null:createSiteServer(path.join(root,'dist'));
if(server){server.listen(0,'127.0.0.1');await once(server,'listening');}
const base=(process.env.SITE_URL||`http://127.0.0.1:${server.address().port}`).replace(/\/$/,'');
const index=JSON.parse(await readFile(path.join(root,'software/site/assets/build-guides/index.json')));
const rows=Object.fromEntries(index.snapshots.map(row=>[row.assembly||'turret',row]));
async function mesh(assembly,i=0){
 const row=rows[assembly],guide=JSON.parse(await readFile(path.join(root,'software/site/assets/build-guides',row.file)));
 const guideURL=new URL(row.file,base+'/web/build-guides/'),viewURL=new URL(guide.model.file,guideURL);
 const localView=path.join(root,'software/site/assets',viewURL.pathname.replace(/^\/web\//,''));
 const view=JSON.parse(await readFile(localView)),url=new URL(view.parts[i].file,viewURL);
 return {url,bytes:await readFile(path.join(root,'software/site/assets',url.pathname.replace(/^\/web\//,''))),total:view.parts.length};
}
let browser,context;const cases=[],errors=[],releases=[];
try{
 browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
 context=await browser.newContext({viewport:{width:1280,height:900},reducedMotion:'reduce'});
 await context.addInitScript(()=>sessionStorage.setItem('gyropup.prototype-notice','2026-10-29-v1'));
 const p=await context.newPage();p.setDefaultTimeout(30000);p.on('pageerror',e=>errors.push(e.message));
 const loading=p.locator('[data-guide-loading]'),bar=loading.locator('progress');
 async function observed(promise){let timer;try{await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Expected mesh interception did not occur')),25000);})]);}finally{clearTimeout(timer);}}
 async function hold(m){
  let release,seen;const wait=new Promise(r=>release=r),observed=new Promise(r=>seen=r);releases.push(release);
  const match=url=>url.pathname===m.url.pathname;
  await p.route(match,async route=>{seen();await wait;await route.fulfill({body:m.bytes,contentType:'application/octet-stream'});});
  return {observed,release,remove:()=>p.unroute(match)};
 }
 async function counts(done,total){
  await loading.waitFor({state:'visible'});
  await p.waitForFunction(({done,total})=>{const b=document.querySelector('[data-guide-loading] progress');return b.value===done&&b.max===total;},{done,total});
  assert.equal(await bar.getAttribute('value'),String(done));
  assert.equal(await loading.locator('[data-loading-count]').textContent(),`${done} of ${total} parts loaded`);
  assert.equal(await p.locator('[data-guide-model]').getAttribute('aria-busy'),'true');
 }
 async function ready(assembly){await p.waitForFunction(a=>window.__buildGuide?.active?.guideAssembly===a&&window.__buildGuide.active.viewer,assembly);await loading.waitFor({state:'hidden'});assert.equal(await p.locator('[data-guide-model]').getAttribute('aria-busy'),'false');}
 const first=await mesh('robot'),second=await mesh('robot',1),gate1=await hold(first),gate2=await hold(second);
 const indexGate=await hold({url:new URL('/web/build-guides/index.json',base),bytes:await readFile(path.join(root,'software/site/assets/build-guides/index.json'))});
 await p.goto(base+'/designer/build.html?assembly=robot#assembly',{waitUntil:'domcontentloaded'});
 await observed(indexGate.observed);assert.equal(await bar.getAttribute('value'),null,'Unknown work stays indeterminate');assert.equal(await loading.isVisible(),true);indexGate.release();await indexGate.remove();
 console.log('PHASE first-part');await observed(gate1.observed);await counts(0,first.total);gate1.release();console.log('PHASE second-part');await observed(gate2.observed);await counts(1,first.total);
 await p.waitForTimeout(250);await counts(1,first.total);
 for(const viewport of [{width:1280,height:900},{width:390,height:844}]){
  await p.setViewportSize(viewport);await loading.scrollIntoViewIfNeeded();
  const box=await loading.boundingBox();assert.ok(box&&box.width>200&&box.x>=0&&box.x+box.width<=viewport.width&&box.y>=0&&box.y+box.height<=viewport.height,JSON.stringify({viewport,box}));
  await p.screenshot({path:out+`/loading-${viewport.width}.png`});
 }
 cases.push('Real first/second mesh holds stay at 0/1 completed parts; desktop/mobile progress is visible');
 console.log('PHASE finish-robot');gate2.release();await ready('robot');await gate1.remove();await gate2.remove();
 console.log('PHASE failure-retry');const turret=await mesh('turret');const fail=url=>url.pathname===turret.url.pathname;
 await p.route(fail,route=>route.fulfill({status:503,body:'intentional test failure'}));
 await p.locator('[data-assembly=turret]').click();await p.locator('[data-guide-retry]').waitFor({state:'visible'});
 assert.equal(await loading.isVisible(),false);assert.equal(await p.evaluate(()=>window.__buildGuide.active.guideAssembly),'robot');
 assert.equal(await p.locator('[data-guide-model] canvas').count(),1);assert.match(await p.locator('[data-guide-status]').innerText(),/previous build remains/);
 await p.unroute(fail);await p.locator('[data-guide-retry]').click();await ready('turret');
 cases.push('Failed replacement ends loading and preserves the old model; retry loads the selected model');
 console.log('PHASE supersession');const stale=await hold(first),combined=await mesh('combined');
 await p.locator('[data-assembly=robot]').click();await observed(stale.observed);await counts(0,first.total);
 // Robot and Combined deliberately share mesh URLs. Register the newer hold only
 // after observing the older request, otherwise the test intercepts itself.
 const current=await hold(combined);
 await p.locator('[data-assembly=combined]').click();await observed(current.observed);await counts(0,combined.total);
 stale.release();await p.waitForTimeout(250);await counts(0,combined.total);
 current.release();await ready('combined');assert.equal(await p.locator('[data-guide-model] canvas').count(),1);
 cases.push('A superseded real request cannot change or dismiss the current progress');
 await stale.remove();await current.remove();
 console.log('PHASE initial-failure-retry');
 const corrupt=url=>url.pathname===first.url.pathname;
 await p.route(corrupt,route=>route.fulfill({body:'not the source-bound mesh'}));
 await p.goto(base+'/designer/build.html?assembly=robot#assembly',{waitUntil:'domcontentloaded'});
 await p.locator('[data-guide-retry]').waitFor({state:'visible'});assert.equal(await loading.isVisible(),false);
 assert.equal(await p.locator('[data-guide-model]').getAttribute('aria-busy'),'false');
 assert.equal(await p.evaluate(()=>window.__buildGuide.active.viewer),undefined);
 await p.unroute(corrupt);const recovery=await hold(first);await p.locator('[data-guide-retry]').click();await observed(recovery.observed);await counts(0,first.total);recovery.release();await ready('robot');
 cases.push('Initial corrupt mesh ends progress; retry feedback remains visible from text fallback and returns real 3D');
 console.log('PHASE index-retry-supersession');
 const indexMatch=url=>url.pathname==='/web/build-guides/index.json';
 await p.route(indexMatch,route=>route.fulfill({status:503,body:'initial index failure'}));
 await p.goto(base+'/designer/build.html?assembly=robot#assembly',{waitUntil:'domcontentloaded'});
 await p.locator('[data-guide-retry]').waitFor({state:'visible'});assert.equal(await loading.isVisible(),false);
 await p.unroute(indexMatch);
 let seenOlder,releaseOlder,indexCalls=0;const olderSeen=new Promise(r=>seenOlder=r),olderWait=new Promise(r=>releaseOlder=r);releases.push(releaseOlder);
 const indexBytes=await readFile(path.join(root,'software/site/assets/build-guides/index.json'));
 await p.route(indexMatch,async route=>{if(++indexCalls===1){seenOlder();await olderWait;await route.fulfill({status:503,body:'superseded index failure'});}else await route.fulfill({body:indexBytes,contentType:'application/json'});});
 const newerMesh=await hold(first);
 await p.locator('[data-guide-retry]').click();await observed(olderSeen);await p.locator('[data-guide-retry]').click();
 await observed(newerMesh.observed);await counts(0,first.total);releaseOlder();await p.waitForTimeout(250);await counts(0,first.total);
 assert.equal(await p.evaluate(()=>!!window.__buildGuide?.active?.viewer),false);
 newerMesh.release();await ready('robot');
 cases.push('A failed older index retry cannot dismiss progress for a newer retry still waiting on a real mesh');
 assert.deepEqual(errors,[]);
 await writeFile(out+'/report.json',JSON.stringify({status:'passed',engine:engine.name(),version:await(await context.request.get(base+'/version.json')).json(),cases,errors},null,2)+'\n');
 console.log(JSON.stringify({status:'passed',engine:engine.name(),cases}));
}catch(error){await writeFile(out+'/failed.json',JSON.stringify({status:'failed',cases,errors,error:String(error)},null,2));throw error;}
finally{for(const release of releases)release();await context?.close();await browser?.close();if(server){server.closeAllConnections();await new Promise(r=>server.close(r));}}
