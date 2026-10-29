/** Validate actual rendered STL landmarks against independently audited CAD datums. */
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { chromium, webkit } from '@playwright/test';
import { createHash } from 'node:crypto';
const fixture = JSON.parse(await readFile(new URL('../tests/fixtures/turret-motion-reference.json', import.meta.url)));
const base = (process.env.SITE_URL || 'http://127.0.0.1:8879').replace(/\/$/, '');
const out = process.env.TEST_OUTPUT || '/tmp/gyropup-turret-motion';
const engine = process.env.PLAYWRIGHT_BROWSER === 'webkit' ? webkit : chromium;
const browser = await engine.launch(engine === chromium ? { channel:process.env.PLAYWRIGHT_CHANNEL === 'chromium' ? undefined : 'chrome', headless:true,
  args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'] } : {headless:true});
await mkdir(out, {recursive:true});
const page = await browser.newPage({viewport:{width:1280,height:900}}), errors=[];
page.on('pageerror', e => errors.push(e.message));
await page.addInitScript(() => localStorage.setItem('gyropup.probe','off'));
const sub=(a,b)=>a.map((x,i)=>x-b[i]), dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0);
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
function rotate(point,joint,deg) {
  const p=sub(point,joint.pivot), a=joint.axis, t=deg*Math.PI/180,c=Math.cos(t),s=Math.sin(t),k=cross(a,p),d=dot(a,p);
  return p.map((x,i)=>joint.pivot[i]+x*c+k[i]*s+a[i]*d*(1-c));
}
function expected(point, owner, angles) {
  while(owner) {const j=fixture.contract.joints[owner];point=rotate(point,j,angles[owner]);owner=j.parent;}
  return point;
}
function maxError(sample) {
  let error=0, worst='';
  for(const [name,c] of Object.entries(fixture.contract.components)) {
    assert.equal(sample.components[name]?.length,c.points.length,`Missing landmarks: ${name}`);
    c.points.forEach((p,i)=>{const want=expected(p,c.joint,sample.angles_deg),v=sample.components[name][i];
      const e=Math.hypot(...sub(v,want));if(e>error){error=e;worst=name;}});
  }
  return {error,worst};
}
try {
  await page.goto(base+'/designer/sim.html?sound=0',{waitUntil:'networkidle'});
  await page.waitForFunction(()=>document.body.dataset.ready==='1');
  // Older CAD snapshots retain their own frames; their beam must still originate
  // at their fitted laser rather than the procedural stand-in's old position.
  const checkLaser=()=>page.evaluate(()=>{
    const t=window.__sim.state.robot.turret;
    let mesh;t.tilt.traverse(m=>{if(m.isMesh && /_laser$/.test(m.name))mesh=m;});
    if(!mesh)return false;
    mesh.geometry.computeBoundingBox();const b=mesh.geometry.boundingBox;
    const front=t.laserOrigin.position.clone();b.getCenter(front);front.z=b.max.z;
    mesh.updateWorldMatrix(true,false);mesh.localToWorld(front);
    return front.distanceTo(t.laserOrigin.getWorldPosition(front.clone()))<1e-6;
  });
  assert.ok(await checkLaser(),'V2 CAD laser origin is on its actual lens');
  await page.selectOption('#design-select','turret-box');
  await page.waitForFunction(()=>window.__sim.bench()?.active);
  const samples = await page.evaluate(({fixture})=>{
    const bench=window.__sim.bench(), api=bench.api,m=api.mechanism;
    window.captureTurret=(id,angles)=>{
      m.world.updateWorldMatrix(true,true);
      const components={};
      for(const p of m.parts) {
        const positions=p.mesh.geometry.attributes.position;
        components[p.e.name]=fixture.vertex_indices[p.e.name].map(i=>{
          const v=p.mesh.position.clone().fromBufferAttribute(positions,i);
          p.mesh.localToWorld(v);m.world.worldToLocal(v);
          return [v.z*1000,v.x*1000,v.y*1000]; // page metres -> CAD millimetres; strip crate/root
        });
      }
      return {id,angles_deg:angles,components};
    };
    return fixture.poses.map((a,i)=>{
      api.poseMechanism(Object.fromEntries(Object.entries(a).map(([k,v])=>[k,v*Math.PI/180])));
      return window.captureTurret('pose-'+i,a);
    });
  },{fixture});
  let worst={error:0};
  for(const sample of samples){const e=maxError(sample);if(e.error>worst.error)worst=e;assert.ok(e.error<.02,`${sample.id} ${e.worst} displaced ${e.error}mm`);}
  // A wrong pivot may pass home and 360 degrees. Prove the quarter-turn check fails.
  const broken=await page.evaluate(()=>{
    const api=window.__sim.bench().api,g=api.mechanism.groups;
    const a={pan:0,tilt:0,pinion:0,dial:0,wheel_l:90,wheel_r:0,flap:0};
    const origin=g.wheel_l.position.clone();g.wheel_l.position.z+=.048;
    const members=api.mechanism.parts.filter(p=>p.e.group==='wheel_l');
    const positions=members.map(p=>p.mesh.position.clone());
    members.forEach(p=>p.mesh.position.z-=.048); // Preserve the correct home pose, exactly as the original bug did.
    api.poseMechanism({...a,wheel_l:0});
    const home=window.captureTurret('wrong-pivot-home',{...a,wheel_l:0});
    api.poseMechanism(Object.fromEntries(Object.entries(a).map(([k,v])=>[k,v*Math.PI/180])));
    const quarter=window.captureTurret('wrong-pivot-quarter',a);
    g.wheel_l.position.copy(origin);members.forEach((p,i)=>p.mesh.position.copy(positions[i]));return {home,quarter};
  });
  assert.ok(maxError(broken.home).error<.02,'Seeded wrong pivot still passes at home');
  assert.ok(maxError(broken.quarter).error>60,'Independent intermediate-pose oracle rejects the original orbit failure');
  // Check connected effects, bearings, balls, and actual live firing through the normal frame loop.
  const attachments=await page.evaluate(()=>{
    const api=window.__sim.bench().api,m=api.mechanism;
    api.poseMechanism({pan:0,tilt:0,pinion:0,dial:0,wheel_l:0,wheel_r:0,flap:0});
    m.world.updateWorldMatrix(true,true);
    const point=o=>{const p=o.position.clone();o.getWorldPosition(p);m.world.worldToLocal(p);return [p.z*1000,p.x*1000,p.y*1000];};
    return {muzzle:point(m.muzzle),laser:point(m.laserOrigin),gateDistance:m.gates[0].position.distanceTo(m.gates[1].position)*1000,
      pocket:point(m.pocketBalls[0]),pathStart:[m.path[0].z*1000,m.path[0].x*1000,m.path[0].y*1000+281],
      owners:Object.fromEntries(m.parts.map(p=>[p.e.name,Object.entries(m.groups).find(([,g])=>g===p.mesh.parent)?.[0]]))};
  });
  assert.deepEqual(attachments.muzzle.map(x=>Math.round(x*100)/100),[147,0,266]);
  assert.deepEqual(attachments.laser.map(x=>Math.round(x*100)/100),[78.5,-32,266]);
  assert.ok(Math.abs(attachments.gateDistance-60)<.001,'Optical gates match CAD 22/82mm positions');
  assert.ok(Math.hypot(...sub(attachments.pocket,attachments.pathStart))<.02,'Pocket reaches actual chute at zero dial angle');
  for(const motor of ['feed_motor','flywheel_motor_l','flywheel_motor_r']) assert.equal(attachments.owners[motor],'tilt');
  await page.evaluate(()=>{
    const api=window.__sim.bench().api;api.aim(35,-15);api.reload();api.arm(true);api.fire(6);
    window.liveSamples=[];
    window.__sim.stage.onFrame(()=>{
      if(window.liveSamples.length>=150)return;
      const s=api.state,deg=180/Math.PI;
      window.liveSamples.push(window.captureTurret('firing-'+window.liveSamples.length,{
        pan:s.pan*deg,tilt:s.tilt*deg,pinion:-3*s.pan*deg,dial:s.phi*deg,wheel_l:s.wheelAng*deg,wheel_r:s.wheelAng*deg,flap:s.flapAngle*deg}));
    });
  });
  await page.waitForFunction(()=>window.__sim.bench().api.state.shots>=4,{},{timeout:30000});
  const live=await page.evaluate(()=>window.liveSamples);
  assert.ok(live.length>5,'Actual frame loop captured');
  for(const sample of live){const e=maxError(sample);assert.ok(e.error<.02,`live ${e.worst}: ${e.error}mm`);}
  const speed=await page.evaluate(()=>{const b=window.__sim.bench();b.api.arm(false);return {measured:b.api.state.lastSpeed,want:b.manifest.mechanics.ball.speed_mps};});
  assert.ok(speed.measured>0 && Math.abs(speed.measured-speed.want)<.5,`Chronograph ${speed.measured} matches configured ${speed.want}m/s`);
  await page.screenshot({path:`${out}/${engine.name()}-firing.png`});
  // Mobile frame/control visibility after the same live scene has fired.
  for(const [width,height] of [[320,568],[360,800],[390,844],[430,932],[844,390]]) {
    await page.setViewportSize({width,height});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`No overflow at ${width}x${height}`);
  }
  await page.screenshot({path:`${out}/${engine.name()}-phone.png`});
  assert.deepEqual(errors,[]);
  const version=await (await page.request.get(base+'/version.json')).json();
  const manifestBytes=await (await page.request.get(base+'/exports/sim/turret_box/manifest.json')).body();
  const manifest=JSON.parse(manifestBytes);
  const requested=await page.evaluate(()=>performance.getEntriesByType('resource').map(e=>e.name));
  for(const p of manifest.parts) assert.ok(requested.some(u=>u.endsWith(`/turret_box/${p.file}?v=${p.sha256}`)),`Content-versioned mesh loaded: ${p.name}`);
  const manifestHash=createHash('sha256').update(manifestBytes).digest('hex');
  const trace={schema_version:1,length_unit:'mm',frame:'assembly-home',capture_source:`${base}; ${engine.name()}; actual Three.js STL vertices; revision=${version.revision}; assets=${version.assets}; manifest_sha256=${manifestHash}; per-mesh hashes in capture-manifest.json`,samples};
  await writeFile(`${out}/capture-manifest.json`,manifestBytes);
  await writeFile(`${out}/capture-version.json`,JSON.stringify(version));
  await writeFile(`${out}/${engine.name()}-trace.json`,JSON.stringify(trace));
  await writeFile(`${out}/contract.json`,JSON.stringify(fixture.contract));
  await writeFile(`${out}/${engine.name()}-summary.json`,JSON.stringify({components:66,poses:samples.length,liveFrames:live.length,maxErrorMm:worst.error,worst:worst.worst,speed,attachments},null,2));
  console.log(`PASS ${engine.name()}: 66 components × ${samples.length} poses; ${live.length} real firing frames; max ${worst.error.toFixed(6)}mm; negative pivot control rejected; CAD attachments, configured launch speed, 5 phone layouts`);
} finally {await browser.close();}
