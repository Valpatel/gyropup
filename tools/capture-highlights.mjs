/** Capture actual current simulator callbacks at fixed steps; never invent a second robot rig. */
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {chromium} from '@playwright/test';
import {acknowledgePrototypeNotice} from './test-prototype-session.mjs';
const base=(process.env.SITE_URL||'http://127.0.0.1:8983').replace(/\/$/,''),out=process.env.CAPTURE_OUTPUT||'/tmp/gyropup-highlights-frames';
const width=1280,height=720,fps=30,seed=1042026;
const shots=[{id:'turret',seconds:4,bench:true},{id:'mechanism',seconds:3,bench:true},{id:'battle',seconds:6},{id:'character',seconds:3}];
const only=process.env.CAPTURE_SHOT,limit=Number(process.env.CAPTURE_FRAMES||0);
await mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const hash=b=>createHash('sha256').update(b).digest('hex');
const report={format:1,sourceRevision:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),recipeSha256:hash(await readFile(new URL(import.meta.url))),width,height,fps,seed,
  browser:browser.version(),instrumentation:'Expose the existing stage callback array to the recorder; stop its RAF loop, advance its callbacks at 60Hz with a fixed performance clock and seeded random source, then explicitly render each captured frame. No model or projectile code is replaced.',shots:[],inputs:{}};
report.servedVersion=await (await fetch(base+'/version.json')).json();
try{
for(const shot of shots.filter(s=>!only||s.id===only)){
 const dir=out+'/'+shot.id;await mkdir(dir,{recursive:true});
 const context=await browser.newContext({viewport:{width,height},deviceScaleFactor:1});await acknowledgePrototypeNotice(context);
 await context.addInitScript(seed=>{let state=seed;Math.random=()=>{state=(Math.imul(state,1664525)+1013904223)>>>0;return state/4294967296;};localStorage.setItem('gyropup.probe','off');localStorage.setItem('gyropup-sfx','0');window.__cadagentLive=true;},seed);
 const page=await context.newPage(),errors=[],requests=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('response',r=>{
  const u=new URL(r.url());if(u.origin!==new URL(base).origin||r.status()!==200)return;
  if(!/^\/(designer|exports|web)\//.test(u.pathname))return;
  requests.push((async()=>{const bytes=await r.body();let repoSha256=null;try{repoSha256=hash(await readFile(new URL('..'+u.pathname,import.meta.url)));}catch{}
   report.inputs[u.pathname]={servedSha256:hash(bytes),bytes:bytes.length,...(repoSha256?{repoSha256}:{})};})());
 });
 await page.route('**/designer/kit/stage.js*',async route=>{
  const response=await route.fetch(),text=await response.text(),needle='const callbacks = [];';
  assert.equal(text.split(needle).length,2,'Stage capture seam changed');
  await route.fulfill({response,body:text.replace(needle,needle+' window.__captureCallbacks = callbacks;')});
 });
 await page.goto(base+'/designer/sim.html?run=none&sound=0&panel=0&light=.55'+(shot.bench?'&design=turret-box':'&demo=1'));
 await page.waitForFunction(bench=>document.body.dataset.ready==='1'&&window.__sim?.talk&&(bench?window.__sim.bench()?.active:window.__sim.state.robot?.presentation.mode==='current'),shot.bench,{timeout:90000});
 await page.evaluate(async({shot,width,height})=>{
  const s=window.__sim,stage=s.stage,THREE=await import('/designer/kit/vendor/three/three.module.min.js');
  stage.stop();s.sfx.setEnabled(false);s.talk.stop();stage.controls.enabled=false;stage.controls.enableDamping=false;
  // The site header normally leaves a 64 px inset. Capture the canvas itself at a real 16:9 raster.
  Object.assign(stage.renderer.domElement.parentElement.style,{position:'fixed',inset:'0',width:width+'px',height:height+'px'});
  stage.renderer.setPixelRatio(1);stage.setInsets({left:0,right:0,top:0,bottom:0});stage.renderer.setSize(width,height,false);
  stage.camera.aspect=width/height;stage.camera.fov=35;stage.camera.clearViewOffset();stage.camera.updateProjectionMatrix();
  stage.setSceneBackground(0x15323f,0x15323f);stage.setSceneLight(shot.bench?.82:.48,true);
  let milliseconds=performance.now(),t=0;Object.defineProperty(performance,'now',{configurable:true,value:()=>milliseconds});
  const step=()=>{milliseconds+=1000/60;t+=1/60;for(const callback of window.__captureCallbacks)callback(t,1/60);};
  const box=new THREE.Box3(),add=object=>{object.updateWorldMatrix(true,true);object.traverseVisible(n=>{if(n.isMesh){n.geometry.computeBoundingBox();box.union(n.geometry.boundingBox.clone().applyMatrix4(n.matrixWorld));}});};
  if(shot.bench){
   const bench=s.bench(),a=bench.api;a.labels(false);a.airflow(false);a.antennas(false);a.view(shot.id==='mechanism'?'xray':'solid');a.aim(shot.id==='mechanism'?0:-15,-5);
   if(shot.id==='mechanism'){a.arm(true);a.fire(10);}
   for(let i=0;i<30;i++)step();
   for(const p of a.mechanism.parts){if(shot.id==='mechanism'&&['j501','adapter'].includes(p.e.group))continue;add(p.mesh);}
  }else{
   for(let i=0;i<60;i++)step();
   s.demo.on=true;s.demo.playing=true;s.demo.t=shot.id==='battle'?10.8:0;s.demo.nextShot=0;
   s.state.speed=0;step();add(s.state.robot.group);
   if(shot.id==='battle')for(const target of s.liveTargets.values())for(const mesh of target.meshes)add(mesh);
  }
  const center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3());
  const direction=shot.id==='battle'?new THREE.Vector3(1.65,.9,-1.3):shot.id==='mechanism'?new THREE.Vector3(1,.4,.4):new THREE.Vector3(.9,.5,1);
  const fit=stage.fitView(box,{direction,target:center,margin:shot.id==='mechanism'?1.13:1.12});
  const distance=fit.distance,baseAngle=Math.atan2(direction.x,direction.z),elevation=Math.asin(direction.clone().normalize().y);
  const frames=[];
  window.__highlightCapture={
   info:{bounds:box.toArray?.()||[...box.min.toArray(),...box.max.toArray()],center:center.toArray(),size:size.toArray(),distance,
    parts:shot.bench?s.bench().api.mechanism.parts.map(p=>p.e.name):s.state.robot.turret.model.parts.map(p=>p.entry.name)},
   frame(index){
    step();step();
    const progress=index/(shot.seconds*30-1),angle=baseAngle+(shot.id==='battle'?.10:shot.id==='mechanism'?.12:.42)*(progress-.5);
    if(shot.id==='turret'){s.bench().api.aim(-15+30*progress,-5);s.bench().step(t,0);}
    stage.renderer.setSize(width,height,false);stage.camera.aspect=width/height;stage.camera.clearViewOffset();stage.camera.updateProjectionMatrix();
    stage.camera.position.copy(center).add(new THREE.Vector3(Math.sin(angle)*Math.cos(elevation),Math.sin(elevation),Math.cos(angle)*Math.cos(elevation)).multiplyScalar(distance));
    stage.camera.lookAt(center);stage.controls.target.copy(center);stage.scene.updateMatrixWorld(true);stage.renderer.render(stage.scene,stage.camera);
    const observation={frame:index,shots:shot.bench?s.bench().api.state.shots:s.demo.shots,hits:shot.bench?s.bench().api.state.hits:s.demo.hits,
      targetsDown:shot.bench?s.bench().api.targets.plates.filter(p=>p.down).length:[...s.liveTargets.values()].filter(p=>p.down).length,
      error:document.body.dataset.stageError||null};
    frames.push(observation);return stage.renderer.domElement.toDataURL('image/png');
   },get observations(){return frames;}
  };
 },{shot,width,height});
 const info=await page.evaluate(()=>window.__highlightCapture.info),count=limit||shot.seconds*fps;
 for(let i=0;i<count;i++){
  const data=await page.evaluate(i=>window.__highlightCapture.frame(i),i);
  const bytes=Buffer.from(data.split(',')[1],'base64');
  assert.equal(bytes.readUInt32BE(16),width);assert.equal(bytes.readUInt32BE(20),height);
  await writeFile(`${dir}/${String(i).padStart(5,'0')}.png`,bytes);
  if(i%60===0)console.log(shot.id,i+'/'+count);
 }
 const observations=await page.evaluate(()=>window.__highlightCapture.observations);
 assert.deepEqual(errors,[]);assert.ok(observations.every(x=>!x.error),JSON.stringify(observations.find(x=>x.error)));
 if(!limit&&shot.id==='battle'){assert.ok(observations.at(-1).shots>=3);assert.ok(observations.at(-1).targetsDown>=2,'Actual demo must knock targets over');}
 if(!limit&&shot.id==='mechanism')assert.ok(observations.at(-1).shots>0,'Actual feed must emit shots');
 await Promise.all(requests);report.shots.push({...shot,frames:count,info,observations});
 await writeFile(out+'/capture-receipt.json',JSON.stringify(report,null,2)+'\n');await context.close();
}
}finally{await browser.close();await writeFile(out+'/capture-receipt.json',JSON.stringify(report,null,2)+'\n');}
console.log(JSON.stringify({out,shots:report.shots.map(s=>({id:s.id,frames:s.frames}))}));
