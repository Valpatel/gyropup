/** Real video playback and honest still/error states on the published portal. */
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {chromium,webkit} from '@playwright/test';
const base=(process.env.SITE_URL||'http://127.0.0.1:8899').replace(/\/$/,''),out=process.env.TEST_OUTPUT||'/tmp/gyropup-study-media';
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
const errors=[],cases=[];await mkdir(out,{recursive:true});
const context=await browser.newContext({viewport:{width:390,height:844},reducedMotion:'reduce'});
await context.addInitScript(()=>{localStorage.setItem('gyropup.probe','off');sessionStorage.setItem('gyropup.prototype-notice','2026-10-29-v1');});
const json=async path=>{const r=await context.request.get(base+path);assert.ok(r.ok(),path);return r.json();};
const version=await json('/version.json'),summary=await json('/exports/leg/fea/summary.json'),media=await json('/exports/leg/fea/media.json');
for(const [key,type] of [['video','video/mp4'],['webm','video/webm']]){
  const response=await context.request.head(base+'/'+media.cases['hip_frame/E1'][key]);
  assert.ok(response.ok());assert.match(response.headers()['content-type'],new RegExp('^'+type));
}
const hip=summary.results.findIndex(r=>r.part==='hip_frame'&&r.case==='E1');
const still=summary.results.findIndex((r,i)=>i!==hip&&!r.animation&&!media.cases[`${r.part}/${r.case}`]);
const selector=i=>`#fea tr.click[data-i="${i}"]`;
const movieURL=url=>/\/hip-frame-e1\.(mp4|webm)$/.test(url.pathname);
const record=label=>{cases.push(label);console.log('PASS '+label);};
async function pageFor(setup=async()=>{}){
  const page=await context.newPage();page.setDefaultTimeout(30000);page.on('pageerror',error=>errors.push(error.message));
  await setup(page);await page.goto(base+'/designer/progress.html',{waitUntil:'domcontentloaded'});
  await page.locator(selector(hip)).waitFor({state:'attached'});
  await page.locator('#load-cases > summary').click();return page;
}
async function select(page,i){await page.locator(selector(i)).locator('td').first().click();}
async function state(page,value){await page.waitForFunction(value=>{
  const host=document.querySelector('#fea-media');if(host?.dataset.state==='error'&&value!=='error')throw new Error(host.textContent);
  return host?.dataset.state===value;
},value);}
async function checkPlayback(page){
  await page.locator('.study-play').click();
  await page.waitForFunction(()=>{const v=document.querySelector('#feavid');return !v.paused&&v.currentTime>.25;});
  const before=await page.locator('#feavid').evaluate(v=>({time:v.currentTime,frames:v.getVideoPlaybackQuality().totalVideoFrames}));
  await page.waitForFunction(before=>{const v=document.querySelector('#feavid');return v.currentTime>before.time+.3&&v.getVideoPlaybackQuality().totalVideoFrames>before.frames;},before);
  await page.locator('.study-play').click();assert.equal(await page.locator('#feavid').evaluate(v=>v.paused),true);
}
try{
  const page=await pageFor();await select(page,hip);await state(page,'ready');
  assert.equal(await page.locator('#feavid').evaluate(v=>v.duration),12);
  assert.equal(await page.locator('#feavid').evaluate(v=>v.currentSrc.endsWith(v.canPlayType('video/mp4; codecs="avc1.64001f"')?'.mp4':'.webm')),true,'Choose a supported encoding');
  assert.equal(await page.locator('#feavid').evaluate(v=>v.paused),true,'Reduced motion waits for deliberate play');
  const e1=summary.results[hip];
  assert.ok((await page.locator('#feanote').innerText()).includes(`Safety factor ${e1.safety_factor} / required ${e1.target}${e1.safety_factor<e1.target?' — below target':''}.`),'The note states the recorded E1 gate');
  assert.match(await page.locator('.study-media-status').innerText(),/static load scaling, not elapsed physical time/);
  await checkPlayback(page);record('12-second real decode/play/pause with the recorded strength gate');
  for(const [width,height] of [[320,568],[390,844],[844,390],[1440,900]]){
    await page.setViewportSize({width,height});await page.locator('#fea-media').scrollIntoViewIfNeeded();
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'No horizontal overflow');
    const box=await page.locator('#fea-media').boundingBox();assert.ok(box.x>=0&&box.x+box.width<=width+1,'Media inside phone width');
    const play=page.locator('.study-play');await play.focus();assert.ok(await play.evaluate(el=>el===document.activeElement));
    const bounds=await play.boundingBox();assert.ok(bounds.width>=44&&bounds.height>=44,'Touch target');
    await play.press('Space');await page.waitForFunction(()=>!document.querySelector('#feavid').paused);
    await play.press('Space');await page.waitForFunction(()=>document.querySelector('#feavid').paused);
    await page.screenshot({path:`${out}/${engine.name()}-${width}x${height}.png`});
  }
  record('Phone portrait/landscape and desktop controls, keyboard, layout');
  const viewerHref=await page.locator('#feanote a').getAttribute('href');
  const viewer=await context.newPage();viewer.on('pageerror',e=>errors.push(e.message));
  await viewer.goto(new URL(viewerHref,page.url()).href);await viewer.waitForFunction(()=>document.body.dataset.ready==='1');
  assert.ok(await viewer.evaluate(()=>window.__fea.stage.renderer.info.render.calls>0),'Published E1 fields render in 3D');await viewer.close();
  record('The same solved field opens in the interactive 3D viewer');
  await select(page,still);await state(page,'still');assert.ok(await page.locator('.study-still').isVisible());
  assert.ok(await page.locator('#feavid').isHidden());assert.equal(await page.locator('#feavid').getAttribute('src'),null);
  assert.match(await page.locator('.study-media-status').innerText(),/No animation was published/);record('Missing clip is an honest still without zero-second controls');await page.close();

  let held;
  const delayed=await pageFor(page=>page.route(movieURL,route=>{held=route;}));
  await select(delayed,hip);await state(delayed,'loading');await select(delayed,still);await state(delayed,'still');
  if(held)await held.continue().catch(()=>{});
  await delayed.waitForTimeout(300);assert.equal(await delayed.locator('#fea-media').getAttribute('data-state'),'still');
  assert.ok(await delayed.locator('#feavid').isHidden());record('Changing case cancels pending animation without late takeover');await delayed.close();
  for(const fault of ['http','invalid']){
    let calls=0;
    const bad=await pageFor(page=>page.route(movieURL,route=>{calls++;return route.fulfill(fault==='http'?{status:503,body:'Unavailable'}:{contentType:route.request().url().includes('.webm')?'video/webm':'video/mp4',body:'Not a movie'});}));
    await select(bad,hip);await state(bad,'error');assert.ok(await bad.locator('.study-still').isVisible());assert.ok(await bad.locator('#feavid').isHidden());
    await bad.unroute(movieURL);await bad.locator('.study-retry').click();await state(bad,'ready');
    assert.ok(calls>0);await checkPlayback(bad);record(fault+' media failure retains image/report and retry restores playback');await bad.close();
  }
  const stale=await pageFor(page=>page.route('**/exports/leg/fea/media.json*',route=>{
    const changed=structuredClone(media);changed.cases['hip_frame/E1'].recorded.safety_factor=99;
    return route.fulfill({json:changed});
  }));
  await select(stale,hip);await state(stale,'error');assert.ok(await stale.locator('#feavid').isHidden());
  assert.equal(await stale.locator('#feanote a').count(),0,'Unbound fields cannot open as this case');
  assert.match(await stale.locator('#feanote').innerText(),/1\.65/);record('Stale result identity rejects animation and field link');await stale.close();
  const automatic=await pageFor(page=>page.emulateMedia({reducedMotion:'no-preference'}));
  await select(automatic,hip);await state(automatic,'ready');await automatic.locator('#fea-media').scrollIntoViewIfNeeded();
  await automatic.waitForFunction(()=>document.querySelector('#feavid').currentTime>.2);record('Muted autoplay works when reduced motion is not requested');await automatic.close();
  assert.deepEqual(errors,[]);assert.deepEqual(await json('/version.json'),version,'Single published build throughout test');
  await writeFile(`${out}/${engine.name()}-report.json`,JSON.stringify({base,version,cases,errors},null,2));
}catch(error){for(const [i,page] of context.pages().entries()){
  console.error('Media failure details',await page.locator('#feavid').evaluate(v=>({state:document.querySelector('#fea-media').dataset.state,
    canPlayH264:v.canPlayType('video/mp4; codecs="avc1.64001f"'),canPlayVP9:v.canPlayType('video/webm; codecs="vp9"'),
    currentSrc:v.currentSrc,readyState:v.readyState,networkState:v.networkState,duration:v.duration,error:v.error&&{code:v.error.code,message:v.error.message}})).catch(()=>null));
  await page.locator('#fea-media').scrollIntoViewIfNeeded().catch(()=>{});await page.screenshot({path:`${out}/${engine.name()}-failure-${i}.png`}).catch(()=>{});
}throw error;}
finally{await browser.close();}
