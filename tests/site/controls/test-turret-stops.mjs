// Kernel-free controls over actual runtime code; compiled bench motion is also checked by test:interactions.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';
const root = new URL('../../../', import.meta.url);
const source = await readFile(new URL('software/site/designer/turret3d.js',root),'utf8');
const vendor = new URL('software/site/designer/kit/vendor/three/three.module.min.js',root).href;
assert.equal(source.split("from 'three'").length,2);
// The browser import map supplies this exact checked-in Three module. No DOM or CAD imports are needed.
const {TILT_STOPS,setTiltStops} = await import('data:text/javascript;base64,'+Buffer.from(source.replace("from 'three'",`from '${vendor}'`)).toString('base64'));
const valid=()=>({tilt_deg:{min:-25,max:12},fire_tilt_max_deg:10});
test('firing bounds are mandatory and atomic, independent of the higher aim stop',()=>{
 assert.equal(setTiltStops(valid()),true);
 assert.ok(Math.abs(TILT_STOPS.max*180/Math.PI-12)<1e-12);
 assert.ok(Math.abs(TILT_STOPS.fire*180/Math.PI-10)<1e-12);
 const before={...TILT_STOPS};
 for(const fire of [undefined,NaN,Infinity,-Infinity,13,-26,'10',true]){
  const value=valid(); if(fire===undefined)delete value.fire_tilt_max_deg;else value.fire_tilt_max_deg=fire;
  assert.equal(setTiltStops(value),false,`reject ${String(fire)}`);assert.deepEqual(TILT_STOPS,before);
 }
 for(const tilt_deg of [{min:12,max:-25},{min:-25,max:Infinity},{min:-25,max:'12'},null]){
  assert.equal(setTiltStops({...valid(),tilt_deg}),false);assert.deepEqual(TILT_STOPS,before);
 }
});
const bench=await readFile(new URL('software/site/designer/turret_bench.js',root),'utf8');
function between(start,end){assert.equal(bench.split(start).length,2);assert.equal(bench.split(end).length,2);return bench.slice(bench.indexOf(start),bench.indexOf(end));}
test('actual bench manifest guard rejects missing firing bounds before any geometry setup',async()=>{
 const body=between('  const stops = readTiltStops(', '  const mech = man.mechanics;');
 const {readTiltStops}=await import('data:text/javascript;base64,'+Buffer.from(source.replace("from 'three'",`from '${vendor}'`)).toString('base64'));
 const guard=new Function('man','readTiltStops',body+'return stops;');
 const limits={tilt_deg:[-25,12],fire_tilt_max_deg:10};
 assert.equal(guard({limits},readTiltStops).fire,10);
 for(const fire of [undefined,NaN,13,-26])assert.throws(()=>guard({limits:{...limits,fire_tilt_max_deg:fire}},readTiltStops),/Invalid turret firing limits/);
});
test('actual servo update reaches positive stop and rejects the former zero-ceiling mutant',()=>{
 const body=between('    const tmin = -tiltMax(S.pan) * D2R;', '    // the safety line:');
 const run=(text)=>{const S={pan:0,panCmd:0,tilt:0,tiltCmd:12*Math.PI/180};
  new Function('S','lim','upMax','D2R','dt','tiltMax','clamp',text)(S,{tilt_deg:[-25,12],pan_rate_deg_s:60,tilt_rate_deg_s:60},12,Math.PI/180,1,()=>25,(v,l,h)=>Math.min(h,Math.max(l,v)));return S.tilt*180/Math.PI;};
 assert.ok(Math.abs(run(body)-12)<1e-12);
 const needle='tmin, upMax * D2R';assert.equal(body.split(needle).length,2);
 assert.equal(run(body.replace(needle,'tmin, 0')),0,'former applied-motion clamp is detected');
});
