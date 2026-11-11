import assert from 'node:assert/strict';
import {test} from 'node:test';
import {mkdtemp,mkdir,writeFile,rm,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {requiredMeshRequestTarget} from './current-motion-target.mjs';

test('held-load and error controls resolve actual manifest bytes, not logical-name spelling',async()=>{
  const root=await mkdtemp(path.join(tmpdir(),'current-motion-target-'));
  try{
    await mkdir(path.join(root,'web/robot-current/meshes'),{recursive:true});
    const bytes=Buffer.from('explicit synthetic target; not CAD evidence');
    await writeFile(path.join(root,'web/robot-current/meshes/item__battery_front.stl'),bytes);
    const part={name:'item.battery_front',file:'meshes/item__battery_front.stl',sha256:createHash('sha256').update(bytes).digest('hex')};
    const resolve=parts=>requiredMeshRequestTarget({parts},'web/robot-current/manifest.json',root,part.name);
    const target=await resolve([part]);
    assert.equal(target.pathname,'/web/robot-current/meshes/item__battery_front.stl');
    assert.ok(target.pattern.test('http://127.0.0.1:1234'+target.pathname+'?cache=1'));
    for(const url of ['http://fixture/web/robot-current/meshes/item.battery_front.stl','http://fixture/other'+target.pathname,'http://fixture'+target.pathname+'.extra'])assert.equal(target.pattern.test(url),false,url);
    await assert.rejects(resolve([]),/exactly one manifest part/);
    await assert.rejects(resolve([part,part]),/exactly one manifest part/);
    await assert.rejects(resolve([{...part,file:'meshes/nonexistent.stl'}]),/ENOENT/);
    await assert.rejects(resolve([{...part,file:'meshes/item.battery_front.stl'}]),/local mesh file/);
    await assert.rejects(resolve([{...part,file:'../outside.stl'}]),/local mesh file/);
    await assert.rejects(resolve([{...part,sha256:'0'.repeat(64)}]),/bytes must match/);
  }finally{await rm(root,{recursive:true,force:true});}
});

test('accepted candidate required-part target exists and has its original bytes',{skip:!process.env.CURRENT_MOTION_CANDIDATE},async()=>{
  const candidate=process.env.CURRENT_MOTION_CANDIDATE;
  const manifest=JSON.parse(await readFile(path.join(candidate,'manifest.json')));
  // A minimal resolver webroot view uses the actual original candidate directory.
  const target=await requiredMeshRequestTarget(manifest,'manifest.json',candidate,'item.battery_front');
  assert.equal(target.file,'meshes/item__battery_front.stl');
  assert.equal(target.sha256,'fff8ba9d6ef22c1a562590c602c9bb381c25257d718e7c2c48ed6760f727bdba');
});
