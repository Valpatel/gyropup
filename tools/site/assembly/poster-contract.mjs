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
  render:{mode:'ghost',explode:1,viewport:{width:1280,height:900},deviceScaleFactor:1,reducedMotion:'reduce',colorScheme:'light',capture:'actual shared viewer canvas after applyStep(id,{mode:ghost,explode:1,frame:true})'},
  dependencies};
 return {inputs:canonical(inputs),visual_sha256:sha(JSON.stringify(canonical(inputs)))};
}
export async function captureContract(root){
 const base=path.join(root,'software/site/assets/build-guides/turret-wip-4866459e2abd');
 const guide=JSON.parse(await readFile(path.join(base,'guide.json'),'utf8')),model=JSON.parse(await readFile(path.join(base,'view.json'),'utf8'));
 const dependencies={};for(const file of ['software/site/designer/kit/viewer.js','software/site/designer/kit/assembly/guide.js','software/site/designer/kit/stage.js','software/site/designer/kit/panel.js','software/site/designer/kit/loading.js','software/site/designer/kit/portal-data.js','software/site/designer/assembly/build-guide.js','software/site/designer/assembly/guide.css','software/site/designer/build.html','software/site/assets/theme.css'])dependencies[file]=sha(await readFile(path.join(root,file)));
 return visualContract(guide,model,dependencies);
}
if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
 const root=path.resolve(import.meta.dirname,'../../..'),value=await captureContract(root);
 if(process.argv[2])await writeFile(process.argv[2],JSON.stringify(value,null,2)+'\n');else console.log(JSON.stringify(value,null,2));
}
