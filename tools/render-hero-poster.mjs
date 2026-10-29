/** Capture the same camera, model, lighting and pose used by the hero's first frame. */
import {writeFile} from 'node:fs/promises';
import {chromium} from '@playwright/test';
const base=(process.env.SITE_URL||'http://127.0.0.1:8890').replace(/\/$/,'');
const browser=await chromium.launch({channel:process.env.PLAYWRIGHT_CHANNEL==='chromium'?undefined:'chrome',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 await page.addInitScript(()=>{localStorage.setItem('gyropup.probe','off');localStorage.setItem('gyropup-sfx','0');});
 await page.goto(base+'/',{waitUntil:'networkidle'});
 await page.waitForFunction(()=>window.__heroPreview?.capturePoster);
 const image=await page.evaluate(()=>window.__heroPreview.capturePoster(1024));
 await writeFile(new URL('../web/robot-poster.png',import.meta.url),Buffer.from(image.split(',')[1],'base64'));
 console.log('Rendered web/robot-poster.png from the actual hero scene at 1024×1024 with alpha.');
}finally{await browser.close();}
