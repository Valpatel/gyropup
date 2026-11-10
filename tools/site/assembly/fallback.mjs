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
 const parsed=parseHTML(text).document,main=parsed.querySelector('main');
 if(!main||main.querySelector('script')||main.querySelectorAll('section').length!==guide.steps.length)throw Error('Incomplete plain Build instructions');
 for(const step of guide.steps){
  const section=[...main.querySelectorAll('section')].find(s=>s.id===step.id);
  if(!section||section.querySelector('p')?.textContent!==step.text)throw Error('Plain Build instructions differ from selected recipe');
 }
 host.innerHTML=`<h2>Assembly walkthrough · ${escape(guide.snapshot.revision)}</h2><p>${escape(guide.source.qualification)}</p>`+main.innerHTML;
}
