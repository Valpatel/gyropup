import assert from 'node:assert/strict';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {chromium,webkit} from '@playwright/test';
import {acknowledgePrototypeNotice} from './test-prototype-session.mjs';
const root=new URL('../',import.meta.url),base=(process.env.SITE_URL||'http://127.0.0.1:8914').replace(/\/$/,'');
const files=execFileSync('git',['ls-files','docs','research'],{cwd:root}).toString().trim().split('\n').filter(f=>f.endsWith('.md'));
const pages=[];for(const file of files){const source=await readFile(new URL(file,root),'utf8'),count=[...source.matchAll(/^```mermaid\s*$/gm)].length;if(count)pages.push({file,count,path:'/site/pages/'+file.toLowerCase().replace(/[^a-z0-9]+/g,'-')+'.html'});}
assert.equal(pages.reduce((n,p)=>n+p.count,0),4,'Inventory every currently published diagram; update explicitly when adding sources');
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true}:{headless:true});
const out=process.env.TEST_OUTPUT||'/tmp/gyropup-mermaid';await mkdir(out,{recursive:true});const cases=[],errors=[];
async function ready(page,count){await page.waitForFunction(n=>document.querySelectorAll('.cad-diagram[data-state=ready] svg').length===n,count);}
async function noSource(page){assert.ok(!/flowchart LR|graph TD|sequenceDiagram/.test(await page.locator('body').innerText()),'Raw syntax is not exposed');assert.equal(await page.locator('.cad-diagram details[open],code.language-mermaid:visible').count(),0);}
try{
 for(const width of [1280,320])for(const doc of pages){
  const context=await browser.newContext({viewport:{width,height:width===320?568:900},colorScheme:'dark'});await acknowledgePrototypeNotice(context);
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(base+doc.path);await ready(page,doc.count);await noSource(page);
  const diagrams=await page.locator('.cad-diagram').evaluateAll(nodes=>nodes.map(el=>({theme:el.dataset.theme,state:el.dataset.state,labelCount:el.querySelectorAll('svg text,svg .nodeLabel,svg foreignObject').length,rect:el.querySelector('svg').getBoundingClientRect().toJSON()})));
  assert.ok(diagrams.every(d=>d.theme==='light'&&d.labelCount>0&&d.rect.width>100&&d.rect.height>30),'Match the actual light document even with a dark OS preference');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No document overflow on phone');
  const markdown=await page.request.get(base+doc.path.replace(/\.html$/,'.md'));assert.equal(markdown.status(),200);assert.match(await markdown.text(),/```mermaid/);
  await page.screenshot({path:`${out}/${engine.name()}-${width}-${doc.file.replaceAll('/','-')}.png`,fullPage:true});cases.push({width,...doc,diagrams});await context.close();
 }
 const context=await browser.newContext({viewport:{width:320,height:568}});await acknowledgePrototypeNotice(context);const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 // The module itself fails before the observer can take ownership: the HTML bootstrap must recover.
 await page.route('**/diagrams.js*',route=>route.abort());await page.goto(base+pages[0].path,{waitUntil:'domcontentloaded'});
 await page.getByRole('button',{name:'Reload diagrams'}).waitFor();assert.equal(await page.locator('code.language-mermaid:visible').count(),0);
 assert.ok((await page.getByRole('button',{name:'Reload diagrams'}).boundingBox()).height>=44);await page.unroute('**/diagrams.js*');
 await page.getByRole('button',{name:'Reload diagrams'}).click();await ready(page,pages[0].count);
 // A failed runtime download is an individual visible retry, not an empty or raw-code panel.
 await context.close();const recovery=await browser.newContext();await acknowledgePrototypeNotice(recovery);const retryPage=await recovery.newPage();
 await retryPage.route('**/mermaid.min.js*',route=>route.abort());await retryPage.goto(base+pages[0].path,{waitUntil:'domcontentloaded'});
 await retryPage.getByRole('button',{name:'Retry diagram'}).waitFor();await noSource(retryPage);await retryPage.unroute('**/mermaid.min.js*');
 await retryPage.getByRole('button',{name:'Retry diagram'}).click();await ready(retryPage,pages[0].count);
 await retryPage.evaluate(()=>{const d=document.createElement('div');d.innerHTML='<pre><code class="language-mermaid">flowchart TD\nLater-->Rendered</code></pre>';document.querySelector('article').append(d);});
 await ready(retryPage,pages[0].count+1);await noSource(retryPage);await recovery.close();
 assert.deepEqual(errors,[]);await writeFile(`${out}/${engine.name()}-report.json`,JSON.stringify({pages,cases,bootstrapRecovery:true,runtimeRecovery:true,dynamic:true,errors},null,2));console.log(`${engine.name()}: all4 published diagrams, desktop/phone, source routes, bootstrap/runtime recovery and dynamic insertion PASS`);
}finally{await browser.close();}
