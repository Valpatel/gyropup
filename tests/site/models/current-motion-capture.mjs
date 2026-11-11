/** Actual Three-world observations and deliberate graph fault controls; no oracle math. */
export async function installCurrentMotion(reference){
    const s=window.__sim,r=s.state.robot;s.stage.stop();s.state.alive=false;s.sfx.setEnabled(false);s.talk?.stop();
    const deg=180/Math.PI,rad=Math.PI/180,records=reference.component_observations;
    const zero=()=>{r.base.position.set(0,0,0);r.base.quaternion.identity();r.group.position.set(0,0,0);r.group.quaternion.identity();};
    const frame=p=>[p.z*1000,p.x*1000,p.y*1000];
    function meshes(){const result=new Map(r.parts.map(p=>[p.mesh.name,p]));if(result.size!==228)throw Error('Actual complete228 display-part inventory differs');return result;}
    function attached(mesh){for(let p=mesh;p;p=p.parent){if(!p.visible)return false;if(p===r.group)return true;}return false;}
    function observe(id,contract,angles,allowMissing=false){
      r.group.updateWorldMatrix(true,true);const parts=meshes(),components={};
      for(const name of Object.keys(contract.components)){
        if(name.startsWith('helper.')){
          const key=name.slice(7),object=({eyes:r.head,camera_front:r.fov.children[0],headlight_l:r.lights[0].lens,headlight_r:r.lights[1].lens,
            pan:r.owners['turret.pan'],tilt:r.owners['turret.tilt'],muzzle:r.turret.muzzle,laser_origin:r.turret.laserOrigin})[key];
          components[name]=[[0,0,0],[0,0,.001],[.001,0,0],[0,.001,0]].map(p=>frame(object.position.clone().set(...p).applyMatrix4(object.matrixWorld)));continue;
        }
        const part=parts.get(name);if(!part||!attached(part.mesh)){if(allowMissing)continue;throw Error('Actual mesh missing from complete holder: '+name);}
        const pos=part.mesh.geometry.attributes.position;
        components[name]=records[name].vertex_indices.map(i=>frame(part.mesh.position.clone().fromBufferAttribute(pos,i).applyMatrix4(part.mesh.matrixWorld)));
      }
      return{id,angles_deg:angles,components};
    }
    function rigidPose(angles){
      r.setPose({legMM:300});zero();r.turret.poseMechanism({pan:0,tilt:0,pinion:0,dial:0,wheel_l:0,wheel_r:0,flap:0});
      for(const [name,value]of Object.entries(angles))r.owners[name].rotation.x=reference.home_owner_angle_rad[name]+value*rad;
      const actual=Object.fromEntries(Object.entries(angles).map(([name])=>[name,(r.owners[name].rotation.x-reference.home_owner_angle_rad[name])*deg]));
      return actual;
    }
    function livePose(row,angles){
      const p=row.pose;r.setPose({legMM:p.leg_mm,pitch:p.pitch_deg*rad,rollMM:p.roll_mm,wheel:p.wheel_deg*rad});
      // Record and check the known free-body presentation before neutralizing
      // only its position/orientation for assembly-home observations. Scale is
      // never removed, so unit faults remain visible.
      if(Math.abs(r.base.position.y-(127+p.leg_mm)*.001)>1e-10||Math.abs(r.base.rotation.x-p.pitch_deg*rad)>1e-10
        ||Math.abs(r.base.rotation.z-Math.atan2(p.roll_mm,434.0996))>1e-8||r.base.scale.toArray().some(v=>v!==1))throw Error('Live free-body presentation differs from its explicit control pose');
      zero();const a=Object.fromEntries(Object.entries(angles).map(([k,v])=>[k,v*rad]));
      r.turret.poseMechanism({pan:a['turret.pan'],tilt:a['turret.tilt'],pinion:a['turret.pinion'],dial:a['turret.dial'],
        wheel_l:a['turret.wheel_l'],wheel_r:a['turret.wheel_r'],flap:a['turret.flap']});
      r.owners['L.wheel'].rotation.x=p.wheel_deg*rad+a['L.wheel'];r.owners['R.wheel'].rotation.x=-(p.wheel_deg*rad+a['R.wheel']);
      return{'turret.pan':r.owners['turret.pan'].rotation.y*deg,'turret.tilt':-r.owners['turret.tilt'].rotation.x*deg,
        'turret.pinion':r.owners['turret.pinion'].rotation.y*deg,'turret.dial':r.owners['turret.dial'].rotation.y*deg,
        'turret.wheel_l':r.owners['turret.wheel_l'].rotation.y*deg,'turret.wheel_r':-r.owners['turret.wheel_r'].rotation.y*deg,
        'turret.flap':-r.owners['turret.flap'].rotation.x*deg,'L.wheel':r.owners['L.wheel'].rotation.x*deg-p.wheel_deg,'R.wheel':-r.owners['R.wheel'].rotation.x*deg-p.wheel_deg};
    }
    const prefix={schema_version:1,length_unit:'mm',frame:'assembly-home',capture_source:'Actual current source-bound renderer geometry attributes through updated world matrices; explicit body position/orientation normalized, scale retained. Reference '+reference.collection_sha256};
    window.__currentMotion={r,s,reference,observe,rigidPose,livePose,zero,prefix};
    if(r.info.massKg!==null||r.info.movingCoverage.mechanical_ownership_verified!==false)throw Error('Current qualification was promoted');
}

export function captureMotionFaults(){
    const t=window.__currentMotion,r=t.r,ref=t.reference,contract=ref.rigid.contract,poses=ref.rigid.required_poses;
    const homeIndex=poses.findIndex(p=>Object.values(p).every(x=>Math.abs(x)<1e-8));
    const turnedIndex=poses.findIndex(p=>Math.abs(p['L.upper_front'])>20&&Math.abs(p['R.upper_front'])<1e-8);
    if(homeIndex<0||turnedIndex<0)throw Error('Frozen non-home/control pose unavailable');
    const result={};
    function run(name,mutate,homePreserved=true){
      let a=t.rigidPose(poses[homeIndex]);const restore=mutate();
      const home=t.observe('rigid-'+homeIndex,contract,a,true);
      a=t.rigidPose(poses[turnedIndex]);const sample=t.observe('rigid-'+turnedIndex,contract,a,true);
      restore();a=t.rigidPose(poses[homeIndex]);const restored=t.observe('rigid-'+homeIndex,contract,a);
      result[name]={home_preserved:homePreserved,home_index:homeIndex,home,sample_index:turnedIndex,sample,restored_index:homeIndex,restored};
    }
    run('right-rotation',()=>{const g=r.owners['R.module'],q=g.quaternion.clone();g.quaternion.identity();return()=>g.quaternion.copy(q);},false);
    run('wrong-pivot-home-preserved',()=>{const g=r.owners['L.upper_front'],position=g.position.clone(),children=g.children.map(o=>[o,o.position.clone()]);
      g.position.z+=.007;const local=g.position.clone().set(0,0,-.007).applyQuaternion(g.quaternion.clone().invert());for(const [o]of children)o.position.add(local);
      return()=>{g.position.copy(position);for(const [o,p]of children)o.position.copy(p);};});
    run('axis-sign',()=>{
      const g=r.owners['L.upper_front'],parent=g.parent,position=g.position.clone(),children=g.children.map(o=>[o,o.position.clone(),o.quaternion.clone(),o.scale.clone()]);
      const carrier=new g.constructor();carrier.position.copy(position);carrier.rotation.y=Math.PI;parent.add(carrier);carrier.add(g);g.position.set(0,0,0);
      const h=ref.home_owner_angle_rad['L.upper_front'],correction=g.matrix.clone().makeRotationX(-h).multiply(g.matrix.clone().makeRotationY(-Math.PI)).multiply(g.matrix.clone().makeRotationX(h));
      for(const [child]of children)child.applyMatrix4(correction);
      return()=>{parent.add(g);g.position.copy(position);carrier.removeFromParent();for(const [o,p,q,s]of children){o.position.copy(p);o.quaternion.copy(q);o.scale.copy(s);}};
    });
    run('units',()=>{const scale=r.group.scale.clone();r.group.scale.setScalar(1000);return()=>r.group.scale.copy(scale);},false);
    run('lost-parent',()=>{const g=r.owners['L.front_link'],parent=g.parent,pos=g.position.clone(),q=g.quaternion.clone();r.group.updateWorldMatrix(true,true);r.base.attach(g);
      return()=>{parent.add(g);g.position.copy(pos);g.quaternion.copy(q);};});
    run('stationary-owner',()=>{const mesh=r.parts.find(p=>p.mesh.name==='L.motor_front').mesh,parent=mesh.parent,p=mesh.position.clone(),q=mesh.quaternion.clone();r.group.updateWorldMatrix(true,true);r.owners['L.upper_front'].attach(mesh);
      return()=>{parent.add(mesh);mesh.position.copy(p);mesh.quaternion.copy(q);};});
    run('missing-part',()=>{const mesh=r.parts.find(p=>p.mesh.name==='L.motor_front').mesh,parent=mesh.parent;mesh.removeFromParent();return()=>parent.add(mesh);},false);
    return result;
}

export function captureMotionOperation(){
  const t=window.__currentMotion,r=t.r,row=t.reference.live[0],zero=Object.fromEntries(Object.keys(row.contract.joints).map(k=>[k,0]));
  t.livePose(row,zero);r.setExplode(.45);const exploded=r.parts.some(p=>p.mesh.position.length()>.001);r.setExplode(0);
  const samples=[t.observe('operation-reset',row.contract,t.livePose(row,zero))];
  r.turret.flash();r.turret.reload();const deg=180/Math.PI,turn=x=>((x%360)+360)%360;
  for(let i=0;i<90;i++){
    r.turret.step(i===45?0:1/60);
    const raw={'turret.pan':r.owners['turret.pan'].rotation.y*deg,'turret.tilt':-r.owners['turret.tilt'].rotation.x*deg,
      'turret.pinion':r.owners['turret.pinion'].rotation.y*deg,'turret.dial':r.owners['turret.dial'].rotation.y*deg,
      'turret.wheel_l':r.owners['turret.wheel_l'].rotation.y*deg,'turret.wheel_r':-r.owners['turret.wheel_r'].rotation.y*deg,
      'turret.flap':-r.owners['turret.flap'].rotation.x*deg,'L.wheel':0,'R.wheel':0};
    const angles={...raw,'turret.wheel_l':turn(raw['turret.wheel_l']),'turret.wheel_r':turn(raw['turret.wheel_r'])};
    samples.push({...t.observe('operation-'+i,row.contract,angles),raw_angles_deg:raw});
  }
  return{exploded,reset:r.parts.every(p=>p.mesh.position.length()<1e-12),flapClosed:Math.abs(r.owners['turret.flap'].rotation.x)<1e-12,
    trace:{...t.prefix,samples},limits:'Actual display operation/stop-start snapshots; no force, timing or ballistic qualification.'};
}
