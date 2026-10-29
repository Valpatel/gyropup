import { acknowledgePrototypeNotice } from './test-prototype-session.mjs';
/** The default experience must use the current model; recordings keep their matching archived geometry. */
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {chromium,webkit} from '@playwright/test';
const base=(process.env.SITE_URL||'http://127.0.0.1:8883').replace(/\/$/,'');
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
const context=await browser.newContext({viewport:{width:1280,height:900}});
await acknowledgePrototypeNotice(context);
await context.addInitScript(()=>localStorage.setItem('gyropup.probe','off'));
const page=await context.newPage(),errors=[],requests=[];page.setDefaultTimeout(90000);
page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
const out=process.env.TEST_OUTPUT||'/tmp/gyropup-live-demo';await mkdir(out,{recursive:true});
const action=name=>page.locator(`#robot-actions [data-action=${name}]`);
const snap=()=>page.evaluate(()=>{const s=window.__sim;return {t:s.demo.t,base:s.state.robot.base.position.toArray(),rotation:s.state.robot.base.quaternion.toArray(),position:s.state.robot.group.position.toArray(),wheel:s.state.wheel,shots:s.demo.shots,balls:s.balls.active.map(b=>b.g.position.toArray())};});
try{
 await page.goto(base+'/designer/sim.html?sound=0',{waitUntil:'networkidle'});
 await page.waitForFunction(()=>document.body.dataset.ready==='1'&&window.__sim.talk);
 const initial=await page.evaluate(()=>{const s=window.__sim;window.liveIdentity={scene:s.stage.scene,robot:s.state.robot,talk:s.talk};return {demo:s.demo.on,replay:!!s.state.replay,presentation:s.state.robot.presentation,speed:s.state.robot.turret.launchSpeed};});
 assert.equal(initial.demo,true);assert.equal(initial.replay,false);assert.equal(initial.presentation.mode,'current');assert.equal(initial.speed,15.85);
 assert.equal(requests.some(u=>/\/exports\/sim\/v2\/(targets|stand|drive)\.json/.test(u)),false,'Default demo does not silently fetch recorded activities');
 await page.waitForFunction(()=>window.__sim.demo.t>.05);
 await page.evaluate(()=>{window.__sim.demo.t=10.9;window.__sim.demo.nextShot=0;}); // Exercise the aim/fire phase boundary without a slow-renderer wall-clock assumption.
 await page.waitForFunction(()=>window.__sim.demo.shots>0);
 await page.waitForFunction(()=>window.__sim.demo.hits>0);
 const active=await page.evaluate(()=>{const s=window.__sim,b=s.balls.active[0];return {phase:s.demo.phase,shots:s.demo.shots,hits:s.demo.hits,launchSpeed:s.state.robot.turret.launchSpeed,ballCount:s.balls.count};});
 assert.equal(active.phase,'Target practice');assert.ok(active.ballCount>0);
 await action('play').click();const paused=await snap();await page.waitForTimeout(250);assert.deepEqual(await snap(),paused,'Pause freezes the live mechanism, movement, clock and balls');
 await action('play').click();await page.waitForFunction(t=>window.__sim.demo.t>t,paused.t);
 const oldMag=await page.evaluate(()=>window.__sim.gun.mag);
 await action('fire').click();await page.waitForFunction(n=>window.__sim.gun.mag<n,oldMag);
 assert.equal(await page.evaluate(()=>window.__sim.demo.on),false,'Manual fire takes over the same live scene');
 await action('reload').click();assert.equal(await page.evaluate(()=>window.__sim.gun.mag),30);
 await page.waitForFunction(()=>Math.abs(window.__sim.state.robot.turret.model.groups.flap.rotation.x)>.15);
 await page.waitForFunction(()=>Math.abs(window.__sim.state.robot.turret.model.groups.flap.rotation.x)<.01);
 // Repeated archive/current changes preserve both source correctness and scene identity.
 for(let i=0;i<3;i++){
  await page.selectOption('#run-select','v2/targets');
  await page.waitForFunction(()=>window.__sim.state.replay?.key==='v2/targets');
  assert.equal(await page.evaluate(()=>window.__sim.state.robot.presentation.mode),'recorded');
  assert.match(await page.locator('#robot-actions [data-status]').textContent(),/Recorded physics.*earlier turret/);
  await action('play').click();assert.equal(await page.evaluate(()=>window.__sim.state.replay.playing),false);
  await page.selectOption('#robot-actions select','demo');
  await page.waitForFunction(()=>window.__sim.demo.on&&!window.__sim.state.replay&&window.__sim.state.robot.presentation.mode==='current');
  assert.equal(await page.evaluate(()=>window.__sim.state.robot.turret.launchSpeed),15.85);
  assert.equal(await page.evaluate(()=>{const s=window.__sim,k=window.liveIdentity;return s.stage.scene===k.scene&&s.state.robot===k.robot&&s.talk===k.talk;}),true);
 }
 // Loading an older recording must not reclaim control after a newer live choice.
 let releaseRun,runRequested;
 const requested=new Promise(resolve=>{runRequested=resolve;});
 await page.route('**/exports/sim/v2/squat.json',async route=>{await new Promise(resolve=>{releaseRun=resolve;runRequested();});await route.continue();});
 await page.selectOption('#run-select','v2/squat');await requested;
 await page.selectOption('#robot-actions select','demo');
 const received=page.waitForResponse(r=>r.url().endsWith('/exports/sim/v2/squat.json'));
 releaseRun();await (await received).finished();
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 assert.equal(await page.evaluate(()=>window.__sim.demo.on&&!window.__sim.state.replay&&window.__sim.state.robot.presentation.mode==='current'),true,'Late recording response cannot replace live play');
 // Drive and reload stages use the existing scene and mechanism, without teleporting or replacing the character.
 await page.evaluate(()=>{window.__sim.demo.t=4.3;window.driveStart=window.__sim.state.robot.group.position.z;});
 await page.waitForFunction(()=>window.__sim.state.robot.group.position.z>window.driveStart+.002);
 const speed=page.locator('.hud-slider').filter({hasText:/^Drive speed/}).locator('input');
 assert.ok(await speed.evaluate(e=>Math.abs(+e.value-window.__sim.state.speed)<=.026),'Drive slider follows demo motion to its displayed precision');
 await speed.fill('0.15');
 assert.equal(await page.evaluate(()=>window.__sim.demo.on),false);assert.equal(await page.evaluate(()=>window.__sim.state.speed),.15);
 await page.selectOption('#robot-actions select','demo');
 await page.evaluate(()=>{window.__sim.demo.t=20.01;window.__sim.demo.reloaded=false;});
 await page.waitForFunction(()=>window.__sim.demo.phase==='Ready again'&&Math.abs(window.__sim.state.robot.turret.model.groups.flap.rotation.x)>.15);
 assert.equal(await page.evaluate(()=>window.__sim.gun.mag),30);
 assert.equal(await page.evaluate(()=>{const s=window.__sim,k=window.liveIdentity;return s.stage.scene===k.scene&&s.state.robot===k.robot&&s.talk===k.talk;}),true);
 // A manual pose edit cannot be immediately overwritten by demo automation.
 const height=page.locator('.hud-slider').filter({hasText:/^Height/}).locator('input');
 await height.evaluate(e=>{e.value='.31';e.dispatchEvent(new Event('input',{bubbles:true}));});
 assert.equal(await page.evaluate(()=>window.__sim.demo.on),false);assert.equal(await page.evaluate(()=>window.__sim.state.height),.31);
 await page.waitForTimeout(180);assert.equal(await page.evaluate(()=>window.__sim.state.height),.31);
 assert.equal(await speed.inputValue(),'0','Stopping demo also clears its displayed drive speed');
 await page.screenshot({path:`${out}/${engine.name()}-current-live.png`});
 assert.deepEqual(errors,[]);assert.equal(await page.evaluate(()=>document.body.dataset.stageError),undefined);
 await writeFile(`${out}/${engine.name()}-report.json`,JSON.stringify({base,initial,active,errors},null,2));
 console.log(`PASS ${engine.name()}: current default live model/physics, autonomous aim/shots/hits, true pause, manual fire/reload/drive takeover, animated reload, repeated recorded/current swaps, late-request cancellation, scene/character identity`);
}finally{await browser.close();}
