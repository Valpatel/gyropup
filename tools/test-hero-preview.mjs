/** Exercise the visible poster-to-WebGL handoff, not merely matching CSS boxes. */
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {chromium,webkit} from '@playwright/test';
const base=(process.env.SITE_URL||'http://127.0.0.1:8890').replace(/\/$/,'');
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
const out=process.env.TEST_OUTPUT||'/tmp/gyropup-hero-preview';await mkdir(out,{recursive:true});
const errors=[],cases=[];
function prefs(){localStorage.setItem('gyropup.probe','off');localStorage.setItem('gyropup-sfx','0');}
function voiceStub(){
 window.voiceTest={spoken:[],cancelled:0};
 Object.defineProperty(window,'SpeechSynthesisUtterance',{configurable:true,value:class{constructor(text){this.text=text;}}});
 Object.defineProperty(window,'speechSynthesis',{configurable:true,value:{getVoices:()=>[],speak(u){window.voiceTest.spoken.push({text:u.text,volume:u.volume});},cancel(){window.voiceTest.cancelled++;}}});
}
async function settle(page){await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));}
async function visibleComposition(page,first=false){return page.evaluate(async first=>{
 const h=window.__heroPreview,container=document.getElementById('robot-preview'),poster=container.querySelector('img'),canvas=h.renderer.domElement;
 const frame=new Image();frame.src=first?window.firstHeroFrame:h.captureFrame();await frame.decode();
 const w=frame.naturalWidth,v=frame.naturalHeight,expected=document.createElement('canvas'),actual=document.createElement('canvas');
 expected.width=actual.width=w;expected.height=actual.height=v;
 const e=expected.getContext('2d'),a=actual.getContext('2d'),scale=Math.min(w/poster.naturalWidth,v/poster.naturalHeight);
 e.drawImage(poster,(w-poster.naturalWidth*scale)/2,(v-poster.naturalHeight*scale)/2,poster.naturalWidth*scale,poster.naturalHeight*scale);a.drawImage(frame,0,0);
 const ep=e.getImageData(0,0,w,v).data,ap=a.getImageData(0,0,w,v).data;
 let union=0,intersection=0,error=0,samples=0;
 for(let i=0;i<ep.length;i+=4){const em=ep[i+3]>32,am=ap[i+3]>32;if(em||am)union++;if(em&&am){intersection++;for(let c=0;c<3;c++){error+=Math.abs(ep[i+c]-ap[i+c]);samples++;}}}
 const rect=x=>{const r=x.getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height};};
 return {poster:rect(poster),canvas:rect(canvas),container:rect(container),silhouetteIoU:intersection/union,meanColorError:error/samples,buffer:[w,v],background:getComputedStyle(document.querySelector('.hero-scene')).backgroundImage};
},first);}
try{
 for(const dpr of [1,2]){
  const context=await browser.newContext({viewport:dpr===1?{width:1440,height:1000}:{width:320,height:568},deviceScaleFactor:dpr,reducedMotion:'reduce'});await context.addInitScript(prefs);
  const page=await context.newPage();page.setDefaultTimeout(60000);page.on('pageerror',e=>errors.push(e.message));
  let release;
  await page.route('**/robot_v2.js*',async route=>{await new Promise(resolve=>release=resolve);await route.continue();});
  await page.goto(base+'/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>{const i=document.querySelector('.scene-fallback');return i.complete&&i.naturalWidth===1024;});
  assert.equal(await page.locator('#robot-preview canvas').count(),0);
  await page.locator('.hero-scene').scrollIntoViewIfNeeded();
  const before=await page.locator('.hero-scene').boundingBox();
  // WebKit's document.fonts.ready waits for the deliberately held module load.
  // Load the two fonts explicitly, then capture this intentionally unfinished page.
  await page.evaluate(()=>Promise.all([document.fonts.load('600 14px Inter'),document.fonts.load('600 10px "JetBrains Mono"')]));
  process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY='1';
  try { await page.locator('.hero-scene').screenshot({path:`${out}/${engine.name()}-loading-dpr${dpr}.png`}); }
  finally { delete process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY; }
  await page.waitForFunction(()=>document.getElementById('robot-preview').dataset.state==='loading');
  assert.ok(release,'Module request deliberately held');release();
  await page.waitForFunction(()=>window.__heroPreview&&document.getElementById('robot-preview').dataset.ready==='true');
  await page.waitForFunction(()=>getComputedStyle(document.querySelector('#robot-preview canvas')).opacity==='1');
  assert.deepEqual(await page.locator('.hero-scene').boundingBox(),before,'Loading handoff does not move the hero frame');
  for(const [width,height] of [[1440,1000],[1024,768],[320,568],[390,844],[430,932],[844,390]]){
   await page.setViewportSize({width,height});await settle(page);
   const c=await visibleComposition(page);
   for(const k of ['x','y','w','h'])assert.ok(Math.abs(c.poster[k]-c.canvas[k])<.1,`Poster/canvas ${k} at${width}dpr${dpr}: ${JSON.stringify(c)}`);
   assert.ok(c.silhouetteIoU>.94,`First visible silhouette aligns ${width}dpr${dpr}: ${JSON.stringify(c)}`);
   assert.ok(c.meanColorError<8,`Same robot pose/lighting ${width}dpr${dpr}: ${JSON.stringify(c)}`);
   assert.match(c.background,/217, 237, 243/,'Cool blue background contrasts with the yellow robot');
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   const controls=await page.locator('.hero-controls').evaluate(e=>[...e.querySelectorAll('button,summary')].map(b=>{const r=b.getBoundingClientRect();return{w:r.width,h:r.height,x:r.x,right:r.right};}));
   for(const b of controls)assert.ok(b.w>=44&&b.h>=44&&b.x>=0&&b.right<=width,`Reachable control ${width}: ${JSON.stringify(b)}`);
   if(width===320||width===844||width===1440)await page.locator('.hero-scene').screenshot({path:`${out}/${engine.name()}-ready-${width}-dpr${dpr}.png`});
   cases.push({width,height,dpr,...c});
  }
  assert.equal(await page.evaluate(()=>window.__heroPreview.controls.autoRotate),false,'Reduced motion disables automatic rotation');
  await context.close();
 }
 // Normal-motion pages must reveal the same first frame before beginning idle motion.
 {
  const context=await browser.newContext({viewport:{width:1440,height:1000}});await context.addInitScript(prefs);
  await context.addInitScript(()=>new MutationObserver(()=>{const h=window.__heroPreview;if(h&&!window.firstHeroFrame){window.firstHeroFrame=h.captureFrame();window.firstHeroCamera=h.camera.position.toArray();}}).observe(document,{subtree:true,attributes:true,attributeFilter:['data-ready']}));
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>window.firstHeroFrame);
  const first=await visibleComposition(page,true);assert.ok(first.silhouetteIoU>.94&&first.meanColorError<8,'Normal-motion first frame matches poster before idle motion');
  await page.waitForFunction(()=>window.__heroPreview.controls.autoRotate&&window.__heroPreview.camera.position.toArray().some((v,i)=>Math.abs(v-window.firstHeroCamera[i])>1e-4));
  await page.waitForFunction(()=>window.__heroPreview.activity.announcements>0,null,{timeout:60000});
  await page.waitForFunction(()=>{const b=document.querySelector('.gp-bubble');return b&&!b.classList.contains('hidden')&&Number(getComputedStyle(b).opacity)>.9;});
  const contrast=await page.locator('.gp-bubble').evaluate(b=>{
   const lum=color=>{const rgb=color.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;});return .2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2];};
   const bg=lum(getComputedStyle(b).backgroundColor),fg=lum(getComputedStyle(b.querySelector('.gp-text')).color);
   return (Math.max(bg,fg)+.05)/(Math.min(bg,fg)+.05);
  });assert.ok(contrast>=4.5,`Greeting text contrast ${contrast}`);
  await page.waitForFunction(()=>!document.querySelector('.gp-bubble').classList.contains('typing'));
  await page.locator('.hero-scene').screenshot({path:`${out}/${engine.name()}-alive-greeting.png`});
  await context.close();
 }
 // Hold the image for actual renderer failures as well as slow network loading.
 for(const failure of ['module','webgl']){
  const context=await browser.newContext({viewport:{width:320,height:568}});await context.addInitScript(prefs);
  if(failure==='webgl')await context.addInitScript(()=>{const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...rest){return /webgl/.test(type)?null:get.call(this,type,...rest);};});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  if(failure==='module')await page.route('**/robot_v2.js*',route=>route.abort());
  await page.goto(base+'/',{waitUntil:'networkidle'});await page.waitForFunction(()=>document.getElementById('robot-preview').dataset.state==='fallback');
  assert.equal(await page.locator('#robot-preview canvas').count(),0);
  assert.equal(await page.locator('.scene-fallback').evaluate(e=>getComputedStyle(e).opacity),'1');
  assert.ok(await page.locator('#hero-inspect').isDisabled());
  await page.locator('.hero-scene').screenshot({path:`${out}/${engine.name()}-fallback-${failure}.png`});await context.close();
 }
 // Native hover, keyboard and touch activation exercise the real presentation API.
 for(const touch of [false,true]){
  const context=await browser.newContext({viewport:touch?{width:390,height:844}:{width:1440,height:1000},hasTouch:touch,isMobile:touch,reducedMotion:'reduce'});
  await context.addInitScript(prefs);await context.addInitScript(voiceStub);
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/',{waitUntil:'networkidle'});await page.waitForFunction(()=>window.__heroPreview);
  assert.equal(await page.evaluate(()=>typeof window.__heroPreview.robot.setExplode),'function');
  await page.locator('.hero-scene').scrollIntoViewIfNeeded();
  if(!touch){
   for(let i=0;i<3;i++){await page.locator('#robot-preview').hover();await page.waitForFunction(()=>window.__heroPreview.inspection.amount===.45);await page.mouse.move(0,0);await page.waitForFunction(()=>window.__heroPreview.inspection.amount===0);}
   await page.locator('#hero-inspect').focus();await page.keyboard.press('Space');
  }else await page.locator('#hero-inspect').tap();
  await page.waitForFunction(()=>window.__heroPreview.inspection.pinned&&window.__heroPreview.inspection.amount===.45);
  assert.equal(await page.locator('#hero-inspect').getAttribute('aria-pressed'),'true');
  await page.locator('#hero-inspect').click();await page.mouse.move(0,0);await page.waitForFunction(()=>window.__heroPreview.inspection.amount===0);
  // A saved master mute also applies before the first gesture and after speech starts.
  await page.evaluate(()=>window.__heroPreview.talk.say('Muted landing test'));
  await settle(page);const bubble=await page.locator('.gp-bubble').boundingBox();
  assert.ok(bubble.x>=0&&bubble.y>=0&&bubble.x+bubble.width<=page.viewportSize().width&&bubble.y+bubble.height<=page.viewportSize().height,'Speech stays inside the visible viewport');
  if(touch)await page.locator('.hero-scene').screenshot({path:`${out}/${engine.name()}-touch-greeting.png`});
  assert.equal(await page.evaluate(()=>window.voiceTest.spoken.length),0);
  await page.locator('#hero-sound').click();await page.evaluate(()=>window.__heroPreview.talk.say('Audible landing test'));
  await page.waitForFunction(()=>window.voiceTest.spoken.some(x=>x.text==='Audible landing test'));
  // Visibility is an input adapter here: hidden pages cancel speech and stop the active chatter clock.
  const hiddenState=await page.evaluate(()=>{const h=window.__heroPreview;Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));return {...h.activity,cancelled:window.voiceTest.cancelled};});
  await settle(page);await page.waitForTimeout(100);
  assert.deepEqual(await page.evaluate(()=>window.__heroPreview.activity),{seconds:hiddenState.seconds,announcements:hiddenState.announcements});
  await page.evaluate(()=>{delete document.hidden;document.dispatchEvent(new Event('visibilitychange'));});
  const cancelled=await page.evaluate(()=>window.voiceTest.cancelled);await page.locator('#hero-sound').click();
  assert.ok(await page.evaluate(n=>window.voiceTest.cancelled>n,cancelled));
  await page.locator('.hero-volume summary').click();await page.locator('#hero-volume').fill('0.25');await page.locator('#hero-volume').dispatchEvent('input');
  assert.equal(await page.evaluate(()=>window.__heroPreview.sfx.volume),.25);assert.equal(await page.evaluate(()=>window.__heroPreview.talk.audio.volume),.25);
  await context.close();
 }
 assert.deepEqual(errors,[]);
 await writeFile(`${out}/${engine.name()}-report.json`,JSON.stringify({base,cases,errors},null,2));
 console.log(`PASS ${engine.name()}: visible poster/first-frame match at12 viewport/DPR combinations; delayed loading; module/WebGL fallback; hover, keyboard, touch inspection; shared audio and reduced motion`);
}finally{await browser.close();}
