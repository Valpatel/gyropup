// Exact byte identity only. No HTML parsing, normalization, stripping or tolerance.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
export function verifyDeploymentHTML({compiled,served,insertion,binding}){
 assert.ok(Buffer.isBuffer(compiled)&&Buffer.isBuffer(served)&&Buffer.isBuffer(insertion));
 assert.equal(binding.artifact,'/designer/build.html');assert.equal(binding.request_path,'/designer/build');
 assert.equal(binding.transformation,'one exact byte insertion');
 assert.equal(sha(compiled),binding.compiled_sha256,'Compiled source identity changed');
 assert.equal(sha(insertion),binding.insertion_sha256,'Bound deployment insertion changed');
 assert.equal(insertion.length,binding.insertion_bytes);
 assert.ok(Number.isInteger(binding.insertion_offset)&&binding.insertion_offset>=0&&binding.insertion_offset<=compiled.length);
 assert.equal(sha(served),binding.served_sha256,'Full served response identity changed');
 const expected=Buffer.concat([compiled.subarray(0,binding.insertion_offset),insertion,compiled.subarray(binding.insertion_offset)]);
 assert.equal(served.equals(expected),true,'Served HTML differs beyond the exact bound insertion');
 return {compiled_sha256:sha(compiled),served_sha256:sha(served),transformation:binding.transformation,insertion_offset:binding.insertion_offset,insertion_sha256:sha(insertion),insertion_bytes:insertion.length};
}
