/** Actual candidate renderer observations; source oracle/shared verdict are separate. */
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {chromium,webkit} from '@playwright/test';
import {createSiteServer} from '../../../tools/site/serve-site.mjs';
import {publicForSource,sourceForPublic} from '../../../tools/site/source-layout.mjs';
import {installCurrentMotion,captureMotionFaults,captureMotionOperation} from './current-motion-capture.mjs';
import {requiredMeshRequestTarget} from './current-motion-target.mjs';
import {currentRobotReady,currentRobotCanvasReady} from './current-motion-ready.mjs';

const root=new URL('../../../',import.meta.url),sha=b=>createHash('sha256').update(b).digest('hex');
const referenceFile=process.env.CURRENT_MOTION_REFERENCE,referenceHash=process.env.CURRENT_MOTION_REFERENCE_SHA256;
assert.ok(referenceFile&&/^[0-9a-f]{64}$/.test(referenceHash??''),'Explicit reviewed source-reference binding required');
const raw=await readFile(referenceFile);assert.equal(sha(raw),referenceHash);const reference=JSON.parse(raw);
const siteRoot=process.env.CURRENT_MOTION_SITE_ROOT,out=process.env.TEST_OUTPUT,sourceRevision=process.env.CURRENT_MOTION_SOURCE;
assert.ok(siteRoot&&out&&/^[0-9a-f]{40}$/.test(sourceRevision??''),'Explicit isolated webroot, fresh output and immutable source required');
const publicManifest=publicForSource('software/site/assets/robot-current/manifest.json');
assert.equal(publicManifest,'web/robot-current/manifest.json');assert.equal(sourceForPublic(publicManifest),'software/site/assets/robot-current/manifest.json');
const source={file:publicManifest,sha256:reference.manifest_sha256};
const manifestBytes=await readFile(path.join(siteRoot,publicManifest));assert.equal(sha(manifestBytes),source.sha256);
const requiredPart=await requiredMeshRequestTarget(JSON.parse(manifestBytes),publicManifest,siteRoot,'item.battery_front');
const currentPart=requiredPart.pattern;
assert.equal(sha(await readFile(path.join(siteRoot,'web/robot-current/collection.json'))),reference.collection_sha256);
const bindingBody='// Reviewed candidate binding only; no renderer algorithm replacement.\nexport const CURRENT_ROBOT_SOURCE = '+JSON.stringify(source)+';\n';
const originalBinding=await readFile(new URL('software/site/designer/robot_current_source.js',root));
await mkdir(out,{recursive:false});
const selected=process.env.PLAYWRIGHT_BROWSER;assert.ok(['chromium','webkit'].includes(selected),'Explicit browser required');
const engine=selected==='webkit'?webkit:chromium,server=createSiteServer(path.resolve(siteRoot));
let browser,aborted=false,deadline;const contexts=[],errors=[];
const report={schema:'gyropup.current-renderer-capture/1',status:'FAILED_OR_INCOMPLETE',sourceRevision,
  referenceSha256:referenceHash,manifestSha256:source.sha256,collectionSha256:reference.collection_sha256,
  bindingOverlay:{file:'/designer/robot_current_source.js',originalSha256:sha(originalBinding),servedSha256:sha(bindingBody),source,notPublicAdoption:true},
  browser:selected,outputs:{},phases:[],engineering:reference.engineering};
report.requiredPartRequest={name:requiredPart.name,file:requiredPart.file,sha256:requiredPart.sha256,pathname:requiredPart.pathname};
const progress=async phase=>{report.phases.push(phase);await writeFile(path.join(out,'progress.json'),JSON.stringify(report,null,2)+'\n');console.log(phase);};
const stop=()=>{aborted=true;void browser?.close().catch(()=>{});server.closeAllConnections();server.close();};
process.once('SIGTERM',stop);process.once('SIGINT',stop);
async function save(name,value){const data=JSON.stringify(value)+'\n';await writeFile(path.join(out,name),data,{flag:'wx'});report.outputs[name]={sha256:sha(data),bytes:Buffer.byteLength(data)};}
async function context(viewport={width:1280,height:900}){
  const c=await browser.newContext({viewport,reducedMotion:'reduce'});contexts.push(c);
  await c.addInitScript(()=>{
    if(!/^https?:$/.test(location.protocol))return;
    sessionStorage.setItem('gyropup.prototype-notice','2026-10-29-v1');
    localStorage.setItem('gyropup.probe','off');localStorage.setItem('gyropup-sfx','0');
  });
  await c.route('**/designer/robot_current_source.js*',async route=>{
    const response=await route.fetch();assert.equal(sha(await response.body()),sha(originalBinding));
    await route.fulfill({response,body:bindingBody,contentType:'text/javascript'});
  });
  c.on('page',page=>page.on('pageerror',error=>errors.push(error.message)));return c;
}

try{
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  const base='http://127.0.0.1:'+server.address().port;report.port=server.address().port;
  deadline=setTimeout(stop,180000);await progress('launch');
  browser=await engine.launch(selected==='chromium'?{channel:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
  if(aborted)throw new Error('Capture cancelled during browser launch');report.browserVersion=browser.version();
  const c=await context(),page=await c.newPage();page.setDefaultTimeout(45000);
  const version=await(await c.request.get(base+'/version.json')).json();assert.equal(version.revision,sourceRevision);report.servedVersion=version;
  report.deliveredSource={};
  for(const file of ['designer/robot_v2.js','designer/current_robot.js','designer/robot_kinematics.js','designer/robot_sensors.js','designer/robot_presentations.js','designer/robot_identity.js',
    'designer/sim.js','designer/turret3d.js','designer/kit/assembly/guide.js','designer/kit/assembly/playback.js','designer/kit/portal-data.js','designer/kit/stage.js',
    'designer/kit/vendor/three/three.module.min.js','designer/kit/vendor/three/addons/loaders/STLLoader.js','web/landing.js']){
    const expected=await readFile(new URL(sourceForPublic(file),root)),response=await c.request.get(base+'/'+file);
    assert.ok(response.ok(),file);const actual=await response.body();assert.equal(sha(actual),sha(expected),file+' actual delivered source');
    report.deliveredSource[file]={sha256:sha(actual),bytes:actual.length};
  }
  await page.goto(base+'/designer/sim.html?run=none&demo=0&sound=0',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(currentRobotReady,reference.collection_sha256);
  await page.evaluate(installCurrentMotion,reference);
  const rigid=await page.evaluate(()=>{const t=window.__currentMotion;return{...t.prefix,samples:t.reference.rigid.required_poses.map((a,i)=>t.observe('rigid-'+i,t.reference.rigid.contract,t.rigidPose(a))) };});
  await save('rigid-capture.json',rigid);await progress('rigid source loop/hinge observations saved');
  for(let index=0;index<reference.live.length;index++){
    const trace=await page.evaluate(index=>{const t=window.__currentMotion,row=t.reference.live[index];return{...t.prefix,samples:row.required_poses.map((a,i)=>t.observe(row.id+'-'+i,row.contract,t.livePose(row,a)))};},index);
    await save('live-'+reference.live[index].id+'.json',trace);await progress('complete source-FK pose '+reference.live[index].id+' saved');
  }
  const operation=await page.evaluate(captureMotionOperation);assert.ok(operation.exploded&&operation.reset&&operation.flapClosed);
  await save('operation-capture.json',operation);await progress('actual firing/reload/stop-start/reset observations saved');
  // Fault observations retain the complete baseline input/coverage. Each has
  // a correct-home and restored control; only actual rendered geometry changes.
  const faults=await page.evaluate(captureMotionFaults);
  await save('fault-captures.json',faults);await progress('actual geometry fault controls saved');
  const archivedPart='**/exports/sim/v2/rig/body__interim_body.stl*';
  await page.route(archivedPart,route=>route.abort());
  const failedRecorded=await page.evaluate(async()=>{
    const r=window.__currentMotion.r,base=r.base;
    try{await r.setPresentation('recorded');return{rejected:false};}
    catch(error){return{rejected:true,error:error.message,mode:r.presentation.mode,sameBase:r.base===base,parts:r.parts.length,mass:r.info.massKg};}
  });
  assert.ok(failedRecorded.rejected&&failedRecorded.sameBase);assert.equal(failedRecorded.mode,'current');assert.equal(failedRecorded.parts,228);assert.equal(failedRecorded.mass,null);
  await page.unroute(archivedPart);
  let releaseRecorded;const heldRecorded=new Promise(resolve=>releaseRecorded=resolve);
  await page.route(archivedPart,async route=>{await heldRecorded;await route.continue();});
  const recordedRequest=page.waitForRequest(archivedPart,{timeout:10000});
  await page.evaluate(()=>{window.__pendingRecorded=window.__currentMotion.r.setPresentation('recorded');});await recordedRequest;
  await page.evaluate(()=>window.__currentMotion.r.setPresentation('current'));releaseRecorded();
  const staleRecorded=await page.evaluate(async()=>{await window.__pendingRecorded;const r=window.__currentMotion.r;return{mode:r.presentation.mode,holders:r.group.children.length,mass:r.info.massKg};});
  await page.unroute(archivedPart);assert.equal(staleRecorded.mode,'current');assert.equal(staleRecorded.holders,1);assert.equal(staleRecorded.mass,null);
  let releaseCurrent;const heldCurrent=new Promise(resolve=>releaseCurrent=resolve);
  await page.route(currentPart,async route=>{await heldCurrent;try{await route.continue();}catch{/* request was deliberately cancelled */}});
  const currentRequest=page.waitForRequest(currentPart,{timeout:10000});
  await page.evaluate(async source=>{
    const {buildRobotV2}=await import('/designer/robot_v2.js');window.__currentAbort=new AbortController();window.__lateReady=false;
    window.__pendingCurrent=buildRobotV2('/',{presentationSource:source,signal:window.__currentAbort.signal}).then(r=>{window.__lateReady=true;r.dispose();return{rejected:false};},error=>({rejected:true,error:error.message}));
  },source);
  await currentRequest;await page.evaluate(()=>window.__currentAbort.abort());releaseCurrent();
  const disposedPending=await page.evaluate(async()=>({...await window.__pendingCurrent,lateReady:window.__lateReady,mainMode:window.__currentMotion.r.presentation.mode}));
  await page.unroute(currentPart);assert.ok(disposedPending.rejected&&!disposedPending.lateReady);assert.equal(disposedPending.mainMode,'current');
  await save('async-model-controls.json',{failedRecorded,staleRecorded,disposedPending});await progress('actual failed/stale/disposed loader controls saved');
  const transitions=await page.evaluate(async()=>{
    const t=window.__currentMotion,r=t.r,summary=()=>({presentation:r.presentation,info:r.info,muzzle:r.turret.muzzle.position.toArray(),head:r.head.position.toArray()});
    r.setPose({legMM:300});const current=summary();await r.setPresentation('recorded');const recorded=summary();
    const q=Array(21).fill(0);q[2]=.5;q[3]=1;const layout={motor_f_l:7,knee_f_l:8,motor_r_l:9,knee_r_l:10,wheel_l:11,motor_f_r:12,knee_f_r:13,motor_r_r:14,knee_r_r:15,wheel_r:16,turret_pan:17,turret_tilt:18};q[7]=.2;q[17]=.4;r.setFromQpos(q,layout);
    const archivedBase=r.base,archivedMuzzle=r.turret.muzzle,archivedPosition=r.base.position.toArray();
    for(let i=0;i<3;i++){await r.setPresentation('current');await r.setPresentation('recorded');}
    const unchanged=r.base===archivedBase&&r.turret.muzzle===archivedMuzzle&&JSON.stringify(r.base.position.toArray())===JSON.stringify(archivedPosition);
    await r.setPresentation('current');r.group.visible=false;r.turret.laser.visible=false;r.group.visible=true;r.turret.updateLaser([],true);
    const laserVisible=r.turret.laser.visible&&r.turret.laser.children.some(c=>c.visible);
    const restored=summary();return{current,recorded,restored,unchanged,laserVisible};
  });
  assert.equal(transitions.current.info.massKg,null);assert.ok(transitions.recorded.info.massKg>0);assert.equal(transitions.restored.info.massKg,null);
  assert.equal(transitions.recorded.presentation.mode,'recorded');assert.equal(transitions.restored.presentation.collectionSha256,reference.collection_sha256);assert.ok(transitions.unchanged&&transitions.laserVisible);
  await save('mode-transitions.json',transitions);
  await page.evaluate(()=>window.__sim.stage.start());
  await page.locator('#design-select').selectOption('turret-box');await page.waitForFunction(()=>window.__sim?.state.bench&&window.__sim.bench()?.active);
  await page.locator('#design-select').selectOption('v2');await page.waitForFunction(()=>window.__sim?.state.modelKey==='v2'&&!window.__sim.state.bench);
  const cachedUiReturn=await page.evaluate(()=>{const s=window.__sim,r=s.state.robot;s.stage.stop();r.turret.updateLaser([],true);return{sameRobot:r===window.__currentMotion.r,mode:r.presentation.mode,laser:r.turret.laser.visible&&r.turret.laser.children.some(g=>g.visible)};});
  assert.ok(cachedUiReturn.sameRobot&&cachedUiReturn.laser);assert.equal(cachedUiReturn.mode,'current');await save('ui-model-roundtrip.json',cachedUiReturn);
  // Capture the actual route/home pose after restoring the complete assembly.
  await page.evaluate(()=>{const t=window.__currentMotion;t.r.setExplode(0);t.r.setPose({legMM:300});t.r.turret.poseMechanism({pan:0,tilt:0,pinion:0,dial:0,wheel_l:0,wheel_r:0,flap:0});t.s.stage.frame(t.r.info.heightM);t.s.stage.renderer.render(t.s.stage.scene,t.s.stage.camera);});
  const desktopCanvas=await page.waitForFunction(currentRobotCanvasReady,reference.collection_sha256,{timeout:10000,polling:'raf'});
  report.visibleCanvas={desktop:await desktopCanvas.jsonValue()};await desktopCanvas.dispose();
  await page.screenshot({path:path.join(out,'current-play-home.png'),timeout:15000});
  const routeIdentities=[];
  for(const [route,key]of [['/','__heroPreview'],['/designer/character/talk-demo.html','__talkDemo']]){
    await page.goto(base+route,{waitUntil:'domcontentloaded'});await page.waitForFunction(key=>window[key]?.robot?.presentation.collectionSha256,key);
    const identity=await page.evaluate(key=>{const r=window[key].robot;return{presentation:r.presentation,parts:r.parts.map(p=>[p.mesh.name,p.entry.sha256]).sort(),mass:r.info.massKg,homeLeg:r.info.homeLegMM};},key);
    assert.equal(identity.presentation.collectionSha256,reference.collection_sha256);assert.equal(identity.parts.length,228);assert.equal(identity.mass,null);assert.equal(identity.homeLeg,300);routeIdentities.push({route,...identity});
    await page.evaluate(key=>{const p=window[key];window.__sim={state:{robot:p.robot},stage:p.stage??{stop:()=>p.renderer.setAnimationLoop(null)},sfx:p.sfx??window.__sfx??{setEnabled(){}},talk:p.talk};},key);
    await page.evaluate(installCurrentMotion,reference);
    const routeTrace=await page.evaluate(()=>{const t=window.__currentMotion,row=t.reference.live[0];return{...t.prefix,samples:row.required_poses.map((a,i)=>t.observe('route-'+i,row.contract,t.livePose(row,a)))};});
    const combined=await page.evaluate(()=>{const t=window.__currentMotion,row=t.reference.live.at(-1),a=Object.fromEntries(Object.keys(row.contract.joints).map(k=>[k,0]));return t.observe('route-combined',row.contract,t.livePose(row,a));});
    const slug=key==='__heroPreview'?'hero':'talk';await save('route-'+slug+'-home-capture.json',routeTrace);await save('route-'+slug+'-combined-sample.json',combined);
  }
  await save('current-route-identities.json',routeIdentities);
  await c.close();
  const mobile=await context({width:320,height:568}),phone=await mobile.newPage();phone.setDefaultTimeout(45000);
  let mobileInterceptions=0;
  await phone.route(currentPart,route=>{mobileInterceptions++;return route.fulfill({status:503,body:'Deliberate candidate required-part failure'});});
  await phone.goto(base+'/designer/sim.html?run=none&demo=0&sound=0',{waitUntil:'domcontentloaded'});
  await phone.waitForFunction(()=>[...document.querySelectorAll('#sim-startup,#sim-loading')].some(e=>e.dataset.state==='error'&&!e.hidden));
  const status=phone.locator('#sim-startup[data-state="error"],#sim-loading[data-state="error"]').filter({visible:true}).first();
  const button=status.locator('button:visible').first();assert.ok(await button.isVisible());
  const box=await button.boundingBox();assert.ok(box&&box.x>=0&&box.y>=0&&box.x+box.width<=320&&box.y+box.height<=568);
  assert.ok(mobileInterceptions>0,'The required-part HTTP failure must actually be intercepted');
  const mobileFailure={text:await status.innerText(),button:box,interceptions:mobileInterceptions,requiredPart:report.requiredPartRequest,falseReady:await phone.evaluate(()=>document.body.dataset.ready==='1')};assert.equal(mobileFailure.falseReady,false);
  await phone.unroute(currentPart);await button.click();
  await phone.waitForFunction(currentRobotReady,reference.collection_sha256);
  const mobileCanvas=await phone.waitForFunction(currentRobotCanvasReady,reference.collection_sha256,{timeout:10000,polling:'raf'});
  report.visibleCanvas.mobile=await mobileCanvas.jsonValue();await mobileCanvas.dispose();mobileFailure.recoveredCanvas=report.visibleCanvas.mobile;
  await save('mobile-error-recovery.json',mobileFailure);await phone.screenshot({path:path.join(out,'mobile-current-recovered.png'),timeout:15000});
  assert.deepEqual(errors,[]);report.status='CAPTURED_AWAITING_INDEPENDENT_SHARED_VALIDATION';await progress('browser observations complete; not a validation/qualification verdict');
}catch(error){report.error=error.stack??String(error);throw error;}
finally{
  clearTimeout(deadline);process.removeListener('SIGTERM',stop);process.removeListener('SIGINT',stop);
  await Promise.allSettled(contexts.map(c=>c.close()));await browser?.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));
  report.listenerClosed=!server.listening;report.pageErrors=errors;await writeFile(path.join(out,'capture-index.json'),JSON.stringify(report,null,2)+'\n');
}
