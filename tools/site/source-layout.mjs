/** Editable source ownership and stable published identities are separate contracts. */
import {readFile} from 'node:fs/promises';
import path from 'node:path';
const layout=JSON.parse(await readFile(new URL('./source-layout.json',import.meta.url),'utf8'));
if(layout.version!==1)throw new Error('Unsupported source-layout contract');
const exact=new Map(layout.files.map(row=>[row.source,row.public]));
const inverse=new Map(layout.files.map(row=>[row.public,row.source]));
if(exact.size!==layout.files.length||inverse.size!==layout.files.length)throw new Error('Duplicate exact publication identity');
const legacyTests=new Set(layout.legacyPublicTestFiles);
function relative(value){
 const file=path.posix.normalize(String(value).replace(/^\/+/,''));
 if(file==='..'||file.startsWith('../')||file.includes('\0'))throw new Error('Source path escapes project');
 return file==='.'?'':file.replace(/\/$/,'');
}
const contains=(file,folder)=>file===folder||file.startsWith(folder+'/');
export function unpublishedSource(value){
 const file=relative(value);
 return /(?:^|\/)(?:AGENTS|CLAUDE)\.md$/.test(file)
   ||layout.unpublished.some(folder=>contains(file,folder))&&!legacyTests.has(file);
}
export function publicForSource(value){
 const file=relative(value);
 if(unpublishedSource(file))return null;
 if(exact.has(file))return exact.get(file);
 // Package initializers have no public download contract merely by becoming source.
 if(file.endsWith('/__init__.py'))return null;
 for(const rule of layout.prefixes){
  if(contains(file,rule.source))return rule.public+file.slice(rule.source.length);
 }
 return null;
}
export function sourceForPublic(value){
 const file=relative(value);
 if(inverse.has(file))return inverse.get(file);
 for(const rule of layout.prefixes){
  if(contains(file,rule.public))return rule.source+file.slice(rule.public.length);
 }
 return file; // Explicit project configuration/internal inputs may be unpublished.
}
export function publicationFiles(sources){
 const files=new Map();
 for(const source of sources){
  const published=publicForSource(source);
  if(published===null)continue;
  if(files.has(published))throw new Error(`Publication collision: ${published}`);
  files.set(published,source);
 }
 return files;
}

// These two dated notes refer to catalogues retired before the ownership move.
// Their labels remain useful history; unrelated unresolved links stay visible.
const retiredCatalogues=new Map([
  ['research/availability-2026-10-25.md','availability.json'],
  ['docs/research/availability-2026-10-25.md','availability.json'],
  ['research/lfp-batteries.md','lfp_batteries.json'],
  ['docs/research/lfp-batteries.md','lfp_batteries.json'],
]);
export function markRetiredCatalogLinks(html,source){
  const retired=retiredCatalogues.get(source);
  if(!retired)return html;
  return html.replace(/<a href="https:\/\/github\.com\/Valpatel\/gyropup\/blob\/main\/(?:docs\/)?catalog\/([^"/]+)">(.*?)<\/a>/g,
    (link,file,label)=>file===retired?`<span title="Historical file, not part of this revision">${label} (historical file)</span>`:link);
}
