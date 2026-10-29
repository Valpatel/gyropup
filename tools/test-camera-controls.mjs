import { acknowledgePrototypeNotice } from './test-prototype-session.mjs';
/** User gestures and stats folding must preserve a predictable view of the simulation. */
import assert from 'node:assert/strict';
import { chromium, webkit } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
const base = (process.env.SITE_URL || 'http://127.0.0.1:8882').replace(/\/$/, '');
const engine = process.env.PLAYWRIGHT_BROWSER === 'webkit' ? webkit : chromium;
const browser = await engine.launch(engine === chromium ? { channel:process.env.PLAYWRIGHT_CHANNEL === 'chromium' ? undefined : 'chrome',headless:true,
  args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'] } : {headless:true});
const context = await browser.newContext({viewport:{width:1440,height:1000},hasTouch:true});
await acknowledgePrototypeNotice(context);
const page = await context.newPage(), errors=[];
page.on('pageerror',e=>errors.push(e.message));
await context.addInitScript(()=>localStorage.setItem('gyropup.probe','off'));
const out=process.env.TEST_OUTPUT || '/tmp/gyropup-camera-controls';await mkdir(out,{recursive:true});
const distance=()=>page.evaluate(()=>{const s=window.__sim.stage;return s.camera.position.distanceTo(s.controls.target);});
async function settle(){await page.waitForTimeout(900);}
async function reaches(value) { await page.waitForFunction(value => {
 const s=window.__sim.stage;return Math.abs(s.camera.position.distanceTo(s.controls.target)-value)<1e-5;
},value,{timeout:8000}); }
async function setRadius(value=2) {
  await page.evaluate(value=>{
    const s=window.__sim.stage;s.controls.dispatchEvent({type:'start'});
    // Start each observation from rest; residual native orbit/pan damping is
    // intentional camera motion and must not masquerade as a stats-card shift.
    const damping=s.controls.enableDamping;s.controls.enableDamping=false;s.controls.update();s.controls.enableDamping=damping;
    s.camera.position.sub(s.controls.target).setLength(value).add(s.controls.target);s.controls.update();
  },value);
}
async function wheel(deltaY,deltaMode=0){return page.evaluate(({deltaY,deltaMode})=>{
  const s=window.__sim.stage, before=s.camera.position.distanceTo(s.controls.target);
  const event=new WheelEvent('wheel',{deltaY,deltaMode,bubbles:true,cancelable:true});s.renderer.domElement.dispatchEvent(event);
  return {before,after:s.camera.position.distanceTo(s.controls.target),prevented:event.defaultPrevented};
},{deltaY,deltaMode});}
async function snapshot(){return page.evaluate(()=>{const s=window.__sim.stage;return {p:s.camera.position.toArray(),q:s.camera.quaternion.toArray(),target:s.controls.target.toArray(),projection:s.camera.projectionMatrix.toArray(),autoCam:window.__sim.state.replay?.autoCam};});}
function close(a,b,label,tol=1e-7){assert.equal(a.length,b.length);assert.ok(a.every((v,i)=>Math.abs(v-b[i])<tol),label);}
try {
 await page.goto(base+'/designer/sim.html?design=turret-box&run=none&sound=0',{waitUntil:'networkidle'});
 await page.waitForFunction(()=>window.__sim?.bench()?.active);await settle();
 // Mouse and trackpad input: preserve magnitude while avoiding an immediate dolly jump.
 await setRadius();const one=await wheel(1);assert.equal(one.before,one.after);assert.equal(one.prevented,true);await settle();const fine=await distance();
 await setRadius();
 // Sample actual frames, not wall-clock polls: SwiftShader CI can render fewer
 // than three frames in 240ms even though the camera is easing correctly.
 const big=await page.evaluate(async()=>{
  const s=window.__sim.stage, radius=()=>s.camera.position.distanceTo(s.controls.target), before=radius();
  s.renderer.domElement.dispatchEvent(new WheelEvent('wheel',{deltaY:120,bubbles:true,cancelable:true}));
  const after=radius(), intermediate=[];
  for(let i=0;i<16;i++){await new Promise(requestAnimationFrame);intermediate.push(radius());}
  return {before,after,intermediate};
 });
 assert.equal(big.before,big.after);const intermediate=big.intermediate;await settle();const notch=await distance();
 assert.ok(fine>2 && fine<2.001,'One-pixel trackpad motion remains fine-grained');
 assert.ok(notch>2.025 && notch<2.04,'A 120-pixel wheel notch changes distance by about1.55%, not6.35%');
 assert.ok(new Set(intermediate.filter(v=>v>2.00001 && v<notch-1e-5).map(v=>v.toFixed(7))).size>=3,'Wheel distance eases through multiple rendered positions');
 assert.ok(intermediate.every((v,i)=>!i || v>=intermediate[i-1]-1e-8),'Easing is monotonic');
 const normalizedRadius=2*Math.pow(1/.95,.25*48/100);
 await setRadius();await wheel(3,1);await reaches(normalizedRadius);const line=await distance();
 await setRadius();await wheel(48);await reaches(normalizedRadius);assert.ok(Math.abs(line-await distance())<2e-5,'Line deltas normalize to16CSSpixels');
 // Real browser mouse wheel reaches the same capture path (not just dispatched DOM events).
 await setRadius();const canvas=await page.locator('#app canvas').boundingBox();await page.mouse.move(canvas.x+canvas.width*.45,canvas.y+canvas.height*.55);await page.mouse.wheel(0,-120);await settle();assert.ok((await distance())<1.98 && (await distance())>1.96,'Real wheel zooms inward smoothly');
 // Both limits clamp without a backlog of accumulated overscroll.
 const limits=await page.evaluate(()=>{const c=window.__sim.stage.controls;return {min:c.minDistance,max:c.maxDistance};});
 await setRadius(limits.min*1.01);for(let i=0;i<10;i++)await wheel(-1200);await reaches(limits.min);assert.ok(Math.abs(await distance()-limits.min)<1e-5);
 await wheel(120);await settle();assert.ok((await distance())>limits.min*1.01,'Reversing direction leaves near limit immediately');
 await setRadius(limits.max*.99);for(let i=0;i<10;i++)await wheel(1200);await reaches(limits.max);assert.ok(Math.abs(await distance()-limits.max)<1e-5);
 await wheel(-120);await settle();assert.ok((await distance())<limits.max*.99,'Reversing direction leaves far limit immediately');
 // A new user gesture cancels pending wheel inertia, and native orbit/pan stay functional.
 await setRadius();await wheel(120);await page.evaluate(()=>window.__sim.stage.controls.dispatchEvent({type:'start'}));const cancelled=await distance();await settle();assert.ok(Math.abs(cancelled-await distance())<1e-7);
 const orbitBefore=await snapshot();await page.mouse.move(canvas.width*.4,canvas.height*.5);await page.mouse.down();await page.mouse.move(canvas.width*.4+60,canvas.height*.5+10,{steps:6});await page.mouse.up();await settle();const orbitAfter=await snapshot();assert.ok(orbitAfter.q.some((v,i)=>Math.abs(v-orbitBefore.q[i])>.001),'Orbit remains active');
 await setRadius();const panBefore=await snapshot();await page.mouse.move(canvas.width*.4,canvas.height*.5);await page.mouse.down({button:'right'});await page.mouse.move(canvas.width*.4+40,canvas.height*.5+15,{steps:6});await page.mouse.up({button:'right'});await settle();const panAfter=await snapshot();assert.ok(panAfter.target.some((v,i)=>Math.abs(v-panBefore.target[i])>.001),'Pan remains active');
 // Real two-finger touch input via the browser protocol; symmetric pinch avoids intentional two-finger pan.
 if(engine===chromium){
  await setRadius();const client=await context.newCDPSession(page);const x=canvas.width*.45,y=canvas.height*.5;
  const aim=()=>page.evaluate(()=>{const s=window.__sim.bench().api.state;return [s.panCmd,s.tiltCmd];});
  const initialAim=await aim();
  await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:x-50,y,id:1},{x:x+50,y,id:2}]});
  const pinch=[];
  for(let i=1;i<=8;i++){await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x-50-i*5,y,id:1},{x:x+50+i*5,y,id:2}]});await page.waitForTimeout(20);pinch.push(await distance());}
  await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await settle();
  assert.ok((await distance())<1.85 && (await distance())>1.65,'Native touch pinch uses fine continuous scaling');
  assert.ok(pinch.every((v,i)=>!i || v<=pinch[i-1]+1e-7) && new Set(pinch.map(v=>v.toFixed(5))).size>=5,`Touch pinch progresses continuously: ${pinch}`);
  close(initialAim,await aim(),'Pinch never changes turret aim');
  await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:x-30,y,id:1},{x:x+30,y,id:2}]});
  await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:x-31,y,id:1},{x:x+31,y,id:2}]});
  await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  close(initialAim,await aim(),'Tiny two-finger gesture is not an aim tap');
  await page.mouse.click(x,y,{button:'right'});
  close(initialAim,await aim(),'Right click is not an aim tap');
  await client.detach();
 }
 // Stats card collapse/expand must not change pose, projection or camera-follow ownership.
 await setRadius();await settle();let before=await snapshot();
 for(let i=0;i<4;i++)await page.locator('#summary .fold').click();await settle();let after=await snapshot();
 for(const key of ['p','q','target','projection'])close(before[key],after[key],`Bench stats does not change ${key}`);
 await page.selectOption('#design-select','v2');await page.waitForFunction(()=>window.__sim.state.modelKey==='v2' && !window.__sim.state.bench);
 await page.selectOption('#run-select','v2/drive');await page.waitForFunction(()=>window.__sim.state.replay?.key==='v2/drive');
 await page.evaluate(()=>{window.__sim.state.replay.playing=false;window.__sim.stage.controls.dispatchEvent({type:'start'});});await setRadius();await settle();before=await snapshot();
 assert.equal(before.autoCam,false);for(let i=0;i<4;i++)await page.locator('#summary .fold').click();await settle();after=await snapshot();
 assert.equal(after.autoCam,false,'Stats does not reacquire replay camera');for(const key of ['p','q','target','projection'])close(before[key],after[key],`Replay stats does not change ${key}`);
 assert.deepEqual(errors,[]);assert.equal(await page.evaluate(()=>document.body.dataset.stageError),undefined);
 const result={browser:engine.name(),fineRatio:fine/2,notchRatio:notch/2,intermediate,realTouchPinch:engine===chromium,statsStable:true};
 await writeFile(`${out}/${engine.name()}.json`,JSON.stringify(result,null,2));
 console.log(`PASS ${engine.name()}: proportional/eased wheel, delta modes, real wheel, bounds/reversal, gesture cancellation, orbit/pan${engine===chromium?', real two-finger pinch':''}, stable bench/replay stats`);
} finally {await browser.close();}
