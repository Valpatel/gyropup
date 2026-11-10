import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import {acknowledgePrototypeNotice} from './test-prototype-session.mjs';

async function fixture(omitURL=false){
 let script,arg;
 const context={addInitScript(fn,value){script=fn;arg=value;}};
 if(omitURL)await acknowledgePrototypeNotice(context);
 else await acknowledgePrototypeNotice(context,'https://site.fixture.test/path');
 return state=>{
  const scope={expected:arg};
  Object.defineProperties(scope,Object.getOwnPropertyDescriptors(state));
  return vm.runInNewContext('('+script.toString()+')(expected)',scope);
 };
}
test('actual init fixture never reads opaque or wrong-origin storage',async()=>{
 const run=await fixture();
 for(const state of [{location:{protocol:'about:'},origin:'null'},{location:{protocol:'https:'},origin:'null'},{location:{protocol:'https:'},origin:'https://other.fixture.test'}]){
  let read=false;
  Object.defineProperty(state,'sessionStorage',{enumerable:true,get(){read=true;throw Error('must not read');}});
  assert.doesNotThrow(()=>run(state));assert.equal(read,false);
 }
});
test('actual matching-origin write has the exact notice key/version',async()=>{
 const run=await fixture(),writes=[];
 run({location:{protocol:'https:'},origin:'https://site.fixture.test',sessionStorage:{setItem(...args){writes.push(args);}}});
 assert.deepEqual(writes,[['gyropup.prototype-notice','2026-10-29-v1']]);
});
test('matching HTTP storage failure is not swallowed',async()=>{
 const run=await fixture();
 assert.throws(()=>run({location:{protocol:'https:'},origin:'https://site.fixture.test',sessionStorage:{setItem(){throw Error('denied fixture');}}}),/denied fixture/);
});
test('existing callers default to SITE_URL and keep standalone HTTP compatibility',async()=>{
 const previous=process.env.SITE_URL;
 try{
  process.env.SITE_URL='https://site.fixture.test/';const bound=await fixture(true);let writes=0;
  bound({location:{protocol:'https:'},origin:'https://other.fixture.test',sessionStorage:{setItem(){writes++;}}});assert.equal(writes,0);
  delete process.env.SITE_URL;const standalone=await fixture(true);
  standalone({location:{protocol:'https:'},origin:'https://other.fixture.test',sessionStorage:{setItem(){writes++;}}});assert.equal(writes,1);
 }finally{if(previous===undefined)delete process.env.SITE_URL;else process.env.SITE_URL=previous;}
});
