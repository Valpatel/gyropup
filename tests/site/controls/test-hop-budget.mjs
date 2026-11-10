import assert from 'node:assert/strict';
import test from 'node:test';
import {checkHopProgress,HOP_LIMITS,pollHop} from './hop-budget.mjs';
// Explicit observer samples, not CAD, copied trajectory logic or physical evidence.
const sample=()=>({simulatedS:1.45,nowMs:22000,startedAt:0,lastFrameAt:22000,frames:30,maxY:.16,y:0,landed:true,paused:false,replay:false,visibility:'visible',stageError:null});
test('completed actual-frame observation can exceed old generic15s and stays bounded',()=>{assert.equal(checkHopProgress(sample()),true);assert.equal(HOP_LIMITS.wallMs,30000);assert.equal(HOP_LIMITS.simulationS,3);});
test('feet on ground do not count as completed recovery',()=>{assert.equal(checkHopProgress({...sample(),landed:false}),false);assert.equal(checkHopProgress({...sample(),maxY:.1}),false);});
test('never-ending motion and frozen frames are separate failures',()=>{assert.throws(()=>checkHopProgress({...sample(),landed:false,simulatedS:3.01,frames:61}),/simulated-time/);assert.throws(()=>checkHopProgress({...sample(),landed:false,lastFrameAt:1000}),/stalled/);assert.throws(()=>checkHopProgress({...sample(),nowMs:30001,lastFrameAt:30001}),/wall budget/);});
test('paused, hidden, erroneous and invalid observations fail before success',()=>{for(const bad of [{paused:true},{replay:true},{visibility:'hidden'},{stageError:'fixture callback failed'},{frames:0},{simulatedS:NaN},{lastFrameAt:22001}])assert.throws(()=>checkHopProgress({...sample(),...bad}));});

test('actual polling adapter returns booleans and rejects promise-valued guards',()=>{
 const args={guard:checkHopProgress,readSample:()=>({...sample(),landed:false}),limits:HOP_LIMITS};
 assert.equal(pollHop(args),false);assert.equal(pollHop({...args,readSample:sample}),true);
 assert.throws(()=>pollHop({...args,guard:()=>Promise.resolve(false)}),/synchronous boolean/);
});
