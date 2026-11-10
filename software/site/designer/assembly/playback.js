/** Product controls for the shared guide player; ticks come only from the existing stage. */
import {createGuidePlayback} from '../kit/assembly/guide.js';
export function mountPlayback(host,active,isCurrent,onStep){
 const button=host.querySelector('button[data-guide-play]'),loop=host.querySelector('button[data-guide-loop]'),speed=host.querySelector('[data-guide-speed]'),status=host.querySelector('[data-playback-status]');
 const events=new AbortController(),motion=matchMedia('(prefers-reduced-motion: reduce)');let unsubscribe=()=>{},player=null,disposed=false;
 function render(state){if(disposed||!isCurrent())return;const playing=state?.status==='playing';button.disabled=!player||motion.matches||document.hidden;button.setAttribute('aria-label',playing?'Pause assembly':'Play assembly');button.title=button.getAttribute('aria-label');button.setAttribute('aria-pressed',String(playing));button.querySelector('span').textContent=playing?'Pause':'Play';button.querySelector('svg').innerHTML=playing?'<path d="M8 5v14m8-14v14"/>':'<path d="m8 5 11 7-11 7Z"/>';loop.disabled=!player;speed.disabled=!player;loop.setAttribute('aria-pressed',String(state?.loop||false));loop.textContent=state?.loop?'Loop on':'Loop off';speed.value=String(state?.speed||1);
  status.textContent=motion.matches?'Animation is stopped for reduced motion. Use the step controls for static instructions.':!player?'This snapshot has no verified installation order. Manual steps remain available.':state.status==='ended'?'Assembly playback finished. Play starts again; completion checkboxes remain yours.':state.status==='idle'?'Play installs one authored model instance at a time. Completion checkboxes remain yours.':`${playing?'Installing':'Paused'}: ${state.partId} · ${Math.round(state.progress*100)}%`;
 }
 try{const reference=active.guide.source?.overview_step_id,order=Object.fromEntries(Object.entries(active.guide.source?.install_order_by_step||{}).filter(([id])=>id!==reference));player=createGuidePlayback(active.controller,{installOrderByStep:order,referenceStepIDs:reference?[reference]:[],durationMs:1100,onState:render,onStep:(id,operation)=>{if(isCurrent())onStep(id,operation);}});unsubscribe=active.viewer.stage.onFrame((_t,dt)=>{if(!disposed&&isCurrent())player.tick(dt);});}
 catch(error){status.dataset.error=error.message;}
 const pause=()=>{player?.pause();render(player?.getState());};
 button.addEventListener('click',()=>{if(!player||motion.matches||document.hidden)return;if(player.getState().status==='playing')player.pause();else{active.selected=null;active.isolate=false;active.partModes={};player.play();}render(player.getState());},{signal:events.signal});
 loop.addEventListener('click',()=>player?.setLoop(!player.getState().loop),{signal:events.signal});speed.addEventListener('change',()=>player?.setSpeed(Number(speed.value)),{signal:events.signal});
 // Orbit/pick, manual navigation and view changes stop time before their own action.
 host.addEventListener('pointerdown',event=>{if(event.target.closest('[data-guide-play],[data-guide-loop],[data-guide-speed]'))return;pause();},{capture:true,signal:events.signal});
 host.addEventListener('keydown',event=>{if(event.target.closest('[data-guide-play],[data-guide-loop],[data-guide-speed]'))return;if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Enter',' ','Escape'].includes(event.key))pause();},{capture:true,signal:events.signal});
 host.addEventListener('change',event=>{if(!event.target.closest('[data-guide-speed]'))pause();},{capture:true,signal:events.signal});
 host.addEventListener('wheel',pause,{passive:true,signal:events.signal});
 document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();else render(player?.getState());},{signal:events.signal});motion.addEventListener('change',()=>{if(motion.matches)pause();render(player?.getState());},{signal:events.signal});
 render(player?.getState());return{player,pause,dispose(){disposed=true;events.abort();unsubscribe?.();player?.dispose();}};
}
