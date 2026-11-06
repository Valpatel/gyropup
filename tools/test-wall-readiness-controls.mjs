import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { acknowledgePrototypeNotice } from './test-prototype-session.mjs';
import { installRenderedReadiness } from './test-rendered-readiness.mjs';
import { loadWallPage } from './test-wall-readiness.mjs';
import { longestStretch, VISUAL, VIEWPORT } from './site-walls.mjs';

/** Exercise the actual loader and measure, with real native resource requests held at bounded test barriers. */
export async function wallReadinessControls(browser,base,root) {
  const contextFor=async()=>{const c=await browser.newContext({viewport:VIEWPORT,reducedMotion:'reduce'});await acknowledgePrototypeNotice(c);await installRenderedReadiness(c);await c.route('https://cad-agent.gyropup.com/**',r=>r.abort());return c;};
  const bound=async(promise,ms=40000)=>{let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Wall readiness control did not complete within its bound')),ms);})]);}finally{clearTimeout(timer);}};
  const geometry=page=>page.evaluate(selector=>{const wall=window.__wallMeasure(selector),article=document.querySelector('main.document article')||document.querySelector('article.prose')||document.querySelector('main'),r=article.getBoundingClientRect();return {...wall,articleWidth:r.width,articleHeight:r.height};},VISUAL);
  // The real published README requests its actual Stars URL. After the hold, a wider fixture proves stable geometry even when status dimensions change.
  {
    const context=await contextFor(),page=await context.newPage();
    let release,held=0,released=false,closing=false;const gate=new Promise(resolve=>{release=()=>{released=true;resolve();};});
    await page.route(url=>url.hostname==='img.shields.io'&&url.pathname==='/github/stars/Valpatel/gyropup',async route=>{held++;await gate;try{await route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="310" height="20"><rect width="310" height="20" fill="#444"/><text x="8" y="15" fill="white">Stars: wide future status</text></svg>'});}catch(error){if(!closing)throw error;}});
    const loading=(async()=>{await loadWallPage(page,base,'/site/pages/readme-md.html');await page.evaluate(`window.__wallMeasure=${longestStretch}`);return geometry(page);})();loading.catch(()=>{});
    try {
      const before=await bound(loading);assert.ok(held>0&&!released,'Actual README badge remains pending when measurement finishes');
      assert.equal(await page.locator('img.repo-badge').count(),7,'All seven status semantics retain explicit boxes');
      const sizes=await page.locator('img.repo-badge').evaluateAll(images=>images.map(img=>({width:img.getBoundingClientRect().width,height:img.getBoundingClientRect().height,complete:img.complete})));
      assert.ok(sizes.every(s=>s.width>0&&s.height===20),'Published badges reserve fixed, small geometry');
      release();
      await page.waitForFunction(()=>[...document.querySelectorAll('img.repo-badge')].filter(img=>img.src.includes('/github/stars/')).every(img=>img.complete&&img.naturalWidth>0),null,{timeout:30000});
      await page.evaluate(async()=>{await document.querySelector('img.repo-badge[src*="/github/stars/"]').decode();await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));});
      assert.deepEqual(await geometry(page),before,'Actual README article and wall geometry remain identical after badge decode');
    } finally {closing=true;release();await context.close();await loading.catch(()=>{});}
  }
  for(const kind of ['font','lazy-primary','missing-primary','stylesheet-error']) {
    const context=await contextFor(),page=await context.newPage();let release,requested,measured=false,closing=false;
    const gate=new Promise(resolve=>{release=resolve;}),seen=new Promise(resolve=>{requested=resolve;});
    const route='/__wall-readiness-control',font=kind==='font',primary=kind==='lazy-primary'||kind==='missing-primary';
    const html='<!doctype html><meta name="viewport" content="width=device-width">'
      +(kind==='stylesheet-error'?'<link rel="stylesheet" href="/__wall-failed.css">':'')
      +`<style>body{margin:0;font:16px/1.5 system-ui}${font?'@font-face{font-family:WallControl;src:url(/__wall-font.woff2)}body{font-family:WallControl}':''}</style>`
      +`<main class="document"><article><h1>Wall readiness</h1><p style="height:${primary?12000:300}px">${'Actual rendered text. '.repeat(20)}</p>`
      +(primary?'<img loading="lazy" src="/__wall-primary.svg" alt="Primary evidence with unknown intrinsic dimensions">':'')+'</article></main>';
    await page.route(base+route,r=>r.fulfill({contentType:'text/html',body:html}));
    await page.route(base+'/__wall-failed.css',r=>r.fulfill({status:404,contentType:'text/css',body:''}));
    await page.route(base+'/__wall-primary.svg',async r=>{requested();if(kind==='missing-primary')return r.fulfill({status:404,body:''});await gate;try{await r.abort();}catch(error){if(!closing)throw error;}});
    await page.route(base+'/__wall-font.woff2',async r=>{requested();await gate;try{await r.fulfill({contentType:'font/woff2',body:await readFile(path.join(root,'designer/kit/vendor/fonts/inter.woff2'))});}catch(error){if(!closing)throw error;}});
    const loading=(async()=>{await loadWallPage(page,base,route);const wall=await page.evaluate(longestStretch,VISUAL);measured=true;return wall;})();loading.catch(()=>{});
    try {
      if(font||primary)await bound(seen,30000);
      if(font) {
        assert.equal(measured,false,'Actual rendered font blocks wall measurement');
        assert.equal(await page.evaluate(()=>[...document.fonts].some(face=>face.family==='WallControl'&&face.status==='loading')),true);
        release();await bound(loading);
        assert.equal(await page.evaluate(()=>document.fonts.check('16px WallControl')),true,'Actual font decoded before measurement');
      } else {
        if(kind==='lazy-primary')assert.equal(await page.locator('img').evaluate(img=>img.getBoundingClientRect().top>innerHeight&&!img.hasAttribute('width')&&!img.hasAttribute('height')),true,'Held unknown-size lazy primary is offscreen');
        let error;try{await bound(loading);}catch(e){error=e;}
        assert.ok(error,`${kind} must fail readiness`);assert.equal(measured,false,`${kind} fails before any wall measurement`);
        assert.match(error.message,kind==='stylesheet-error'?/Stylesheet failed to load/:kind==='missing-primary'?/Primary image failed to load/:/Timeout 30000ms/);
      }
    } finally {closing=true;release();await context.close();await loading.catch(()=>{});}
  }
  console.log('walls readiness controls: real pending README badge preserves geometry; actual font awaited; offscreen lazy held/missing primary and failed stylesheet reject before measurement');
}
