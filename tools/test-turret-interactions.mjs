import { acknowledgePrototypeNotice } from './test-prototype-session.mjs';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {chromium,webkit} from '@playwright/test';
const base=(process.env.SITE_URL||'http://127.0.0.1:8882').replace(/\/$/,'');
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];
await acknowledgePrototypeNotice(page);
page.setDefaultTimeout(90000); // Software-rendered CI advances capped simulation time slowly.
async function resize(width,height){
 const wasPhone=page.viewportSize().width<900;
 await page.setViewportSize({width,height});
 if(wasPhone!==(width<900))await page.waitForFunction(phone=>document.getElementById('drawer-handle').getAttribute('aria-expanded')===(phone?'false':'true'),width<900);
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
}

const out=process.env.TEST_OUTPUT||'/tmp/gyropup-turret-interactions';await mkdir(out,{recursive:true});
page.on('pageerror',e=>errors.push(e.message));
await page.addInitScript(()=>localStorage.setItem('gyropup.probe','off'));
try{
 await page.goto(base+'/designer/sim.html?design=turret-box&run=none&sound=0',{waitUntil:'networkidle'});
 await page.waitForFunction(()=>window.__sim?.bench()?.active);
 await page.waitForFunction(()=>window.__sim.talk);
 // Native controls own their keys; releasing a shortcut after focus moves still clears it.
 const guide=page.getByRole('checkbox',{name:'Show curved shot guide',exact:true});
 await guide.focus();await page.keyboard.press('Space');assert.equal(await guide.isChecked(),false);
 assert.equal(await page.evaluate(()=>window.__sim.bench().api.state.arm.size),0);
 await page.keyboard.press('Space');assert.equal(await guide.isChecked(),true);
 const rate=page.getByRole('slider',{name:/Rate of fire/});
 await rate.fill('1');await rate.dispatchEvent('input');
 await rate.focus();await page.keyboard.press('ArrowRight');assert.equal(await rate.inputValue(),'2');
 await page.keyboard.press('ArrowLeft');assert.equal(await rate.inputValue(),'1');
 await page.evaluate(()=>document.activeElement.blur());await page.keyboard.down('Space');
 await rate.focus();await page.keyboard.up('Space');assert.equal(await page.evaluate(()=>window.__sim.bench().api.state.arm.size),0);
 await page.getByRole('combobox',{name:'Part',exact:true}).selectOption({index:1});
 assert.ok(await page.evaluate(()=>!!window.__sim.bench().api.state.selected));
 await page.getByRole('combobox',{name:'Part',exact:true}).selectOption('');
 assert.equal(await page.evaluate(()=>window.__sim.bench().api.state.selected?.e.name??null),null);
 const armButton=page.locator('.tb-arm'),fireButton=page.locator('.tb-fire');
 await armButton.focus();await page.keyboard.down('Space');
 assert.ok(await page.evaluate(()=>window.__sim.bench().api.state.arm.has('button')));
 await page.keyboard.up('Space');assert.equal(await page.evaluate(()=>window.__sim.bench().api.state.arm.size),0);
 await armButton.focus();await page.keyboard.down('Enter');await rate.focus();
 assert.equal(await page.evaluate(()=>window.__sim.bench().api.state.arm.size),0,'Blur releases button hold');await page.keyboard.up('Enter');
 await page.evaluate(()=>window.__sim.bench().api.arm(true));await fireButton.focus();await page.keyboard.down('Enter');
 assert.equal(await page.evaluate(()=>window.__sim.bench().api.state.trigger),true);await page.keyboard.up('Enter');
 assert.equal(await page.evaluate(()=>window.__sim.bench().api.state.trigger),false);await page.evaluate(()=>window.__sim.bench().api.arm(false));
 // A journey must reunite exploded geometry before its ball enters the barrel.
 await page.evaluate(()=>window.__sim.bench().api.explode(1));
 await page.waitForFunction(()=>window.__sim.bench().api.state.explode>.9);
 await page.evaluate(()=>window.__sim.bench().api.journey(6));
 assert.equal(await page.evaluate(()=>!!window.__sim.bench().api.state.journey.ball),false,'No disconnected ball during reassembly');
 await page.locator('[data-j=play]').click(); // Pause during assembly must still place the pending stage.
 await page.waitForFunction(()=>window.__sim.bench().api.state.journey.step===6&&!window.__sim.bench().api.state.journey.reassembling);
 const bore=await page.evaluate(()=>{
  const a=window.__sim.bench().api,m=a.mechanism,p=m.parts.find(p=>p.e.part==='barrel').mesh;
  p.geometry.computeBoundingBox();const box=p.geometry.boundingBox;
  const center=p.position.clone();box.getCenter(center);center.z=box.max.z;
  p.localToWorld(center);const muzzle=m.muzzle.getWorldPosition(center.clone());
  const ball=a.state.journey.ball.g.getWorldPosition(center.clone());
  const axis=center.clone().set(0,0,1).applyQuaternion(p.getWorldQuaternion(p.quaternion.clone()));
  return {mouthErrorMM:center.distanceTo(muzzle)*1000,ballAxisErrorMM:ball.sub(center).cross(axis).length()*1000};
 });
 assert.ok(bore.mouthErrorMM<.001&&bore.ballAxisErrorMM<.001,`Journey follows actual barrel: ${JSON.stringify(bore)}`);
 // Manual stage navigation must demonstrate nominal flight, even when paused before wheel spin-up.
 await page.evaluate(()=>{window.__sim.bench().api.state.rpm=1;});
 await page.locator('[data-j=next]').click();
 const flight=await page.evaluate(()=>{const b=window.__sim.bench(),s=b.api.state,ball=s.flying.find(b=>b.demo);return {speed:ball.v.length(),nominal:b.manifest.mechanics.ball.speed_mps,age:ball.age};});
 assert.ok(Math.abs(flight.speed-flight.nominal)<1e-9);assert.equal(flight.age,0);
 await page.locator('.tb-jhead button').click();
 // A live shot from inspection also waits until the visible barrel is assembled.
 await page.evaluate(()=>{const a=window.__sim.bench().api;a.explode(1);});
 await page.waitForFunction(()=>window.__sim.bench().api.state.explode>.9);
 const shotsBefore=await page.evaluate(()=>{const a=window.__sim.bench().api;a.arm(true);a.fire(1);return a.state.shots;});
 await page.waitForFunction(()=>window.__sim.bench().api.state.explodeCmd===0);
 assert.equal(await page.evaluate(()=>window.__sim.bench().api.state.shots),shotsBefore);
 await page.waitForFunction(n=>window.__sim.bench().api.state.shots>n,shotsBefore,{timeout:90000});
 assert.equal(await page.evaluate(()=>window.__sim.bench().api.state.explode),0);
 await page.evaluate(()=>window.__sim.bench().api.arm(false));
 // PAUSE freezes the demonstrated ball and all rotating mechanism parts, then PLAY resumes them.
 await page.evaluate(()=>window.__sim.bench().api.journey(2));
 await page.waitForFunction(()=>window.__sim.bench().api.state.journey.t>.05);
 await page.locator('[data-j=play]').click();
 const pose=()=>page.evaluate(()=>{const s=window.__sim.bench().api.state;return {t:s.journey.t,s:s.journey.ball.s,phi:s.phi,wheel:s.wheelAng,rpm:s.rpm,position:s.journey.ball.g.position.toArray()};});
 const frozenJourney=await pose();await page.waitForTimeout(450);assert.deepEqual(await pose(),frozenJourney);
 await page.locator('[data-j=next]').click();
 assert.equal(await page.evaluate(()=>window.__sim.bench().api.state.journey.step),3);
 const nextJourney=await pose();await page.waitForTimeout(150);assert.deepEqual(await pose(),nextJourney);
 assert.notDeepEqual(nextJourney.position,frozenJourney.position,'Manual NEXT places the paused ball in the selected stage');
 await page.locator('[data-j=play]').click();await page.waitForFunction(t=>window.__sim.bench().api.state.journey.t>t,nextJourney.t);
 await page.locator('.tb-jhead button').click();
 await page.evaluate(()=>window.__sim.talk.ask('Remember our orange reload jar.'));
 await page.evaluate(()=>{const s=window.__sim,b=s.bench();b.api.aim(-140,0);b.api.arm(true);
  window.kept={scene:s.stage.scene,renderer:s.stage.renderer,talk:s.talk,conversation:s.talk.conversation,mechanism:b.api.mechanism.world,jar:b.api.mechanism.refill.jar};});
 await page.waitForFunction(()=>window.__sim.bench().api.prediction.points.length>4&&window.__sim.bench().api.prediction.arc.visible);
 const arc=await page.evaluate(()=>{
  const a=window.__sim.bench().api,p=a.prediction,points=p.points,start=points[0],last=points.at(-1),line=last.clone().sub(start),len=line.length();line.normalize();
  const bend=Math.max(...points.map(v=>v.clone().sub(start).cross(line).length()));
  const muzzle=a.mechanism.muzzle.getWorldPosition(start.clone());
  return {bend,startError:start.distanceTo(muzzle),visible:p.arc.visible,segments:p.arc.count,laser:p.laser.visible,length:len};
 });
 assert.ok(arc.bend>.025,'Primary guide follows a visibly curved ballistic path');assert.ok(arc.startError<.001,'Arc starts at muzzle');assert.ok(arc.visible&&arc.segments>4);assert.equal(arc.laser,false,'Straight laser is opt-in');
 await page.screenshot({path:`${out}/${engine.name()}-arc.png`});
 await page.evaluate(()=>{const b=window.__sim.bench();b.api.arm(false);b.api.aim(0,-3);b.frame('turret');const s=b.api.state;s.pockets.fill(false);s.pile=0;window.reloadShots=s.shots;});
 await page.waitForTimeout(900);
 await page.getByRole('button',{name:'Reload hopper',exact:true}).click();
 assert.ok(await page.evaluate(()=>window.__sim.bench().api.state.reloading));
 assert.equal(await page.evaluate(()=>{const s=window.__sim.bench().api.state;return s.pile+s.pockets.filter(Boolean).length;}),0,'Reload does not instantly refill');
 await page.evaluate(()=>{const a=window.__sim.bench().api;for(let i=0;i<10;i++){a.reload();a.arm(true);a.fire(5);a.journey();}});
 await page.waitForFunction(()=>{const a=window.__sim.bench().api;return a.state.reloading?.elapsed>2.25;});
 const pouring=await page.evaluate(()=>{const a=window.__sim.bench().api,m=a.mechanism;return {count:a.state.pile+a.state.pockets.filter(Boolean).length,angle:a.state.flapAngle,jar:m.refill.group.visible,balls:m.refill.stream.filter(b=>b.visible).length,shots:a.state.shots,journey:!!a.state.journey,opening:m.refill.opening.toArray()};});
 assert.ok(pouring.count>0&&pouring.count<30);assert.ok(pouring.angle>Math.PI/2);assert.ok(pouring.jar&&pouring.balls>0);assert.equal(pouring.shots,await page.evaluate(()=>window.reloadShots));assert.equal(pouring.journey,false);assert.deepEqual(pouring.opening.map(x=>Math.round(x*1000)),[0,85,-68]);
 await page.screenshot({path:`${out}/${engine.name()}-pouring.png`});
 assert.ok(await page.evaluate(()=>{const s=window.__sim,j=s.bench().api.mechanism.refill.jar;let ok=true;j.traverse(o=>{if(o.isMesh&&o.visible){o.geometry.computeBoundingBox();const b=o.geometry.boundingBox;for(let i=0;i<8;i++){const p=o.position.clone().set(i&1?b.max.x:b.min.x,i&2?b.max.y:b.min.y,i&4?b.max.z:b.min.z);o.localToWorld(p);p.project(s.stage.camera);if(Math.abs(p.x)>1||Math.abs(p.y)>1||p.z>1)ok=false;}}});return ok;}),'Reload jar stays on screen even from a close inspection');
 // Hardware switches pause this same reload; returning resumes it without replacing the character.
 const paused=await page.evaluate(()=>window.__sim.bench().api.state.reloading.elapsed);
 await page.selectOption('#design-select','v2');await page.waitForFunction(()=>window.__sim.state.modelKey==='v2'&&!window.__sim.state.bench);
 const frozen=await page.evaluate(()=>window.__sim.bench().api.state.reloading?.elapsed);
 await page.waitForTimeout(180);
 assert.equal(await page.evaluate(()=>window.__sim.bench().api.state.reloading?.elapsed),frozen);
 assert.ok(frozen>=paused);
 await page.selectOption('#design-select','turret-box');await page.waitForFunction(()=>window.__sim.bench().active);
 await page.waitForFunction(()=>!window.__sim.bench().api.state.reloading,null,{timeout:60000});
 const completed=await page.evaluate(()=>{const s=window.__sim,a=s.bench().api,m=a.mechanism,k=window.kept;return {count:a.state.pile+a.state.pockets.filter(Boolean).length,angle:a.state.flapAngle,hidden:!m.refill.group.visible,jar:m.refill.jar===k.jar,scene:s.stage.scene===k.scene,renderer:s.stage.renderer===k.renderer,talk:s.talk===k.talk,conversation:JSON.stringify(s.talk.conversation)===JSON.stringify(k.conversation),mechanism:m.world===k.mechanism};});
 assert.deepEqual(completed,{count:30,angle:0,hidden:true,jar:true,scene:true,renderer:true,talk:true,conversation:true,mechanism:true},'Completed in same scene/conversation; capacity exact; pooled jar hidden; flap closed');
 // Full hopper does not start a second pour. Reduced-motion completion follows the same state path.
 assert.equal(await page.evaluate(()=>window.__sim.bench().api.reload()),false);
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.evaluate(()=>{const a=window.__sim.bench().api;a.state.pile-=3;a.reload();});
 await page.waitForFunction(()=>!window.__sim.bench().api.state.reloading,null,{timeout:60000});
 assert.equal(await page.evaluate(()=>{const a=window.__sim.bench().api;return a.state.pile+a.state.pockets.filter(Boolean).length;}),30);
 await page.emulateMedia({reducedMotion:'no-preference'});
 const phones=[];
 for(const [width,height] of [[320,568],[360,640],[390,844],[430,932],[844,390]]){
  await resize(width,height);
  await page.evaluate(()=>window.__sim.bench().api.select('pan_base'));
  const metrics=await page.evaluate(()=>{
   const b=document.querySelector('.tb-reload'),r=b.getBoundingClientRect(),el=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
   const card=document.getElementById('tb-card').getBoundingClientRect(),bar=document.getElementById('tb-actions').getBoundingClientRect();
   const overlap=Math.min(card.right,bar.right)>Math.max(card.left,bar.left)&&Math.min(card.bottom,bar.bottom)>Math.max(card.top,bar.top);
   const actions=[...document.querySelectorAll('.tb-arm,.tb-fire,.tb-reload')].every(b=>{const r=b.getBoundingClientRect();return b.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));});
   return {overlap,actions,visible:!!el&&b.contains(el),x:r.x,y:r.y,w:r.width,h:r.height,overflow:document.documentElement.scrollWidth-innerWidth};});
  assert.ok(!metrics.overlap&&metrics.actions&&metrics.visible&&metrics.w>=44&&metrics.h>=44,`Reload reachable ${width}x${height}: ${JSON.stringify(metrics)}`);assert.ok(metrics.overflow<=1);phones.push({width,height,...metrics});
 }
 await page.evaluate(()=>window.__sim.bench().api.select(null));
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:`${out}/${engine.name()}-phone.png`});
 // Text chips must remain optically centered, with useful tap targets, at desktop and phone widths.
 await page.selectOption('#design-select','v2');await page.waitForFunction(()=>!window.__sim.state.bench);
 const centers=[];
 for(const [width,height] of [[1280,900],[320,568],[390,844]]){
  await resize(width,height);
  const drawer=page.locator('#drawer-handle');if(await drawer.isVisible()&&await drawer.getAttribute('aria-expanded')==='false')await drawer.click();
  await page.evaluate(()=>{document.querySelector('#hud').classList.remove('panel-collapsed');document.querySelectorAll('#panel details').forEach(d=>d.open=true);});
  const auto=page.locator('button.hud-chip[data-id=auto]');await auto.scrollIntoViewIfNeeded();
  const c=await auto.evaluate(b=>{const r=b.getBoundingClientRect(),range=document.createRange();range.selectNodeContents(b);const t=range.getBoundingClientRect();return {dx:t.x+t.width/2-r.x-r.width/2,dy:t.y+t.height/2-r.y-r.height/2,w:r.width,h:r.height};});
  assert.ok(Math.abs(c.dx)<1&&Math.abs(c.dy)<2&&c.w>=44&&c.h>=44,`AUTO centered ${width}: ${JSON.stringify(c)}`);centers.push({width,height,...c});
  await auto.click();assert.ok(await auto.evaluate(b=>b.classList.contains('active')));
 }
 assert.deepEqual(errors,[]);assert.equal(await page.evaluate(()=>document.body.dataset.stageError),undefined);
 await writeFile(`${out}/${engine.name()}-report.json`,JSON.stringify({base,arc,bore,flight,pouring,phones,centers,errors},null,2));
 console.log(`PASS ${engine.name()}: visible ballistic arc; progressive jar reload; spam/fire/journey gates; paused resume; same scene/conversation; reduced motion; 5 reachable phone layouts; native keyboard; real pause; centered AUTO`);
}catch(error){console.error('Failure state',await page.evaluate(()=>{const s=window.__sim,a=s?.bench()?.api;return {error:document.body.dataset.stageError,bench:s?.state.bench,active:s?.bench()?.active,reloading:a?.state.reloading,journey:!!a?.state.journey};}).catch(()=>null),errors);throw error;}finally{await browser.close();}
