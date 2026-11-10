/** Exact-part handoff into the existing Print view; never prints neutral scene meshes. */
import {readAsset,loadGuide,parseJSON} from '../kit/assembly/guide.js';
import {validateIndex,matchSnapshot} from './state.js';
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const digest=/^[0-9a-f]{64}$/;
export function validateManufacturingOriginals(mapping){
 if(!['print','machine','sheet'].includes(mapping?.kind)||!Array.isArray(mapping.originals)||!mapping.originals.length||mapping.originals.length>32)throw new Error('This part has no mapped manufacturing originals.');
 for(const original of mapping.originals){
  if(!digest.test(original.sha256||'')||!/^hardware\/exports\/[a-zA-Z0-9_./-]+\.(?:stl|3mf|step|stp|dxf)$/.test(original.source_file||'')||!/^\/exports\/(?!sim\/)[a-zA-Z0-9_./-]+\.(?:stl|3mf|step|stp|dxf)$/.test(original.public_file||'')||original.public_file.split('/').includes('..')||original.source_file.split('/').includes('..'))throw new Error('The mapping does not identify a manufacturing original.');
 }
 return mapping;
}
export function validatePrintMapping(mapping){if(mapping?.kind!=='print')throw new Error('This part is not a mapped printed part.');return validateManufacturingOriginals(mapping);}
export async function verifyManufacturingOriginals(mapping,{signal,fetcher=fetch,origin=globalThis.location?.origin||'https://print.invalid'}={}){
 validateManufacturingOriginals(mapping);const records=[];let total=0;
 for(const original of mapping.originals){const bytes=await readAsset(new URL(original.public_file,origin),{signal,fetcher,expectedHash:original.sha256,maxBytes:128*1024*1024});total+=bytes.byteLength;if(total>128*1024*1024)throw new Error('Selected originals exceed the 128 MB preview limit.');records.push({...original,bytes});}
 return records;
}
export async function verifyPrintOriginals(mapping,options){validatePrintMapping(mapping);return verifyManufacturingOriginals(mapping,options);}
export function mountPrintSelection(host){
 if(!host)return;let abort=null,generation=0,currentKey='',urls=[];const events=new AbortController();
 const clear=()=>{for(const url of urls)URL.revokeObjectURL(url);urls=[];};
 function reveal(){const details=document.getElementById('build-details');details.open=true;window.selectBuildPanel?.('print');host.hidden=false;requestAnimationFrame(()=>host.scrollIntoView({block:'start'}));}
 function writeChoice(detail){const url=new URL(location.href);url.searchParams.set('printPart',detail.part.name);url.searchParams.set('printSnapshot',detail.guide.snapshot.id);url.searchParams.set('printGuide',detail.guideHash);url.searchParams.set('printAssembly',detail.assembly);url.hash='print-selection';const oldURL=location.href;history.pushState(null,'',url);window.dispatchEvent(new HashChangeEvent('hashchange',{oldURL,newURL:url.href}));}
 async function show(detail,{navigate=false}={}){
  const key=detail.guideHash+':'+detail.part.name;if(currentKey===key){reveal();return;}currentKey=key;const own=++generation;abort?.abort();abort=new AbortController();clear();
  const mapping=detail.part.manufacturing||detail.guide.source?.manufacturing_by_part?.[detail.part.name];
  host.innerHTML=`<div class="sec">Prepare this part</div><div class="card print-selection-card"><h3>${esc(detail.part.title||detail.part.name)}</h3><p><code>${esc(detail.part.name)}</code> · ${esc(detail.guide.snapshot.revision)} · ${esc(detail.guide.snapshot.status.toUpperCase())}</p><p data-print-selection-status role="status">Verifying the source-bound manufacturing files…</p><div data-print-selection-downloads></div></div>`;
  reveal();if(navigate)writeChoice(detail);
  try{
   const originals=await verifyPrintOriginals(mapping,{signal:abort.signal});if(own!==generation)return;
   const downloads=host.querySelector('[data-print-selection-downloads]');
   for(const original of originals){const url=URL.createObjectURL(new Blob([original.bytes],{type:original.public_file.endsWith('.3mf')?'model/3mf':'model/stl'}));urls.push(url);const link=document.createElement('a');link.href=url;link.download=original.public_file.split('/').at(-1);link.textContent='Download original '+link.download;link.className='print-selection-download';downloads.append(link);
    // Only an explicitly audited immutable project may use the official client URI.
    if(original.project===true&&original.immutable===true&&original.public_file.endsWith('.3mf')){const client=document.createElement('a');client.href='bambustudio://open?file='+encodeURIComponent(new URL(original.public_file,location.origin).href);client.textContent='Open project in Bambu Studio';client.className='print-selection-download';downloads.append(client);}
   }
   const plan=mapping.plan;host.querySelector('[data-print-selection-status]').textContent='Original file bytes verified for this snapshot. Download and open in your slicer.';
   if(plan){const note=document.createElement('p');note.className='small dim';note.textContent=[plan.material&&'Material: '+plan.material,plan.qty!==undefined&&'Plan quantity: '+plan.qty+(plan.qty_scope?' ('+plan.qty_scope+')':'')].filter(Boolean).join(' · ');downloads.append(note);}
   if(mapping.qualification){const note=document.createElement('p');note.className='small dim';note.textContent=mapping.qualification;downloads.append(note);}
   // Existing list search remains the source of quantities and status checkboxes.
   const wanted=mapping.key||mapping.part_key;for(const input of document.querySelectorAll('#queue .cad-table-search input')){input.value=wanted||detail.part.name;input.dispatchEvent(new Event('input',{bubbles:true}));}
   host.dataset.state='ready';
  }catch(error){if(own!==generation||abort.signal.aborted)return;host.dataset.state='error';host.querySelector('[data-print-selection-status]').textContent='Print preparation unavailable: '+error.message+' The current planner remains below.';}
 }
 async function fromRoute(){const query=new URLSearchParams(location.search),name=query.get('printPart'),snapshot=query.get('printSnapshot'),hash=query.get('printGuide');if(!name||!snapshot||!digest.test(hash||''))return;const key=hash+':'+name;if(currentKey===key)return;
  const own=++generation;abort?.abort();abort=new AbortController();host.hidden=false;host.innerHTML='<p role="status">Loading the selected part’s exact snapshot…</p>';
  try{const indexURL=new URL('../../web/build-guides/index.json',import.meta.url),index=validateIndex(parseJSON(await readAsset(indexURL,{signal:abort.signal,maxBytes:512*1024}))),row=index.snapshots.find(item=>item.id===snapshot&&item.sha256===hash);if(!row)throw new Error('The selected snapshot digest is no longer available.');if(query.get('printAssembly')&&(row.assembly||'turret')!==query.get('printAssembly'))throw new Error('The selected part belongs to a different assembly.');const loaded=await loadGuide(new URL(row.file,indexURL).href,{signal:abort.signal,expectedHash:row.sha256});if(own!==generation)return;matchSnapshot(row,loaded.guide);const part=loaded.manifest.parts.find(item=>item.name===name);if(!part)throw new Error('This part is absent from the selected snapshot.');await show({guide:loaded.guide,guideHash:hash,guideURL:loaded.guideUrl,assembly:row.assembly||'turret',part:{...part,manufacturing:loaded.guide.source?.manufacturing_by_part?.[name]}});
  }catch(error){if(own!==generation||abort.signal.aborted)return;host.dataset.state='error';host.textContent='Print preparation unavailable: '+error.message;reveal();}
 }
 window.addEventListener('gyropup:prepare-print',event=>show(event.detail,{navigate:true}),{signal:events.signal});window.addEventListener('hashchange',fromRoute,{signal:events.signal});window.addEventListener('popstate',fromRoute,{signal:events.signal});fromRoute();
 const dispose=()=>{++generation;abort?.abort();clear();events.abort();};window.addEventListener('pagehide',dispose,{once:true,signal:events.signal});return{dispose};
}
