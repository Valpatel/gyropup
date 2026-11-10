/** Visual fingerprint excludes poster hashes/full-guide digest to avoid a cycle. */
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
const sha=data=>createHash('sha256').update(data).digest('hex');
const canonical=x=>Array.isArray(x)?x.map(canonical):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,canonical(x[k])])):x;
export function visualContract(guide,model,dependencies){
 const inputs={schema:'gyropup.assembly-posters/1',snapshot:guide.snapshot,
  source_recipe_sha256:guide.source.inputs['hardware/cad/turret/turret_assembly.py'],
  model_sha256:guide.model.sha256,
  meshes:Object.fromEntries(model.parts.map(p=>[p.name,{file:p.file,sha256:p.sha256}])),
  steps:guide.steps.map(({id,parts,highlight,offsets_mm,camera})=>({id,parts,highlight,offsets_mm,camera})),
  render:{mode:'ghost',explode:1,viewport:{width:1280,height:900},deviceScaleFactor:1,reducedMotion:'reduce',colorScheme:'light',capture:'actual preserved WebGL canvas PNG readback after applyStep(id,{mode:ghost,explode:1,frame:true})'},
  dependencies};
 return {inputs:canonical(inputs),visual_sha256:sha(JSON.stringify(canonical(inputs)))};
}
export async function captureContract(root){
 const base=path.join(root,'software/site/assets/build-guides/turret-wip-4866459e2abd');
 const guide=JSON.parse(await readFile(path.join(base,'guide.json'),'utf8')),model=JSON.parse(await readFile(path.join(base,'view.json'),'utf8'));
 const dependencies={};for(const file of ['tools/site/assembly/render-posters.mjs','tools/site/build-site.mjs','software/site/designer/kit/appnav.js','software/site/designer/kit/part-table.css','software/site/designer/kit/loading.css','software/site/designer/kit/vendor/fonts/fonts.css','software/site/designer/kit/vendor/fonts/inter.woff2','software/site/designer/kit/vendor/fonts/jetbrains-mono.woff2','software/site/assets/theme.js','software/site/assets/prototype-notice.html','software/site/assets/prototype-notice.js','software/site/assets/prototype-notice.css','software/site/assets/model-links.js','software/site/assets/model-links.css','software/site/designer/kit/viewer.js','software/site/designer/kit/assembly/guide.js','software/site/designer/kit/assembly/playback.js','software/site/designer/kit/stage.js','software/site/designer/kit/panel.js','software/site/designer/kit/loading.js','software/site/designer/kit/portal-data.js','software/site/designer/kit/file-geometry.js','software/site/designer/kit/smooth_zoom.js','software/site/designer/kit/vendor/three/three.module.min.js','software/site/designer/kit/vendor/three/addons/loaders/STLLoader.js','software/site/designer/kit/vendor/three/addons/controls/OrbitControls.js','software/site/designer/kit/hud.css','software/site/designer/portal-parts.css','software/site/designer/assembly/state.js','software/site/designer/assembly/build-guide.js','software/site/designer/assembly/workspace.js','software/site/designer/assembly/playback.js','software/site/designer/assembly/part-inspector.js','software/site/designer/assembly/print-selection.js','software/site/designer/assembly/guide.css','software/site/designer/build.html','software/site/assets/theme.css'])dependencies[file]=sha(await readFile(path.join(root,file)));
 return visualContract(guide,model,dependencies);
}
if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
 const root=path.resolve(import.meta.dirname,'../../..'),value=await captureContract(root);
 if(process.argv[2]==='--check'){
  const guide=JSON.parse(await readFile(path.join(root,'software/site/assets/build-guides/turret-wip-4866459e2abd/guide.json'),'utf8'));
  if(guide.source.poster_visual_sha256!==value.visual_sha256||guide.steps.some(step=>!step.poster))throw new Error('Fresh source-bound posters are missing or stale; capture the actual viewer before publication.');
  console.log('PASS twelve posters bind the current visual inputs');
 }else if(process.argv[2])await writeFile(process.argv[2],JSON.stringify(value,null,2)+'\n');else console.log(JSON.stringify(value,null,2));
}
