import {acknowledgePrototypeNotice} from './test-prototype-session.mjs';
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {chromium,webkit} from '@playwright/test';
const fixture=JSON.parse(await readFile(new URL('../tests/fixtures/leg-attachment-motion.json',import.meta.url)));
const base=(process.env.SITE_URL||'http://127.0.0.1:8890').replace(/\/$/,''),out=process.env.TEST_OUTPUT||'/tmp/gyropup-leg-attachment-motion';
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,
 args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
const context=await browser.newContext({viewport:{width:1280,height:900},reducedMotion:'reduce'});
await acknowledgePrototypeNotice(context);await context.addInitScript(()=>{localStorage.setItem('gyropup.probe','off');localStorage.setItem('gyropup-sfx','0');});
const page=await context.newPage(),errors=[];page.setDefaultTimeout(60000);page.on('pageerror',e=>errors.push(e.message));await mkdir(out,{recursive:true});
const sub=(a,b)=>a.map((x,i)=>x-b[i]);
function error(sample){let max=0,worst='';for(const [name,component] of Object.entries(fixture.contract.components)){
 assert.equal(sample.components[name]?.length,component.points.length,name);
 for(let i=0;i<component.points.length;i++){
  let p=component.points[i];if(component.joint){const j=fixture.contract.joints[component.joint],v=sub(p,j.pivot),a=sample.angles_deg[component.joint]*Math.PI/180;
   p=[j.pivot[0]+v[0]*Math.cos(a)-v[2]*Math.sin(a),p[1],j.pivot[2]+v[0]*Math.sin(a)+v[2]*Math.cos(a)];}
  const distance=Math.hypot(...sub(sample.components[name][i],p));if(distance>max){max=distance;worst=name;}
 }}return{max,worst};}
async function install(key){return page.evaluate(({fixture,key})=>{
 const r=key==='sim'?window.__sim.state.robot:key==='hero'?window.__heroPreview.robot:window.__talkDemo.robot;
 r.setExplode(0);
 const by=Object.fromEntries(r.legHardware.current.map(p=>[p.name,p.mesh]));
 for(const name of Object.keys(fixture.contract.components))if(name.startsWith('motor_'))by[name]=r.base.getObjectByName(name);
 window.legMotionTest={r,by,pose(angles){
  const q=[.4,-.2,.8,1,0,0,0],layout={};for(const side of ['l','r'])for(const end of ['f','r']){
   const name=`upper_${end}_${side}`;layout[`motor_${end}_${side}`]=q.length;q.push(angles[name]*Math.PI/180);
  }r.setFromQpos(q,layout);
 },capture(id,angles){
  r.group.updateWorldMatrix(true,true);const components={};
  for(const [name,indices] of Object.entries(fixture.vertex_indices)){
   const m=by[name];if(!m)throw new Error('Missing component '+name);
   components[name]=indices.map(i=>{const v=m.position.clone().fromBufferAttribute(m.geometry.attributes.position,i);m.localToWorld(v);r.base.worldToLocal(v);return[v.z*1000,v.x*1000,v.y*1000];});
  }
  return{id,angles_deg:angles,components};
 }};
 return{count:r.legHardware.current.length,legacy:r.legHardware.recorded.length,parts:r.legHardware.current.map(p=>({name:p.name,hash:p.entry.sha256,vertices:p.mesh.geometry.attributes.position.count})),source:r.presentation.legSource};
 },{fixture,key});}
try{
 await page.goto(base+'/designer/sim.html?run=none&demo=0&sound=0',{waitUntil:'networkidle'});
 await page.waitForFunction(()=>document.body.dataset.ready==='1'&&window.__sim.state.robot?.legHardware);
 const initial=await install('sim');assert.equal(initial.count,40);assert.equal(initial.legacy,4);
 const samples=await page.evaluate(poses=>poses.map((angles,i)=>{const t=window.legMotionTest;t.pose(angles);return t.capture('pose-'+i,angles);}),fixture.poses);
 let worst={max:0};for(const s of samples){const e=error(s);if(e.max>worst.max)worst=e;assert.ok(e.max<fixture.tolerance_mm,`${s.id}: ${e.worst} ${e.max}mm`);}
 // Wrong parent with exactly correct home placement must fail away from home.
 const negative=await page.evaluate(()=>{
  const t=window.legMotionTest,zero=Object.fromEntries(Object.keys(t.r.legs).flatMap(side=>['f','r'].map(end=>[`upper_${end}_${side}`,0])));
  const turn={...zero,upper_f_l:30};t.pose(zero);
  const m=t.by.output_adapter_f_l,owner=m.parent,pos=m.position.clone(),quat=m.quaternion.clone(),scale=m.scale.clone();
  t.r.base.attach(m);const parentHome=t.capture('wrong-parent-home',zero);t.pose(turn);const parentTurn=t.capture('wrong-parent-turn',turn);
  owner.add(m);m.position.copy(pos);m.quaternion.copy(quat);m.scale.copy(scale);t.pose(zero);
  // Shift the physical pivot while retaining the adapter's exact home world pose.
  const pivot=owner.position.clone(),children=owner.children.map(object=>({object,position:object.position.clone(),quaternion:object.quaternion.clone(),scale:object.scale.clone()}));
  children.forEach(p=>t.r.base.attach(p.object));owner.position.z+=.01;children.forEach(p=>owner.attach(p.object));
  const pivotHome=t.capture('wrong-pivot-home',zero);t.pose(turn);const pivotTurn=t.capture('wrong-pivot-turn',turn);
  owner.position.copy(pivot);children.forEach(p=>{p.object.position.copy(p.position);p.object.quaternion.copy(p.quaternion);p.object.scale.copy(p.scale);});t.pose(zero);
  owner.rotation.y=.25;const axis=t.capture('wrong-axis',zero);owner.rotation.y=0;t.pose(zero);
  const housing=t.by.motor_f_l,hp=housing.position.clone(),hq=housing.quaternion.clone(),hs=housing.scale.clone();
  owner.attach(housing);const housingHome=t.capture('wrong-housing-home',zero);t.pose(turn);const housingTurn=t.capture('wrong-housing-turn',turn);
  t.r.base.add(housing);housing.position.copy(hp);housing.quaternion.copy(hq);housing.scale.copy(hs);t.pose(zero);
  m.scale.multiplyScalar(1000);const units=t.capture('wrong-units',zero);m.scale.copy(scale);
  const restored=t.capture('restored',zero);return{parentHome,parentTurn,pivotHome,pivotTurn,axis,housingHome,housingTurn,units,restored};
 });
 assert.ok(error(negative.parentHome).max<.02);assert.ok(error(negative.parentTurn).max>10,'Wrong parent rejected');
 assert.ok(error(negative.pivotHome).max<.02,'Wrong pivot preserves every component at home');
 assert.ok(error(negative.pivotTurn).max>5,'Wrong pivot rejected');assert.ok(error(negative.axis).max>5,'Wrong axis rejected');
 assert.ok(error(negative.housingHome).max<.02);assert.ok(error(negative.housingTurn).max>20,'Spinning stationary housing rejected');
 assert.ok(error(negative.units).max>1000,'Unit mismatch rejected');assert.ok(error(negative.restored).max<.02);
 const transitions=await page.evaluate(async()=>{
  const t=window.legMotionTest,r=t.r;
  const archivedBefore=r.legHardware.recorded.map(m=>({name:m.name,parent:m.parent===r.base,position:m.position.toArray(),rotation:m.quaternion.toArray(),scale:m.scale.toArray()}));
  await r.setPresentation('recorded');const recorded={oldVisible:r.legHardware.recorded.every(m=>m.visible),currentHidden:r.legHardware.current.every(p=>!p.mesh.visible),source:r.presentation.legSource};
  await r.setPresentation('current');const pending=r.setPresentation('recorded');r.setPresentation('current');await pending;
  const staleProtected=r.presentation.mode==='current'&&r.legHardware.current.every(p=>p.mesh.visible)&&r.legHardware.recorded.every(m=>!m.visible);
  const zero=Object.fromEntries(Object.keys(r.legs).flatMap(side=>['f','r'].map(end=>[`upper_${end}_${side}`,0])));
  t.pose(zero);r.setExplode(.45);r.setExplode(0);
  const archivedAfter=r.legHardware.recorded.map(m=>({name:m.name,parent:m.parent===r.base,position:m.position.toArray(),rotation:m.quaternion.toArray(),scale:m.scale.toArray()}));
  return{archivedBefore,archivedAfter,recorded,staleProtected,current:r.legHardware.current.every(p=>p.mesh.visible),oldHidden:r.legHardware.recorded.every(m=>!m.visible),restored:t.capture('explosion-restored',zero)};
 });
 assert.deepEqual(transitions.archivedAfter,transitions.archivedBefore,'Archive mesh transforms unchanged');
 assert.ok(transitions.recorded.oldVisible&&transitions.recorded.currentHidden&&transitions.current&&transitions.oldHidden&&transitions.staleProtected);
 assert.ok(error(transitions.restored).max<.02,'Explosion reset restores the joint frames');
 // Closed-loop live controls and body pose changes use the same ownership.
 const live=await page.evaluate(fixture=>{
  const t=window.legMotionTest,result=[];
  for(let i=0;i<60;i++){
   t.r.setPose({height:.45+.35*Math.sin(i*.12),pitch:.08*Math.sin(i*.17),rollMM:14*Math.cos(i*.13),wheel:i*.15});
   const angles={};for(const side of ['l','r'])for(const [end,key] of [['f','upperF'],['r','upperR']])angles[`upper_${end}_${side}`]=(-t.r.legs[side][key].rotation.x-fixture.home_angle_rad[end])*180/Math.PI;
   result.push(t.capture('live-'+i,angles));
  }return result;
 },fixture);
 for(const sample of live){const e=error(sample);assert.ok(e.max<.02,`${sample.id}: ${e.worst} ${e.max}mm`);}
 await page.screenshot({path:`${out}/${engine.name()}-current.png`});
 for(const [route,key,ready] of [['/','hero',()=>window.__heroPreview?.robot.legHardware],['/designer/character/talk-demo.html','talk',()=>window.__talkDemo?.robot.legHardware]]){
  await page.goto(base+route,{waitUntil:'networkidle'});await page.waitForFunction(ready);const actual=await install(key);assert.deepEqual(actual.parts,initial.parts,`${key}: same attachments`);
  const sample=await page.evaluate(angles=>{const t=window.legMotionTest;t.pose(angles);return t.capture('route',angles);},fixture.poses.at(-1));assert.ok(error(sample).max<.02);
 }
 const delivered={};for(const file of Object.keys(fixture.source_hashes).filter(f=>f.startsWith('exports/'))){const response=await page.request.get(base+'/'+file);assert.ok(response.ok());delivered[file]=createHash('sha256').update(await response.body()).digest('hex');assert.equal(delivered[file],fixture.source_hashes[file],file);}
 for(const file of ['designer/robot_v2.js','exports/sim/v2/rig/manifest.json','exports/sim/v2/leg-attachments/manifest.json']){
  const response=await page.request.get(base+'/'+file);assert.ok(response.ok());delivered[file]=createHash('sha256').update(await response.body()).digest('hex');
 }
 const version=await(await page.request.get(base+'/version.json')).json();
 // Any missing required attachment preserves the honest landing fallback.
 await page.route('**/leg-attachments/output_screw_1.stl*',route=>route.abort());await page.goto(base+'/',{waitUntil:'networkidle'});
 await page.waitForFunction(()=>document.getElementById('robot-preview').dataset.state==='fallback');assert.equal(await page.locator('#robot-preview canvas').count(),0);
 assert.deepEqual(errors,[]);
 await writeFile(`${out}/contract.json`,JSON.stringify(fixture.contract));
 const trace={schema_version:1,length_unit:'mm',frame:'assembly-home',capture_source:`${base};${engine.name()}; actual STL vertices through world matrices; only known free-body placement removed; revision ${version.revision}; source hashes in adjacent receipt`,samples:[...samples,...live,transitions.restored]};
 await writeFile(`${out}/${engine.name()}-trace.json`,JSON.stringify(trace));
 await writeFile(`${out}/${engine.name()}-source-hashes.json`,JSON.stringify(delivered,null,2));
 await writeFile(`${out}/${engine.name()}-summary.json`,JSON.stringify({version,worst,components:44,poses:samples.length,liveFrames:live.length,negative:Object.fromEntries(Object.entries(negative).map(([k,v])=>[k,error(v)])),transitions,errors},null,2));
 console.log(`PASS ${engine.name()}: 44 components × ${samples.length} required/combined poses + ${live.length} live frames; worst ${worst.max.toFixed(6)}mm; 5 negative controls; archive transforms/race; hero/sim/talk; failed-load fallback`);
}finally{await browser.close();}
