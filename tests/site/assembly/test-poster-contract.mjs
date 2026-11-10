import test from'node:test';import assert from'node:assert/strict';import{readFile}from'node:fs/promises';
import{visualContract}from'../../../tools/site/assembly/poster-contract.mjs';
const base=new URL('../../../software/site/assets/build-guides/turret-wip-4866459e2abd/',import.meta.url),guide=JSON.parse(await readFile(new URL('guide.json',base))),model=JSON.parse(await readFile(new URL('view.json',base)));
test('visual fingerprint is sensitive to actual recipe/geometry/runtime, independent of poster sealing',()=>{
 const a=visualContract(guide,model,{'viewer.js':'a'.repeat(64)}),sealed=structuredClone(guide);sealed.steps[0].poster={file:'posters/step-01.png',sha256:'f'.repeat(64)};
 assert.equal(visualContract(sealed,model,{'viewer.js':'a'.repeat(64)}).visual_sha256,a.visual_sha256);
 for(const mutate of [g=>g.steps[0].offsets_mm.pan_base=[0,0,1],g=>g.steps[0].camera.direction=[1,0,0],g=>g.steps[0].parts=[],g=>g.model.sha256='b'.repeat(64)]){const g=structuredClone(guide);mutate(g);assert.notEqual(visualContract(g,model,{'viewer.js':'a'.repeat(64)}).visual_sha256,a.visual_sha256);}
 assert.notEqual(visualContract(guide,model,{'viewer.js':'b'.repeat(64)}).visual_sha256,a.visual_sha256);
 const changed=structuredClone(model);changed.parts[0].sha256='c'.repeat(64);assert.notEqual(visualContract(guide,changed,{'viewer.js':'a'.repeat(64)}).visual_sha256,a.visual_sha256);
});
