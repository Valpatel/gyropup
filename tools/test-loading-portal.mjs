/** Held responses and retryable failures must never look like usable reports/models. */
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {chromium,webkit} from '@playwright/test';
const base=(process.env.SITE_URL||'http://127.0.0.1:8892').replace(/\/$/,''),out=process.env.TEST_OUTPUT||'/tmp/gyropup-loading-portal';
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
const record=label=>{cases.push(label);console.log('PASS '+label);};
const context=await browser.newContext({viewport:{width:320,height:568},reducedMotion:'reduce'}),errors=[],cases=[];
await context.addInitScript(()=>{localStorage.setItem('gyropup.probe','off');localStorage.setItem('gyropup-sfx','0');sessionStorage.setItem('gyropup.prototype-notice','2026-10-29-v1');});
await mkdir(out,{recursive:true});
const json=async path=>{const r=await context.request.get(base+path);assert.ok(r.ok(),path);return r.json();};
const turret=await json('/exports/sim/turret_box/manifest.json'),part=turret.parts.find(p=>p.name==='barrel');
const partURL='/exports/sim/turret_box/'+part.file;
const manifest={title:'Loading test: published barrel',parts:[{name:part.name,file:base+partURL,color:part.color,bounds_mm:part.bbox}]};
const progress=await json('/docs/progress.json');
async function pageFor(path,setup=async()=>{}){
  const page=await context.newPage();page.setDefaultTimeout(60000);page.on('pageerror',error=>errors.push(error.message));
  await setup(page);await page.goto(base+path,{waitUntil:'domcontentloaded'});return page;
}
async function state(page,id,want){await page.waitForFunction(({id,want})=>document.getElementById(id)?.dataset.state===want,{id,want});}
async function retry(page,id){await page.locator('#'+id+' [data-retry]').click();}
async function ready(page){await page.waitForFunction(()=>document.body.dataset.ready==='1');}
async function errorLayout(page,id,label){
  const box=await page.locator('#'+id).boundingBox();assert.ok(box&&box.width>0,`${label}: status visible`);
  const button=page.locator('#'+id+' [data-retry]');await button.focus();assert.equal(await button.evaluate(el=>el===document.activeElement),true);
  const r=await button.boundingBox();assert.ok(r&&r.width>=44&&r.height>=44,`${label}: useful retry target`);
  assert.ok(r.x>=0&&r.y>=0&&r.x+r.width<=await page.evaluate(()=>innerWidth)+1&&r.y+r.height<=await page.evaluate(()=>innerHeight)+1,`${label}: retry in viewport`);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${label}: no horizontal overflow`);
  assert.equal(await page.locator('#'+id+' .gp-loading-icon').evaluate(el=>getComputedStyle(el).animationName),'none','Reduced motion has no spinner animation');
  await page.screenshot({path:`${out}/${engine.name()}-${label}.png`});
}
async function captured(predicate){for(let n=0;n<100&&!predicate();n++)await new Promise(resolve=>setTimeout(resolve,50));assert.ok(predicate(),'Request reached the held route');}
const fail=(route,status=503,body='Unavailable')=>route.fulfill({status,contentType:'text/plain',body});
try{
  // Entry-graph failures cannot rely on the loading helper that failed to import.
  // The inline fallback is reserved for bootstrap; normal data retries below
  // retain their scene and conversation instead of reloading the document.
  for(const [label,path,module,host] of [
    ['Build','/designer/build.html','/designer/build.js','build-loading'],
    ['Progress','/designer/progress.html','/designer/progress.js','progress-loading'],
    ['CAD viewer','/designer/kit/viewer.html?manifest='+encodeURIComponent('/__loading__/model.json'),'/designer/kit/loading.js','viewer-loading'],
    ['FEA','/designer/kit/fea.html?case='+encodeURIComponent('../../exports/fea/thigh-T1.json'),'/designer/kit/fea-viewer.js','fea-loading'],
    ['Talk','/designer/character/talk-demo.html','/designer/robot_v2.js','talk-loading'],
  ]){
    let held,requests=0;const match=url=>url.pathname===module;
    const page=await pageFor(path,async page=>{
      page.on('request',request=>{if(new URL(request.url()).pathname===module)requests++;});
      await page.route(match,route=>{held=route;});
      if(label==='CAD viewer')await page.route(url=>url.pathname==='/__loading__/model.json',route=>route.fulfill({contentType:'application/json',body:JSON.stringify(manifest)}));
    });
    await captured(()=>held);const pending=page.locator('#'+host+' .gp-loading');
    assert.equal(await pending.getAttribute('data-state'),'loading');assert.equal(await pending.getAttribute('aria-busy'),'true');assert.ok(await pending.isVisible());
    assert.equal(await page.locator('canvas').count(),0,'No usable scene exists before bootstrap completes');
    await held.abort('internetdisconnected');await page.waitForFunction(host=>!!document.querySelector('#'+host+' [data-bootstrap-error]'),host);
    const retryButton=page.locator('#'+host+' [data-bootstrap-retry]');await retryButton.focus();assert.ok(await retryButton.evaluate(el=>el===document.activeElement));
    const bounds=await retryButton.boundingBox();assert.ok(bounds&&bounds.height>=44&&bounds.width>=44&&bounds.x>=0&&bounds.y>=0&&bounds.x+bounds.width<=320&&bounds.y+bounds.height<=568,'Bootstrap reload remains reachable on a phone');
    await page.screenshot({path:`${out}/${engine.name()}-bootstrap-${host}.png`});
    await page.unroute(match);await page.evaluate(()=>window.bootstrapSentinel={});
    await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}),retryButton.click()]);await ready(page);
    assert.ok(requests>=2,'Native reload refetches the failed entry graph');assert.ok(await page.evaluate(()=>!window.bootstrapSentinel));assert.equal(await page.locator('[data-bootstrap-error]').count(),0);
    record(label+' held/failed entry graph and native reload');await page.close();
  }
  // The catalog may still be downloading while optional navigation is stalled.
  let release;
  const build=await pageFor('/designer/build.html',async page=>{
    await page.route('**/site/nav.json*',route=>new Promise(resolve=>setTimeout(()=>resolve(route.abort()),1000)));
    await page.route('**/exports/leg/bom.json*',async route=>{await new Promise(resolve=>release=resolve);await route.continue();});
  });
  await state(build,'build-data-status','loading');assert.equal(await build.locator('#grand-usd').count(),0,'No total before required data');
  assert.equal(await build.locator('#build-data-status').getAttribute('aria-busy'),'true');
  await build.waitForFunction(()=>document.querySelector('#build-data-status')?.textContent.includes('Loading'));
  await captured(()=>release);release();await ready(build);await state(build,'build-data-status','ready');
  assert.equal(await build.locator('#grand-usd').count(),1);record('held Build data and optional navigation');await build.close();

  for(const mode of ['http','parse','offline']){
    const pattern=mode==='parse'?'**/catalog/index.json*':'**/exports/leg/bom.json*';
    const page=await pageFor('/designer/build.html',page=>page.route(pattern,route=>mode==='http'?fail(route):mode==='offline'?route.abort('internetdisconnected'):route.fulfill({contentType:'application/json',body:'<html>Wrong response</html>'})));
    await state(page,'build-data-status','error');assert.equal(await page.locator('#grand-usd').count(),0);
    assert.ok(!(await page.locator('#streams').innerText()).includes('NOT GENERATED YET'),'Failure is not unpublished');
    await errorLayout(page,'build-data-status','build-'+mode);
    await page.unroute(pattern);await retry(page,'build-data-status');await ready(page);
    assert.equal(await page.locator('#grand-usd').count(),1,'Retry creates one real total');record('Build '+mode+' recovery');await page.close();
  }
  const unpublished=await pageFor('/designer/build.html',async page=>{
    await page.route('**/exports/body/bom.json*',route=>fail(route,404,'Not published'));
    await page.route('**/exports/body/print-plan.json*',route=>fail(route,404,'Not published'));
  });
  await ready(unpublished);assert.match(await unpublished.locator('#streams').innerText(),/NOT GENERATED YET/);
  assert.match(await unpublished.locator('#summary').innerText(),/Published-data subtotal/);record('Explicit optional404 remains unpublished');await unpublished.close();

  // One report cannot hold back unrelated sections. An older response cannot
  // overwrite the newer retry's content or error state.
  for(const stale of ['success','failure']){
    let oldRoute,calls=0;
    const page=await pageFor('/designer/progress.html',page=>page.route('**/docs/progress.json*',async route=>{
      if(++calls===1){oldRoute=route;return;}
      await route.fulfill({contentType:'application/json',body:JSON.stringify({...progress,status:[{title:'Newer report',value:'Current response'}]})});
    }));
    await state(page,'load-progress','loading');await state(page,'load-leg','ready');
    assert.match(await page.locator('#leglede').innerText(),/Two RS-04s/);
    await page.evaluate(()=>window.__portalLoads.progress.retry());await state(page,'load-progress','ready');
    assert.match(await page.locator('#status').innerText(),/Newer report/);
    if(stale==='failure')await fail(oldRoute);else await oldRoute.fulfill({contentType:'application/json',body:JSON.stringify({...progress,status:[{title:'Obsolete report',value:'Old response'}]})});
    await ready(page);assert.match(await page.locator('#status').innerText(),/Newer report/);assert.doesNotMatch(await page.locator('#status').innerText(),/Obsolete/);
    record('Progress independence and stale '+stale);await page.close();
  }
  const reports=await pageFor('/designer/progress.html',async page=>{
    await page.route('**/exports/leg/leg.json*',route=>fail(route,404,'Not published'));
    await page.route('**/exports/leg/fea/summary.json*',route=>fail(route));
  });
  await state(reports,'load-leg','unavailable');await state(reports,'load-fea','error');await state(reports,'load-progress','ready');
  assert.match(await reports.locator('#load-leg').innerText(),/not been published/);assert.doesNotMatch(await reports.locator('#load-fea').innerText(),/not been published/);
  await reports.evaluate(()=>window.savedLog=document.getElementById('log'));
  await reports.unroute('**/exports/leg/fea/summary.json*');await retry(reports,'load-fea');await state(reports,'load-fea','ready');
  assert.ok(await reports.evaluate(()=>window.savedLog===document.getElementById('log')),'Retry preserves unrelated report identity');record('Independent report failure versus optional404');await reports.close();

  for(const mode of ['held','http','html','empty']){
    let releasePart;
    const page=await pageFor('/designer/kit/viewer.html?manifest='+encodeURIComponent('/__loading__/model.json'),async page=>{
      await page.route('**/__loading__/model.json',route=>route.fulfill({contentType:'application/json',body:JSON.stringify(manifest)}));
      await page.route('**'+partURL+'*',async route=>{
        if(mode==='held'){await new Promise(resolve=>releasePart=resolve);await route.continue();}
        else if(mode==='http')await fail(route);
        else await route.fulfill({contentType:mode==='html'?'text/html':'application/octet-stream',body:mode==='html'?'<html>Not STL</html>':Buffer.alloc(84)});
      });
    });
    if(mode==='held'){
      await state(page,'viewer-load-status','loading');await page.waitForFunction(()=>document.querySelector('#viewer-load-status').textContent.includes('parts'));
      assert.equal(await page.locator('#app canvas').count(),0);await captured(()=>releasePart);releasePart();
    }else{
      await state(page,'viewer-load-status','error');assert.equal(await page.locator('#app canvas').count(),0,'Invalid part never creates a partial ready scene');
      await errorLayout(page,'viewer-load-status','viewer-'+mode);await page.unroute('**'+partURL+'*');await retry(page,'viewer-load-status');
    }
    await ready(page);assert.equal(await page.locator('#app canvas').count(),1);assert.ok(await page.evaluate(()=>window.__viewer.stage.renderer.info.render.calls>0));
    record('CAD viewer '+mode);await page.close();
  }
  for(const mode of ['held','parse','surface']){
    let releaseCase;
    const page=await pageFor('/designer/kit/fea.html?case='+encodeURIComponent('../../exports/fea/thigh-T1.json'),page=>page.route('**/exports/fea/thigh-T1.json*',async route=>{
      if(mode==='held'){await new Promise(resolve=>releaseCase=resolve);await route.continue();}
      else await route.fulfill({contentType:'application/json',body:mode==='parse'?'<html>Not JSON</html>':JSON.stringify({format:'cadagent-fea-viewer',surface:{}})});
    }));
    if(mode==='held'){
      await state(page,'fea-load-status','loading');assert.equal(await page.locator('#app canvas').count(),0);await captured(()=>releaseCase);releaseCase();
    }else{
      await state(page,'fea-load-status','error');assert.equal(await page.locator('#app canvas').count(),0);assert.doesNotMatch(await page.locator('#fea-load-status').innerText(),/undefined|properties|b64/,'Malformed reports have a user-readable explanation');await errorLayout(page,'fea-load-status','fea-'+mode);
      await page.setViewportSize({width:568,height:320});await errorLayout(page,'fea-load-status','fea-'+mode+'-landscape');
      await page.unroute('**/exports/fea/thigh-T1.json*');await retry(page,'fea-load-status');
    }
    await ready(page);assert.equal(await page.locator('#app canvas').count(),1);assert.ok(await page.evaluate(()=>window.__fea.stage.renderer.info.render.calls>0));record('FEA '+mode);await page.close();
  }
  const talk=await pageFor('/designer/character/talk-demo.html',page=>page.route('**'+partURL+'*',route=>route.fulfill({contentType:'text/html',body:'<html>Not the robot part</html>'})));
  await state(talk,'talk-load-status','error');await errorLayout(talk,'talk-load-status','talk-error');assert.ok(await talk.locator('#detect').isDisabled());
  await talk.evaluate(()=>window.originalCanvas=document.querySelector('#app canvas'));
  await talk.unroute('**'+partURL+'*');await retry(talk,'talk-load-status');await ready(talk);
  assert.ok(await talk.evaluate(()=>window.originalCanvas===document.querySelector('#app canvas')),'Robot retry preserves the stage canvas');
  assert.equal(await talk.locator('#app canvas').count(),1);assert.equal(await talk.locator('.gp-dock').count(),1);assert.equal(await talk.locator('#events button').count(),9);
  await talk.getByRole('button',{name:'SHOW PANEL',exact:true}).click();
  await talk.evaluate(()=>{window.savedTalk=window.__talk;window.__talk.detect=()=>new Promise(resolve=>window.releaseServices=resolve);});
  await talk.locator('#detect').click();await state(talk,'service-load-status','loading');assert.ok(await talk.locator('#detect').isDisabled());
  await talk.evaluate(()=>window.releaseServices({tts:{ok:false,name:'Browser voice'},stt:{ok:false,name:'Unavailable'},llm:{ok:false}}));
  await state(talk,'service-load-status','ready');assert.ok(await talk.locator('#detect').isEnabled());assert.ok(await talk.evaluate(()=>window.savedTalk===window.__talk));
  assert.match(await talk.locator('#svc').innerText(),/scripted/);record('Talk same-stage retry and service pending state');await talk.close();
  assert.deepEqual(errors,[],'No escaped bootstrap or decode exceptions');
  const version=await json('/version.json');await writeFile(`${out}/${engine.name()}-report.json`,JSON.stringify({checkedAt:new Date().toISOString(),base,version,cases,errors},null,2));
  console.log(`PASS ${engine.name()}: ${cases.length} portal loading/recovery cases; optional404 versus failure, stale reports, invalid STL/JSON/surfaces, real frame readiness, same-stage Talk retry and keyboard/phone status controls`);
}catch(error){
  console.error('Escaped page errors:',errors);
  for(const [index,page] of context.pages().entries()){
    console.error('Failed page',page.url(),await page.locator('.gp-loading').evaluateAll(elements=>elements.map(el=>({id:el.id,state:el.dataset.state,text:el.textContent}))));
    await page.screenshot({path:`${out}/${engine.name()}-failure-${index}.png`}).catch(()=>{});
  }
  throw error;
}finally{await browser.close();}
