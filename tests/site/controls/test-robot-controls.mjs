import { acknowledgePrototypeNotice } from '../assembly/build-prototype-session.mjs';
/** Real vehicle controls must remain useful while the default demo is playing. */
import assert from 'node:assert/strict';
import {safeReadinessURL,safeReadinessText} from '../layout/readiness-diagnostics.mjs';
import { checkPublicAvailability } from './sim-availability.mjs';
import { mkdir, writeFile } from 'node:fs/promises';
import { chromium, webkit } from '@playwright/test';
const base = (process.env.SITE_URL || 'http://127.0.0.1:8882').replace(/\/$/, '');
const engine = process.env.PLAYWRIGHT_BROWSER === 'webkit' ? webkit : chromium;
const browser = await engine.launch(engine === chromium ? { channel:process.env.PLAYWRIGHT_CHANNEL === 'chromium' ? undefined : 'chrome', headless:true,
  args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'] } : {headless:true});
function disableAutomaticProbe(expectedOrigin) {
 if(!/^https?:$/.test(location.protocol)||globalThis.origin!==expectedOrigin)return;
 localStorage.setItem('gyropup.probe','off');
}
const context = await browser.newContext({viewport:{width:1440,height:1000},hasTouch:true});
await acknowledgePrototypeNotice(context,base);
await context.addInitScript(disableAutomaticProbe,new URL(base).origin);
const page = await context.newPage(), errors=[];
page.on('pageerror',e=>errors.push(e.message));
const out=process.env.TEST_OUTPUT || '/tmp/gyropup-robot-controls'; await mkdir(out,{recursive:true});
const action=name=>page.locator(`#robot-actions [data-action=${name}]`);
const activity=value=>page.selectOption('#robot-actions select',value);
const ready=()=>page.waitForFunction(()=>document.body.dataset.ready==='1' && !!window.__sim.state.robot);
async function model(value) {
 await page.selectOption('#design-select',value);
 await page.waitForFunction(value=>{
  const stem=value.split('/').pop().replace(/\.json$/, '');
  const options=[...document.querySelector('#run-select').options].map(option=>option.value);
  return window.__sim.state.modelKey===value && !window.__sim.state.bench
   && ['drive','targets'].every(activity=>options.includes(`${stem}/${activity}`));
 },value);
}
// Bounded observations of this owned fixture only; no readiness decision or retry.
function observeTalkCss(page,origin) {
 const events=[],counts={},requests=new WeakMap(),started=Date.now();let dropped=0,nextRequest=0;
 const record=(event,{request,url,error,status,timing}={})=>{
  const row={event,nodeElapsedMs:Date.now()-started,url:safeReadinessURL(url??request?.url()??page.url(),origin)};
  counts[event]=(counts[event]??0)+1;
  if(request){if(!requests.has(request))requests.set(request,++nextRequest);row.requestId=requests.get(request);}
  if(error)row.error=safeReadinessText(error.message??error,origin);
  if(Number.isFinite(status))row.status=status;
  if(timing)row.browserTiming=Object.fromEntries(['startTime','requestStart','responseStart','responseEnd'].filter(key=>Number.isFinite(timing[key])).map(key=>[key,timing[key]]));
  if(events.length===64){events.shift();dropped++;}events.push(row);
 };
 const relevant=request=>{const url=new URL(request.url()),matches=url.origin===origin&&url.pathname==='/designer/character/talk.css';if(matches&&!requests.has(request))requests.set(request,++nextRequest);return matches;};
 const mainNavigation=request=>request.isNavigationRequest?.()&&request.frame()===page.mainFrame();
 const watch=(event,handler)=>page.on(event,(...args)=>{try{handler(...args);}catch(error){record('observer-error',{error});}});
 watch('request',request=>{if(relevant(request))record('request',{request,timing:request.timing()});else if(mainNavigation(request))record('navigation-request',{url:request.url(),timing:request.timing()});});
 watch('response',response=>{if(relevant(response.request()))record('response',{request:response.request(),status:response.status(),timing:response.request().timing()});else if(mainNavigation(response.request()))record('navigation-response',{url:response.url(),status:response.status(),timing:response.request().timing()});});
 watch('requestfinished',request=>{if(relevant(request))record('requestfinished',{request,timing:request.timing()});else if(mainNavigation(request))record('navigation-requestfinished',{url:request.url(),timing:request.timing()});});
 watch('requestfailed',request=>{if(relevant(request))record('requestfailed',{request,error:request.failure()?.errorText,timing:request.timing()});else if(mainNavigation(request))record('navigation-requestfailed',{url:request.url(),error:request.failure()?.errorText,timing:request.timing()});});
 watch('pageerror',error=>record('pageerror',{error}));
 watch('framenavigated',frame=>{if(frame===page.mainFrame())record('navigation',{url:frame.url()});});
 watch('domcontentloaded',()=>record('domcontentloaded'));
 return {record,snapshot:error=>({schema:'gyropup.fresh-talk-css/1',observerPerturbation:true,events:[...events],counts:{...counts},matchingRequests:nextRequest,dropped,error:error?{name:safeReadinessText(error.name,origin),message:safeReadinessText(error.message,origin)}:null})};
}
async function retainTalkCssReport(observation,error,write) {
 let timer;
 try {await Promise.race([Promise.resolve().then(()=>write(observation.snapshot(error))),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Talk CSS evidence write exceeded 2000 ms')),2000);})]);return null;}
 catch(failure){return failure;}
 finally {clearTimeout(timer);}
}
async function checkFreshLayout() {
 const fresh=await browser.newContext({viewport:{width:1280,height:900}});
await acknowledgePrototypeNotice(fresh,base);
 await fresh.addInitScript(disableAutomaticProbe,new URL(base).origin);
 const p=await fresh.newPage();p.on('pageerror',e=>errors.push(e.message));
 const evidence=observeTalkCss(p,new URL(base).origin);let failure=null;
 let releaseCss,heldCss,closing=false,routeFailure=null,routeErrors=0,nativePending=0;
 const releasers=new Set(),routes=new Set();let expireCleanup;
 const cleanupLimit=new Promise(resolve=>{expireCleanup=resolve;});
 await p.route('**/character/talk.css*',route=>{
  const task=(async()=>{
   const request=route.request();evidence.record('route-enter',{request});
   await new Promise(resolve=>{
    if(heldCss)evidence.record('held-resolver-replaced',{request:heldCss});
    const release=()=>{if(!releasers.delete(release))return;if(heldCss===request)heldCss=null;resolve();evidence.record('release',{request});};
    releasers.add(release);heldCss=request;releaseCss=release;
    if(closing)release();
   });
   evidence.record('continue-start',{request});
   try{
    const continued=route.continue();nativePending++;
    const completed=Promise.resolve(continued).then(()=>{nativePending--;return null;},error=>{nativePending--;return error;});
    const error=await Promise.race([completed,cleanupLimit]);if(error)throw error;
    evidence.record('continue-complete',{request});
   }catch(error){evidence.record('continue-failed',{request,error});throw error;}
  })().catch(error=>{routeErrors++;routeFailure??=error;});
  routes.add(task);task.then(()=>routes.delete(task));return task;
 });
 try {
  await p.goto(base+'/designer/sim.html?run=none&demo=0&sound=0',{waitUntil:'domcontentloaded'});
  await p.waitForFunction(()=>document.body.dataset.ready==='1'&&!!window.__sim.talk);
  assert.ok(releaseCss,'Fresh startup genuinely waits for delayed talk styling');
  const received=p.waitForResponse(r=>/\/character\/talk\.css/.test(r.url()));releaseCss();await (await received).finished();
  await p.waitForFunction(()=>getComputedStyle(document.querySelector('.gp-dock')).position==='fixed'&&window.__sim.stage.camera.view.offsetY<200);
  await p.evaluate(()=>document.fonts.ready);
  const bounds=await p.evaluate(async()=>{
   const THREE=await import('three'),s=window.__sim,r=s.stage.renderer.domElement.getBoundingClientRect();
   const points=[];
   s.stage.scene.updateMatrixWorld(true);s.stage.camera.updateMatrixWorld(true);
   s.state.robot.group.traverse(mesh=>{
    if(!mesh.isMesh)return;
    for(let parent=mesh;parent;parent=parent.parent)if(!parent.visible)return;
    mesh.geometry.computeBoundingBox();const box=mesh.geometry.boundingBox;
    for(let i=0;i<8;i++){
     const v=new THREE.Vector3(i&1?box.max.x:box.min.x,i&2?box.max.y:box.min.y,i&4?box.max.z:box.min.z).applyMatrix4(mesh.matrixWorld).project(s.stage.camera);
     points.push({x:r.left+(v.x+1)*r.width/2,y:r.top+(1-v.y)*r.height/2});
    }
   });
   return {top:Math.min(...points.map(v=>v.y)),bottom:Math.max(...points.map(v=>v.y)),left:Math.min(...points.map(v=>v.x)),right:Math.max(...points.map(v=>v.x)),
    freeTop:document.querySelector('#topbar').getBoundingClientRect().bottom,freeBottom:document.querySelector('.gp-dock-body').getBoundingClientRect().top,
    freeRight:document.querySelector('#panel').getBoundingClientRect().left,view:s.stage.camera.view};
  });
  assert.ok(bounds.top>=bounds.freeTop&&bounds.bottom<=bounds.freeBottom&&bounds.left>=0&&bounds.right<=bounds.freeRight,`Fresh robot fits above the dock and beside controls: ${JSON.stringify(bounds)}`);
  const projection=await p.evaluate(()=>window.__sim.stage.camera.projectionMatrix.toArray());
  await p.locator('#summary .fold').click();
  await p.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  assert.deepEqual(await p.evaluate(()=>window.__sim.stage.camera.projectionMatrix.toArray()),projection,'Stats remains an overlay after late dock layout');
  await p.screenshot({path:`${out}/${engine.name()}-fresh-manual.png`});
 } catch(error){failure=error;throw error;}
 finally {
  closing=true;let closeState='pending',cleanupFailure=null,timedOut=false;
  const timer=setTimeout(()=>{timedOut=true;expireCleanup(Error('Talk CSS cleanup exceeded 2000 ms'));},2000);
  try{
   for(const release of [...releasers]){try{release();}catch(error){cleanupFailure??=error;}}
   // Queue each released continuation before closing its owned context.
   await Promise.resolve();
   const closed=fresh.close().then(()=>{closeState='closed';evidence.record('context-closed');},error=>{closeState='failed';cleanupFailure=error;evidence.record('context-close-failed',{error});});
   const complete=(async()=>{await closed;while(routes.size)await Promise.allSettled([...routes]);return null;})();
   const bound=await Promise.race([complete,cleanupLimit]);cleanupFailure??=bound;
   // Expiry settles the owned callbacks even if a native command never answers.
   if(bound)await Promise.allSettled([...routes]);
  }catch(error){cleanupFailure??=error;expireCleanup(error);await Promise.allSettled([...routes]);}
  finally{clearTimeout(timer);}
  cleanupFailure??=routeFailure;
  const observation={snapshot:error=>({...evidence.snapshot(error),cleanup:{context:closeState,timedOut,pendingRoutes:routes.size,pendingNativeContinues:nativePending,heldReleasers:releasers.size,routeErrors}})};
  const secondary=await retainTalkCssReport(observation,failure,report=>writeFile(`${out}/${engine.name()}-fresh-talk-css.json`,JSON.stringify(report,null,2)));
  if(secondary)console.error('Talk CSS evidence: '+safeReadinessText(secondary.message,new URL(base).origin));
  if(!failure&&(cleanupFailure||secondary))throw cleanupFailure||secondary;
 }
}
async function playChecks() {
 await activity('targets');await page.waitForFunction(()=>window.__sim.state.replay?.key.endsWith('/targets'));
 await action('play').click();assert.equal(await page.evaluate(()=>window.__sim.state.replay.playing),false);
 await action('play').click();assert.equal(await page.evaluate(()=>window.__sim.state.replay.playing),true);
 await page.evaluate(()=>{const s=window.__sim;window.vehicleIdentity={scene:s.stage.scene,robot:s.state.robot,talk:s.talk,props:[...s.props.values()]};});
 await action('fire').click();await page.waitForFunction(()=>window.__sim.gun.mag===window.__sim.gun.capacity-1);
 assert.equal(await page.evaluate(()=>window.__sim.state.replay),null,'Fire takes control immediately');
 assert.equal(await page.evaluate(()=>window.__sim.demo.on),false);
 await action('burst').click();await page.waitForFunction(()=>window.__sim.gun.mag===window.__sim.gun.capacity-9);
 assert.equal(await page.evaluate(()=>{const s=window.__sim,o=window.vehicleIdentity;return s.stage.scene===o.scene && s.state.robot===o.robot && s.talk===o.talk && o.props.every(p=>[...s.props.values()].includes(p));}),true,'Live takeover keeps scene, character and target identities');
 await action('reload').click();assert.equal(await page.evaluate(()=>window.__sim.gun.mag===window.__sim.gun.capacity && window.__sim.gun.queue.length===0),true);
 assert.match(await page.locator('#robot-actions [data-ammo]').textContent(),/\d+ \/ \d+ balls/);
 await activity('drive');await page.waitForFunction(()=>window.__sim.state.replay?.key.endsWith('/drive'));
 await action('reload').click();assert.equal(await page.evaluate(()=>window.__sim.state.replay),null,'Reload also takes control from a recording');
 await activity('targets');await page.waitForFunction(()=>window.__sim.state.replay?.key.endsWith('/targets'));
 await action('demo').click();assert.equal(await page.evaluate(()=>window.__sim.demo.on),true);
 await page.waitForFunction(()=>window.__sim.state.replay===null);
 const previous=await page.evaluate(()=>{const d=window.__sim.demo;d.t=3.95;return d.phase;});
 await page.waitForFunction(previous=>window.__sim.demo.phase!==previous,previous);
 assert.equal(await page.evaluate(()=>window.__sim.talk===window.vehicleIdentity.talk),true,'Live demo phase changes keep the conversation');
 await action('play').click();assert.equal(await page.evaluate(()=>window.__sim.demo.playing),false);
 const pausedTime=await page.evaluate(()=>window.__sim.demo.t);await page.waitForTimeout(150);
 assert.equal(await page.evaluate(()=>window.__sim.demo.t),pausedTime,'Demo pause freezes its clock');
 await action('play').click();await page.waitForFunction(t=>window.__sim.demo.t>t,pausedTime);
 await activity('live');assert.equal(await page.evaluate(()=>window.__sim.state.replay),null);
 assert.equal(await action('play').isDisabled(),true,'Live mode does not pretend to pause a recording');
}
try {
 const availability = await checkPublicAvailability({ page, base, out, engine });
 await writeFile(`${out}/${engine.name()}-availability.json`, JSON.stringify({ availability, errors }, null, 2));
 if (process.env.ROBOT_CONTROL_CASE !== 'availability') {
 await page.evaluate(() => { localStorage.removeItem('gyropup-sfx'); localStorage.removeItem('gyropup-design-v1'); });
 // Availability is complete; retain its evidence and retire its independent rendered scene.
 await page.goto('about:blank');
 await checkFreshLayout();
 await page.goto(base+'/designer/sim.html',{waitUntil:'networkidle'});await ready();
 assert.equal(await page.evaluate(()=>window.__sim.demo.on && window.__sim.sfx.enabled && !window.__sim.state.replay && window.__sim.state.robot.presentation.mode==='current'),true,'Fresh visitors start with current-model live demo and sound enabled');
 await model('v2');await playChecks();
 // Light sliders affect empty sky, not just the model and yard. Bench restores
 // the robot preference after its fixed, darker target range.
 const daylight=page.locator('.hud-slider').filter({hasText:'Daylight'}).locator('input');
 await daylight.evaluate(el=>{el.value='0.05';el.dispatchEvent(new Event('input',{bubbles:true}));});
 await page.waitForFunction(()=>window.__sim.stage.scene.background.r<.06);
 const dark=await page.evaluate(()=>window.__sim.stage.scene.background.toArray());
 await page.selectOption('#design-select','turret-box');await page.waitForFunction(()=>window.__sim.bench()?.active);
 assert.equal(await page.locator('#robot-actions').isVisible(),false);
 await model('v2');await page.waitForFunction(()=>window.__sim.stage.scene.background.r<.06);
 await daylight.evaluate(el=>{el.value='1';el.dispatchEvent(new Event('input',{bubbles:true}));});
 await page.waitForFunction(()=>window.__sim.stage.scene.background.r>.7);
 assert.equal(await page.evaluate(dark=>window.__sim.stage.scene.background.toArray().every((v,i)=>v>dark[i]*5),dark),true);
 // Portrait and landscape touch targets must fit and remain reachable; drawer
 // and conversation never lie over the play controls.
 for(const [width,height] of [[320,568],[375,667],[390,844],[430,932],[768,1024],[844,390]]) {
  await page.setViewportSize({width,height});await page.waitForTimeout(150);
  await page.evaluate(()=>{if(document.body.classList.contains('drawer-open'))document.getElementById('drawer-handle').click();window.__sim.talk?.dock?.collapse(true);});
  await page.waitForTimeout(100);
  const boxes=await page.locator('#robot-actions button,#robot-actions select').evaluateAll(elements=>elements.map(el=>{const r=el.getBoundingClientRect();const top=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {text:el.textContent,w:r.width,h:r.height,x:r.x,y:r.y,right:r.right,bottom:r.bottom,reachable:el===top||el.contains(top)};}));
  for(const b of boxes) {assert.ok(b.h>=44 && b.w>=44 && b.x>=0 && b.y>=0 && b.right<=width && b.bottom<=height,`Touch control fits ${width}x${height}: ${JSON.stringify(b)}`);assert.ok(b.reachable,`Touch control is reachable ${width}x${height}: ${b.text}`);}
  await page.screenshot({path:`${out}/${engine.name()}-${width}x${height}.png`});
 }
 await page.setViewportSize({width:390,height:844});
 await model('v2');await playChecks();
 await page.goto(base+'/designer/sim.html?demo=0&sound=0&run=none',{waitUntil:'networkidle'});await ready();
 assert.equal(await page.evaluate(()=>!window.__sim.demo.on && !window.__sim.sfx.enabled && !window.__sim.state.replay),true,'Explicit opt-outs preserved');
 await page.goto(base+'/designer/sim.html?demo=0',{waitUntil:'networkidle'});await ready();
 assert.equal(await page.evaluate(()=>window.__sim.sfx.enabled),false,'Saved mute is respected');
 await page.goto(base+'/designer/sim.html?sound=1&demo=1',{waitUntil:'networkidle'});await ready();
 assert.equal(await page.evaluate(()=>window.__sim.sfx.enabled && window.__sim.demo.on),true,'Explicit on overrides saved mute');
 assert.deepEqual(errors,[]);assert.equal(await page.evaluate(()=>document.body.dataset.stageError),undefined);
 }
 assert.deepEqual(errors, []);
 console.log(process.env.ROBOT_CONTROL_CASE === 'availability'
  ? `PASS ${engine.name()}: public v1 disabled; current fallback, unavailable notice, direct URL, restored selection, reload and history`
  : `PASS ${engine.name()}: public v1 disabled; fresh delayed-CSS startup framing, stable stats overlay, current robot desktop+touch play/pause, fire/burst/reload from replay, current-model live demo/pause, stable scene/conversation, daylight sky, defaults/opt-outs and 6 phone/tablet layouts`);
} finally {await browser.close();}
