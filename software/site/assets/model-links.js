// Original files keep their addresses; one preview serves repeated links to a model in a table row.
export function addModelPreviews(host,{base,published}) {
  const doc=host.ownerDocument||host,here=new URL(base);
  if(/\/file-viewer(?:\.html)?$/.test(here.pathname))return;
  const scopes=new Map();
  for(const anchor of host.querySelectorAll('a[href]')) {
    if(anchor.hasAttribute('data-model-preview'))continue;
    let url;try{url=new URL(anchor.getAttribute('href'),here);}catch{continue;}
    if(url.origin!==here.origin||!published.has(decodeURIComponent(url.pathname)))continue;
    if(!anchor.hasAttribute('data-model-original'))anchor.setAttribute('data-model-original','');
    if(!anchor.hasAttribute('download'))anchor.setAttribute('download','');
    const title='Download original '+url.pathname.split('/').pop();
    if(anchor.getAttribute('title')!==title)anchor.setAttribute('title',title);
    // A thumbnail and the named download often link to the exact same file.
    // Scope deduplication to that row and exact file: never conflate different models.
    const scope=anchor.closest('tr')||anchor;
    if(!scopes.has(scope))scopes.set(scope,new Map());
    const files=scopes.get(scope),key=decodeURIComponent(url.pathname);
    if(!files.has(key))files.set(key,{url,anchors:[]});
    files.get(key).anchors.push(anchor);
  }
  for(const [scope,files] of scopes)for(const [key,{url,anchors}] of files) {
    // Keep the action beside a named download, leaving the picture column clean.
    const anchor=anchors.find(link=>link.textContent.trim())||anchors[0];
    const candidates=scope.tagName==='TR'?[...scope.querySelectorAll('a[data-model-preview]')]
      :[anchor.nextElementSibling].filter(node=>node?.hasAttribute('data-model-preview'));
    const existing=candidates.filter(link=>{
      try{return decodeURIComponent(new URL(link.getAttribute('href'),here).searchParams.get('file')||'')===key;}catch{return false;}
    });
    const preview=existing.shift()||doc.createElement('a');
    for(const duplicate of existing)duplicate.remove();
    const href='/designer/kit/file-viewer.html?'+new URLSearchParams({file:url.pathname,back:here.pathname+here.search});
    if(preview.getAttribute('href')!==href)preview.setAttribute('href',href);
    if(!preview.classList.contains('model-preview'))preview.classList.add('model-preview');
    if(!preview.hasAttribute('data-model-preview'))preview.setAttribute('data-model-preview','');
    if(preview.textContent!=='Preview 3D')preview.textContent='Preview 3D';
    const label='Preview '+decodeURIComponent(url.pathname.split('/').pop())+' in 3D';
    if(preview.getAttribute('aria-label')!==label)preview.setAttribute('aria-label',label);
    const identity=scope.tagName==='TR'?scope.querySelector('.cad-part-identity'):null;
    if(identity){if(preview.parentElement!==identity)identity.append(preview);}
    else if(anchor.nextElementSibling!==preview)anchor.after(preview);
  }
}
if(typeof window!=='undefined'&&window.document) {
  fetch('/site/models.json').then(response=>{if(!response.ok)throw new Error('Model inventory unavailable');return response.json();}).then(inventory=>{
    const published=new Set(inventory.files.map(file=>file.path)),refresh=()=>addModelPreviews(document,{base:location.href,published});
    refresh();let scheduled=false;
    new MutationObserver(records=>{if(scheduled||!records.some(record=>record.addedNodes.length))return;scheduled=true;queueMicrotask(()=>{scheduled=false;refresh();});}).observe(document.body,{childList:true,subtree:true});
  }).catch(error=>console.warn(error.message));
}
