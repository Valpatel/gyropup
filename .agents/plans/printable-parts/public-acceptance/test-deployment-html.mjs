import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {verifyDeploymentHTML} from './deployment-html.mjs';
const binding=JSON.parse(readFileSync(new URL('fixtures/deployment-html-binding.json',import.meta.url)));
const compiled=readFileSync(new URL('fixtures/'+binding.compiled_fixture,import.meta.url));
const served=readFileSync(new URL('fixtures/'+binding.served_fixture,import.meta.url));
const insertion=readFileSync(new URL('fixtures/'+binding.insertion_file,import.meta.url));
const sha=x=>createHash('sha256').update(x).digest('hex');
const verify=changes=>verifyDeploymentHTML({compiled,served,insertion,binding,...changes});
const extra=Buffer.from('<script>unexpected-injection()</script>');
test('actual retained response equals exact compiled bytes plus bound beacon insertion',()=>assert.equal(verify().served_sha256,'775d4094fbc673bfacc1a9daadea1dad6468e466bd8b29b8040a3e9db80aa1e5'));
test('unexpected source-byte change is rejected',()=>{const changed=Buffer.from(compiled);changed[10]^=1;assert.throws(()=>verify({compiled:changed}),/Compiled source identity changed/);});
test('unexpected ordinary served-byte change is rejected',()=>{const changed=Buffer.from(served);changed[10]^=1;assert.throws(()=>verify({served:changed}),/Full served response identity changed/);});
test('additional arbitrary injection is rejected without stripping',()=>assert.throws(()=>verify({served:Buffer.concat([served,extra])}),/Full served response identity changed/));
test('beacon attribute/token/version change is rejected byte for byte',()=>{const changed=Buffer.from(insertion);changed[50]^=1;assert.throws(()=>verify({insertion:changed}),/Bound deployment insertion changed/);});
test('missing, moved or duplicate insertion is rejected',()=>{
 for(const changed of [compiled,Buffer.concat([insertion,compiled]),Buffer.concat([compiled.subarray(0,binding.insertion_offset),insertion,insertion,compiled.subarray(binding.insertion_offset)])])assert.throws(()=>verify({served:changed}),/Full served response identity changed/);
});
test('rebinding only served hash cannot admit any extra injection',()=>{const changed=Buffer.concat([served,extra]);assert.throws(()=>verify({served:changed,binding:{...binding,served_sha256:sha(changed)}}),/differs beyond the exact bound insertion/);});
test('rebinding only served hash cannot admit a changed source or changed beacon',()=>{
 const changed=Buffer.from(served);changed[100]^=1;assert.throws(()=>verify({served:changed,binding:{...binding,served_sha256:sha(changed)}}),/differs beyond the exact bound insertion/);
 const beacon=Buffer.from(served);beacon[binding.insertion_offset+100]^=1;assert.throws(()=>verify({served:beacon,binding:{...binding,served_sha256:sha(beacon)}}),/differs beyond the exact bound insertion/);
});
test('wrong offset cannot pass despite unchanged full response digest',()=>assert.throws(()=>verify({binding:{...binding,insertion_offset:binding.insertion_offset+1}}),/differs beyond the exact bound insertion/));
