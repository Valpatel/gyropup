// Build-specific ensure-state contract. No forced input or app-state mutation.
export function inspectPanel({panel,selector,index}){
 const rect=element=>{if(!element)return null;const r=element.getBoundingClientRect();return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height};};
 const rendered=element=>{
  if(!element?.isConnected)return false;
  const r=rect(element);if(!(r.width>0&&r.height>0))return false;
  for(let e=element;e;e=e.parentElement){const s=getComputedStyle(e);if(s.display==='none'||['hidden','collapse'].includes(s.visibility)||Number(s.opacity)===0)return false;}
  return true; // CSS rendering only; viewport/nested clipping is proved by grid().
 };
 const table=document.querySelectorAll(selector)[index]??null;
 const dataRows=table?[...table.tBodies[0].rows].filter(row=>!row.hidden&&!row.hasAttribute('data-fixed')):[];
 return {atMs:performance.now(),documentId:performance.timeOrigin,requested:panel,scrollX,scrollY,visibility:document.visibilityState,
  tabs:[...document.querySelectorAll('[data-build-tab]')].map(button=>({key:button.dataset.buildTab,pressed:button.getAttribute('aria-pressed'),disabled:button.matches(':disabled')||button.getAttribute('aria-disabled')==='true',rendered:rendered(button),rect:rect(button)})),
  panels:[...document.querySelectorAll('[data-build-panel]')].map(element=>({key:element.dataset.buildPanel,hidden:element.hidden,rendered:rendered(element),rect:rect(element)})),
  target:{exists:Boolean(table),connected:Boolean(table?.isConnected),panel:table?.closest('[data-build-panel]')?.dataset.buildPanel??null,rendered:rendered(table),rect:rect(table),dataRows:dataRows.length,firstId:dataRows[0]?.dataset.partKey??null}};
}

const invalid=message=>{const error=Error(message);error.name='PanelStateError';throw error;};
export function panelDecision(requested,state){
 const {tabs,panels,target}=state;
 if(!Array.isArray(tabs)||!Array.isArray(panels)||!tabs.length)invalid('Missing tab/panel state');
 const tabKeys=tabs.map(x=>x.key),panelKeys=panels.map(x=>x.key);
 if(new Set(tabKeys).size!==tabs.length||new Set(panelKeys).size!==panels.length||JSON.stringify([...tabKeys].sort())!==JSON.stringify([...panelKeys].sort()))invalid('Ambiguous tab/panel identities');
 if(tabs.some(x=>!['true','false'].includes(x.pressed)))invalid('Invalid pressed state');
 const chosen=tabs.filter(x=>x.pressed==='true'),shown=panels.filter(x=>!x.hidden);
 if(chosen.length!==1||shown.length!==1||chosen[0].key!==shown[0].key||panels.some(x=>x.hidden===x.rendered))invalid('Selected tab and CSS-rendered panel disagree');
 const tab=tabs.find(x=>x.key===requested);
 if(!tab||tab.disabled||!tab.rendered)invalid('Requested tab is missing, disabled or not CSS-rendered');
 if(!target?.exists||!target.connected||target.panel!==requested||!(target.dataRows>0)||!target.firstId)invalid('Actual requested table is missing/disconnected/wrong/empty');
 if(chosen[0].key===requested){if(!target.rendered)invalid('Selected panel target is not CSS-rendered');return 'already-selected';}
 if(target.rendered)invalid('Unselected target unexpectedly CSS-rendered');
 return 'native-transition';
}

const describe=error=>{try{return {name:error?.name??typeof error,message:String(error?.message??error)};}catch{return {name:'UnserializableError',message:'Panel error could not be described'};}};
async function sample(inspect,timeout){
 let timer;
 try{return {status:'available',value:await Promise.race([Promise.resolve().then(inspect),new Promise((_,reject)=>timer=setTimeout(()=>{const error=Error('Panel observation exceeded '+timeout+' ms');error.name='PanelObservationTimeoutError';reject(error);},timeout))])};}
 catch(error){return {status:'unavailable',error:describe(error),original:error};}
 finally{clearTimeout(timer);}
}

export async function ensurePanelSelected({requested,inspect,click,waitVisible,record,metadata={},diagnosticTimeout=500}){
 const receipt={...metadata,requested,status:'pending',startedMs:performance.now(),clickAttempts:0,steps:[]};record(receipt);
 const step=async(label,operation)=>{const row={label,status:'pending',startedMs:performance.now()};receipt.steps.push(row);try{const value=await operation();row.status='returned';return value;}catch(error){row.status='failed';row.error=describe(error);throw error;}finally{row.completedMs=performance.now();}};
 let before,after;
 try{
  before=await sample(inspect,diagnosticTimeout);receipt.before={...before};delete receipt.before.original;
  if(before.status!=='available')throw before.original;
  receipt.decision=panelDecision(requested,before.value);
  if(receipt.decision==='native-transition'){
   receipt.clickAttempts++;await step('native tab click',click);await step('target CSS visibility wait',waitVisible);
  }
  after=await sample(inspect,diagnosticTimeout);receipt.after={...after};delete receipt.after.original;
  if(after.status!=='available')throw after.original;
  if(before.value.documentId!==after.value.documentId)invalid('Document changed during panel selection');
  if(panelDecision(requested,after.value)!=='already-selected')invalid('Native transition did not select the requested real target');
  receipt.status='passed';return receipt;
 }catch(error){
  if(receipt.clickAttempts&&!after){after=await sample(inspect,diagnosticTimeout);receipt.after={...after};delete receipt.after.original;}
  receipt.status='failed';receipt.error=describe(error);throw error;
 }finally{receipt.completedMs=performance.now();}
}
