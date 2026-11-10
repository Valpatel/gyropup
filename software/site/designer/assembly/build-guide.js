import {mountPlayback} from './playback.js';
import {createPartInspector,partMetadata} from './part-inspector.js';
import {createWorkspace,disposeRobot} from './workspace.js';
import {readLocation,stepFor,validateIndex,matchSnapshot,progressKey,readProgress,saveProgress,writeLocation,snapshotsFor,canCompleteStep} from './state.js';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const host=document.getElementById('assembly');
let active=null,request=0,pending=null,applying=false,navigationEvents=null;
const initialAnchor=location.hash,interactionEvents=new AbortController();let userMoved=false;
for(const type of ['wheel','touchmove','pointerdown','keydown'])window.addEventListener(type,()=>{userMoved=true;},{once:true,passive:true,signal:interactionEvents.signal});
const tabProgress=new Map(),assemblyChoices=new Map(),viewStates=new Map();
const workspace=createWorkspace(host,()=>active,paint,report);
const inspector=createPartInspector(host,()=>active,({active,part})=>window.dispatchEvent(new CustomEvent('gyropup:prepare-print',{detail:{guide:active.guide,guideHash:active.guideHash,guideURL:active.url.href,assembly:active.guideAssembly,part}})));
let retryAction=()=>start();
host.querySelector('[data-guide-retry]').onclick=()=>retryAction();
const storage=()=>{try{return globalThis.localStorage;}catch{return null;}};
const loading=host.querySelector('[data-guide-loading]'),loadingBar=loading.querySelector('progress');
function showLoading(message,completed,total){
 loading.hidden=false;host.querySelector('[data-guide-model]').setAttribute('aria-busy','true');
 loading.querySelector('[data-loading-phase]').textContent=message;
 const measured=Number.isInteger(completed)&&Number.isInteger(total)&&total>0&&completed>=0&&completed<=total;
 loading.querySelector('[data-loading-count]').textContent=measured?`${completed} of ${total} parts loaded`:'Checking the selected build files…';
 if(measured){loadingBar.max=total;loadingBar.value=completed;}else loadingBar.removeAttribute('value');
}
function finishLoading(){loading.hidden=true;host.querySelector('[data-guide-model]').setAttribute('aria-busy','false');}
// Adapter for the pinned shared viewer's existing text callback. N starts before
// download/validation, so only N-1 parts are complete. Unknown phases stay indeterminate.
function modelProgress(message,total){
 const part=/^Loading model part (\d+) of (\d+)…$/.exec(message);
 if(part&&Number(part[2])===total&&Number(part[1])>=1&&Number(part[1])<=total){showLoading('Loading model parts…',Number(part[1])-1,total);return;}
 if(message==='Preparing the 3D view…'||message==='Model ready'){showLoading('Preparing the 3D view…',total,total);return;}
 showLoading(message);
}

function selection(name,interactive=false,interaction){
 if(!active)return;
 const wasIsolated=active.isolate;active.selected=name;if(!name)active.isolate=false;
 const part=active.viewer?.parts.find(p=>p.name===name);
 host.querySelector('[data-guide-selection]').textContent=!active.viewer?'3D selection is unavailable; the parts below remain a reading list.':part?`Selected: ${part.title||part.name.replaceAll('_',' ')}`:'Choose a part in the model or the step list.';
 host.querySelector('[data-guide-isolate]').disabled=!name;
 const appearance=host.querySelector('[data-guide-part-mode]');appearance.disabled=!name;appearance.value=active.partModes[name]||'automatic';
 inspector.update(name,{interactive,interaction});
 host.querySelectorAll('[data-part]').forEach(button=>button.setAttribute('aria-pressed',String(JSON.parse(button.dataset.instances).includes(name))));
 if(wasIsolated&&!name&&interactive&&interaction)paint(active.step);
}
function partInfo(name){const a=active,meta=a&&partMetadata(a.guide,a.modelParts||a.viewer?.parts||[],name);return meta?`<b>${esc(meta.title)}</b><small>${esc(meta.name)}${meta.compound?' · compound':''}</small>`:'';}
function partHover(name,point){const tip=host.querySelector('[data-part-tooltip]');tip.hidden=!name;if(!name)return;tip.innerHTML=partInfo(name,true);const bounds=host.querySelector('.assembly-layout').getBoundingClientRect(),x=(point?.clientX??bounds.left)-bounds.left+14,y=(point?.clientY??bounds.top)-bounds.top+14;tip.style.left=Math.max(8,Math.min(x,bounds.width-tip.offsetWidth-8))+'px';tip.style.top=Math.max(8,Math.min(y,bounds.height-tip.offsetHeight-8))+'px';}
function report(message,error=false){host.querySelector('[data-guide-status]').textContent=message;host.querySelector('[data-guide-status]').dataset.state=error?'error':'ready';host.querySelector('[data-guide-retry]').hidden=!error;}
async function start(){
 const startup=++request;pending?.abort();const boot=pending=new AbortController();
 showLoading('Opening the assembly workshop…');
 try{
 const indexURL=new URL('../../web/build-guides/index.json',import.meta.url);
 const {loadGuide,createGuideController,readAsset,parseJSON}=await import('../kit/assembly/guide.js');
 const published=validateIndex(parseJSON(await readAsset(indexURL,{signal:boot.signal,maxBytes:512*1024})));
 if(startup!==request||boot.signal.aborted)return;
 const index=published;
 const selects=new Map([...host.querySelectorAll('[data-assembly-snapshot]')].map(select=>[select.dataset.assemblySnapshot,select]));
 for(const [assembly,select]of selects){const rows=snapshotsFor(index,assembly);if(rows.length)select.replaceChildren(...rows.map(s=>{const o=document.createElement('option');o.value=s.id;o.textContent=s.title;return o;}));}
 async function load(id,route={}){
  retryAction=()=>load(id,route);
  const own=++request;pending?.abort();const abort=pending=new AbortController();
  const row=index.snapshots.find(s=>s.id===id);if(!row)throw new Error('Unknown snapshot');
  const assembly=row.assembly||'turret',select=selects.get(assembly);
  showLoading('Checking the selected build…');
  report(active?'Loading the selected snapshot… The previous model and instructions remain visible until it is ready.':'Loading this exact build snapshot…');
  let nextViewer,posterURLs=new Map();
  try{
   const url=new URL(row.file,indexURL);
   // Shared loader owns schema/model/mesh binding; no guessed or cross-version fallback.
   const [loaded,{createViewer}]=await Promise.all([loadGuide(url.href,{signal:abort.signal,expectedHash:row.sha256}),import('../kit/viewer.js')]);
   const guide=matchSnapshot(row,loaded.guide);
   const posterBytes=await Promise.all(guide.steps.filter(s=>s.poster).map(async s=>[s.id,await readAsset(new URL(s.poster.file,url),{signal:abort.signal,expectedHash:s.poster.sha256,maxBytes:8*1024*1024})]));
   if(own!==request||abort.signal.aborted)return;
   posterURLs=new Map(posterBytes.map(([id,bytes])=>[id,URL.createObjectURL(new Blob([bytes],{type:'image/png'}))]));
   const step=stepFor(guide,route),canvas=document.createElement('div'),panel=document.createElement('div');canvas.className='assembly-canvas';
   let renderError=null;
   try{nextViewer=await createViewer({app:canvas,panel,guideBound:true,manifest:loaded.manifest,manifestUrl:loaded.manifestUrl,signal:abort.signal,
     onProgress:message=>{if(own===request&&!abort.signal.aborted)modelProgress(message,loaded.manifest.parts.length);},
     onSelect:(name,point)=>{if(applying||active?.viewer!==nextViewer||active?.overview)return;if(point)active.playback?.pause();selection(name,!!point,point);},onHover:(name,point)=>{if(active?.viewer===nextViewer&&!active?.overview)partHover(name,point);}});}
   catch(error){if(abort.signal.aborted)throw error;renderError=error;}
   if(renderError&&active?.viewer)throw renderError;
   if(own!==request){nextViewer?.dispose();for(const value of posterURLs.values())URL.revokeObjectURL(value);return;}
   const previous=active;if(previous)viewStates.set(previous.guideHash,{mode:previous.mode,explode:previous.explode,section:previous.section,sectionPlane:previous.sectionPlane});workspace.invalidate();
   const key=progressKey(guide,row.sha256),done=tabProgress.has(key)?new Set([...tabProgress.get(key)].filter(id=>canCompleteStep(guide,id))):readProgress(storage(),guide,row.sha256);
   active={guide,modelParts:loaded.manifest.parts,guideAssembly:assembly,assembly,guideHash:row.sha256,viewer:nextViewer,controller:nextViewer?createGuideController(nextViewer,guide):null,done,url,posterURLs,step:step.id,mode:step.id===guide.source?.overview_step_id?'solid':'ghost',explode:step.id===guide.source?.overview_step_id?0:1,section:1,selected:null,isolate:false,partModes:{},sectionPlane:{axis:'x',flipped:false},...viewStates.get(row.sha256),renderError};
   const model=host.querySelector('[data-guide-model]'),previousNodes=[...model.childNodes];model.replaceChildren(canvas);
   host.querySelector('[data-guide-visual]').hidden=!!renderError;host.querySelector('.assembly-layout').dataset.static=String(!!renderError);
   try{select.value=id;paint(step.id,{preserveAnchor:true});}
   catch(error){active=previous;model.replaceChildren(...previousNodes);if(previous){try{paint(previous.step,{preserveAnchor:true});}catch{}}else{host.dataset.ready='0';}throw error;}
   previous?.playback?.dispose();disposeRobot(previous?.robot);previous?.viewer?.dispose();for(const value of previous?.posterURLs?.values()||[])URL.revokeObjectURL(value);
   if(nextViewer)active.playback=mountPlayback(host,active,()=>active?.viewer===nextViewer,(id)=>{if(active.step!==id)paint(id,{playback:true});});active.player=active.playback?.player;
   finishLoading();
   if(renderError)report('Interactive 3D is unavailable. '+(guide.steps.some(step=>step.poster)?'The same snapshot’s text and diagrams remain below.':'The same snapshot’s text remains below.'),true);
   else report(guide.snapshot.status==='wip'?'Source-bound WIP guide loaded. No physical build release.':'Versioned guide loaded. Its publication status is separate from physical qualification.');
   window.__buildGuide={get active(){return active;},load,apply:id=>paint(id),dispose(){++request;finishLoading();interactionEvents.abort();navigationEvents?.abort();inspector.dispose();workspace.dispose();pending?.abort();active?.playback?.dispose();disposeRobot(active?.robot);active?.viewer?.dispose();for(const value of active?.posterURLs?.values()||[])URL.revokeObjectURL(value);active=null;}};
   if(!renderError&&route.assembly&&route.assembly!==assembly)workspace.choose(route.assembly,false);
   if(pending===abort)pending=null;
  }catch(error){const cancelled=abort.signal.aborted||own!==request;abort.abort();if(pending===abort)pending=null;nextViewer?.dispose();for(const value of posterURLs.values())URL.revokeObjectURL(value);if(cancelled)return;finishLoading();report(error.message+(active?' Your previous build remains selected.':''),true);if(active){const choice=assemblyChoices.get(assembly);select.value=choice?.snapshot||'';}else select.selectedIndex=-1;}
 }
 for(const [assembly,select]of selects)select.onchange=()=>{if(!snapshotsFor(index,assembly).length)return;const choice={snapshot:select.value};if(!active||(active.overview?active.assembly:active.guideAssembly)===assembly)load(select.value,{assembly});else assemblyChoices.set(assembly,choice);};
 workspace.setNavigation(assembly=>{const rows=snapshotsFor(index,assembly);if(!rows.length)return false;const choice=assemblyChoices.get(assembly)||{snapshot:rows[0].id};if(active?.guideAssembly===assembly&&active.guide.snapshot.id===choice.snapshot)workspace.step(choice.step||active.step);else load(choice.snapshot,{assembly,step:choice.step});return true;});
 // Recovery must retain navigation/lifecycle even when the initial route is rejected.
 navigationEvents?.abort();navigationEvents=new AbortController();
 window.addEventListener('popstate',()=>{try{const next=readLocation(location,index),assembly=next.assembly||'turret',row=index.snapshots.find(s=>s.id===next.snapshot);if(row&&(row.assembly||'turret')===assembly){if(next.snapshot!==active?.guide.snapshot.id)load(next.snapshot,next);else workspace.step(stepFor(active.guide,next).id);}else if(!active)load(next.snapshot,next);else workspace.choose(assembly,false);}catch(error){report(error.message+(active?' Your previous build remains selected.':''),true);}},{signal:navigationEvents.signal});
 window.addEventListener('pagehide',()=>window.__buildGuide?.dispose(),{once:true,signal:navigationEvents.signal});
 let route;try{route=readLocation(location,index);}catch(error){selects.get('turret').selectedIndex=-1;throw error;}
 const desired=route.assembly||(route.step||route.chapter?'turret':'combined'),rows=snapshotsFor(index,desired),requested=index.snapshots.find(s=>s.id===route.snapshot);
 if(requested)assemblyChoices.set(requested.assembly||'turret',{snapshot:requested.id,step:route.step});
 const initial=rows.length&&(!requested||(requested.assembly||'turret')!==desired)?rows[0].id:route.snapshot;
 await load(initial,{...route,assembly:desired,step:initial===route.snapshot?route.step:null,chapter:initial===route.snapshot?route.chapter:null});
 if(!initialAnchor||initialAnchor==='#assembly'){await document.fonts.ready;await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));if(!userMoved){const top=document.querySelector('.appnav')?.getBoundingClientRect().bottom||64;window.scrollTo({top:host.getBoundingClientRect().top+scrollY-top-8,behavior:'instant'});}}

 }catch(error){if(startup!==request||boot.signal.aborted)return;if(pending===boot)pending=null;finishLoading();report(error.message,true);}
}
function applyPresentation(s,frame){
 const a=active;
 if(a.selected&&!s.parts.includes(a.selected)){a.selected=null;a.isolate=false;}
 applying=true;
 try{
  a.controller?.applyStep(s.id,{mode:a.mode,explode:a.explode,frame});
  if(a.viewer)for(const [name,mode]of Object.entries(a.partModes))a.viewer.setPartMode(name,mode);
  if(a.selected)a.viewer?.setSelection(a.selected);
  if(a.isolate){a.viewer?.applyState({...a.viewer.getState(),selected:a.selected,isolate:a.selected?[a.selected]:null});if(frame&&a.selected)a.viewer?.frameParts([a.selected],s.camera?.direction);}
  a.viewer?.setSection(a.section);a.viewer?.setSectionPlane?.(a.sectionPlane);
 }
 finally{applying=false;}
}
function partTree(active,step){
 const guide=active.guide,parts=new Map(active.modelParts.map(part=>[part.name,part]));
 function instances(names){const groups=new Map();for(const name of names){const part=parts.get(name),key=part.logical_part||name;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(part);}
  return `<ul>${[...groups].map(([logical,items])=>{const buttons=items.map(part=>{const visible=step.parts.includes(part.name);return `<button type="button" data-part="${esc(part.name)}" data-instances="${esc(JSON.stringify([part.name]))}" aria-pressed="false" ${active.viewer&&visible?'':'disabled'} title="${esc(visible?part.name:'Shown in a later step')}"><span class="assembly-tree-cube" aria-hidden="true">◇</span><span>${esc(part.title||part.name.replaceAll('_',' '))}<small>${esc(part.name)}${part.compound||part.grouped?' · compound':''}${visible?'':' · later step'}</small></span></button>`;}).join('');return `<li>${items.length>1?`<details ${items.some(part=>step.highlight.includes(part.name))?'open':''}><summary>${esc(logical.replaceAll('_',' '))} ×${items.length}</summary>${buttons}</details>`:buttons}</li>`;}).join('')}</ul>`;
 }
 return `<p class="assembly-tree-root">${esc((active.guideAssembly||'turret').replace(/^./,c=>c.toUpperCase()))} <span class="tag warn">${esc(guide.snapshot.status.toUpperCase())}</span></p>`+guide.subassemblies.filter(chapter=>guide.steps.some(operation=>operation.subassembly===chapter.id&&canCompleteStep(guide,operation.id))).map(chapter=>{
  const owned=new Set(chapter.parts),claimed=new Set(),stages=[];
  for(const operation of guide.steps.filter(item=>item.subassembly===chapter.id&&canCompleteStep(guide,item.id))){
   const listed=guide.source?.requirements_by_step?.[operation.id]?.flatMap(row=>row.instances)||operation.highlight,names=listed.filter(name=>owned.has(name)&&!claimed.has(name));
   for(const name of names)claimed.add(name);if(names.length)stages.push(`<details class="assembly-tree-stage" ${operation.id===step.id?'open':''}><summary aria-current="${operation.id===step.id?'step':'false'}">${esc(operation.title)}</summary><button type="button" data-tree-step="${esc(operation.id)}" class="assembly-tree-jump">View step ${guide.steps.indexOf(operation)+1} →</button>${instances(names)}</details>`);
  }
  const context=chapter.parts.filter(name=>!claimed.has(name));return `<details ${chapter.id===step.subassembly?'open':''}><summary>${esc(chapter.title)} <small>${chapter.parts.length} instances</small></summary>${stages.join('')}${context.length?`<details><summary>Modeled context</summary>${instances(context)}</details>`:''}</details>`;
 }).join('');
}
function paint(id,{preserveAnchor=false,playback=false}={}){
 const a=active,g=a.guide,s=stepFor(g,{step:id});partHover(null);a.wantsOverview=false;a.overview=false;a.assembly=a.guideAssembly||'turret';if(a.step!==s.id){if(s.id===g.source?.overview_step_id){a.mode='solid';a.explode=0;}else if(a.step===g.source?.overview_step_id){a.mode='ghost';a.explode=1;}a.selected=null;a.isolate=false;a.partModes={};}a.step=s.id;assemblyChoices.set(a.guideAssembly||'turret',{snapshot:g.snapshot.id,step:s.id});
 if(playback){a.mode='solid';a.explode=0;}else applyPresentation(s,true);
 const index=g.steps.indexOf(s),chapter=g.subassemblies.find(c=>c.id===s.subassembly);
 host.querySelector('[data-guide-source]').innerHTML=`${esc(g.snapshot.revision)} · ${esc(g.snapshot.status)} · <a href="https://github.com/Valpatel/gyropup/tree/${esc(g.snapshot.source_commit)}">Source snapshot</a>`;
 host.querySelector('[data-guide-scope-description]').textContent=`${g.steps.length} authored entries for ${a.guideAssembly||'turret'}, bound to this snapshot. Overview entries are reference views; physical qualification remains separate.`;const plain=host.querySelector('[data-guide-plain]');plain.href=new URL('instructions.html',a.url);plain.textContent=(a.guideAssembly==='turret'&&g.steps.length===12)?'All twelve instructions in plain HTML':`All ${g.steps.length} ${a.guideAssembly} instructions (plain HTML)`;host.querySelector('[data-guide-manifest]').href=a.url.href;
 host.querySelector('[data-guide-warning]').textContent=g.source?.qualification||'Educational work in progress; no physical qualification.';
 host.querySelector('[data-guide-scope]').innerHTML=Object.entries(g.source?.excluded||{}).map(([name,reason])=>`<li><b>${esc(name.replaceAll('_',' '))}</b>: ${esc(reason)}</li>`).join('');
 host.querySelector('[data-guide-title]').textContent=s.title;
 host.querySelector('[data-guide-count]').textContent=`${chapter.title} · ${index+1} / ${g.steps.length}`;
 host.querySelector('[data-guide-text]').textContent=s.text;
 const poster=host.querySelector('[data-guide-poster]');poster.hidden=!s.poster||!a.renderError;
 if(s.poster){poster.src=a.posterURLs.get(s.id);poster.alt=`Step ${index+1}: ${s.title}`;}else{poster.removeAttribute('src');poster.alt='';}
 host.querySelector('[data-guide-chapters]').innerHTML=partTree(a,s);
 host.querySelectorAll('[data-tree-step]').forEach(button=>button.onclick=()=>workspace.step(button.dataset.treeStep));
 host.querySelectorAll('[data-part]').forEach(button=>{const show=()=>{a.playback?.pause();if(a.viewer)a.viewer.setSelection(button.dataset.part);selection(button.dataset.part,true);};button.onclick=show;button.onfocus=show;});
 const stepSelect=host.querySelector('[data-guide-step]');stepSelect.innerHTML=g.steps.map((x,i)=>`<option value="${esc(x.id)}">${i+1}. ${esc(x.title)}</option>`).join('');stepSelect.value=s.id;stepSelect.disabled=false;stepSelect.onchange=()=>paint(stepSelect.value);
 const prev=host.querySelector('[data-guide-prev]'),next=host.querySelector('[data-guide-next]');prev.title='Previous step';next.title='Next step';prev.disabled=index===0;next.disabled=index===g.steps.length-1;prev.onclick=()=>paint(g.steps[index-1].id);next.onclick=()=>paint(g.steps[index+1].id);
 selection(a.selected);
 const complete=host.querySelector('[data-guide-complete]');complete.disabled=!canCompleteStep(g,s.id);complete.title=complete.disabled?'Reference overview · no construction operation to complete':'Mark this construction operation complete';complete.checked=!complete.disabled&&a.done.has(s.id);complete.onchange=()=>{if(!canCompleteStep(g,s.id))complete.checked=false;complete.checked?a.done.add(s.id):a.done.delete(s.id);tabProgress.set(progressKey(g,a.guideHash),new Set(a.done));try{saveProgress(storage(),g,a.done,a.guideHash);}catch{report('Completion stays in this tab because browser storage is unavailable.',true);host.querySelector('[data-guide-retry]').hidden=true;}};
 const mode=host.querySelector('[data-guide-mode]');mode.value=a.mode;mode.onchange=()=>{a.mode=mode.value;paint(s.id);};
 const explode=host.querySelector('[data-guide-explode]');explode.value=String(a.explode);explode.oninput=()=>{a.explode=+explode.value;applyPresentation(s,false);};
 const orientation=host.querySelector('[data-section-orientation]');orientation.hidden=!a.viewer?.setSectionPlane;
 const cutAxis=host.querySelector('[data-guide-cut-axis]');cutAxis.value=a.sectionPlane.axis;const cutFlip=host.querySelector('[data-guide-cut-flip]');cutFlip.setAttribute('aria-pressed',String(a.sectionPlane.flipped));
 const changeCut=()=>{a.viewer?.setSectionPlane?.(a.sectionPlane);cutAxis.value=a.sectionPlane.axis;cutFlip.setAttribute('aria-pressed',String(a.sectionPlane.flipped));};cutAxis.onchange=()=>{a.sectionPlane.axis=cutAxis.value;changeCut();};host.querySelector('[data-guide-cut-rotate]').onclick=()=>{a.sectionPlane.axis={x:'y',y:'z',z:'x'}[a.sectionPlane.axis];changeCut();};cutFlip.onclick=()=>{a.sectionPlane.flipped=!a.sectionPlane.flipped;changeCut();};
 const section=host.querySelector('[data-guide-section]');section.value=String(a.section);section.oninput=()=>{a.section=+section.value;a.viewer?.setSection(a.section);a.viewer?.setSectionPlane?.(a.sectionPlane);};
 const isolate=host.querySelector('[data-guide-isolate]');isolate.disabled=!a.selected;isolate.onclick=()=>{a.isolate=!a.isolate;paint(s.id);};isolate.setAttribute('aria-pressed',String(a.isolate));
 const appearance=host.querySelector('[data-guide-part-mode]');appearance.onchange=()=>{if(!a.selected)return;if(appearance.value==='automatic')delete a.partModes[a.selected];else a.partModes[a.selected]=appearance.value;applyPresentation(s,false);selection(a.selected);};
 host.querySelector('[data-guide-reset]').onclick=()=>{a.mode='solid';a.explode=0;a.section=1;a.sectionPlane={axis:'x',flipped:false};a.selected=null;a.isolate=false;a.partModes={};a.viewer?.setSelection(null);paint(s.id);};
 const previousHash=location.hash;writeLocation(location,history,g,s);const locationURL=new URL(location.href);if(preserveAnchor&&previousHash&&previousHash!=='#assembly')locationURL.hash=previousHash;locationURL.searchParams.delete('view');locationURL.searchParams.set('assembly',a.guideAssembly||'turret');history.replaceState(null,'',locationURL);
 workspace.present();
 host.dataset.ready='1';
}
start();
