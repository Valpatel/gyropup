import {sourceForPublic} from '../../../tools/site/source-layout.mjs';
import { acknowledgePrototypeNotice } from '../content/test-prototype-session.mjs';
/** Master audio gates both synthesis backends without erasing voice-only preferences. */
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { chromium, webkit } from '@playwright/test';
const engine = process.env.PLAYWRIGHT_BROWSER === 'webkit' ? webkit : chromium;
const browser = await engine.launch(engine === chromium ? {channel:process.env.PLAYWRIGHT_CHANNEL === 'chromium' ? undefined : 'chrome',headless:true,
  args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']} : {headless:true});
const root = new URL('../../../', import.meta.url), base=(process.env.SITE_URL || 'http://127.0.0.1:8882').replace(/\/$/,'');
const errors=[];
function browserVoice() {
 localStorage.setItem('gyropup.probe','off');
 window.audioTest={spoken:[],cancelled:0,active:null};
 Object.defineProperty(window,'SpeechSynthesisUtterance',{configurable:true,value:class {constructor(text){this.text=text;}}});
 Object.defineProperty(window,'speechSynthesis',{configurable:true,value:{getVoices:()=>[],speak(u){window.audioTest.spoken.push(u);window.audioTest.active=u;},cancel(){window.audioTest.cancelled++;const old=window.audioTest.active;window.audioTest.active=null;old?.onend?.();}}});
}
async function remoteVoice() {
 const context=await browser.newContext();await context.addInitScript(browserVoice);
await acknowledgePrototypeNotice(context);
 await context.addInitScript(()=>{
  window.remoteAudio={started:0,stopped:0,gains:[]};
  class AudioContext {
   state='running';destination={};resume(){return Promise.resolve();}decodeAudioData(){return Promise.resolve({});}
   createGain(){const node={gain:{value:0},connect(){return this;}};window.remoteAudio.gains.push(node);return node;}
   createBufferSource(){return {playbackRate:{value:1},connect(node){return node;},start(){window.remoteAudio.started++;},stop(){window.remoteAudio.stopped++;this.onended?.();}};}
  }
  Object.defineProperty(window,'AudioContext',{value:AudioContext,configurable:true});
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 let release, waiting;
 const html=`<!doctype html><script type="importmap">{"imports":{"three":"/designer/kit/vendor/three/three.module.min.js"}}</script><script type="module">
 import { mountTalk } from '/designer/character/talk.js';
 window.talk=mountTalk({stage:{onFrame(){}},getHead:()=>null,audio:{enabled:true,volume:.4}});
 await window.talk.detect();Object.assign(window.talk.services.tts,{ok:true,base:location.origin});
 window.audioReady=true;</script>`;
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url());
  if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:html});
  if(url.pathname.startsWith('/designer/'))return route.fulfill({contentType:url.pathname.endsWith('.css')?'text/css':'text/javascript',body:await readFile(new URL(sourceForPublic(url.pathname.slice(1)),root))});
  if(url.pathname==='/tts'){
   if(url.searchParams.get('text')==='Delayed reply') {waiting=true;await new Promise(resolve=>{release=resolve;});}
   return route.fulfill({contentType:'audio/wav',body:Buffer.from([0])}); // Decoder is a deterministic adapter; no voice service is contacted.
  }
  throw new Error('Unexpected speech request: '+url.href);
 });
 try {
  await page.goto('https://speech.example.test');await page.waitForFunction(()=>window.audioReady);
  await page.evaluate(()=>window.talk.setMuted(false));
  assert.equal(await page.evaluate(()=>window.talk.say('Remote speech')),true);
  assert.ok(Math.abs(await page.evaluate(()=>window.remoteAudio.gains.at(-1).gain.value)-.22)<1e-9);
  await page.evaluate(()=>window.talk.setAudio({volume:.2}));
  assert.ok(Math.abs(await page.evaluate(()=>window.remoteAudio.gains.at(-1).gain.value)-.11)<1e-9,'Remote speech volume changes while playing');
  await page.evaluate(()=>window.talk.setAudio({enabled:false}));
  assert.equal(await page.evaluate(()=>window.remoteAudio.stopped),1,'Master mute stops remote playback immediately');
  assert.equal(await page.evaluate(()=>window.talk.audio.voiceVolume),0);
  await page.evaluate(()=>{window.talk.setAudio({enabled:true});window.pendingVoice=window.talk.say('Delayed reply');});
  for(let i=0;i<100&&!waiting;i++)await page.waitForTimeout(10);
  assert.ok(waiting,'Remote response is pending');
  await page.evaluate(()=>{window.talk.setAudio({volume:0});window.talk.setAudio({volume:.4});});
  release();await page.evaluate(()=>window.pendingVoice);
  assert.equal(await page.evaluate(()=>window.remoteAudio.started),1,'A response muted while loading never revives after unmute');
  await page.evaluate(()=>{window.talk.setMuted(true);window.talk.setAudio({enabled:false});window.talk.setAudio({enabled:true});});
  assert.equal(await page.evaluate(()=>window.talk.audio.muted && window.talk.audio.voiceVolume===0 && localStorage.getItem('gyropup.muted')==='1'),true);
 } finally {release?.();await context.close();}
}
// Fixed lines play their recorded clip; any other line is spoken live through the pronunciation key, while the bubble
// keeps the written text (designer/character/pronunciation.json, voice/manifest.json).
async function pronunciation() {
 const context=await browser.newContext({reducedMotion:'reduce'});await context.addInitScript(browserVoice);
 await acknowledgePrototypeNotice(context);
 await context.addInitScript(()=>{
  window.remoteAudio={started:0};
  class AudioContext {
   state='running';destination={};resume(){return Promise.resolve();}decodeAudioData(){return Promise.resolve({});}
   createGain(){return {gain:{value:0},connect(){return this;}};}
   createBufferSource(){return {playbackRate:{value:1},connect(node){return node;},start(){window.remoteAudio.started++;},stop(){this.onended?.();}};}
  }
  Object.defineProperty(window,'AudioContext',{value:AudioContext,configurable:true});
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 const html=`<!doctype html><script type="importmap">{"imports":{"three":"/designer/kit/vendor/three/three.module.min.js"}}</script><script type="module">
 import { mountTalk } from '/designer/character/talk.js';
 window.talk=mountTalk({stage:{onFrame(){}},getHead:()=>null,audio:{enabled:true,volume:.4},dock:false});
 await window.talk.detect();window.audioReady=true;</script>`;
 const requests=[];
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url());requests.push(url.pathname+url.search);
  if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:html});
  if(url.pathname.startsWith('/designer/'))return route.fulfill({contentType:url.pathname.endsWith('.css')?'text/css':url.pathname.endsWith('.mp3')?'audio/mpeg':'text/javascript',body:await readFile(new URL(sourceForPublic(url.pathname.slice(1)),root))});
  if(url.pathname==='/tts')return route.fulfill({contentType:'audio/wav',body:Buffer.from([0])});
  throw new Error('Unexpected speech request: '+url.href);
 });
 const manifest=JSON.parse(await readFile(new URL(sourceForPublic('designer/character/voice/manifest.json'),root),'utf8'));
 const bubble=()=>page.evaluate(()=>document.querySelector('.gp-bubble .gp-text').textContent);
 try {
  await page.goto('https://speech.example.test');await page.waitForFunction(()=>window.audioReady);
  await page.evaluate(()=>window.talk.setMuted(false));
  // A fixed line: its clip, no live voice at all.
  assert.equal(await page.evaluate(()=>window.talk.say('Hi! I am Gyropup!')),true);
  assert.equal(await bubble(),'Hi! I am Gyropup!');
  assert.ok(requests.includes('/designer/character/voice/'+manifest.lines['Hi! I am Gyropup!'].clip),'Fixed line plays its recorded clip');
  assert.equal(manifest.lines['Hi! I am Gyropup!'].spoken,'Hi! I am gyro pup!');
  assert.equal(requests.filter(r=>r.startsWith('/tts')).length+await page.evaluate(()=>window.audioTest.spoken.length),0,'No live speech for a recorded line');
  // A live line through the sidecar: the request carries the key's text, the bubble the written one.
  await page.evaluate(()=>Object.assign(window.talk.services.tts,{ok:true,base:location.origin}));
  assert.equal(await page.evaluate(()=>window.talk.say("Gyropup's turret is ready, see gyropup.com")),true);
  assert.equal(await bubble(),"Gyropup's turret is ready, see gyropup.com");
  const tts=requests.filter(r=>r.startsWith('/tts')).map(r=>new URL(r,'https://x.test').searchParams.get('text'));
  assert.deepEqual(tts,["gyro pup's turret is ready, see gyropup.com"],'Sidecar is sent the pronounced text');
  // The same live line through browser speech.
  await page.evaluate(()=>{window.talk.services.tts.ok=false;});
  assert.equal(await page.evaluate(()=>window.talk.say('Two Gyropups, one Tritium team')),true);
  assert.equal(await bubble(),'Two Gyropups, one Tritium team');
  assert.equal(await page.evaluate(()=>window.audioTest.active.text),'Two gyro pups, one Trittium team','Browser speech is sent the pronounced text');
 } finally {await context.close();}
}
async function firstMountSoundOverride({startupDelayMs=0}={}) {
 const context=await browser.newContext({viewport:{width:1200,height:900}});
 await context.addInitScript(browserVoice);await acknowledgePrototypeNotice(context);
 await context.addInitScript(()=>{localStorage.setItem('gyropup-sfx','1');localStorage.setItem('gyropup-sfx-volume','.3');localStorage.setItem('gyropup.muted','0');});
 const page=await context.newPage(),started=performance.now(),timeline=[],pending=new Map(),pageErrors=[];
 const mark=event=>timeline.push({event,ms:Math.round(performance.now()-started)});
 page.on('pageerror',e=>{errors.push(e.message);pageErrors.push(e.message);});
 page.on('request',request=>pending.set(request,new URL(request.url()).pathname));
 page.on('requestfinished',request=>pending.delete(request));page.on('requestfailed',request=>pending.delete(request));
 let release,signalHeld,timer,releaseStartup,startupTimer,startupHeldAt,startupReleasedAt,coreBudget;
 const gate=new Promise(resolve=>{release=resolve;});
 const held=new Promise(resolve=>{signalHeld=resolve;});
 const startupGate=new Promise(resolve=>{releaseStartup=resolve;});
 if(startupDelayMs)await page.route(url=>url.pathname==='/designer/sim.js',async route=>{
  startupHeldAt=performance.now();mark('startup requested');
  startupTimer=setTimeout(()=>{startupReleasedAt=performance.now();mark('startup released');releaseStartup();},startupDelayMs);
  await startupGate;await route.continue();mark('startup continued');
 });
 const gamepadPath=url=>url.pathname==='/designer/sim_gamepad.js';
 await page.route(gamepadPath,async route=>{mark('gamepad requested');signalHeld();await gate;await route.continue();});
 try {
  await page.goto(base+'/designer/sim.html?run=none&sound=0',{waitUntil:'commit'});
  mark('navigation committed');
  // Core startup precedes this optional import; its existing readiness bound is a separate phase.
  mark('talk readiness started');
  const talkStarted=performance.now();
  await page.waitForFunction(()=>window.__sim?.talk,null,{timeout:startupDelayMs?48000:30000});
  const talkEnded=performance.now();
  mark('talk ready');
  if(startupDelayMs) {
   assert.ok(Number.isFinite(startupHeldAt) && Number.isFinite(startupReleasedAt),'The actual startup gate was requested and released');
   const holdMs=startupReleasedAt-startupHeldAt;
   assert.ok(holdMs>=17000 && holdMs<=18000,'The measured injected hold stays within its 17–18 second window');
   // Exclude only the measured intersection; request continuation/network work stays in the genuine core budget.
   const excludedMs=Math.max(0,Math.min(talkEnded,startupReleasedAt)-Math.max(talkStarted,startupHeldAt));
   coreBudget={talkMs:talkEnded-talkStarted,holdMs,excludedMs,genuineCoreMs:talkEnded-talkStarted-excludedMs};
   assert.ok(coreBudget.genuineCoreMs<=30000,'Actual core readiness, excluding only verified injected hold, stays within 30 seconds');
  }
  await Promise.race([held,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('The gamepad import was not held')),15000);})]);
  clearTimeout(timer);
  mark('optional import held');
  assert.equal(await page.evaluate(()=>!window.__sim.sfx.enabled && window.__sim.talk.audio.voiceVolume===0),true,'Query mute applies at first talk mount while optional gamepad import is held');
  assert.match(await page.locator('#topbar button').filter({hasText:/SOUND/}).textContent(),/SOUND OFF/);
  release();
  await page.waitForFunction(()=>document.body.dataset.ready==='1');
  assert.equal(await page.evaluate(()=>!window.__sim.sfx.enabled && window.__sim.talk.audio.voiceVolume===0),true,'Query mute remains after optional initialization');
  if(startupDelayMs)console.log('audio startup timing',JSON.stringify({startupDelayMs,coreBudget,timeline}));
 } catch(error) {
  const state=await page.evaluate(()=>({document:document.readyState,ready:document.body?.dataset.ready,sim:!!window.__sim,robot:!!window.__sim?.state?.robot,talk:!!window.__sim?.talk})).catch(()=>null);
  console.error('audio first-mount failure',JSON.stringify({startupDelayMs,coreBudget,timeline,pending:[...pending.values()],state,pageErrors}));throw error;
 } finally {clearTimeout(timer);clearTimeout(startupTimer);releaseStartup();release();await context.close();}
}
async function siteControls() {
 const context=await browser.newContext({viewport:{width:1200,height:900}});await context.addInitScript(browserVoice);
await acknowledgePrototypeNotice(context);
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 if(process.env.AUDIO_SOURCE==='1')await page.route('**/designer/**',async route=>{
  const p=new URL(route.request().url()).pathname;
  if(['/designer/sim.js','/designer/sfx.js','/designer/character/talk.js','/designer/character/talk-demo.html'].includes(p))return route.fulfill({contentType:p.endsWith('.html')?'text/html':'text/javascript',body:await readFile(new URL(sourceForPublic(p.slice(1)),root))});
  return route.continue();
 });
 try {
  for(const design of ['v2','turret-box','talk']) {
   await page.goto(base+(design==='talk'?'/designer/character/talk-demo.html':`/designer/sim.html?design=${design}&run=none&demo=0&alive=0&sound=1`),{waitUntil:'networkidle'});
   await page.waitForFunction(()=>window.__sim?.talk || window.__talk);
   await page.evaluate(()=>{window.testTalk=window.__sim?.talk || window.__talk;window.testSfx=window.__sim?.sfx || window.__sfx;window.testSfx.setEnabled(true);window.testTalk.setMuted(false);});
   const volume=page.locator('.hud-slider').filter({hasText:'Volume'}).locator('input');
   await volume.evaluate(el=>{el.value='.4';el.dispatchEvent(new Event('input',{bubbles:true}));});
   assert.equal(await page.evaluate(()=>window.testTalk.say('A volume controlled answer',{conversation:true})),true);
   assert.ok(Math.abs(await page.evaluate(()=>window.audioTest.active.volume)-.22)<1e-9,`${design} uses shared volume`);
   await page.evaluate(()=>window.audioTest.active.onboundary?.({charIndex:2}));
   await volume.evaluate(el=>{el.value='.2';el.dispatchEvent(new Event('input',{bubbles:true}));});
   assert.ok(Math.abs(await page.evaluate(()=>window.audioTest.active.volume)-.11)<1e-9,`${design} updates current browser speech volume`);
   assert.equal(await page.evaluate(()=>window.audioTest.active.text),'volume controlled answer');
   const sound=page.locator('#topbar button').filter({hasText:/SOUND/});
   await sound.click();
   assert.equal(await page.evaluate(()=>window.audioTest.active===null && window.testTalk.audio.voiceVolume===0),true,`${design} mute cancels current browser speech`);
   assert.equal(await page.evaluate(()=>localStorage.getItem('gyropup.muted')),'0','Master mute does not overwrite voice-only preference');
   assert.equal(await page.evaluate(()=>window.testTalk.say('Muted answer')),false);
   await sound.click();await page.evaluate(()=>window.testTalk.say('Zero volume answer',{conversation:true}));
   await volume.evaluate(el=>{el.value='0';el.dispatchEvent(new Event('input',{bubbles:true}));});
   assert.equal(await page.evaluate(()=>window.audioTest.active===null && window.testTalk.audio.voiceVolume===0 && window.testSfx.volume===0),true,'Zero silences both audio backends');
   await page.evaluate(()=>{window.testTalk.setMuted(true);window.testSfx.setEnabled(false);window.testSfx.setEnabled(true);window.testSfx.setVolume(.3);});
   assert.equal(await page.evaluate(()=>window.testTalk.audio.voiceVolume===0 && window.testTalk.audio.muted),true,'Explicit voice mute survives master toggles');
   await page.reload({waitUntil:'networkidle'});await page.waitForFunction(()=>window.__sim?.talk || window.__talk);
   assert.equal(await page.evaluate(()=>{const t=window.__sim?.talk || window.__talk,s=window.__sim?.sfx || window.__sfx;return t.audio.muted && t.audio.voiceVolume===0 && s.volume===.3;}),true,'Saved volume and voice preference survive reload');
   if(design==='talk') {
    for(const width of [390,320]){
     await page.setViewportSize({width,height:width===390?844:568});await page.waitForTimeout(100);
     const title=await page.locator('#topbar h1').evaluate(h=>({text:h.textContent,scroll:h.scrollWidth,client:h.clientWidth,right:h.getBoundingClientRect().right}));
     assert.ok(title.scroll<=title.client && title.right<=width,`Talk demo title "${title.text}" is not cut short at ${width}px: ${JSON.stringify(title)}`);
    }
    await page.setViewportSize({width:320,height:568});await page.waitForTimeout(100);
    assert.equal(await page.locator('#topbar').evaluate(el=>el.scrollWidth<=el.clientWidth && [...el.querySelectorAll('button')].every(button=>{const r=button.getBoundingClientRect();return r.x>=0 && r.right<=innerWidth && r.height>=44;})),true,'Talk demo master controls fit a 320px phone');
    await page.setViewportSize({width:1200,height:900});
   }
  }
  await firstMountSoundOverride();
  if(process.argv.includes('--startup-control')) {
   // Aim inside the verified 17–18 second window rather than at a timer-resolution boundary.
   await firstMountSoundOverride({startupDelayMs:17500});
   console.log('PASS startup control: actual startup module held beyond 15 seconds; first-mounted mute remains enforced');
  }
 } finally {await context.close();}
}
try {
 await remoteVoice();
 await pronunciation();
 if(process.env.AUDIO_UNIT_ONLY!=='1')await siteControls();
 assert.deepEqual(errors,[]);
 console.log(`PASS ${engine.name()}: recorded clips for fixed lines, pronounced live speech, shared speech gain, immediate browser/Piper cancellation, pending response invalidation, independent saved voice mute${process.env.AUDIO_UNIT_ONLY==='1'?' (isolated voice adapter)':' and robot/bench/talk-demo controls'}`);
} finally {await browser.close();}
