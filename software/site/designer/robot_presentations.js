// Complete current/recorded Gyropup holders. Geometry, pose metadata, sensors
// and effect anchors commit together; only the archived holder loads lazily.
import * as THREE from 'three';

export function composeRobotPresentations(current,loadRecorded,{signal}={}){
  const group=new THREE.Group(),laser=new THREE.Group(),lifetime=new AbortController();
  group.add(current.group);laser.add(current.turret.laser);laser.visible=false;
  let active=current,recorded=null,loading=null,request=0,disposed=false,currentPlacement=null;
  const ensureLive=()=>{if(disposed)throw new Error('Robot presentation is disposed');};
  const placement=()=>({position:group.position.clone(),quaternion:group.quaternion.clone(),scale:group.scale.clone()});
  const applyPlacement=value=>{group.position.copy(value.position);group.quaternion.copy(value.quaternion);group.scale.copy(value.scale);};
  function commit(next){
    ensureLive();if(next===active)return;
    const previous=active,showFov=previous.fov.visible,attached=previous.turret.group.visible;
    const lights=previous.lights.map(p=>({visible:p.spot.visible,emissive:p.lens.material.emissiveIntensity,intensity:p.spot.intensity}));
    previous.setExplode(0);next.setExplode(0);
    if(previous===current){currentPlacement=placement();group.position.set(0,0,0);group.quaternion.identity();group.scale.set(1,1,1);}
    else if(next===current&&currentPlacement)applyPlacement(currentPlacement);
    previous.group.visible=false;previous.turret.laser.visible=false;
    if(!next.group.parent)group.add(next.group);
    if(!next.turret.laser.parent)laser.add(next.turret.laser);
    next.fov.visible=showFov;next.turret.group.visible=attached;
    next.lights.forEach((p,i)=>{const state=lights[i];if(state){p.spot.visible=state.visible;p.spot.intensity=state.intensity;p.lens.material.emissiveIntensity=state.emissive;}});
    next.group.visible=true;next.turret.laser.visible=false;laser.visible=false;active=next;
  }
  async function recordedHolder(){
    if(recorded)return recorded;
    if(!loading)loading=(async()=>{
      const candidate=await loadRecorded({signal:lifetime.signal});
      if(disposed){candidate.dispose();throw new Error('Robot presentation was disposed during recorded loading');}
      // A completed stale request can be cached off-scene. It may never attach
      // or mutate current metadata until a still-current selection commits it.
      candidate.group.visible=false;candidate.turret.laser.visible=false;recorded=candidate;return candidate;
    })().catch(error=>{loading=null;throw error;});
    return loading;
  }
  async function setPresentation(mode='current'){
    ensureLive();if(mode!=='current'&&mode!=='recorded')throw new Error('Unknown robot presentation: '+mode);
    const generation=++request;
    if(mode==='current'){commit(current);return;}
    const next=await recordedHolder();if(!disposed&&generation===request)commit(next);
  }
  function dispose(){
    if(disposed)return;disposed=true;++request;lifetime.abort();
    signal?.removeEventListener('abort',dispose);
    group.removeFromParent();laser.removeFromParent();current.dispose();recorded?.dispose();group.clear();laser.clear();
  }
  signal?.addEventListener('abort',dispose,{once:true});if(signal?.aborted)dispose();
  // Pages retain this effect API and its one laser scene attachment across mode
  // switches. All other values/methods resolve on the fully committed holder.
  const turret=new Proxy({}, {get(_target,key){
    if(key==='laser')return laser;
    if(key==='updateLaser')return(...args)=>{
      ensureLive();for(const holder of [current,recorded])if(holder&&holder!==active)holder.turret.laser.visible=false;
      active.turret.updateLaser(...args);
      // Pages hide this stable stage attachment during bench/model changes.
      // Restore the same public visibility semantics as the single laser API.
      laser.visible=active.turret.laser.visible;
    };
    ensureLive();const value=active.turret[key];return typeof value==='function'?value.bind(active.turret):value;
  }});
  const result={group,turret,setPresentation,dispose,
    setPose(pose){ensureLive();if(active!==current)throw new Error('Live pose requires the current robot presentation');return current.setPose(pose);},
    setFromQpos(q,layout){ensureLive();if(active!==recorded)throw new Error('Recorded qpos requires the complete recorded robot presentation');return recorded.setFromQpos(q,layout);},
    setExplode(value){ensureLive();active.setExplode(value);},
  };
  for(const key of ['base','head','lights','fov','legs','parts','owners','legHardware','info','presentation'])Object.defineProperty(result,key,{get(){ensureLive();return active[key];}});
  return result;
}
