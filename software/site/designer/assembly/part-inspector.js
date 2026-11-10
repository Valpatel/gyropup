/** One source-backed selection popover. Picking remains owned by the shared viewer. */
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function partMetadata(guide,parts,name){
 const part=parts.find(p=>p.name===name);if(!part)return null;
 const requirement=Object.values(guide.source?.requirements_by_step||{}).flat().find(row=>row.instances?.includes(name));
 const manufacturing=guide.source?.manufacturing_by_part?.[name]||null;
 return {name,title:part.title||name.replaceAll('_',' '),logical:part.logical_part||null,compound:!!(part.compound||part.grouped),material:part.material||manufacturing?.plan?.material||null,requirement,manufacturing,revision:guide.snapshot.revision,snapshot:guide.snapshot.id};
}
export function createPartInspector(host,getActive,onPrint){
 const popup=host.querySelector('[data-part-popup]'),details=popup.querySelector('[data-part-details]'),print=popup.querySelector('[data-part-print]'),status=popup.querySelector('[data-part-file-status]');
 const events=new AbortController();let open=false,name=null,point=null;
 function close(){open=false;popup.hidden=true;}
 function place(){if(!open)return;const bounds=host.querySelector('.assembly-layout').getBoundingClientRect(),size=popup.getBoundingClientRect();const x=point?point.clientX-bounds.left+12:bounds.width-size.width-16,y=point?point.clientY-bounds.top+12:host.querySelector('.assembly-nav').getBoundingClientRect().bottom-bounds.top+12;popup.style.left=Math.max(8,Math.min(x,bounds.width-size.width-8))+'px';popup.style.top=Math.max(8,Math.min(y,bounds.height-size.height-8))+'px';}
 function update(selected,{interactive=false,interaction}={}){
  const active=getActive(),meta=active&&partMetadata(active.guide,active.modelParts||active.viewer?.parts||[],selected);name=selected;
  if(!meta){close();return;}if(interactive){open=true;point=interaction||null;const focused=document.activeElement;if(!point&&focused?.matches('[data-part]')){const r=focused.getBoundingClientRect();point={clientX:r.right,clientY:r.top};}}
  popup.hidden=!open;if(!open)return;
  details.innerHTML=`<b>${esc(meta.title)}</b><code>${esc(meta.name)}</code>${meta.compound?'<p class="assembly-compound">Compound source mesh · components shown together</p>':''}<dl>${meta.material?`<dt>Material</dt><dd>${esc(meta.material)}</dd>`:''}${meta.requirement?`<dt>Operation qty</dt><dd>${meta.requirement.quantity} modeled instance${meta.requirement.quantity===1?'':'s'}</dd>`:''}<dt>Snapshot</dt><dd>${esc(meta.revision)}</dd>${meta.requirement?.catalogue?.length?`<dt>BOM</dt><dd>${meta.requirement.catalogue.map(c=>esc(c.part_number||c.item||c.key)).join('<br>')}</dd>`:''}</dl>`;
  const kind=meta.manufacturing?.kind;print.hidden=kind!=='print'||!meta.manufacturing?.originals?.length;print.onclick=()=>onPrint({active,part:meta});
  status.textContent=kind==='bought'?'Bought component · use the source BOM to order.':kind==='machine'||kind==='sheet'?'Fabricated part · use its source drawings.':kind==='print'?'Original file identity is verified before print preparation.':'Manufacturing files are not mapped for this snapshot.';
  place();
 }
 popup.querySelector('[data-part-close]').onclick=close;
 document.addEventListener('pointerdown',event=>{if(open&&!popup.contains(event.target)&&!event.target.closest('[data-part]'))close();},{capture:true,signal:events.signal});
 document.addEventListener('keydown',event=>{if(event.key==='Escape')close();},{signal:events.signal});window.addEventListener('resize',place,{signal:events.signal});
 return {update,close,dispose(){close();events.abort();},get selected(){return name;}};
}
