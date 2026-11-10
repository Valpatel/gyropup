/** Exact-part handoff into the existing Print view; never prints neutral scene meshes. */
import {readAsset,loadGuide,parseJSON} from '../kit/assembly/guide.js';
import {validateIndex,matchSnapshot} from './state.js';
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const digest=/^[0-9a-f]{64}$/;
export function validateManufacturingOriginals(mapping){
 if(!['print','machine','sheet'].includes(mapping?.kind)||!Array.isArray(mapping.originals)||!mapping.originals.length||mapping.originals.length>32)throw new Error('This part has no mapped manufacturing originals.');
 for(const original of mapping.originals){
  if(!digest.test(original.sha256||'')||!/^hardware\/exports\/[a-zA-Z0-9_./-]+\.(?:stl|3mf|step|stp|dxf)$/.test(original.source_file||'')||!/^\/exports\/(?!sim\/)[a-zA-Z0-9_./-]+\.(?:stl|3mf|step|stp|dxf)$/.test(original.public_file||'')||original.source_file!=='hardware'+original.public_file||original.public_file.split('/').includes('..'))throw new Error('The mapping does not identify a manufacturing original.');
 }
 return mapping;
}
export function validatePrintMapping(mapping){if(mapping?.kind!=='print')throw new Error('This part is not a mapped printed part.');if(mapping.geometry_match?.status!=='matched')throw new Error('The recorded original has no verified geometry match to this model snapshot.');return validateManufacturingOriginals(mapping);}
export async function verifyManufacturingOriginals(mapping,{signal,fetcher=fetch,origin=globalThis.location?.origin||'https://print.invalid'}={}){
 validateManufacturingOriginals(mapping);const records=[];let total=0;
 for(const original of mapping.originals){const bytes=await readAsset(new URL(original.public_file,origin),{signal,fetcher,expectedHash:original.sha256,maxBytes:128*1024*1024});total+=bytes.byteLength;if(total>128*1024*1024)throw new Error('Selected originals exceed the 128 MB preview limit.');records.push({...original,bytes});}
 return records;
}
export async function verifyPrintOriginals(mapping,options){validatePrintMapping(mapping);return verifyManufacturingOriginals(mapping,options);}
export function validatePreparedProject(mapping,project){
 validatePrintMapping(mapping);
 const path='/web/build-guides/prepared-projects/'+project?.sha256+'/';
 if(!digest.test(project?.sha256||'')||project.kind!=='geometry-only'||project.immutable!==true||!mapping.originals.some(original=>original.sha256===project.source_original_sha256)||typeof project.public_file!=='string'||!project.public_file.startsWith(path)||!/^[-a-zA-Z0-9_.]+\.3mf$/.test(project.public_file.slice(path.length))||project.public_file.includes('..')||project.source_file!=='software/site/assets/'+project.public_file.slice('/web/'.length)||!Array.isArray(project.limitations)||!project.limitations.length||project.limitations.some(item=>typeof item!=='string'))throw new Error('This project is not an immutable derivative of the verified original.');
 return project;
}
export async function verifyPreparedProject(mapping,project,{signal,fetcher=fetch,origin=globalThis.location?.origin||'https://print.invalid'}={}){validatePreparedProject(mapping,project);return {...project,bytes:await readAsset(new URL(project.public_file,origin),{signal,fetcher,expectedHash:project.sha256,maxBytes:128*1024*1024})};}
/** Pinned official client source has distinct macOS and Windows/Linux handlers. */
export function studioURL(publicURL,platform){const url=new URL(publicURL);if(!['http:','https:'].includes(url.protocol)||!url.pathname.endsWith('.3mf'))throw new Error('Bambu Studio requires an HTTP(S) 3MF project.');if(platform==='mac')return 'bambustudioopen://'+encodeURIComponent(url.href);if(platform==='windows-linux')return 'bambustudio://open?file='+encodeURIComponent(url.href);throw new Error('Choose a supported desktop platform.');}
export function mountPrintSelection(host){
 if(!host)return;let abort=null,generation=0,currentKey='',urls=[];const events=new AbortController();
 const clear=()=>{for(const url of urls)URL.revokeObjectURL(url);urls=[];};
 async function reveal(){
  window.dispatchEvent(new Event('gyropup:exit-workspace-fullscreen'));
  if(document.fullscreenElement){try{await document.exitFullscreen();}catch{throw new Error('Leave full screen with Escape, then prepare the part again.');}}
  const details=document.getElementById('build-details');details.open=true;window.selectBuildPanel?.('print');host.hidden=false;requestAnimationFrame(()=>host.scrollIntoView({block:'start'}));
 }
 function writeChoice(detail){const url=new URL(location.href);url.searchParams.set('printPart',detail.part.name);url.searchParams.set('printSnapshot',detail.guide.snapshot.id);url.searchParams.set('printGuide',detail.guideHash);url.searchParams.set('printAssembly',detail.assembly);url.hash='print-selection';const oldURL=location.href;history.pushState(null,'',url);window.dispatchEvent(new HashChangeEvent('hashchange',{oldURL,newURL:url.href}));}
 function download(container,record,label){const url=URL.createObjectURL(new Blob([record.bytes],{type:record.public_file.endsWith('.3mf')?'model/3mf':'application/octet-stream'}));urls.push(url);const link=document.createElement('a');link.href=url;link.download=record.public_file.split('/').at(-1);link.textContent=label;link.className='print-selection-download';container.append(link);}
 async function show(detail,{navigate=false}={}){
  const key=detail.guideHash+':'+detail.part.name;if(currentKey===key&&['ready','loading'].includes(host.dataset.state)){await reveal();return;}
  currentKey=key;const own=++generation;abort?.abort();abort=new AbortController();const signal=abort.signal;clear();host.dataset.state='loading';
  const mapping=detail.part.manufacturing||detail.guide.source?.manufacturing_by_part?.[detail.part.name];
  host.innerHTML=`<div class="sec">Prepare this part</div><div class="card print-selection-card"><h3>${esc(detail.part.title||detail.part.name)}</h3><p><code>${esc(detail.part.name)}</code> · ${esc(detail.guide.snapshot.revision)} · ${esc(detail.guide.snapshot.status.toUpperCase())}</p><p data-print-selection-status role="status">Verifying the source-bound manufacturing files…</p><div data-print-selection-downloads></div></div>`;
  try{
   await reveal();if(navigate)writeChoice(detail);
   const originals=await verifyPrintOriginals(mapping,{signal});if(own!==generation)return;
   const downloads=host.querySelector('[data-print-selection-downloads]');
   for(const original of originals)download(downloads,original,'Download original '+original.public_file.split('/').at(-1));
   for(const project of mapping.prepared_projects||[]){
    try{const verified=await verifyPreparedProject(mapping,project,{signal});if(own!==generation)return;const section=document.createElement('div');section.className='print-prepared-project';const heading=document.createElement('h4');heading.textContent='Geometry-only 3MF project';section.append(heading);download(section,verified,'Download geometry-only 3MF');
     for(const [platform,label]of [['windows-linux','Open in Bambu Studio (Windows / Linux)'],['mac','Open in Bambu Studio (macOS)']]){const link=document.createElement('a');link.href=studioURL(new URL(project.public_file,location.origin).href,platform);link.textContent=label;link.className='print-selection-download';section.append(link);}
     const note=document.createElement('p');note.textContent='Select your printer, filament and settings in the desktop slicer. This project is not sliced and does not start a print. If the app does not open, download the 3MF.';section.append(note);const limits=document.createElement('details');const summary=document.createElement('summary');summary.textContent='Project placement and limitations';limits.append(summary);for(const text of project.limitations){const p=document.createElement('p');p.textContent=text;limits.append(p);}section.append(limits);downloads.append(section);
    }catch(error){if(signal.aborted)throw error;const note=document.createElement('p');note.textContent='Prepared project unavailable: '+error.message;downloads.append(note);}
   }
   host.querySelector('[data-print-selection-status]').textContent='Original file bytes verified for this snapshot. Geometry correspondence is recorded; physical qualification is separate.';
   const plan=mapping.plan;if(plan){const note=document.createElement('p');note.className='small dim';note.textContent=[plan.material&&'Material: '+plan.material,plan.qty!==undefined&&'Plan quantity: '+plan.qty+(plan.qty_scope?' ('+plan.qty_scope+')':'')].filter(Boolean).join(' · ');downloads.append(note);}
   if(mapping.qualification){const note=document.createElement('p');note.className='small dim';note.textContent=mapping.qualification;downloads.append(note);}
   const wanted=mapping.key||mapping.part_key;for(const input of document.querySelectorAll('#queue .cad-table-search input')){input.value=wanted||detail.part.name;input.dispatchEvent(new Event('input',{bubbles:true}));}
   host.dataset.state='ready';
  }catch(error){if(own!==generation||signal.aborted)return;currentKey='';host.dataset.state='error';host.querySelector('[data-print-selection-status]').textContent='Print preparation unavailable: '+error.message;const retry=document.createElement('button');retry.type='button';retry.textContent='Retry print preparation';retry.onclick=()=>show(detail);host.querySelector('[data-print-selection-downloads]').append(retry);}
 }
 async function fromRoute(){const query=new URLSearchParams(location.search),name=query.get('printPart'),snapshot=query.get('printSnapshot'),hash=query.get('printGuide');if(!name||!snapshot||!digest.test(hash||''))return;const key=hash+':'+name;if(currentKey===key)return;
  const own=++generation;abort?.abort();abort=new AbortController();host.hidden=false;host.innerHTML='<p role="status">Loading the selected part’s exact snapshot…</p>';
  try{const indexURL=new URL('../../web/build-guides/index.json',import.meta.url),index=validateIndex(parseJSON(await readAsset(indexURL,{signal:abort.signal,maxBytes:512*1024}))),row=index.snapshots.find(item=>item.id===snapshot&&item.sha256===hash);if(!row)throw new Error('The selected snapshot digest is no longer available.');if(query.get('printAssembly')&&(row.assembly||'turret')!==query.get('printAssembly'))throw new Error('The selected part belongs to a different assembly.');const loaded=await loadGuide(new URL(row.file,indexURL).href,{signal:abort.signal,expectedHash:row.sha256});if(own!==generation)return;matchSnapshot(row,loaded.guide);const part=loaded.manifest.parts.find(item=>item.name===name);if(!part)throw new Error('This part is absent from the selected snapshot.');await show({guide:loaded.guide,guideHash:hash,guideURL:loaded.guideUrl,assembly:row.assembly||'turret',part:{...part,manufacturing:loaded.guide.source?.manufacturing_by_part?.[name]}});
  }catch(error){if(own!==generation||abort.signal.aborted)return;currentKey='';host.dataset.state='error';host.textContent='Print preparation unavailable: '+error.message;await reveal();}
 }
 window.addEventListener('gyropup:prepare-print',event=>show(event.detail,{navigate:true}),{signal:events.signal});window.addEventListener('hashchange',fromRoute,{signal:events.signal});window.addEventListener('popstate',fromRoute,{signal:events.signal});fromRoute();
 const dispose=()=>{++generation;abort?.abort();clear();events.abort();};window.addEventListener('pagehide',dispose,{once:true,signal:events.signal});return{dispose};
}
