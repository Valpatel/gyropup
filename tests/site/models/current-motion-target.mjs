/** Resolve the actual required-part request before a browser/server is started. */
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';

export async function requiredMeshRequestTarget(manifest,publicManifest,siteRoot,name){
  const matches=manifest.parts.filter(part=>part.name===name);
  assert.equal(matches.length,1,'Required request target must name exactly one manifest part: '+name);
  const part=matches[0];
  assert.match(part.file,/^meshes\/[A-Za-z0-9_-]+\.stl$/,'Required request target must be a local mesh file');
  assert.match(part.sha256,/^[0-9a-f]{64}$/);
  const pathname='/'+path.posix.join(path.posix.dirname(publicManifest),part.file);
  const bytes=await readFile(path.join(siteRoot,pathname.slice(1)));
  assert.equal(createHash('sha256').update(bytes).digest('hex'),part.sha256,'Required request target bytes must match the manifest');
  const escaped=pathname.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  return {name,file:part.file,sha256:part.sha256,pathname,pattern:new RegExp('^https?://[^/]+?'+escaped+'(?:\\?.*)?$')};
}
