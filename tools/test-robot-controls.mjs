/** Real vehicle controls must remain useful while the default demo is playing. */
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium, webkit } from '@playwright/test';
const base = (process.env.SITE_URL || 'http://127.0.0.1:8882').replace(/\/$/, '');
const engine = process.env.PLAYWRIGHT_BROWSER === 'webkit' ? webkit : chromium;
const browser = await engine.launch(engine === chromium ? { channel:process.env.PLAYWRIGHT_CHANNEL === 'chromium' ? undefined : 'chrome', headless:true,
  args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'] } : {headless:true});
const context = await browser.newContext({viewport:{width:1440,height:1000},hasTouch:true});
await context.addInitScript(()=>localStorage.setItem('gyropup.probe','off'));
const page = await context.newPage(), errors=[];
page.on('pageerror',e=>errors.push(e.message));
const out=process.env.TEST_OUTPUT || '/tmp/gyropup-robot-controls'; await mkdir(out,{recursive:true});
const action=name=>page.locator(`#robot-actions [data-action=${name}]`);
const activity=value=>page.selectOption('#robot-actions select',value);
const ready=()=>page.waitForFunction(()=>document.body.dataset.ready==='1' && !!window.__sim.state.robot);
async function model(value) {
 await page.selectOption('#design-select',value);
 await page.waitForFunction(value=>window.__sim.state.modelKey===value && !window.__sim.state.bench,value);
}
async function checkFreshLayout() {
 const fresh=await browser.newContext({viewport:{width:1280,height:900}});
 await fresh.addInitScript(()=>localStorage.setItem('gyropup.probe','off'));
 const p=await fresh.newPage();p.on('pageerror',e=>errors.push(e.message));
 let releaseCss;
 await p.route('**/character/talk.css*',async route=>{await new Promise(resolve=>{releaseCss=resolve;});await route.continue();});
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
 } finally {releaseCss?.();await fresh.close();}
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
 await checkFreshLayout();
 await page.goto(base+'/designer/sim.html',{waitUntil:'networkidle'});await ready();
 assert.equal(await page.evaluate(()=>window.__sim.demo.on && window.__sim.sfx.enabled && !window.__sim.state.replay && window.__sim.state.robot.presentation.mode==='current'),true,'Fresh visitors start with current-model live demo and sound enabled');
 for(const value of ['v2','designs/default.json']) {await model(value);await playChecks();}
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
 for(const value of ['v2','designs/default.json']) {await model(value);await playChecks();}
 await page.goto(base+'/designer/sim.html?demo=0&sound=0&run=none',{waitUntil:'networkidle'});await ready();
 assert.equal(await page.evaluate(()=>!window.__sim.demo.on && !window.__sim.sfx.enabled && !window.__sim.state.replay),true,'Explicit opt-outs preserved');
 await page.goto(base+'/designer/sim.html?demo=0',{waitUntil:'networkidle'});await ready();
 assert.equal(await page.evaluate(()=>window.__sim.sfx.enabled),false,'Saved mute is respected');
 await page.goto(base+'/designer/sim.html?sound=1&demo=1',{waitUntil:'networkidle'});await ready();
 assert.equal(await page.evaluate(()=>window.__sim.sfx.enabled && window.__sim.demo.on),true,'Explicit on overrides saved mute');
 assert.deepEqual(errors,[]);assert.equal(await page.evaluate(()=>document.body.dataset.stageError),undefined);
 console.log(`PASS ${engine.name()}: fresh delayed-CSS startup framing, stable stats overlay, robot v1/v2 desktop+touch play/pause, fire/burst/reload from replay, current-model live demo/pause, stable scene/conversation, daylight sky, defaults/opt-outs and 6 phone/tablet layouts`);
} finally {await browser.close();}
