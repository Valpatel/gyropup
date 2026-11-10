import test from 'node:test';
import assert from 'node:assert/strict';
import {observeCaptureProtocol,observeScreenshot} from './capture-diagnostics.mjs';

function fixture(overrides={}){
 const options={path:'/capture/required.png',timeout:15000},value=Buffer.from('actual capture'),reports=[],calls=[];
 const input={options,capture:argument=>{calls.push(argument);return Promise.resolve(value);},collect:phase=>({phase,documentId:1}),writeReport:report=>reports.push(report),protocol:{begin(){},finish(){return{calls:[]};}},...overrides};
 return{options,value,reports,calls,input};
}

test('one required capture receives the original options and returns its exact value',async()=>{
 const f=fixture();assert.strictEqual(await observeScreenshot(f.input),f.value);assert.deepEqual(f.calls,[f.options]);assert.strictEqual(f.calls[0],f.options);assert.equal(f.options.timeout,15000);assert.equal(f.reports.length,1);assert.equal(f.reports[0].capture.status,'passed');assert.deepEqual(f.reports[0].options,{file:'required.png',timeout:15000});
});

test('capture rejection remains the identical failure; no retry or later phase can run',async()=>{
 const original=Object.assign(Error('Timeout 15000ms exceeded'),{name:'TimeoutError'});let attempts=0,later=false;
 const f=fixture({capture:()=>{attempts++;return Promise.reject(original);}});
 await assert.rejects(async()=>{await observeScreenshot(f.input);later=true;},error=>error===original);
 assert.equal(attempts,1);assert.equal(later,false);assert.equal(f.reports.length,1);assert.equal(f.reports[0].capture.status,'failed');assert.equal(f.reports[0].capture.error.name,'TimeoutError');
});

test('collection, protocol observation, timing and report-write errors cannot replace capture failure',async()=>{
 const original=Error('required capture failed'),diagnostic=Error('diagnostic failed');let attempts=0;
 const f=fixture({capture:()=>{attempts++;throw original;},collect:()=>{throw diagnostic;},protocol:{begin(){throw diagnostic;},finish(){throw diagnostic;}},now:()=>{throw diagnostic;},writeReport:()=>{throw diagnostic;}});
 await assert.rejects(observeScreenshot(f.input),error=>error===original);assert.equal(attempts,1);
});

test('a stalled observation is bounded and reported; a stalled writer still preserves capture failure',async()=>{
 const original=Error('capture failed'),never=()=>new Promise(()=>{});let report,attempts=0;
 const f=fixture({diagnosticTimeout:10,collect:never,capture:()=>{attempts++;throw original;},writeReport:value=>{report=value;return never();}});
 await assert.rejects(observeScreenshot(f.input),error=>error===original);assert.equal(attempts,1);assert.equal(report.before.status,'unavailable');assert.equal(report.after.error.name,'DiagnosticTimeoutError');assert.equal(report.capture.status,'failed');
});

test('a successful PNG cannot be reported complete when required diagnostic writing fails',async()=>{
 const writeError=Error('evidence write failed'),f=fixture({writeReport:()=>{throw writeError;}});await assert.rejects(observeScreenshot(f.input),error=>error===writeError);assert.equal(f.calls.length,1);
});

test('even an undescribable original rejection retains its identity',async()=>{
 const original=Object.create(null),f=fixture({capture:()=>{throw original;}});await assert.rejects(observeScreenshot(f.input),error=>error===original);assert.equal(f.reports[0].capture.status,'failed');
});

test('protocol wrappers preserve this, arguments, result and rejection identity, then restore originals',async()=>{
 const receivedPromise=Promise.resolve('native result'),params={clip:{width:1366,height:900}},response={id:7,result:{data:'DO_NOT_PUBLISH_RAW_SCREENSHOT'}};let sentThis,sentArgs,receivedThis,receivedArgument;
 class Connection{_rawSend(...args){sentThis=this;sentArgs=args;return 7;}_onMessage(message){receivedThis=this;receivedArgument=message;return receivedPromise;}}
 const send=Connection.prototype._rawSend,receive=Connection.prototype._onMessage,observer=observeCaptureProtocol(Connection);const connection=new Connection();observer.begin();
 assert.equal(connection._rawSend('session','Page.captureScreenshot',params),7);assert.strictEqual(sentThis,connection);assert.strictEqual(sentArgs[2],params);
 assert.strictEqual(connection._onMessage(response),receivedPromise);assert.strictEqual(receivedThis,connection);assert.strictEqual(receivedArgument,response);
 const report=observer.finish();assert.equal(report.calls.length,1);assert.equal(report.calls[0].base64Length,response.result.data.length);assert.ok(!JSON.stringify(report).includes(response.result.data));assert.ok(!JSON.stringify(report).includes('clip'));
 observer.dispose();assert.strictEqual(Connection.prototype._rawSend,send);assert.strictEqual(Connection.prototype._onMessage,receive);
});

test('protocol observation is inactive outside the capture and distinguishes preparation/font/layout/capture/cleanup',()=>{
 let id=0;class Connection{_rawSend(){return++id;}_onMessage(value){return value;}}
 const observer=observeCaptureProtocol(Connection),connection=new Connection();connection._rawSend('','Page.captureScreenshot',{});observer.begin();
 for(const [method,params]of [['Runtime.callFunctionOn',{functionDeclaration:'inPagePrepareForScreenshots'}],['Runtime.callFunctionOn',{arguments:[{value:'document.fonts.ready'}]}],['Page.getLayoutMetrics',{}],['Page.captureScreenshot',{}],['Runtime.callFunctionOn',{functionDeclaration:'window.__pwCleanupScreenshot()'}]]){const n=connection._rawSend('',method,params);connection._onMessage({id:n,result:{}});}
 assert.deepEqual(observer.finish().calls.map(row=>row.phase),['prepare-screenshot','font-ready','Page.getLayoutMetrics','Page.captureScreenshot','restore-screenshot']);observer.dispose();
});

test('observer faults and bounded metadata never block the original transport',()=>{
 let id=0;class Connection{_rawSend(){return++id;}_onMessage(value){return value;}}
 const observer=observeCaptureProtocol(Connection,{limit:1}),connection=new Connection();observer.begin();const cyclic={};cyclic.arguments=[cyclic];assert.equal(connection._rawSend('','Runtime.callFunctionOn',cyclic),1);assert.equal(connection._rawSend('','Page.captureScreenshot',{}),2);assert.equal(connection._rawSend('','Page.getLayoutMetrics',{}),3);const report=observer.finish();assert.equal(report.observerErrors.length,1);assert.equal(report.calls.length,1);assert.equal(report.droppedCalls,1);observer.dispose();
});

test('native transport errors pass through unchanged and unsupported WebKit is explicit',()=>{
 const error=Error('native failure');class Connection{_rawSend(){throw error;}_onMessage(){throw error;}}
 const observer=observeCaptureProtocol(Connection);observer.begin();assert.throws(()=>new Connection()._rawSend('','Page.captureScreenshot',{}),value=>value===error);assert.throws(()=>new Connection()._onMessage({}),value=>value===error);observer.dispose();const webkit=observeCaptureProtocol(null);webkit.begin();assert.equal(webkit.finish().supported,false);webkit.dispose();
});

test('asynchronous protocol rejection and observer clock faults keep native promise identity',async()=>{
 const error=Error('native asynchronous error'),rejection=Promise.reject(error);let sends=0;
 class Connection{_rawSend(){return++sends;}_onMessage(){return rejection;}}
 const observer=observeCaptureProtocol(Connection,{now:()=>{throw Error('observer clock failed');}}),connection=new Connection();observer.begin();assert.equal(connection._rawSend('','Page.captureScreenshot',{}),1);const returned=connection._onMessage({id:1,result:{data:'private-image-payload'}});assert.strictEqual(returned,rejection);await assert.rejects(returned,value=>value===error);assert.equal(observer.finish().observerErrors.length,2);observer.dispose();
});
