import assert from 'node:assert/strict';
import {test} from 'node:test';
import {EventEmitter} from 'node:events';
import {isDocumentReturn,classifyCancellation,trackNavigationRequests} from './hosted-navigation.mjs';
const base='https://gyropup.com',docPath='/site/pages/docs-carrier-service-connectors-md.html';
test('static and enhanced returns accept only the exact document and known query',()=>{
  for(const path of [docPath,docPath.slice(0,-5)])for(const search of ['','?live=0'])
    assert.ok(isDocumentReturn(base+path+search,{base,docPath}));
  for(const url of ['https://elsewhere.test'+docPath,'https://user@gyropup.com'+docPath,
    base+'/designer/build',base+docPath+'-wrong',base+docPath+'?live=1',base+docPath+'?live=0&other=1',base+docPath+'#other'])
    assert.equal(isDocumentReturn(url,{base,docPath}),false,url);
  assert.equal(isDocumentReturn(base+docPath,{base,docPath,search:'?live=0'}),false,'Enhanced query must survive Back');
  assert.equal(isDocumentReturn(base+docPath+'?live=0',{base,docPath,search:''}),false,'Static href is not rewritten by the harness');
});
test('known hosting cancellation never masks failed assets, HTTP failures or unrelated hosts',()=>{
  const rum={url:base+'/cdn-cgi/rum?',method:'POST',type:'ping',error:'net::ERR_ABORTED'};
  assert.equal(classifyCancellation(rum,{base}),'hostingTelemetry');
  for(const type of ['beacon','xhr'])assert.equal(classifyCancellation({...rum,type,error:'Load request cancelled'},{base}),'hostingTelemetry');
  for(const change of [{url:base+'/cdn-cgi/rum?extra=1'},{method:'GET'},{type:'script'},
    {error:'net::ERR_CONNECTION_RESET'},{url:'https://elsewhere.test/cdn-cgi/rum'},
    {url:base+'/designer/kit/file-geometry.js'}])assert.equal(classifyCancellation({...rum,...change},{base}),null);
  const local='http://127.0.0.1:8879';
  assert.equal(classifyCancellation({...rum,url:local+'/cdn-cgi/rum'},{base:local}),null);
});
test('only already pending metadata may be cancelled by the explicit outgoing navigation',async()=>{
  const page=new EventEmitter();page.url=()=>base+docPath;
  const report={requestFailures:[]},navigate=trackNavigationRequests(page,base,report);
  const request=(path,error='net::ERR_ABORTED',type='fetch')=>({url:()=>base+path,method:()=>'GET',resourceType:()=>type,failure:()=>({errorText:error})});
  const old=request('/site/models.json'),current=request('/site/models.json'),asset=request('/exports/part.step'),broken=request('/site/nav.json','net::ERR_FAILED');
  for(const r of [old,asset,broken])page.emit('request',r);
  await navigate(async()=>{
    page.emit('request',current);
    for(const r of [old,current,asset,broken])page.emit('requestfailed',r);
  });
  assert.equal(report.cancelledOnNavigation.length,1);
  assert.equal(report.cancelledOnNavigation[0].navigationFrom,base+docPath);
  assert.equal(report.requestFailures.length,3);
});
