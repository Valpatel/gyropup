/** Bounded real planner acceptance; no printer/device action and no CAD regeneration. */
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {chromium,webkit} from '@playwright/test';
import {createSiteServer} from '../../../tools/site/serve-site.mjs';
const checklistCase=process.env.CHECKLIST_CASE||'all';assert.ok(['all','orders','queue'].includes(checklistCase));
const ordersOnly=checklistCase==='orders';
const out=process.env.TEST_OUTPUT||'/tmp/gyropup-print-checklist';await mkdir(out,{recursive:true});
const server=createSiteServer(path.resolve(process.env.SITE_ROOT||'dist'));
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
let browser;const errors=[],observations=[];
try{
 browser=await engine.launch(engine===chromium?{channel:'chrome',headless:true}:{headless:true});
 const context=await browser.newContext({viewport:{width:1280,height:900}});
 await context.addInitScript(()=>{if(location.protocol==='http:')sessionStorage.setItem('gyropup.prototype-notice','2026-10-29-v1');});
 // Isolate the actual planner: the unrelated assembly viewer is outside this table-only test.
 await context.route('**/designer/assembly/build-guide.js*',route=>route.fulfill({status:200,contentType:'text/javascript',body:'// planner-only fixture: assembly viewer intentionally excluded'}));
 const page=await context.newPage();page.setDefaultTimeout(30000);page.on('pageerror',e=>errors.push(e.message));
 await page.goto(`http://127.0.0.1:${server.address().port}/designer/build#queue`);
 await page.waitForFunction(()=>document.body?.dataset.ready==='1');
 await page.locator('#build-details').evaluate(el=>el.open=true);
 await page.locator('[data-build-tab=print]').click();
 if(!ordersOnly){
 const table=page.locator('#queue table').first(),tools=page.locator('#queue .cad-table-tools').first();
 const measure=(target=table)=>target.evaluate(table=>{const row=[...table.tBodies[0].rows].find(row=>!row.hidden);return [...table.tHead.rows[0].cells].map((head,index)=>{const h=head.getBoundingClientRect(),c=row.cells[index].getBoundingClientRect();return {column:head.textContent,headerWidth:h.width,cellWidth:c.width,left:h.left-c.left,right:h.right-c.right};});});
 const aligned=rows=>rows.every(row=>row.headerWidth>0&&row.cellWidth>0&&Math.abs(row.left)<1&&Math.abs(row.right)<1);
 for(const width of [1280,320]){await page.setViewportSize({width,height:900});for(const [label,target,panel] of [['Print queue',table,'print'],['Find a part',page.locator('#made table').first(),'buy']]){await page.locator(`[data-build-tab=${panel}]`).click();const bounds=await measure(target);assert.ok(aligned(bounds),JSON.stringify(bounds));observations.push({label,width,bounds});}assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
 await page.locator('[data-build-tab=print]').click();
 // Prove that the same measurement rejects a real broken header/cell grid.
 await table.locator('th').first().evaluate(th=>th.style.transform='translateX(12px)');assert.equal(aligned(await measure()),false);
 await table.locator('th').first().evaluate(th=>th.style.removeProperty('transform'));
 if(!process.env.CHECKLIST_BASELINE){
  await page.setViewportSize({width:1280,height:900});
  const total=await table.locator('tbody tr').count(),visible=await table.locator('tbody tr:not([hidden])').count();assert.ok(total>visible,'real print queue spans pages');
  const first=table.locator('tbody tr:not([hidden])').first(),key=await first.getAttribute('data-part-key');
  await first.getByRole('checkbox').check();const before=await table.locator('tbody').innerHTML();
  const opened=page.waitForEvent('popup');await tools.getByRole('button',{name:'Print checklist',exact:true}).click();const printed=await opened;
  await printed.waitForLoadState();assert.equal(await printed.locator('tbody tr[data-print-part]').count(),total);
  assert.match(await printed.locator('body').textContent(),/Current front\/rear-pack robot manufacturing plan remains incomplete/);
  assert.match(await printed.locator('body').textContent(),/Revision: [a-f0-9]{40}/);
  assert.equal(await table.locator('tbody').innerHTML(),before);
  const checkRow=printed.getByRole('cell',{name:key,exact:true}).locator('..');assert.match(await checkRow.textContent(),/☑/);
  await printed.emulateMedia({media:'print'});
  for(const format of ['A4','Letter']){
   const landscape=await printed.evaluate(()=>document.body.dataset.printOrientation==='landscape');
   const paperWidth=(landscape?(format==='A4'?297:279.4):(format==='A4'?210:215.9))-24;
   await printed.setViewportSize({width:Math.floor(paperWidth/25.4*96),height:900});
   const compact=await printed.locator('th,td[data-print-kind=number],td[data-print-kind=status]').evaluateAll(cells=>cells.map(cell=>{const range=document.createRange();range.selectNodeContents(cell);const lines=[...range.getClientRects()],box=cell.getBoundingClientRect();return {text:cell.textContent,lines:lines.length,within:lines.every(line=>line.left>=box.left&&line.right<=box.right)};}));
   assert.ok(compact.every(cell=>cell.lines===1&&cell.within),JSON.stringify(compact.filter(cell=>cell.lines!==1||!cell.within)));
   const hipFrame=printed.getByRole('cell',{name:'print/leg/hip_frame',exact:true}).locator('..');
   assert.equal(await hipFrame.getByRole('cell',{name:'1106',exact:true}).count(),1);
   assert.equal(await hipFrame.getByRole('cell',{name:'72.5',exact:true}).count(),1);
   assert.equal(await printed.getByRole('columnheader',{name:'Hours',exact:true}).count(),1);
   if(engine===chromium)await printed.pdf({path:`${out}/gyropup-${format}.pdf`,format,landscape,printBackground:true});
  }
  await printed.close();
  const term=await first.getAttribute('data-part-label');await tools.getByRole('searchbox').fill(term);
  const expected=await table.locator('tbody tr').evaluateAll((rows,term)=>rows.filter(row=>row.textContent.toLowerCase().includes(term.toLowerCase())).map(row=>row.dataset.partKey),term);
  const filteredEvent=page.waitForEvent('popup');await tools.getByRole('button',{name:'Print checklist',exact:true}).click();const filtered=await filteredEvent;
  await filtered.waitForLoadState();assert.equal(await filtered.locator('tbody tr[data-print-part]').count(),expected.length);
  for(const id of expected)assert.ok((await filtered.locator('tbody').textContent()).includes(id));await filtered.close();
  await tools.getByLabel(/Checklist scope/).selectOption('all');const allEvent=page.waitForEvent('popup');await tools.getByRole('button',{name:'Print checklist',exact:true}).click();const all=await allEvent;await all.waitForLoadState();assert.equal(await all.locator('tbody tr[data-print-part]').count(),total);await all.close();
  observations.push({total,visible,filtered:expected.length,checkedKey:key});
  // Exercise the actual product adapter with a durable one-part fixture: list size
  // must suppress search/sort without making its printable checklist unreachable.
  await page.evaluate(async()=>{
   const {createPortalParts}=await import('/designer/portal-parts.js');
   const host=document.createElement('section');host.id='single-part-checklist';
   host.innerHTML='<div data-single-progress></div><table data-track="print" data-label="One-part print queue"><thead><tr><th>Part</th><th>Quantity</th></tr></thead><tbody><tr data-part-key="test/single-part" data-part-label="Single test part"><td>Single test part</td><td data-sort-value="1">1</td></tr></tbody></table>';
   document.body.append(host);window.singlePartUI=createPortalParts(host.querySelector('[data-single-progress]'),{revision:'single-part-fixture'});window.singlePartUI.enhance(host);
  });
  const single=page.locator('#single-part-checklist');
  assert.equal(await single.getByRole('searchbox').count(),0);
  assert.equal(await single.getByLabel(/^Sort /).count(),0);
  await single.getByRole('checkbox',{name:'Printed: Single test part',exact:true}).check();
  const singleEvent=page.waitForEvent('popup');await single.getByRole('button',{name:'Print checklist',exact:true}).click();const singlePrint=await singleEvent;
  await singlePrint.waitForLoadState();assert.equal(await singlePrint.locator('tbody tr[data-print-part]').count(),1);
  assert.match(await singlePrint.locator('tbody').textContent(),/test\/single-part/);assert.match(await singlePrint.locator('tbody').textContent(),/☑/);
  await singlePrint.close();await page.evaluate(()=>{const host=document.getElementById('single-part-checklist');window.singlePartUI.dispose(host);host.remove();});
  const pending=await page.locator('#queue table').evaluateAll(tables=>tables.map((table,index)=>({index,count:[...table.tBodies[0].rows].filter(row=>row.textContent.includes('Model export pending')).length})).find(item=>item.count>0));
  assert.ok(pending,'actual retained turret plan has pending model exports');
  const pendingTools=page.locator('#queue .cad-table-tools').nth(pending.index);
  await pendingTools.getByRole('searchbox').fill('');await pendingTools.getByLabel(/Checklist scope/).selectOption('all');
  const pendingEvent=page.waitForEvent('popup');await pendingTools.getByRole('button',{name:'Print checklist',exact:true}).click();const pendingPrint=await pendingEvent;await pendingPrint.waitForLoadState();
  assert.equal(await pendingPrint.locator('tbody tr[data-print-part]').filter({hasText:'Model export pending'}).count(),pending.count);
  if(engine===chromium)for(const format of ['A4','Letter'])await pendingPrint.pdf({path:`${out}/gyropup-pending-${format}.pdf`,format,landscape:await pendingPrint.evaluate(()=>document.body.dataset.printOrientation==='landscape'),printBackground:true});
  await pendingPrint.close();observations.push({case:'actual turret pending exports retained',pendingRows:pending.count});
  observations.push({case:'one-part printable product adapter',printedRows:1,checked:true,searchControls:0,sortControls:0});
 }
 }
 if(!process.env.CHECKLIST_BASELINE&&checklistCase!=='queue')await checkOrders(page,out,engine,observations);
 assert.deepEqual(errors,[]);await page.screenshot({path:`${out}/planner.png`,fullPage:false});
 await writeFile(`${out}/report.json`,JSON.stringify({engine:engine.name(),errors,observations},null,2));console.log(ordersOnly?'PASS actual All orders full/matched numeric/currency/status and printable geometry':'PASS planner alignment, seeded misalignment rejection and printable checklist scope/state');
}catch(error){await writeFile(`${out}/failure.json`,JSON.stringify({error:error.stack,errors,observations},null,2));throw error;}finally{await browser?.close();await new Promise(resolve=>{server.close(resolve);server.closeAllConnections();});}


async function checkOrders(page,out,engine,observations){
 await page.setViewportSize({width:1280,height:900});
 await page.locator('[data-build-tab=buy]').click();
 const table=page.locator('#orders table'),tools=page.locator('#orders .cad-table-tools');
 const state=()=>table.evaluate(table=>({html:table.tBodies[0].innerHTML,scrollLeft:table.parentElement.scrollLeft,rows:[...table.tBodies[0].rows].map(row=>({id:row.dataset.partKey,hidden:row.hidden,checks:[...row.querySelectorAll('input[type=checkbox]')].map(c=>c.checked)}))}));
 const ids=await table.locator('tbody tr').evaluateAll(rows=>rows.map(row=>row.dataset.partKey));
 assert.ok(ids.length>12,'actual orders table spans screen pages');assert.equal(new Set(ids).size,ids.length);
 const exactRow=id=>table.locator(`tbody tr[data-part-key=${JSON.stringify(id)}]`);
 await exactRow(ids[0]).getByRole('checkbox',{name:/^Ordered:/}).check();
 await exactRow(ids[1]).getByRole('checkbox',{name:/^In hand:/}).check();
 const source=await table.evaluate(table=>{const headers=[...table.tHead.rows[0].cells].map(th=>th.textContent.trim().replace(/[↕↑↓]/g,'').trim());return [...table.tBodies[0].rows].map(row=>({id:row.dataset.partKey,label:row.dataset.partLabel,text:row.textContent,numeric:[...row.cells].flatMap((cell,index)=>cell.hasAttribute('data-sort-value')?[{title:headers[index],raw:cell.dataset.sortValue,text:cell.dataset.printValue??cell.textContent.trim()}]:[]),supporting:[...row.cells].flatMap((cell,index)=>['Supplier part number','Alternates'].includes(headers[index])?[{title:headers[index],text:cell.dataset.printValue??cell.textContent.trim()}]:[]),ordered:row.querySelector('[aria-label^="Ordered:"]').checked,inHand:row.querySelector('[aria-label^="In hand:"]').checked}));});
 const version=await page.evaluate(async()=>fetch('/version.json').then(r=>r.json()));
 await writeFile(`${out}/orders-source.json`,JSON.stringify({fixture:'real planner with unrelated assembly module isolated',version,source},null,2));
 const allIds=source.map(row=>row.id);observations.push({case:'actual All orders source',total:ids.length,ids:allIds,version,checkedOrdered:ids[0],checkedInHand:ids[1]});
 const term=source[0].label;await tools.getByRole('searchbox').fill(term);
 const matching=source.filter(row=>row.text.toLowerCase().includes(term.toLowerCase())).map(row=>row.id);
 assert.ok(matching.length>0&&matching.length<source.length);
 for(const [scope,expected] of [['matched',matching],['all',allIds]]){
  await tools.getByLabel(/Checklist scope/).selectOption(scope);
  const before=await state();const opened=page.waitForEvent('popup');await tools.getByRole('button',{name:'Print checklist',exact:true}).click();const print=await opened;
  try{
   await print.waitForLoadState();
   const headers=await print.locator('th').allTextContents();assert.ok(headers.includes('Quantity needed')&&headers.includes('Unit price')&&headers.includes('Order cost'));
   assert.deepEqual(await print.locator('tbody tr[data-print-part]').evaluateAll(rows=>rows.map(row=>row.cells[1].textContent)),expected);
   const text=await print.locator('body').textContent();assert.ok(text.includes('Revision: '+version.revision));assert.ok(text.includes(scope==='all'?'All parts:':'Matching parts, all pages:'));
   const values=new Map((await print.locator('tbody').evaluateAll(bodies=>bodies.map(body=>{const row=body.querySelector('[data-print-part]');return {id:row.cells[1].textContent,cells:[...row.cells].map(cell=>cell.textContent),notes:Object.fromEntries([...body.querySelectorAll('[data-print-column]')].map(note=>[note.dataset.printColumn,note.lastChild.textContent]))};}))).map(item=>[item.id,item]));
   for(const item of source.filter(row=>expected.includes(row.id))){
    const record=values.get(item.id),actual=record.cells;
    for(const field of item.supporting){const displayed=record.notes[field.title]??actual[headers.indexOf(field.title)];assert.equal(displayed.replace(/\s/g,''),field.text.replace(/\s/g,''),'complete supporting source text for '+item.id+' '+field.title);}
    for(const field of item.numeric)assert.equal(actual[headers.indexOf(field.title)],field.text,'exact numeric/currency text for '+item.id+' '+field.title);
    for(const [title,value] of [['Ordered',item.ordered],['In hand',item.inHand]])assert.equal(actual[headers.indexOf(title)],value?'☑':'☐');
   }
   await print.emulateMedia({media:'print'});const landscape=await print.evaluate(()=>document.body.dataset.printOrientation==='landscape');
   const measurements=[];
   for(const format of ['A4','Letter']){
    const mm=(landscape?(format==='A4'?297:279.4):(format==='A4'?210:215.9))-24;
    await print.setViewportSize({width:Math.floor(mm/25.4*96),height:900});
    // Keep actual output before asserting readability, so a failed attempt stays inspectable.
    if(engine===chromium)await print.pdf({path:`${out}/orders-${scope}-${format}.pdf`,format,landscape,printBackground:true,timeout:20000});
    const cells=await print.locator('th,td[data-print-kind=number],td[data-print-kind=status]').evaluateAll(cells=>cells.map(cell=>{const range=document.createRange();range.selectNodeContents(cell);const rs=[...range.getClientRects()],b=cell.getBoundingClientRect();return {text:cell.textContent,compact:cell.hasAttribute('data-print-compact')||cell.dataset.printKind==='status'||(cell.tagName==='TH'&&!/\s/.test(cell.textContent)),lines:rs.length,within:rs.every(r=>r.left>=b.left&&r.right<=b.right)};}));
    const documentBounds=await print.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,rows:[...document.querySelectorAll('tbody tr[data-print-part]')].map(row=>({id:row.cells[1].textContent,height:row.parentElement.getBoundingClientRect().height,nameWidth:row.cells[2].getBoundingClientRect().width,idWidth:row.cells[1].getBoundingClientRect().width}))}));
    measurements.push({format,cells,documentBounds});
    await writeFile(`${out}/orders-${scope}-measurements.json`,JSON.stringify(measurements,null,2));
   }
   observations.push({case:'actual All orders printable',scope,ids:expected,landscape,measurements});
   for(const measurement of measurements){
    assert.ok(measurement.cells.every(cell=>(!cell.compact||cell.lines===1)&&cell.within),JSON.stringify(measurement.cells.filter(cell=>(cell.compact&&cell.lines!==1)||!cell.within)));
    assert.ok(measurement.documentBounds.scroll<=measurement.documentBounds.width,'actual All orders print must fit printable width: '+measurement.format);
    const printableHeight=((landscape?(measurement.format==='A4'?210:215.9):(measurement.format==='A4'?297:279.4))-24)/25.4*96;
    assert.ok(measurement.documentBounds.rows.every(row=>row.height<=printableHeight&&row.nameWidth>=100&&row.idWidth>=50),'actual All orders rows must fit one printable page: '+measurement.format);
   }
  }finally{await print.close();}
  assert.deepEqual(await state(),before,'orders printing preserves live DOM/page/status/scroll');
 }
}
