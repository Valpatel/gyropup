/** Product overlays around the existing shared stage; no second renderer. */
import * as THREE from 'three';
import {buildRobotV2} from '../robot_v2.js';
export function createWorkspace(host,getActive,paint,report){
 const layout=host.querySelector('.assembly-layout'),tree=host.querySelector('#assembly-explorer'),tools=host.querySelector('#assembly-tools');
 let disposed=false,generation=0;
 function panels(panel,open){panel.hidden=!open;host.querySelector(panel===tree?'[data-explorer-toggle]':'[data-tools-toggle]').setAttribute('aria-expanded',String(open));if(open){const other=panel===tree?tools:tree;other.hidden=true;host.querySelector(panel===tree?'[data-tools-toggle]':'[data-explorer-toggle]').setAttribute('aria-expanded','false');}frame();}
 for(const [selector,panel]of [['[data-explorer-toggle]',tree],['[data-tools-toggle]',tools]])host.querySelector(selector).onclick=()=>panels(panel,panel.hidden);
 host.querySelector('[data-explorer-close]').onclick=()=>panels(tree,false);host.querySelector('[data-tools-close]').onclick=()=>panels(tools,false);
 host.querySelector('[data-guide-fit]').onclick=()=>frame();for(const button of host.querySelectorAll('[data-assembly]'))button.onclick=()=>choose(button.dataset.assembly);host.querySelector('[data-tree-robot]').onclick=()=>choose('robot');host.querySelector('[data-tree-combined]').onclick=()=>choose('combined');
 host.addEventListener('keydown',e=>{if(e.key==='Escape'){panels(tree,false);panels(tools,false);host.querySelector('[data-explorer-toggle]').focus();}});
 function frame(){const a=getActive();if(!a?.viewer)return;const stage=a.viewer.stage,r=layout.getBoundingClientRect(),card=host.querySelector('.assembly-step').getBoundingClientRect();const topbar=host.querySelector('.assembly-topbar').getBoundingClientRect();const inset={top:topbar.bottom-r.top+12,bottom:r.bottom-card.top+12,left:12,right:12};
  for(const panel of [tree,tools])if(!panel.hidden){const p=panel.getBoundingClientRect();if(r.width<=760)inset.top=Math.max(inset.top,p.bottom-r.top+12);else if(panel===tree)inset.left=p.right-r.left+16;else inset.right=r.right-p.left+16;}
  stage.setInsets(inset);
  if(a.overview&&a.robot){a.robot.group.updateMatrixWorld(true);stage.fitView(new THREE.Box3().setFromObject(a.robot.group),{direction:new THREE.Vector3(1,.45,1.5),margin:1.12});}
  else if(!a.overview)a.viewer.frameParts(a.isolate&&a.selected?[a.selected]:undefined,a.guide.steps.find(s=>s.id===a.step)?.camera?.direction);
 }
 function present(){const a=getActive();if(!a)return;layout.dataset.overview=String(!!a.overview);for(const button of host.querySelectorAll('[data-assembly]'))button.setAttribute('aria-pressed',String(button.dataset.assembly===(a.overview?a.assembly:'turret')));host.querySelector('[data-context-tools]').hidden=!a.overview;host.querySelector('[data-step-tools]').hidden=!!a.overview;
  for(const child of a.viewer?.stage.root.children||[])child.visible=child===a.robot?.group?!!a.overview:!a.overview;
  host.querySelector('[data-guide-step-detail]').hidden=!!a.overview;host.querySelector('.assembly-progress').hidden=!!a.overview;
  if(a.robot)a.robot.turret.group.visible=a.assembly!=='robot';
  if(a.overview){host.querySelector('[data-guide-count]').textContent=`GYROPUP / ${a.assembly==='robot'?'ROBOT':'COMBINED'} / CURRENT WIP`;host.querySelector('[data-guide-title]').textContent=a.assembly==='robot'?'Robot · body & legs':'Combined · robot & turret';host.querySelector('[data-guide-text]').textContent=a.assembly==='robot'?'The committed playground body and both five-bar legs, with the turret hidden. This assembly currently has a model overview; authored body and leg build steps are not published.':'The existing playground model with its correctly mounted current turret. This is robot context; choose Turret for the separate twelve-step bench walkthrough.';const prev=host.querySelector('[data-guide-prev]'),next=host.querySelector('[data-guide-next]');prev.disabled=true;next.disabled=false;next.onclick=()=>step(a.guide.steps[0].id);}
  frame();
 }
 function choose(id){const a=getActive();if(!a)return;if(id==='turret'){step(a.step);return;}a.assembly=id;overview();}
 function step(id){const a=getActive();if(!a)return;a.wantsOverview=false;a.overview=false;paint(id);present();if(innerWidth<=760)panels(tree,false);}
 async function overview(){const a=getActive();if(!a?.viewer){report('Interactive robot context is unavailable. The bound turret instructions remain available.',true);return;}a.assembly=a.assembly||'combined';a.wantsOverview=true;
  const show=()=>{a.overview=true;const url=new URL(location.href);url.searchParams.delete('step');url.searchParams.delete('chapter');url.searchParams.set('assembly',a.assembly);history.replaceState(null,'',url);present();report('Current playground WIP context. Robot/Combined source: exports/sim/v2/rig/manifest.json; mounted turret: exports/sim/turret_box/manifest.json.');};
  if(a.robot){show();return;}if(a.robotLoading)return;const own=generation;a.robotLoading=true;report('Loading the full robot; the working turret guide remains available…');
  try{const robot=await buildRobotV2('../');if(disposed||own!==generation||getActive()!==a){disposeRobot(robot);return;}a.robot=robot;a.viewer.stage.root.add(robot.group);robot.group.visible=false;if(a.wantsOverview)show();}
  catch(error){if(getActive()!==a||disposed)return;a.overview=false;paint(a.step);present();report('Robot context could not load: '+error.message+'. The bound turret guide remains available; choose Robot or Combined to retry.',true);}
  finally{a.robotLoading=false;}
 }

 const resize=()=>requestAnimationFrame(()=>{if(!disposed)frame();});window.addEventListener('resize',resize);const observer=new ResizeObserver(resize);observer.observe(layout);
 return {frame,present,step,overview,choose,invalidate(){++generation;},dispose(){disposed=true;++generation;observer.disconnect();window.removeEventListener('resize',resize);}};
}
export function disposeRobot(robot){if(!robot)return;robot.group.removeFromParent();const geometries=new Set(),materials=new Set();robot.group.traverse(o=>{if(o.geometry)geometries.add(o.geometry);for(const m of Array.isArray(o.material)?o.material:o.material?[o.material]:[])materials.add(m);});for(const g of geometries)g.dispose();for(const m of materials)m.dispose();}
