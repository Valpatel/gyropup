/** Test-only observation of one required screenshot; never retry or replace it. */
import {performance} from 'node:perf_hooks';
import path from 'node:path';

export function captureScope(value='all'){
 if(!['all','fresh-capture'].includes(value))throw Error('Unknown docking case: '+value);
 return value;
}
export function requireFreshCaptureRuntime({engine,channel,version}){
 if(engine!=='chromium'||channel!=='chromium'||version!=='141.0.7390.37')throw Error('Fresh capture control requires bundled pinned Chromium141.0.7390.37; no browser substitution');
}

const errorInfo=error=>{try{return{name:error?.name||typeof error,message:String(error?.message??error)};}catch{return{name:'UnserializableError',message:'Diagnostic could not describe this error'};}};
const phase=(method,params)=>{
 if(!method.startsWith('Runtime.'))return method;
 const script=(params?.expression||params?.functionDeclaration||'')+JSON.stringify(params?.arguments||[]);
 return script.includes('document.fonts.ready')?'font-ready':script.includes('inPagePrepareForScreenshots')?'prepare-screenshot':script.includes('__pwCleanupScreenshot')?'restore-screenshot':method;
};

/** Pinned Chromium internals. Wrappers preserve receiver, arguments and return identity. */
export function observeCaptureProtocol(Connection,{now=()=>performance.now(),limit=100}={}){
 let active=null;const pending=new WeakMap(),prototype=Connection?.prototype;
 const send=prototype?._rawSend,receive=prototype?._onMessage;
 const fault=error=>{if(active)active.observerErrors.push(errorInfo(error));};
 function wrappedSend(session,method,params){
  let started;try{if(active)started=now();}catch(error){fault(error);}
  const result=send.apply(this,arguments);
  try{if(active&&/^(Page\.(getLayoutMetrics|captureScreenshot)|Runtime\.(evaluate|callFunctionOn))$/.test(method)){
   if(active.calls.length>=limit){active.droppedCalls++;return result;}
   const row={id:result,method,phase:phase(method,params),sentMs:started};active.calls.push(row);
   if(!pending.has(this))pending.set(this,new Map());pending.get(this).set(result,row);
  }}catch(error){fault(error);}return result;
 }
 function wrappedReceive(message){
  try{const requests=pending.get(this),row=requests?.get(message.id);if(active&&row){row.receivedMs=now();row.durationMs=row.receivedMs-row.sentMs;row.errorCode=message.error?.code??null;if(row.method==='Page.captureScreenshot')row.base64Length=typeof message.result?.data==='string'?message.result.data.length:null;requests.delete(message.id);}}catch(error){fault(error);}
  return receive.apply(this,arguments);
 }
 if(prototype){if(typeof send!=='function'||typeof receive!=='function')throw Error('Pinned capture protocol methods are unavailable');prototype._rawSend=wrappedSend;prototype._onMessage=wrappedReceive;}
 return{
  begin(){if(active)throw Error('Capture observation already active');active={supported:Boolean(prototype),calls:[],observerErrors:[],droppedCalls:0};},
  finish(){const result=active;active=null;return result;},
  dispose(){active=null;if(prototype){if(prototype._rawSend===wrappedSend)prototype._rawSend=send;if(prototype._onMessage===wrappedReceive)prototype._onMessage=receive;}}
 };
}

async function bounded(operation,timeout){
 let timer;try{return await Promise.race([Promise.resolve().then(operation),new Promise((_,reject)=>timer=setTimeout(()=>{const error=Error('Capture diagnostic deadline exceeded');error.name='DiagnosticTimeoutError';reject(error);},timeout))]);}finally{clearTimeout(timer);}
}
export async function readCaptureDiagnostic(collect,timeout=500){try{return{status:'available',value:await bounded(collect,timeout)};}catch(error){return{status:'unavailable',error:errorInfo(error)};}}

/** Diagnostic failures cannot replace the exact original capture rejection. */
export async function observeScreenshot({capture,options,collect,writeReport,protocol,metadata={},now=()=>performance.now(),diagnosticTimeout=500}){
 const stamp=()=>{try{return now();}catch{return null;}};
 const report={schema:'gyropup.capture-diagnostic/1',metadata,options:{file:path.basename(options.path),timeout:options.timeout},before:await readCaptureDiagnostic(()=>collect('before'),diagnosticTimeout)};
 try{protocol.begin();}catch(error){report.protocolStartError=errorInfo(error);}
 let value,failure,failed=false,writeFailure,writeFailed=false;report.capture={startedMs:stamp()};
 try{value=await capture(options);report.capture.status='passed';}catch(error){failed=true;failure=error;report.capture.status='failed';report.capture.error=errorInfo(error);}
 finally{report.capture.completedMs=stamp();report.capture.durationMs=report.capture.completedMs===null||report.capture.startedMs===null?null:report.capture.completedMs-report.capture.startedMs;try{report.protocol=protocol.finish();}catch(error){report.protocolEndError=errorInfo(error);}}
 if(Number.isFinite(metadata.referenceArtifactBoundMs)&&metadata.referenceArtifactBoundMs>0){
  report.capture.completionComparedWithReference=failed?'capture-failed':report.capture.durationMs===null?'duration-unavailable':report.capture.durationMs<=metadata.referenceArtifactBoundMs?'completed-within-reference-bound':'completed-after-reference-bound';
 }
 report.after=await readCaptureDiagnostic(()=>collect('after'),diagnosticTimeout);
 try{await bounded(()=>writeReport(report),diagnosticTimeout);}catch(error){writeFailed=true;writeFailure=error;}
 if(failed)throw failure;
 if(writeFailed)throw writeFailure;
 return value;
}

/** Passive browser/page state only: no forced render, frame wait or focus change. */
export async function watchCapturePage(page,{now=()=>performance.now()}={}){
 const pending=new Map(),events=[],listeners=[];
 const listen=(type,callback)=>{page.on(type,callback);listeners.push([type,callback]);};
 const pathname=url=>{try{return new URL(url).pathname;}catch{return'<unparsed>';}};
 listen('request',request=>pending.set(request,{path:pathname(request.url()),resourceType:request.resourceType(),startedMs:now()}));
 for(const type of ['requestfinished','requestfailed'])listen(type,request=>{pending.delete(request);if(type==='requestfailed')events.push({type,path:pathname(request.url()),atMs:now()});});
 listen('pageerror',error=>events.push({type:'pageerror',atMs:now(),error:errorInfo(error)}));listen('crash',()=>events.push({type:'crash',atMs:now()}));
 listen('framenavigated',frame=>{if(frame===page.mainFrame())events.push({type:'navigation',path:pathname(frame.url()),atMs:now()});});
 await page.addInitScript(()=>{window.__dockingCaptureContextEvents=[];for(const type of ['webglcontextlost','webglcontextrestored'])document.addEventListener(type,()=>window.__dockingCaptureContextEvents.push({type,atMs:performance.now()}),true);});
 const dispose=()=>{for(const [type,callback]of listeners)page.off(type,callback);page.off('close',dispose);};page.once('close',dispose);
 return{
  async snapshot(){const state=await page.evaluate(()=>{
   const a=window.__buildGuide?.active,stage=a?.viewer?.stage,renderer=stage?.renderer,canvas=renderer?.domElement;
   return{documentId:performance.timeOrigin,visibility:document.visibilityState,hasFocus:document.hasFocus(),readyState:document.readyState,fullscreen:Boolean(document.fullscreenElement),workspaceFullscreen:document.querySelector('.assembly-layout')?.dataset.fullscreen??null,fonts:{status:document.fonts.status,faces:[...document.fonts].map(face=>({family:face.family,status:face.status}))},renderer:renderer?{frame:renderer.info.render.frame,calls:renderer.info.render.calls,triangles:renderer.info.render.triangles,programs:renderer.info.programs?.length,memory:{...renderer.info.memory},contextLost:renderer.getContext().isContextLost()}:null,canvas:canvas?{width:canvas.width,height:canvas.height}:null,contextEvents:window.__dockingCaptureContextEvents,stageError:document.body.dataset.stageError??null,section:a?.viewer?.getSectionState(),player:a?.player?.getState(),scrollY};
  });return{...state,pendingRequests:[...pending.values()],pageEvents:[...events]};},dispose
 };
}
