/** Actual accepted triangles through real Three groups, without a browser/WebGL.
 * This is a source/control preflight; both-engine actual page captures remain required. */
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {registerHooks} from 'node:module';
import {execFileSync} from 'node:child_process';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {installCurrentMotion,captureMotionFaults,captureMotionOperation} from './current-motion-capture.mjs';

const root=new URL('../../../',import.meta.url),vendor=new URL('software/site/designer/kit/vendor/three/',root);
registerHooks({resolve(s,c,n){if(s==='three')return{url:new URL('three.module.min.js',vendor).href,shortCircuit:true};if(s.startsWith('three/addons/'))return{url:new URL(s.slice(6),vendor).href,shortCircuit:true};return n(s,c);}});
const {buildRobotV2}=await import('../../../software/site/designer/robot_v2.js');
const candidate=process.env.CURRENT_MOTION_CANDIDATE,python=process.env.CURRENT_MOTION_PYTHON,toolkit=process.env.CURRENT_MOTION_TOOLKIT,revision=process.env.CURRENT_MOTION_TOOLKIT_REVISION;
const ready=candidate&&python&&toolkit&&revision;
const error=(actual,expected)=>{
  assert.deepEqual(Object.keys(actual).sort(),Object.keys(expected).sort());let worst=0;
  for(const [name,row]of Object.entries(expected)){assert.equal(actual[name].length,row.points.length);row.points.forEach((p,i)=>{worst=Math.max(worst,Math.hypot(...p.map((v,k)=>v-actual[name][i][k])));});}return worst;
};

test('actual accepted-data observation and fault helpers agree with independent source home/live points',{skip:!ready},async()=>{
  const code="import importlib.util,json,sys;from pathlib import Path;p=Path('tools/engineering/robot/current_motion.py').resolve();s=importlib.util.spec_from_file_location('preflight_reference',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);motion=m.load_motion(sys.argv[2],sys.argv[3]);print(json.dumps(m.build_reference(sys.argv[1],motion),allow_nan=False))";
  const reference=JSON.parse(execFileSync(python,['-I','-B','-c',code,candidate,toolkit,revision],{cwd:new URL('../../../',import.meta.url),maxBuffer:8*1024*1024,timeout:20000}));
  const raw=await readFile(path.join(candidate,'manifest.json'));assert.equal(createHash('sha256').update(raw).digest('hex'),reference.manifest_sha256);
  const fetcher=async url=>{const relative=new URL(url).pathname.replace(/^\/web\/robot-current\//,'');assert.ok(!relative.startsWith('/')&&!relative.includes('..'));return new Response(await readFile(path.join(candidate,relative)));};
  const robot=await buildRobotV2('http://fixture.invalid/',{presentationSource:{file:'web/robot-current/manifest.json',sha256:reference.manifest_sha256},fetcher});
  const prior=globalThis.window;globalThis.window={__sim:{state:{robot},stage:{stop(){}},sfx:{setEnabled(){}},talk:{stop(){}}}};
  try{
    await installCurrentMotion(reference);const t=window.__currentMotion;
    for(const row of reference.live){const angles=Object.fromEntries(Object.keys(row.contract.joints).map(k=>[k,0]));const actual=t.observe(row.id,row.contract,t.livePose(row,angles));assert.ok(error(actual.components,row.contract.components)<reference.tolerance_mm,row.id);}
    const home=reference.live[0],homeTrace={...t.prefix,samples:home.required_poses.map((a,i)=>t.observe('home-'+i,home.contract,t.livePose(home,a)))};
    const operation=captureMotionOperation();assert.ok(operation.exploded&&operation.reset&&operation.flapClosed);homeTrace.samples.push(...operation.trace.samples);
    const baseline={...t.prefix,samples:reference.rigid.required_poses.map((a,i)=>t.observe('rigid-'+i,reference.rigid.contract,t.rigidPose(a)))};
    const faults=captureMotionFaults(),components=reference.rigid.contract.components;
    for(const [name,probe]of Object.entries(faults)){
      if(probe.home_preserved)assert.ok(error(probe.home.components,components)<reference.tolerance_mm,name+' home');
      assert.ok(error(probe.restored.components,components)<reference.tolerance_mm,name+' restored');
      if(name==='missing-part')assert.equal(Object.keys(probe.sample.components).length,Object.keys(components).length-1);
    }
    const validate="import importlib.util,json,sys;from pathlib import Path;p=Path('tools/engineering/robot/current_motion.py').resolve();s=importlib.util.spec_from_file_location('preflight_reference',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);v=json.load(sys.stdin);motion=m.load_motion(sys.argv[1],sys.argv[2]);result=m.validate_rigid_controls(v['reference'],v['baseline'],v['faults'],motion);op=motion.validate_motion_trace(v['reference']['live'][0]['contract'],v['homeTrace'],tolerance_mm=v['reference']['tolerance_mm']);print(json.dumps({'status':result['status'],'faults':list(result['rejected_faults']),'operation':op['status'],'operationFailures':op['failures']}))";
    const controls=JSON.parse(execFileSync(python,['-I','-B','-c',validate,toolkit,revision],{cwd:new URL('../../../',import.meta.url),input:JSON.stringify({reference,baseline,faults,homeTrace}),maxBuffer:4*1024*1024,timeout:20000}));
    assert.equal(controls.status,'pass');assert.equal(controls.faults.length,7);assert.equal(controls.operation,'pass',JSON.stringify(controls.operationFailures));
  }finally{robot.dispose();globalThis.window=prior;}
});
