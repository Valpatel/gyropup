import { acknowledgePrototypeNotice } from './test-prototype-session.mjs';
/** Current presentation: independent CAD frames, cross-route geometry and archive isolation. */
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {chromium,webkit} from '@playwright/test';
const fixture=JSON.parse(await readFile(new URL('../tests/fixtures/turret-motion-reference.json',import.meta.url)));
const mountReference=JSON.parse(await readFile(new URL('../tests/fixtures/current-robot-mount.json',import.meta.url)));
async function stlBounds(source){
  const bytes=await readFile(new URL('../'+source.file,import.meta.url));assert.equal(createHash('sha256').update(bytes).digest('hex'),source.sha256,'Independent body datum geometry is pinned');
  const lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];
  for(let n=0;n<bytes.readUInt32LE(80);n++)for(let v=0;v<3;v++)for(let axis=0;axis<3;axis++){const x=bytes.readFloatLE(84+n*50+12+v*12+axis*4);lo[axis]=Math.min(lo[axis],x);hi[axis]=Math.max(hi[axis],x);}
  return{lo,hi};
}
const deck=await stlBounds(mountReference.deck),bearing=await stlBounds(mountReference.bearing);
const bodyMount=[(bearing.lo[0]+bearing.hi[0])/2,(bearing.lo[1]+bearing.hi[1])/2,deck.hi[2]];
assert.ok(Math.hypot(...bodyMount.map((x,i)=>x-mountReference.pan_axis_at_deck_mm[i]))<mountReference.datum_tolerance_mm);

const base=(process.env.SITE_URL||'http://127.0.0.1:8890').replace(/\/$/,''),out=process.env.TEST_OUTPUT||'/tmp/gyropup-current-model';
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
const context=await browser.newContext({viewport:{width:1280,height:900},reducedMotion:'reduce'});
await acknowledgePrototypeNotice(context);
await context.addInitScript(()=>{localStorage.setItem('gyropup.probe','off');localStorage.setItem('gyropup-sfx','0');});
const page=await context.newPage(),errors=[];page.setDefaultTimeout(60000);page.on('pageerror',e=>errors.push(e.message));
await mkdir(out,{recursive:true});
const sub=(a,b)=>a.map((x,i)=>x-b[i]),dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0),cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
function expected(point,owner,angles){while(owner){const j=fixture.contract.joints[owner],p=sub(point,j.pivot),a=j.axis,t=angles[owner]*Math.PI/180,c=Math.cos(t),s=Math.sin(t),k=cross(a,p),d=dot(a,p);point=p.map((x,i)=>j.pivot[i]+x*c+k[i]*s+a[i]*d*(1-c));owner=j.parent;}return point;}
let names;
function error(sample){let max=0,worst='';for(const name of names){const c=fixture.contract.components[name];assert.equal(sample.components[name]?.length,c.points.length,name);c.points.forEach((p,i)=>{const e=Math.hypot(...sub(sample.components[name][i],expected(p,c.joint,sample.angles_deg)));if(e>max){max=e;worst=name;}});}return{max,worst};}
async function fingerprint(key){return page.evaluate(key=>{const r=key==='sim'?window.__sim.state.robot:key==='hero'?window.__heroPreview.robot:window.__talkDemo.robot;return{presentation:r.presentation,parts:r.turret.model.parts.map(p=>({name:p.entry.name,hash:p.entry.sha256,count:p.mesh.geometry.attributes.position.count,first:Array.from(p.mesh.geometry.attributes.position.array.slice(0,12))})).sort((a,b)=>a.name.localeCompare(b.name)),massBasis:r.info.massBasis};},key);}
try{
  await page.goto(base+'/designer/sim.html?run=none&demo=0&sound=0',{waitUntil:'networkidle'});
  await page.waitForFunction(()=>document.body.dataset.ready==='1'&&window.__sim.state.robot?.presentation);
  const initial=await fingerprint('sim');names=initial.parts.map(p=>p.name);assert.equal(names.length,48);
  assert.equal(initial.presentation.turretId,'turret-box-v2');assert.match(initial.massBasis,/not rerun/);
  const requests=await page.evaluate(()=>performance.getEntriesByType('resource').map(e=>e.name));
  assert.ok(!requests.some(u=>/\/v2\/rig\/turret_.*\.stl/.test(u)),'No archived turret downloads on current startup');
  const samples=await page.evaluate(({fixture,bodyMount})=>{
    const r=window.__sim.state.robot,t=r.turret,m=t.model,deg=180/Math.PI;
    window.captureCurrent=(id,angles)=>{
      r.group.updateWorldMatrix(true,true);const components={};
      for(const p of m.parts){components[p.entry.name]=fixture.vertex_indices[p.entry.name].map(i=>{
        const v=p.mesh.position.clone().fromBufferAttribute(p.mesh.geometry.attributes.position,i);p.mesh.localToWorld(v);r.base.worldToLocal(v);
        // Independent body TM datum (inspected deck and pan-bearing STL),
        // expressed in audited box assembly frame. Do NOT strip the turret root:
        // doing so would hide an incorrect full-robot mounting position.
        return[v.z*1000-bodyMount[0],v.x*1000-bodyMount[1],v.y*1000-bodyMount[2]+141];
      });}return{id,angles_deg:angles,components};
    };
    window.currentAngles=(wrap=false)=>{const phase=x=>wrap?((x*deg)%360+360)%360:x*deg;return{pan:t.pan.rotation.y*deg,tilt:-t.tilt.rotation.x*deg,pinion:m.groups.pinion.rotation.y*deg,dial:phase(m.groups.dial.rotation.y),wheel_l:phase(m.groups.wheel_l.rotation.y),wheel_r:phase(-m.groups.wheel_r.rotation.y),flap:-m.groups.flap.rotation.x*deg};};
    return fixture.poses.map((a,i)=>{t.poseMechanism(Object.fromEntries(Object.entries(a).map(([k,v])=>[k,v/deg])));return window.captureCurrent('pose-'+i,window.currentAngles());});
  },{fixture,bodyMount});
  let worst={max:0};for(const s of samples){const e=error(s);if(e.max>worst.max)worst=e;assert.ok(e.max<.02,`${s.id}: ${e.worst} ${e.max}mm`);}
  const negative=await page.evaluate(()=>{
    const r=window.__sim.state.robot,t=r.turret,m=t.model,g=m.groups,zero={pan:0,tilt:0,pinion:0,dial:0,wheel_l:0,wheel_r:0,flap:0};
    const pose=a=>t.poseMechanism(Object.fromEntries(Object.entries(a).map(([k,v])=>[k,v*Math.PI/180]))),capture=(name,a)=>window.captureCurrent(name,a),result={};
    pose(zero);const home=g.wheel_l.position.clone(),members=m.parts.filter(p=>p.entry.group==='wheel_l');
    g.wheel_l.position.z+=.048;members.forEach(p=>p.mesh.position.z-=.048);result.pivotHome=capture('pivot-home',zero);
    const quarter={...zero,wheel_l:90};pose(quarter);result.pivot=capture('pivot-quarter',quarter);
    g.wheel_l.position.copy(home);members.forEach(p=>p.mesh.position.z=0);pose(zero);
    const motor=m.parts.find(p=>p.entry.name==='feed_motor').mesh,owner=motor.parent,position=motor.position.clone();
    r.group.updateWorldMatrix(true,true);g.dial.attach(motor);pose({...zero,dial:90});result.owner=capture('motor-on-rotor',{...zero,dial:90});owner.attach(motor);motor.position.copy(position);motor.rotation.set(0,0,0);pose(zero);
    pose({...zero,wheel_r:90});g.wheel_r.rotation.y*=-1;result.sign=capture('wrong-wheel-sign',{...zero,wheel_r:90});pose(zero);
    const p=g.tilt.parent,pos=g.tilt.position.clone();r.group.updateWorldMatrix(true,true);t.group.attach(g.tilt);pose({...zero,pan:45,pinion:-135});result.parent=capture('lost-pan-parent',{...zero,pan:45,pinion:-135});p.attach(g.tilt);g.tilt.position.copy(pos);g.tilt.rotation.set(0,0,0);pose(zero);
    t.group.scale.setScalar(1000);result.units=capture('millimetres-as-metres',zero);t.group.scale.setScalar(1);
    result.restored=capture('restored',zero);return result;
  });
  assert.ok(error(negative.pivotHome).max<.02,'Wrong pivot is invisible at home');
  for(const key of ['pivot','owner','sign','parent','units'])assert.ok(error(negative[key]).max>10,`Independent reference rejects ${key}`);
  assert.ok(error(negative.restored).max<.02,'Negative controls restore actual assembly');
  const connected=await page.evaluate(()=>{
    const r=window.__sim.state.robot,t=r.turret,m=t.model,barrel=m.parts.find(p=>p.entry.name==='barrel').mesh;
    barrel.geometry.computeBoundingBox();const b=barrel.geometry.boundingBox;
    const checks=[];
    for(const [pan,tilt] of [[0,0],[.7,-.2],[-1.2,-.4]]){
      t.poseMechanism({pan,tilt});r.group.updateWorldMatrix(true,true);
      const mouth=b.getCenter(t.muzzle.position.clone());mouth.z=b.max.z;barrel.localToWorld(mouth);
      const muzzle=t.muzzle.getWorldPosition(mouth.clone());const ball=window.__sim.balls;ball.clear();ball.fire(t.muzzle);
      const shot=ball.active[0];checks.push({gap:mouth.distanceTo(muzzle),origin:shot.g.position.distanceTo(muzzle),speed:shot.v.length()});ball.clear();
    }
    r.setExplode(.45);const exploded=m.parts.some(p=>p.mesh.position.length()>.001);
    r.setExplode(0);t.flash();t.reload();const live=[],rawOperationAngles=[];
    for(let i=0;i<90;i++){t.step(1/60);rawOperationAngles.push(window.currentAngles());live.push(window.captureCurrent('operation-'+i,window.currentAngles(true)));}
    const rejoined=m.parts.every(p=>p.mesh.position.length()<1e-12),flapClosed=Math.abs(m.groups.flap.rotation.x)<1e-12;
    return{checks,exploded,rejoined,flapClosed,live,rawOperationAngles};
  });
  for(const c of connected.checks){assert.ok(c.gap<.00002,'Visible barrel mouth matches effect frame');assert.ok(c.origin<1e-9,'Ball starts at the visible muzzle');assert.ok(Math.abs(c.speed-15.85)<1e-9,'Current configured launch speed');}
  assert.ok(connected.exploded&&connected.rejoined&&connected.flapClosed);
  for(const s of connected.live){const e=error(s);assert.ok(e.max<.02,`${s.id}: ${e.worst} ${e.max}mm`);}
  const emission=await page.evaluate(()=>{
    const s=window.__sim,r=s.state.robot,t=r.turret,camera=s.stage.camera,saved=camera.clone();
    r.setExplode(0);t.poseMechanism({pan:.6,tilt:-.2});r.group.updateWorldMatrix(true,true);
    const barrel=t.model.parts.find(p=>p.entry.name==='barrel').mesh,b=barrel.geometry.boundingBox;
    const mouth=b.getCenter(t.muzzle.position.clone());mouth.z=b.max.z;barrel.localToWorld(mouth);
    s.balls.clear();s.balls.fire(t.muzzle);const ball=s.balls.active[0];
    camera.clearViewOffset();camera.position.copy(mouth).add(t.muzzle.position.clone().set(.3,.18,.32));camera.lookAt(mouth);camera.updateMatrixWorld();
    const a=mouth.clone().project(camera),z=ball.g.position.clone().project(camera),canvas=s.stage.renderer.domElement;
    const pixelGap=Math.hypot((a.x-z.x)*canvas.width/2,(a.y-z.y)*canvas.height/2);
    s.stage.renderer.render(s.stage.scene,camera);const image=canvas.toDataURL('image/png');
    camera.copy(saved);s.balls.clear();return{pixelGap,image};
  });
  assert.ok(emission.pixelGap<.01,'Actual emitted ball and visible STL mouth project to the same pixel');
  await writeFile(`${out}/${engine.name()}-shot-at-mouth.png`,Buffer.from(emission.image.split(',')[1],'base64'));
  // Failed archived mesh load must preserve a usable current scene; retry then
  // race a new current choice against the successful old request.
  await page.route('**/exports/sim/v2/rig/turret_*.stl',route=>route.abort());
  const failure=await page.evaluate(async()=>{const r=window.__sim.state.robot;try{await r.setPresentation('recorded');return false;}catch{return r.presentation.mode==='current'&&r.turret.model.parts.every(p=>p.mesh.visible);}});
  assert.ok(failure,'Failed archive cannot silently replace current');await page.unroute('**/exports/sim/v2/rig/turret_*.stl');
  const transitions=await page.evaluate(async()=>{
    const r=window.__sim.state.robot,t=r.turret;const first=r.setPresentation('recorded');r.setPresentation('current');await first;const stale=r.presentation.mode;
    await r.setPresentation('recorded');const recorded={id:r.presentation.turretId,muzzle:t.muzzle.position.toArray(),tilt:t.tilt.position.toArray(),speed:t.launchSpeed,hidden:t.model.parts.every(p=>!p.mesh.visible)};
    await r.setPresentation('current');const current={muzzle:t.muzzle.position.toArray(),tilt:t.tilt.position.toArray(),speed:t.launchSpeed,shown:t.model.parts.every(p=>p.mesh.visible)};
    await r.setPresentation('recorded');await r.setPresentation('current');return{stale,recorded,current};
  });
  assert.equal(transitions.stale,'current');assert.equal(transitions.recorded.id,'v2-recorded-turret');assert.ok(transitions.recorded.hidden&&transitions.current.shown);
  assert.ok(Math.abs(transitions.recorded.muzzle[2]-.194)<1e-9);assert.ok(Math.abs(transitions.current.muzzle[2]-.147)<1e-9);
  assert.ok(Math.abs(transitions.recorded.tilt[1]-.123)<1e-9);assert.ok(Math.abs(transitions.current.tilt[1]-.140)<1e-9);
  assert.equal(transitions.current.speed,15.85);assert.equal(transitions.recorded.speed,21.3);
  await page.screenshot({path:`${out}/${engine.name()}-current.png`});
  for(const [route,key,ready] of [['/','hero',()=>window.__heroPreview],['/designer/character/talk-demo.html','talk',()=>window.__talkDemo]]){
    await page.goto(base+route,{waitUntil:'networkidle'});await page.waitForFunction(ready);const actual=await fingerprint(key);
    assert.deepEqual(actual.parts,initial.parts,`${key}: identical actual current STL geometry`);assert.equal(actual.presentation.turretId,'turret-box-v2');
  }
  // A missing CURRENT mesh must reject the entire loader, retaining the honest poster.
  await page.route('**/exports/sim/turret_box/parts/*.stl*',route=>route.abort());
  // File names are manifest-defined, so intercept exactly one required mesh too.
  const manifestBytes=await(await page.request.get(base+'/exports/sim/turret_box/manifest.json')).body(),manifest=JSON.parse(manifestBytes);
  await page.route('**/turret_box/'+manifest.parts.find(p=>p.name==='barrel').file+'*',route=>route.abort());
  await page.goto(base+'/',{waitUntil:'networkidle'});await page.waitForFunction(()=>document.getElementById('robot-preview').dataset.state==='fallback');
  assert.equal(await page.locator('#robot-preview canvas').count(),0);assert.equal(await page.locator('.scene-fallback').evaluate(e=>getComputedStyle(e).opacity),'1');
  assert.deepEqual(errors,[]);
  const contract={...fixture.contract,components:Object.fromEntries(names.map(n=>[n,fixture.contract.components[n]]))};
  const version=await(await page.request.get(base+'/version.json')).json();
  const sourceHashes=Object.fromEntries(await Promise.all(['designer/current_turret.js','designer/robot_v2.js','designer/turret3d.js','designer/kit/stage.js','designer/character/talk-demo.html','exports/sim/v2/rig/manifest.json'].map(async file=>{
    const response=await page.request.get(base+'/'+file);assert.ok(response.ok(),file);return[file,createHash('sha256').update(await response.body()).digest('hex')];
  })));
  const trace={schema_version:1,length_unit:'mm',frame:'assembly-home',capture_source:`${base}; ${engine.name()}; robot free-body transform removed, independently pinned TM mount converted to reference box frame; actual STL vertices; revision=${version.revision}; manifest_sha256=${createHash('sha256').update(manifestBytes).digest('hex')}`,samples:[...samples,...connected.live]};
  await writeFile(`${out}/capture-manifest.json`,manifestBytes);await writeFile(`${out}/capture-version.json`,JSON.stringify(version));
  await writeFile(`${out}/${engine.name()}-source-hashes.json`,JSON.stringify(sourceHashes,null,2));
  await writeFile(`${out}/contract.json`,JSON.stringify(contract));await writeFile(`${out}/${engine.name()}-trace.json`,JSON.stringify(trace));
  await writeFile(`${out}/${engine.name()}-summary.json`,JSON.stringify({components:names.length,poses:samples.length,operationFrames:connected.live.length,worst,negative:Object.fromEntries(Object.entries(negative).map(([k,v])=>[k,error(v)])),connected:connected.checks,rawOperationAngles:connected.rawOperationAngles,transitions,version},null,2));
  console.log(`PASS ${engine.name()}: 48 actual current parts × ${samples.length} independent poses + ${connected.live.length} operating frames, max ${worst.max.toFixed(6)}mm; 5 negative controls; current/recorded frames and failures; hero/sim/talk geometry match`);
}finally{await browser.close();}
