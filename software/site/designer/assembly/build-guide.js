import {readLocation,stepFor,validateIndex,readProgress,saveProgress,writeLocation} from './state.js';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const hash=async bytes=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
const host=document.getElementById('assembly');
let active=null,request=0,pending=null;
function report(message,error=false){host.querySelector('[data-guide-status]').textContent=message;host.querySelector('[data-guide-status]').dataset.state=error?'error':'ready';}
async function get(url,signal){const r=await fetch(url,{signal,cache:'no-store'});if(!r.ok)throw new Error(`Build data returned HTTP ${r.status}.`);return r;}
async function start(){
 const indexURL=new URL('../../web/build-guides/index.json',import.meta.url);
 const index=validateIndex(await(await get(indexURL)).json());
 const select=host.querySelector('[data-snapshot]');
 select.replaceChildren(...index.snapshots.map(s=>{const o=document.createElement('option');o.value=s.id;o.textContent=s.title+' · '+s.status.toUpperCase();return o;}));
 async function load(id,route={}){
  const own=++request;pending?.abort();const abort=pending=new AbortController();
  const row=index.snapshots.find(s=>s.id===id);if(!row)throw new Error('Unknown snapshot');
  report('Loading this exact build snapshot…');
  let nextViewer;
  try{
   const url=new URL(row.file,indexURL),bytes=await(await get(url,abort.signal)).arrayBuffer();
   if(await hash(bytes)!==row.sha256)throw new Error('Build snapshot digest mismatch.');
   const guide=JSON.parse(new TextDecoder().decode(bytes));
   // Shared loader owns schema/model/mesh binding; no guessed or cross-version fallback.
   const [{loadGuide,createGuideController},{createViewer}]=await Promise.all([import('../kit/assembly/guide.js'),import('../kit/viewer.js')]);
   const loaded=await loadGuide(url.href,{signal:abort.signal});
   if(JSON.stringify(loaded.guide)!==JSON.stringify(guide))throw new Error('Build guide changed while loading.');
   const step=stepFor(guide,route),canvas=document.createElement('div'),panel=document.createElement('div');canvas.className='assembly-canvas';
   let renderError=null;
   try{nextViewer=await createViewer({app:canvas,panel,manifest:loaded.manifest,manifestUrl:loaded.manifestUrl,signal:abort.signal,
     onSelect:name=>{if(active?.viewer!==nextViewer)return;active.selected=name;host.querySelector('[data-guide-isolate]').disabled=!name;}});}
   catch(error){if(abort.signal.aborted)throw error;renderError=error;}
   if(own!==request){nextViewer?.dispose();return;}
   const previous=active;
   active={guide,viewer:nextViewer,controller:nextViewer?createGuideController(nextViewer,guide):null,done:readProgress(localStorage,guide),url,step:step.id,mode:'ghost',explode:1,selected:null,isolate:false,renderError};
   const model=host.querySelector('[data-guide-model]');model.replaceChildren(canvas);previous?.viewer?.dispose();
   select.value=id;paint(step.id);
   if(renderError)report('Interactive 3D is unavailable. The same snapshot’s text and poster remain below.',true);
   else report('Source-bound WIP guide loaded. No physical build release.');
   window.__buildGuide={get active(){return active;},load,apply:id=>paint(id),dispose(){pending?.abort();active?.viewer?.dispose();active=null;}};
  }catch(error){nextViewer?.dispose();if(abort.signal.aborted||own!==request)return;report(error.message+(active?' Your previous build remains selected.':''),true);if(active)select.value=active.guide.snapshot.id;}
 }
 select.onchange=()=>load(select.value);
 const route=readLocation(location,index);await load(route.snapshot,route);
 window.addEventListener('pagehide',()=>{pending?.abort();active?.viewer?.dispose();},{once:true});
}
function paint(id){
 const a=active,g=a.guide,s=stepFor(g,{step:id});a.step=s.id;
 a.controller?.applyStep(s.id,{mode:a.mode,explode:a.explode,frame:true});
 if(a.selected&&!s.parts.includes(a.selected)){a.selected=null;a.isolate=false;}
 if(a.selected)a.viewer?.setSelection(a.selected);
 if(a.isolate)a.viewer?.applyState({...a.viewer.getState(),selected:a.selected,isolate:a.selected?[a.selected]:null});
 const index=g.steps.indexOf(s),chapter=g.subassemblies.find(c=>c.id===s.subassembly);
 host.querySelector('[data-guide-source]').innerHTML=`${esc(g.snapshot.revision)} · ${esc(g.snapshot.status)} · <a href="https://github.com/Valpatel/gyropup/tree/${esc(g.snapshot.source_commit)}">Source snapshot</a>`;
 host.querySelector('[data-guide-warning]').textContent=g.source?.qualification||'Educational work in progress; no physical qualification.';
 host.querySelector('[data-guide-title]').textContent=s.title;
 host.querySelector('[data-guide-count]').textContent=`${chapter.title} · ${index+1} / ${g.steps.length}`;
 host.querySelector('[data-guide-text]').textContent=s.text;
 const poster=host.querySelector('[data-guide-poster]');poster.hidden=!s.poster;
 if(s.poster){poster.src=new URL(s.poster.file,a.url).href;poster.alt=`Step ${index+1}: ${s.title}`;}
 host.querySelector('[data-guide-chapters]').innerHTML=g.subassemblies.map(c=>`<button type="button" data-chapter="${esc(c.id)}" aria-current="${c.id===s.subassembly?'step':'false'}">${esc(c.title)}</button>`).join('');
 host.querySelectorAll('[data-chapter]').forEach(b=>b.onclick=()=>paint(stepFor(g,{chapter:b.dataset.chapter}).id));
 const stepSelect=host.querySelector('[data-guide-step]');stepSelect.innerHTML=g.steps.map((x,i)=>`<option value="${esc(x.id)}">${i+1}. ${esc(x.title)}</option>`).join('');stepSelect.value=s.id;stepSelect.onchange=()=>paint(stepSelect.value);
 const prev=host.querySelector('[data-guide-prev]'),next=host.querySelector('[data-guide-next]');prev.disabled=index===0;next.disabled=index===g.steps.length-1;prev.onclick=()=>paint(g.steps[index-1].id);next.onclick=()=>paint(g.steps[index+1].id);
 host.querySelector('[data-guide-parts]').innerHTML=(s.requirements||[]).map(r=>`<li><button type="button" data-part="${esc(r.instances[0])}">${esc(r.title)}</button> <span>×${r.quantity} modeled instance${r.quantity===1?'':'s'}</span>${r.catalogue?.length?`<small>${r.catalogue.map(c=>esc(c.part_number||c.item)).join(' · ')}</small>`:''}</li>`).join('');
 host.querySelectorAll('[data-part]').forEach(b=>b.onclick=()=>{a.selected=b.dataset.part;a.viewer?.setSelection(a.selected);host.querySelector('[data-guide-isolate]').disabled=false;});
 const complete=host.querySelector('[data-guide-complete]');complete.checked=a.done.has(s.id);complete.onchange=()=>{complete.checked?a.done.add(s.id):a.done.delete(s.id);try{saveProgress(localStorage,g,a.done);}catch{report('Completion stays in this tab because browser storage is unavailable.',true);}};
 const mode=host.querySelector('[data-guide-mode]');mode.value=a.mode;mode.onchange=()=>{a.mode=mode.value;paint(s.id);};
 const explode=host.querySelector('[data-guide-explode]');explode.value=String(a.explode);explode.oninput=()=>{a.explode=+explode.value;a.controller?.applyStep(s.id,{mode:a.mode,explode:a.explode,frame:false});};
 const isolate=host.querySelector('[data-guide-isolate]');isolate.disabled=!a.selected;isolate.onclick=()=>{a.isolate=!a.isolate;paint(s.id);};isolate.setAttribute('aria-pressed',String(a.isolate));
 host.querySelector('[data-guide-reset]').onclick=()=>{a.mode='solid';a.explode=0;a.selected=null;a.isolate=false;a.viewer?.setSelection(null);paint(s.id);};
 writeLocation(location,history,g,s);
 host.dataset.ready='1';
}
start().catch(error=>report(error.message,true));
