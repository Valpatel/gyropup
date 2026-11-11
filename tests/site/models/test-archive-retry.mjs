/** Real archive bytes and loader with controlled fetch failures. No browser or CAD construction. */
import assert from 'node:assert/strict';
import test from 'node:test';
import {registerHooks} from 'node:module';
import {readFile} from 'node:fs/promises';
import {sourceForPublic} from '../../../tools/site/source-layout.mjs';

const root=new URL('../../../',import.meta.url),vendor=new URL('software/site/designer/kit/vendor/three/',root);
registerHooks({resolve(specifier,context,next){
  if(specifier==='three')return{url:new URL('three.module.min.js',vendor).href,shortCircuit:true};
  if(specifier.startsWith('three/addons/'))return{url:new URL(specifier.slice('three/'.length),vendor).href,shortCircuit:true};
  return next(specifier,context);
}});
const {buildRobotV2}=await import('../../../software/site/designer/robot_v2.js');

async function withArchive(run) {
  const original=globalThis.fetch,held=[];
  let intercept=false,robot;
  globalThis.fetch=async(url,options)=>{
    const name=new URL(url).pathname.slice(1);
    if(intercept && /^exports\/sim\/v2\/rig\/turret_.*\.stl$/.test(name)){
      return new Promise((resolve,reject)=>{
        const item={name,settled:false,reject(error){
          if(item.settled)return;
          item.settled=true;options.signal.removeEventListener('abort',abort);reject(error);
        }};
        const abort=()=>item.reject(options.signal.reason);
        options.signal.addEventListener('abort',abort,{once:true});
        held.push(item);
        if(options.signal.aborted)abort();
      });
    }
    return new Response(await readFile(new URL(sourceForPublic(name),root)),{status:200});
  };
  try {
    robot=await buildRobotV2('http://fixture.invalid/',{presentationSource:null});
    await run({robot,held,failArchive(){intercept=true;},allowArchive(){intercept=false;}});
  } finally {
    robot?.dispose();
    for(const item of held)item.reject(Error('fixture cleanup'));
    globalThis.fetch=original;
  }
}

test('an immediate retry succeeds after staggered archive mesh failures',async()=>{
  await withArchive(async({robot,held,failArchive,allowArchive})=>{
    failArchive();
    let firstError,retry;
    const first=robot.setPresentation('recorded').catch(error=>{
      firstError=error;allowArchive();
      // The same error boundary used by a caller's immediate retry.
      retry=robot.setPresentation('recorded').then(()=>({ok:true}),error=>({ok:false,error:error.message}));
    });
    assert.ok(held.length>2,'the actual archive starts parallel mesh reads');
    const victim=held.find(item=>item.name.endsWith('turret__tilt_12_flywheel_motor_l.stl'));
    assert.ok(victim);
    const trigger=held.find(item=>item!==victim);
    trigger.reject(TypeError('first controlled connection failure'));
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(robot.presentation.mode,'current','the failed attempt preserves the usable current scene');
    victim.reject(TypeError('later controlled connection failure'));
    for(const item of held)item.reject(TypeError('remaining controlled connection failure'));
    await first;
    assert.ok(firstError.message.startsWith('Robot mesh '+trigger.name.split('/').at(-1)+':'),'retain the first rejected mesh error');
    assert.deepEqual(await retry,{ok:true},'the immediate retry cannot inherit a failed sibling promise');
    assert.equal(robot.presentation.mode,'recorded');
  });
});

test('disposal aborts a failed cohort and prevents later attachment',async()=>{
  await withArchive(async({robot,held,failArchive})=>{
    failArchive();
    const first=robot.setPresentation('recorded').then(()=>({ok:true}),error=>({ok:false,error}));
    held[0].reject(TypeError('first controlled connection failure'));
    await new Promise(resolve=>setImmediate(resolve));
    robot.dispose();
    assert.equal((await first).ok,false);
    assert.ok(held.every(item=>item.settled),'all held readers observe the existing lifetime abort signal');
    await assert.rejects(robot.setPresentation('recorded'),/disposed/);
  });
});
