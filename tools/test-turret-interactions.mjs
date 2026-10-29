import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {chromium,webkit} from '@playwright/test';
const base=(process.env.SITE_URL||'http://127.0.0.1:8882').replace(/\/$/,'');
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];
const out=process.env.TEST_OUTPUT||'/tmp/gyropup-turret-interactions';await mkdir(out,{recursive:true});
page.on('pageerror',e=>errors.push(e.message));
await page.addInitScript(()=>localStorage.setItem('gyropup.probe','off'));
try{
 await page.goto(base+'/designer/sim.html?design=turret-box&run=none&sound=0',{waitUntil:'networkidle'});
 await page.waitForFunction(()=>window.__sim?.bench()?.active);
 await page.waitForFunction(()=>window.__sim.talk);
 await page.evaluate(()=>window.__sim.talk.ask('Remember our orange reload jar.'));
 await page.evaluate(()=>{const s=window.__sim,b=s.bench();b.api.aim(-140,0);b.api.arm(true);
  window.kept={scene:s.stage.scene,renderer:s.stage.renderer,talk:s.talk,conversation:s.talk.conversation,mechanism:b.api.mechanism.world,jar:b.api.mechanism.refill.jar};});
 await page.waitForFunction(()=>window.__sim.bench().api.prediction.points.length>4);
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
 await page.waitForFunction(()=>!window.__sim.bench().api.state.reloading,null,{timeout:15000});
 const completed=await page.evaluate(()=>{const s=window.__sim,a=s.bench().api,m=a.mechanism,k=window.kept;return {count:a.state.pile+a.state.pockets.filter(Boolean).length,angle:a.state.flapAngle,hidden:!m.refill.group.visible,jar:m.refill.jar===k.jar,scene:s.stage.scene===k.scene,renderer:s.stage.renderer===k.renderer,talk:s.talk===k.talk,conversation:JSON.stringify(s.talk.conversation)===JSON.stringify(k.conversation),mechanism:m.world===k.mechanism};});
 assert.deepEqual(completed,{count:30,angle:0,hidden:true,jar:true,scene:true,renderer:true,talk:true,conversation:true,mechanism:true},'Completed in same scene/conversation; capacity exact; pooled jar hidden; flap closed');
 // Full hopper does not start a second pour. Reduced-motion completion follows the same state path.
 assert.equal(await page.evaluate(()=>window.__sim.bench().api.reload()),false);
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.evaluate(()=>{const a=window.__sim.bench().api;a.state.pile-=3;a.reload();});
 await page.waitForFunction(()=>!window.__sim.bench().api.state.reloading,null,{timeout:5000});
 assert.equal(await page.evaluate(()=>{const a=window.__sim.bench().api;return a.state.pile+a.state.pockets.filter(Boolean).length;}),30);
 await page.emulateMedia({reducedMotion:'no-preference'});
 const phones=[];
 for(const [width,height] of [[320,568],[360,640],[390,844],[430,932],[844,390]]){
  await page.setViewportSize({width,height});await page.waitForTimeout(100);
  const metrics=await page.evaluate(()=>{
   const b=document.querySelector('.tb-reload'),r=b.getBoundingClientRect(),el=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
   return {visible:!!el&&b.contains(el),x:r.x,y:r.y,w:r.width,h:r.height,overflow:document.documentElement.scrollWidth-innerWidth};});
  assert.ok(metrics.visible&&metrics.w>=44&&metrics.h>=44,`Reload reachable ${width}x${height}: ${JSON.stringify(metrics)}`);assert.ok(metrics.overflow<=1);phones.push({width,height,...metrics});
 }
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:`${out}/${engine.name()}-phone.png`});
 assert.deepEqual(errors,[]);assert.equal(await page.evaluate(()=>document.body.dataset.stageError),undefined);
 await writeFile(`${out}/${engine.name()}-report.json`,JSON.stringify({base,arc,pouring,phones,errors},null,2));
 console.log(`PASS ${engine.name()}: visible ballistic arc; progressive jar reload; spam/fire/journey gates; paused resume; same scene/conversation; reduced motion; 5 reachable phone layouts`);
}finally{await browser.close();}
