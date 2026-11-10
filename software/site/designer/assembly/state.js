/** Product navigation/progress only; the shared viewer owns 3D guide state. */
const ID=/^[a-zA-Z0-9][a-zA-Z0-9._-]*$/;
export function readLocation(location,index){
 const q=new URLSearchParams(location.search),snapshot=q.get('snapshot')||index.snapshots[0]?.id;
 if(!index.snapshots.some(s=>s.id===snapshot))throw new Error('This build snapshot is unavailable. Choose one of the published snapshots.');
 return {snapshot,step:q.get('step'),chapter:q.get('chapter')};
}
export function stepFor(guide,{step,chapter}={}){
 if(step){const found=guide.steps.find(s=>s.id===step);if(!found)throw new Error('This instruction step does not exist in the selected snapshot.');return found;}
 if(chapter){const found=guide.steps.find(s=>s.subassembly===chapter);if(!found)throw new Error('This subassembly does not exist in the selected snapshot.');return found;}
 return guide.steps[0];
}
export function validateIndex(index){
 if(index?.schema!=='gyropup.build-guides/1'||!Array.isArray(index.snapshots)||!index.snapshots.length)throw new Error('No published build snapshots are available.');
 const ids=new Set();for(const s of index.snapshots){
  if(!ID.test(s.id)||ids.has(s.id)||typeof s.title!=='string'||!['wip','released'].includes(s.status)||!/^[a-zA-Z0-9][a-zA-Z0-9/._-]*\.json$/.test(s.file)||s.file.includes('..')||!s.sha256?.match(/^[0-9a-f]{64}$/))throw new Error('Invalid build snapshot index.');
  ids.add(s.id);
 }
 return index;
}
export function progressKey(guide,guideHash){
 if(!/^[0-9a-f]{64}$/.test(guideHash||''))throw new Error('Completion needs the exact guide digest.');
 return `gyropup.assembly.${guide.snapshot.id}.${guideHash}`;
}
export function readProgress(storage,guide,guideHash){
 try{const x=JSON.parse(storage.getItem(progressKey(guide,guideHash))||'[]');return new Set(Array.isArray(x)?x.filter(id=>guide.steps.some(s=>s.id===id)):[]);}catch{return new Set();}
}
export function saveProgress(storage,guide,done,guideHash){storage.setItem(progressKey(guide,guideHash),JSON.stringify([...done].filter(id=>guide.steps.some(s=>s.id===id))));}
export function writeLocation(location,history,guide,step){
 const url=new URL(location.href);url.searchParams.set('snapshot',guide.snapshot.id);url.searchParams.set('chapter',step.subassembly);url.searchParams.set('step',step.id);url.hash='assembly';history.replaceState(null,'',url);
}
