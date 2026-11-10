/** Attach already captured actual viewer pixels. This command never renders. */
import {readFile,writeFile,mkdir,copyFile}from'node:fs/promises';
import path from'node:path';import{createHash}from'node:crypto';import{execFileSync}from'node:child_process';
import{captureContract}from'./poster-contract.mjs';
const root=path.resolve(import.meta.dirname,'../../..'),[receiptFile,imageDirectory]=process.argv.slice(2);
if(!receiptFile||!imageDirectory)throw Error('Usage: node tools/site/assembly/attach-posters.mjs RECEIPT.json IMAGES');
const receipt=JSON.parse(await readFile(receiptFile,'utf8')),contract=await captureContract(root);
if(receipt.visual_sha256!==contract.visual_sha256)throw Error('Captured visual inputs are stale');
const base=path.join(root,'software/site/assets/build-guides/turret-wip-4866459e2abd'),guide=JSON.parse(await readFile(path.join(base,'guide.json'),'utf8'));
if(JSON.stringify(Object.keys(receipt.frames||{}).sort())!==JSON.stringify(guide.steps.map(s=>s.id).sort()))throw Error('Need exactly twelve captured steps');
const frames={};
for(const step of guide.steps){
 const frame=receipt.frames[step.id];if(frame.file!==step.id+'.png')throw Error('Unexpected captured poster filename');
 const data=await readFile(path.join(imageDirectory,frame.file)),hash=createHash('sha256').update(data).digest('hex');
 if(hash!==frame.sha256)throw Error('Captured poster digest mismatch');
 if(!data.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))||data.length<24||data.readUInt32BE(16)<250||data.readUInt32BE(20)<200)throw Error('Not a useful-sized captured PNG');
 frames[step.id]={file:'posters/'+frame.file,sha256:hash};
}
await mkdir(path.join(base,'posters'),{recursive:true});
for(const frame of Object.values(frames))await copyFile(path.join(imageDirectory,path.basename(frame.file)),path.join(base,frame.file));
await writeFile(path.join(base,'posters.json'),JSON.stringify({schema:'gyropup.assembly-posters/1',visual_sha256:contract.visual_sha256,frames},null,2)+'\n');
execFileSync('python3',['-B','tools/site/assembly/export_turret_guide.py'],{cwd:root,stdio:'inherit'});
console.log('Attached twelve captured posters; source/CI/publication acceptance remains separate.');
