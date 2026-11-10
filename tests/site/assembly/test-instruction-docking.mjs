/** Real desktop/right-dock and narrow sheet controls across native and denied fullscreen. */
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {chromium,webkit} from '@playwright/test';
import {createSiteServer} from '../../../tools/site/serve-site.mjs';
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const out=process.env.TEST_OUTPUT||'/tmp/gyropup-instruction-docking-'+engine.name();
await mkdir(out,{recursive:true});
const server=createSiteServer(path.resolve(import.meta.dirname,'../../../dist'));
server.listen(0,'127.0.0.1');await once(server,'listening');
const base='http://127.0.0.1:'+server.address().port,observations=[],errors=[];
const sources=Object.fromEntries(await Promise.all(['tests/site/assembly/test-instruction-docking.mjs','software/site/designer/assembly/workspace.js','software/site/designer/assembly/guide.css'].map(async file=>[file,createHash('sha256').update(await readFile(path.resolve(import.meta.dirname,'../../..',file))).digest('hex')])));
console.log('Owned docking listener',base);
let browser,page;
const settle=()=>page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
async function clickState(selector,attribute,value){if(await page.locator(selector).getAttribute(attribute)!==String(value))await page.locator(selector).click();}
async function inspect(label){
 // Ordinary short windows scroll through the page; native/fallback fullscreen must fit as one viewport.
 await page.evaluate(()=>{const layout=document.querySelector('.assembly-layout');if(!document.fullscreenElement&&layout.dataset.expanded!=='true'){const nav=document.querySelector('.appnav')?.getBoundingClientRect();window.scrollTo({top:layout.getBoundingClientRect().top+scrollY-(nav?.height||64)-8,behavior:'instant'});}});
 await settle();
 const data=await page.evaluate(()=>{
  const layout=document.querySelector('.assembly-layout'),rect=e=>{const r=e.getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height,right:r.right,bottom:r.bottom};};
  const visible=s=>[...document.querySelectorAll(s)].filter(e=>!e.hidden&&e.getClientRects().length);
  const controls=visible('.assembly-topbar button,.assembly-nav button,.assembly-nav select,.assembly-progress,.assembly-sheet-tabs button,.assembly-instruction-heading button').filter(e=>!e.disabled).map(e=>{const r=rect(e),hit=document.elementFromPoint(r.x+r.w/2,r.y+r.h/2);return{label:e.getAttribute('aria-label')||e.textContent.trim(),...r,hit:e===hit||e.contains(hit),inViewport:r.y>=0&&r.bottom<=innerHeight};});
  const panels=Object.fromEntries(visible('.assembly-step,#assembly-tools,#assembly-explorer').map(e=>[e.classList.contains('assembly-step')?'instructions':e.id,rect(e)]));
  const v=window.__buildGuide.active.viewer,modelBox={left:Infinity,right:-Infinity,top:Infinity,bottom:-Infinity},c=v.stage.renderer.domElement,r=rect(c),overlays=visible('.assembly-topbar,.assembly-nav,.assembly-step,#assembly-tools,#assembly-explorer').map(rect);let vertices=0,unoccluded=true;
  v.stage.root.updateMatrixWorld(true);v.stage.camera.updateMatrixWorld(true);
  for(const part of v.parts.filter(p=>p.mesh.visible)){const positions=part.mesh.geometry.attributes.position;for(let i=0;i<positions.count;i+=Math.max(1,Math.floor(positions.count/60))){const q=part.mesh.position.clone().fromBufferAttribute(positions,i).applyMatrix4(part.mesh.matrixWorld).project(v.stage.camera),x=r.x+(q.x+1)*r.w/2,y=r.y+(1-q.y)*r.h/2;vertices++;modelBox.left=Math.min(modelBox.left,x);modelBox.right=Math.max(modelBox.right,x);modelBox.top=Math.min(modelBox.top,y);modelBox.bottom=Math.max(modelBox.bottom,y);if(![x,y,q.z].every(Number.isFinite)||x<r.x||x>r.right||y<r.y||y>r.bottom||Math.abs(q.z)>1||overlays.some(o=>x>o.x&&x<o.right&&y>o.y&&y<o.bottom))unoccluded=false;}}
  const bounds=rect(layout),navigation=rect(document.querySelector('.assembly-nav')),left=layout.dataset.mobile==='false'&&panels['assembly-explorer']?panels['assembly-explorer'].right-bounds.x+12:16,top=navigation.bottom-bounds.y+12,projectionOffset=v.stage.camera.view,insets={left,right:left+2*(projectionOffset?.offsetX||0),top,bottom:top+2*(projectionOffset?.offsetY||0)};
  return{mobile:layout.dataset.mobile,sheetLayout:layout.dataset.sheetLayout,sheet:rect(document.querySelector('.assembly-panels')),insets,projectionOffset,modelBox:{...modelBox,w:modelBox.right-modelBox.left,h:modelBox.bottom-modelBox.top},pointerCoarse:matchMedia('(pointer:coarse)').matches,mode:layout.dataset.fullscreen||'none',expanded:layout.dataset.instructions,workspace:rect(layout),navigation:rect(document.querySelector('.assembly-nav')),panels,controls,vertices,unoccluded,shortWindow:!document.fullscreenElement&&layout.dataset.expanded!=='true'&&innerHeight<500,horizontalOverflow:document.documentElement.scrollWidth>innerWidth+1};
 });
 observations.push({label,...data});assert.ok(data.controls.every(c=>c.w>=44&&c.h>=44&&(c.hit||data.mobile==='true'&&data.shortWindow&&!c.inViewport)),JSON.stringify({label,controls:data.controls}));assert.equal(data.horizontalOverflow,false,label);assert.ok(data.vertices>0&&data.unoccluded,JSON.stringify({label,vertices:data.vertices,unoccluded:data.unoccluded}));
 if(data.mobile==='false'){
  const i=data.panels.instructions,t=data.panels['assembly-tools'],p=data.panels['assembly-explorer'];
  assert.ok(i,label+' keeps instructions visible');assert.ok(Math.abs(i.y-data.navigation.bottom-12)<2,label+' starts below navigation');assert.ok(Math.abs(i.right-(t?t.x-12:data.workspace.right-16))<2,label+' docks beside Tools or at right edge');
  assert.ok(i.w>=240&&i.h>=44,label+' readable instruction panel');
  if(p){assert.ok(p.right<=i.x,label+' Parts do not overlap instructions');if(data.workspace.w>=950)assert.ok(i.x-p.right-24>=320,label+' retains useful model width');}
  for(const panel of Object.values(data.panels))assert.ok(panel.y>=data.navigation.bottom+10,label+' panel cannot cover toolbar/navigation');
 }else assert.equal(Object.keys(data.panels).length,data.controls.some(c=>c.label==='Expand panel')&&await page.locator('.assembly-layout').getAttribute('data-sheet-size')==='collapsed'?0:1,label+' one compact mobile pane');
 if(data.mobile==='true'&&data.sheetLayout==='side'){assert.ok(Math.abs(data.insets.right-(data.workspace.right-data.sheet.x+12))<2,label+' actual camera inset follows the pane width');assert.ok(data.sheet.x>=data.workspace.x+300,label+' leaves a useful model lane');assert.ok(data.workspace.h-data.insets.top-data.insets.bottom>=210,label+' leaves useful model height');assert.ok(data.modelBox.h>=150&&data.modelBox.w>=120,JSON.stringify({label,modelBox:data.modelBox}));}
 return data;
}
async function mobilePane(pane){
 const tab=page.locator(`[data-sheet-tab=${pane}]`);await tab.scrollIntoViewIfNeeded();
 assert.equal(await tab.evaluate(e=>{const r=e.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return e===hit||e.contains(hit);}),true,'Actual mobile '+pane+' tab hit target');await tab.click();
}
async function fullscreen(mode){
 if(mode==='denied')await page.evaluate(()=>document.querySelector('.assembly-layout').requestFullscreen=()=>Promise.reject(new DOMException('Intentional denial','NotAllowedError')));
 await page.locator('[data-guide-fullscreen]').click();
 await page.waitForFunction(({mode,nativeRequired})=>{const l=document.querySelector('.assembly-layout');return mode==='denied'?l.dataset.fullscreen==='expanded':nativeRequired?document.fullscreenElement===l&&l.dataset.fullscreen==='native':['native','expanded'].includes(l.dataset.fullscreen);},{mode,nativeRequired:engine===chromium});
}
try{
 browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000},hasTouch:true,isMobile:true,reducedMotion:'reduce'});
 await context.addInitScript(()=>sessionStorage.setItem('gyropup.prototype-notice','2026-10-29-v1'));
 page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 const version=await(await context.request.get(base+'/version.json')).json();
 await page.goto(base+'/designer/build.html?assembly=turret&step=step-02#assembly',{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>window.__buildGuide?.active?.viewer?.parts.some(p=>p.mesh.visible)&&document.querySelector('#assembly').dataset.ready==='1');await page.evaluate(()=>document.fonts.ready);
 for(const mode of ['windowed','native','denied']){
  console.log('PHASE docking-'+mode);if(mode!=='windowed')await fullscreen(mode);
  for(const width of [1440,1024]){
   await page.setViewportSize({width,height:1000});const compactDocks=new Map();
   for(const expanded of [false,true])for(const parts of [false,true])for(const tools of [false,true]){
    await clickState('[data-instructions-toggle]','aria-expanded',expanded);await clickState('[data-explorer-toggle]','aria-expanded',parts);await clickState('[data-tools-toggle]','aria-expanded',tools);
    const state=await inspect(`${mode} ${width} expanded=${expanded} Parts=${parts} Tools=${tools}`);
    assert.equal(Boolean(state.panels['assembly-explorer']),parts,'Parts visibility follows its own control');assert.equal(Boolean(state.panels['assembly-tools']),tools,'Tools visibility follows its own control');
    const instruction=state.panels.instructions,key=parts+':'+tools;if(!expanded)compactDocks.set(key,instruction);else{const compact=compactDocks.get(key);assert.equal(instruction.x,compact.x,'Expanding preserves horizontal dock');assert.equal(instruction.w,compact.w,'Expanding preserves dock width');assert.ok(instruction.h>=compact.h,'Expansion adds vertical reading space');}
   }
   await page.screenshot({path:`${out}/${mode}-${width}-expanded-panels.png`,timeout:15000});
  }
  // Resize the same active fullscreen document across the real desktop/mobile boundary.
  for(const viewport of [{width:1280,height:900},{width:844,height:390},{width:720,height:390},{width:390,height:844},{width:320,height:700}]){
   await page.setViewportSize(viewport);await settle();
   const expectedCompact=viewport.width<=760||viewport.width<=1000&&viewport.height<=500;assert.equal(await page.locator('.assembly-layout').getAttribute('data-mobile'),String(expectedCompact),'Phone pointer/height breakpoint');
   if(!expectedCompact){await inspect(`${mode} resize ${viewport.width}x${viewport.height}`);}
   else{
    assert.equal(await page.evaluate(()=>matchMedia('(pointer:coarse)').matches),true,'Actual coarse pointer mobile context');
    for(const pane of ['instructions','parts','tools']){await mobilePane(pane);await inspect(`${mode} ${viewport.width} ${pane}`);}
    if(viewport.width>=600){await mobilePane('parts');const part=page.locator('[data-part=pan_servo]');for(const ancestor of await part.locator('xpath=ancestor::details').all())if(!await ancestor.evaluate(e=>e.open))await ancestor.locator(':scope > summary').click();await part.click();const popup=page.locator('[data-part-popup]');await popup.waitFor({state:'visible'});assert.equal(await popup.evaluate(e=>{const r=e.getBoundingClientRect(),tabs=document.querySelector('.assembly-sheet-tabs').getBoundingClientRect(),sheet=document.querySelector('.assembly-panels').getBoundingClientRect();return Math.abs(r.left-sheet.left)<2&&Math.abs(r.right-sheet.right)<2&&r.top>=tabs.bottom&&r.bottom<=sheet.bottom;}),true,'Selected part stays beside model below compact tabs');await page.locator('[data-part-close]').click();}
    await page.locator('[data-sheet-tab=instructions]').click();await page.locator('[data-sheet-resize]').click();await inspect(`${mode} ${viewport.width} expanded mobile instructions`);await page.locator('[data-sheet-resize]').click();
    await page.screenshot({path:`${out}/${mode}-${viewport.width}-mobile.png`,timeout:15000});
   }
  }
  await page.setViewportSize({width:1440,height:1000});await inspect(mode+' desktop restored after resize');
  if(mode!=='windowed'){await page.locator('[data-guide-fullscreen]').click();await page.waitForFunction(()=>document.querySelector('[data-guide-fullscreen]').getAttribute('aria-pressed')==='false');}
 }
 await context.close();
 const fine=await browser.newContext({viewport:{width:844,height:390},hasTouch:false,isMobile:false,reducedMotion:'reduce'});await fine.addInitScript(()=>sessionStorage.setItem('gyropup.prototype-notice','2026-10-29-v1'));page=await fine.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(base+'/designer/build.html?assembly=turret&step=step-02#assembly',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>window.__buildGuide?.active?.viewer?.parts.some(p=>p.mesh.visible)&&document.querySelector('#assembly').dataset.ready==='1');await page.evaluate(()=>document.fonts.ready);await fullscreen('native');
 await clickState('[data-instructions-toggle]','aria-expanded',true);await clickState('[data-explorer-toggle]','aria-expanded',true);await clickState('[data-tools-toggle]','aria-expanded',true);const desktop=await inspect('fine-pointer 844x390 native desktop control');assert.equal(desktop.pointerCoarse,false);assert.equal(desktop.mobile,'false');assert.equal(Object.keys(desktop.panels).length,3);await page.screenshot({path:out+'/fine-pointer-844-desktop.png',timeout:15000});await fine.close();
 assert.deepEqual(errors,[]);await writeFile(out+'/report.json',JSON.stringify({status:'passed',engine:engine.name(),browser:browser.version(),version,sources,observations,errors},null,2)+'\n');console.log('PASS',engine.name(),observations.length,'actual docking/control states');
}catch(error){await writeFile(out+'/failed.json',JSON.stringify({status:'failed',sources,observations,errors,error:error.stack},null,2));try{await page?.screenshot({path:out+'/failure.png',timeout:15000});}catch{}throw error;}
finally{await browser?.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));console.log('Owned docking listener closed');}
