/** Real product scenes and user actions. Fixtures are explicitly synthetic, never release history. */
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {chromium,webkit} from '@playwright/test';
const base=(process.env.SITE_URL||'http://127.0.0.1:8879').replace(/\/$/,'');
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const out=process.env.TEST_OUTPUT||'/tmp/gyropup-build-guide';await mkdir(out,{recursive:true});
const browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
const scope=process.env.GUIDE_CASE||'all';if(!['all','core','switching','fallback','touch'].includes(scope))throw Error('Unknown guide test scope');
const contexts=[],cases=[],errors=[],phases=[];let provenance;
const phase=name=>{phases.push({name,at:new Date().toISOString()});console.log('PHASE '+name);};
async function context(options={}){const c=await browser.newContext(options);contexts.push(c);await c.addInitScript(()=>sessionStorage.setItem('gyropup.prototype-notice','2026-10-29-v1'));return c;}
async function pageFor(c,url=''){const p=await c.newPage();p.setDefaultTimeout(45000);p.on('pageerror',e=>errors.push(e.message));await p.goto(base+'/designer/build.html'+url);await p.waitForFunction(()=>window.__buildGuide?.active?.viewer);return p;}
const state=p=>p.evaluate(()=>{const a=window.__buildGuide.active;return {step:a.step,snapshot:a.guide.snapshot.id,text:document.querySelector('[data-guide-text]').textContent,parts:a.viewer.parts.map(p=>({name:p.name,visible:p.mesh.visible,position:p.mesh.position.toArray(),opacity:p.mesh.material.opacity,wireframe:p.mesh.material.wireframe,emissive:p.mesh.material.emissive?.getHex()}))};});
try{
 provenance={...provenance,base,version:await(await fetch(base+'/version.json')).json(),browser:browser.version(),scope};
 if(scope==='all'||scope==='core'){
 phase('core-start');
 const c=await context({viewport:{width:1280,height:900},reducedMotion:'reduce'}),p=await pageFor(c);const initial=await state(p);
 assert.equal(initial.snapshot,'turret-wip-4866459e2abd');assert.equal(initial.parts.length,55);
 const guide=await p.evaluate(()=>window.__buildGuide.active.guide);provenance={...provenance,base,version:await(await c.request.get(base+'/version.json')).json(),browser:browser.version(),snapshot:guide.snapshot,guide_sha256:await p.evaluate(()=>window.__buildGuide.active.guideHash),model_sha256:guide.model.sha256};
 // Every stage via native navigation, then back: verify actual rendered instance visibility/materials/offsets.
 const captures=new Map();
 for(let i=0;i<12;i++){
  phase('forward-'+(i+1));if(i)await p.getByRole('button',{name:'Next →',exact:true}).click();
  const actual=await state(p),s=guide.steps[i];assert.equal(actual.step,s.id);
  assert.deepEqual(actual.parts.filter(v=>v.visible).map(v=>v.name).sort(),[...s.parts].sort());
  for(const part of actual.parts){if(!part.visible)continue;assert.deepEqual(part.position,s.offsets_mm[part.name]||[0,0,0]);if(s.highlight.includes(part.name))assert.equal(part.opacity,1);else assert.ok(part.opacity>0&&part.opacity<.5);}
  captures.set(s.id,actual.parts);
 }
 for(let i=10;i>=0;i--){await p.getByRole('button',{name:'← Previous',exact:true}).click();assert.deepEqual((await state(p)).parts,captures.get(guide.steps[i].id));}
 await p.getByLabel('Instruction step',{exact:true}).selectOption('step-10');assert.deepEqual((await state(p)).parts,captures.get('step-10'));
 await p.reload();await p.waitForFunction(()=>window.__buildGuide?.active?.step==='step-10');assert.deepEqual((await state(p)).parts,captures.get('step-10'));
 cases.push('all12 sequential/back/direct/reload actual object states');
 await p.locator('[data-guide-mode]').selectOption('wireframe');assert.ok((await state(p)).parts.filter(v=>v.visible).every(v=>v.wireframe));
 await p.locator('[data-guide-section]').focus();await p.keyboard.press('Home');await p.keyboard.press('ArrowRight');assert.equal(await p.locator('[data-guide-section]').inputValue(),'0.01');assert.ok(await p.evaluate(()=>window.__buildGuide.active.viewer.parts.every(p=>p.mesh.material.clippingPlanes[0].constant<1e9)));
 await p.locator('[data-guide-reset]').click();assert.ok((await state(p)).parts.every(v=>v.position.every(x=>x===0)));assert.ok((await state(p)).parts.filter(v=>v.visible).every(v=>!v.wireframe));assert.equal(await p.locator('[data-guide-mode]').inputValue(),'solid');assert.equal(await p.locator('[data-guide-explode]').inputValue(),'0');assert.equal(await p.locator('[data-guide-section]').inputValue(),'1');assert.equal(await p.locator('[data-guide-isolate]').getAttribute('aria-pressed'),'false');
 await p.getByText('Parts in this step',{exact:true}).focus();await p.keyboard.press('Enter');assert.equal(await p.locator('[data-guide-parts]').isVisible(),true);
 await p.locator('[data-guide-parts]').locator('button').first().click();await p.locator('[data-guide-isolate]').click();assert.equal((await state(p)).parts.filter(v=>v.visible).length,1);
 const hit=await p.evaluate(async()=>{const a=window.__buildGuide.active,part=a.viewer.parts.find(p=>p.name===a.selected),THREE=await import('/designer/kit/vendor/three/three.module.min.js'),v=new THREE.Vector3(),pos=part.mesh.geometry.attributes.position;for(let i=0;i<3;i++)v.add(new THREE.Vector3().fromBufferAttribute(pos,i));v.divideScalar(3);part.mesh.localToWorld(v);a.viewer.stage.camera.updateMatrixWorld(true);v.project(a.viewer.stage.camera);const c=a.viewer.stage.renderer.domElement,r=c.getBoundingClientRect(),x=r.left+(v.x+1)*r.width/2,y=r.top+(1-v.y)*r.height/2;return{x,y,name:a.selected,unoccluded:document.elementFromPoint(x,y)===c};});assert.equal(hit.unoccluded,true,JSON.stringify(hit));await p.mouse.click(hit.x,hit.y);assert.equal(await p.evaluate(()=>window.__buildGuide.active.selected),hit.name);assert.match(await p.locator('[data-guide-selection]').innerText(),/Selected:/);await p.locator('[data-guide-isolate]').click();
 cases.push('wireframe, native section control, assembled reset, actual canvas/list selection/isolation and keyboard details');
 const selected=await p.evaluate(()=>window.__buildGuide.active.selected),beforePartModes=(await state(p)).parts;
 await p.locator('[data-guide-part-mode]').selectOption('transparent');const transparent=(await state(p)).parts;assert.ok(transparent.find(v=>v.name===selected).opacity<.5);assert.deepEqual(transparent.filter(v=>v.name!==selected),beforePartModes.filter(v=>v.name!==selected));
 await p.locator('[data-guide-part-mode]').selectOption('wireframe');const partWire=(await state(p)).parts;assert.equal(partWire.find(v=>v.name===selected).wireframe,true);assert.deepEqual(partWire.filter(v=>v.name!==selected),beforePartModes.filter(v=>v.name!==selected));
 await p.locator('[data-guide-part-mode]').selectOption('automatic');assert.deepEqual((await state(p)).parts,beforePartModes);
 await p.locator('[data-guide-part-mode]').selectOption('transparent');await p.getByRole('button',{name:'Next →',exact:true}).click();assert.deepEqual(await p.evaluate(()=>window.__buildGuide.active.viewer.getState().partModes),{});assert.equal(await p.locator('[data-guide-part-mode]').inputValue(),'automatic');
 await p.getByRole('button',{name:'← Previous',exact:true}).click();await p.locator('[data-guide-reset]').click();assert.deepEqual(await p.evaluate(()=>window.__buildGuide.active.viewer.getState().partModes),{});assert.equal(await p.locator('[data-guide-part-mode]').inputValue(),'automatic');
 cases.push('selected-instance transparent/wireframe leaves others exact; Automatic/newstep/reset clear overrides');

 const completed=p.locator('[data-guide-complete]');await completed.check();await p.reload();await p.waitForFunction(()=>window.__buildGuide?.active?.step==='step-10');assert.equal(await completed.isChecked(),true);
 // Actual independent visible displacement: +Z CAD lift maps to +Y world metres exactly once.
 await p.getByLabel('Instruction step',{exact:true}).selectOption('step-02');
 const delta=await p.evaluate(()=>{const a=window.__buildGuide.active,p=a.viewer.parts.find(p=>p.name==='pan_pinion');const v=p.mesh.position.clone();a.controller.applyStep('step-02',{explode:0,frame:false});p.mesh.updateWorldMatrix(true,false);const x=p.mesh.getWorldPosition(v.clone());a.controller.applyStep('step-02',{explode:1,frame:false});p.mesh.updateWorldMatrix(true,false);return p.mesh.getWorldPosition(v.clone()).sub(x).toArray();});
 assert.ok(Math.abs(delta[0])<1e-8&&Math.abs(delta[1]-.070)<1e-8&&Math.abs(delta[2])<1e-8,JSON.stringify(delta));
 cases.push('independent70mm CAD-Z/world-Y displacement');
 for(const viewport of [{width:390,height:844},{width:844,height:390},{width:1280,height:900}]){
  await p.setViewportSize(viewport);await p.locator('#assembly').scrollIntoViewIfNeeded();
  const rect=await p.locator('[data-guide-model]').boundingBox();assert.ok(rect.width>=250&&rect.height>=240);
  assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await p.screenshot({path:`${out}/${engine.name()}-${viewport.width}.png`});
 }
 // Opening legacy anchors keeps the original tables/downloads reachable.
 await p.goto(base+'/designer/build.html#queue');await p.waitForFunction(()=>document.body.dataset.ready==='1');assert.equal(await p.locator('#build-details').getAttribute('open')!==null,true);assert.ok(await p.locator('#queue tr[data-part-key]').count()>0);
 cases.push('phone/landscape bounds and preserved Buy/Print anchor');
 // Two immutable synthetic versions go through the real product loader, not mocked controller calls.
 await c.close();phase('core-complete');
 }
 if(scope==='all'||scope==='switching'){
 phase('switching-start');
 const fc=await context({viewport:{width:390,height:844}});await fc.addInitScript(()=>Object.defineProperty(window,'localStorage',{get(){throw new DOMException('Storage denied','SecurityError');}}));const f=await fc.newPage();f.on('pageerror',e=>errors.push(e.message));f.setDefaultTimeout(45000);
 const snapshots=[];for(const key of ['one','two']){const raw=await readFile(new URL(`./fixtures/version-${key}.json`,import.meta.url));const g=JSON.parse(raw);snapshots.push({id:g.snapshot.id,title:'TEST fixture '+key,status:g.snapshot.status,file:`fixture-${key}/guide.json`,sha256:createHash('sha256').update(raw).digest('hex')});}
 const publishedIndex=await(await fc.request.get(base+'/web/build-guides/index.json')).json();snapshots.push(publishedIndex.snapshots[0]);
 await f.route('**/web/build-guides/index.json',r=>r.fulfill({json:{schema:'gyropup.build-guides/1',snapshots}}));
 await f.route('**/web/build-guides/fixture-*/*',async r=>{const u=new URL(r.request().url()),last=u.pathname.split('/').at(-1),key=u.pathname.includes('fixture-one')?'one':'two';const name=last==='guide.json'?`version-${key}.json`:last;try{await r.fulfill({body:await readFile(new URL('./fixtures/'+name,import.meta.url)),contentType:name.endsWith('.json')?'application/json':'application/octet-stream'});}catch{await r.fulfill({status:404});}});
 await f.goto(base+'/designer/build.html');await f.waitForFunction(()=>window.__buildGuide?.active?.guide.snapshot.id==='fixture-one');await f.locator('[data-guide-complete]').check();
 phase('switch-to-two');await f.getByLabel('Design snapshot',{exact:true}).selectOption('fixture-two');await f.waitForFunction(()=>window.__buildGuide?.active?.guide.snapshot.id==='fixture-two');assert.match(await f.locator('[data-guide-text]').innerText(),/Fixture two/);assert.equal(await f.locator('[data-guide-complete]').isChecked(),false);assert.equal((await state(f)).parts.length,3);
 phase('switch-back-one');await f.getByLabel('Design snapshot',{exact:true}).selectOption('fixture-one');await f.waitForFunction(()=>window.__buildGuide?.active?.guide.snapshot.id==='fixture-one');assert.equal(await f.locator('[data-guide-complete]').isChecked(),true);
 await f.route('**/fixture-two/two-view.json',r=>r.fulfill({body:'{}',contentType:'application/json'}));await f.getByLabel('Design snapshot',{exact:true}).selectOption('fixture-two');await f.waitForFunction(()=>document.querySelector('[data-guide-status]').dataset.state==='error');assert.equal((await state(f)).snapshot,'fixture-one');assert.equal(await f.getByLabel('Design snapshot',{exact:true}).inputValue(),'fixture-one');
 await f.getByLabel('Design snapshot',{exact:true}).selectOption('turret-wip-4866459e2abd');await f.waitForFunction(()=>window.__buildGuide.active.guide.snapshot.id==='turret-wip-4866459e2abd');assert.equal((await state(f)).parts.length,55);assert.equal(await f.locator('[data-guide-complete]').isChecked(),false);
 await f.getByLabel('Design snapshot',{exact:true}).selectOption('fixture-one');await f.waitForFunction(()=>window.__buildGuide.active.guide.snapshot.id==='fixture-one');assert.equal(await f.locator('[data-guide-complete]').isChecked(),true);
 cases.push('two distinct frozen versions plus exact WIP/tab-only progress under denied storage and corrupt-switch preservation');
 await f.unroute('**/fixture-two/two-view.json');let releaseLate,lateSettled;const settled=new Promise(resolve=>lateSettled=resolve);
 await f.route('**/fixture-two/two-view.json',async r=>{await new Promise(resolve=>releaseLate=resolve);try{await r.fulfill({body:await readFile(new URL('./fixtures/two-view.json',import.meta.url)),contentType:'application/json'});}catch{}finally{lateSettled();}});
 await f.evaluate(()=>{window.oldGuideViewer=window.__buildGuide.active.viewer;window.oldGuideTicks=0;window.oldGuideViewer.stage.onFrame(()=>window.oldGuideTicks++);});
 await f.getByLabel('Design snapshot',{exact:true}).selectOption('fixture-two');for(let i=0;i<100&&!releaseLate;i++)await new Promise(r=>setTimeout(r,10));assert.ok(releaseLate,'held actual model request observed');
 await f.getByLabel('Design snapshot',{exact:true}).selectOption('fixture-one');await f.waitForFunction(()=>window.__buildGuide.active.viewer!==window.oldGuideViewer);releaseLate();await settled;
 assert.equal((await state(f)).snapshot,'fixture-one');const beforeTicks=await f.evaluate(()=>({ticks:window.oldGuideTicks,gone:window.oldGuideViewer.stage.renderer.getContext().isContextLost(),connected:window.oldGuideViewer.stage.renderer.domElement.isConnected}));
 await f.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));assert.equal(await f.evaluate(()=>window.oldGuideTicks),beforeTicks.ticks);assert.equal(beforeTicks.gone,true);assert.equal(beforeTicks.connected,false);assert.equal(await f.locator('[data-guide-model] canvas').count(),1);cases.push('late superseded actual model request cannot replace scene; old callbacks/context disposed');
 await fc.close();phase('switching-complete');
 }
 if(scope==='all'||scope==='fallback'){
 phase('fallback-start');
 const plain=await context({javaScriptEnabled:false,viewport:{width:390,height:844}}),np=await plain.newPage();await np.goto(base+'/designer/build.html');await np.getByRole('link',{name:'All twelve instructions in plain HTML'}).click();assert.equal(await np.locator('main section').count(),12);assert.match(await np.locator('#step-08').innerText(),/\+12 and -25/);
 const noGL=await context({viewport:{width:390,height:844}});await noGL.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return String(type).includes('webgl')?null:original.call(this,type,...args);};});const gp=await noGL.newPage();gp.on('pageerror',e=>errors.push(e.message));await gp.goto(base+'/designer/build.html');await gp.waitForFunction(()=>window.__buildGuide?.active&&document.getElementById('assembly').dataset.ready==='1');assert.equal(await gp.locator('[data-guide-visual]').isVisible(),false);assert.match(await gp.locator('[data-guide-status]').innerText(),/3D is unavailable/);assert.ok((await gp.locator('[data-guide-text]').innerText()).length>50);cases.push('native no-script/current plain instructions and real WebGL-disabled fallback');
 phase('fallback-complete');
 }
 if(scope==='all'||scope==='touch'){
 phase('touch-start');
 const tc=await context({viewport:{width:390,height:844},hasTouch:true,isMobile:true,reducedMotion:'reduce'}),tp=await pageFor(tc);
 assert.equal(await tp.evaluate(()=>navigator.maxTouchPoints>0),true);assert.ok(await tp.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 async function touchControl(locator){await locator.scrollIntoViewIfNeeded();const box=await locator.boundingBox();assert.ok(box&&box.width>=44&&box.height>=44);assert.equal(await locator.evaluate(el=>{const r=el.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return el===hit||el.contains(hit);}),true);await locator.tap();}
 await touchControl(tp.getByRole('button',{name:'Next →',exact:true}));assert.equal((await state(tp)).step,'step-02');
 await touchControl(tp.getByRole('button',{name:'← Previous',exact:true}));assert.equal((await state(tp)).step,'step-01');assert.equal(await tp.evaluate(()=>window.__buildGuide.active.selected),null);
 await tp.locator('[data-guide-model]').scrollIntoViewIfNeeded();
 const target=await tp.evaluate(async()=>{const a=window.__buildGuide.active,part=a.viewer.parts.find(p=>p.name==='pan_base'),THREE=await import('/designer/kit/vendor/three/three.module.min.js'),pos=part.mesh.geometry.attributes.position,c=a.viewer.stage.renderer.domElement,r=c.getBoundingClientRect();part.mesh.updateWorldMatrix(true,false);a.viewer.stage.camera.updateMatrixWorld(true);for(let i=0;i<pos.count-2;i+=Math.max(3,Math.floor(pos.count/384)*3)){const v=new THREE.Vector3();for(let j=0;j<3;j++)v.add(new THREE.Vector3().fromBufferAttribute(pos,i+j));v.divideScalar(3);part.mesh.localToWorld(v);v.project(a.viewer.stage.camera);const x=r.left+(v.x+1)*r.width/2,y=r.top+(1-v.y)*r.height/2;if(x>8&&x<innerWidth-8&&y>70&&y<innerHeight-8&&document.elementFromPoint(x,y)===c)return{x,y};}return null;});
 assert.ok(target,'A real pan-base surface is unoccluded at phone touch coordinates');await tp.touchscreen.tap(target.x,target.y);assert.equal(await tp.evaluate(()=>window.__buildGuide.active.selected),'pan_base');assert.match(await tp.locator('[data-guide-selection]').innerText(),/Selected:/);
 await touchControl(tp.getByRole('button',{name:'Next →',exact:true}));const summary=tp.getByText('Parts in this step',{exact:true});await summary.scrollIntoViewIfNeeded();await summary.tap();await touchControl(tp.locator('[data-guide-parts] button').first());assert.equal(await tp.evaluate(()=>window.__buildGuide.active.selected),'pan_servo');
 assert.ok(await tp.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await tp.screenshot({path:`${out}/${engine.name()}-touch-phone.png`});await tc.close();cases.push('real hasTouch phone taps: previous/next, canvas picking and part list, unoccluded hitboxes');phase('touch-complete');
 }
 assert.deepEqual(errors,[]);await writeFile(`${out}/${engine.name()}-report.json`,JSON.stringify({status:'passed',provenance,cases,phases,errors},null,2));console.log(`PASS ${engine.name()}: ${cases.length} build guide groups`);
}catch(error){
 const pages=[];for(const c of contexts)for(const p of c.pages()){try{pages.push(await p.evaluate(()=>({url:location.href,status:document.querySelector('[data-guide-status]')?.textContent,step:window.__buildGuide?.active?.step,snapshot:window.__buildGuide?.active?.guide.snapshot.id})));await p.screenshot({path:`${out}/${engine.name()}-failure-${pages.length}.png`});}catch{}}
 await writeFile(`${out}/${engine.name()}-failed.json`,JSON.stringify({status:'failed',provenance,cases,phases,errors,pages,error:String(error)},null,2));throw error;
}finally{await Promise.all(contexts.map(c=>c.close()));await browser.close();}
