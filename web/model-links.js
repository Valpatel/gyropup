// Original files keep their addresses; previews are an extra browsing affordance.
export function addModelPreviews(host,{base,published}) {
  const doc=host.ownerDocument||host,here=new URL(base);
  if(/\/file-viewer(?:\.html)?$/.test(here.pathname))return;
  for(const anchor of host.querySelectorAll('a[href]')) {
    if(anchor.hasAttribute('data-model-original')||anchor.hasAttribute('data-model-preview'))continue;
    let url;try{url=new URL(anchor.getAttribute('href'),here);}catch{continue;}
    if(url.origin!==here.origin||!published.has(decodeURIComponent(url.pathname)))continue;
    anchor.setAttribute('data-model-original','');anchor.setAttribute('download','');
    anchor.setAttribute('title','Download original '+url.pathname.split('/').pop());
    const preview=doc.createElement('a');preview.className='model-preview';preview.setAttribute('data-model-preview','');
    preview.href='/designer/kit/file-viewer.html?'+new URLSearchParams({file:url.pathname,back:here.pathname+here.search});
    preview.textContent='Preview 3D';preview.setAttribute('aria-label','Preview '+decodeURIComponent(url.pathname.split('/').pop())+' in 3D');
    anchor.after(' ',preview);
  }
}
if(typeof window!=='undefined'&&window.document) {
  fetch('/site/models.json').then(response=>{if(!response.ok)throw new Error('Model inventory unavailable');return response.json();}).then(inventory=>{
    const published=new Set(inventory.files.map(file=>file.path)),refresh=()=>addModelPreviews(document,{base:location.href,published});
    refresh();let scheduled=false;
    new MutationObserver(records=>{if(scheduled||!records.some(record=>record.addedNodes.length))return;scheduled=true;queueMicrotask(()=>{scheduled=false;refresh();});}).observe(document.body,{childList:true,subtree:true});
  }).catch(error=>console.warn(error.message));
}
