/** CI partitions must cover every size and reject selections that would omit work. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {EventEmitter} from 'node:events';
import vm from 'node:vm';
import {observeReadiness,readReadinessState,retainReadinessFailure,safeReadinessText,safeReadinessURL} from './readiness-diagnostics.mjs';
import {acknowledgePrototypeNotice as guardedAcknowledgement} from '../assembly/build-prototype-session.mjs';
import {installRenderedReadiness} from './test-rendered-readiness.mjs';
import {installSetupProbe,setupDiagnosticScope} from '../diagnostic-probes.mjs';
import {SIZES,SCHEMES} from '../../../tools/site/site-empty-space.mjs';

const root=new URL('../../../',import.meta.url),harness=fileURLToPath(new URL('tests/site/layout/test-empty-space.mjs',root));
test('CI size partitions retain every page, both themes and every canonical size exactly once',()=>{
  assert.deepEqual(SIZES.map(size=>size.name),['phone-360','iphone-13','tablet-768','laptop-1024','desktop-1440']);
  assert.deepEqual(SCHEMES,['light','dark']);
  const workflow=readFileSync(new URL('.github/workflows/web-scene.yml',root),'utf8');
  const commands=workflow.split('\n').map(line=>line.trim()).filter(line=>line.startsWith('npm run test:empty-space'));
  assert.deepEqual(commands.sort(),SIZES.map(size=>`npm run test:empty-space -- --sizes=${size.name}`).sort());
  assert.match(workflow,/name: browser-validation \(layout\)[\s\S]*?needs: browser-validation/,'The retained check name must depend on the full partition result');
});

for(const [name,values]of [['sizes',['','unknown','phone-360,unknown','phone-360,phone-360']],['schemes',['','unknown','light,unknown','light,light']]]){
  test(`invalid ${name} selections fail before a browser or listener starts`,()=>{
    for(const value of values){
      const result=spawnSync(process.execPath,[harness,`--${name}=${value}`],{cwd:root,encoding:'utf8',timeout:5000,
        env:{...process.env,SITE_URL:'http://127.0.0.1:9',PLAYWRIGHT_BROWSERS_PATH:'/nonexistent-empty-space-negative-control'}});
      assert.equal(result.error,undefined);
      assert.notEqual(result.status,0);
      assert.match(result.stderr,new RegExp(`Invalid empty-space ${name} selection`));
      assert.doesNotMatch(result.stderr,/Executable doesn't exist|browserType\.launch|ECONNREFUSED/);
    }
  });
}

const readWorkflow=()=>readFileSync(new URL('.github/workflows/web-scene.yml',root),'utf8');
function commandsFor(workflow,suite){
  const marker='          - suite: '+suite+'\n            commands: |\n';
  const offset=workflow.indexOf(marker);assert.ok(offset>=0,'Missing '+suite+' commands');
  return workflow.slice(offset+marker.length).split(/\n {10}- suite:|\n {4}steps:/,1)[0].split('\n').map(line=>line.trim()).filter(Boolean);
}
test('presentation partitions retain the original command order and strict required aggregate',()=>{
  const workflow=readWorkflow();
  const expected=['notice','hero','viewers','file-viewer-theme','audio','voice','web','progress','landing-loop','status-board','timeline','doc-pages','walls','theme','highlights','highlight-integration','markdown','cache','diagrams','services','preview'].map(name=>'npm run test:'+name);
  assert.deepEqual([...commandsFor(workflow,'presentation-controls'),...commandsFor(workflow,'presentation-content')],expected);
  assert.match(workflow,/name: browser-validation \(presentation\)[\s\S]*?needs: browser-validation/);
});
test('the browser image is immutable and matches the locked Playwright release',()=>{
  const workflow=readWorkflow(),lock=JSON.parse(readFileSync(new URL('package-lock.json',root),'utf8'));
  const version=lock.packages['node_modules/@playwright/test'].version;
  const prefix='image: mcr.microsoft.com/playwright:v'+version+'-noble@sha256:';
  assert.ok(workflow.includes(prefix));assert.match(workflow.slice(workflow.indexOf(prefix)+prefix.length),/^[a-f0-9]{64}\n/);
  assert.doesNotMatch(workflow,/^\s+- run: npx playwright install/m);
});


test('timeout state serializes actual current design and partial scene without inventing readiness',()=>{
  const elements={'#app canvas':{width:360,height:780},'#sim-startup':{innerText:'Loading current robot'},'#design-select':{value:'v2'}};
  const fixture={
    location:{pathname:'/designer/sim.html'},performance:{timeOrigin:1000,getEntriesByType:()=>[{domContentLoadedEventEnd:12,responseEnd:5}]},getComputedStyle:()=>({opacity:'0'}),
    document:{readyState:'complete',visibilityState:'visible',hasFocus:()=>false,body:{dataset:{}},querySelector:selector=>elements[selector]??null,querySelectorAll:()=>[]},
    window:{__sim:{
      state:{modelKey:'v2',robot:{presentation:{mode:'current',robotId:'collection266'}},bench:false},
      stage:{renderer:{info:{render:{frame:7,triangles:100}},getContext:()=>({isContextLost:()=>false})}},
    }},
  };
  const read=()=>vm.runInNewContext('('+readReadinessState.toString()+')()',fixture);
  const value=read();assert.equal(value.bodyReady,null);assert.equal(value.selectedDesign,'v2');assert.equal(value.startupText,'Loading current robot');assert.equal(value.scene.frame,7);assert.equal(value.scene.presentation,'current');assert.equal(value.documentTimeOrigin,1000);assert.equal(value.navigationTiming.domContentLoadedEventEnd,12);assert.equal(value.visibility,'visible');assert.equal(value.focused,false);
  fixture.window.__sim=undefined;assert.equal(read().scene,null,'A startup failure can precede scene construction');
});

test('readiness observer retains relevant errors and pending/failed requests without headers, queries or private endpoints',()=>{
  const page=new EventEmitter();page.url=()=> 'https://site.fixture/designer/sim.html';
  const observer=observeReadiness(page,'https://site.fixture');observer.begin('/designer/sim.html');
  const request=url=>({url:()=>url,method:()=> 'GET',resourceType:()=> 'fetch',failure:()=>({errorText:'net::ERR_TIMED_OUT'})});
  const mesh=request('https://site.fixture/mesh.stl?token=secret');page.emit('request',mesh);
  const external=request('http://'+['10','4','5','6'].join('.')+'/health?token=secret');page.emit('request',external);page.emit('requestfailed',external);
  page.emit('response',{url:()=> 'https://site.fixture/manifest.json?secret=hidden',status:()=>503});
  page.emit('pageerror',Error('Failed '+external.url()));page.emit('console',{type:()=> 'error',text:()=> 'Failure '+mesh.url()});
  const value=observer.snapshot();assert.equal(value.pending[0].url,'/mesh.stl');assert.equal(value.failed[0].url,'<external-url>');assert.equal(value.responses[0].status,503);assert.equal(value.errors.length,1);assert.equal(value.consoleErrors.length,1);
  assert.doesNotMatch(JSON.stringify(value),/secret|hidden/);assert.ok(!JSON.stringify(value).includes(['10','4','5','6'].join('.')));
  const privatePath='/'+['home','private-user','file'].join('/');assert.equal(safeReadinessText(privatePath,'https://site.fixture'),'<private-path>');
  page.emit('requestfinished',mesh);assert.equal(observer.snapshot().pendingCount,0);
});

test('state read and write failures retain the original timeout evidence',async()=>{
  const error=Object.assign(Error('Original 30000ms timeout'),{name:'TimeoutError'});let saved,reads=0,writes=0;
  const report=await retainReadinessFailure({error,observer:{snapshot:()=>({route:'/designer/sim.html'})},readState:async()=>{reads++;throw Error('state failed');},write:async value=>{writes++;saved=structuredClone(value);throw Error('write failed');},ownedOrigin:'https://site.fixture'});
  assert.equal(report.error.name,'TimeoutError');assert.equal(report.error.message,error.message);assert.deepEqual(report.diagnosticErrors.map(row=>row.phase),['state','write']);assert.equal(saved.error.message,error.message);assert.equal(report.coreDeadline,30000);assert.equal(reads,1);assert.equal(writes,1);
});

test('a stalled diagnostic state read is bounded and does not replace the original failure',async()=>{
  let written;
  const report=await retainReadinessFailure({error:Error('original core failure'),observer:{snapshot:()=>({route:'/designer/sim.html'})},readState:()=>new Promise(()=>{}),write:async value=>{written=value;},ownedOrigin:'https://site.fixture',boundMs:1});
  assert.equal(report.error.message,'original core failure');assert.equal(report.diagnosticErrors[0].phase,'state');assert.match(report.diagnosticErrors[0].message,/exceeded/);assert.equal(written.error.message,report.error.message);
});


test('independent privacy reproductions redact temp paths, WebSockets and about queries',()=>{
  const origin='https://site.fixture';
  assert.equal(safeReadinessText('failed at /tmp/private-session/key.json',origin),'failed at <private-path>');
  assert.equal(safeReadinessText('ws://private-host:1234/stream?token=secret',origin),'<external-url>');
  assert.equal(safeReadinessURL('about:blank?token=secret',origin),'about:blank');
  assert.equal(safeReadinessURL('about:srcdoc#secret',origin),'about:srcdoc');
});

test('adjacent schemes and encoded or malformed endpoints do not survive text or URL serialization',()=>{
  const origin='https://site.fixture';
  const values=[
    'wss://private-host/stream?token=secret','WS://user:secret@private-host/stream#secret',
    'ftp://private-host/key.json?token=secret','file:///tmp/private-session/key.json','file:/tmp/private-session/key.json',
    'blob:https://private-host/private-session?token=secret','data:text/plain,secret','mailto:secret@private-host',
    'chrome-error://private-host/private-session?token=secret','//private-host/stream?token=secret',
    'ws://[malformed/stream?token=secret',encodeURIComponent('wss://private-host/stream?token=secret'),
    encodeURIComponent(encodeURIComponent('file:///tmp/private-session/key.json')),
    String.raw`wss:\/\/private-host/stream?token=secret`,
    String.raw`\u0077\u0073\u003a\u002f\u002fprivate-host/stream?token=secret`,
    '%77%73%3a%e0%a4private-host/stream?token=secret',
  ];
  for(const input of values){
    for(const output of [safeReadinessText('failed '+input,origin),safeReadinessURL(input,origin)])
      assert.doesNotMatch(output,/private-host|private-session|key\.json|secret|token=/,input);
  }
  assert.equal(safeReadinessURL('HTTPS://site.fixture/designer/sim.js?token=secret#secret',origin),'/designer/sim.js');
  assert.equal(safeReadinessText('Timeout 30000ms at HTTPS://site.fixture/designer/sim.js?token=secret; frame 7',origin),'Timeout 30000ms at /designer/sim.js frame 7');
});

test('filesystem error forms are redacted while ordinary public source paths stay useful',()=>{
  const origin='https://site.fixture';
  const paths=[
    '/tmp/private-session/key.json','/var/tmp/private-session/key.json','/private/var/private-session/key.json',
    '/custom-root/private-session/key.json',String.raw`C:\temp\private-session\key.json`,String.raw`\\private-host\share\key.json`,
    encodeURIComponent('/tmp/private-session/key.json'),encodeURIComponent(encodeURIComponent('/tmp/private-session/key.json')),
    String.raw`\u002ftmp\u002fprivate-session\u002fkey.json`,"'/tmp/private session/key.json'",'/tmp/private session/key.json',
    '/designer/../../tmp/private-session/key.json',
  ];
  for(const path of paths)assert.doesNotMatch(safeReadinessText('failed at '+path,origin),/private.session|key\.json|private-host/,path);
  assert.equal(safeReadinessText('failed at /designer/sim.js:80:5',origin),'failed at /designer/sim.js:80:5');
  assert.equal(safeReadinessText('model v2, frame 7, triangles 100',origin),'model v2, frame 7, triangles 100');
  assert.equal(safeReadinessText('replay v2/targets, exports/sim/v2/drive.json',origin),'replay v2/targets, exports/sim/v2/drive.json');
});

test('the full written timeout report sanitizes error, console and state strings without losing safe scene evidence',async()=>{
  const origin='https://site.fixture',page=new EventEmitter();page.url=()=> 'about:blank?token=secret';
  const observer=observeReadiness(page,origin);observer.begin('/designer/sim.html?token=secret');
  page.emit('pageerror',Object.assign(Error('failed at /tmp/private-session/key.json'),{name:'Error ws://private-host/stream?token=secret'}));
  page.emit('console',{type:()=> 'error',text:()=> 'failed file:///var/tmp/private-session/key.json'});
  const error=Object.assign(Error('Timeout 30000ms; wss://private-host/stream?token=secret'),{name:'TimeoutError'});let saved;
  await retainReadinessFailure({error,observer,ownedOrigin:origin,readState:async()=>({bodyReady:null,selectedDesign:'v2',startupText:'failed at /tmp/private-session/key.json',statusText:'about:blank?token=secret',scene:{frame:7,triangles:100,presentation:'current'},source:'https://site.fixture/designer/sim.js?token=secret'}),write:async report=>{saved=JSON.parse(JSON.stringify(report));}});
  assert.doesNotMatch(JSON.stringify(saved),/private-host|private-session|key\.json|secret|token=/);
  assert.equal(saved.error.name,'TimeoutError');assert.equal(saved.coreDeadline,30000);assert.equal(saved.state.selectedDesign,'v2');assert.equal(saved.state.scene.frame,7);assert.equal(saved.state.source,'/designer/sim.js');assert.equal(saved.observation.errors.length,1);assert.equal(saved.observation.consoleErrors.length,1);
});


test('the actual layout context calls the existing origin-guarded acknowledgement without hiding matching-origin failure',async()=>{
  const source=readFileSync(harness,'utf8');assert.ok(source.includes("from '../assembly/build-prototype-session.mjs'"));
  const actual=source.match(/^async function contextFor\(size\) \{[^]*?^}/m);assert.ok(actual);
  const scripts=[],context={addInitScript(fn,arg){scripts.push({fn,arg});},on(){},async route(){}};
  const make=new Function('browser','devices','acknowledgePrototypeNotice','installRenderedReadiness','observeReadiness','base','setupDiagnosticScope','installSetupProbe','sizes','process','return ('+actual[0]+');');
  const configure=make({async newContext(){return context;}},{},guardedAcknowledgement,installRenderedReadiness,observeReadiness,'https://site.fixture.test',setupDiagnosticScope,installSetupProbe,[{name:'phone-360'}],{env:{GITHUB_ACTIONS:'true'}});
  await configure({name:'phone-360',context:{viewport:{width:360,height:780}}});
  assert.ok(scripts.some(item=>item.fn===installSetupProbe&&item.arg===true),'Actual CI caller installs the exact scoped setup probe');
  const script=scripts.find(item=>item.arg==='https://site.fixture.test');assert.ok(script,'Actual caller supplies its explicit owned origin');
  const run=state=>{const scope={expected:script.arg};Object.defineProperties(scope,Object.getOwnPropertyDescriptors(state));return vm.runInNewContext('('+script.fn.toString()+')(expected)',scope);};
  for(const state of [{location:{protocol:'about:'},origin:'null'},{location:{protocol:'https:'},origin:'https://wrong.fixture.test'}]){
    let read=false;Object.defineProperty(state,'sessionStorage',{enumerable:true,get(){read=true;throw Error('not readable');}});assert.doesNotThrow(()=>run(state));assert.equal(read,false);
  }
  const writes=[];run({location:{protocol:'https:'},origin:'https://site.fixture.test',sessionStorage:{setItem(...args){writes.push(args);}}});assert.deepEqual(writes,[['gyropup.prototype-notice','2026-10-29-v1']]);
  assert.throws(()=>run({location:{protocol:'https:'},origin:'https://site.fixture.test',sessionStorage:{setItem(){throw Error('denied matching origin');}}}),/denied matching origin/);
  context.addInitScript=(fn,arg)=>{if(fn===installSetupProbe)throw Error('synthetic probe registration failure');scripts.push({fn,arg});};
  await assert.doesNotReject(configure({name:'phone-360',context:{viewport:{width:360,height:780}}}),'Optional diagnostic registration cannot replace the actual test');
});

test('navigation and resource clocks retain successful and pending timing without relabeling Node event receipt as network start',()=>{
  const context={},page=new EventEmitter();let url='https://site.fixture/site/previous.html';page.url=()=>url;page.context=()=>context;page.viewportSize=()=>({width:360,height:780});
  const observer=observeReadiness(page,'https://site.fixture');observer.begin('/site/previous.html?token=secret');observer.mark('core-wait-accepted');
  url='https://site.fixture/designer/sim.html';observer.begin('/designer/sim.html');page.emit('domcontentloaded');observer.mark('domcontentloaded-return');observer.mark('core-wait-start');
  const request={url:()=> 'https://site.fixture/designer/sim.js?token=secret',method:()=> 'GET',resourceType:()=> 'script',timing:()=>({startTime:1000,requestStart:2,responseStart:10,responseEnd:20,privateEndpoint:'ws://private-host/?token=secret'})};
  page.emit('request',request);page.emit('response',{url:request.url,status:()=>200,request:()=>request});page.emit('requestfinished',request);
  const pending={url:()=> 'https://site.fixture/web/robot-current/manifest.json',method:()=> 'GET',resourceType:()=> 'fetch',timing:()=>({startTime:2000,responseEnd:-1})};page.emit('request',pending);observer.mark('core-wait-rejected');
  const value=observer.snapshot();assert.equal(value.previousRoute,'/site/previous.html');assert.equal(value.history.length,2);assert.equal(value.history[1].route,'/designer/sim.html');assert.ok(Number.isInteger(value.contextId));assert.ok(Number.isInteger(value.pageId));
  assert.deepEqual(value.events.map(row=>row.event),['navigation-start','domcontentloaded-event','domcontentloaded-return','core-wait-start','core-wait-rejected']);
  assert.equal(value.completed[0].status,200);assert.equal(value.completed[0].browserTiming.startTime,1000);assert.equal(value.completed[0].browserTiming.responseEnd,20);assert.notEqual(value.completed[0].nodeRequestObservedAt,1000);assert.equal(value.pending[0].browserTiming.startTime,2000);assert.equal(value.pending[0].browserTiming.responseEnd,-1);assert.match(value.timingClocks.node,/not network start/);
  assert.doesNotMatch(JSON.stringify(value),/private-host|secret|token=/);pending.timing=()=>{throw Error('timing unavailable');};assert.equal(observer.snapshot().pending[0].browserTiming,null);
});
