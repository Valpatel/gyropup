/** Product overlays around the existing shared stage; no second renderer. */
import * as THREE from 'three';
import {buildRobotV2} from '../robot_v2.js';
export function createWorkspace(host,getActive,paint,report){
 const layout=host.querySelector('.assembly-layout'),tree=host.querySelector('#assembly-explorer'),tools=host.querySelector('#assembly-tools');
 let disposed=false,generation=0,previousOverflow='',assemblyLoader=null,expandedInstructions=false;
 const instructionToggle=host.querySelector('[data-instructions-toggle]');
 function instructionState(){const panelOpen=!tree.hidden||!tools.hidden;layout.dataset.instructions=panelOpen?'collapsed':expandedInstructions?'expanded':'normal';instructionToggle.setAttribute('aria-expanded',String(!panelOpen&&expandedInstructions));instructionToggle.textContent=panelOpen?'Show instructions ↓':expandedInstructions?'Collapse ↙':'Expand ↗';}
 instructionToggle.onclick=()=>{if(!tree.hidden||!tools.hidden){panels(tree,false);panels(tools,false);}else expandedInstructions=!expandedInstructions;instructionState();frame();};
 const full=host.querySelector('[data-guide-fullscreen]');
 function fullState(){const native=document.fullscreenElement===layout,expanded=layout.dataset.expanded==='true',on=native||expanded;layout.dataset.fullscreen=native?'native':expanded?'expanded':'none';full.setAttribute('aria-pressed',String(on));full.setAttribute('aria-label',on?'Exit full screen':'Enter full screen');full.title=on?'Exit full screen':'Enter full screen';requestAnimationFrame(frame);}
 function collapse(){layout.dataset.expanded='false';document.body.style.overflow=previousOverflow;fullState();}
 full.onclick=async()=>{if(document.fullscreenElement===layout){try{await document.exitFullscreen();}catch{report('Use Escape to leave full screen.');}return;}if(layout.dataset.expanded==='true'){collapse();return;}try{if(!layout.requestFullscreen)throw new Error('Unavailable');await layout.requestFullscreen();}catch{previousOverflow=document.body.style.overflow;document.body.style.overflow='hidden';layout.dataset.expanded='true';report('Fullscreen is unavailable here. Expanded workspace enabled; press Escape to close.');fullState();}};
 document.addEventListener('fullscreenchange',fullState);
 function panels(panel,open){panel.hidden=!open;host.querySelector(panel===tree?'[data-explorer-toggle]':'[data-tools-toggle]').setAttribute('aria-expanded',String(open));if(open){const other=panel===tree?tools:tree;other.hidden=true;host.querySelector(panel===tree?'[data-tools-toggle]':'[data-explorer-toggle]').setAttribute('aria-expanded','false');}instructionState();frame();}
 for(const [selector,panel]of [['[data-explorer-toggle]',tree],['[data-tools-toggle]',tools]])host.querySelector(selector).onclick=()=>panels(panel,panel.hidden);
 host.querySelector('[data-explorer-close]').onclick=()=>panels(tree,false);host.querySelector('[data-tools-close]').onclick=()=>panels(tools,false);
 host.querySelector('[data-guide-fit]').onclick=()=>frame();for(const button of host.querySelectorAll('[data-assembly]'))button.onclick=()=>choose(button.dataset.assembly);
 host.addEventListener('keydown',e=>{if(e.key==='Escape'){if(layout.dataset.expanded==='true')collapse();if(document.fullscreenElement===layout)document.exitFullscreen().catch(()=>{});panels(tree,false);panels(tools,false);host.querySelector('[data-explorer-toggle]').focus();}});
 function frame(){const a=getActive();if(!a?.viewer)return;const stage=a.viewer.stage,r=layout.getBoundingClientRect();const topbar=host.querySelector('.assembly-topbar').getBoundingClientRect();layout.style.setProperty('--assembly-toolbar-bottom',`${topbar.bottom-r.top}px`);const nav=host.querySelector('.assembly-nav').getBoundingClientRect();layout.style.setProperty('--assembly-nav-bottom',`${nav.bottom-r.top}px`);const card=host.querySelector('.assembly-step').getBoundingClientRect();layout.style.setProperty('--assembly-card-height',`${card.height}px`);const inset={top:nav.bottom-r.top+12,bottom:r.bottom-card.top+12,left:12,right:12};
  for(const panel of [tree,tools])if(!panel.hidden){const p=panel.getBoundingClientRect();if(panel===tree)inset.left=p.right-r.left+16;else inset.right=r.right-p.left+16;}
  stage.setInsets(inset);
  if(a.overview&&a.robot){a.robot.group.updateMatrixWorld(true);const bounds=new THREE.Box3();a.robot.group.traverseVisible(object=>{if(object.isMesh)bounds.union(new THREE.Box3().setFromObject(object));});stage.fitView(bounds,{direction:new THREE.Vector3(1,.45,1.5),margin:1.12});}
  else if(!a.overview)a.viewer.frameParts(a.isolate&&a.selected?[a.selected]:undefined,a.guide.steps.find(s=>s.id===a.step)?.camera?.direction);
 }
 function present(){const a=getActive();if(!a)return;layout.dataset.overview=String(!!a.overview);for(const button of host.querySelectorAll('[data-assembly]'))button.setAttribute('aria-pressed',String(button.dataset.assembly===(a.overview?a.assembly:a.guideAssembly||'turret')));host.querySelector('[data-context-tools]').hidden=!a.overview;host.querySelector('[data-step-tools]').hidden=!!a.overview;
  for(const child of a.viewer?.stage.root.children||[])child.visible=child===a.robot?.group?!!a.overview:!a.overview;
  host.querySelector('[data-guide-step-detail]').hidden=!!a.overview;host.querySelector('.assembly-progress').hidden=!!a.overview;
  if(a.robot)a.robot.turret.group.visible=a.assembly!=='robot';
  if(a.overview){const jump=host.querySelector('[data-guide-step]');jump.replaceChildren(new Option('Overview','overview'));jump.disabled=true;host.querySelector('[data-guide-count]').textContent=`GYROPUP / ${a.assembly==='robot'?'ROBOT':'COMBINED'} / CURRENT WIP`;host.querySelector('[data-guide-title]').textContent=a.assembly==='robot'?'Robot · body & legs':'Combined · robot & turret';host.querySelector('[data-guide-text]').textContent=a.assembly==='robot'?'The interim playground body and both five-bar legs, with the turret hidden. This reference model retains the playground’s mirrored leg presentation; source-bound installation stages are separate.':'The existing playground model with its correctly mounted current turret. This is robot context; choose Turret for the separate twelve-step bench walkthrough.';const prev=host.querySelector('[data-guide-prev]'),next=host.querySelector('[data-guide-next]');prev.disabled=true;next.disabled=true;next.title='This reference overview has no authored steps';}
  frame();
 }
 function choose(id,navigate=true){const a=getActive();if(!a)return;if(navigate){const url=new URL(location.href);url.searchParams.set('assembly',id);if(id!=='turret'){url.searchParams.delete('step');url.searchParams.delete('chapter');}history.pushState(null,'',url);}if(assemblyLoader?.(id,navigate))return;if(id==='turret'){step(a.step);return;}a.assembly=id;overview();}
 function step(id){const a=getActive();if(!a)return;a.wantsOverview=false;a.overview=false;paint(id);present();if(innerWidth<=760)panels(tree,false);}
 async function overview(){const a=getActive();if(!a?.viewer){report('Interactive robot context is unavailable. The bound turret instructions remain available.',true);return;}a.assembly=a.assembly||'combined';a.wantsOverview=true;
  const show=()=>{a.overview=true;const url=new URL(location.href);url.searchParams.delete('step');url.searchParams.delete('chapter');url.searchParams.set('assembly',a.assembly);history.replaceState(null,'',url);present();report('Current WIP model · orbit to explore. Choose Turret for the authored walkthrough.');};
  if(a.robot){show();return;}if(a.robotLoading)return;const own=generation;a.robotLoading=true;report('Loading the full robot; the working turret guide remains available…');
  try{const robot=await buildRobotV2('../');if(disposed||own!==generation||getActive()!==a){disposeRobot(robot);return;}a.robot=robot;a.viewer.stage.root.add(robot.group);robot.group.visible=false;if(a.wantsOverview)show();}
  catch(error){if(getActive()!==a||disposed)return;a.overview=false;paint(a.step);present();report('Robot context could not load: '+error.message+'. The bound turret guide remains available; choose Robot or Combined to retry.',true);host.querySelector('[data-guide-retry]').hidden=true;}
  finally{a.robotLoading=false;}
 }

 const resize=()=>requestAnimationFrame(()=>{if(!disposed)frame();});window.addEventListener('resize',resize);const observer=new ResizeObserver(resize);observer.observe(layout);
 return {frame,present,step,overview,choose,setNavigation(handler){assemblyLoader=handler;},invalidate(){++generation;},dispose(){if(layout.dataset.expanded==='true')collapse();document.removeEventListener('fullscreenchange',fullState);disposed=true;++generation;observer.disconnect();window.removeEventListener('resize',resize);}};
}
export function disposeRobot(robot){if(!robot)return;robot.group.removeFromParent();const geometries=new Set(),materials=new Set();robot.group.traverse(o=>{if(o.geometry)geometries.add(o.geometry);for(const m of Array.isArray(o.material)?o.material:o.material?[o.material]:[])materials.add(m);});for(const g of geometries)g.dispose();for(const m of materials)m.dispose();}
