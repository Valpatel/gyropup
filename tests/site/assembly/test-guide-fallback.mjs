import test from 'node:test';import assert from 'node:assert/strict';import {mkdtemp,cp,readFile,writeFile,rm}from'node:fs/promises';import os from'node:os';import path from'node:path';import {parseHTML}from'linkedom';
import {installGuideFallback}from'../../../tools/site/assembly/fallback.mjs';
test('plain fallback binds actual selected recipe and rejects stale HTML',async()=>{
 const dir=await mkdtemp(path.join(os.tmpdir(),'gy-guide-fallback-'));
 try{
  const source=new URL('../../../software/site/assets/build-guides/',import.meta.url);await cp(source,path.join(dir,'web/build-guides'),{recursive:true});
  const {document}=parseHTML('<main><section id="assembly"></section><div id="orders">preserved</div></main>');
  await installGuideFallback(document,dir);assert.equal(document.querySelectorAll('#assembly section').length,12);assert.equal(document.querySelector('#orders').textContent,'preserved');assert.match(document.querySelector('#assembly').textContent,/\+12 and -25/);assert.doesNotMatch(document.querySelector('#assembly').textContent,/cannot be pushed above level/);
  const file=path.join(dir,'web/build-guides/turret-wip-4866459e2abd/instructions.html'),original=await readFile(file,'utf8');
  await writeFile(file,original.replace('1. The pan base and its inserts','1. Wrong assembly action'));
  await assert.rejects(installGuideFallback(document,dir),/Stale plain Build instructions digest/);
  await writeFile(file,original.replace('Check the +12 and -25','Check the 0 and -25'));
  await assert.rejects(installGuideFallback(document,dir),/Stale plain Build instructions digest/);
 }finally{await rm(dir,{recursive:true,force:true});}
});
