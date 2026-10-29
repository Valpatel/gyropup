/** Product integration: real tables, original downloads, and browser-local part state. */
import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {parseHTML} from 'linkedom';
import {chromium,webkit} from '@playwright/test';
const base=(process.env.SITE_URL||'http://127.0.0.1:8893').replace(/\/$/,'');
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const out=process.env.TEST_OUTPUT||'/tmp/gyropup-build-portal';await mkdir(out,{recursive:true});
const browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
const context=await browser.newContext({viewport:{width:1280,height:900}});await context.addInitScript(()=>sessionStorage.setItem('gyropup.prototype-notice','2026-10-29-v1'));
const page=await context.newPage(),errors=[];page.setDefaultTimeout(60000);page.on('pageerror',error=>errors.push(error.message));
const ready=()=>page.waitForFunction(()=>document.body.dataset.ready==='1');
const checkModelActions=async()=>{
 await page.locator('[data-model-preview]').first().waitFor({state:'attached'});
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 const rows=await page.locator('tr').evaluateAll(rows=>rows.map(row=>{
  const originals=[...row.querySelectorAll('a[data-model-original]')],previews=[...row.querySelectorAll('a[data-model-preview]')];
  return {key:row.dataset.partKey||row.textContent.trim().slice(0,40),
   files:[...new Set(originals.map(a=>new URL(a.href,location.href).pathname))].sort(),
   previews:previews.map(a=>new URL(a.href,location.href).searchParams.get('file')).sort(),
   downloads:originals.every(a=>a.hasAttribute('download')),
   identityVisible:!row.querySelector('.cad-part-identity')||previews.every(a=>a.parentElement===row.querySelector('.cad-part-identity'))};
 }).filter(row=>row.files.length));
 assert.ok(rows.length>0,'Real BOM contains downloadable models');
 for(const row of rows){assert.deepEqual(row.previews,row.files,row.key+' has exactly one preview per model');assert.equal(row.downloads,true,row.key);assert.equal(row.identityVisible,true,row.key+' keeps preview with part identity');}
};
const exported=async()=>{const download=page.waitForEvent('download');await page.getByRole('button',{name:'Export progress',exact:true}).click();return JSON.parse(await readFile(await(await download).path(),'utf8'));};
const checkNativeSort=async(table,column,direction)=>{
 const before=await table.locator('tbody tr:not([data-fixed])').evaluateAll(rows=>rows.map(row=>row.dataset.partKey||row.textContent));
 const header=table.locator('thead th').nth(column),button=header.locator('button');
 await button.click();if(direction==='descending')await button.click();
 assert.equal(await header.getAttribute('aria-sort'),direction);
 const values=await table.locator('tbody tr:not([data-fixed])').evaluateAll((rows,index)=>rows.map(row=>row.cells[index].dataset.sortValue??''),column);
 const known=values.filter(value=>value!=='').map(Number);assert.ok(known.length>1);
 assert.deepEqual(known,[...known].sort((a,b)=>direction==='ascending'?a-b:b-a));
 const firstUnknown=values.indexOf('');if(firstUnknown>=0)assert.ok(values.slice(firstUnknown).every(value=>value===''));
 const after=await table.locator('tbody tr:not([data-fixed])').evaluateAll(rows=>rows.map(row=>row.dataset.partKey||row.textContent));assert.deepEqual([...before].sort(),[...after].sort());
};
try{
 const version=await(await context.request.get(base+'/version.json')).json();
 const wasm=await context.request.get(base+'/designer/kit/vendor/occt-import-js/occt-import-js.wasm',{method:'HEAD'});assert.equal(wasm.status(),200);assert.match(wasm.headers()['content-type'],/^application\/wasm/);
 await page.goto(base+'/designer/progress.html');await ready();await checkModelActions();
 const progressKeys=await page.locator('tr[data-part-key^="buy/"]').evaluateAll(rows=>rows.map(row=>row.dataset.partKey));
 assert.ok(progressKeys.length>20);assert.equal(await page.locator('table:not(.cad-part-table)').count(),0);
 await page.goto(base+'/designer/build.html');await ready();await checkModelActions();
 assert.equal(await page.locator('table:not(.cad-part-table)').count(),0);
 assert.equal(await page.getByRole('button',{name:/^Picture: sort/}).count(),0,'Picture-only columns have no meaningless sort control');
 const summaries=await page.evaluate(()=>({total:+document.querySelector('#sum-total').dataset.usd,sellers:[...document.querySelectorAll('#sellertable tbody tr[data-seller]')].reduce((sum,row)=>sum+ +row.dataset.usd,0),made:+document.querySelector('#sum-made').dataset.usd,hours:+document.querySelector('#sum-hours').dataset.h}));
 assert.ok(Math.abs(summaries.total-summaries.sellers)<.01);assert.ok(summaries.made>0&&summaries.hours>0);
 const shared=await page.locator('#orders tr[data-part-key]').evaluateAll((rows,keys)=>rows.find(row=>keys.includes(row.dataset.partKey)&&row.closest('table').tBodies[0].rows.length>2)?.dataset.partKey,progressKeys);assert.ok(shared,'Build and Progress share catalog part identities');

 const target=page.locator('#orders tr[data-part-key='+JSON.stringify(shared)+']');
 const seller=target.locator('xpath=ancestor::details[contains(@class,"seller")]');await seller.locator(':scope > summary').click();
 const table=seller.locator('table');await checkNativeSort(table,4,'ascending');
 await target.locator('input[type=checkbox]').first().check();
 const label=await target.getAttribute('data-part-label');
 const search=seller.getByRole('searchbox');await search.fill(label);assert.equal(await target.isVisible(),true);assert.equal(await target.locator('input').first().isChecked(),true);await search.fill('');
 const body=page.locator('[data-stream=body]');await body.uncheck();await body.check();await checkModelActions();
 const reopened=target.locator('xpath=ancestor::details[contains(@class,"seller")]');await reopened.locator(':scope > summary').click();assert.equal(await target.locator('input').first().isChecked(),true);
 assert.equal(await page.locator('#orders .cad-table-tools').count(),await page.locator('#orders table').count(),'Rerender disposes old toolbars');
 await page.reload();await ready();await target.locator('xpath=ancestor::details[contains(@class,"seller")]').locator(':scope > summary').click();assert.equal(await target.locator('input').first().isChecked(),true);
 const saved=await exported();assert.equal(saved.project,'gyropup');assert.equal(saved.parts[shared].ordered,true);
 const input=page.locator('.cad-progress-tools input[type=file]');
 await input.setInputFiles({name:'invalid.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({version:1,project:'gyropup',parts:{[shared]:{ordered:false},broken:{ordered:'yes'}}}))});
 await page.waitForFunction(()=>document.querySelector('.cad-progress-receipt').textContent.includes('unsupported status'));assert.deepEqual(await exported(),saved,'Invalid imports are atomic');
 await input.setInputFiles({name:'valid.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({version:1,project:'gyropup',parts:{[shared]:{inHand:true}}}))});
 await page.waitForFunction(()=>document.querySelector('.cad-progress-receipt').textContent.includes('Imported'));assert.equal(await target.locator('input').nth(1).isChecked(),true);
 await page.goto(base+'/designer/progress.html');await ready();const other=page.locator('tr[data-part-key='+JSON.stringify(shared)+']').first();assert.equal(await other.locator('input').first().isChecked(),true);assert.equal(await other.locator('input').nth(1).isChecked(),true);
 const parts=page.locator('#buy table').first();await parts.locator('thead th').nth(1).locator('button').click();
 const names=await parts.locator('tbody tr').evaluateAll(rows=>rows.map(row=>row.cells[1].textContent.trim()));assert.deepEqual(names,[...names].sort(new Intl.Collator(undefined,{numeric:true,sensitivity:'base'}).compare));
 const prints=page.locator('#print table');await checkNativeSort(prints,7,'ascending');await prints.locator('tbody input[type=checkbox]').first().check();
 const printedKey=await prints.locator('tbody tr').first().getAttribute('data-part-key');await page.reload();await ready();assert.equal(await page.locator('tr[data-part-key='+JSON.stringify(printedKey)+'] input').first().isChecked(),true);
 const inventory=await(await context.request.get(base+'/site/models.json')).json();assert.equal(inventory.files.length,495);assert.deepEqual(inventory.files.reduce((counts,f)=>(counts[f.format]=(counts[f.format]||0)+1,counts),{}),{step:188,stl:288,'3mf':19});
 // Every published original has its own adjacent directory preview and unchanged download.
 const directories=new Map();for(const file of inventory.files){const dir=file.path.slice(0,file.path.lastIndexOf('/')+1);if(!directories.has(dir))directories.set(dir,[]);directories.get(dir).push(file);}
 for(const [dir,files] of directories){const response=await context.request.get(base+dir);assert.equal(response.status(),200);const {document}=parseHTML(await response.text());for(const file of files){const name=file.path.split('/').pop(),original=[...document.querySelectorAll('a[data-model-original]')].find(a=>decodeURIComponent(new URL(a.getAttribute('href'),base+dir).pathname)===file.path);assert.ok(original,file.path+' original');const preview=original.nextElementSibling;assert.ok(preview.hasAttribute('data-model-preview'),file.path+' preview');assert.equal(new URL(preview.getAttribute('href'),base).searchParams.get('file'),file.path);assert.ok(original.hasAttribute('download'));}}
 await page.goto(base+'/designer/build.html');await ready();
 const media=await(await context.request.get(base+'/catalog/images.json')).json();
 const shown=await page.locator('#made tr[data-part-key],#queue tr[data-part-key^="print/body/"]').evaluateAll(rows=>rows.map(row=>({key:row.dataset.partKey.replace(/^(made|print)\//,''),src:row.querySelector('img')?.getAttribute('src')})));
 assert.equal(shown.length,26);for(const row of shown)assert.equal(new URL(row.src,base+'/designer/build.html').pathname,'/'+media[row.key].path,row.key);
 for(const key of ['pa6-cf','petg','tpu95','tpu95-gyroid']){const img=page.locator('#orders tr[data-part-key="material/'+key+'"] img');if(await img.count())assert.equal(await img.getAttribute('src'),media[key].image_url,key);}
 await page.route(url=>url.href===media.petg.image_url,route=>route.abort('failed'));
 const filament=page.locator('#orders tr[data-part-key="material/petg"]');await filament.locator('xpath=ancestor::details[contains(@class,"seller")]').locator(':scope > summary').click();
 await filament.locator('.thumb').scrollIntoViewIfNeeded();await filament.locator('.thumb.source').waitFor();assert.equal(await filament.locator('.thumb.source').getAttribute('href'),media.petg.source_url,'Unavailable remote photos retain their source link');
 const modelLink=page.locator('#made a[data-model-preview]').first();await modelLink.waitFor();assert.ok((await modelLink.getAttribute('href')).includes('file-viewer.html?'));
 for(const [width,height] of [[320,568],[568,320],[390,844],[844,390]]){await page.setViewportSize({width,height});await page.evaluate(()=>window.scrollTo(0,document.querySelector('#made').getBoundingClientRect().top+scrollY-70));const layout=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,controls:[...document.querySelectorAll('#made .cad-table-tools input,#made .cad-table-tools select')].map(el=>({width:el.getBoundingClientRect().width,height:el.getBoundingClientRect().height}))}));assert.ok(layout.scroll<=width+1,JSON.stringify(layout));assert.ok(layout.controls.every(r=>r.height>=44&&r.width<=width),JSON.stringify(layout));await page.screenshot({path:`${out}/${engine.name()}-${width}x${height}.png`});}
 await page.setViewportSize({width:320,height:568});await page.evaluate(()=>{const host=document.querySelector('#made'),scroll=host.querySelector('.cad-table-scroll');scroll.scrollLeft=scroll.scrollWidth;window.scrollTo(0,host.getBoundingClientRect().top+scrollY-70);});
 const sticky=await page.locator('#made tbody tr').first().evaluate(row=>{const cell=row.querySelector('.cad-part-identity'),r=cell.getBoundingClientRect(),checks=[...row.querySelectorAll('.cad-status-check')].map(label=>{const r=label.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {x:r.x,right:r.right,height:r.height,width:r.width,reachable:label===hit||label.contains(hit)};});return {text:(cell.querySelector('b')||cell).innerText.trim(),x:r.x,right:r.right,checks};});assert.ok(sticky.text&&sticky.x>=0&&sticky.right<=160,JSON.stringify(sticky));assert.ok(sticky.checks.every(r=>r.height>=44&&r.width>=44&&r.x>=sticky.right-1&&r.right<=320&&r.reachable),JSON.stringify(sticky));await page.screenshot({path:`${out}/${engine.name()}-status-320.png`});
 // Follow real portal preview links, then verify original parsers and native camera controls.
 await page.setViewportSize({width:1280,height:900});
 for(const file of ['/exports/body/post.stl','/exports/leg/cnc/output_adapter.step','/exports/turret/print/barrel.3mf']) {
  const dir=file.slice(0,file.lastIndexOf('/')+1);await page.goto(base+dir);
  const link=page.locator('a[data-model-preview]').filter({hasText:'Preview 3D'});
  const wanted=await link.evaluateAll((links,file)=>links.find(link=>new URL(link.href).searchParams.get('file')===file)?.getAttribute('href'),file);assert.ok(wanted);
  await page.locator('a[data-model-preview][href='+JSON.stringify(wanted)+']').click();
  await page.waitForFunction(()=>window.__fileViewer?.root.dataset.state==='ready',null,{timeout:120000});
  const geometry=await page.evaluate(()=>({triangles:window.__fileViewer.info.triangles,dimensions:window.__fileViewer.info.boundsMm,canvases:document.querySelectorAll('canvas').length}));assert.ok(geometry.triangles>0);assert.ok(geometry.dimensions.every(Number.isFinite));assert.equal(geometry.canvases,1);
  assert.equal(new URL(await page.getByRole('link',{name:'Download original',exact:true}).getAttribute('href'),base).pathname,file);
  const canvas=page.locator('.file-canvas canvas');await canvas.hover();
  const wheel=await page.evaluate(()=>{const s=window.__fileViewer.stage,radius=()=>s.camera.position.distanceTo(s.controls.target),before=radius(),event=new WheelEvent('wheel',{deltaY:100,bubbles:true,cancelable:true});s.renderer.domElement.dispatchEvent(event);return {before,after:radius(),prevented:event.defaultPrevented};});
  assert.equal(wheel.before,wheel.after,'Wheel input cannot jump the camera immediately');assert.equal(wheel.prevented,true);
  const expected=wheel.before*Math.exp(.013);
  await page.waitForFunction(expected=>{const s=window.__fileViewer.stage;return Math.abs(s.camera.position.distanceTo(s.controls.target)-expected)<expected*.00002;},expected);
  const zoom=await page.evaluate(()=>window.__fileViewer.stage.camera.position.distanceTo(window.__fileViewer.stage.controls.target));assert.ok(zoom>wheel.before&&zoom/wheel.before<1.03,'Wheel zoom remains a small increment');
  await page.mouse.wheel(0,-100);
  await page.waitForFunction(expected=>{const s=window.__fileViewer.stage;return Math.abs(s.camera.position.distanceTo(s.controls.target)-expected)<expected*.00003;},wheel.before);
  await page.getByRole('button',{name:'Front',exact:true}).click();await page.getByRole('button',{name:'Fit',exact:true}).click();
  await page.screenshot({path:`${out}/${engine.name()}-viewer-${file.split('.').pop()}.png`});
 }
 const stopped=await page.evaluate(async()=>{const v=window.__fileViewer;window.viewerTicks=0;v.stage.onFrame(()=>window.viewerTicks++);const frames=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));await frames();v.stage.stop();const count=window.viewerTicks;await frames();const stopped=count===window.viewerTicks;v.stage.start();await frames();const resumed=window.viewerTicks>count;v.dispose();v.dispose();const final=window.viewerTicks;await frames();return {stopped,resumed,disposed:final===window.viewerTicks,canvases:document.querySelectorAll('canvas').length,lost:v.stage.renderer.getContext().isContextLost()};});assert.deepEqual(stopped,{stopped:true,resumed:true,disposed:true,canvases:0,lost:true});
 await context.close();
 const denied=await browser.newContext({viewport:{width:320,height:568}});await denied.addInitScript(()=>{sessionStorage.setItem('gyropup.prototype-notice','2026-10-29-v1');Object.defineProperty(window,'localStorage',{get(){throw new Error('Storage denied');}});});const blocked=await denied.newPage();blocked.on('pageerror',error=>errors.push(error.message));await blocked.goto(base+'/designer/build.html');await blocked.waitForFunction(()=>document.body.dataset.ready==='1');assert.match(await blocked.locator('.cad-progress-tools').textContent(),/Changes stay in this tab/);await denied.close();
 const firstEntry=await browser.newContext({viewport:{width:320,height:568}}),notice=await firstEntry.newPage();notice.on('pageerror',error=>errors.push(error.message));
 await notice.goto(base+'/designer/kit/file-viewer.html?file=%2Fexports%2Fbody%2Fpost.stl&back=%2Fdesigner%2Fbuild.html');
 await notice.locator('#prototype-notice-dialog[open]').waitFor();await notice.locator('#prototype-notice-ack').click();await notice.waitForFunction(()=>window.__fileViewer?.root.dataset.state==='ready');
 const reopen=notice.locator('.file-nav .prototype-notice-reopen');await reopen.waitFor();
 const placement=await reopen.evaluate(button=>{const r=button.getBoundingClientRect();return {height:r.height,width:r.width,left:r.left,right:r.right,top:r.top,bottom:r.bottom,enhanced:document.body.dataset.prototypeEnhanced,footerHidden:getComputedStyle(document.getElementById('prototype-notice-footer')).display==='none'};});assert.ok(placement.height>=44&&placement.width>=44&&placement.left>=0&&placement.right<=320&&placement.top>=0&&placement.bottom<=568,JSON.stringify(placement));assert.equal(placement.enhanced,'true');assert.equal(placement.footerHidden,true);
 await notice.evaluate(()=>window.noticeIdentity={viewer:window.__fileViewer,model:window.__fileViewer.model,scene:window.__fileViewer.stage.scene});await reopen.click();await notice.locator('#prototype-notice-dialog[open]').waitFor();await notice.locator('#prototype-notice-ack').click();
 assert.equal(await notice.evaluate(()=>window.noticeIdentity.viewer===window.__fileViewer&&window.noticeIdentity.model===window.__fileViewer.model&&window.noticeIdentity.scene===window.__fileViewer.stage.scene&&document.activeElement===document.querySelector('.file-nav .prototype-notice-reopen')&&sessionStorage.getItem('gyropup.prototype-notice')==='2026-10-29-v1'),true);
 await notice.screenshot({path:`${out}/${engine.name()}-viewer-phone-notice.png`});await firstEntry.close();
 assert.deepEqual(errors,[]);await writeFile(`${out}/${engine.name()}-report.json`,JSON.stringify({base,version,shared,printedKey,summaries,sticky,publishedModels:inventory.files.length,errors},null,2));console.log(`PASS ${engine.name()}: sortable semantic tables, fixed totals, shared persistent checklists, print status, atomic import/export, denied storage, 495 original/preview mappings, real STL/STEP/3MF controls and stage disposal, and four phone layouts`);
}finally{await browser.close();}
