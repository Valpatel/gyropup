/** Initial hero feedback must survive the very import graph that failed. */
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {chromium,webkit} from '@playwright/test';
const base=(process.env.SITE_URL||'http://127.0.0.1:8892').replace(/\/$/,'');
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
const out=process.env.TEST_OUTPUT||'/tmp/gyropup-loading-hero';await mkdir(out,{recursive:true});
const errors=[],results=[];
let version;
async function fresh(viewport={width:320,height:568}){
 const context=await browser.newContext({viewport,reducedMotion:'reduce'});
 await context.addInitScript(()=>{localStorage.setItem('gyropup.probe','off');localStorage.setItem('gyropup-sfx','0');sessionStorage.setItem('gyropup.prototype-notice','2026-10-29-v1');});
 const page=await context.newPage();page.setDefaultTimeout(60000);page.on('pageerror',e=>errors.push(e.message));return {context,page};
}
const ready=page=>page.waitForFunction(()=>window.__heroPreview&&document.getElementById('robot-preview').dataset.ready==='true'&&document.getElementById('hero-loading').hidden);
const failed=page=>page.waitForFunction(()=>document.getElementById('hero-loading').dataset.state==='error');
async function layout(page){return page.evaluate(()=>{
 const status=document.getElementById('hero-loading'),poster=document.querySelector('.scene-fallback'),hero=document.querySelector('.hero-scene');
 const box=e=>{const r=e.getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height,right:r.right,bottom:r.bottom};};
 const lum=color=>{const c=color.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;});return .2126*c[0]+.7152*c[1]+.0722*c[2];};
 const style=getComputedStyle(status),a=lum(style.color),b=lum(style.backgroundColor);
 return {hero:box(hero),poster:box(poster),status:box(status),retry:box(status.querySelector('button')),contrast:(Math.max(a,b)+.05)/(Math.min(a,b)+.05),posterOpacity:getComputedStyle(poster).opacity,overflow:document.documentElement.scrollWidth>innerWidth+1};
});}
async function capture(page,name){
 await page.evaluate(()=>Promise.all([document.fonts.load('600 12px Inter'),document.fonts.load('600 10px "JetBrains Mono"')]));
 // An intentionally held module can keep WebKit's document.fonts.ready pending.
 const previous=process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY;process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY='1';
 try{await page.locator('.hero-scene').screenshot({path:`${out}/${engine.name()}-${name}.png`});}finally{if(previous===undefined)delete process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY;else process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY=previous;}
}
try{
 version=await(await fetch(base+'/version.json')).json();
 for(const [width,height] of [[1440,1000],[320,568],[844,390]]){
  const {context,page}=await fresh({width,height});let release,requested;const request=new Promise(resolve=>requested=resolve);
  await page.route('**/web/landing.js*',async route=>{await new Promise(resolve=>{release=resolve;requested();});await route.continue();});
  await page.goto(base+'/',{waitUntil:'domcontentloaded'});await request;
  await page.waitForFunction(()=>document.querySelector('.scene-fallback').naturalWidth===1024);await page.locator('.hero-scene').scrollIntoViewIfNeeded();
  const before=await layout(page);assert.equal(before.posterOpacity,'1');assert.equal(before.overflow,false);assert.ok(before.contrast>=4.5);
  assert.equal(await page.locator('#hero-loading').getAttribute('aria-busy'),'true');assert.match(await page.locator('#hero-loading-message').textContent(),/Loading/);
  assert.ok(await page.locator('#hero-loading').isVisible());assert.ok(await page.locator('#hero-loading button').isHidden());assert.equal(await page.locator('#robot-preview canvas').count(),0);
  assert.equal(await page.locator('.hero-loading-icon').evaluate(e=>getComputedStyle(e).animationName),'none','Reduced motion preserves static loading feedback');
  assert.ok(before.status.y>=before.poster.bottom&&before.status.bottom<=before.hero.bottom,'Status uses the caption band below the matching poster');
  await capture(page,`loading-${width}`);release();await ready(page);
  const after=await layout(page);assert.deepEqual(after.hero,before.hero);assert.deepEqual(after.poster,before.poster);
  const boxes=await page.evaluate(()=>[document.querySelector('.scene-fallback'),document.querySelector('#robot-preview canvas')].map(e=>{const r=e.getBoundingClientRect();return [r.x,r.y,r.width,r.height];}));assert.deepEqual(boxes[0],boxes[1]);
  await page.evaluate(()=>{window.heroIdentity=window.__heroPreview;document.querySelector('#hero-loading button').click();});
  await page.waitForTimeout(100);assert.ok(await page.evaluate(()=>window.heroIdentity===window.__heroPreview),'A stale retry cannot reload a usable scene');
  results.push({case:'delayed entry',width,height,...before});await context.close();
 }
 for(const mode of ['entry','dependency','geometry','webgl']){
  const {context,page}=await fresh();let failures=mode==='entry'?2:1;
  if(mode==='webgl')await context.addInitScript(()=>{if(sessionStorage.getItem('hero-webgl-attempt'))return;sessionStorage.setItem('hero-webgl-attempt','1');const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return /webgl/.test(type)?null:get.call(this,type,...args);};});
  else await page.route(mode==='entry'?'**/web/landing.js*':mode==='dependency'?'**/robot_v2.js*':'**/*.stl*',route=>{if(failures>0){failures--;return route.abort();}return route.continue();});
  await page.goto(base+'/',{waitUntil:'domcontentloaded'});await failed(page);await page.waitForFunction(()=>document.querySelector('.scene-fallback').naturalWidth===1024);await page.locator('.hero-scene').scrollIntoViewIfNeeded();
  for(let attempt=0;attempt<(mode==='entry'?2:1);attempt++){
   await failed(page);assert.equal(await page.locator('#hero-loading').getAttribute('aria-busy'),'false');assert.ok(await page.locator('#hero-loading button').isVisible());assert.equal(await page.locator('#robot-preview canvas').count(),0);
   assert.equal(await page.locator('.scene-fallback').evaluate(e=>getComputedStyle(e).opacity),'1');assert.ok(await page.locator('#hero-inspect').isDisabled());
   const measured=await layout(page);assert.ok(measured.retry.w>=44&&measured.retry.h>=44&&measured.retry.right<=measured.hero.right&&measured.status.y>=measured.poster.bottom&&!measured.overflow);
   if(attempt===0){await capture(page,`failed-${mode}`);results.push({case:mode,...measured});}
   await page.locator('#hero-loading button').focus();await Promise.all([page.waitForEvent('domcontentloaded'),page.keyboard.press('Enter')]);
   if(mode==='entry'&&attempt===0)await failed(page);
  }
  await ready(page);assert.equal(await page.locator('#robot-preview canvas').count(),1);assert.ok(await page.locator('#hero-loading').isHidden());await context.close();
 }
 const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:320,height:568}}),page=await nojs.newPage();await page.goto(base+'/');assert.ok(await page.locator('.hero-loading-static').isVisible());assert.ok(await page.locator('#hero-loading').isHidden());await nojs.close();
 assert.deepEqual(errors,[]);assert.deepEqual(await(await fetch(base+'/version.json')).json(),version,'The built site stayed unchanged during the suite');await writeFile(`${out}/${engine.name()}-report.json`,JSON.stringify({base,version,results,errors},null,2));
 console.log(`PASS ${engine.name()}: delayed hero feedback at3 layouts, matching poster/frame, entry/dependency/geometry/WebGL failure and real keyboard retry, repeated failure, no stale reset, reduced motion and no-JS fallback`);
}finally{await browser.close();}
