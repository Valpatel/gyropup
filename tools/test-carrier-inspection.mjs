/** Inspect the actual exported carrier through the document's native preview link. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {chromium,webkit} from '@playwright/test';
import {createSiteServer} from './serve-site.mjs';
import {acknowledgePrototypeNotice} from './test-prototype-session.mjs';

const server=process.env.SITE_URL?null:createSiteServer();
if(server)await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const base=(process.env.SITE_URL||`http://127.0.0.1:${server.address().port}`).replace(/\/$/,'');
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
const context=await browser.newContext();await acknowledgePrototypeNotice(context);
const page=await context.newPage(),out=process.env.TEST_OUTPUT||'/tmp/gyropup-carrier-inspection';
await mkdir(out,{recursive:true});
const report={engine:engine.name(),passed:false,cases:[],errors:[],missing:[],requestFailures:[]};
page.on('pageerror',error=>report.errors.push(error.message));
page.on('response',response=>{if(response.status()>=400)report.missing.push({url:response.url(),status:response.status()});});
page.on('requestfailed',request=>report.requestFailures.push({url:request.url(),error:request.failure()?.errorText}));
const original='/exports/turret/base-board-service/interfaces/carrier-wiring-layout.step';
const docPath='/site/pages/docs-base-board-interfaces-md.html';
const doc=base+docPath+'?live=0'; // Static previews do not run cad-agent's local live-reload endpoint.
const state=()=>page.evaluate(()=>({url:location.href,visibility:document.visibilityState,
  state:window.__fileViewer?.root.dataset.state,message:document.querySelector('.file-status')?.innerText,
  bootstrap:document.body.dataset.viewerError,diagramStates:[...document.querySelectorAll('.cad-diagram')].map(n=>n.dataset.state)}));
async function ready(){
  await page.waitForFunction(()=>['ready','error','cancelled'].includes(window.__fileViewer?.root.dataset.state),null,{timeout:135000});
  const current=await state();assert.equal(current.state,'ready',JSON.stringify(current));
}
async function inspect(){return page.evaluate(async()=>{
  const v=window.__fileViewer,THREE=await import('/designer/kit/vendor/three/three.module.min.js');
  const box=new THREE.Box3().setFromObject(v.model),meshes=[];
  v.model.traverseVisible(n=>{if(n.isMesh)meshes.push({name:n.name,colors:[].concat(n.material).map(m=>m.color.getHexString())});});
  const points=Array.from({length:8},(_,i)=>new THREE.Vector3(i&1?box.max.x:box.min.x,i&2?box.max.y:box.min.y,i&4?box.max.z:box.min.z).project(v.stage.camera).toArray());
  return{meshes,triangles:v.info.triangles,boundsMm:v.info.boundsMm,scrollWidth:document.documentElement.scrollWidth,points};
});}
function assertIdentity(model){
  const names=model.meshes.map(m=>m.name);assert.equal(new Set(names).size,names.length,'STEP member identities must be unique');
  for(const name of ['pan_base_authored','carrier_authored','cut_PCB_nominal_stock'])assert.ok(names.includes(name),name);
  assert.equal(names.filter(n=>/^authored_public_.*screws#/.test(n)).length,8,'All eight mounting screws remain individually visible');
  assert.equal(names.filter(n=>/^authored_public_.*inserts#/.test(n)).length,8,'All eight mounting inserts remain individually visible');
  const reservations=model.meshes.filter(m=>m.name.startsWith('RESERVATION_ONLY_C2_'));
  assert.equal(reservations.length,4,'Both halves of both C2 candidates remain explicitly reservations');
  assert.ok(reservations.every(m=>m.colors.every(c=>c==='f25c17')),'Reservation orange survives the STEP importer');
  const colorClasses=[[/^pan_base_authored$/,'667585'],[/^carrier_authored$/,'337aad'],[/^cut_PCB_nominal_stock$/,'1f7a47'],[/^component_envelope_/,'424a54'],[/^authored_public_.*screws#/,'b8bfc7'],[/^authored_public_.*inserts#/,'b88733']];
  for(const [pattern,color] of colorClasses){
    const members=model.meshes.filter(m=>pattern.test(m.name));assert.ok(members.length,pattern.source);
    assert.ok(members.every(m=>m.colors.length&&m.colors.every(c=>c===color)),`STEP materials must remain attached to ${pattern.source}`);
  }
  assert.ok(new Set(model.meshes.flatMap(m=>m.colors)).size>=7,'Mechanical parts, PCB, components, screws, inserts and reservations retain separate colors');
}
try{
  report.version=await(await context.request.get(base+'/version.json')).json();
  const receipt=JSON.parse(await readFile(new URL('../exports/turret/base-board-service/interfaces/interfaces.json',import.meta.url),'utf8'));
  const file=await context.request.get(base+original);assert.equal(file.status(),200);
  report.stepSha256=createHash('sha256').update(await file.body()).digest('hex');
  assert.equal(report.stepSha256,receipt.artifact_sha256['carrier-wiring-layout.step'],'Served original matches the committed geometry receipt');
  for(const [width,height]of [[320,568],[390,844],[1440,1000]]){
    await page.setViewportSize({width,height});await page.goto(doc);
    await page.locator('.cad-diagram-view svg').waitFor();
    const documentState=await page.evaluate(()=>({width:document.documentElement.scrollWidth,
      diagrams:document.querySelectorAll('.cad-diagram[data-state=ready] svg').length,
      visibleSource:[...document.querySelectorAll('pre.mermaid,code.language-mermaid')].filter(n=>n.getClientRects().length).length}));
    assert.ok(documentState.width<=width);assert.equal(documentState.diagrams,1);assert.equal(documentState.visibleSource,0);
    assert.match(await page.locator('article').innerText(),/readiness: false/);
    const link=page.getByRole('link',{name:'Preview carrier-wiring-layout.step in 3D',exact:true});
    await link.scrollIntoViewIfNeeded();await page.screenshot({path:`${out}/${engine.name()}-${width}-document.png`});
    await link.click();await ready();
    assert.equal(new URL(page.url()).searchParams.get('file'),original);
    const model=await inspect();assertIdentity(model);
    assert.ok(model.triangles>0&&model.boundsMm.every(n=>Number.isFinite(n)&&n>0));
    assert.ok(model.scrollWidth<=width);
    assert.ok(model.points.every(p=>p.every(Number.isFinite)&&p.slice(0,2).every(n=>Math.abs(n)<1.01)),'Imported assembly fits the canvas');
    await page.screenshot({path:`${out}/${engine.name()}-${width}-assembly.png`});
    const viewDirections=[];
    for(const [name,direction]of [['Front',[0,0,1]],['Side',[1,0,0]],['Top',[0,1,.0001]],['Isometric',[1,.7,1.3]]]){
      await page.getByRole('button',{name,exact:true}).click();
      await page.waitForFunction(expected=>{
        const v=window.__fileViewer,actual=v.stage.camera.position.clone().sub(v.stage.controls.target).normalize();
        const length=Math.hypot(...expected);return expected.every((n,i)=>Math.abs(actual.getComponent(i)-n/length)<.0001);
      },direction,{timeout:5000});
      viewDirections.push({name,expected:direction,actual:await page.evaluate(()=>{const v=window.__fileViewer;return v.stage.camera.position.clone().sub(v.stage.controls.target).normalize().toArray();})});
    }
    const radius=await page.evaluate(()=>window.__fileViewer.stage.camera.position.distanceTo(window.__fileViewer.stage.controls.target));
    const canvas=await page.locator('.file-canvas canvas').boundingBox();await page.mouse.move(canvas.x+canvas.width/2,canvas.y+canvas.height/2);await page.mouse.wheel(0,120);
    await page.waitForFunction(r=>window.__fileViewer.stage.camera.position.distanceTo(window.__fileViewer.stage.controls.target)>r*1.01,radius);
    const wheelRatio=await page.evaluate(r=>window.__fileViewer.stage.camera.position.distanceTo(window.__fileViewer.stage.controls.target)/r,radius);assert.ok(wheelRatio<1.02);
    // Fit must visibly undo the wheel change, not just accept a click.
    await page.getByRole('button',{name:'Fit',exact:true}).click();
    await page.waitForFunction(expected=>{const v=window.__fileViewer;return Math.abs(v.stage.camera.position.distanceTo(v.stage.controls.target)-expected)<expected*.0001;},radius,{timeout:5000});
    const fitRadius=await page.evaluate(()=>{const v=window.__fileViewer;return v.stage.camera.position.distanceTo(v.stage.controls.target);});
    assert.equal(await page.getByRole('link',{name:'Download original',exact:true}).getAttribute('href'),base+original);
    if(width===1440){
      const applyColors=async meshes=>page.evaluate(rows=>{
        const model=window.__fileViewer.model;
        for(const row of rows){const node=model.getObjectByName(row.name);[].concat(node.material).forEach((m,i)=>m.color.setHex(parseInt(row.colors[i],16)));}
        return new Promise(resolve=>requestAnimationFrame(resolve));
      },meshes);
      // Corrupt actual scene materials/instances, then re-inspect through the same
      // browser observation path. These controls do not mutate source geometry.
      const gray=structuredClone(model.meshes);gray.forEach(m=>m.colors=m.colors.map(()=> 'b8bfc7'));
      await applyColors(gray);const grayModel=await inspect();assert.throws(()=>assertIdentity(grayModel),/Reservation orange/);
      await applyColors(model.meshes);
      const swapped=structuredClone(model.meshes),baseMesh=swapped.find(m=>m.name==='pan_base_authored'),carrierMesh=swapped.find(m=>m.name==='carrier_authored');
      [baseMesh.colors,carrierMesh.colors]=[carrierMesh.colors,baseMesh.colors];
      await applyColors(swapped);const swappedModel=await inspect();assert.throws(()=>assertIdentity(swappedModel),/STEP materials must remain attached/);
      await applyColors(model.meshes);
      await page.evaluate(()=>window.__fileViewer.model.getObjectByName('authored_public_base_board_inserts#0').visible=false);
      const hiddenInsert=await inspect();assert.throws(()=>assertIdentity(hiddenInsert),/eight mounting inserts/);
      await page.evaluate(()=>window.__fileViewer.model.getObjectByName('authored_public_base_board_inserts#0').visible=true);
      await page.evaluate(()=>{const model=window.__fileViewer.model;model.userData.removedReviewScrew=model.getObjectByName('authored_public_base_board_screws#0');model.remove(model.userData.removedReviewScrew);});
      const missingScrew=await inspect();assert.throws(()=>assertIdentity(missingScrew),/eight mounting screws/);
      await page.evaluate(()=>{const model=window.__fileViewer.model;model.add(model.userData.removedReviewScrew);delete model.userData.removedReviewScrew;});
      assertIdentity(await inspect());report.negativeControls=['lost STEP materials','swapped part colors','hidden mounting insert','missing mounting screw'];
    }

    await page.getByRole('link',{name:'Back to parts',exact:true}).click();
    await page.waitForURL(url=>url.origin===new URL(base).origin&&[docPath,docPath.slice(0,-5)].includes(url.pathname)&&url.search==='?live=0');
    await page.locator('.cad-diagram[data-state=ready] svg').waitFor();
    report.cases.push({width,height,documentState,model,viewDirections,wheelRatio,fitRadius});
  }
  assert.deepEqual(report.errors,[]);assert.deepEqual(report.missing,[]);assert.deepEqual(report.requestFailures,[]);
  report.passed=true;console.log(JSON.stringify({passed:true,engine:engine.name(),cases:report.cases.length,out}));
}catch(error){
  report.failure={message:error.message,stack:error.stack};
  try{report.lastState=await state();await page.screenshot({path:`${out}/${engine.name()}-failure.png`});}catch(diagnosticError){report.diagnosticError=diagnosticError.message;}
  throw error;
}finally{
  await writeFile(`${out}/${engine.name()}-report.json`,JSON.stringify(report,null,2));
  await browser.close();if(server)await new Promise(resolve=>{server.close(resolve);server.closeAllConnections();});
}
