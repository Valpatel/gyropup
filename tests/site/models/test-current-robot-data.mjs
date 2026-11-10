/** Synthetic loader/lifecycle controls over actual Three groups, not CAD evidence. */
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {registerHooks} from 'node:module';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';

const root=new URL('../../../',import.meta.url),vendor=new URL('software/site/designer/kit/vendor/three/',root);
registerHooks({resolve(specifier,context,next){
  if(specifier==='three')return{url:new URL('three.module.min.js',vendor).href,shortCircuit:true};
  if(specifier.startsWith('three/addons/'))return{url:new URL(specifier.slice('three/'.length),vendor).href,shortCircuit:true};
  return next(specifier,context);
}});
const THREE=await import('three');
const {buildCurrentRobot,validateCurrentRobot}=await import('../../../software/site/designer/current_robot.js');
const {fiveBar}=await import('../../../software/site/designer/robot_kinematics.js');
const {composeRobotPresentations}=await import('../../../software/site/designer/robot_presentations.js');
const {buildRobotV2}=await import('../../../software/site/designer/robot_v2.js');
const {robotIdentity}=await import('../../../software/site/designer/robot_identity.js');
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const encode=value=>Buffer.from(JSON.stringify(value));

function tetra(y=0){
  const p=[[0,y,0],[2,y,0],[0,y+3,0],[0,y,4]],triangles=[[0,2,1],[0,1,3],[0,3,2],[1,2,3]];
  const b=Buffer.alloc(84+triangles.length*50);b.write('SYNTHETIC NON-CAD LIFECYCLE FIXTURE');b.writeUInt32LE(triangles.length,80);
  triangles.forEach((t,i)=>t.forEach((v,j)=>p[v].forEach((x,k)=>b.writeFloatLE(x,84+i*50+12+j*12+k*4))));
  return b;
}

function fixture(){
  const owners={body:{parent:null,origin_mm:[0,0,0],axis:[0,0,0],home_rad:0}};
  const add=(name,parent,origin=[0,0,0],axis=[0,0,0],angle=0)=>owners[name]={parent,origin_mm:origin,axis,home_rad:angle};
  const fb=fiveBar(150,150,250),[front,rear]=fb.ik(0,-300),lower=p=>Math.atan2(-300-p.C[1],-p.C[0]);
  for(const side of ['L','R']){
    add(side+'.module','body',[0,side==='L'?102.5498:-102.5498,0],[0,0,1],side==='L'?0:Math.PI);
    add(side+'.fixed',side+'.module');add(side+'.upper_front',side+'.module',[75,0,0],[0,1,0],-front.ang);add(side+'.upper_rear',side+'.module',[-75,0,0],[0,1,0],-rear.ang);
    add(side+'.front_link',side+'.upper_front',[150,0,0],[0,1,0],-(lower(front)-front.ang));add(side+'.wheel_link',side+'.upper_rear',[150,0,0],[0,1,0],-(lower(rear)-rear.ang));
    for(const [key,p]of [['knee_front_point',front.C],['knee_rear_point',rear.C],['apex_point',[0,-300]]])add(side+'.'+key,side+'.module',[p[0],0,p[1]]);
    add(side+'.wheel',side+'.apex_point',[0,0,0],[0,1,0]);
  }
  add('turret.base','body',[-40,0,246]);add('turret.pan','turret.base',[0,0,0],[0,0,1]);add('turret.tilt','turret.pan',[0,0,140],[0,-1,0]);add('turret.pinion','turret.base',[-52.65,0,0],[0,0,1]);
  for(const [key,p,axis]of [['dial',[-48,0,0],[0,0,1]],['wheel_l',[25,25.81,0],[0,0,1]],['wheel_r',[25,-25.81,0],[0,0,1]],['flap',[-87,0,91],[0,-1,0]]])add('turret.'+key,'turret.tilt',p,axis);
  const parts=[],files=new Map();
  function part(name,owner,y=0){const file='meshes/'+name+'.stl',bytes=tetra(y);files.set('/assets/robot-current/'+file,bytes);parts.push({name,owner,file,sha256:sha(bytes),color:'#223344',visible:true,bounds_mm:[0,y,0,2,y+3,4]});}
  for(let i=0;i<82;i++)part('fixture_body_'+i,'body');
  for(const side of ['L','R']){
    const actual=[['motor_front','fixed'],['output_adapter_front','upper_front'],['front_link','front_link'],['wheel_link','wheel_link'],['wheel_tyre','wheel']];
    for(const [name,owner]of actual)part(side+'.'+name,side+'.'+owner,name==='wheel_tyre'?(side==='L'?216:-216):0);
    for(let i=actual.length;i<40;i++)part(side+'.fixture_'+i,side+'.fixed');
  }
  for(let i=0;i<62;i++)part('turret.fixture_'+i,'turret.'+(i%2?'tilt':'base'));
  const model={schema:'gyropup.current-robot-presentation/1',native_source:'3a40891962b0b0a04625e070700f1d130bea3c7b',collection_sha256:'7c2f1905474a8c89bdc477ea472f5c826e57c674aa222f2134f6a0a4138d5a67',units:'mm',up:'z',owners,parts,
    home:{leg_mm:300},home_bounds_mm:[-300,-300,-427,300,300,510],fivebar:{D_mm:150,l1_mm:150,l2_mm:250,y_off_mm:102.5498,wheel_radius_mm:127,h_range_mm:[185,375]},
    mounts:{eyes:[162.6,0,182],camera_front:[192.6,0,142.5],headlights:[[55,155,160],[55,-155,160]],pan:[-40,0,246],tilt:[-40,0,386],muzzle:[110,0,371],laser:[44.5,0,400.5]},
    engineering:{mass_kg:null,com_mm:null,physics_current:false,manufacturing_released:false,physical_qualified:false},moving_coverage:{mechanical_ownership_verified:false},limits:'Synthetic control fixture; no native evidence.'};
  const refresh=()=>{const raw=encode(model);files.set('/assets/robot-current/manifest.json',raw);return{file:'assets/robot-current/manifest.json',sha256:sha(raw)};};
  return{model,files,refresh,source:refresh(),fetcher:async url=>{const raw=files.get(new URL(url).pathname);return new Response(raw??'missing',{status:raw?200:404});}};
}

test('real loader requires an external manifest hash and rejects qualified or incomplete input',async()=>{
  const f=fixture();await assert.rejects(buildCurrentRobot('http://fixture.invalid/',{fetcher:f.fetcher}),/binding required/);
  for(const change of [m=>m.parts.pop(),m=>m.parts.push(m.parts[0]),m=>m.engineering.mass_kg=35,m=>m.engineering.physics_current=true,
                       m=>m.owners['L.upper_front'].parent='L.front_link',m=>m.parts[0].owner='missing',m=>m.fivebar.y_off_mm=82.3]){
    const model=structuredClone(f.model);change(model);assert.throws(()=>validateCurrentRobot(model));
  }
  f.files.get('/assets/robot-current/manifest.json')[0]^=1;
  await assert.rejects(buildCurrentRobot('http://fixture.invalid/',{source:f.source,fetcher:f.fetcher}),/SHA-256/);
});

test('actual builder owns complete fixture, uses the live solver, and resets firing/explode',async()=>{
  const f=fixture(),robot=await buildCurrentRobot('http://fixture.invalid/',{source:f.source,fetcher:f.fetcher});
  try{
    assert.equal(robot.parts.length,224);assert.equal(robot.turret.model.parts.length,62);assert.equal(robot.info.massKg,null);assert.equal(robot.info.homeLegMM,300);
    const home=robot.setPose({legMM:300});assert.equal(home.legMM,300);assert.equal(robot.base.position.y,.427);
    for(const [legMM,pitch,rollMM,wheel]of [[185,0,0,0],[375,0,0,0],[300,.1,24,1.2],[250,-.1,-16,-.7]]){
      const state=robot.setPose({legMM,pitch,rollMM,wheel});assert.ok(Number.isFinite(state.hipHeightMM));
      assert.equal(robot.owners['L.wheel'].rotation.x,wheel);assert.equal(robot.owners['R.wheel'].rotation.x,-wheel);
      const expected=fiveBar(150,150,250).ik((legMM+rollMM/2)*Math.sin(pitch),-(legMM+rollMM/2)*Math.cos(pitch));
      assert.ok(Math.abs(robot.owners['L.upper_front'].rotation.x+expected[0].ang)<1e-12);
      const right=fiveBar(150,150,250).ik(-(legMM-rollMM/2)*Math.sin(pitch),-(legMM-rollMM/2)*Math.cos(pitch));
      assert.ok(Math.abs(robot.owners['R.upper_front'].rotation.x+right[0].ang)<1e-12);
    }
    const before=robot.base.matrix.clone();assert.throws(()=>robot.setPose({pitch:Infinity}),/nonfinite/);assert.deepEqual(robot.base.matrix,before);
    robot.setExplode(.5);assert.ok(robot.parts.some(p=>p.mesh.position.length()>.001));robot.turret.flash();assert.ok(robot.parts.every(p=>p.mesh.position.length()===0));
    robot.turret.reload();for(let i=0;i<90;i++)robot.turret.step(1/60);
    assert.ok(Math.abs(robot.owners['turret.flap'].rotation.x)<1e-12);assert.ok(robot.owners['turret.wheel_l'].rotation.y>0);assert.ok(robot.owners['turret.wheel_r'].rotation.y<0);
    assert.throws(()=>robot.setFromQpos([],{}),/complete recorded/);
    assert.deepEqual(robot.head.position.toArray(),[0,.182,.1626]);
  }finally{robot.dispose();robot.dispose();}
  assert.equal(robot.group.children.length,0);assert.throws(()=>robot.setPose(),/disposed/);
});

test('partition holes and corrupt real mesh bytes reject before readiness',async()=>{
  for(const mutate of [f=>f.files.get('/assets/robot-current/meshes/fixture_body_0.stl')[90]^=1,
    f=>{const p=f.model.parts[0];delete p.owner;p.partitions=[{owner:'body',triangle_indices:[0]},{owner:'body',triangle_indices:[1]}];p.triangle_records_sha256='0'.repeat(64);}]){
    const f=fixture();mutate(f);const source=f.refresh();await assert.rejects(buildCurrentRobot('http://fixture.invalid/',{source,fetcher:f.fetcher}),/SHA-256|incomplete partition/);
  }
});

test('held late transfer cannot attach after cancellation; every created geometry disposes once',async()=>{
  const f=fixture(),controller=new AbortController(),seen=new Map();
  const original=THREE.BufferGeometry.prototype.dispose;
  THREE.BufferGeometry.prototype.dispose=function(){seen.set(this,(seen.get(this)??0)+1);return original.call(this);};
  let release,reached;const held=new Promise(resolve=>release=resolve),started=new Promise(resolve=>reached=resolve);
  const fetcher=async(url,opts)=>{if(new URL(url).pathname.endsWith('fixture_body_0.stl')){reached();await held;}return f.fetcher(url,opts);};
  try{
    const build=buildCurrentRobot('http://fixture.invalid/',{source:f.source,fetcher,signal:controller.signal});
    await started;controller.abort(new Error('fixture cancellation'));release();await assert.rejects(build);
    await new Promise(resolve=>setTimeout(resolve,0));assert.ok(seen.size>0);assert.ok([...seen.values()].every(n=>n===1),'No model/effect geometry disposed twice');
  }finally{release();THREE.BufferGeometry.prototype.dispose=original;}
});

test('ready model cancellation disposes every owned visible/effect resource once',async()=>{
  const f=fixture(),controller=new AbortController(),robot=await buildCurrentRobot('http://fixture.invalid/',{source:f.source,fetcher:f.fetcher,signal:controller.signal});
  const expected=new Map();
  for(const root of [robot.group,robot.turret.laser])root.traverse(o=>{if(o.geometry)expected.set(o.geometry,0);for(const m of o.material?(Array.isArray(o.material)?o.material:[o.material]):[])expected.set(m,0);});
  for(const resource of expected.keys())resource.addEventListener('dispose',()=>expected.set(resource,expected.get(resource)+1));
  controller.abort();robot.dispose();assert.ok([...expected.values()].every(n=>n===1));assert.throws(()=>robot.setPose(),/disposed/);
});

function holder(mode){
  const group=new THREE.Group(),base=new THREE.Group(),head=new THREE.Object3D(),fov=new THREE.Group(),turret={group:new THREE.Group(),laser:new THREE.Group(),muzzle:new THREE.Object3D(),flash(){}};
  group.add(base);base.add(turret.group,head,fov);
  const log={disposed:0,poses:[],qpos:[],explodes:[]};
  return{group,base,head,fov,turret,lights:[],info:{massKg:mode==='current'?null:35,hMin:mode==='current'?185:150},presentation:{mode,bodySource:mode+'-source'},log,
    setPose(p){log.poses.push(p);return p;},setFromQpos(q){log.qpos.push(q);},setExplode(x){log.explodes.push(x);},dispose(){log.disposed++;group.removeFromParent();}};
}

test('whole mode metadata/anchors commit atomically and repeated switches reuse only two holders',async()=>{
  const current=holder('current'),recorded=holder('recorded');let release,calls=0;
  const waiting=new Promise(resolve=>release=resolve),robot=composeRobotPresentations(current,async()=>{calls++;await waiting;return recorded;});
  robot.group.position.z=2;const switching=robot.setPresentation('recorded');
  assert.equal(robot.presentation.mode,'current');assert.equal(robot.info.massKg,null);assert.equal(robot.base,current.base);
  assert.throws(()=>robot.setFromQpos([1],{}),/complete recorded/);
  release();await switching;
  assert.equal(robot.presentation.mode,'recorded');assert.equal(robot.info.massKg,35);assert.equal(robot.info.hMin,150);assert.equal(robot.head,recorded.head);assert.equal(robot.base,recorded.base);
  assert.equal(robot.group.position.z,0);robot.setFromQpos([2],{});assert.deepEqual(recorded.log.qpos,[[2]]);
  assert.throws(()=>robot.setPose({}),/current robot/);assert.equal(current.group.visible,false);
  await robot.setPresentation('current');assert.equal(robot.group.position.z,2);assert.equal(robot.presentation.bodySource,'current-source');assert.equal(robot.turret.muzzle,current.turret.muzzle);
  for(let i=0;i<4;i++){await robot.setPresentation('recorded');await robot.setPresentation('current');}
  assert.equal(calls,1);assert.equal(robot.group.children.length,2);assert.equal(robot.turret.laser.children.length,2);
  robot.dispose();robot.dispose();assert.equal(current.log.disposed,1);assert.equal(recorded.log.disposed,1);assert.throws(()=>robot.setPose({}),/disposed/);
});

test('failed or superseded recorded load preserves current, and a late disposed holder never attaches',async()=>{
  const current=holder('current'),recorded=holder('recorded');let release,calls=0;
  const waiting=new Promise(resolve=>release=resolve),original=new Error('retained fixture download failed');
  const robot=composeRobotPresentations(current,async()=>{if(++calls===1)throw original;await waiting;return recorded;});
  await assert.rejects(robot.setPresentation('recorded'),e=>e===original);assert.equal(robot.presentation.mode,'current');assert.equal(current.group.visible,true);
  const loading=robot.setPresentation('recorded');await robot.setPresentation('current');release();await loading;
  assert.equal(robot.presentation.mode,'current');assert.equal(recorded.group.parent,null);assert.equal(robot.group.children.length,1);
  await robot.setPresentation('recorded');assert.equal(robot.presentation.mode,'recorded');robot.dispose();
  const late=holder('recorded'),otherCurrent=holder('current');let complete;
  const pending=new Promise(resolve=>complete=resolve),other=composeRobotPresentations(otherCurrent,async()=>{await pending;return late;});
  const load=other.setPresentation('recorded');other.dispose();complete();await assert.rejects(load,/disposed/);
  assert.equal(late.log.disposed,1);assert.equal(late.group.parent,null);assert.equal(other.group.children.length,0);
});

test('real v2 entry loads the whole tracked archive, preserves qpos/muzzle/mass, then restores current',async()=>{
  const f=fixture(),originalFetch=globalThis.fetch,requests=[];
  globalThis.fetch=async(url,options)=>{
    const path=new URL(url).pathname;requests.push(path);
    if(path.startsWith('/assets/robot-current/'))return f.fetcher(url,options);
    if(!path.startsWith('/exports/sim/v2/rig/'))throw new Error('Unexpected non-archive request: '+path);
    try{return new Response(await readFile(new URL('hardware'+path,root)),{status:200});}
    catch(error){return new Response(error.message,{status:404});}
  };
  let robot;
  try{
    robot=await buildRobotV2('http://fixture.invalid/',{presentationSource:f.source,fetcher:globalThis.fetch});
    const currentMass=robot.info.massKg;assert.equal(currentMass,null);
    assert.equal(robotIdentity(robot).massRow[0],'current mass');assert.match(robotIdentity(robot).massRow[1],/Pending/);
    assert.match(robotIdentity(robot).body,/Collection266/);assert.match(robotIdentity(robot).movingCoverage,/unresolved/);
    const currentMuzzle=robot.turret.muzzle.position.toArray();await robot.setPresentation('recorded');
    const archive=JSON.parse(await readFile(new URL('hardware/exports/sim/v2/rig/manifest.json',root)));
    assert.equal(robot.presentation.mode,'recorded');assert.equal(robot.info.massKg,archive.mass_kg);assert.equal(robot.info.hMin,archive.fivebar.h_range_mm[0]);
    assert.equal(robotIdentity(robot).massRow[0],'recorded rig mass');assert.match(robotIdentity(robot).massRow[1],/earlier physics snapshot/);
    assert.match(robotIdentity(robot).body,/Recorded interim/);
    const expectedMuzzle=[archive.turret.muzzle_mm[1]-archive.turret.tilt_mm[1],archive.turret.muzzle_mm[2]-archive.turret.tilt_mm[2],archive.turret.muzzle_mm[0]-archive.turret.tilt_mm[0]].map(v=>v*.001);
    robot.turret.muzzle.position.toArray().forEach((v,i)=>assert.ok(Math.abs(v-expectedMuzzle[i])<1e-12));
    const recordedBase=robot.base,recordedMuzzle=robot.turret.muzzle,recordedInfo=robot.info;
    const q=Array(21).fill(0);q[2]=.5;q[3]=1;
    const layout={motor_f_l:7,knee_f_l:8,motor_r_l:9,knee_r_l:10,wheel_l:11,motor_f_r:12,knee_f_r:13,motor_r_r:14,knee_r_r:15,wheel_r:16,turret_pan:17,turret_tilt:18};
    q[7]=.2;q[11]=.3;q[17]=.4;q[18]=.1;robot.setFromQpos(q,layout);
    assert.equal(robot.base.position.y,.5);assert.equal(robot.legs.l.wheel.rotation.x,.3);assert.equal(robot.turret.pan.rotation.y,.4);assert.equal(robot.turret.tilt.rotation.x,.1);
    const recordedTransforms=robot.base.children.filter(o=>o.isMesh).map(o=>[o.name,o.position.toArray(),o.quaternion.toArray(),o.geometry.attributes.position.count]);
    await robot.setPresentation('current');assert.equal(robot.info.massKg,null);assert.equal(robot.info.hMin,185);assert.deepEqual(robot.turret.muzzle.position.toArray(),currentMuzzle);
    robot.setPose({legMM:300});await robot.setPresentation('recorded');
    assert.equal(robot.base,recordedBase);assert.equal(robot.turret.muzzle,recordedMuzzle);assert.equal(robot.info,recordedInfo);
    assert.deepEqual(robot.base.children.filter(o=>o.isMesh).map(o=>[o.name,o.position.toArray(),o.quaternion.toArray(),o.geometry.attributes.position.count]),recordedTransforms);
    assert.ok(!requests.some(path=>path.includes('turret_box')||path.includes('leg-attachments')),'Recorded-only construction loads no unrelated current geometry');
  }finally{robot?.dispose();globalThis.fetch=originalFetch;}
});
