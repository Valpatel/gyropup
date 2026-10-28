/** Browser regression checks against the real static site (SITE_URL selects local or production). */
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { chromium } from '@playwright/test';
const base = (process.env.SITE_URL || 'http://127.0.0.1:8764').replace(/\/$/,'');
const browser = await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL || 'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const context = await browser.newContext({viewport:{width:390,height:844},hasTouch:true,deviceScaleFactor:1});
const page = await context.newPage();
const errors=[],missing=[],results=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('response',r=>{if(r.status()>=400 && r.url().startsWith(base) && !r.url().includes('/_cadagent/')) missing.push({status:r.status(),url:r.url()});});
const portrait = [[320,568],[360,640],[375,667],[390,844],[393,852],[412,915],[414,896],[430,932],[480,960]];
const sizes=[...portrait,...portrait.map(([w,h])=>[h,w]),[768,1024],[1024,768],[1440,1000]];
await mkdir('test-results',{recursive:true});
try {
 for(const route of ['/','/designer/sim.html','/designer/progress.html','/designer/build.html','/site/']) {
  await page.goto(base+route,{waitUntil:'networkidle'});
  if(route==='/') await page.waitForSelector('#robot-preview[data-ready="true"]');
  if(route.includes('sim.html')) await page.waitForFunction(()=>document.body.dataset.ready==='1');
  if(route.includes('progress')) await page.waitForSelector('#status .card');
  if(route!=='/') await page.waitForSelector('.appnav');
  for(const [width,height] of sizes) {
   await page.setViewportSize({width,height});
   await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
   const metrics=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,height:innerHeight,nav:document.querySelector('.site-header,.appnav')?.getBoundingClientRect().height}));
   assert.ok(metrics.scroll<=width+1,`${route} overflows ${width}×${height}: ${metrics.scroll}`);
   if(route.includes('sim.html')) {
    const canvas=await page.locator('#app canvas').boundingBox();
    assert.ok(canvas.width>=width-1 && canvas.height>100,'Simulator canvas missing');
    if(width<900) {
      const drawer=page.locator('#drawer-handle');assert.ok(await drawer.isVisible(),`Missing drawer at ${width}×${height}`);
      await drawer.click();assert.equal(await drawer.getAttribute('aria-expanded'),'true');
      await drawer.click();assert.equal(await drawer.getAttribute('aria-expanded'),'false');
    }
   }
   if(route!=='/' && width<=760) {
    await page.getByRole('button',{name:'Menu'}).click();
    assert.ok(await page.locator('.nav-links').isVisible());
    assert.ok(await page.getByRole('link',{name:'Home',exact:true}).isVisible());
    await page.keyboard.press('Escape');
    assert.equal(await page.getByRole('button',{name:'Menu'}).getAttribute('aria-expanded'),'false');
   }
   results.push({route,width,height,pass:true});
  }
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:`test-results/${route==='/'?'landing':route.replaceAll('/','-')}-phone.png`,fullPage:route==='/'});
 }
 // Exercise actual simulator behavior: replay, live pose, shots, and the standalone turret.
 await page.goto(base+'/designer/sim.html?run=none&sound=0',{waitUntil:'networkidle'});
 await page.waitForFunction(()=>document.body.dataset.ready==='1');
 await page.evaluate(()=>window.__sim.setHeight(.25));
 assert.equal(await page.evaluate(()=>window.__sim.state.height),.25);
 await page.selectOption('#run-select','v2/drive');
 await page.waitForFunction(()=>window.__sim.state.replay?.key==='v2/drive');
 await page.selectOption('#run-select','');
 await page.waitForFunction(()=>window.__sim.state.replay===null);
 await page.locator('#drawer-handle').click();
 const turretSection=page.locator('details').filter({has:page.locator('summary',{hasText:'Turret'})}).first();
 if(await turretSection.count() && !await turretSection.getAttribute('open')) await turretSection.locator('summary').click();
 await page.getByRole('button',{name:'FIRE',exact:true}).click();
 await page.locator('#drawer-handle').click();
 await page.selectOption('#design-select','turret-box');
 await page.waitForFunction(()=>window.__sim.state.bench===true);
 await page.screenshot({path:'test-results/turret-phone.png'});
 assert.equal(errors.length,0,`Browser errors: ${errors.join('; ')}`);
 assert.equal(missing.length,0,`Missing assets: ${JSON.stringify(missing)}`);
 // Verify static downloads and generated doc anchors survive Cloudflare's URL normalization.
 const response=await context.request.get(base+'/exports/leg/leg_stand.step');assert.equal(response.status(),200);
 const doc=await context.request.get(base+'/site/pages/docs-leg-prototype-plan-md.html');assert.ok((await doc.text()).includes('id="62-'));
 const notFound=await context.request.get(base+'/not-a-real-gyropup-file.json');assert.equal(notFound.status(),404);
 await writeFile('test-results/report.json',JSON.stringify({base,checkedAt:new Date().toISOString(),results,errors,missing},null,2));
 console.log(`PASS ${results.length} responsive page checks; simulator replay, pose, fire, turret, menus, download, doc anchor, and real 404. ${base}`);
} finally { await browser.close(); }
