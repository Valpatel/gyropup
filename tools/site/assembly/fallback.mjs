/** Install the same source-bound plain instructions in Build's Markdown snapshot. */
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {parseHTML} from 'linkedom';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export async function installGuideFallback(document,out){
 const host=document.querySelector('#assembly');if(!host)return;
 const indexFile=path.join(out,'web/build-guides/index.json'),index=JSON.parse(await readFile(indexFile,'utf8'));
 const snapshot=index.snapshots?.[0];if(!snapshot)throw Error('Missing Build guide snapshot');
 const guideFile=path.resolve(path.dirname(indexFile),snapshot.file);
 if(!guideFile.startsWith(path.resolve(out)+path.sep))throw Error('Guide escapes published bundle');
 const raw=await readFile(guideFile);if(sha(raw)!==snapshot.sha256)throw Error('Stale Build guide snapshot digest');
 const guide=JSON.parse(raw),text=await readFile(path.join(path.dirname(guideFile),'instructions.html'),'utf8');
 if(guide.source?.instructions?.file!=='instructions.json')throw Error('Missing immutable plain instruction data');
 const instructionBytes=await readFile(path.join(path.dirname(guideFile),'instructions.json'));
 if(sha(instructionBytes)!==guide.source.instructions.sha256)throw Error('Stale plain Build instruction data digest');
 const instructions=JSON.parse(instructionBytes);
 if(JSON.stringify(instructions.snapshot)!==JSON.stringify(guide.snapshot)||instructions.qualification!==guide.source.qualification||instructions.steps.length!==guide.steps.length)throw Error('Plain instruction data differs from snapshot');
 const parsed=parseHTML(text).document,main=parsed.querySelector('main');
 if(!main||main.querySelector('script')||main.querySelectorAll('section').length!==guide.steps.length)throw Error('Incomplete plain Build instructions');
 for(const [i,step] of guide.steps.entries()){
  const row=instructions.steps[i];
  if(row.id!==step.id||row.title!==step.title||row.text!==step.text||JSON.stringify(row.requirements)!==JSON.stringify(guide.source.requirements_by_step[step.id]))throw Error('Plain instruction data differs from recipe');
  const section=[...main.querySelectorAll('section')].find(s=>s.id===step.id);
  if(!section||section.querySelector('h2')?.textContent!==`${i+1}. ${step.title}`||section.querySelector('p')?.textContent!==step.text)throw Error('Plain Build instructions differ from selected recipe');
  const items=[...section.querySelectorAll('li')].map(li=>li.textContent);
  if(JSON.stringify(items)!==JSON.stringify(row.requirements.map(r=>`${r.title} ×${r.quantity} modeled instances`)))throw Error('Plain Build part list differs from recipe');
  if(step.poster){
   const image=section.querySelector('img'),expected=new URL(step.poster.file,'https://bundle.invalid/'+path.relative(out,guideFile));
   if(!image||new URL(image.getAttribute('src'),'https://bundle.invalid/'+path.relative(out,guideFile)).pathname!==expected.pathname||image.getAttribute('alt')!==step.title)throw Error('Plain Build poster differs from recipe');
   if(sha(await readFile(path.join(out,expected.pathname)))!==step.poster.sha256)throw Error('Plain Build poster bytes are stale');
  }
 }
 host.innerHTML=`<h2>Assembly walkthrough · ${escape(guide.snapshot.revision)}</h2><p>${escape(guide.source.qualification)}</p>`+main.innerHTML;
}
