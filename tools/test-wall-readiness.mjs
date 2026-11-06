import { waitForRenderedText } from './test-rendered-readiness.mjs';

/** Whole-article geometry needs every unfolded primary image, including native lazy images below the viewport. */
export async function waitForWallImages(page) {
  await page.waitForFunction(() => {
    const content=document.querySelector('main.document article')||document.querySelector('article.prose')||document.querySelector('main');
    if(!content)throw new Error('Wall content is missing');
    const folded=el=>{for(let d=el.closest('details:not([open])');d;d=d.parentElement?.closest('details:not([open])'))if(!d.querySelector(':scope > summary')?.contains(el))return true;return false;};
    const hidden=el=>{for(let n=el;n&&n!==content;n=n.parentElement){const s=getComputedStyle(n);if(s.visibility==='hidden'||s.display==='none'||Number(s.opacity)===0)return true;}return false;};
    const images=[...content.querySelectorAll('img')].filter(img=>{
      if(folded(img)||hidden(img))return false;
      const r=img.getBoundingClientRect(),width=parseFloat(img.style.width),height=parseFloat(img.style.height);
      const reserved=img.classList.contains('repo-badge')&&/^\d+(?:\.\d+)?px$/.test(img.style.width)&&/^\d+(?:\.\d+)?px$/.test(img.style.height)
        &&width>0&&height>0&&Math.abs(r.width-width)<1&&Math.abs(r.height-height)<1;
      // A class or a currently tiny/zero rect alone cannot establish a stable decorative box.
      if(reserved&&(r.width<120||r.height<80))return false;
      img.loading='eager'; // Activate the browser's real load even for unknown-size offscreen images.
      return true;
    });
    for(const img of images)if(img.complete&&!img.naturalWidth)throw new Error(`Primary image failed to load: ${img.getAttribute('src')}`);
    if(images.some(img=>!img.complete))return false;
    window.__wallPrimaryImages=images;
    return true;
  },null,{timeout:30000});
  await page.evaluate(()=>{
    const state=window.__wallImageDecode={done:false,error:null};
    Promise.all(window.__wallPrimaryImages.map(img=>img.decode()))
      .then(()=>{state.done=true;},error=>{state.error=String(error.message||error);});
  });
  await page.waitForFunction(()=>{
    const state=window.__wallImageDecode;
    if(state?.error)throw new Error(`Primary image decode failed: ${state.error}`);
    return state?.done;
  },null,{timeout:30000});
}

/** The actual navigation/readiness boundary used before both ordinary and planted wall measurements. */
export async function loadWallPage(page,base,route) {
  await page.goto(base+route,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!document.querySelector('pre.mermaid, pre > code.language-mermaid')
    &&[...document.querySelectorAll('.cad-diagram')].every(f=>f.dataset.state==='ready'||f.dataset.state==='error')
    &&(!/^\/designer\/(progress|build|sim)\.html$/.test(location.pathname)||document.body.dataset.ready==='1'),null,{timeout:30000});
  await waitForRenderedText(page);
  await waitForWallImages(page);
  await page.evaluate(()=>{scrollTo(0,0);return new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));});
}
