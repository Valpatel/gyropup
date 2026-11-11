/** Read-only timeout evidence; never changes a readiness decision or retries it. */
const observers=new WeakMap();
const LIMIT=512;
export function safeReadinessURL(value,ownedOrigin){
  try{const url=new URL(value);return url.protocol==='about:'?url.href:url.origin===ownedOrigin?url.pathname:'<external-url>';}catch{return '<invalid-url>';}
}
export function safeReadinessText(value,ownedOrigin){
  return String(value??'').replace(/https?:\/\/[^\s<>"']+/g,url=>safeReadinessURL(url,ownedOrigin))
    .replace(/\b(?:\d{1,3}\.){3}\d{1,3}\b/g,'<address>')
    .replace(/\/(?:home|Users)\/[^\s<>"']+/g,'<private-path>')
    .replace(/Bearer\s+\S+/gi,'Bearer <redacted>').slice(0,2000);
}
export function observeReadiness(page,ownedOrigin){
  if(observers.has(page))return observers.get(page);
  let generation=0,route=null,pendingDropped=0;
  const errors=[],consoleErrors=[],failed=[],responses=[],pending=new Map(),counts={errors:0,consoleErrors:0,failed:0,responses:0};
  const text=value=>safeReadinessText(value,ownedOrigin);
  const keep=(name,list,row)=>{counts[name]++;if(list.length===LIMIT)list.shift();list.push({generation,at:Date.now(),...row});};
  const requestRow=request=>({at:Date.now(),url:safeReadinessURL(request.url(),ownedOrigin),method:request.method(),type:request.resourceType()});
  page.on('pageerror',error=>keep('errors',errors,{url:safeReadinessURL(page.url(),ownedOrigin),name:error.name,message:text(error.message)}));
  page.on('console',message=>{if(['error','warning'].includes(message.type()))keep('consoleErrors',consoleErrors,{url:safeReadinessURL(page.url(),ownedOrigin),type:message.type(),message:text(message.text())});});
  page.on('request',request=>{if(pending.size===LIMIT){pending.delete(pending.keys().next().value);pendingDropped++;}pending.set(request,{generation,...requestRow(request)});});
  page.on('requestfinished',request=>pending.delete(request));
  page.on('requestfailed',request=>{keep('failed',failed,{...pending.get(request),...requestRow(request),error:text(request.failure()?.errorText)});pending.delete(request);});
  page.on('response',response=>{if(response.status()>=400)keep('responses',responses,{generation:pending.get(response.request?.())?.generation??generation,url:safeReadinessURL(response.url(),ownedOrigin),status:response.status()});});
  const api={begin(nextRoute){route=safeReadinessURL(new URL(nextRoute,ownedOrigin).href,ownedOrigin);generation++;},snapshot(){
    const relevant=rows=>rows.filter(row=>row.generation===0||row.generation===generation);
    const outstanding=relevant([...pending.values()]);
    return{route,generation,errors:relevant(errors),consoleErrors:relevant(consoleErrors),failed:relevant(failed),responses:relevant(responses),pending:outstanding.slice(0,LIMIT),counts:{...counts},pendingCount:outstanding.length,pendingDropped,limit:LIMIT};
  }};
  observers.set(page,api);return api;
}
/** Executed in the actual page only after its original core wait rejects. */
export function readReadinessState(){
  const sim=window.__sim,robot=sim?.state.robot,canvas=document.querySelector('#app canvas');
  return{documentState:document.readyState,bodyReady:document.body?.dataset.ready??null,stageError:document.body?.dataset.stageError??null,
    path:location.pathname,startupText:document.querySelector('#sim-startup')?.innerText??null,
    statusText:[...document.querySelectorAll('[data-state="error"],[data-bootstrap-error]')].map(node=>node.innerText).join('\n'),
    selectedDesign:document.querySelector('#design-select')?.value??null,
    pendingMermaid:document.querySelectorAll('pre.mermaid,pre>code.language-mermaid').length,
    diagramStates:[...document.querySelectorAll('.cad-diagram')].map(node=>node.dataset.state??null),
    assemblyReady:document.querySelector('#assembly')?.dataset.ready??null,
    scene:!sim?null:{modelKey:sim.state.modelKey??null,robot:!!robot,bench:!!sim.state.bench,replay:sim.state.replay?.key??null,transition:!!sim.state.transition,
      presentation:robot?.presentation?.mode??null,robotId:robot?.presentation?.robotId??null,
      frame:sim.stage.renderer.info.render.frame,triangles:sim.stage.renderer.info.render.triangles,contextLost:sim.stage.renderer.getContext().isContextLost()},
    canvas:!canvas?null:{width:canvas.width,height:canvas.height,opacity:getComputedStyle(canvas).opacity}};
}
export async function retainReadinessFailure({error,observer,readState,write,ownedOrigin,boundMs=2000}){
  const clean=value=>Array.isArray(value)?value.map(clean):value&&typeof value==='object'?Object.fromEntries(Object.entries(value).map(([key,item])=>[key,clean(item)])):typeof value==='string'?safeReadinessText(value,ownedOrigin):value;
  const report={schema:'gyropup.layout-readiness-failure/1',observedAt:new Date().toISOString(),coreDeadline:30000,error:{name:error.name,message:safeReadinessText(error.message,ownedOrigin),stack:safeReadinessText(error.stack,ownedOrigin)},observation:observer.snapshot(),state:null,diagnosticErrors:[]};
  let timer;
  try{report.state=clean(await Promise.race([readState(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Read-only state snapshot exceeded its bound')),boundMs);})]));}
  catch(failure){report.diagnosticErrors.push({phase:'state',message:safeReadinessText(failure.message,ownedOrigin)});}
  finally{clearTimeout(timer);}
  try{await write(report);}catch(failure){report.diagnosticErrors.push({phase:'write',message:safeReadinessText(failure.message,ownedOrigin)});}
  return report;
}
