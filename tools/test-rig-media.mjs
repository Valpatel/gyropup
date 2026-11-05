/** Decode retained leg movies, then challenge the same validator with honestly rehashed wrong pixels. */
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile,writeFile,mkdtemp,mkdir,copyFile,rm} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import os from 'node:os';
import {verifyRigFiles} from './rig-media.mjs';
import {rigDigest,prepareRigMedia} from '../designer/rig-media.js';
const root=path.resolve(import.meta.dirname,'..');
const receipt=JSON.parse(await readFile(path.join(root,'exports/leg/rig-media.json')));

test('every retained companion preserves all original decoded pixels and timing',async()=>{
  assert.equal((await verifyRigFiles(root,{historical:true,decode:true})).clips.length,7);
});

test('rehashed substituted and frozen companions cannot pass decoded correspondence',async()=>{
  const fixture=await mkdtemp(path.join(os.tmpdir(),'gyropup-rig-faults-'));
  try {
    for(const file of [receipt.report.path,...receipt.clips.flatMap(c=>[c.path,c.companion.path])]){
      const target=path.join(fixture,file);await mkdir(path.dirname(target),{recursive:true});await copyFile(path.join(root,file),target);
    }
    const recordPath=path.join(fixture,'exports/leg/rig-media.json');
    const selected=receipt.clips.find(c=>c.scenario==='jump');
    const target=path.join(fixture,selected.companion.path);
    for(const fault of ['different-scenario','frozen']){
      if(fault==='different-scenario')await copyFile(path.join(root,receipt.clips.find(c=>c.scenario==='jump_peak').companion.path),target);
      else execFileSync('ffmpeg',['-v','error','-nostdin','-y','-i',path.join(fixture,selected.path),
        '-vf','trim=end_frame=1,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=100',
        '-frames:v',String(selected.companion.decoded.frames),'-an','-c:v','libvpx-vp9','-lossless','1',
        '-pix_fmt','yuv420p','-deadline','good','-cpu-used','4','-threads','2',target],{timeout:120000});
      const changed=structuredClone(receipt),clip=changed.clips.find(c=>c.scenario==='jump');
      clip.companion.sha256=await rigDigest(await readFile(target));
      // These bytes pass every identity check: only fresh decoding can reject their claimed correspondence.
      await writeFile(recordPath,JSON.stringify(changed));
      await prepareRigMedia(await readFile(path.join(fixture,receipt.report.path)),changed,file=>readFile(path.join(fixture,file)));
      await assert.rejects(verifyRigFiles(fixture,{decode:true}),/decoded pixels differ|frame count/,fault);
    }
  }finally{await rm(fixture,{recursive:true,force:true});}
});
