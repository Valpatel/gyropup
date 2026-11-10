/** Capture the twelve current guide diagrams through the existing product viewer. */
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {captureContract} from './poster-contract.mjs';
import {createSiteServer} from '../serve-site.mjs';
import {chromium} from '@playwright/test';

const root=path.resolve(import.meta.dirname,'../../..');
const out=process.argv[2]||process.env.TEST_OUTPUT;
assert.ok(out&&path.isAbsolute(out),'Explicit output directory required');
assert.match(process.env.POSTER_VISUAL_SHA256||'',/^[0-9a-f]{64}$/,'Pin the expected visual SHA256');
await mkdir(out,{recursive:false});
const sha=x=>createHash('sha256').update(x).digest('hex');
const contract=await captureContract(root);
assert.equal(contract.visual_sha256,process.env.POSTER_VISUAL_SHA256,'Exact final visual contract');
const head=execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim();
const server=createSiteServer(path.join(root,'dist'));
server.listen(0,'127.0.0.1');await once(server,'listening');
const base='http://127.0.0.1:'+server.address().port;
console.log('Owned poster listener',base,'source',head);
const errors=[],foreign=[],frames={},proof={};let browser;
try{
 browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const context=await browser.newContext({viewport:{width:1280,height:900},deviceScaleFactor:1,colorScheme:'light',reducedMotion:'reduce'});
 const page=await context.newPage();
 const version=await(await context.request.get(base+'/version.json')).json();assert.equal(version.revision,head,'Build the exact current checkout before capture');
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(!r.url().startsWith(base+'/')&&!r.url().startsWith('data:')&&!r.url().startsWith('blob:'))foreign.push(r.url());});
 await page.goto(base+'/designer/build.html?snapshot=turret-wip-4866459e2abd&step=step-01#assembly');
 await page.locator('#prototype-notice-dialog[open]').waitFor();await page.locator('#prototype-notice-ack').click();
 await page.waitForFunction(()=>document.querySelector('.appnav'));await page.evaluate(()=>document.fonts.ready);
 await page.waitForFunction(()=>window.__buildGuide?.active?.viewer&&document.querySelector('#assembly').dataset.ready==='1',null,{timeout:30000});
 const guide=await page.evaluate(()=>window.__buildGuide.active.guide);
 assert.equal(guide.steps.length,12);
 for(const step of guide.steps){
  await page.evaluate(id=>window.__buildGuide.apply(id),step.id);
  await page.locator('[data-guide-model]').evaluate(el=>{const r=el.getBoundingClientRect();window.scrollTo({left:0,top:r.top+scrollY-(innerHeight-r.height)/2,behavior:'instant'});});
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  const state=await page.evaluate(()=>{
   const a=window.__buildGuide.active,v=a.viewer,c=v.stage.renderer.domElement;
   return {step:a.step,state:v.getState(),calls:v.stage.renderer.info.render.calls,
    canvas:{width:c.width,height:c.height,cssWidth:c.getBoundingClientRect().width,cssHeight:c.getBoundingClientRect().height,unoccluded:[.1,.5,.9].every(x=>[.1,.5,.9].every(y=>{const r=c.getBoundingClientRect();return document.elementFromPoint(r.x+r.width*x,r.y+r.height*y)===c;}))},
    visible:v.parts.filter(p=>p.mesh.visible).map(p=>p.name),camera:v.stage.camera.position.toArray(),target:v.stage.controls.target.toArray()};
  });
  assert.equal(state.step,step.id);assert.ok(state.calls>0);assert.equal(state.canvas.unoccluded,true,'Canvas must be exposed before capturing its pixels');
  if(step.camera){const expected=[step.camera.direction[0],step.camera.direction[2],-step.camera.direction[1]],actual=state.camera.map((v,i)=>v-state.target[i]),dot=expected.reduce((sum,v,i)=>sum+v*actual[i],0)/(Math.hypot(...expected)*Math.hypot(...actual));assert.ok(dot>1-1e-9,'Authored CAD camera direction must be applied exactly once');}
  assert.equal(state.state.mode,'ghost');assert.equal(state.state.selected,null);assert.equal(state.state.isolate,null);
  assert.deepEqual(state.state.partModes,{});assert.deepEqual(state.state.offsets_mm,step.offsets_mm);
  assert.deepEqual([...state.visible].sort(),[...step.parts].sort());assert.deepEqual(state.state.highlight,step.highlight);
  const file=step.id+'.png';
  await page.locator('[data-guide-model] canvas').screenshot({path:path.join(out,file)});
  frames[step.id]={file,sha256:sha(await readFile(path.join(out,file)))};proof[step.id]=state;
  console.log('Captured',step.id,state.canvas.width+'x'+state.canvas.height,state.visible.length,'visible instances');
 }
 assert.deepEqual(errors,[]);assert.deepEqual(foreign,[]);
 assert.equal((await captureContract(root)).visual_sha256,contract.visual_sha256,'Source remained frozen');
 assert.equal(execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(),head,'Checkout remained frozen');
 const receipt={visual_sha256:contract.visual_sha256,source_commit:head,version,browser:browser.version(),session_notice_acknowledged:true,render:contract.inputs.render,frames,proof,errors,foreign};
 await writeFile(path.join(out,'posters.json'),JSON.stringify(receipt,null,2)+'\n');
 await writeFile(path.join(out,'visual-contract.json'),JSON.stringify(contract,null,2)+'\n');
 console.log('PASS',Object.keys(frames).length,'actual canvas posters',sha(await readFile(path.join(out,'posters.json'))));
 await context.close();
}catch(error){await writeFile(path.join(out,'failure.json'),JSON.stringify({head,frames,proof,errors,foreign,error:error.stack},null,2)+'\n');throw error;}
finally{await browser?.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));console.log('Owned poster listener closed');}
