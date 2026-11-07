import { acknowledgePrototypeNotice } from '../content/test-prototype-session.mjs';
/** Validate actual rendered STL landmarks against independently audited CAD datums. */
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { chromium, webkit } from '@playwright/test';
import { createHash } from 'node:crypto';
const fixture = JSON.parse(await readFile(new URL('../../fixtures/turret-motion-reference.json', import.meta.url)));
assert.ok(fixture.source?.parts, 'Regenerate the independent reference from the reviewed current full scene');
const base = (process.env.SITE_URL || 'http://127.0.0.1:8879').replace(/\/$/, '');
const out = process.env.TEST_OUTPUT || '/tmp/gyropup-turret-motion';
const engine = process.env.PLAYWRIGHT_BROWSER === 'webkit' ? webkit : chromium;
function assertReferenceAssets(reference, manifestBytes, responses) {
  assert.ok(reference.source?.parts, 'Regenerate the independent reference from the reviewed current full scene');
  assert.equal(createHash('sha256').update(manifestBytes).digest('hex'), reference.source.manifest_sha256);
  const manifest = JSON.parse(manifestBytes);
  assert.deepEqual(manifest.parts.map(p=>p.name).sort(), Object.keys(reference.source.parts).sort());
  assert.equal(new Set(manifest.parts.map(p=>p.name)).size, manifest.parts.length);
  const expectedFiles = new Map();
  for (const part of manifest.parts) {
    const bound = reference.source.parts[part.name];
    assert.equal(part.file, bound.file); assert.equal(part.group, bound.group); assert.equal(part.sha256, bound.sha256);
    assert.equal(reference.contract.components[part.name].joint,
      Object.hasOwn(reference.contract.joints, bound.group) ? bound.group : null);
    assert.ok(!expectedFiles.has(bound.file)); expectedFiles.set(bound.file, bound.sha256);
  }
  const loaded = new Set(); let loadedManifests = 0;
  for (const response of responses) {
    assert.ok(!response.error, JSON.stringify(response)); assert.equal(response.status, 200);
    if (response.file === 'manifest.json') {
      loadedManifests++; assert.equal(response.sha256, reference.source.manifest_sha256);
    } else {
      assert.ok(expectedFiles.has(response.file), `Unknown loaded mesh: ${response.file}`);
      assert.equal(response.version, expectedFiles.get(response.file));
      assert.equal(response.sha256, expectedFiles.get(response.file)); loaded.add(response.file);
    }
  }
  assert.ok(loadedManifests > 0, 'Hash the actual manifest response used by the renderer');
  assert.deepEqual([...loaded].sort(), [...expectedFiles.keys()].sort(), 'Hash every actual loaded mesh response');
  return manifest;
}
const browser = await engine.launch(engine === chromium ? { channel:process.env.PLAYWRIGHT_CHANNEL === 'chromium' ? undefined : 'chrome', headless:true,
  args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'] } : {headless:true});
await mkdir(out, {recursive:true});
const page = await browser.newPage({viewport:{width:1280,height:900}}), errors=[];
const assetResponses=[];
page.on('response', response=>{
  const url=new URL(response.url()), prefix='/exports/sim/turret_box/';
  if (url.origin!==new URL(base).origin || !url.pathname.startsWith(prefix)) return;
  const file=url.pathname.slice(prefix.length);
  if (file!=='manifest.json' && !file.endsWith('.stl')) return;
  assetResponses.push(response.body().then(bytes=>({file,status:response.status(),version:url.searchParams.get('v'),
    sha256:createHash('sha256').update(bytes).digest('hex')})).catch(error=>({file,error:String(error)})));
});
await acknowledgePrototypeNotice(page);
page.on('pageerror', e => errors.push(e.message));
// 80 box meshes and the site's own assets overflow the default 250-entry Resource Timing buffer that the mesh check reads.
await page.addInitScript(() => {localStorage.setItem('gyropup.probe','off');performance.setResourceTimingBufferSize(2000);});
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
  const loadedParts=await page.evaluate(()=>window.__sim.bench().api.mechanism.parts.map(p=>({name:p.e.name,file:p.e.file,group:p.e.group,sha256:p.e.sha256})));
  assert.equal(loadedParts.length,Object.keys(fixture.contract.components).length);
  for(const part of loadedParts) assert.deepEqual({file:part.file,group:part.group,sha256:part.sha256},fixture.source.parts[part.name]);
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
  const sensitivities=await page.evaluate(()=>{
    const api=window.__sim.bench().api,m=api.mechanism;
    const zero={pan:0,tilt:0,pinion:0,dial:0,wheel_l:0,wheel_r:0,flap:0};
    const pose=(angles)=>{const a={...zero,...angles};api.poseMechanism(Object.fromEntries(Object.entries(a).map(([k,v])=>[k,v*Math.PI/180])));return a;};
    const result={};
    pose({});
    const leaf=m.parts.find(p=>p.e.name==='barrel').mesh,scale=leaf.scale.clone();
    try {leaf.scale.multiplyScalar(.001);const a=pose({pan:35,tilt:12});result.units=window.captureTurret('wrong-units',a);}
    finally {leaf.scale.copy(scale);pose({});}
    try {const a=pose({pan:35,tilt:12});m.groups.tilt.rotation.x*=-1;result.axis=window.captureTurret('wrong-tilt-sign',a);}
    finally {pose({});}
    const detach=(object,newParent,angles,name)=>{
      pose({});const parent=object.parent,position=object.position.clone(),rotation=object.quaternion.clone(),size=object.scale.clone();
      try {
        newParent.attach(object);result[name+'Home']=window.captureTurret(name+'-home',zero);
        const a=pose(angles);result[name]=window.captureTurret(name,a);
      } finally {parent.attach(object);object.position.copy(position);object.quaternion.copy(rotation);object.scale.copy(size);pose({});}
    };
    detach(m.groups.tilt,m.world,{pan:60,tilt:12},'lostParent');
    detach(m.parts.find(p=>p.e.name==='flywheel_motor_l').mesh,m.groups.wheel_l,{wheel_l:90},'motorOwnership');
    return result;
  });
  for(const name of ['units','axis','lostParent','motorOwnership'])
    assert.ok(maxError(sensitivities[name]).error>1,`Independent landmarks reject ${name}`);
  for(const name of ['lostParentHome','motorOwnershipHome'])
    assert.ok(maxError(sensitivities[name]).error<.02,`${name} deliberately preserves correct home geometry`);
  // Check connected effects, bearings, balls, and actual live firing through the normal frame loop.
  const attachments=await page.evaluate(()=>{
    const api=window.__sim.bench().api,m=api.mechanism;
    api.poseMechanism({pan:0,tilt:0,pinion:0,dial:0,wheel_l:0,wheel_r:0,flap:0});
    m.world.updateWorldMatrix(true,true);
    const point=o=>{const p=o.position.clone();o.getWorldPosition(p);m.world.worldToLocal(p);return [p.z*1000,p.x*1000,p.y*1000];};
    return {muzzle:point(m.muzzle),laser:point(m.laserOrigin),gateDistance:m.gates[0].position.distanceTo(m.gates[1].position)*1000,
      pocket:point(m.pocketBalls[0]),pathStart:[m.path[0].z*1000,m.path[0].x*1000,m.path[0].y*1000+285],
      owners:Object.fromEntries(m.parts.map(p=>[p.e.name,Object.entries(m.groups).find(([,g])=>g===p.mesh.parent)?.[0]]))};
  });
  assert.deepEqual(attachments.muzzle.map(x=>Math.round(x*100)/100),[150,0,270]);
  assert.deepEqual(attachments.laser.map(x=>Math.round(x*100)/100),[84.5,0,299.5]);
  assert.ok(Math.abs(attachments.gateDistance-60)<.001,'Optical gates match CAD 22/82mm positions');
  // The pockets are the settled MuJoCo pile (sim/turret_feed.py --pile, rerun with the D76 gates): 0.02 mm under the exit.
  assert.ok(Math.hypot(...sub(attachments.pocket,attachments.pathStart))<.05,'Pocket reaches actual chute at zero dial angle');
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
  const responses=await Promise.all(assetResponses);
  const manifest=assertReferenceAssets(fixture,manifestBytes,responses);
  // Actual binding guard sensitivity; no stale/missing-asset normalization.
  const changed=JSON.parse(manifestBytes);changed.parts[0].group='foreign-owner';
  const changedBytes=Buffer.from(JSON.stringify(changed)),claimed=structuredClone(fixture);
  claimed.source.manifest_sha256=createHash('sha256').update(changedBytes).digest('hex');
  const claimedResponses=responses.map(r=>r.file==='manifest.json'?{...r,sha256:claimed.source.manifest_sha256}:r);
  assert.throws(()=>assertReferenceAssets(claimed,changedBytes,claimedResponses),'A self-consistent manifest hash cannot bless different ownership');
  const changedMesh=responses.map(r=>({...r}));changedMesh.find(r=>r.file.endsWith('.stl')).sha256='0'.repeat(64);
  assert.throws(()=>assertReferenceAssets(fixture,manifestBytes,changedMesh));
  assert.throws(()=>assertReferenceAssets(fixture,manifestBytes,responses.filter(r=>r.file!==manifest.parts[0].file)));
  const requested=await page.evaluate(()=>performance.getEntriesByType('resource').map(e=>e.name));
  for(const p of manifest.parts) assert.ok(requested.some(u=>u.endsWith(`/turret_box/${p.file}?v=${p.sha256}`)),`Content-versioned mesh loaded: ${p.name}`);
  const manifestHash=createHash('sha256').update(manifestBytes).digest('hex');
  const trace={schema_version:1,length_unit:'mm',frame:'assembly-home',capture_source:`${base}; ${engine.name()}; actual Three.js STL vertices; revision=${version.revision}; assets=${version.assets}; manifest_sha256=${manifestHash}; per-mesh hashes in capture-manifest.json`,samples};
  await writeFile(`${out}/capture-manifest.json`,manifestBytes);
  await writeFile(`${out}/capture-version.json`,JSON.stringify(version));
  await writeFile(`${out}/${engine.name()}-trace.json`,JSON.stringify(trace));
  await writeFile(`${out}/contract.json`,JSON.stringify(fixture.contract));
  await writeFile(`${out}/${engine.name()}-asset-bindings.json`,JSON.stringify(responses,null,2));
  await writeFile(`${out}/${engine.name()}-sensitivity.json`,JSON.stringify(sensitivities));
  await writeFile(`${out}/${engine.name()}-summary.json`,JSON.stringify({components:Object.keys(fixture.contract.components).length,poses:samples.length,liveFrames:live.length,maxErrorMm:worst.error,worst:worst.worst,speed,attachments},null,2));
  console.log(`PASS ${engine.name()}: ${Object.keys(fixture.contract.components).length} components × ${samples.length} poses; ${live.length} real firing frames; max ${worst.error.toFixed(6)}mm; negative pivot control rejected; CAD attachments, configured launch speed, 5 phone layouts`);
} finally {await browser.close();}
