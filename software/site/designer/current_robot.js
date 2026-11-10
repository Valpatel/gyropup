// Product adapter for original collection meshes and source-owned joint frames.
// Generic asset/hash validation and rendering primitives remain in cad-agent's kit.
// This builder is not selected by public routes until its artifact/trace adoption.
import * as THREE from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { readAsset, assetURL } from './kit/assembly/guide.js';
import { validateGeometry, validateSTLBytes, isRecord } from './kit/portal-data.js';
import { fiveBar } from './robot_kinematics.js';
import { buildRobotSensors } from './robot_sensors.js';
import { buildTurret, BALL } from './turret3d.js';

const M=.001, at=p=>new THREE.Vector3(p[1]*M,p[2]*M,p[0]*M);
const axis=p=>new THREE.Vector3(p[1],p[2],p[0]);
const BASIS=new THREE.Matrix4().set(0,1,0,0,0,0,1,0,1,0,0,0,0,0,0,1).multiply(new THREE.Matrix4().makeScale(M,M,M));
const hash=/^[0-9a-f]{64}$/,vec=(p,n=3)=>Array.isArray(p)&&p.length===n&&p.every(Number.isFinite);
const COLLECTION='7c2f1905474a8c89bdc477ea472f5c826e57c674aa222f2134f6a0a4138d5a67';
const NATIVE='3a40891962b0b0a04625e070700f1d130bea3c7b';
const fail=text=>{throw new Error('Current robot: '+text);};

export function validateCurrentRobot(model){
  if(!isRecord(model)||model.schema!=='gyropup.current-robot-presentation/1'||model.units!=='mm'||model.up!=='z'
    ||model.native_source!==NATIVE||model.collection_sha256!==COLLECTION)fail('collection/frame identity differs');
  if(!isRecord(model.owners)||!isRecord(model.owners.body)||!Array.isArray(model.parts)||model.parts.length!==224)fail('complete owner/part inventory required');
  const names=new Set(),counts={body:0,leg:0,turret:0};
  for(const [name,owner]of Object.entries(model.owners)){
    if(!isRecord(owner)||!vec(owner.origin_mm)||!vec(owner.axis)||!Number.isFinite(owner.home_rad)
      ||(owner.parent!==null&&!(owner.parent in model.owners)))fail('invalid owner '+name);
    const norm=Math.hypot(...owner.axis);if(norm!==0&&Math.abs(norm-1)>1e-10)fail('nonunit owner axis');
    const ancestors=new Set([name]);let p=owner.parent;
    while(p!==null){if(ancestors.has(p))fail('cyclic owner chain');ancestors.add(p);p=model.owners[p]?.parent;if(p===undefined)fail('missing parent');}
  }
  if(model.owners.body.parent!==null)fail('body must own the complete model');
  for(const p of model.parts){
    if(!isRecord(p)||typeof p.name!=='string'||names.has(p.name)||!hash.test(p.sha256)||!vec(p.bounds_mm,6)
      ||!/^#[0-9a-f]{6}$/i.test(p.color)||typeof p.visible!=='boolean')fail('invalid/duplicate part');
    names.add(p.name);counts[/^[LR]\./.test(p.name)?'leg':p.name.startsWith('turret.')?'turret':'body']++;
    if(typeof p.file!=='string'||!p.file.startsWith('meshes/'))fail('invalid mesh path');
    if(p.partitions!==undefined){
      if(p.owner!==undefined||!Array.isArray(p.partitions)||p.partitions.length!==2||!hash.test(p.triangle_records_sha256))fail('invalid grouped part');
      const used=new Set();for(const r of p.partitions){
        if(!isRecord(r)||!(r.owner in model.owners)||!Array.isArray(r.triangle_indices)||!r.triangle_indices.length)fail('empty partition');
        for(const i of r.triangle_indices){if(!Number.isSafeInteger(i)||i<0||used.has(i))fail('invalid/duplicate partition triangle');used.add(i);}
      }
    }else if(!(p.owner in model.owners))fail('unassigned part '+p.name);
  }
  if(counts.body!==82||counts.leg!==80||counts.turret!==62)fail('current224 membership differs');
  if(!isRecord(model.engineering)||model.engineering.mass_kg!==null||model.engineering.com_mm!==null
    ||model.engineering.physics_current!==false||model.engineering.manufacturing_released!==false||model.engineering.physical_qualified!==false
    ||model.moving_coverage?.mechanical_ownership_verified!==false)fail('unsupported engineering qualification');
  if(model.home?.leg_mm!==300||!vec(model.home_bounds_mm,6))fail('home/bounds contract missing');
  const f=model.fivebar;if(!isRecord(f)||f.D_mm!==150||f.l1_mm!==150||f.l2_mm!==250||f.y_off_mm!==102.5498
    ||f.wheel_radius_mm!==127||JSON.stringify(f.h_range_mm)!=='[185,375]')fail('source linkage dimensions differ');
  if(!isRecord(model.mounts)||!['eyes','camera_front','pan','tilt','muzzle','laser'].every(k=>vec(model.mounts[k]))
    ||!Array.isArray(model.mounts.headlights)||model.mounts.headlights.length!==2||!model.mounts.headlights.every(p=>vec(p)))fail('sensor/effect anchors missing');
  return model;
}

/** source is an external reviewed manifest hash, never a self-supplied manifest field. */
export async function buildCurrentRobot(root,{source,eyes,color=0xf5b82e,fetcher=fetch,signal}={}){
  if(!source||!hash.test(source.sha256))fail('reviewed presentation manifest binding required');
  const baseURL=new URL(root,globalThis.location?.href??'http://fixture.invalid/');
  const url=assetURL(source.file,baseURL,baseURL),lifetime=new AbortController();
  const geometries=new Set(),materials=new Set(),parts=[],owners={},group=new THREE.Group(),base=new THREE.Group();group.add(base);
  let disposed=false,turret;
  const abort=()=>{lifetime.abort(signal?.reason);dispose();};
  const ensureLive=()=>{if(disposed||lifetime.signal.aborted)fail('presentation is disposed or cancelled');};
  function dispose(){
    if(disposed)return;disposed=true;lifetime.abort();signal?.removeEventListener('abort',abort);
    turret?.dispose();group.removeFromParent();for(const g of geometries)g.dispose();for(const m of materials)m.dispose();geometries.clear();materials.clear();group.clear();
  }
  signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted)abort();
  try{
    const bytes=await readAsset(url,{signal:lifetime.signal,fetcher,expectedHash:source.sha256,maxBytes:4*1024*1024});ensureLive();
    const model=validateCurrentRobot(JSON.parse(new TextDecoder().decode(bytes)));
    for(const name of Object.keys(model.owners))owners[name]=new THREE.Group();
    for(const [name,entry]of Object.entries(model.owners)){
      const g=owners[name];g.name=name;g.position.copy(at(entry.origin_mm));
      if(entry.axis.some(Boolean))g.quaternion.setFromAxisAngle(axis(entry.axis),entry.home_rad);
      (entry.parent===null?base:owners[entry.parent]).add(g);
    }
    const frame={group:owners['turret.base'],pan:owners['turret.pan'],tilt:owners['turret.tilt']};
    if(Object.values(frame).some(g=>!g))fail('turret owner graph missing');
    turret=buildTurret(color,{frames:frame,geometry:false});
    group.updateMatrixWorld(true);
    const homes=Object.fromEntries(Object.entries(owners).map(([name,g])=>[name,g.matrixWorld.clone().invert()]));
    const loader=new STLLoader();let next=0,firstError;
    function makePart(entry,geometry,owner,partition){
      ensureLive();geometry.applyMatrix4(BASIS).applyMatrix4(homes[owner]);geometry.computeVertexNormals();geometry.computeBoundingBox();
      const logical=entry.name.replace(/^turret\./,''),opacity=logical==='hopper'?.35:logical==='hopper_lid'?.6:1;
      const material=new THREE.MeshPhysicalMaterial({color:entry.color,roughness:.45,metalness:.15,clearcoat:.15,opacity,transparent:opacity<1,depthWrite:opacity>=1,side:THREE.FrontSide});materials.add(material);
      const mesh=new THREE.Mesh(geometry,material);mesh.name=entry.name+(partition?'@'+owner:'');mesh.visible=entry.visible;mesh.castShadow=opacity>=1;mesh.receiveShadow=true;
      mesh.userData.sourcePart=entry.name;mesh.userData.owner=owner;owners[owner].add(mesh);
      const direction=geometry.boundingBox.getCenter(new THREE.Vector3());if(direction.length()<.001)direction.set(0,1,0);direction.normalize().multiplyScalar(.075);
      parts.push({entry,mesh,owner,partition,explode:direction});
    }
    async function worker(){
      while(next<model.parts.length&&!lifetime.signal.aborted){
        const entry=model.parts[next++];
        try{
          const raw=await readAsset(assetURL(entry.file,url,new URL('./',url)),{signal:lifetime.signal,fetcher,expectedHash:entry.sha256,maxBytes:16*1024*1024});ensureLive();
          validateSTLBytes(raw);const full=loader.parse(raw);geometries.add(full);validateGeometry(full);
          if(full.index)fail('unexpected indexed source geometry');
          const b=full.boundingBox,observed=[...b.min.toArray(),...b.max.toArray()];
          if(observed.some((v,i)=>Math.abs(v-entry.bounds_mm[i])>.00002))fail('source mesh bounds differ: '+entry.name);
          if(entry.partitions){
            const count=full.attributes.position.count/3,ids=entry.partitions.flatMap(p=>p.triangle_indices);
            if(ids.length!==count||ids.some(i=>i>=count))fail('incomplete partition triangle coverage');
            for(const partition of entry.partitions){
              const positions=new Float32Array(partition.triangle_indices.length*9),original=full.attributes.position.array;
              partition.triangle_indices.forEach((t,i)=>positions.set(original.subarray(t*9,t*9+9),i*9));
              const geometry=new THREE.BufferGeometry();geometries.add(geometry);geometry.setAttribute('position',new THREE.BufferAttribute(positions,3));
              makePart(entry,geometry,partition.owner,partition);
            }
            geometries.delete(full);full.dispose();
          }else makePart(entry,full,entry.owner);
        }catch(error){firstError??=error;lifetime.abort(error);}
      }
    }
    await Promise.allSettled(Array.from({length:4},worker));if(firstError)throw firstError;ensureLive();
    const sensors=buildRobotSensors(base,model.mounts,eyes);
    // Eye textures belong to createEyes/the caller, not to this model instance.
    base.traverse(o=>{if((o.isMesh||o.isLineSegments)&&!parts.some(p=>p.mesh===o)&&!o.userData.keep){geometries.add(o.geometry);for(const m of Array.isArray(o.material)?o.material:[o.material])materials.add(m);}});
    const fb=fiveBar(model.fivebar.D_mm,model.fivebar.l1_mm,model.fivebar.l2_mm),[hMin,hMax]=model.fivebar.h_range_mm,wheelR=model.fivebar.wheel_radius_mm;
    const tyres=model.parts.filter(p=>/^[LR]\.wheel_tyre$/.test(p.name));
    const trackMM=Math.abs((tyres[0].bounds_mm[1]+tyres[0].bounds_mm[4]-tyres[1].bounds_mm[1]-tyres[1].bounds_mm[4])/2);
    const legs=Object.fromEntries(['L','R'].map(s=>[s.toLowerCase(),{upperF:owners[s+'.upper_front'],upperR:owners[s+'.upper_rear'],lowerF:owners[s+'.front_link'],lowerR:owners[s+'.wheel_link'],wheel:owners[s+'.wheel']}]));
    function setLeg(side,h,lean,wheel){
      const sign=side==='L'?1:-1,target=[sign*h*Math.sin(lean),-h*Math.cos(lean)],solution=fb.ik(...target);
      if(!solution)fail('requested live pose is outside the source linkage');
      const [f,r]=solution,angle=p=>Math.atan2(target[1]-p.C[1],target[0]-p.C[0]);
      return()=>{
        owners[side+'.upper_front'].rotation.x=-f.ang;owners[side+'.upper_rear'].rotation.x=-r.ang;
        owners[side+'.front_link'].rotation.x=-(angle(f)-f.ang);owners[side+'.wheel_link'].rotation.x=-(angle(r)-r.ang);
        for(const [key,p]of [['knee_front_point',f.C],['knee_rear_point',r.C],['apex_point',target]])owners[side+'.'+key].position.copy(at([p[0],0,p[1]]));
        owners[side+'.wheel'].rotation.x=sign*wheel;
      };
    }
    let explode=0;
    function setExplode(value=0){ensureLive();explode=Math.max(0,Math.min(1,Number.isFinite(+value)?+value:0));for(const p of parts)p.mesh.position.copy(p.explode).multiplyScalar(explode);}
    function setPose({height=(300-hMin)/(hMax-hMin),legMM,pitch=0,rollMM=0,wheel=0}={}){
      ensureLive();if(![height,pitch,rollMM,wheel].every(Number.isFinite)||(legMM!==undefined&&!Number.isFinite(legMM)))fail('nonfinite pose');
      const h=legMM??(hMin+(hMax-hMin)*height),clamp=x=>Math.min(hMax,Math.max(hMin,x)),hs={L:clamp(h+rollMM/2),R:clamp(h-rollMM/2)};
      const apply=['L','R'].map(s=>setLeg(s,hs[s],pitch,wheel));apply.forEach(fn=>fn());
      const mean=(hs.L+hs.R)/2;base.position.set(0,(wheelR+mean)*M,0);base.rotation.set(pitch,0,Math.atan2(hs.L-hs.R,trackMM),'YXZ');
      return {hipHeightMM:mean+wheelR,legMM:mean,kneeDeg:null};
    }
    const tiltP=at(model.mounts.tilt),local=p=>at(p).sub(tiltP);
    turret.muzzle.position.copy(local(model.mounts.muzzle));turret.laserOrigin.position.copy(local(model.mounts.laser));turret.flashMesh.position.copy(turret.muzzle.position).add(new THREE.Vector3(0,0,.006));
    turret.muzzle.userData.launchSpeed=BALL.speed;
    let wheel=0,dial=0,dialTo=0,spinFor=0,reloadFor=0;
    const originalFlash=turret.flash,originalStep=turret.step;
    function poseMechanism(a={}){
      ensureLive();turret.pan.rotation.y=a.pan??turret.pan.rotation.y;turret.tilt.rotation.x=-(a.tilt??-turret.tilt.rotation.x);
      owners['turret.pinion'].rotation.y=a.pinion??-3*turret.pan.rotation.y;
      owners['turret.dial'].rotation.y=a.dial??dial;owners['turret.wheel_l'].rotation.y=a.wheel_l??wheel;owners['turret.wheel_r'].rotation.y=-(a.wheel_r??wheel);owners['turret.flap'].rotation.x=-(a.flap??0);
    }
    Object.assign(turret,{poseMechanism,reload(){setExplode(0);reloadFor=1;},
      flash(){setExplode(0);dialTo+=Math.PI/4;spinFor=.65;originalFlash();},
      step(dt){ensureLive();originalStep(dt);spinFor=Math.max(0,spinFor-dt);wheel+=Math.min(40,spinFor*120)*dt;dial+=Math.min(Math.max(0,dialTo-dial),190*Math.PI/180*dt);reloadFor=Math.max(0,reloadFor-dt);poseMechanism({flap:Math.sin(Math.PI*reloadFor)*110*Math.PI/180});},
      model:{id:'collection266-turret',source:url.href,parts:parts.filter(p=>p.entry.name.startsWith('turret.')),groups:Object.fromEntries(Object.entries(owners).filter(([k])=>k.startsWith('turret.')).map(([k,v])=>[k.slice(7),v])),manifest:model},
    });
    Object.defineProperty(turret,'launchSpeed',{get:()=>turret.muzzle.userData.launchSpeed});
    setPose({legMM:300});
    return {group,base,parts,owners,legs,turret,...sensors,setPose,setExplode,dispose,
      setFromQpos(){fail('recorded qpos requires the complete recorded presentation');},
      presentation:{mode:'current',robotId:'collection266',bodySource:url.href,legSource:url.href,turretSource:url.href,nativeSource:NATIVE,collectionSha256:COLLECTION},
      info:{v2:true,heightM:(wheelR+hMax+model.home_bounds_mm[5])*M,hMin,hMax,wheelR,trackMM,homeLegMM:300,homeHeight:(300-hMin)/(hMax-hMin),massKg:null,massSplit:null,deck:null,
        massBasis:'Current collection266 presentation; current mass/COM and physics have not been recomputed.',movingCoverage:model.moving_coverage,limits:model.limits},
    };
  }catch(error){dispose();throw error;}
}
