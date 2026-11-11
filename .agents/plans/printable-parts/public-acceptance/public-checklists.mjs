// Prepared only. No fixtures, route interception, remote writes, device calls or local listener.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {pathToFileURL,fileURLToPath} from 'node:url';
import path from 'node:path';
const packet=path.dirname(fileURLToPath(import.meta.url));
const c=JSON.parse(await readFile(path.join(packet,'contract.json')));
assert.equal(c.approved_for_execution,true,'Prepared packet is NOT approved for execution');
assert.ok(!JSON.stringify(c).includes('TODO')&&!JSON.stringify(c).includes('UNBOUND'),'Bind every future identity before execution');
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const git=(...args)=>execFileSync('git',['-C',c.repo,...args],{timeout:10000,maxBuffer:8*1024*1024});
assert.match(c.main,/^[a-f0-9]{40}$/);assert.match(c.tree,/^[a-f0-9]{40}$/);assert.match(c.assets,/^[a-f0-9]{20}$/);
assert.equal(git('rev-parse',c.main+'^{tree}').toString().trim(),c.tree);
assert.equal(git('rev-parse','origin/main').toString().trim(),c.main);
const providers=JSON.parse(await readFile(path.join(packet,'provider-reference.json')));
for(const key of ['node','playwright','chrome'])assert.equal(hash(await readFile(providers[key].path)),providers[key].sha256,'Provider changed: '+key);
assert.equal(process.execPath,providers.node.path);assert.equal(process.version,providers.node.version);
const release=JSON.parse(await readFile(path.join(packet,'release-binding.json')));
assert.equal(release.tag,c.toolkit_release);assert.equal(release.commit,c.toolkit_commit);assert.equal(release.part_table_sha256,c.toolkit_part_table_sha256);
for(const [url,expected] of Object.entries(c.sources)){
 assert.match(expected,/^[a-f0-9]{64}$/);assert.equal(hash(git('show',c.main+':software/site'+url)),expected);
}
assert.equal(c.sources['/designer/kit/part-table.js'],c.toolkit_part_table_sha256);
for(const t of c.tables){assert.ok(Number.isInteger(t.count)&&t.count>0&&Number.isInteger(t.index));assert.equal(t.ids.length,t.count);assert.equal(new Set(t.ids).size,t.count);assert.ok(t.ids.includes(t.requiredId));}
await mkdir(c.out); // Exclusive namespace; never reuse a spent evidence directory.
// This executes INSIDE the exact transient unit, before any network/browser work.
const props=execFileSync('systemctl',['--user','show',c.unit+'.service','-p','LoadState','-p','ActiveState','-p','MainPID','-p','InvocationID','-p','ControlGroup','-p','CPUQuotaPerSecUSec','-p','MemoryMax','-p','MemorySwapMax','-p','TasksMax','-p','RuntimeMaxUSec','-p','TimeoutStopUSec','-p','KillMode'],{encoding:'utf8',timeout:5000});
const p=Object.fromEntries(props.trim().split('\n').map(line=>line.split(/=(.*)/s).slice(0,2)));
await writeFile(path.join(c.out,'live-unit.json'),JSON.stringify({at:new Date().toISOString(),properties:p},null,2),{flag:'wx'});
assert.equal(p.LoadState,'loaded');assert.ok(['active','activating'].includes(p.ActiveState));assert.equal(p.MainPID,String(process.pid));assert.match(p.InvocationID,/^[a-f0-9]{32}$/);
assert.equal(p.MemoryMax,'3221225472');assert.equal(p.MemorySwapMax,'0');assert.equal(p.TasksMax,'512');assert.equal(p.KillMode,'control-group');
assert.ok(['2s','2000000us'].includes(p.CPUQuotaPerSecUSec));assert.ok(['8min','480s'].includes(p.RuntimeMaxUSec));assert.ok(['5s','5000000us'].includes(p.TimeoutStopUSec));
assert.ok(p.ControlGroup.endsWith('/'+c.unit+'.service'));assert.ok(!p.ControlGroup.includes('..'));
const base='https://gyropup.com',rows=[],captures=[],pdfs=[],errors=[],failures=[],delivered=[],deliveries=[];
let browser,context,page,primary=null,phase='version',closing=false,work,timer;
const started=Date.now();
async function bounded(promise,ms,label){let timer;try{return await Promise.race([promise,new Promise((_,reject)=>timer=setTimeout(()=>reject(Error(label+' exceeded '+ms+' ms')),ms))]);}finally{clearTimeout(timer);}}
async function version(){const r=await fetch(base+'/version.json',{signal:AbortSignal.timeout(15000),redirect:'error'});assert.equal(r.status,200);const v=await r.json();assert.equal(v.revision,c.main);assert.equal(v.assets,c.assets);return v;}
async function shot(name){const at=Date.now();await page.screenshot({path:path.join(c.out,name+'.png'),timeout:30000,fullPage:false});captures.push({name,elapsedMs:Date.now()-at,artifactBoundMs:30000});}
async function ready(){await page.waitForFunction(()=>{const a=window.__buildGuide?.active,v=a?.viewer;return document.body.dataset.ready==='1'&&document.querySelector('#assembly')?.dataset.ready==='1'&&a.guideAssembly==='combined'&&v?.stage.renderer.domElement.isConnected&&v.parts.some(p=>p.mesh.visible)&&v.stage.renderer.info.render.calls>0;},null,{timeout:45000,polling:100});
 const state=await page.evaluate(()=>{const a=window.__buildGuide.active,g=a.guide;return {assembly:a.guideAssembly,snapshot:g.snapshot.id,native:g.snapshot.source_commit,collection:g.source.collection_sha256,model:g.model.sha256,parts:a.modelParts.length,steps:g.steps.length};});assert.deepEqual(state,c.guide);return state;}
function locate(t){return page.locator(t.selector).nth(t.index);}
function controls(t){return locate(t).locator('..').locator('xpath=preceding-sibling::*[contains(concat(" ",normalize-space(@class)," ")," cad-table-tools ")][1]');}
async function panel(t){await page.locator('[data-build-tab='+t.panel+']').click();await locate(t).waitFor({state:'visible'});}
async function tableState(t){return locate(t).evaluate(table=>({html:table.tBodies[0].innerHTML,rows:[...table.tBodies[0].rows].filter(r=>!r.hasAttribute('data-fixed')).map(r=>({id:r.dataset.partKey,label:r.dataset.partLabel,hidden:r.hidden,text:(()=>{const copy=r.cloneNode(true);copy.querySelectorAll('.cad-status-cell').forEach(cell=>cell.remove());return copy.textContent;})(),checks:[...r.querySelectorAll('input[type=checkbox]')].map(e=>({label:e.ariaLabel,checked:e.checked}))})),scroll:table.parentElement.scrollLeft}));}
async function grid(t,label){
 // Vertical-only scroll preserves actual initial horizontal visibility.
 await locate(t).evaluate(table=>scrollTo({top:table.getBoundingClientRect().top+scrollY-110,left:0,behavior:'instant'}));
 const actual=await locate(t).evaluate(table=>{const rs=[...table.tBodies[0].rows].filter(r=>!r.hidden&&!r.hasAttribute('data-fixed')).slice(0,3);const wrap=table.parentElement;return {overflow:document.documentElement.scrollWidth>innerWidth+1,scrollLeft:wrap.scrollLeft,viewport:innerWidth,columns:[...table.tHead.rows[0].cells].map((h,i)=>{const b=h.getBoundingClientRect();return {title:h.textContent,width:b.width,cells:rs.map(r=>{const d=r.cells[i].getBoundingClientRect();return {width:d.width,left:b.left-d.left,right:b.right-d.right};})};})};});
 assert.equal(actual.overflow,false);assert.ok(actual.columns.length>0);for(const col of actual.columns){assert.ok(col.width>0);assert.ok(col.cells.length>0);for(const cell of col.cells)assert.ok(cell.width>0&&Math.abs(cell.left)<1&&Math.abs(cell.right)<1,JSON.stringify({label,col}));}
 rows.push({case:'visible grid',table:t.name,label,...actual});
}
async function printed(t,scope,suffix,paper){
 const toolbar=controls(t);await toolbar.getByLabel(/Checklist scope/).selectOption(scope);
 const before=await tableState(t),query=scope==='matched'?(await toolbar.getByRole('searchbox').inputValue()).trim().toLocaleLowerCase():'';
 const expected=(scope==='all'?before.rows:before.rows.filter(r=>r.text.toLocaleLowerCase().includes(query))).map(r=>r.id);
 // No consumer filter is changed in this run; search text is calculated from actual source rows independently.
 assert.ok(expected.length>0);const opened=page.waitForEvent('popup');const action=toolbar.getByRole('button',{name:'Print checklist',exact:true});if(scope==='matched'){await action.focus();await action.press('Enter');}else await action.click();const popup=await opened;
 try{await popup.waitForLoadState('domcontentloaded');
  const text=await popup.locator('body').textContent();assert.ok(text.includes('Revision: '+c.main));assert.match(text,/Current front\/rear-pack robot manufacturing plan remains incomplete/);assert.ok(text.includes(scope==='all'?'All parts:':'Matching parts, all pages:'));
  const ids=await popup.locator('tbody tr[data-print-part]').evaluateAll(rs=>rs.map(r=>r.cells[1].textContent));assert.deepEqual(ids,expected);assert.deepEqual([...ids].sort(),[...(scope==='all'?t.ids:t.matchingIds)].sort());assert.equal(new Set(ids).size,expected.length);
  const groups=await popup.locator('tbody').evaluateAll(bodies=>bodies.map(body=>({key:body.dataset.printKey,id:body.querySelector('[data-print-part]')?.cells[1]?.textContent,notes:Object.fromEntries([...body.querySelectorAll('[data-print-column]')].map(note=>[note.dataset.printColumn,note.lastChild.textContent])),height:body.getBoundingClientRect().height})));
  assert.deepEqual(groups.map(group=>[group.key,group.id]),ids.map(id=>[id,id]));for(const group of groups)assert.deepEqual(group.notes,t.longNotes[group.id]??{});
  const fieldRows=await popup.locator('tbody').evaluateAll(bodies=>{const headings=[...document.querySelectorAll('thead th')].map(th=>th.textContent);return bodies.map(body=>{const main=body.querySelector('[data-print-part]'),fields=Object.fromEntries([...main.cells].map((cell,index)=>[headings[index],cell.textContent]));for(const note of body.querySelectorAll('[data-print-column]'))fields[note.dataset.printColumn]=note.lastChild.textContent;return {id:body.dataset.printKey,fields};});});
  const canonical=value=>String(value??'').replace(/\s+/g,' ').trim();for(const row of fieldRows)for(const [column,fragments] of Object.entries(t.requiredFields[row.id]??{}))for(const fragment of fragments)assert.ok(canonical(row.fields[column]).includes(canonical(fragment)),JSON.stringify({table:t.name,id:row.id,column,missing:fragment}));
  for(const source of before.rows.filter(r=>expected.includes(r.id))){const r=popup.getByRole('cell',{name:source.id,exact:true}).locator('..');for(const check of source.checks){const label=check.label.split(':')[0];const head=await popup.locator('th').allTextContents();const index=head.indexOf(label);assert.ok(index>=0);assert.equal(await r.locator('td').nth(index).textContent(),check.checked?'☑':'☐');}}
  if(t.pendingWarnings!==undefined)assert.equal(await popup.locator('tbody tr[data-print-part]').filter({hasText:'Model export pending'}).count(),t.pendingWarnings);
  if(t.name==='queue'&&scope==='all'){const hip=popup.getByRole('cell',{name:'print/leg/hip_frame',exact:true}).locator('..');for(const value of ['1106','72.5'])assert.equal(await hip.getByRole('cell',{name:value,exact:true}).count(),1);}
  if(paper){await popup.emulateMedia({media:'print'});const landscape=await popup.evaluate(()=>document.body.dataset.printOrientation==='landscape');
   for(const format of ['A4','Letter']){const mm=(landscape?(format==='A4'?297:279.4):(format==='A4'?210:215.9))-24;await popup.setViewportSize({width:Math.floor(mm/25.4*96),height:900});
    const compact=await popup.locator('th,td[data-print-kind=number],td[data-print-kind=status]').evaluateAll(cells=>cells.map(cell=>{const range=document.createRange();range.selectNodeContents(cell);const rs=[...range.getClientRects()],b=cell.getBoundingClientRect();return {text:cell.textContent,compact:cell.hasAttribute('data-print-compact')||cell.dataset.printKind==='status'||(cell.tagName==='TH'&&!/\s/.test(cell.textContent)),lines:rs.length,within:rs.every(r=>r.left>=b.left&&r.right<=b.right)};}));assert.ok(compact.every(cell=>(!cell.compact||cell.lines===1)&&cell.within),JSON.stringify(compact.filter(cell=>(cell.compact&&cell.lines!==1)||!cell.within)));
    const groupGeometry=await popup.locator('tbody').evaluateAll(bodies=>bodies.map(body=>({key:body.dataset.printKey,height:body.getBoundingClientRect().height,nameWidth:body.querySelector('[data-print-primary]')?.getBoundingClientRect().width})));const pageHeight=((landscape?(format==='A4'?210:215.9):(format==='A4'?297:279.4))-24)/25.4*96;assert.ok(groupGeometry.every(group=>group.height<=pageHeight&&group.nameWidth>=100));
    const file=t.name+'-'+suffix+'-'+format+'.pdf';await popup.pdf({path:path.join(c.out,file),format,landscape,printBackground:true,timeout:20000});pdfs.push({file,table:t.name,scope,ids,landscape,format,expectedPages:scope==='all'?t.pdfPages[format]:null,pendingWarnings:t.pendingWarnings??null});}
  }
  rows.push({case:'printed',table:t.name,scope,ids});
 }finally{await popup.close();}
 assert.deepEqual(await tableState(t),before,'Printing preserves live rows/checkboxes/page/scroll');
}
try{
 const initial=await version();const {chromium}=await import(pathToFileURL(providers.playwright.path));
 browser=await chromium.launch({executablePath:providers.chrome.path,headless:true,timeout:20000,args:['--no-sandbox','--mute-audio','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});assert.equal(browser.version(),providers.chrome.expected_browser_version);
 context=await browser.newContext({viewport:{width:1280,height:900},deviceScaleFactor:1,colorScheme:'light',reducedMotion:'reduce',acceptDownloads:false});
 // Isolated context only. Native notice interaction; no route interception or app bootstrap injection.
 page=await context.newPage();page.setDefaultTimeout(15000);page.setDefaultNavigationTimeout(45000);
 page.on('pageerror',e=>{if(errors.length<64)errors.push({phase,message:e.message});});
 page.on('requestfailed',r=>{if(!closing&&failures.length<128)failures.push({phase,url:r.url(),error:r.failure()?.errorText});});
 page.on('response',r=>{const u=new URL(r.url()),artifact=u.pathname==='/designer/build'?'/designer/build.html':u.pathname;if(u.origin===base&&(artifact in c.sources||artifact in c.built)){const task=r.body().then(bytes=>{assert.equal(hash(bytes),c.sources[artifact]??c.built[artifact]);if(artifact!=='/designer/build.html')assert.equal(u.searchParams.get('v'),c.assets);delivered.push({url:artifact,pathname:u.pathname,sha256:hash(bytes),v:u.searchParams.get('v')});});task.catch(()=>{});deliveries.push(task);}if(r.status()>=400&&failures.length<128)failures.push({phase,url:r.url(),status:r.status()});});
 work=(async()=>{
  phase='real Build integration';assert.equal((await page.goto(base+'/designer/build',{waitUntil:'domcontentloaded'})).status(),200);
  await page.locator('#prototype-notice-dialog[open]').waitFor({state:'visible'});await page.getByRole('button',{name:'I understand',exact:true}).click();await page.locator('#prototype-notice-dialog').waitFor({state:'hidden'});
  rows.push({case:'actual assembly integrated',state:await ready()});
  if(!await page.locator('#build-details').evaluate(e=>e.open))await page.locator('#build-details > summary').click();assert.equal(await page.locator('#build-details').evaluate(e=>e.open),true);
  const mainTables=c.tables.filter(t=>t.name!=='pending');
  for(const t of c.tables){await panel(t);const state=await tableState(t);assert.equal(state.rows.length,t.count);assert.deepEqual([...state.rows.map(r=>r.id)].sort(),[...t.ids].sort());}
  for(const width of [1280,320]){await page.setViewportSize({width,height:900});for(const t of mainTables){phase=t.name+' visible '+width;await panel(t);await grid(t,'initial '+width);await shot(t.name+'-'+width);}}
  await page.setViewportSize({width:1280,height:900});
  for(const t of mainTables.filter(t=>t.name!=='made')){
   phase=t.name+' scope/state';await panel(t);const toolbar=controls(t),row=locate(t).locator('tr[data-part-key='+JSON.stringify(t.requiredId)+']');
   // Reveal a real stable ID via native search, then set only its isolated-browser checkbox.
   const source=(await tableState(t)).rows.find(r=>r.id===t.requiredId);const search=toolbar.getByRole('searchbox');await search.focus();await search.press('Control+A');await search.pressSequentially(source.label,{delay:0});const box=row.getByRole('checkbox').first();await box.check();assert.equal(await box.isChecked(),true);
   for(const width of [1280,320]){await page.setViewportSize({width,height:900});await grid(t,'filtered '+width);}await page.setViewportSize({width:1280,height:900});await printed(t,'matched','matching',true);
   // Filtering stays active for full output: hidden rows/pages must still appear exactly once.
   await printed(t,'all','all',true);await toolbar.getByRole('searchbox').fill('');
   const sort=toolbar.getByLabel(/^Sort /);const option=await sort.locator('option').nth(1).getAttribute('value');assert.ok(option);await sort.selectOption(option);for(const width of [1280,320]){await page.setViewportSize({width,height:900});await grid(t,'sorted '+width);}await page.setViewportSize({width:1280,height:900});
   const nav=locate(t).locator('..').locator('xpath=following-sibling::nav[contains(@class,"cad-table-pagination")][1]');if(await nav.isVisible()){await nav.getByRole('button',{name:/Next page/}).click();await printed(t,'all','all-from-next-page',false);}
   await toolbar.getByRole('searchbox').fill(source.label);assert.equal(await row.getByRole('checkbox').first().isChecked(),true);await toolbar.getByRole('searchbox').fill('');
  }
  const made=c.tables.find(t=>t.name==='made');phase='fabrication callouts';await panel(made);await printed(made,'all','all',true);
  const pending=c.tables.find(t=>t.name==='pending');phase='pending warnings';await panel(pending);await printed(pending,'all','all',true);
  phase='reload saved statuses';await page.reload({waitUntil:'domcontentloaded'});await ready();if(!await page.locator('#build-details').evaluate(e=>e.open))await page.locator('#build-details > summary').click();
  for(const t of mainTables.filter(t=>t.name!=='made')){await panel(t);const source=(await tableState(t)).rows.find(r=>r.id===t.requiredId);await controls(t).getByRole('searchbox').fill(source.label);assert.equal(await locate(t).locator('tr[data-part-key='+JSON.stringify(t.requiredId)+']').getByRole('checkbox').first().isChecked(),true);}
  assert.equal(captures.length,6);assert.equal(pdfs.length,12);
  phase='final identity';assert.deepEqual(await version(),initial);await Promise.all(deliveries);for(const url of [...Object.keys(c.sources),...Object.keys(c.built)])assert.ok(delivered.some(x=>x.url===url),'Actually loaded '+url);assert.deepEqual(errors,[]);assert.deepEqual(failures,[]);
 })();
 await bounded(work,420000-(Date.now()-started),'entire public acceptance');
}catch(error){primary=error;if(page&&!page.isClosed())await page.screenshot({path:path.join(c.out,'failure.png'),timeout:1000}).catch(()=>{});}
finally{
 closing=true;const cleanup={contextClosed:false,browserClosed:false,workSettled:!work};
 try{if(context){await bounded(context.close(),5000,'context close');cleanup.contextClosed=true;}}catch(e){primary??=e;}
 try{if(browser){await bounded(browser.close(),15000,'browser close');cleanup.browserClosed=!browser.isConnected();}}catch(e){primary??=e;}
 try{if(work){await bounded(work.catch(()=>{}),2000,'work settle');cleanup.workSettled=true;}}catch(e){primary??=e;}
 await writeFile(path.join(c.out,'report.json'),JSON.stringify({pass:!primary&&cleanup.contextClosed&&cleanup.browserClosed&&cleanup.workSettled,phase,error:primary?.stack??null,contract:c,rows,captures,pdfs,errors,failures,delivered,cleanup,elapsedMs:Date.now()-started},null,2),{flag:'wx'});if(primary)process.exitCode=1;
}
