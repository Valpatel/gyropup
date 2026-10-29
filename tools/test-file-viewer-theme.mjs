/** Real published geometry and product colors at every supported phone boundary. */
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {chromium,webkit} from '@playwright/test';
import {createSiteServer} from './serve-site.mjs';
import {acknowledgePrototypeNotice} from './test-prototype-session.mjs';

const server=process.env.SITE_URL?null:createSiteServer();
if(server)await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const base=process.env.SITE_URL||`http://127.0.0.1:${server.address().port}`;
const engine=process.env.PLAYWRIGHT_BROWSER==='webkit'?webkit:chromium;
const browser=await engine.launch(engine===chromium?{channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']}:{headless:true});
const context=await browser.newContext();await acknowledgePrototypeNotice(context);
const page=await context.newPage(),errors=[],missing=[],external=[],cases=[];
const out=process.env.TEST_OUTPUT||'/tmp/gyropup-file-viewer-theme';await mkdir(out,{recursive:true});
const original='/exports/sim/turret_box/pan_base.stl';
const url=`${base}/designer/kit/file-viewer.html?file=${encodeURIComponent(original)}`;
page.on('pageerror',error=>errors.push(error.message));
page.on('response',response=>{if(response.status()>=400)missing.push(response.url());});
page.on('request',request=>{if(/^https?:/.test(request.url())&&!request.url().startsWith(base+'/'))external.push(request.url());});
function luminance(color){const x=color.match(/[\d.]+/g).slice(0,3).map(Number).map(n=>n/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4);return x[0]*.2126+x[1]*.7152+x[2]*.0722;}
const contrast=(a,b)=>{const x=luminance(a),y=luminance(b);return(Math.max(x,y)+.05)/(Math.min(x,y)+.05);};
async function ready(target=page){await target.waitForFunction(()=>window.__fileViewer?.root.dataset.state==='ready');await target.evaluate(()=>document.fonts.ready);}
async function inspect(target=page){return target.evaluate(async()=>{
  const viewer=window.__fileViewer,root=viewer.root,button=root.querySelector('.file-tools button'),header=root.querySelector('.file-header'),muted=root.querySelector('.file-title p'),download=root.querySelector('[download]');
  const color=node=>{const s=getComputedStyle(node);return{color:s.color,background:s.backgroundColor,border:s.borderColor,font:s.fontFamily};};
  const THREE=await import('/designer/kit/vendor/three/three.module.min.js'),box=new THREE.Box3().setFromObject(viewer.model);
  const points=Array.from({length:8},(_,i)=>new THREE.Vector3(i&1?box.max.x:box.min.x,i&2?box.max.y:box.min.y,i&4?box.max.z:box.min.z).project(viewer.stage.camera).toArray());
  const canvas=viewer.stage.renderer.domElement.getBoundingClientRect();
  return{theme:root.dataset.fileTheme,root:color(root),button:color(button),header:color(header),muted:color(muted),download:color(download),
    canvas:{width:canvas.width,height:canvas.height},scrollWidth:document.documentElement.scrollWidth,points,
    background:viewer.stage.scene.background.getHexString(),buttons:[...root.querySelectorAll('button,a,select')].filter(n=>n.getClientRects().length).map(n=>({label:n.textContent,minimum:n.getBoundingClientRect().height}))};
});}
try{
  const phones=[[320,568],[360,640],[375,667],[390,844],[393,852],[412,915],[414,896],[430,932],[480,960]];
  const viewports=[...phones,...phones.map(([w,h])=>[h,w]),[768,1024],[1024,768],[1440,900]];
  for(const [index,[width,height]]of viewports.entries()){
    await page.setViewportSize({width,height});await page.emulateMedia({colorScheme:index%2?'dark':'light'});
    await page.goto(url);await ready();const state=await inspect();
    assert.equal(state.theme,'light','Gyropup follows the main site palette in either OS scheme');
    assert.equal(state.root.color,'rgb(23, 61, 60)');assert.match(state.root.font,/Inter/);
    assert.equal(state.background,'d9edf3');assert.ok(state.scrollWidth<=width&&state.canvas.height>120);
    assert.ok(state.points.every(p=>p.slice(0,2).every(n=>Math.abs(n)<1.01)),'Model stays in its canvas');
    assert.ok(state.buttons.every(b=>b.minimum>=44),JSON.stringify(state.buttons));
    assert.ok(contrast(state.button.color,state.button.background)>=4.5);
    assert.ok(contrast(state.button.border,state.button.background)>=3);
    assert.ok(contrast(state.header.color,state.header.background)>=4.5);
    assert.ok(contrast(state.muted.color,state.header.background)>=4.5);
    assert.ok(contrast(state.download.color,state.download.background)>=4.5);
    assert.equal(await page.getByRole('link',{name:'Back to parts'}).getAttribute('href'),base+'/designer/build.html');
    assert.equal(await page.getByRole('link',{name:'Download original'}).getAttribute('href'),base+original);
    if([0,3,9,20].includes(index))await page.screenshot({path:`${out}/${engine.name()}-${width}x${height}.png`});
    cases.push({width,height,state});
  }
  // A fresh browser tab receives the same consumer theme and closes cleanly.
  const popupPromise=page.waitForEvent('popup');await page.evaluate(url=>window.open(url,'_blank'),url);const popup=await popupPromise;await ready(popup);
  assert.equal((await inspect(popup)).root.color,'rgb(23, 61, 60)');await popup.close();assert.ok(popup.isClosed());
  await page.getByRole('button',{name:'Top',exact:true}).click();
  assert.ok(await page.evaluate(()=>window.__fileViewer.stage.camera.position.clone().sub(window.__fileViewer.stage.controls.target).normalize().y)>.99);
  const before=await page.evaluate(()=>window.__fileViewer.stage.camera.position.distanceTo(window.__fileViewer.stage.controls.target));
  const canvas=await page.locator('.file-canvas canvas').boundingBox();await page.mouse.move(canvas.x+canvas.width/2,canvas.y+canvas.height/2);await page.mouse.wheel(0,120);
  await page.waitForFunction(r=>window.__fileViewer.stage.camera.position.distanceTo(window.__fileViewer.stage.controls.target)>r*1.01,before);
  const ratio=await page.evaluate(r=>window.__fileViewer.stage.camera.position.distanceTo(window.__fileViewer.stage.controls.target)/r,before);assert.ok(ratio<1.02);
  await page.goto(url+'&theme=dark');await ready();assert.equal((await inspect()).theme,'dark');
  await page.screenshot({path:`${out}/${engine.name()}-explicit-dark.png`});
  // Entry-module failure keeps the themed, local download/retry fallback usable.
  await page.route('**/file-viewer.js*',route=>route.abort());await page.setViewportSize({width:320,height:568});await page.goto(url);
  await page.getByRole('button',{name:'Retry viewer'}).waitFor();
  assert.equal(await page.locator('html').getAttribute('data-file-theme'),'light');
  assert.equal(await page.getByRole('link',{name:'Download original'}).getAttribute('href'),base+original);
  await page.screenshot({path:`${out}/${engine.name()}-entry-fallback.png`});
  await page.unroute('**/file-viewer.js*');await page.getByRole('button',{name:'Retry viewer'}).click();await ready();
  await page.getByRole('link',{name:'Back to parts'}).click();await page.waitForURL(base+'/designer/build.html');
  assert.deepEqual(errors,[]);assert.deepEqual(missing,[]);assert.deepEqual(external,[]);
  await writeFile(`${out}/${engine.name()}-report.json`,JSON.stringify({passed:true,cases,wheelRatio:ratio,errors,missing,external},null,2));
  console.log(JSON.stringify({passed:true,engine:engine.name(),viewports:viewports.length,out}));
}finally{await browser.close();if(server)await new Promise(resolve=>{server.close(resolve);server.closeAllConnections();});}
