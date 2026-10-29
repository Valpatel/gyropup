/** Loading must be visible, recoverable, and unable to steal a newer player choice. */
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {chromium,webkit} from '@playwright/test';
const base=(process.env.SITE_URL||'http://127.0.0.1:8892').replace(/\/$/,'');
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
const context=await browser.newContext({viewport:{width:1280,height:900}});
await context.addInitScript(()=>{localStorage.setItem('gyropup.probe','off');sessionStorage.setItem('gyropup.prototype-notice','2026-10-29-v1');});
const page=await context.newPage(),errors=[];page.setDefaultTimeout(60000);
page.on('pageerror',e=>errors.push(e.message));
const out=process.env.TEST_OUTPUT||'/tmp/gyropup-loading-sim';await mkdir(out,{recursive:true});
const status=page.locator('#sim-loading'),retry=status.locator('[data-retry]');
const ready=()=>page.waitForFunction(()=>document.body.dataset.ready==='1'&&window.__sim?.talk&&document.getElementById('sim-startup').hidden);
const hidden=()=>page.waitForFunction(()=>document.getElementById('sim-loading').hidden);
const identity=()=>page.evaluate(()=>{const s=window.__sim,k=window.loadingIdentity;return s.stage.scene===k.scene&&s.talk===k.talk&&JSON.stringify(s.talk.conversation)===k.history;});
const afterFrames=()=>page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
let releaseNav,releaseModel,releaseRun,releaseDesign;
try {
 const version=await(await context.request.get(base+'/version.json')).json();
 // The real nav helper returns useful links while its optional config is still pending.
 let navRequested;const navRequest=new Promise(resolve=>{navRequested=resolve;});
 await page.route('**/__loading_shell__',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><body></body>'}));
 await page.route('**/site/nav.json',async r=>{await new Promise(resolve=>{releaseNav=resolve;navRequested();});await r.continue();});
 await page.goto(base+'/__loading_shell__');
 const navResult=await page.evaluate(async()=>{const {mountAppNav}=await import('/designer/kit/appnav.js');const nav=await mountAppNav({root:'../'});return {links:nav.querySelectorAll('a').length,text:nav.textContent};});
 await navRequest;
 assert.ok(releaseNav&&navResult.links>=6&&navResult.text.includes('Play'),'Navigation is usable before its configuration arrives');
 releaseNav();await page.unroute('**/site/nav.json');
 // Static startup feedback exists even if the main module cannot load; Retry recovers a fresh bootstrap.
 let moduleAttempts=0;
 await page.route('**/designer/sim.js*',r=>++moduleAttempts===1?r.abort():r.continue());
 await page.goto(base+'/designer/sim.html?run=none&demo=0&sound=0',{waitUntil:'networkidle'});
 await page.waitForFunction(()=>document.getElementById('sim-startup').dataset.state==='error');
 assert.equal(await page.locator('#sim-startup button').isVisible(),true);
 await page.route('**/exports/sim/v2/rig/manifest.json',async r=>{await new Promise(resolve=>{releaseModel=resolve;});await r.continue();});
 const modelRequest=page.waitForRequest('**/exports/sim/v2/rig/manifest.json');
 await page.locator('#sim-startup button').click();await modelRequest;
 await page.waitForFunction(()=>document.getElementById('sim-startup').dataset.state==='loading');
 assert.equal(await page.locator('#sim-startup').getAttribute('aria-busy'),'true');
 assert.match(await page.locator('#sim-startup').textContent(),/Loading/);
 releaseModel();await page.unroute('**/exports/sim/v2/rig/manifest.json');await ready();
 assert.equal(await page.locator('#app canvas').count(),1);
 await page.unroute('**/designer/sim.js*');
 // Record a real exchange so an empty, recreated conversation cannot pass identity checks.
 await page.getByLabel('Message to Gyropup').fill('Hello Gyropup');await page.locator('.gp-ask').click();
 await page.waitForFunction(()=>window.__sim.talk.conversation.length===2);
 await page.evaluate(()=>{const s=window.__sim;window.loadingIdentity={scene:s.stage.scene,robot:s.state.robot,talk:s.talk,history:JSON.stringify(s.talk.conversation)};});
 // A stalled model switch times out, preserving live play; Retry loads the chosen model.
 let designAttempts=0;
 await page.route('**/designs/default.json',async r=>{
  if(++designAttempts===1)await new Promise(resolve=>{releaseDesign=resolve;});
  await r.continue().catch(()=>{}); // The first request has already been aborted by the reader.
 });
 await page.selectOption('#design-select','designs/default.json');
 await page.waitForFunction(()=>document.getElementById('sim-loading').dataset.state==='error');
 assert.ok(releaseDesign,'A genuinely held response reaches a bounded failure');releaseDesign();
 assert.equal(await identity(),true);assert.equal(await page.evaluate(()=>window.__sim.state.robot===window.loadingIdentity.robot),true);
 await retry.click();await page.waitForFunction(()=>window.__sim.state.modelKey==='designs/default.json');await hidden();assert.equal(await identity(),true);
 let summaryAttempts=0;
 await page.route('**/exports/sim/v2/summary.json',async r=>{
  ++summaryAttempts;
  if(summaryAttempts===1){await r.fulfill({json:{scenarios:null}});return;}
  if(summaryAttempts===2){const response=await r.fetch(),summary=await response.json();summary.mass_kg='broken';await r.fulfill({json:summary});return;}
  await r.continue();
 });
 await page.selectOption('#design-select','v2');await page.waitForFunction(()=>window.__sim.state.modelKey==='v2');
 await page.waitForFunction(()=>document.getElementById('sim-loading').dataset.state==='error');
 assert.match(await status.textContent(),/recordings could not load/);
 const malformedSummary=page.waitForResponse(r=>r.url().endsWith('/exports/sim/v2/summary.json'));
 await retry.click();await(await malformedSummary).finished();
 await page.waitForFunction(()=>document.getElementById('sim-loading').dataset.state==='error');
 assert.equal(await page.evaluate(()=>window.__sim.state.modelMass),null,'Malformed metadata cannot enter render state');
 await retry.click();await hidden();assert.equal(summaryAttempts,3,'Retry refetches a malformed recording list instead of reusing it');
 await page.waitForFunction(()=>!window.__sim.state.cameraTransition&&!window.__sim.state.transition);
 // Background loading is an overlay: it cannot move the camera or hide manual actions.
 await page.route('**/exports/sim/v2/targets.json',async r=>{await new Promise(resolve=>{releaseRun=resolve;});await r.continue();});
 const camera=await page.evaluate(()=>{const s=window.__sim.stage;return {p:s.camera.position.toArray(),projection:s.camera.projectionMatrix.toArray()};});
 const runRequest=page.waitForRequest('**/exports/sim/v2/targets.json');
 await page.selectOption('#run-select','v2/targets');await runRequest;
 assert.equal(await status.getAttribute('aria-busy'),'true');
 assert.equal(await page.locator('#robot-actions [data-action=fire]').isEnabled(),true);
 await afterFrames();
 assert.deepEqual(await page.evaluate(()=>window.__sim.stage.camera.projectionMatrix.toArray()),camera.projection);
 assert.deepEqual(await page.evaluate(()=>window.__sim.stage.camera.position.toArray()),camera.p);
 const mag=await page.evaluate(()=>window.__sim.gun.mag);
 await page.locator('#robot-actions [data-action=fire]').click();await hidden();
 await page.waitForFunction(n=>window.__sim.gun.mag<n,mag);
 const response=page.waitForResponse(r=>r.url().endsWith('/exports/sim/v2/targets.json'));releaseRun();await (await response).finished();await afterFrames();
 assert.equal(await page.evaluate(()=>!window.__sim.state.replay&&window.__sim.state.robot.presentation.mode==='current'),true);
 assert.equal(await identity(),true);await hidden();
 await page.unroute('**/exports/sim/v2/targets.json');
 let recordingAttempts=0;
 await page.route('**/exports/sim/v2/drive.json',async r=>{
  ++recordingAttempts;if(recordingAttempts>4){await r.continue();return;}
  const response=await r.fetch(),run=await response.json();
  if(recordingAttempts===1)run.frames.qpos=[];
  if(recordingAttempts===2)run.props=[{name:'broken',type:6,pos:[],quat:[1,0,0,0],size:[1,1,1],rgba:[1,1,1,1]}];
  if(recordingAttempts===3)run.movers=[{pivot:[0,0,0],axis:[],qpos:0,geoms:[]}];
  if(recordingAttempts===4)run.qpos_layout.ball_bad=run.frames.qpos[0].length-1;
  await r.fulfill({json:run});
 });
 await page.selectOption('#run-select','v2/drive');
 for(let attempt=1;attempt<=4;attempt++) {
  await page.waitForFunction(()=>document.getElementById('sim-loading').dataset.state==='error');
  assert.equal(recordingAttempts,attempt);
  assert.equal(await page.evaluate(()=>window.__sim.state.robot.presentation.mode==='current'&&!window.__sim.state.replay),true);
  assert.equal(await identity(),true);
  if(attempt<4){const next=page.waitForResponse(r=>r.url().endsWith('/exports/sim/v2/drive.json'));await retry.click();await(await next).finished();}
 }
 await retry.click();await page.waitForFunction(()=>window.__sim.state.replay?.key==='v2/drive');await hidden();
 assert.equal(recordingAttempts,5);
 assert.equal(await identity(),true);
 await page.locator('#robot-actions [data-action=reload]').click();assert.equal(await page.evaluate(()=>window.__sim.state.replay),null);
 // Required bench geometry must fail as a whole, then recover without duplicate controls.
 let meshAttempts=0;
 await page.route('**/exports/sim/turret_box/barrel.stl*',r=>{
  meshAttempts++;
  if(meshAttempts===1)return r.fulfill({status:503,body:'Unavailable'});
  if(meshAttempts===2)return r.fulfill({body:' '.repeat(80)+'solid invalid\nendsolid invalid\n'});
  if(meshAttempts===3)return r.fulfill({contentType:'text/html',body:'<html>Not STL</html>'});
  if(meshAttempts===4)return r.fulfill({body:Buffer.alloc(84)});
  return r.continue();
 });
 await page.selectOption('#design-select','turret-box');
 await page.waitForFunction(()=>document.getElementById('sim-loading').dataset.state==='error');
 assert.equal(await page.evaluate(()=>window.__sim.state.bench||!!window.__sim.bench()),false);
 assert.equal(await identity(),true);
 const layouts=[];
 for(const [width,height] of [[320,568],[844,390]]) {
  await page.setViewportSize({width,height});await page.evaluate(()=>window.__sim.talk.dock.collapse(true));await afterFrames();
  const layout=await retry.evaluate(el=>{
   const r=el.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
   const status=el.closest('.gp-loading'),box=status.getBoundingClientRect(),actions=document.getElementById('robot-actions').getBoundingClientRect();
   const bubble=document.querySelector('.gp-bubble'),b=bubble.getBoundingClientRect();
   const left=Math.max(box.left,b.left),right=Math.min(box.right,b.right),top=Math.max(box.top,b.top),bottom=Math.min(box.bottom,b.bottom);
   let readable=true;
   if(right>left&&bottom>top&&!bubble.classList.contains('hidden')) {
    // Pointer transparency must not conceal a stacking-order bug in this visual overlap check.
    const pointer=bubble.style.pointerEvents;bubble.style.pointerEvents='auto';
    readable=status.contains(document.elementFromPoint((left+right)/2,(top+bottom)/2));bubble.style.pointerEvents=pointer;
   }
   return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,height:r.height,reachable:el===hit||el.contains(hit),aboveControls:box.bottom<=actions.top,readable};
  });
  assert.ok(layout.x>=0&&layout.right<=width&&layout.y>=0&&layout.bottom<=height&&layout.height>=44&&layout.reachable&&layout.aboveControls&&layout.readable,JSON.stringify({width,height,layout}));
  layouts.push({viewportWidth:width,viewportHeight:height,...layout});await page.screenshot({path:`${out}/${engine.name()}-retry-${width}x${height}.png`});
 }
 for(let attempt=2;attempt<=4;attempt++){
  await retry.click();await page.waitForFunction(()=>document.getElementById('sim-loading').dataset.state==='error');
  assert.equal(meshAttempts,attempt);assert.equal(await page.evaluate(()=>!!window.__sim.bench()),false);
  assert.equal(await identity(),true,'Malformed required geometry keeps the prior scene/conversation');
 }
 await retry.click();await page.waitForFunction(()=>window.__sim.bench()?.active);await hidden();
 assert.equal(meshAttempts,5);
 assert.equal(await page.evaluate(()=>window.__sim.bench().api.mechanism.parts.length===window.__sim.bench().manifest.parts.length),true);
 assert.equal(await page.locator('#tb-actions').count(),1);assert.equal(await identity(),true);
 // Stale completion tokens cannot hide a newer status, including finally-style cleanup.
 const tokens=await page.evaluate(async()=>{const {createLoadingStatus}=await import('./kit/loading.js');const s=createLoadingStatus(document.body);const first=s.begin('First');const second=s.begin('Second');s.fail('Old failure',{token:first});s.ready(first);const before=s.element.textContent;s.ready(second);const result={before,hidden:s.element.hidden};s.dispose();return result;});
 assert.match(tokens.before,/Second/);assert.equal(tokens.hidden,true);
 assert.deepEqual(errors,[]);assert.equal(await page.evaluate(()=>document.body.dataset.stageError),undefined);
 assert.deepEqual(await(await context.request.get(base+'/version.json')).json(),version,'The same build must serve the whole test');
 await writeFile(`${out}/${engine.name()}-report.json`,JSON.stringify({checkedAt:new Date().toISOString(),base,version,moduleAttempts,designAttempts,summaryAttempts,recordingAttempts,meshAttempts,layouts,errors},null,2));
 console.log(`PASS ${engine.name()}: nonblocking navigation, static startup/retry, visible delayed loads, model retry, retained scene/conversation, manual takeover cancellation, strict bench parts/retry, phone actions and stale status tokens`);
} finally {releaseNav?.();releaseModel?.();releaseRun?.();releaseDesign?.();await browser.close();}
