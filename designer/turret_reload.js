import * as THREE from 'three';
import { ballMesh } from './turret3d.js';

export const RELOAD_SECONDS = 4.6;
export const RELOAD_OPEN_ANGLE = 110 * Math.PI / 180;
const ease = x => { x = THREE.MathUtils.clamp(x, 0, 1); return x*x*(3-2*x); };

/** Pooled cosmetic refill, in the cartridge's tilt frame. Ammo commits belong to
 * the caller; no scene, conversation, camera or physical geometry is replaced. */
export function createReloadEffect(parent, opening) {
  const group = new THREE.Group(), jar = new THREE.Group();
  group.name = 'reload-effect'; group.visible = false; group.add(jar); parent.add(group);
  const plastic = new THREE.MeshPhysicalMaterial({color:0xa4dbea,roughness:.2,transparent:true,opacity:.32,depthWrite:false,side:THREE.DoubleSide});
  const orange = new THREE.MeshStandardMaterial({color:0xf27524,roughness:.5});
  const body = new THREE.Mesh(new THREE.CylinderGeometry(.048,.048,.15,28,1,true),plastic);
  body.position.y = .09;
  const bottom = new THREE.Mesh(new THREE.CylinderGeometry(.05,.05,.009,28),orange); bottom.position.y=.168;
  const mouth = new THREE.Mesh(new THREE.CylinderGeometry(.021,.04,.025,28,1,true),plastic); mouth.position.y=.0125;
  const rim = new THREE.Mesh(new THREE.TorusGeometry(.021,.004,8,28),orange); rim.rotation.x=Math.PI/2;
  const band = new THREE.Mesh(new THREE.CylinderGeometry(.0485,.0485,.04,28,1,true),orange);band.position.y=.092;
  jar.add(body,bottom,mouth,rim,band);
  const jarBalls = Array.from({length:18},(_,i)=>{
    const b=ballMesh().g,a=i*2.4,r=.016+(i%2)*.012;
    b.position.set(Math.cos(a)*r,.04+Math.floor(i/6)*.04,Math.sin(a)*r);jar.add(b);return b;
  });
  const stream = Array.from({length:30},()=>{const b=ballMesh().g;b.visible=false;group.add(b);return b;});
  const mouthAt=opening.clone().add(new THREE.Vector3(0,.085,.012));
  const start=mouthAt.clone().add(new THREE.Vector3(.16,.23,.02));
  const end=opening.clone().add(new THREE.Vector3(0,-.026,0));
  let last={delivered:0,open:0,done:true,phase:'Ready'};
  return {
    group, jar, stream, opening:opening.clone(),
    bounds:new THREE.Box3(opening.clone().add(new THREE.Vector3(-.08,-.04,-.08)),opening.clone().add(new THREE.Vector3(.23,.4,.1))),
    hide(){group.visible=false;stream.forEach(b=>{b.visible=false;});},
    step(elapsed,missing,reduced=false){
      group.visible=true;
      if(reduced){
        jar.position.copy(mouthAt);jar.rotation.z=.3;jar.scale.setScalar(1);
        stream.forEach(b=>{b.visible=false;});
        const delivered=elapsed>=.3?missing:0;
        return last={delivered,open:elapsed<.5?1:0,done:elapsed>=.65,phase:delivered?'Closing flap':'Refilling'};
      }
      const arriving=ease((elapsed-.2)/.8),leaving=ease((elapsed-3.65)/.75),tip=ease((elapsed-.95)/.55);
      jar.position.lerpVectors(start,mouthAt,arriving*(1-leaving));
      jar.rotation.z=THREE.MathUtils.lerp(Math.PI,.3,tip*(1-leaving));
      jar.scale.setScalar(Math.max(.001,ease(elapsed/.35)*(1-leaving)));
      jarBalls.forEach((b,i)=>{b.visible=elapsed<1.6+(i/18)*1.5 || elapsed>3.6;});
      const interval=1.35/Math.max(1,missing-1),flight=.48;
      let delivered=0;
      stream.forEach((b,i)=>{
        const progress=(elapsed-1.6-i*interval)/flight;
        b.visible=i<missing && progress>=0 && progress<1;
        if(i<missing && progress>=1)delivered++;
        if(b.visible){
          b.position.lerpVectors(mouthAt,end,progress*progress);
          b.position.x+=Math.sin(i*2.4)*.003*Math.sin(Math.PI*progress);
          b.rotation.x=progress*5+i;
        }
      });
      const open=ease(elapsed/.55)*(1-ease((elapsed-3.9)/.65));
      return last={delivered,open,done:elapsed>=RELOAD_SECONDS,
        phase:elapsed<.65?'Opening flap':elapsed<1.6?'Jar arriving':elapsed<3.5?'Pouring balls':'Closing flap'};
    },
    get status(){return last;},
  };
}
