/** Product navigation/progress only; the shared viewer owns 3D guide state. */
const ID=/^[a-zA-Z0-9][a-zA-Z0-9._-]*$/;
export function readLocation(location,index){
 const q=new URLSearchParams(location.search),snapshot=q.get('snapshot')||index.snapshots[0]?.id;
 if(!index.snapshots.some(s=>s.id===snapshot))throw new Error('This build snapshot is unavailable. Choose one of the published snapshots.');
 const assembly=q.get('assembly');if(assembly&&!['robot','turret','combined'].includes(assembly))throw new Error('Unknown assembly selection.');
 return {snapshot,step:q.get('step'),chapter:q.get('chapter'),assembly};
}
export function stepFor(guide,{step,chapter}={}){
 if(step){const found=guide.steps.find(s=>s.id===step);if(!found)throw new Error('This instruction step does not exist in the selected snapshot.');return found;}
 if(chapter){const found=guide.steps.find(s=>s.subassembly===chapter);if(!found)throw new Error('This subassembly does not exist in the selected snapshot.');return found;}
 return guide.steps[0];
}
export function validateIndex(index){
 if(index?.schema!=='gyropup.build-guides/1'||!Array.isArray(index.snapshots)||!index.snapshots.length)throw new Error('No published build snapshots are available.');
 const ids=new Set();for(const s of index.snapshots){
  if(s.assembly!==undefined&&!['robot','turret','combined'].includes(s.assembly))throw new Error('Invalid snapshot assembly identity.');
  if(!ID.test(s.id)||ids.has(s.id)||typeof s.title!=='string'||!['wip','released'].includes(s.status)||!/^[a-zA-Z0-9][a-zA-Z0-9/._-]*\.json$/.test(s.file)||s.file.includes('..')||!s.sha256?.match(/^[0-9a-f]{64}$/))throw new Error('Invalid build snapshot index.');
  ids.add(s.id);
 }
 return index;
}
export function matchSnapshot(entry,guide){
 if(entry.id!==guide.snapshot.id||entry.status!==guide.snapshot.status)throw new Error('Snapshot index does not match the bound guide identity.');
 return guide;
}
export function progressKey(guide,guideHash){
 if(!/^[0-9a-f]{64}$/.test(guideHash||''))throw new Error('Completion needs the exact guide digest.');
 return `gyropup.assembly.${guide.snapshot.id}.${guideHash}`;
}
export function canCompleteStep(guide,id){return guide.steps.some(step=>step.id===id)&&id!==guide.source?.overview_step_id&&guide.source?.step_kinds?.[id]!=='reference';}
export function readProgress(storage,guide,guideHash){
 try{const key=progressKey(guide,guideHash),x=JSON.parse(storage.getItem(key)||'[]'),clean=Array.isArray(x)?[...new Set(x.filter(id=>canCompleteStep(guide,id)))]:[];if(Array.isArray(x)&&JSON.stringify(x)!==JSON.stringify(clean)){try{storage.setItem(key,JSON.stringify(clean));}catch{}}return new Set(clean);}catch{return new Set();}
}
export function saveProgress(storage,guide,done,guideHash){storage.setItem(progressKey(guide,guideHash),JSON.stringify([...done].filter(id=>canCompleteStep(guide,id))));}
export function writeLocation(location,history,guide,step){
 const url=new URL(location.href);url.searchParams.set('snapshot',guide.snapshot.id);url.searchParams.set('chapter',step.subassembly);url.searchParams.set('step',step.id);url.hash='assembly';history.replaceState(null,'',url);
}

/** Legacy product guide entries are turret guides; future authored guides may declare their assembly. */
export function snapshotsFor(index,assembly){if(!['robot','turret','combined'].includes(assembly))throw new Error('Unknown assembly');return index.snapshots.filter(snapshot=>(snapshot.assembly||'turret')===assembly);}
