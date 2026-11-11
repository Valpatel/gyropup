/** Test-only observer budgets over actual stage dt; this contains no hop trajectory. */
export const HOP_LIMITS=Object.freeze({simulationS:3,wallMs:30000,stalledMs:10000});
export function checkHopProgress(sample,limits=HOP_LIMITS){
 for(const key of ['simulatedS','nowMs','startedAt','lastFrameAt','frames','maxY','y'])if(!Number.isFinite(sample[key]))throw Error('Invalid hop observation: '+key);
 if(sample.frames<1||sample.simulatedS<0||sample.startedAt>sample.lastFrameAt||sample.lastFrameAt>sample.nowMs)throw Error('Invalid hop observation ordering');
 if(sample.stageError)throw Error('Hop stage callback failed: '+sample.stageError);
 if(sample.paused||sample.replay||sample.visibility!=='visible')throw Error('Hop observer lost the active visible manual scene');
 if(sample.nowMs-sample.startedAt>limits.wallMs)throw Error('Hop exceeded hard wall budget');
 if(sample.nowMs-sample.lastFrameAt>limits.stalledMs)throw Error('Hop stage frames stalled');
 if(sample.simulatedS>limits.simulationS)throw Error('Hop did not complete within simulated-time budget');
 return sample.landed===true&&sample.y===0&&sample.maxY>.12;
}
/** Passed directly to Playwright; a Promise must never be accepted as truthy. */
export function pollHop({guard,readSample,limits}){
 const sample=readSample();if(!sample)return false;
 const decision=guard(sample,limits);
 if(typeof decision!=='boolean')throw Error('Hop guard must return a synchronous boolean');
 return decision;
}
/** Reads only actual existing stage observations and current rendered state. */
export function readHopSample(){
 const r=window.__hopTrace,s=window.__sim;if(!r.started)return null;
 return {simulatedS:r.simulatedS,nowMs:performance.now(),startedAt:r.startedAt,lastFrameAt:r.lastFrameAt,frames:r.frames,maxY:r.maxY,y:s.state.robot.group.position.y,landed:!s.state.jump,paused:s.demo.on&&!s.demo.playing,replay:!!s.state.replay,visibility:document.visibilityState,stageError:document.body.dataset.stageError||null};
}
