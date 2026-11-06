/** Decode retained leg movies, then challenge the same validator with honestly rehashed wrong pixels. */
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile,writeFile,mkdtemp,mkdir,copyFile,rm} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import os from 'node:os';
import {verifyRigFiles} from '../../../tools/evidence/media/rig-media.mjs';
import {rigDigest,prepareRigMedia} from '../../../software/site/designer/rig-media.js';
const root=path.resolve(import.meta.dirname, '../../..');
const receipt=JSON.parse(await readFile(path.join(root,'exports/leg/rig-media.json')));

test('publication checks both actual formats even if a browser selects only one',async()=>{
  const report=await readFile(path.join(root,receipt.report.path)),clip=receipt.clips[0];
  for(const file of [clip.path,clip.companion.path])
    await assert.rejects(prepareRigMedia(report,receipt,p=>p===file?Buffer.from('wrong bytes'):readFile(path.join(root,p))),/identity does not match/);
});

test('every retained companion preserves all original decoded pixels and timing',async()=>{
  assert.equal((await verifyRigFiles(root,{historical:true,decode:true})).clips.length,7);
});

test('rehashed substituted, frozen and false-duration companions cannot pass decoded correspondence',async()=>{
  const fixture=await mkdtemp(path.join(os.tmpdir(),'gyropup-rig-faults-'));
  try {
    for(const file of [receipt.report.path,...receipt.clips.flatMap(c=>[c.path,c.companion.path])]){
      const target=path.join(fixture,file);await mkdir(path.dirname(target),{recursive:true});await copyFile(path.join(root,file),target);
    }
    const recordPath=path.join(fixture,'exports/leg/rig-media.json');
    const selected=receipt.clips.find(c=>c.scenario==='jump');
    const target=path.join(fixture,selected.companion.path);
    for(const fault of ['different-scenario','frozen','duration']){
      if(fault==='different-scenario')await copyFile(path.join(root,receipt.clips.find(c=>c.scenario==='jump_peak').companion.path),target);
      else if(fault==='frozen')execFileSync('ffmpeg',['-v','error','-nostdin','-y','-i',path.join(fixture,selected.path),
        '-vf','trim=end_frame=1,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=100',
        '-frames:v',String(selected.companion.decoded.frames),'-an','-c:v','libvpx-vp9','-lossless','1',
        '-pix_fmt','yuv420p','-deadline','good','-cpu-used','4','-threads','2',target],{timeout:120000});
      else {
        const bytes=await readFile(path.join(root,selected.companion.path));
        // FFmpeg writes the Matroska Duration element as an eight-byte float.
        // Change only that field: all encoded frames, hashes and presentation timestamps remain intact.
        const tag=Buffer.from([0x44,0x89,0x88]),at=bytes.indexOf(tag);
        assert.ok(at>=0 && at<4096 && bytes.indexOf(tag,at+1)===-1,'Unambiguous duration metadata control');
        bytes.writeDoubleBE(bytes.readDoubleBE(at+3)*10,at+3);await writeFile(target,bytes);
        const duration=Number(execFileSync('ffprobe',['-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',target],{encoding:'utf8'}));
        assert.ok(duration>selected.companion.decoded.duration_s*9,'The container actually advertises the wrong duration');
      }
      const changed=structuredClone(receipt),clip=changed.clips.find(c=>c.scenario==='jump');
      clip.companion.sha256=await rigDigest(await readFile(target));
      // These bytes pass every identity check: only fresh decoding can reject their claimed correspondence.
      await writeFile(recordPath,JSON.stringify(changed));
      await prepareRigMedia(await readFile(path.join(fixture,receipt.report.path)),changed,file=>readFile(path.join(fixture,file)));
      await assert.rejects(verifyRigFiles(fixture,{decode:true}),fault==='duration'?/duration differs/:/decoded pixels differ|frame count/,fault);
    }
  }finally{await rm(fixture,{recursive:true,force:true});}
});
