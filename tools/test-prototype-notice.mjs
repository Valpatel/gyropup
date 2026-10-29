/** Fresh-entry warning, native focus, retained scene, audio gates and static agent content. */
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { chromium, webkit } from '@playwright/test';
const base=(process.env.SITE_URL||'http://127.0.0.1:8891').replace(/\/$/,'');
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
const out=process.env.TEST_OUTPUT||'/tmp/gyropup-prototype-notice';await mkdir(out,{recursive:true});
const errors=[],results=[];
function preferences(){
 localStorage.setItem('gyropup.probe','off');localStorage.setItem('gyropup-sfx','1');localStorage.setItem('gyropup-sfx-volume','.23');localStorage.setItem('gyropup.muted','0');
 window.noticeVoice={spoken:[],cancelled:0};
 Object.defineProperty(window,'SpeechSynthesisUtterance',{configurable:true,value:class{constructor(text){this.text=text;}}});
 Object.defineProperty(window,'speechSynthesis',{configurable:true,value:{getVoices:()=>[],speak(u){window.noticeVoice.spoken.push(u.text);},cancel(){window.noticeVoice.cancelled++;}}});
 const AC=window.AudioContext||window.webkitAudioContext;window.noticeAudio=[];
 if(AC){window.AudioContext=function(...args){const context=new AC(...args),gains=[],create=context.createGain.bind(context);context.createGain=()=>{const g=create();gains.push(g);return g;};window.noticeAudio.push({context,gains});return context;};window.AudioContext.prototype=AC.prototype;}
}
async function pageFor(options={}){const context=await browser.newContext(options);await context.addInitScript(preferences);const page=await context.newPage();page.setDefaultTimeout(60000);page.on('pageerror',e=>errors.push(e.message));return {context,page};}
async function noticeOpen(page){await page.waitForFunction(()=>document.getElementById('prototype-notice-dialog')?.open);}
async function measure(page){return page.evaluate(()=>{
 const d=document.getElementById('prototype-notice-dialog'),c=d.querySelector('.prototype-notice-content'),a=document.getElementById('prototype-notice-ack');
 const box=e=>{const r=e.getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height,right:r.right,bottom:r.bottom};};
 return {dialog:box(d),ack:box(a),content:box(c),overflow:document.documentElement.scrollWidth>innerWidth+1,modal:d.matches(':modal')};
});}
try{
 const {context,page}=await pageFor({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 await page.goto(base+'/',{waitUntil:'networkidle'});await noticeOpen(page);
 assert.match(await page.locator('#prototype-notice-dialog').textContent(),/death.*property/s);
 assert.match(await page.locator('#prototype-notice-dialog').textContent(),/will not be offered for sale/);
 assert.match(await page.locator('#prototype-notice-dialog').textContent(),/proper training/);
 await page.waitForFunction(()=>window.__heroPreview);
 const clock=await page.evaluate(()=>window.__heroPreview.activity.seconds);
 await page.evaluate(()=>new Promise(resolve=>{let n=0;function frame(){if(++n===4)resolve();else requestAnimationFrame(frame);}requestAnimationFrame(frame);}));
 assert.equal(await page.evaluate(()=>window.__heroPreview.activity.seconds),clock,'Entry warning does not consume the first greeting');
 for(const [width,height] of [[1440,1000],[768,1024],[320,568],[390,844],[568,320],[844,390]]){
  await page.setViewportSize({width,height});const m=await measure(page);
  assert.ok(m.modal&&!m.overflow&&m.dialog.x>=0&&m.dialog.y>=0&&m.dialog.right<=width+1&&m.dialog.bottom<=height+1,JSON.stringify(m));
  assert.ok(m.ack.w>=44&&m.ack.h>=44&&m.ack.bottom<=height&&m.content.h>40,`Scrollable notice and reachable acknowledgement ${width}: ${JSON.stringify(m)}`);
  await page.screenshot({path:`${out}/${engine.name()}-entry-${width}.png`});results.push({width,height,...m});
 }
 await page.setViewportSize({width:390,height:844});await page.keyboard.press('Escape');assert.equal(await page.locator('#prototype-notice-dialog').evaluate(e=>e.open),true);
 for(let i=0;i<10;i++){await page.keyboard.press(i%2?'Shift+Tab':'Tab');assert.ok(await page.evaluate(()=>document.getElementById('prototype-notice-dialog').contains(document.activeElement)),'Native modal contains keyboard focus');}
 await page.waitForFunction(()=>window.__heroPreview);
 await page.evaluate(()=>{window.keptHero=window.__heroPreview.robot;window.__heroPreview.talk.say('Blocked before acknowledgement');});
 assert.deepEqual(await page.evaluate(()=>window.noticeVoice.spoken),[]);
 await page.locator('#prototype-notice-ack').focus();await page.keyboard.press('Enter');
 await page.waitForFunction(()=>!document.getElementById('prototype-notice-dialog').open);
 assert.equal(await page.evaluate(()=>sessionStorage.getItem('gyropup.prototype-notice')),'2026-10-29-v1');
 assert.ok(await page.evaluate(()=>window.keptHero===window.__heroPreview.robot));
 const targetCopy=await page.locator('.hero-description').textContent();assert.match(targetCopy,/100 lb/);assert.match(targetCopy,/\$10,000/);
 await page.locator('#prototype-notice-footer [data-prototype-notice-open]').click();await noticeOpen(page);await page.keyboard.press('Escape');
 await page.waitForFunction(()=>!document.getElementById('prototype-notice-dialog').open);
 assert.equal(await page.evaluate(()=>document.activeElement.hasAttribute('data-prototype-notice-open')),true,'Reopening restores focus');
 for(const route of ['/designer/sim.html?run=none&demo=0&sound=1','/designer/character/talk-demo.html','/site/']){
  await page.goto(base+route,{waitUntil:'networkidle'});assert.equal(await page.locator('#prototype-notice-dialog').evaluate(e=>e.open),false,'Same session remains acknowledged');
  if(route.includes('sim.html'))await page.waitForFunction(()=>document.body.dataset.ready==='1');
  if(route.includes('talk-demo'))await page.waitForFunction(()=>window.__talkDemo);
  const reopen=page.locator('button[data-prototype-notice-open]:visible').first();assert.ok(await reopen.isVisible(),`Notice can reopen on ${route}`);
  await reopen.click();await noticeOpen(page);await page.locator('#prototype-notice-ack').click();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 }
 // FEA creates its full-screen HUD only after a report fetch. A notice that
 // classifies the page once at startup can leave its footer over the controls.
 let releaseFea,seenFea;const feaRequested=new Promise(resolve=>seenFea=resolve);
 await page.route('**/exports/fea/thigh-T1.json*',async route=>{await new Promise(resolve=>{releaseFea=resolve;seenFea();});await route.continue();});
 await page.goto(base+'/designer/kit/fea.html?case=../../exports/fea/thigh-T1.json',{waitUntil:'domcontentloaded'});
 await feaRequested;await page.waitForFunction(()=>document.documentElement.dataset.prototypeNoticeOpen==='false');
 assert.equal(await page.evaluate(()=>!!window.__fea),false,'Report is deliberately held before HUD creation');releaseFea();
 await page.waitForFunction(()=>window.__fea&&document.body.dataset.prototypeEnhanced==='true'&&document.body.dataset.prototypeFullscreen==='true');
 assert.equal(await page.locator('#prototype-notice-footer').isVisible(),false,'Full footer leaves the late-created viewer controls clear');
 await page.getByRole('button',{name:'SHOW PANEL',exact:true}).click();await page.locator('[data-a=max]').click();
 await page.locator('button[data-prototype-notice-open]:visible').click();await noticeOpen(page);await page.locator('#prototype-notice-ack').click();
 await page.screenshot({path:`${out}/${engine.name()}-late-fea.png`});
 await context.close();

 // A direct simulator entry is gated too; reopening releases held controls and
 // silences existing output without resetting the robot/conversation/preferences.
 const direct=await pageFor({viewport:{width:1280,height:900}}),p=direct.page;
 await p.goto(base+'/designer/sim.html?design=turret-box&run=none&demo=0&sound=1',{waitUntil:'networkidle'});await noticeOpen(p);
 await p.waitForFunction(()=>window.__sim?.bench()?.active&&window.__sim.talk);
 await p.evaluate(()=>{const s=window.__sim;window.kept={scene:s.stage.scene,talk:s.talk,bench:s.bench()};s.talk.say('Blocked direct entry');});
 assert.deepEqual(await p.evaluate(()=>window.noticeVoice.spoken),[]);
 await p.keyboard.press('Space');await p.keyboard.press('f');
 assert.equal(await p.evaluate(()=>window.__sim.bench().api.state.shots),0,'Modal keys do not fire the scene');
 await p.locator('#prototype-notice-ack').click();
 await p.evaluate(()=>{const s=window.__sim;window.sfxContext=s.sfx.unlock();s.talk.say('Audible after acknowledgement');});
 await p.waitForFunction(()=>window.noticeVoice.spoken.includes('Audible after acknowledgement'));
 const prefs=await p.evaluate(()=>[localStorage.getItem('gyropup-sfx'),localStorage.getItem('gyropup-sfx-volume'),localStorage.getItem('gyropup.muted')]);
 await p.locator('#app canvas').click({position:{x:300,y:300}});await p.keyboard.down('Space');await p.keyboard.down('ArrowLeft');
 await p.waitForFunction(()=>window.__sim.bench().api.state.arm.size>0);
 await p.locator('button[data-prototype-notice-open]:visible').first().click();await noticeOpen(p);
 const gated=await p.evaluate(()=>{const s=window.__sim,b=s.bench().api.state;return{arm:b.arm.size,keys:b.keys.size,trigger:b.trigger,voice:s.talk.audio.voiceVolume,output:window.noticeAudio.find(x=>x.context===window.sfxContext)?.gains[0]?.gain.value,identity:s.stage.scene===window.kept.scene&&s.talk===window.kept.talk&&s.bench()===window.kept.bench};});
 assert.deepEqual(gated,{arm:0,keys:0,trigger:false,voice:0,output:0,identity:true});
 await p.keyboard.up('Space');await p.keyboard.up('ArrowLeft');
 const spoken=await p.evaluate(()=>window.noticeVoice.spoken.length);await p.evaluate(()=>window.__sim.talk.say('Blocked reopened warning'));
 assert.equal(await p.evaluate(()=>window.noticeVoice.spoken.length),spoken);
 assert.deepEqual(await p.evaluate(()=>[localStorage.getItem('gyropup-sfx'),localStorage.getItem('gyropup-sfx-volume'),localStorage.getItem('gyropup.muted')]),prefs);
 await p.locator('#prototype-notice-ack').click();assert.ok(await p.evaluate(()=>window.__sim.talk.audio.voiceVolume>0));
 await direct.context.close();

 // Old acknowledgements and denied session storage cannot silently skip entry.
 for(const mode of ['old','blocked']){
  const test=await pageFor({viewport:{width:320,height:568}});
  await test.context.addInitScript(mode=>{if(mode==='old')sessionStorage.setItem('gyropup.prototype-notice','old');else{const get=Storage.prototype.getItem,set=Storage.prototype.setItem;Storage.prototype.getItem=function(k){if(this===sessionStorage)throw new DOMException('Denied','SecurityError');return get.call(this,k);};Storage.prototype.setItem=function(k,v){if(this===sessionStorage)throw new DOMException('Denied','SecurityError');return set.call(this,k,v);};}},mode);
  await test.page.goto(base+'/site/',{waitUntil:'networkidle'});await noticeOpen(test.page);await test.page.locator('#prototype-notice-ack').click();assert.equal(await test.page.locator('#prototype-notice-dialog').evaluate(e=>e.open),false);await test.context.close();
 }
 const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:320,height:568}}),staticPage=await nojs.newPage();
 for(const route of ['/','/designer/sim.html','/site/']){await staticPage.goto(base+route);const footer=staticPage.locator('#prototype-notice-footer');await footer.scrollIntoViewIfNeeded();assert.ok(await footer.isVisible());assert.match(await footer.textContent(),/research purposes only/);}
 await nojs.close();
 for(const route of ['/index.md','/designer/sim.md','/designer/build.md','/site/index.md']){
  const response=await browser.newPage();try{const r=await response.request.get(base+route);assert.equal(r.status(),200);const text=await r.text();assert.match(text,/will not be offered for sale/);assert.match(text,/research purposes only/);}finally{await response.close();}
 }
 assert.deepEqual(errors,[]);
 await writeFile(`${out}/${engine.name()}-report.json`,JSON.stringify({base,results,errors},null,2));
 console.log(`PASS ${engine.name()}: fresh/direct entry, 6 layouts, native focus/acknowledgement, session/version/storage failure, retained scene, held-input release, speech/SFX gates, static/Markdown warnings`);
}finally{await browser.close();}
