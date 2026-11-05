/** Source-bound VP9 companions for the existing recorded leg movies.
 * --record <full-producer-sha>: verify originals, convert without changing decoded pixels, then write a receipt.
 * --check: verify retained identities, historical sources and every decoded original/companion frame.
 */
import {execFileSync, spawnSync} from 'node:child_process';
import {readFile, writeFile, mkdtemp, mkdir, copyFile, rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {prepareRigMedia, rigDigest} from '../designer/rig-media.js';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const REPORT = 'exports/leg/rig-results.json', RECEIPT = 'exports/leg/rig-media.json', CONVERTER = 'tools/rig-media.mjs';
const SHA = /^[0-9a-f]{40}$/;
const requireValid = (ok, why) => {if (!ok) throw new Error(why);};
const gitBytes = (directory, revision, file) => execFileSync('git', ['show', `${revision}:${file}`], {cwd: directory, maxBuffer: 64 << 20});
const encodeArgs = (input, output) => ['-v','error','-nostdin','-y','-i',input,'-map','0:v:0','-an','-c:v','libvpx-vp9',
  '-lossless','1','-pix_fmt','yuv420p','-deadline','good','-cpu-used','4','-row-mt','1','-threads','2','-fps_mode','passthrough',output];
function command(program, args) {
  const result=spawnSync(program,args,{encoding:'utf8',maxBuffer:64<<20,timeout:120000});
  requireValid(!result.error && result.status===0 && !result.stderr.trim(), `${program} failed to decode/convert the complete movie: ${result.error?.message || result.stderr}`);
  return result.stdout;
}
function frameHashes(file, pixelFormat) {
  return command('ffmpeg',['-v','error','-nostdin','-i',file,'-map','0:v:0','-an','-pix_fmt',pixelFormat,'-f','framehash','-hash','sha256','-'])
    .split('\n').filter(line=>line && !line.startsWith('#')).map(line=>line.split(',').at(-1).trim());
}
function decoded(file) {
  const info=JSON.parse(command('ffprobe',['-v','error','-select_streams','v:0','-show_frames','-show_entries',
    'stream=codec_name,profile,level,width,height,pix_fmt,r_frame_rate,color_range,color_space,color_transfer,color_primaries,duration:format=duration:frame=best_effort_timestamp_time','-of','json',file]));
  requireValid(info.streams?.length===1 && info.frames?.length>1, 'Missing complete decoded video stream.');
  const stream=info.streams[0], times=info.frames.map(f=>Number(f.best_effort_timestamp_time));
  const hashes=frameHashes(file,'yuv420p');
  requireValid(hashes.length===times.length && hashes.every(hash=>/^[0-9a-f]{64}$/.test(hash)), 'Incomplete decoded frame hashes.');
  requireValid(times.every((t,i)=>Number.isFinite(t) && (i===0 || t>times[i-1])), 'Invalid decoded frame timing.');
  const duration=Number(info.format?.duration);
  requireValid(Number.isFinite(duration) && duration>0, 'Missing finite positive container duration.');
  if(stream.duration!=null)requireValid(Number.isFinite(Number(stream.duration)) && Math.abs(Number(stream.duration)-duration)<=0.001001, 'Stream/container duration differs.');
  return {stream,times,hashes,duration};
}

export async function compareRigPixels(original, companion) {
  const a=decoded(original),b=decoded(companion);
  requireValid(a.stream.codec_name==='h264' && a.stream.profile==='High' && a.stream.level===31, 'Original codec is not the recorded AVC profile.');
  requireValid(b.stream.codec_name==='vp9', 'Companion is not VP9.');
  for (const key of ['width','height','pix_fmt','r_frame_rate','color_space','color_transfer','color_primaries'])
    requireValid(a.stream[key]===b.stream[key], `Companion ${key} differs.`);
  // These AVC files omit range metadata; VP9 declares limited range. Accept only that
  // specific normalization, and independently require identical interpreted RGB pixels below.
  requireValid(a.stream.color_range===b.stream.color_range || (a.stream.color_range==null && b.stream.color_range==='tv'), 'Companion color range differs.');
  requireValid(a.stream.pix_fmt==='yuv420p' && a.hashes.length===b.hashes.length, 'Companion frame count or pixel format differs.');
  const maxTime=Math.max(...a.times.map((t,i)=>Math.abs(t-b.times[i])));
  // WebM timestamps have a 1 ms timebase; the original 30 Hz frames round by at most 2/3 ms.
  requireValid(maxTime<=0.001001, 'Companion changes recorded frame timing.');
  requireValid(a.hashes.every((hash,i)=>hash===b.hashes[i]), 'Companion decoded pixels differ from the original.');
  const rgbA=frameHashes(original,'rgb24'),rgbB=frameHashes(companion,'rgb24');
  requireValid(rgbA.length===a.hashes.length && rgbB.length===a.hashes.length
    && rgbA.every((hash,i)=>/^[0-9a-f]{64}$/.test(hash)&&hash===rgbB[i]), 'Companion interpreted RGB pixels differ from the original.');
  const [n,d]=a.stream.r_frame_rate.split('/').map(Number),fps=n/d;
  requireValid(Number.isFinite(fps) && fps>0, 'Invalid recorded frame rate.');
  for(const movie of [a,b])requireValid(Math.abs(movie.duration-(movie.times.at(-1)-movie.times[0]+1/fps))<=0.001001,
    'Container duration differs from decoded frame timing.');
  requireValid(Math.abs(a.duration-b.duration)<=0.001001, 'Companion container duration differs.');
  return {width:a.stream.width,height:a.stream.height,pixel_format:a.stream.pix_fmt,frame_rate:a.stream.r_frame_rate,
    color:{original_range:a.stream.color_range??'unspecified',companion_range:b.stream.color_range??'unspecified',space:a.stream.color_space??'unspecified',transfer:a.stream.color_transfer??'unspecified',primaries:a.stream.color_primaries??'unspecified'},
    frames:a.hashes.length,duration_s:a.duration,companion_duration_s:b.duration,max_timestamp_delta_s:maxTime,
    comparison:'Every decoded YUV420P and interpreted RGB24 frame SHA-256 matches; zero pixel error',
    decoded_frame_sequence_sha256:await rigDigest(new TextEncoder().encode(a.hashes.join('\n')+'\n')),
    rgb_frame_sequence_sha256:await rigDigest(new TextEncoder().encode(rgbA.join('\n')+'\n'))};
}

export async function producerRigRecord(directory, revision) {
  requireValid(SHA.test(revision), 'Use a full immutable producer commit SHA.');
  const reportBytes=gitBytes(directory,revision,REPORT), report=JSON.parse(reportBytes);
  const scenarios=Object.keys(report.scenarios||{});
  requireValid(scenarios.length>0 && scenarios.every(name=>/^[a-z0-9_]+$/.test(name) && report.scenarios[name]?.scenario===name), 'Invalid producer scenarios.');
  const record={schema:2,producer_revision:revision,report:{path:REPORT,sha256:await rigDigest(reportBytes)},clips:[]};
  for (const scenario of scenarios) {
    const file=`exports/leg/rig_${scenario}.mp4`;
    record.clips.push({scenario,path:file,sha256:await rigDigest(gitBytes(directory,revision,file))});
  }
  for (const item of [record.report,...record.clips])
    requireValid(await rigDigest(await readFile(path.join(directory,item.path)))===item.sha256, `Recorded movie/report identity differs from producer: ${item.path}`);
  return record;
}

export async function verifyRigFiles(directory, {historical=false,decode=false}={}) {
  const record=JSON.parse(await readFile(path.join(directory,RECEIPT),'utf8'));
  const media=await prepareRigMedia(await readFile(path.join(directory,REPORT)),record,file=>readFile(path.join(directory,file)));
  const derived=record.derivation;
  requireValid(derived?.kind==='lossless-vp9-companion' && SHA.test(derived.converter_revision)
    && derived.converter_path===CONVERTER && /^[0-9a-f]{64}$/.test(derived.converter_sha256)
    && typeof derived.ffmpeg_version==='string' && derived.ffmpeg_version.startsWith('ffmpeg version ')
    && JSON.stringify(derived.argv_template)===JSON.stringify(encodeArgs('{original}','{companion}')), 'Invalid companion conversion provenance.');
  if (historical) {
    await producerRigRecord(directory,record.producer_revision);
    requireValid(await rigDigest(gitBytes(directory,derived.converter_revision,CONVERTER))===derived.converter_sha256, 'Historical companion converter differs.');
  }
  if (decode) for (const clip of record.clips) {
    const actual=await compareRigPixels(path.join(directory,clip.path),path.join(directory,clip.companion.path));
    requireValid(JSON.stringify(actual)===JSON.stringify(clip.companion.decoded), `Recorded decoded comparison differs: ${clip.scenario}`);
  }
  return media;
}

export async function recordRigMedia(directory, revision) {
  const record=await producerRigRecord(directory,revision); // Refuse changed originals before conversion or any write.
  const converterRevision=execFileSync('git',['rev-parse','HEAD'],{cwd:directory,encoding:'utf8'}).trim();
  const converterBytes=await readFile(path.join(directory,CONVERTER));
  requireValid(await rigDigest(converterBytes)===await rigDigest(gitBytes(directory,converterRevision,CONVERTER)), 'Commit the converter before recording its outputs.');
  record.derivation={kind:'lossless-vp9-companion',converter_revision:converterRevision,converter_path:CONVERTER,
    converter_sha256:await rigDigest(converterBytes),ffmpeg_version:execFileSync('ffmpeg',['-version'],{encoding:'utf8'}).split('\n')[0],
    argv_template:encodeArgs('{original}','{companion}')};
  const temporary=await mkdtemp(path.join(os.tmpdir(),'gyropup-rig-vp9-'));
  try {
    for (const clip of record.clips) {
      const original=path.join(directory,clip.path),file=`exports/leg/rig_${clip.scenario}.webm`,output=path.join(temporary,clip.scenario+'.webm');
      command('ffmpeg',encodeArgs(original,output));
      clip.companion={path:file,source_sha256:clip.sha256,sha256:await rigDigest(await readFile(output)),decoded:await compareRigPixels(original,output)};
    }
    // All decoded comparisons pass before publishing any companion, and the receipt is written last.
    for (const clip of record.clips) {
      const output=path.join(directory,clip.companion.path);await mkdir(path.dirname(output),{recursive:true});
      await copyFile(path.join(temporary,clip.scenario+'.webm'),output);
    }
    await writeFile(path.join(directory,RECEIPT),JSON.stringify(record,null,2)+'\n');
    return record;
  } finally {await rm(temporary,{recursive:true,force:true});}
}

if (process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  if (process.argv[2]==='--record' && process.argv.length===4) {
    const record=await recordRigMedia(root,process.argv[3]);
    console.log(`Recorded ${record.clips.length} lossless VP9 companions; original report/movies unchanged from ${record.producer_revision}.`);
  } else if (process.argv[2]==='--check' && process.argv.length===3) {
    const media=await verifyRigFiles(root,{historical:true,decode:true});
    console.log(`Verified report, all ${media.clips.length} original movies and every decoded companion frame.`);
  } else throw new Error('Use --record <full-producer-sha> or --check.');
}
