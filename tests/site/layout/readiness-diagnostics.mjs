/** Read-only timeout evidence; never changes a readiness decision or retries it. */
const observers=new WeakMap();
const LIMIT=512;
const PUBLIC_PATH=/^\/(?:designer|web|exports|site|docs|catalog|designs|research|hardware|firmware|cad|sim|_cadagent)(?:\/|$)|^\/(?:index\.(?:html|md)|version\.json|llms\.txt)$/i;
const PRIVATE_ROOT=/^\/(?:tmp|var|private|home|Users|root|run|mnt|media|opt|proc|sys|dev|etc)(?:\/|$)/i;
function decodedEvidence(value){
  let text=String(value??'');
  for(let pass=0;pass<4;pass++){
    text=text.replace(/\\(?:u\{([0-9a-f]{1,6})\}|u([0-9a-f]{4})|x([0-9a-f]{2}))/gi,(_,a,b,c)=>{
      const code=parseInt(a||b||c,16);return code<=0x10ffff?String.fromCodePoint(code):'<encoded-data>';
    }).replace(/\\\//g,'/');
    text=text.replace(/[^\s<>"'`]+/g,token=>{
      let invalid=false;const decoded=token.replace(/(?:%[0-9a-f]{2})+/gi,part=>{
        try{return decodeURIComponent(part).replace(/[\s<>"'`]/g,character=>encodeURIComponent(character));}catch{invalid=true;return '';}
      });
      return invalid?'<encoded-data>':decoded;
    });
  }
  return text;
}
function safeOwnedPath(value){
  const path=value.split(/[?#]/,1)[0];
  return PRIVATE_ROOT.test(path.replace(/^\/+/, '/'))?'<private-path>':path;
}
export function safeReadinessURL(value,ownedOrigin){
  try{
    const normalized=decodedEvidence(value);
    if(!/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(normalized))return '<invalid-url>';
    const url=new URL(normalized,ownedOrigin);
    if(url.protocol==='about:')return ['blank','srcdoc'].includes(url.pathname)?'about:'+url.pathname:'<external-url>';
    return ['http:','https:'].includes(url.protocol)&&url.origin===ownedOrigin?safeOwnedPath(url.pathname):'<external-url>';
  }catch{return '<invalid-url>';}
}
export function safeReadinessText(value,ownedOrigin){
  // Protect sanitized owned URLs while untrusted bare filesystem paths are removed.
  const urls=[];let text=decodedEvidence(value).replace(/(?:[a-z][a-z\d+.-]*:\/\/|(?:https?|wss?|file|about|blob|data|javascript|mailto):|\/\/)[^\s<>"'`]+/gi,url=>{
    const token='\0READINESS_URL_'+urls.length+'\0';urls.push(safeReadinessURL(url,ownedOrigin));return token;
  });
  const path=value=>{try{const url=new URL(value,ownedOrigin);return url.origin===ownedOrigin&&PUBLIC_PATH.test(url.pathname)&&!PRIVATE_ROOT.test(url.pathname)?safeOwnedPath(url.pathname):'<private-path>';}catch{return '<private-path>';}};
  text=text.replace(/(["'`])((?:\/|[a-z]:[\\/]|\\\\)[^\r\n]*?)\1/gi,(_,quote,value)=>quote+path(value)+quote)
    .replace(/(?:[a-z]:[\\/]|\\\\)[^\s<>"'`\0]+/gi,'<private-path>')
    .replace(/(?<![\w.\/\\])\/(?:tmp|var|private|home|Users|root|run|mnt|media|opt|proc|sys|dev|etc)(?:\/|$)[^\r\n<>"'`\0;)]*/gi,'<private-path>')
    .replace(/(?<![\w.\/\\])\/(?!\/)[^\s<>"'`\0]+/g,path)
    .replace(/\b(?:\d{1,3}\.){3}\d{1,3}\b/g,'<address>')
    .replace(/Bearer\s+\S+/gi,'Bearer <redacted>');
  return text.replace(/\0READINESS_URL_(\d+)\0/g,(_,index)=>urls[Number(index)]).slice(0,2000);
}
export function observeReadiness(page,ownedOrigin){
  if(observers.has(page))return observers.get(page);
  let generation=0,route=null,pendingDropped=0;
  const errors=[],consoleErrors=[],failed=[],responses=[],pending=new Map(),counts={errors:0,consoleErrors:0,failed:0,responses:0};
  const text=value=>safeReadinessText(value,ownedOrigin);
  const keep=(name,list,row)=>{counts[name]++;if(list.length===LIMIT)list.shift();list.push({generation,at:Date.now(),...row});};
  const requestRow=request=>({at:Date.now(),url:safeReadinessURL(request.url(),ownedOrigin),method:request.method(),type:request.resourceType()});
  page.on('pageerror',error=>keep('errors',errors,{url:safeReadinessURL(page.url(),ownedOrigin),name:text(error.name),message:text(error.message)}));
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
  const report={schema:'gyropup.layout-readiness-failure/1',observedAt:new Date().toISOString(),coreDeadline:30000,error:{name:safeReadinessText(error.name,ownedOrigin),message:safeReadinessText(error.message,ownedOrigin),stack:safeReadinessText(error.stack,ownedOrigin)},observation:observer.snapshot(),state:null,diagnosticErrors:[]};
  let timer;
  try{report.state=clean(await Promise.race([readState(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Read-only state snapshot exceeded its bound')),boundMs);})]));}
  catch(failure){report.diagnosticErrors.push({phase:'state',message:safeReadinessText(failure.message,ownedOrigin)});}
  finally{clearTimeout(timer);}
  try{await write(report);}catch(failure){report.diagnosticErrors.push({phase:'write',message:safeReadinessText(failure.message,ownedOrigin)});}
  return report;
}
