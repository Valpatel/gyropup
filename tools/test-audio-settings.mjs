import { acknowledgePrototypeNotice } from './test-prototype-session.mjs';
/** Master audio gates both synthesis backends without erasing voice-only preferences. */
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { chromium, webkit } from '@playwright/test';
const engine = process.env.PLAYWRIGHT_BROWSER === 'webkit' ? webkit : chromium;
const browser = await engine.launch(engine === chromium ? {channel:process.env.PLAYWRIGHT_CHANNEL === 'chromium' ? undefined : 'chrome',headless:true,
  args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']} : {headless:true});
const root = new URL('../',import.meta.url), base=(process.env.SITE_URL || 'http://127.0.0.1:8882').replace(/\/$/,'');
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
  if(url.pathname.startsWith('/designer/'))return route.fulfill({contentType:url.pathname.endsWith('.css')?'text/css':'text/javascript',body:await readFile(new URL(url.pathname.slice(1),root))});
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
async function siteControls() {
 const context=await browser.newContext({viewport:{width:1200,height:900}});await context.addInitScript(browserVoice);
await acknowledgePrototypeNotice(context);
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 if(process.env.AUDIO_SOURCE==='1')await page.route('**/designer/**',async route=>{
  const p=new URL(route.request().url()).pathname;
  if(['/designer/sim.js','/designer/sfx.js','/designer/character/talk.js','/designer/character/talk-demo.html'].includes(p))return route.fulfill({contentType:p.endsWith('.html')?'text/html':'text/javascript',body:await readFile(new URL(p.slice(1),root))});
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
    await page.setViewportSize({width:320,height:568});await page.waitForTimeout(100);
    assert.equal(await page.locator('#topbar').evaluate(el=>el.scrollWidth<=el.clientWidth && [...el.querySelectorAll('button')].every(button=>{const r=button.getBoundingClientRect();return r.x>=0 && r.right<=innerWidth && r.height>=44;})),true,'Talk demo master controls fit a 320px phone');
    await page.setViewportSize({width:1200,height:900});
   }
  }
  await page.goto(base+'/designer/sim.html?run=none&sound=0',{waitUntil:'networkidle'});await page.waitForFunction(()=>window.__sim?.talk);
  assert.equal(await page.evaluate(()=>{window.__sim.talk.setMuted(false);return window.__sim.talk.audio.voiceVolume===0;}),true,'Master mute applies when talk first mounts');
 } finally {await context.close();}
}
try {
 await remoteVoice();
 if(process.env.AUDIO_UNIT_ONLY!=='1')await siteControls();
 assert.deepEqual(errors,[]);
 console.log(`PASS ${engine.name()}: shared speech gain, immediate browser/Piper cancellation, pending response invalidation, independent saved voice mute${process.env.AUDIO_UNIT_ONLY==='1'?' (isolated voice adapter)':' and robot/bench/talk-demo controls'}`);
} finally {await browser.close();}
