import test from 'node:test';import assert from 'node:assert/strict';import {readFile} from 'node:fs/promises';import {createHash} from 'node:crypto';
import {validatePrintMapping,verifyPrintOriginals} from '../../../software/site/designer/assembly/print-selection.js';
const bytes=await readFile(new URL('../../../hardware/exports/body/post.stl',import.meta.url)),sha256=createHash('sha256').update(bytes).digest('hex');
const mapping={kind:'print',geometry_match:{status:'matched',basis:'Identical source STL bytes in this test fixture'},originals:[{source_file:'hardware/exports/body/post.stl',public_file:'/exports/body/post.stl',sha256}]};
test('print handoff verifies exact manufacturing bytes and preserves original identity',async()=>{const records=await verifyPrintOriginals(mapping,{origin:'https://fixture.invalid',fetcher:async url=>{assert.equal(url.pathname,'/exports/body/post.stl');return new Response(bytes);}});assert.equal(records.length,1);assert.equal(records[0].source_file,mapping.originals[0].source_file);assert.deepEqual(new Uint8Array(records[0].bytes),new Uint8Array(bytes));});
test('moving latest original cannot masquerade as a bound historical file',async()=>{await assert.rejects(verifyPrintOriginals(mapping,{origin:'https://fixture.invalid',fetcher:async()=>new Response(new Uint8Array([1,2,3]))}),/SHA-256 mismatch/);});
test('neutral posed scenes and bought or fabricated parts cannot enter the Print action',()=>{for(const kind of ['bought','machine','sheet','unresolved'])assert.throws(()=>validatePrintMapping({...mapping,kind}));for(const public_file of ['/web/build-guides/example/meshes/post.stl','/exports/sim/v2/rig/post.stl','/exports/body/../sim/post.stl','https://fixture.invalid/post.stl']){const bad=structuredClone(mapping);bad.originals[0].public_file=public_file;assert.throws(()=>validatePrintMapping(bad));}});

test('file category and identity cannot substitute for a geometry match',()=>{const unproved=structuredClone(mapping);delete unproved.geometry_match;assert.throws(()=>validatePrintMapping(unproved),/geometry match/);unproved.geometry_match={status:'pending'};assert.throws(()=>validatePrintMapping(unproved),/geometry match/);});

const {validatePreparedProject,verifyPreparedProject,studioURL}=await import('../../../software/site/designer/assembly/print-selection.js');
const robot=JSON.parse(await readFile(new URL('../../../software/site/assets/build-guides/robot-wip-540056ba4e59/guide.json',import.meta.url))),hip=robot.source.manufacturing_by_part['L.hip_frame'],project=hip.prepared_projects[0],projectBytes=await readFile(new URL('../../../'+project.source_file,import.meta.url));
test('actual reviewed hip project verifies independently from the original',async()=>{assert.equal(validatePreparedProject(hip,project),project);const record=await verifyPreparedProject(hip,project,{origin:'https://fixture.invalid',fetcher:async url=>{assert.equal(url.pathname,project.public_file);return new Response(projectBytes);}});assert.equal(record.bytes.byteLength,326658);await assert.rejects(verifyPreparedProject(hip,project,{fetcher:async()=>new Response(new Uint8Array([1,2,3]))}),/SHA-256 mismatch/);});
test('project identity cannot turn a scene mesh or unrelated original into print preparation',()=>{for(const patch of [{kind:'original'},{immutable:false},{source_original_sha256:'0'.repeat(64)},{public_file:'/exports/leg/hip_frame.stl'},{source_file:'hardware/exports/leg/hip_frame.stl'},{public_file:project.public_file.replace(project.sha256,'0'.repeat(64))},{limitations:[]}])assert.throws(()=>validatePreparedProject(hip,{...project,...patch}));assert.throws(()=>validatePreparedProject({...hip,geometry_match:{status:'pending'}},project));});
test('desktop links follow distinct official Studio handlers without opening an application',()=>{const url='https://fixture.invalid'+project.public_file;assert.equal(studioURL(url,'mac'),'bambustudioopen://'+encodeURIComponent(url));assert.equal(studioURL(url,'windows-linux'),'bambustudio://open?file='+encodeURIComponent(url));for(const bad of ['file:///tmp/project.3mf','https://fixture.invalid/mesh.stl'])assert.throws(()=>studioURL(bad,'mac'));assert.throws(()=>studioURL(url,'unknown'));});

// Exercise the actual browser-harness activation functions without launching a browser.
const workspaceSource=await readFile(new URL('./test-build-workspace.mjs',import.meta.url),'utf8');
const extractFunction=pattern=>{const match=workspaceSource.match(pattern);assert.ok(match);return match[0];};
const openKeyboard=new Function('assert','return ('+extractFunction(/^async function openSummaryWithKeyboard\(p,summary\) \{[^]*?^}/m)+');')(assert);
const {default:vm}=await import('node:vm');
function keyboardDisclosureFixture(mode='normal'){
 const details={tagName:'DETAILS',open:false,isConnected:true},element={tagName:'SUMMARY',isConnected:mode!=='disconnected',parentElement:details};
 const document={activeElement:null,hasFocus:()=>mode!=='document-unfocused'},calls={focus:0,keys:[],disposed:0},activationError=Error('native Enter failed');
 const parent={node:details,dispose:async()=>{calls.disposed++;}};
 const target={
  evaluateHandle:async fn=>{assert.equal(fn(element),details);return parent;},
  evaluate:async(fn,arg)=>vm.runInNewContext('('+fn.toString()+')(element,details)',{element,details:arg.node,document}),
  isVisible:async()=>mode!=='invisible',isEnabled:async()=>mode!=='disabled',
  focus:async()=>{calls.focus++;document.activeElement=mode==='wrong-focus'?{}:element;},
  dispose:async()=>{calls.disposed++;},
 };
 const summary={elementHandle:async()=>target,click:async()=>{throw Error('Keyboard mode must not click');}};
 const page={keyboard:{press:async key=>{
  calls.keys.push(key);assert.equal(key,'Enter');
  if(mode==='activation-error')throw activationError;
  if(mode==='wrong-parent'){details.open=true;element.parentElement={...details};}
  else if(mode!=='no-open')details.open=true;
 }}};
 return {page,summary,calls,activationError,details};
}
test('keyboard disclosure opens the same captured parent through focused native Enter',async()=>{
 const fixture=keyboardDisclosureFixture();await openKeyboard(fixture.page,fixture.summary);
 assert.deepEqual(fixture.calls,{focus:1,keys:['Enter'],disposed:2});assert.equal(fixture.details.open,true);
});
test('keyboard disclosure rejects wrong focus, no toggle, wrong parent and native activation errors',async()=>{
 for(const mode of ['invisible','disabled','disconnected','wrong-focus','document-unfocused','no-open','wrong-parent','activation-error']){
  const fixture=keyboardDisclosureFixture(mode);
  await assert.rejects(()=>openKeyboard(fixture.page,fixture.summary),mode==='activation-error'?error=>error===fixture.activationError:undefined,mode);
  assert.equal(fixture.calls.disposed,2,mode);
  if(['invisible','disabled','disconnected','wrong-focus','document-unfocused'].includes(mode))assert.equal(fixture.calls.keys.length,0,mode);
 }
});
test('pointer disclosure retains the actual native click and never falls back after its error',async()=>{
 const definition=extractFunction(/^async function pickList\(p,name,input='pointer'\)\{[^]*?(?=^async function surface)/m);
 for(const fail of [false,true]){
  let opened=false,clicks=0,keys=0;const original=Error('original30s pointer failure');
  const summary={click:async()=>{clicks++;if(fail)throw original;opened=true;},elementHandle:()=>{throw Error('Pointer mode must not enter keyboard activation');}};
  const outer={count:async()=>opened?0:1,locator:()=>summary};
  const button={locator:selector=>selector.includes('not(@open)')?outer:{count:async()=>1},focus:async()=>{assert.equal(opened,true);}};
  const page={locator:()=>button,keyboard:{press:async key=>{keys++;assert.equal(key,'Enter');}},waitForFunction:async(_,name)=>assert.equal(name,'L.upper_link_front')};
  const pick=new Function('assert','openTree','scope','process','observedSummaryClick','openSummaryWithKeyboard','observations','return ('+definition+');')(
   assert,async()=>{},'print',{env:{PRINT_CASE:'current'}},async(_p,_s,action)=>action(),()=>{throw Error('No keyboard fallback');},[]);
  if(fail)await assert.rejects(()=>pick(page,'L.upper_link_front'),error=>error===original);
  else await pick(page,'L.upper_link_front');
  assert.equal(clicks,1);assert.equal(keys,fail?0:1);
 }
});
test('current Print caller preselects keyboard only for the R-hip pending selection and preserves campaign coverage',async()=>{
 const declaration=workspaceSource.match(/const pendingInput=([^;]+);/);assert.ok(declaration);
 const select=new Function('name','return '+declaration[1]);assert.equal(select('L.hip_frame'),'pointer');assert.equal(select('R.hip_frame'),'keyboard');
 assert.match(workspaceSource,/await pickList\(p,'L\.upper_link_front',pendingInput\)/);
 assert.match(workspaceSource,/for\(const name of \['L\.hip_frame','R\.hip_frame'\]\)/);
 assert.match(workspaceSource,/assert\.equal\(await p\.locator\('\[data-part-print\]'\)\.isHidden\(\),true\)/);
 const workflow=await readFile(new URL('../../../.github/workflows/web-scene.yml',import.meta.url),'utf8');
 assert.match(workflow,/WORKSPACE_CASE=print npm run test:build-workspace\n\s+TEST_OUTPUT=.*PRINT_CASE=current npm run test:build-workspace\n\s+PLAYWRIGHT_BROWSER=webkit WORKSPACE_CASE=print npm run test:build-workspace\n\s+TEST_OUTPUT=.*PLAYWRIGHT_BROWSER=webkit WORKSPACE_CASE=print PRINT_CASE=current npm run test:build-workspace/);
});

test('actual pending-part selection exercises keyboard disclosure before native part Enter',async()=>{
 const definition=extractFunction(/^async function pickList\(p,name,input='pointer'\)\{[^]*?(?=^async function surface)/m),fixture=keyboardDisclosureFixture();let partFocus=0;
 const outer={count:async()=>fixture.details.open?0:1,locator:()=>fixture.summary};
 const button={locator:selector=>selector.includes('not(@open)')?outer:{count:async()=>1},focus:async()=>{partFocus++;}};
 fixture.page.locator=()=>button;fixture.page.waitForFunction=async(_,name)=>assert.equal(name,'L.upper_link_front');
 const pick=new Function('assert','openTree','scope','process','observedSummaryClick','openSummaryWithKeyboard','observations','return ('+definition+');')(
  assert,async()=>{},'print',{env:{PRINT_CASE:'current'}},async(_p,_s,action)=>action(),openKeyboard,[]);
 await pick(fixture.page,'L.upper_link_front','keyboard');
 assert.deepEqual(fixture.calls.keys,['Enter','Enter']);assert.equal(fixture.calls.focus,1);assert.equal(partFocus,1);assert.equal(fixture.calls.disposed,2);
});
