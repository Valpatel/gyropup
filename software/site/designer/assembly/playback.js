/** Product controls for the shared guide player; ticks come only from the existing stage. */
import {canCompleteStep} from './state.js';
import {createGuidePlayback} from '../kit/assembly/guide.js';
export function mountPlayback(host,active,isCurrent,onStep){
 const button=host.querySelector('button[data-guide-play]'),loop=host.querySelector('button[data-guide-loop]'),speed=host.querySelector('[data-guide-speed]'),status=host.querySelector('[data-playback-status]');
 const events=new AbortController(),motion=matchMedia('(prefers-reduced-motion: reduce)');let unsubscribe=()=>{},player=null,disposed=false;
 function writeText(node,value){if(node.textContent===value)return;const leaf=node.firstChild;if(leaf?.nodeType===3&&!leaf.nextSibling)leaf.nodeValue=value;else node.textContent=value;}
 function render(state){
  if(disposed||!isCurrent())return;
  const playing=state?.status==='playing',disabled=!player||active.overview||motion.matches||document.hidden,label=playing?'Pause assembly':'Play assembly',pressed=String(playing),verb=playing?'Pause':'Play',looped=String(state?.loop||false),loopText=state?.loop?'Loop on':'Loop off',speedValue=String(state?.speed||1);
  // A pause is observed during pointerdown. Rewriting unchanged native controls here can scroll their pane before click.
  if(button.disabled!==disabled)button.disabled=disabled;
  if(button.getAttribute('aria-label')!==label)button.setAttribute('aria-label',label);
  if(button.title!==label)button.title=label;
  if(button.getAttribute('aria-pressed')!==pressed)button.setAttribute('aria-pressed',pressed);
  writeText(button.querySelector('span'),verb);const shape=playing?'M8 5v14m8-14v14':'m8 5 11 7-11 7Z',path=button.querySelector('svg path');if(path){if(path.getAttribute('d')!==shape)path.setAttribute('d',shape);}else button.querySelector('svg').innerHTML=`<path d="${shape}"/>`;
  if(loop.disabled!==!player)loop.disabled=!player;
  if(speed.disabled!==!player)speed.disabled=!player;
  if(loop.getAttribute('aria-pressed')!==looped)loop.setAttribute('aria-pressed',looped);
  writeText(loop,loopText);
  if(speed.value!==speedValue)speed.value=speedValue;
  const message=active.overview?'This interim reference supports orbit and zoom. Choose an authored guide for assembly playback.':motion.matches?'Animation is stopped for reduced motion. Use the step controls for static instructions.':!player?'This snapshot has no verified installation order. Manual steps remain available.':state.status==='ended'?'Assembly playback finished. Play starts again; completion checkboxes remain yours.':state.status==='idle'?'Play installs one authored model instance at a time. Completion checkboxes remain yours.':`${playing?'Installing':'Paused'}: ${state.partId} · ${Math.round(state.progress*100)}%`;
  writeText(status,message);
 }

 try{const references=active.guide.steps.filter(step=>!canCompleteStep(active.guide,step.id)).map(step=>step.id),order=Object.fromEntries(Object.entries(active.guide.source?.install_order_by_step||{}).filter(([id])=>!references.includes(id)));player=createGuidePlayback(active.controller,{installOrderByStep:order,referenceStepIDs:references,durationMs:1100,onState:render,onStep:(id,operation)=>{if(isCurrent())onStep(id,operation);}});unsubscribe=active.viewer.stage.onFrame((_t,dt)=>{if(!disposed&&isCurrent())player.tick(dt);});}
 catch(error){status.dataset.error=error.message;}
 const pause=()=>{player?.pause();render(player?.getState());};
 button.addEventListener('click',()=>{if(!player||active.overview||motion.matches||document.hidden)return;if(player.getState().status==='playing')player.pause();else{active.selected=null;active.isolate=false;active.partModes={};player.play();}render(player.getState());},{signal:events.signal});
 loop.addEventListener('click',()=>player?.setLoop(!player.getState().loop),{signal:events.signal});speed.addEventListener('change',()=>player?.setSpeed(Number(speed.value)),{signal:events.signal});
 // Orbit/pick, manual navigation and view changes stop time before their own action.
 host.addEventListener('pointerdown',event=>{if(event.target.closest('[data-guide-play],[data-guide-loop],[data-guide-speed]'))return;pause();},{capture:true,signal:events.signal});
 host.addEventListener('keydown',event=>{if(event.target.closest('[data-guide-play],[data-guide-loop],[data-guide-speed]'))return;if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Enter',' ','Escape'].includes(event.key))pause();},{capture:true,signal:events.signal});
 host.addEventListener('change',event=>{if(!event.target.closest('[data-guide-speed]'))pause();},{capture:true,signal:events.signal});
 host.addEventListener('wheel',pause,{passive:true,signal:events.signal});
 document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();else render(player?.getState());},{signal:events.signal});motion.addEventListener('change',()=>{if(motion.matches)pause();render(player?.getState());},{signal:events.signal});
 render(player?.getState());return{player,pause,refresh(){render(player?.getState());},dispose(){disposed=true;events.abort();unsubscribe?.();player?.dispose();}};
}
