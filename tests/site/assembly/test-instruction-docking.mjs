/** Real desktop/right-dock and narrow sheet controls across native and denied fullscreen. */
import assert from 'node:assert/strict';
import {once} from 'node:events';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {createRequire} from 'node:module';
import {chromium,webkit} from '@playwright/test';
import {createSiteServer} from '../../../tools/site/serve-site.mjs';
import {captureScope,requireFreshCaptureRuntime,observeCaptureProtocol,observeScreenshot,readCaptureDiagnostic,watchCapturePage} from './capture-diagnostics.mjs';
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const scope=captureScope(process.env.DOCKING_CASE);
const out=process.env.TEST_OUTPUT||'/tmp/gyropup-instruction-docking-'+engine.name()+(scope==='all'?'':'-fresh-capture');
await mkdir(out,{recursive:true});
const server=createSiteServer(path.resolve(import.meta.dirname,'../../../dist'));
server.listen(0,'127.0.0.1');await once(server,'listening');
const base='http://127.0.0.1:'+server.address().port,observations=[],errors=[];
const sources=Object.fromEntries(await Promise.all(['tests/site/assembly/test-instruction-docking.mjs','tests/site/assembly/capture-diagnostics.mjs','tests/site/assembly/test-capture-diagnostics.mjs','software/site/designer/assembly/workspace.js','software/site/designer/assembly/guide.css','software/site/designer/build.html','software/site/designer/assembly/playback.js'].map(async file=>[file,createHash('sha256').update(await readFile(path.resolve(import.meta.dirname,'../../..',file))).digest('hex')])));
console.log('Owned docking listener',base);
let browser,page,builtVersion,captureProtocol;
const captureLifecycle=[];
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
async function selectDesktopPart(name='pan_servo'){
 const part=page.locator('[data-part='+JSON.stringify(name)+']');for(const ancestor of await part.locator('xpath=ancestor::details').all())if(!await ancestor.evaluate(e=>e.open))await ancestor.locator(':scope > summary').click();await part.click();
}
async function desktopSelection(label){
 await selectDesktopPart();await page.locator('[data-guide-isolate]').click();assert.equal(await page.evaluate(()=>window.__buildGuide.active.viewer.parts.filter(p=>p.mesh.visible).length),1,'Native isolate action leaves exactly one part');
 const dock=await page.evaluate(()=>{const rect=s=>{const r=document.querySelector(s).getBoundingClientRect();return{left:r.left,right:r.right,top:r.top,bottom:r.bottom};};return{popup:rect('[data-part-popup]'),parts:rect('#assembly-explorer')};});
 assert.ok(dock.popup.left>=dock.parts.left-1&&dock.popup.right<=dock.parts.right+1,JSON.stringify({label,dock}));
 await inspect(label+' isolated selection');
 const hit=await page.evaluate(()=>{const a=window.__buildGuide.active,part=a.viewer.parts.find(p=>p.name===a.selected),point=part.mesh.position.clone().set(0,0,0),positions=part.mesh.geometry.attributes.position;for(let i=0;i<3;i++)point.add(part.mesh.position.clone().fromBufferAttribute(positions,i));point.divideScalar(3);part.mesh.updateWorldMatrix(true,false);point.applyMatrix4(part.mesh.matrixWorld);a.viewer.stage.camera.updateMatrixWorld(true);point.project(a.viewer.stage.camera);const canvas=a.viewer.stage.renderer.domElement,r=canvas.getBoundingClientRect(),x=r.x+(point.x+1)*r.width/2,y=r.y+(1-point.y)*r.height/2;return{x,y,name:a.selected,canvas:document.elementFromPoint(x,y)===canvas};});
 assert.equal(hit.canvas,true,JSON.stringify({label,hit,dock}));await page.mouse.click(hit.x,hit.y);assert.equal(await page.evaluate(()=>window.__buildGuide.active.selected),hit.name);assert.equal(await page.locator('[data-part-popup]').isVisible(),true);assert.equal(await page.locator('[data-explorer-toggle]').getAttribute('aria-expanded'),'true');
 await page.screenshot({path:out+'/'+label.replaceAll(' ','-')+'-isolated-popup.png',timeout:15000});await page.locator('[data-guide-isolate]').click();assert.equal(await page.evaluate(()=>window.__buildGuide.active.isolate),false,'Native isolate action restores assembly');await page.locator('[data-part-close]').click();
}
async function trustedTap(selector,label){
 const button=page.locator(selector);await button.scrollIntoViewIfNeeded();const before=await button.boundingBox();assert.ok(before&&before.width>=44&&before.height>=44,label+' touch target');
 await page.evaluate(selector=>{window.actionTrace=[];window.actionTraceController=new AbortController();for(const type of ['pointerdown','pointerup','click'])document.addEventListener(type,event=>{const button=document.querySelector(selector),r=button.getBoundingClientRect();window.actionTrace.push({type,target:event.target===button,trusted:event.isTrusted,pointerType:event.pointerType||null,box:[r.x,r.y,r.width,r.height]});},{capture:true,signal:window.actionTraceController.signal});},selector);
 await button.tap();const trace=await page.evaluate(()=>{window.actionTraceController.abort();return window.actionTrace;});
 assert.ok(['pointerdown','pointerup','click'].every(type=>trace.some(event=>event.type===type&&event.target&&event.trusted)),JSON.stringify({label,trace}));assert.ok(trace.filter(event=>event.type!=='click').every(event=>event.pointerType==='touch'),JSON.stringify({label,trace}));
 for(const event of trace)for(const [index,key]of ['x','y','width','height'].entries())assert.ok(Math.abs(event.box[index]-before[key])<1,JSON.stringify({label,before,trace}));observations.push({label,trace,before});
}
async function selectNamedPart(name){
 await mobilePane('parts');const part=page.locator('[data-part='+JSON.stringify(name)+']');for(const ancestor of await part.locator('xpath=ancestor::details').all())if(!await ancestor.evaluate(e=>e.open))await ancestor.locator(':scope > summary').click();await part.tap();await page.locator('[data-part-popup]').waitFor({state:'visible'});
}
async function phoneFooterCases(){
 const phone=await browser.newContext({viewport:{width:320,height:700},hasTouch:true,isMobile:true,reducedMotion:'reduce'});await phone.addInitScript(()=>sessionStorage.setItem('gyropup.prototype-notice','2026-10-29-v1'));page=await phone.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/designer/build.html?assembly=robot#assembly',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>window.__buildGuide?.active?.guideAssembly==='robot'&&window.__buildGuide.active.viewer?.parts.length===171&&document.querySelector('#assembly').dataset.ready==='1',null,{timeout:60000});await page.evaluate(()=>document.fonts.ready);await fullscreen('native');
 for(const viewport of [{width:320,height:700},{width:844,height:390}]){
  await page.setViewportSize(viewport);await mobilePane('tools');const section=page.locator('[data-guide-section]');await section.focus();await page.keyboard.press('Home');await page.keyboard.press('ArrowRight');await page.keyboard.press('Tab');assert.equal(await page.locator('[data-guide-reset]').evaluate(e=>document.activeElement===e),true,'Tab reaches fixed Reset');await page.keyboard.press('Enter');assert.equal(await section.inputValue(),'1','Keyboard Reset restores section');
  await section.focus();await page.keyboard.press('Home');await page.keyboard.press('ArrowRight');await trustedTap('[data-guide-reset]',viewport.width+' actual touch Reset');assert.equal(await section.inputValue(),'1');
  await selectNamedPart('L.hip_frame');assert.equal(await page.locator('[data-part-print]').isVisible(),true,'Real source-matched hip exposes both standard actions');assert.ok(await page.locator('[data-part-downloads] button').count()>0,'Source original download remains in readable content');
  // Explicit UI-only long-label stress; real part identity and manufacturing metadata stay unchanged.
  const stress='[UI TEST] Very long selected-part name with an intentionally unbroken suffix '+ 'long_label_'.repeat(10);await page.locator('[data-part-details]>b').evaluate((e,text)=>e.textContent=text,stress);
  const footer=await page.locator('.assembly-part-actions').boundingBox();const body=await page.locator('.assembly-part-content').evaluate(e=>({height:e.clientHeight,width:e.clientWidth,scrollWidth:e.scrollWidth,scrollHeight:e.scrollHeight}));assert.ok(body.height>=44&&body.scrollHeight>body.height&&body.scrollWidth<=body.width,JSON.stringify({viewport,body}));
  await page.locator('[data-guide-part-mode]').focus();await page.keyboard.press('Tab');assert.equal(await page.locator('[data-guide-isolate]').evaluate(e=>document.activeElement===e),true,'Tab reaches Isolate');await page.keyboard.press('Tab');assert.equal(await page.locator('[data-part-print]').evaluate(e=>document.activeElement===e),true,'Tab reaches Prepare print');
  await page.locator('[data-part-details]>b').scrollIntoViewIfNeeded();assert.deepEqual(await page.locator('.assembly-part-actions').boundingBox(),footer,'Content scrolling preserves footer position');await page.screenshot({path:out+'/phone-actions-'+viewport.width+'.png',timeout:15000});
  await page.keyboard.press('Shift+Tab');await page.keyboard.press('Enter');assert.equal(await page.evaluate(()=>window.__buildGuide.active.isolate),true,'Keyboard Isolate activates');await page.keyboard.press('Enter');assert.equal(await page.evaluate(()=>window.__buildGuide.active.isolate),false,'Keyboard Isolate restores assembly');
  await trustedTap('[data-guide-isolate]',viewport.width+' actual touch Isolate');assert.equal(await page.evaluate(()=>window.__buildGuide.active.isolate),true);await trustedTap('[data-guide-isolate]',viewport.width+' actual touch restore');assert.equal(await page.evaluate(()=>window.__buildGuide.active.isolate),false);await trustedTap('[data-part-close]',viewport.width+' actual touch close');assert.equal(await page.locator('[data-part-popup]').isVisible(),false);
  if(viewport.width===844){await mobilePane('tools');await page.getByLabel('Section plane',{exact:true}).selectOption('z');await page.locator('[data-guide-section]').fill('0.4');await trustedTap('[data-guide-cut-flip]','844 actual touch Flip after closing hip details');assert.deepEqual(await page.evaluate(()=>window.__buildGuide.active.viewer.getSectionState()),{axis:'z',flipped:true,depth:.4});await trustedTap('[data-guide-cut-rotate]','844 actual touch Rotate');assert.deepEqual(await page.evaluate(()=>window.__buildGuide.active.viewer.getSectionState()),{axis:'x',flipped:true,depth:.4});const loop=await page.evaluate(()=>window.__buildGuide.active.player.getState().loop);await trustedTap('[data-guide-loop]','844 actual touch Loop');assert.equal(await page.evaluate(()=>window.__buildGuide.active.player.getState().loop),!loop);}
  observations.push({label:viewport.width+' long-label multi-action footer and keyboard navigation',syntheticLabelOnly:true,realPart:'L.hip_frame',body,footer});
 }
 // Observe native-fullscreen ownership before the existing phone-context teardown;
 // do not exit fullscreen, focus a page or change the compositor sequence.
 captureLifecycle.push({phase:'before phone context close',atMs:performance.now(),state:await readCaptureDiagnostic(()=>page.evaluate(()=>({documentId:performance.timeOrigin,visibility:document.visibilityState,hasFocus:document.hasFocus(),fullscreen:Boolean(document.fullscreenElement),viewport:{width:innerWidth,height:innerHeight}})))});
 await phone.close();captureLifecycle.push({phase:'phone context close completed',atMs:performance.now(),contexts:browser.contexts().length});
}
async function mouseControl(selector,label){
 const button=page.locator(selector);await button.scrollIntoViewIfNeeded();const before=await button.boundingBox();
 await page.evaluate(selector=>{window.controlTrace=[];window.controlTraceController=new AbortController();window.controlNodes={status:document.querySelector('[data-playback-status]').firstChild,loop:document.querySelector('[data-guide-loop]').firstChild,verb:document.querySelector('[data-guide-play] span').firstChild,icon:document.querySelector('[data-guide-play] svg path')};for(const type of ['pointerdown','pointerup','click'])document.addEventListener(type,event=>{const button=document.querySelector(selector),r=button.getBoundingClientRect(),a=window.__buildGuide.active;window.controlTrace.push({type,target:event.target===button,trusted:event.isTrusted,pointerType:event.pointerType||null,box:[r.x,r.y,r.width,r.height],scroll:document.querySelector('.assembly-tool-content').scrollTop,player:a.player.getState(),section:a.viewer.getSectionState()});},{capture:true,signal:window.controlTraceController.signal});},selector);
 await button.click();const result=await page.evaluate(()=>{window.controlTraceController.abort();const a=window.__buildGuide.active;const nodes=window.controlNodes,identity={status:nodes.status===document.querySelector('[data-playback-status]').firstChild,loop:nodes.loop===document.querySelector('[data-guide-loop]').firstChild,verb:nodes.verb===document.querySelector('[data-guide-play] span').firstChild,icon:nodes.icon===document.querySelector('[data-guide-play] svg path')};delete window.controlNodes;return{trace:window.controlTrace,player:a.player.getState(),section:a.viewer.getSectionState(),nodeIdentity:identity};});
 assert.ok(['pointerdown','pointerup','click'].every(type=>result.trace.some(event=>event.type===type&&event.target&&event.trusted)),JSON.stringify({label,result}));for(const event of result.trace)for(const [index,key]of ['x','y','width','height'].entries())assert.ok(Math.abs(event.box[index]-before[key])<=1,JSON.stringify({label,before,result}));observations.push({label,before,...result});return result;
}
async function playbackActivationCases(){
 const desktop=await browser.newContext({viewport:{width:1366,height:900},colorScheme:'dark',reducedMotion:'reduce'});await desktop.addInitScript(()=>sessionStorage.setItem('gyropup.prototype-notice','2026-10-29-v1'));page=await desktop.newPage();page.on('pageerror',e=>errors.push(e.message));
 const capturePage=await watchCapturePage(page);captureLifecycle.push({phase:'playback context created',atMs:performance.now(),contexts:browser.contexts().length});
 await page.goto(base+'/designer/build.html?assembly=robot#assembly',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>window.__buildGuide?.active?.guideAssembly==='robot'&&window.__buildGuide.active.viewer?.parts.length===171&&document.querySelector('#assembly').dataset.ready==='1',null,{timeout:60000});await page.evaluate(()=>document.fonts.ready);
 await clickState('[data-explorer-toggle]','aria-expanded',true);await clickState('[data-tools-toggle]','aria-expanded',true);await clickState('[data-instructions-toggle]','aria-expanded',true);await selectDesktopPart('L.hip_frame');await page.locator('[data-part-close]').click();
 assert.equal(await page.evaluate(()=>window.__buildGuide.active.player.getState().status),'idle');await page.getByLabel('Section plane',{exact:true}).selectOption('z');let result=await mouseControl('[data-guide-cut-flip]','stopped Robot Flip after closing hip details');assert.deepEqual(result.section,{axis:'z',flipped:true,depth:1});assert.equal(result.player.status,'idle');await page.locator('[data-guide-section]').fill('0.4');assert.deepEqual(await page.evaluate(()=>window.__buildGuide.active.viewer.getSectionState()),{axis:'z',flipped:true,depth:.4});
 result=await mouseControl('[data-guide-cut-rotate]','stopped Robot Rotate');assert.deepEqual(result.section,{axis:'x',flipped:true,depth:.4});let loop=result.player.loop;result=await mouseControl('[data-guide-loop]','stopped Robot Loop');assert.equal(result.player.loop,!loop);assert.equal(result.player.status,'idle');
 try{await observeScreenshot({capture:options=>page.screenshot(options),options:{path:out+'/robot-stopped-control-activation.png',timeout:15000},collect:()=>capturePage.snapshot(),protocol:captureProtocol,metadata:{label:'robot-stopped-control-activation',scope,engine:engine.name(),browser:browser.version(),version:builtVersion,sources,lifecycle:captureLifecycle,qualification:'Passive observation adds timing overhead; no render/focus/fullscreen/timeout changes or retry.'},writeReport:report=>writeFile(out+'/robot-stopped-capture-diagnostic.json',JSON.stringify(report,null,2)+'\n')});}finally{capturePage.dispose();}
 if(scope==='fresh-capture'){await desktop.close();return;}
 await page.emulateMedia({reducedMotion:'no-preference'});await page.waitForFunction(()=>!matchMedia('(prefers-reduced-motion: reduce)').matches&&!document.querySelector('[data-guide-play]').disabled);
 await page.locator('[data-guide-reset]').click();await page.locator('[data-guide-play]').click();await page.waitForFunction(()=>window.__buildGuide.active.player.getState().status==='playing'&&window.__buildGuide.active.player.getState().elapsedMs>100);await page.locator('[data-guide-play]').click();assert.equal(await page.evaluate(()=>window.__buildGuide.active.player.getState().status),'paused');
 await page.getByLabel('Section plane',{exact:true}).selectOption('z');await page.locator('[data-guide-section]').fill('0.4');result=await mouseControl('[data-guide-cut-flip]','already-paused Robot Flip');assert.deepEqual(result.section,{axis:'z',flipped:true,depth:.4});assert.equal(result.player.status,'paused');result=await mouseControl('[data-guide-cut-rotate]','already-paused Robot Rotate');assert.deepEqual(result.section,{axis:'x',flipped:true,depth:.4});loop=result.player.loop;result=await mouseControl('[data-guide-loop]','already-paused Robot Loop');assert.equal(result.player.loop,!loop);assert.equal(result.player.status,'paused');
 await page.getByLabel('Section plane',{exact:true}).selectOption('z');await mouseControl('[data-guide-cut-flip]','paused section preparation');await page.getByLabel('Assembly playback speed',{exact:true}).selectOption('2');let elapsed=await page.evaluate(()=>window.__buildGuide.active.player.getState().elapsedMs);await page.locator('[data-guide-play]').click();await page.waitForFunction(start=>window.__buildGuide.active.player.getState().status==='playing'&&window.__buildGuide.active.player.getState().elapsedMs>start+50,elapsed);assert.deepEqual(await page.evaluate(()=>window.__buildGuide.active.viewer.getSectionState()),{axis:'z',flipped:false,depth:.4});
 result=await mouseControl('[data-guide-cut-flip]','actively-playing Robot Flip pauses before action');assert.equal(result.trace.find(event=>event.type==='pointerdown').player.status,'playing');assert.equal(result.trace.find(event=>event.type==='pointerup').player.status,'paused');assert.equal(result.player.status,'paused');assert.equal(result.player.speed,2);assert.deepEqual(result.section,{axis:'z',flipped:true,depth:.4});elapsed=result.player.elapsedMs;await settle();assert.equal(await page.evaluate(()=>window.__buildGuide.active.player.getState().elapsedMs),elapsed);
 await page.locator('[data-guide-play]').click();await page.waitForFunction(start=>window.__buildGuide.active.player.getState().status==='playing'&&window.__buildGuide.active.player.getState().elapsedMs>start+50,elapsed);loop=await page.evaluate(()=>window.__buildGuide.active.player.getState().loop);result=await mouseControl('[data-guide-loop]','actively-playing Robot Loop keeps playback running');assert.equal(result.player.status,'playing');assert.equal(result.player.loop,!loop);assert.deepEqual(result.section,{axis:'z',flipped:true,depth:.4});result=await mouseControl('[data-guide-cut-rotate]','actively-playing Robot Rotate pauses before action');assert.equal(result.trace.find(event=>event.type==='pointerdown').player.status,'playing');assert.equal(result.trace.find(event=>event.type==='pointerup').player.status,'paused');assert.equal(result.player.status,'paused');assert.equal(result.player.speed,2);assert.equal(result.player.loop,!loop);assert.deepEqual(result.section,{axis:'x',flipped:true,depth:.4});elapsed=result.player.elapsedMs;await settle();assert.equal(await page.evaluate(()=>window.__buildGuide.active.player.getState().elapsedMs),elapsed);
 await desktop.close();
}
async function fullscreen(mode){
 if(mode==='denied')await page.evaluate(()=>document.querySelector('.assembly-layout').requestFullscreen=()=>Promise.reject(new DOMException('Intentional denial','NotAllowedError')));
 await page.locator('[data-guide-fullscreen]').click();
 await page.waitForFunction(({mode,nativeRequired})=>{const l=document.querySelector('.assembly-layout');return mode==='denied'?l.dataset.fullscreen==='expanded':nativeRequired?document.fullscreenElement===l&&l.dataset.fullscreen==='native':['native','expanded'].includes(l.dataset.fullscreen);},{mode,nativeRequired:engine===chromium});
}
try{
 const require=createRequire(import.meta.url);assert.equal(require('playwright-core/package.json').version,'1.56.1','Review pinned screenshot internals before upgrading the diagnostic observer');
 const Connection=engine===chromium?require(path.join(path.dirname(require.resolve('playwright-core/package.json')),'lib/server/chromium/crConnection.js')).CRConnection:null;
 captureProtocol=observeCaptureProtocol(Connection);
 if(scope==='fresh-capture'){assert.equal(engine,chromium,'Fresh control uses Chromium only');assert.equal(process.env.PLAYWRIGHT_CHANNEL,'chromium','Fresh control cannot substitute native Chrome');}
 browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
 if(scope==='fresh-capture'){
  requireFreshCaptureRuntime({engine:engine.name(),channel:process.env.PLAYWRIGHT_CHANNEL,version:browser.version()});assert.equal(browser.contexts().length,0,'Fresh control starts before any browser context or WebGL scene');
  builtVersion=await(await fetch(base+'/version.json')).json();captureLifecycle.push({phase:'fresh browser before Robot context',atMs:performance.now(),contexts:0});
  await playbackActivationCases();assert.deepEqual(errors,[]);assert.equal(observations.length,3,'Exactly the original stopped Flip/Rotate/Loop observations');
  await writeFile(out+'/report.json',JSON.stringify({status:'passed',scope,completeCampaign:false,qualification:'Fresh pinned-browser control only; not the full132-state campaign or a root-cause result.',engine:engine.name(),browser:browser.version(),version:builtVersion,sources,observations,errors},null,2)+'\n');console.log('PASS fresh-capture diagnostic only; full campaign not run by this separate control');
 }else{
 const context=await browser.newContext({viewport:{width:1440,height:1000},hasTouch:true,isMobile:true,reducedMotion:'reduce'});
 await context.addInitScript(()=>sessionStorage.setItem('gyropup.prototype-notice','2026-10-29-v1'));
 page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 const version=await(await context.request.get(base+'/version.json')).json();
 builtVersion=version;
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
   await page.screenshot({path:`${out}/${mode}-${width}-expanded-panels.png`,timeout:15000});await desktopSelection(mode+' '+width);
  }
  // Resize the same active fullscreen document across the real desktop/mobile boundary.
  for(const viewport of [{width:1280,height:900},{width:844,height:390},{width:720,height:390},{width:390,height:844},{width:320,height:700}]){
   await page.setViewportSize(viewport);await settle();
   const expectedCompact=viewport.width<=760||viewport.width<=1000&&viewport.height<=500;assert.equal(await page.locator('.assembly-layout').getAttribute('data-mobile'),String(expectedCompact),'Phone pointer/height breakpoint');
   if(!expectedCompact){await inspect(`${mode} resize ${viewport.width}x${viewport.height}`);}
   else{
    assert.equal(await page.evaluate(()=>matchMedia('(pointer:coarse)').matches),true,'Actual coarse pointer mobile context');
    for(const pane of ['instructions','parts','tools']){await mobilePane(pane);await inspect(`${mode} ${viewport.width} ${pane}`);}
    if(viewport.width>=600){await mobilePane('parts');const part=page.locator('[data-part=pan_servo]');for(const ancestor of await part.locator('xpath=ancestor::details').all())if(!await ancestor.evaluate(e=>e.open))await ancestor.locator(':scope > summary').click();await part.click();const popup=page.locator('[data-part-popup]');await popup.waitFor({state:'visible'});assert.equal(await popup.evaluate(e=>{const r=e.getBoundingClientRect(),tabs=document.querySelector('.assembly-sheet-tabs').getBoundingClientRect(),sheet=document.querySelector('.assembly-panels').getBoundingClientRect();return Math.abs(r.left-sheet.left)<2&&Math.abs(r.right-sheet.right)<2&&r.top>=tabs.bottom&&r.bottom<=sheet.bottom;}),true,'Selected part stays beside model below compact tabs');await page.locator('[data-guide-isolate]').tap();assert.equal(await page.evaluate(()=>window.__buildGuide.active.isolate),true,'Actual touch isolates selected part');await page.locator('[data-guide-isolate]').tap();assert.equal(await page.evaluate(()=>window.__buildGuide.active.isolate),false,'Actual touch restores assembly');await page.locator('[data-part-close]').tap();}
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
 await phoneFooterCases();await playbackActivationCases();assert.deepEqual(errors,[]);await writeFile(out+'/report.json',JSON.stringify({status:'passed',engine:engine.name(),browser:browser.version(),version,sources,observations,errors},null,2)+'\n');console.log('PASS',engine.name(),observations.length,'actual docking/control states');
 }
}catch(error){await writeFile(out+'/failed.json',JSON.stringify({status:'failed',scope,completeCampaign:false,sources,observations,errors,error:error.stack},null,2));try{await page?.screenshot({path:out+'/failure.png',timeout:15000});}catch{}throw error;}
finally{captureProtocol?.dispose();await browser?.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));console.log('Owned docking listener closed');}
