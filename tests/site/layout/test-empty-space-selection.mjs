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


test('each full single-size CI partition defaults to one worker and Home-to-Sim without changing explicit modes',()=>{
  const source=readFileSync(harness,'utf8');
  const declarations=source.match(/^const singleSizeCIDefault =[^]*?^const workers =[^]*?;/m);assert.ok(declarations);
  const evaluate=new Function('arg','process','sizes','report',declarations[0]+';return {singleSizeCIDefault,workers};');
  const run=({ci='true',selected=['phone-360'],args={},env={},report=false,argv=[]}={})=>evaluate(name=>args[name],{env:{GITHUB_ACTIONS:ci,...env},argv},selected.map(name=>({name})),report);
  for(const size of SIZES)assert.deepEqual(run({selected:[size.name]}),{singleSizeCIDefault:true,workers:1},size.name);
  for(const options of [{ci:'false'},{selected:['phone-360','tablet-768']},{args:{pages:'/'}},{args:{schemes:'light,dark'}},{report:true},{argv:['--controls']},{env:{EMPTY_SPACE_WORKERS:''}}])
    assert.deepEqual(run(options),{singleSizeCIDefault:false,workers:3},JSON.stringify(options));
  assert.deepEqual(run({args:{workers:'2'}}),{singleSizeCIDefault:false,workers:2});
  assert.deepEqual(run({env:{EMPTY_SPACE_WORKERS:'4'}}),{singleSizeCIDefault:false,workers:4});
  const selection=source.match(/^  const pages = [^]*?;/m);assert.ok(selection);
  const pageSelect=new Function('arg','process','singleSizeCIDefault','fullCIPageOrder','all',selection[0]+';return pages;');
  const all=['/','/designer/progress.html','/designer/build.html','/designer/sim.html','/site/'];
  assert.deepEqual(pageSelect(name=>name==='pages'?'/site/,/':undefined,{argv:[]},false,()=>{throw Error('Explicit order must be untouched');},all),['/site/','/']);
  assert.deepEqual(pageSelect(()=>undefined,{argv:['--controls']},false,()=>{throw Error('Control-only mode must be untouched');},all),[]);
});

test('actual CI permutation retains every dynamic route/theme tuple once and rejects malformed source closure',()=>{
  const source=readFileSync(harness,'utf8'),definition=source.match(/^function fullCIPageOrder\(all\) \{[^]*?^}/m);assert.ok(definition);
  const order=new Function('return ('+definition[0]+');')();
  for(const added of [0,1,7,152,203]){
    const all=['/','/designer/progress.html','/designer/build.html','/designer/sim.html','/site/',...Array.from({length:added},(_,i)=>'/site/pages/dynamic-'+i+'.html')];
    const original=[...all],ordered=order(all);assert.deepEqual(all,original,'Input closure is not mutated');
    assert.deepEqual(ordered.slice(0,2),['/','/designer/sim.html']);assert.equal(ordered.length,all.length);assert.equal(new Set(ordered).size,all.length);assert.deepEqual([...ordered].sort(),[...all].sort());
    assert.deepEqual(ordered.slice(2),all.filter(route=>route!=='/'&&route!=='/designer/sim.html'));
    for(const size of SIZES){
      const tuples=ordered.flatMap(route=>SCHEMES.map(scheme=>({route,size:size.name,scheme})));
      assert.equal(tuples.length,SCHEMES.length*all.length);assert.equal(new Set(tuples.map(row=>JSON.stringify(row))).size,tuples.length);
      assert.deepEqual(tuples.filter(row=>row.scheme==='light').slice(0,2).map(row=>row.route),['/','/designer/sim.html']);
      if(added===152)assert.equal(tuples.length,314);
    }
  }
  for(const bad of [['/','/'],['/','/site/'],['/designer/sim.html','/site/']])assert.throws(()=>order(bad),/Invalid full CI page closure/);
  assert.match(source,/if \(!report && !arg\('pages'\) \|\| process\.argv\.includes\('--controls'\)\)/,'Default CI still executes the existing planted controls');
});


test('owned talk CSS serializer retains identities, caps and sanitized event fields',()=>{
  const source=readFileSync(new URL('../controls/test-robot-controls.mjs',import.meta.url),'utf8');
  const definition=source.match(/^function observeTalkCss\(page,origin\) \{[^]*?^}/m);assert.ok(definition);
  const observe=new Function('safeReadinessURL','safeReadinessText','return ('+definition[0]+');')(safeReadinessURL,safeReadinessText);
  const page=new EventEmitter(),origin='https://site.fixture';page.url=()=>origin+'/designer/sim.html?token=secret';
  const frame={url:page.url};page.mainFrame=()=>frame;
  const observation=observe(page,origin);
  const request=token=>({url:()=>origin+'/designer/character/talk.css?v='+token,timing:()=>({startTime:100,requestStart:2,responseStart:4,responseEnd:5,headers:'secret'}),failure:()=>({errorText:'failed at /tmp/private-session/key.json'})});
  const first=request('secret'),second=request('hidden');
  for(const req of [first,second]){page.emit('request',req);observation.record('route-enter',{request:req});}
  observation.record('held-resolver-replaced',{request:first});observation.record('continue-failed',{request:second,error:Error('ws://private-host/stream?token=secret')});

  page.emit('response',{request:()=>second,status:()=>200});page.emit('requestfailed',first);
  const navigation={url:page.url,isNavigationRequest:()=>true,frame:()=>frame,timing:()=>({startTime:90,requestStart:1,responseStart:3,responseEnd:4})};
  page.emit('request',navigation);page.emit('response',{request:()=>navigation,url:page.url,status:()=>200});
  page.emit('framenavigated',frame);page.emit('domcontentloaded');page.emit('pageerror',Error('file:///tmp/private-session/key.json'));
  page.emit('request',{url:()=> 'https://outside.fixture/designer/character/talk.css?token=secret'});
  let value=observation.snapshot(Object.assign(Error('Original30s TimeoutError'),{name:'TimeoutError'}));
  assert.equal(value.matchingRequests,2);assert.equal(value.counts.request,2);assert.equal(value.events.find(row=>row.event==='held-resolver-replaced').requestId,1);assert.equal(value.events.find(row=>row.event==='continue-failed').requestId,2);
  assert.equal(value.error.name,'TimeoutError');assert.ok(value.events.some(row=>row.event==='navigation'));assert.equal(value.events.find(row=>row.event==='navigation-response').browserTiming.startTime,90);assert.ok(value.events.some(row=>row.event==='requestfailed'));assert.deepEqual(value.events.find(row=>row.event==='response').browserTiming,{startTime:100,requestStart:2,responseStart:4,responseEnd:5});
  assert.doesNotMatch(JSON.stringify(value),/secret|hidden|private-session|private-host|outside\.fixture|headers/);
  for(let i=0;i<100;i++)page.emit('request',request(String(i)));
  value=observation.snapshot();assert.equal(value.events.length,64);assert.ok(value.dropped>0);assert.equal(value.matchingRequests,102);assert.equal(value.counts.request,102);
  const clear=source.indexOf("localStorage.removeItem('gyropup-sfx')"),blank=source.indexOf("await page.goto('about:blank')"),fresh=source.indexOf('await checkFreshLayout();');assert.ok(clear<blank&&blank<fresh,'Saved state clears precede retiring the completed availability page');
});

test('talk CSS evidence writes retain original failures and have one finite write bound',async()=>{
  const source=readFileSync(new URL('../controls/test-robot-controls.mjs',import.meta.url),'utf8');
  const definition=source.match(/^async function retainTalkCssReport\(observation,error,write\) \{[^]*?^}/m);assert.ok(definition);
  const retain=new Function('return ('+definition[0]+');')(),original=Error('Original30s timeout'),secondary=Error('write failed');
  const observation={snapshot:error=>({error:error?.message??null})};let saved;
  assert.equal(await retain(observation,null,async value=>{saved=value;}),null);assert.equal(saved.error,null);
  await assert.rejects(async()=>{try{throw original;}finally{assert.equal(await retain(observation,original,async value=>{saved=value;throw secondary;}),secondary);}},error=>error===original);
  assert.equal(saved.error,original.message);
  assert.equal(await retain({snapshot:()=>{throw secondary;}},original,()=>{throw Error('must not write');}),secondary);
  const bound=await retain(observation,original,()=>new Promise(()=>{}));assert.match(bound.message,/exceeded 2000 ms/);
});


test('actual robot fixture callbacks avoid opaque/foreign storage and retain intended-origin failures',()=>{
  const source=readFileSync(new URL('../controls/test-robot-controls.mjs',import.meta.url),'utf8');
  assert.match(source,/from '\.\.\/assembly\/build-prototype-session\.mjs'/);
  for(const context of ['context','fresh']){
    assert.ok(source.includes(`acknowledgePrototypeNotice(${context},base)`));
    assert.ok(source.includes(`${context}.addInitScript(disableAutomaticProbe,new URL(base).origin)`));
  }
  const definition=source.match(/^function disableAutomaticProbe\(expectedOrigin\) \{[^]*?^}/m);assert.ok(definition);
  const origin='https://site.fixture';let writes=0;
  const run=(protocol,actual,denied=false)=>vm.runInNewContext('('+definition[0]+')(expectedOrigin)',{location:{protocol},origin:actual,expectedOrigin:origin,localStorage:{setItem(key,value){writes++;if(denied)throw Error('intended storage denied');assert.equal(key,'gyropup.probe');assert.equal(value,'off');}}});
  run('about:','null',true);run('https:','https://other.fixture',true);assert.equal(writes,0);
  run('https:',origin);assert.equal(writes,1);
  assert.throws(()=>run('https:',origin,true),/intended storage denied/);assert.equal(writes,2);
});


test('actual fresh CSS caller drains every owned route under success, failure and bounded cleanup', {timeout:15000},async()=>{
  const source=readFileSync(new URL('../controls/test-robot-controls.mjs',import.meta.url),'utf8');
  const extract=pattern=>{const match=source.match(pattern);assert.ok(match);return match[0];};
  const observe=new Function('safeReadinessURL','safeReadinessText','return ('+extract(/^function observeTalkCss\(page,origin\) \{[^]*?^}/m)+');')(safeReadinessURL,safeReadinessText);
  const retain=new Function('return ('+extract(/^async function retainTalkCssReport\(observation,error,write\) \{[^]*?^}/m)+');')();
  const caller=extract(/^async function checkFreshLayout\(\) \{[^]*?^}/m);
  for(const mode of ['success','primary-failure','continue-failure','primary-continue-failure','close-failure','primary-close-failure','close-stall','continue-stall','late-route','write-failure']){
    const original=Error('original30s timeout'),secondary=Error(mode),page=new EventEmitter(),origin='https://site.fixture';
    const primary=['primary-failure','primary-continue-failure','primary-close-failure','close-stall','continue-stall','write-failure'].includes(mode);
    let handler,closeCalls=0,settled=0,saved,registered=false;
    const callbacks=[],continued=[],actions=[];
    page.url=()=>origin+'/designer/sim.html';const frame={url:page.url};page.mainFrame=()=>frame;
    const startRoute=id=>{
      const request={url:()=>origin+'/designer/character/talk.css?v='+id,timing:()=>({startTime:id})};page.emit('request',request);
      const callback=handler({request:()=>request,continue:()=>{
        continued.push(id);actions.push('continue'+id);
        if(id===1&&['continue-failure','primary-continue-failure'].includes(mode))return Promise.reject(secondary);
        if(id===1&&mode==='continue-stall')return new Promise(()=>{});
        return Promise.resolve();
      }});callbacks.push(callback);callback.then(()=>settled++,()=>settled++);
    };
    Object.assign(page,{
      route:async(_,callback)=>{handler=callback;},goto:async()=>{startRoute(1);startRoute(2);},
      waitForFunction:async()=>{if(primary)throw original;},
      waitForResponse:()=>{registered=true;actions.push('response-listener');return Promise.resolve({finished:async()=>{}});},
      evaluate:async fn=>fn.toString().includes('const THREE')?{top:0,bottom:1,left:0,right:1,freeTop:0,freeBottom:2,freeRight:2}:fn.toString().includes('projectionMatrix')?[1]:undefined,
      locator:()=>({click:async()=>{}}),screenshot:async()=>{},
    });
    const fresh={addInitScript:async()=>{},newPage:async()=>page,close:async()=>{
      closeCalls++;if(mode==='late-route')startRoute(3);
      if(['close-failure','primary-close-failure'].includes(mode))throw secondary;if(mode==='close-stall')await new Promise(()=>{});
    }};
    const run=new Function('browser','acknowledgePrototypeNotice','disableAutomaticProbe','base','errors','out','engine','observeTalkCss','retainTalkCssReport','writeFile','assert','safeReadinessText','return ('+caller+');')(
      {newContext:async()=>fresh},async()=>{},()=>{},origin,[],'.',{name:()=> 'fixture'},observe,retain,async(_,data)=>{if(mode==='write-failure')throw secondary;saved=JSON.parse(data);},assert,safeReadinessText);
    let actual;try{await run();}catch(error){actual=error;}
    await Promise.allSettled(callbacks);
    const count=mode==='late-route'?3:2;
    assert.equal(closeCalls,1,mode);assert.equal(settled,count,mode);assert.equal(continued.length,count,mode);assert.equal(new Set(continued).size,count,mode);
    if(primary)assert.equal(actual,original,mode);
    else if(['continue-failure','close-failure'].includes(mode))assert.equal(actual,secondary,mode);
    else assert.equal(actual,undefined,mode);
    if(!primary){assert.equal(registered,true,mode);assert.ok(actions.indexOf('response-listener')<actions.indexOf('continue2'),mode);}
    if(mode!=='write-failure'){
      assert.equal(saved.cleanup.pendingRoutes,0,mode);assert.equal(saved.cleanup.heldReleasers,0,mode);
      assert.equal(saved.error?.message??null,primary?original.message:null,mode);
      assert.equal(saved.cleanup.context,mode==='close-stall'?'pending':['close-failure','primary-close-failure'].includes(mode)?'failed':'closed',mode);
      assert.equal(saved.cleanup.timedOut,['close-stall','continue-stall'].includes(mode),mode);
      assert.equal(saved.cleanup.pendingNativeContinues,mode==='continue-stall'?1:0,mode);
      assert.equal(saved.cleanup.routeErrors,['continue-failure','primary-continue-failure','continue-stall'].includes(mode)?1:0,mode);
    }
  }
});
