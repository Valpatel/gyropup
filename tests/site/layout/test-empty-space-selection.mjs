/** CI partitions must cover every size and reject selections that would omit work. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {EventEmitter} from 'node:events';
import vm from 'node:vm';
import {observeReadiness,readReadinessState,retainReadinessFailure,safeReadinessText} from './readiness-diagnostics.mjs';
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
    location:{pathname:'/designer/sim.html'},getComputedStyle:()=>({opacity:'0'}),
    document:{readyState:'complete',body:{dataset:{}},querySelector:selector=>elements[selector]??null,querySelectorAll:()=>[]},
    window:{__sim:{
      state:{modelKey:'v2',robot:{presentation:{mode:'current',robotId:'collection266'}},bench:false},
      stage:{renderer:{info:{render:{frame:7,triangles:100}},getContext:()=>({isContextLost:()=>false})}},
    }},
  };
  const read=()=>vm.runInNewContext('('+readReadinessState.toString()+')()',fixture);
  const value=read();assert.equal(value.bodyReady,null);assert.equal(value.selectedDesign,'v2');assert.equal(value.startupText,'Loading current robot');assert.equal(value.scene.frame,7);assert.equal(value.scene.presentation,'current');
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
