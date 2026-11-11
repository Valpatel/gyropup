import assert from 'node:assert/strict';
import {framing,horizontalOffsets,viewportSupport} from './clip-geometry.mjs';

// Serialized once against the pinned real table/header. Native scrolling only.
export function scrollHeaderOnce(table,{header,deadlineEpochMs}){
 if(!Number.isFinite(deadlineEpochMs)||Date.now()>deadlineEpochMs){const error=Error('Native action reached browser after positioning deadline');error.name='PositionDeadlineError';throw error;}
 const state=()=>({documentId:performance.timeOrigin,tableConnected:table.isConnected,headerConnected:header.isConnected,sameDocument:table.ownerDocument===document&&header.ownerDocument===document,sameHeader:table.querySelector('thead th.cad-part-identity')===header});
 const valid=s=>s.tableConnected&&s.headerConnected&&s.sameDocument&&s.sameHeader;
 const before=state();if(!valid(before)){const error=Error('Pinned native scroll target changed');error.name='TargetChangedError';throw error;}
 const startedMs=performance.now();
 header.scrollIntoView({behavior:'instant',block:'center',inline:'nearest'});
 const completedMs=performance.now(),after=state();
 if(!valid(after)||before.documentId!==after.documentId){const error=Error('Native scroll target changed during call');error.name='TargetChangedError';throw error;}
 return {before,after,startedMs,completedMs,options:{behavior:'instant',block:'center',inline:'nearest'}};
}

export function sampleStability(a,b,tolerance=1){
 const reasons=[];let maxDelta=0;
 const project=s=>({documentId:s.documentId,panel:s.panel,identityId:s.identity?.id,table:s.table,header:s.header,identity:s.identity,viewport:s.viewport,ancestors:s.ancestors.map(x=>({key:x.key,role:x.role,clip:x.clip,scrollTop:x.scrollTop,scrollLeft:x.scrollLeft}))});
 const compare=(x,y,path)=>{
  if(typeof x==='number'&&typeof y==='number'){const delta=Math.abs(x-y);maxDelta=Math.max(maxDelta,delta);if(!Number.isFinite(delta)||delta>tolerance)reasons.push(path+' drift');return;}
  if(x&&y&&typeof x==='object'&&typeof y==='object'){
   const keys=Object.keys(x).sort();if(JSON.stringify(keys)!==JSON.stringify(Object.keys(y).sort())){reasons.push(path+' shape changed');return;}
   for(const key of keys)compare(x[key],y[key],path+'.'+key);return;
  }
  if(x!==y)reasons.push(path+' identity changed');
 };
 compare(project(a),project(b),'geometry');return {pass:reasons.length===0,maxDelta,reasons};
}

const fail=(name,message)=>{const error=Error(message);error.name=name;throw error;};
function requireTarget(sample,documentId){
 if(sample.documentId!==documentId||!sample.target?.headerPinned||!sample.target.sameHeader||!sample.target.tableConnected||!sample.target.headerConnected||!sample.target.sameDocument)fail('TargetChangedError','Same connected table/header/document required');
 const support=viewportSupport(sample);if(!support.pass)fail('UnsupportedViewportError',support.reasons.join('; '));
}

// Finite workflow, no polling/retry. Caller supplies one total five-second deadline.
export async function positionHeaderOnce({resolve,collect,scroll,wait,active,phase}){
 const step=async(name,operation)=>{
  active();const row={phase:name,status:'pending',startedMs:performance.now()};phase(row);
  try{const value=await operation();active();row.status='available';row.value=value;return value;}
  catch(error){row.status='unavailable';row.error={name:error.name,message:error.message};throw error;}
  finally{row.completedMs=performance.now();}
 };
 await step('resolve pinned table/header',resolve);
 const before=await step('before native scroll',collect);requireTarget(before,before.documentId);
 const native=await step('one native Element.scrollIntoView',scroll);
 if(native.before.documentId!==before.documentId||native.after.documentId!==before.documentId)fail('TargetChangedError','Native scroll document changed');
 const first=await step('passive sample 1',collect);requireTarget(first,before.documentId);
 await step('100 ms passive gap',()=>wait(100));
 const second=await step('passive sample 2',collect);requireTarget(second,before.documentId);
 try{
  assert.deepEqual(horizontalOffsets(first),horizontalOffsets(before));assert.deepEqual(horizontalOffsets(second),horizontalOffsets(before));
 }catch{fail('HorizontalPositionChangedError','Native scrolling changed an observed horizontal offset');}
 const stability=sampleStability(first,second,1);
 if(!stability.pass)fail('UnstableFramingError',JSON.stringify(stability));
 for(const sample of [first,second]){const proof=framing(sample);if(!proof.pass)fail('InvalidFramingError',JSON.stringify(proof));}
 return {before,native,first,second,stability};
}
