/** Product docking and context around the existing guide stage; never another renderer. */
import * as THREE from 'three';
import {buildRobotV2} from '../robot_v2.js';
export function createWorkspace(host,getActive,paint,report){
 const required=selector=>{const node=host.querySelector(selector);if(!node)throw new Error('Missing workspace element: '+selector);return node;};
 const layout=required('.assembly-layout'),tree=required('#assembly-explorer'),tools=required('#assembly-tools'),instructions=required('.assembly-step'),sheet=required('[data-workspace-sheet]');
 const toolbar=required('.assembly-topbar'),nav=required('.assembly-nav'),full=required('[data-guide-fullscreen]'),instructionToggle=required('[data-instructions-toggle]');
 const mobile=matchMedia('(max-width:1000px)'),events=new AbortController();
 let disposed=false,generation=0,assemblyLoader=null,previousOverflow='',expandedInstructions=false,partsOpen=false,toolsOpen=false,pane='instructions',sheetCollapsed=false,sheetExpanded=false,framePending=false;
 const useSheet=()=>mobile.matches||!!getActive()&&!getActive().viewer;
 function renderPanels(){
  layout.dataset.mobile=String(useSheet());layout.dataset.instructions=expandedInstructions?'expanded':'normal';layout.dataset.tools=String(toolsOpen);layout.dataset.parts=String(partsOpen);layout.dataset.sheetSize=sheetCollapsed?'collapsed':sheetExpanded?'expanded':'normal';
  if(useSheet()){tree.hidden=pane!=='parts'||sheetCollapsed;tools.hidden=pane!=='tools'||sheetCollapsed;instructions.hidden=pane!=='instructions'||sheetCollapsed;}
  else{tree.hidden=!partsOpen;tools.hidden=!toolsOpen;instructions.hidden=false;}
  required('[data-explorer-toggle]').setAttribute('aria-expanded',String(useSheet()?pane==='parts'&&!sheetCollapsed:partsOpen));required('[data-tools-toggle]').setAttribute('aria-expanded',String(useSheet()?pane==='tools'&&!sheetCollapsed:toolsOpen));
  instructionToggle.setAttribute('aria-expanded',String(expandedInstructions));instructionToggle.textContent=expandedInstructions?'Collapse ↙':'Expand ↗';
  for(const button of host.querySelectorAll('[data-sheet-tab]'))button.setAttribute('aria-pressed',String(button.dataset.sheetTab===pane));
  const size=required('[data-sheet-size]');size.setAttribute('aria-label',sheetExpanded&&!sheetCollapsed?'Reduce panel':'Expand panel');size.title=size.getAttribute('aria-label');size.textContent=sheetExpanded&&!sheetCollapsed?'↙':'↗';
 }
 function panels(which,open){if(useSheet()){pane=which===tree?'parts':'tools';sheetCollapsed=!open;}else if(which===tree)partsOpen=open;else toolsOpen=open;renderPanels();frame();}
 function selectPane(id){pane=id;sheetCollapsed=false;renderPanels();frame();}
 required('[data-explorer-toggle]').onclick=()=>panels(tree,useSheet()?pane!=='parts'||sheetCollapsed:!partsOpen);
 required('[data-tools-toggle]').onclick=()=>panels(tools,useSheet()?pane!=='tools'||sheetCollapsed:!toolsOpen);
 required('[data-explorer-close]').onclick=()=>panels(tree,false);required('[data-tools-close]').onclick=()=>panels(tools,false);
 for(const button of host.querySelectorAll('[data-sheet-tab]'))button.onclick=()=>selectPane(button.dataset.sheetTab);
 required('[data-sheet-size]').onclick=()=>{sheetCollapsed=false;sheetExpanded=!sheetExpanded;renderPanels();frame();};
 required('[data-sheet-close]').onclick=()=>{sheetCollapsed=true;renderPanels();frame();};
 instructionToggle.onclick=()=>{expandedInstructions=!expandedInstructions;renderPanels();frame();};
 required('[data-guide-fit]').onclick=()=>frame();
 for(const button of host.querySelectorAll('[data-assembly]'))button.onclick=()=>choose(button.dataset.assembly);
 function fullState(){const native=document.fullscreenElement===layout,expanded=layout.dataset.expanded==='true',on=native||expanded;layout.dataset.fullscreen=native?'native':expanded?'expanded':'none';full.setAttribute('aria-pressed',String(on));full.setAttribute('aria-label',on?'Exit full screen':'Enter full screen');full.title=full.getAttribute('aria-label');scheduleFrame();}
 function collapseFullscreen(){layout.dataset.expanded='false';document.body.style.overflow=previousOverflow;fullState();}
 full.onclick=async()=>{if(document.fullscreenElement===layout){try{await document.exitFullscreen();}catch{report('Use Escape to leave full screen.');}return;}if(layout.dataset.expanded==='true'){collapseFullscreen();return;}try{if(!layout.requestFullscreen)throw new Error('Unavailable');await layout.requestFullscreen();}catch{previousOverflow=document.body.style.overflow;document.body.style.overflow='hidden';layout.dataset.expanded='true';report('Fullscreen is unavailable here. Expanded workspace enabled; press Escape to close.');fullState();}};
 document.addEventListener('fullscreenchange',fullState,{signal:events.signal});
 host.addEventListener('keydown',event=>{if(event.key!=='Escape')return;if(layout.dataset.expanded==='true')collapseFullscreen();if(document.fullscreenElement===layout)document.exitFullscreen().catch(()=>{});if(useSheet()){if(getActive()?.viewer)sheetCollapsed=true;else{pane='instructions';sheetCollapsed=false;}}else{partsOpen=false;toolsOpen=false;}renderPanels();frame();},{signal:events.signal});
 host.addEventListener('gyropup:part-selected',()=>{if(mobile.matches){pane='parts';sheetCollapsed=false;sheetExpanded=true;renderPanels();frame();}},{signal:events.signal});
 function frame(){
  const active=getActive(),viewer=active?.viewer;if(!viewer)return;
  const bounds=layout.getBoundingClientRect(),top=toolbar.getBoundingClientRect();layout.style.setProperty('--assembly-toolbar-bottom',`${top.bottom-bounds.top}px`);
  const navigation=nav.getBoundingClientRect();layout.style.setProperty('--assembly-nav-bottom',`${navigation.bottom-bounds.top}px`);
  const insets={top:navigation.bottom-bounds.top+12,bottom:16,left:16,right:16};
  if(mobile.matches){const occupied=sheet.getBoundingClientRect();insets.bottom=Math.max(16,bounds.bottom-occupied.top+12);layout.style.setProperty('--assembly-sheet-height',`${occupied.height}px`);}
  else{
   layout.style.setProperty('--assembly-left-dock',partsOpen?'278px':'0px');layout.style.setProperty('--assembly-right-dock',toolsOpen?'278px':'0px');
   if(partsOpen)insets.left=tree.getBoundingClientRect().right-bounds.left+12;
   if(toolsOpen)insets.right=bounds.right-tools.getBoundingClientRect().left+12;
   const instructionBounds=instructions.getBoundingClientRect();if(expandedInstructions)insets.right=Math.max(insets.right,bounds.right-instructionBounds.left+12);else insets.bottom=Math.max(16,bounds.bottom-instructionBounds.top+12);
  }
  viewer.stage.setInsets(insets);
  if(active.overview&&active.robot){active.robot.group.updateMatrixWorld(true);const box=new THREE.Box3();active.robot.group.traverseVisible(object=>{if(object.isMesh)box.union(new THREE.Box3().setFromObject(object));});viewer.stage.fitView(box,{direction:new THREE.Vector3(1,.45,1.5),margin:1.12});}
  else if(!active.overview)viewer.frameParts(active.isolate&&active.selected?[active.selected]:undefined,active.guide.steps.find(step=>step.id===active.step)?.camera?.direction);
 }
 function scheduleFrame(){if(framePending||disposed)return;framePending=true;requestAnimationFrame(()=>{framePending=false;if(!disposed)frame();});}
 function present(){
  const active=getActive();if(!active)return;layout.dataset.overview=String(!!active.overview);renderPanels();
  for(const button of host.querySelectorAll('[data-assembly]'))button.setAttribute('aria-pressed',String(button.dataset.assembly===(active.overview?active.assembly:active.guideAssembly||'turret')));
  required('[data-context-tools]').hidden=!!active.viewer&&!active.overview;required('[data-step-tools]').hidden=!!active.overview||!active.viewer;required('[data-guide-fit]').disabled=!active.viewer;
  if(!active.viewer)required('[data-context-tools]').textContent='Interactive 3D tools are unavailable. The bound instructions and available diagrams remain accessible.';
  else required('[data-context-tools]').textContent='Orbit and zoom this interim reference model. Source-bound assembly guides expose the assembly tools.';
  for(const child of active.viewer?.stage.root.children||[])child.visible=child===active.robot?.group?!!active.overview:!active.overview;
  required('.assembly-progress').hidden=!!active.overview;if(active.robot)active.robot.turret.group.visible=active.assembly!=='robot';
  if(active.overview){const jump=required('[data-guide-step]');jump.replaceChildren(new Option('Overview','overview'));jump.disabled=true;required('[data-guide-count]').textContent=`GYROPUP / ${active.assembly==='robot'?'ROBOT':'COMBINED'} / CURRENT WIP`;required('[data-guide-title]').textContent=active.assembly==='robot'?'Robot · body & legs':'Combined · robot & turret';required('[data-guide-text]').textContent=active.assembly==='robot'?'Explore the body and both five-bar legs. This interim reference retains the playground’s mirrored leg presentation.':'Explore the body, both legs and mounted turret. Choose an authored guide to follow its installation sequence.';required('[data-guide-prev]').disabled=true;required('[data-guide-next]').disabled=true;required('[data-guide-next]').title='This reference overview has no authored steps';}
  frame();
 }
 function choose(id,navigate=true){const active=getActive();if(!active)return;if(navigate){const url=new URL(location.href);url.searchParams.set('assembly',id);if(id!=='turret'){url.searchParams.delete('step');url.searchParams.delete('chapter');}history.pushState(null,'',url);}if(assemblyLoader?.(id,navigate))return;if(id==='turret'){step(active.step);return;}active.assembly=id;overview();}
 function step(id){const active=getActive();if(!active)return;active.wantsOverview=false;active.overview=false;paint(id);present();report('Assembly guide ready. Current step retained.');}
 async function overview(){
  const active=getActive();if(!active?.viewer){report('Interactive robot context is unavailable. The bound guide remains available.',true);return;}active.assembly=active.assembly||'combined';active.wantsOverview=true;
  const show=()=>{active.overview=true;const url=new URL(location.href);url.searchParams.delete('step');url.searchParams.delete('chapter');url.searchParams.set('assembly',active.assembly);history.replaceState(null,'',url);present();report('Current WIP reference model · orbit to explore.');};
  if(active.robot){show();return;}if(active.robotLoading)return;const own=generation;active.robotLoading=true;report('Loading the interim robot reference; the working guide remains available…');
  try{const robot=await buildRobotV2('../');if(disposed||own!==generation||getActive()!==active){disposeRobot(robot);return;}active.robot=robot;active.viewer.stage.root.add(robot.group);robot.group.visible=false;if(active.wantsOverview)show();else report('Assembly guide ready. Current step retained.');}
  catch(error){if(getActive()!==active||disposed)return;active.overview=false;paint(active.step);present();report('Robot context could not load: '+error.message+'. The bound guide remains available; choose Robot or Combined to retry.',true);required('[data-guide-retry]').hidden=true;}
  finally{active.robotLoading=false;}
 }
 const observer=new ResizeObserver(scheduleFrame);observer.observe(layout);observer.observe(toolbar);observer.observe(sheet);window.addEventListener('resize',()=>{renderPanels();scheduleFrame();},{signal:events.signal});mobile.addEventListener('change',()=>{renderPanels();scheduleFrame();},{signal:events.signal});renderPanels();
 return{frame,present,step,overview,choose,setNavigation(handler){assemblyLoader=handler;},invalidate(){++generation;},dispose(){if(layout.dataset.expanded==='true')collapseFullscreen();disposed=true;++generation;events.abort();observer.disconnect();}};
}
export function disposeRobot(robot){if(!robot)return;robot.group.removeFromParent();const geometries=new Set(),materials=new Set();robot.group.traverse(object=>{if(object.geometry)geometries.add(object.geometry);for(const material of Array.isArray(object.material)?object.material:object.material?[object.material]:[])materials.add(material);});for(const geometry of geometries)geometry.dispose();for(const material of materials)material.dispose();}
