/** Bounded real planner acceptance; no printer/device action and no CAD regeneration. */
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {chromium,webkit} from '@playwright/test';
import {createSiteServer} from '../../../tools/site/serve-site.mjs';
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
  await printed.waitForLoadState();assert.equal(await printed.locator('tbody tr').count(),total);
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
   assert.equal(await printed.getByRole('cell',{name:'72.56',exact:true}).count(),1);
   assert.equal(await printed.getByRole('columnheader',{name:'Hours',exact:true}).count(),1);
   if(engine===chromium)await printed.pdf({path:`${out}/gyropup-${format}.pdf`,format,landscape,printBackground:true});
  }
  await printed.close();
  const term=await first.getAttribute('data-part-label');await tools.getByRole('searchbox').fill(term);
  const expected=await table.locator('tbody tr').evaluateAll((rows,term)=>rows.filter(row=>row.textContent.toLowerCase().includes(term.toLowerCase())).map(row=>row.dataset.partKey),term);
  const filteredEvent=page.waitForEvent('popup');await tools.getByRole('button',{name:'Print checklist',exact:true}).click();const filtered=await filteredEvent;
  await filtered.waitForLoadState();assert.equal(await filtered.locator('tbody tr').count(),expected.length);
  for(const id of expected)assert.ok((await filtered.locator('tbody').textContent()).includes(id));await filtered.close();
  await tools.getByLabel(/Checklist scope/).selectOption('all');const allEvent=page.waitForEvent('popup');await tools.getByRole('button',{name:'Print checklist',exact:true}).click();const all=await allEvent;await all.waitForLoadState();assert.equal(await all.locator('tbody tr').count(),total);await all.close();
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
  await singlePrint.waitForLoadState();assert.equal(await singlePrint.locator('tbody tr').count(),1);
  assert.match(await singlePrint.locator('tbody').textContent(),/test\/single-part/);assert.match(await singlePrint.locator('tbody').textContent(),/☑/);
  await singlePrint.close();await page.evaluate(()=>{const host=document.getElementById('single-part-checklist');window.singlePartUI.dispose(host);host.remove();});
  const pending=await page.locator('#queue table').evaluateAll(tables=>tables.map((table,index)=>({index,count:[...table.tBodies[0].rows].filter(row=>row.textContent.includes('Model export pending')).length})).find(item=>item.count>0));
  assert.ok(pending,'actual retained turret plan has pending model exports');
  const pendingTools=page.locator('#queue .cad-table-tools').nth(pending.index);
  await pendingTools.getByRole('searchbox').fill('');await pendingTools.getByLabel(/Checklist scope/).selectOption('all');
  const pendingEvent=page.waitForEvent('popup');await pendingTools.getByRole('button',{name:'Print checklist',exact:true}).click();const pendingPrint=await pendingEvent;await pendingPrint.waitForLoadState();
  assert.equal(await pendingPrint.locator('tbody tr').filter({hasText:'Model export pending'}).count(),pending.count);
  if(engine===chromium)for(const format of ['A4','Letter'])await pendingPrint.pdf({path:`${out}/gyropup-pending-${format}.pdf`,format,landscape:await pendingPrint.evaluate(()=>document.body.dataset.printOrientation==='landscape'),printBackground:true});
  await pendingPrint.close();observations.push({case:'actual turret pending exports retained',pendingRows:pending.count});
  observations.push({case:'one-part printable product adapter',printedRows:1,checked:true,searchControls:0,sortControls:0});
 }
 assert.deepEqual(errors,[]);await page.screenshot({path:`${out}/planner.png`,fullPage:false});
 await writeFile(`${out}/report.json`,JSON.stringify({engine:engine.name(),errors,observations},null,2));console.log('PASS planner alignment, seeded misalignment rejection and printable checklist scope/state');
}finally{await browser?.close();await new Promise(resolve=>{server.close(resolve);server.closeAllConnections();});}
