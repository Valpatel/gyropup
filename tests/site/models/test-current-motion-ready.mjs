import assert from 'node:assert/strict';
import {test} from 'node:test';
import {runInNewContext} from 'node:vm';
import {currentRobotReady,currentRobotCanvasReady} from './current-motion-ready.mjs';

test('actual serialized readiness callback waits through bodyless/loading/wrong-source states',()=>{
  const observe=(document,window={})=>runInNewContext('('+currentRobotReady.toString()+')("expected")',{document,window});
  assert.equal(observe({body:null}),false);
  assert.equal(observe({body:{dataset:{}}}),false);
  assert.equal(observe({body:{dataset:{ready:'0'}}}),false);
  const ready={body:{dataset:{ready:'1'}}};
  for(const window of [{},{__sim:{}},{__sim:{state:{}}},{__sim:{state:{robot:{}}}},{__sim:{state:{robot:{presentation:{collectionSha256:'wrong'}}}}}])assert.equal(observe(ready,window),false);
  assert.equal(observe(ready,{__sim:{state:{robot:{presentation:{collectionSha256:'expected'}}}}}),true);
  const broken={get body(){throw new Error('Deliberate observer access failure');}};
  assert.throws(()=>observe(broken),/Deliberate observer access failure/);
});

test('actual canvas observer rejects logical-only readiness, fade, missing draw and hidden model',()=>{
  function fixture(){const scene={visible:true,parent:null};return {document:{body:{dataset:{ready:'1'}}},window:{__sim:{state:{robot:{presentation:{collectionSha256:'expected'},parts:Array(228).fill({}),group:{visible:true,parent:scene}}},stage:{scene,renderer:{domElement:{isConnected:true,width:640,height:1136,getBoundingClientRect:()=>({x:0,y:0,width:320,height:568})},info:{render:{frame:2,calls:250,triangles:346639}}}}}},getComputedStyle:()=>({opacity:'1',display:'block',visibility:'visible'})};}
  const observe=f=>runInNewContext('('+currentRobotCanvasReady.toString()+')("expected")',f);
  const accepted=observe(fixture());assert.equal(accepted.opacity,1);assert.equal(accepted.parts,228);assert.equal(accepted.render.triangles,346639);assert.equal(accepted.rect.width,320);
  const mutations=[
    f=>f.document.body=null,
    f=>f.window.__sim.state.robot.presentation.collectionSha256='wrong',
    f=>f.getComputedStyle=()=>({opacity:'0',display:'block',visibility:'visible'}),
    f=>f.getComputedStyle=()=>({opacity:'.99',display:'block',visibility:'visible'}),
    f=>f.getComputedStyle=()=>({opacity:'1',display:'none',visibility:'visible'}),
    f=>f.getComputedStyle=()=>({opacity:'1',display:'block',visibility:'hidden'}),
    f=>f.window.__sim.stage.renderer.domElement.isConnected=false,
    f=>f.window.__sim.stage.renderer.domElement.getBoundingClientRect=()=>({width:0,height:568}),
    f=>f.window.__sim.stage.renderer.domElement.width=0,
    ...['frame','calls','triangles'].map(key=>f=>f.window.__sim.stage.renderer.info.render[key]=0),
    f=>f.window.__sim.stage.renderer.info.render.triangles=NaN,
    f=>delete f.window.__sim.stage.renderer.info.render.calls,
    f=>f.window.__sim.state.robot.parts.pop(),
    f=>f.window.__sim.state.robot.group.visible=false,
    f=>f.window.__sim.state.robot.group.parent.visible=false,
    f=>f.window.__sim.state.robot.group.parent=null,
    f=>f.window.__sim.stage.scene={visible:true,parent:null},
  ];
  for(const mutate of mutations){const f=fixture();mutate(f);assert.equal(observe(f),false);}
  const broken=fixture();broken.getComputedStyle=()=>{throw new Error('Deliberate CSS observer failure');};assert.throws(()=>observe(broken),/Deliberate CSS observer failure/);
});
