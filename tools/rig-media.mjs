/** Record/check existing leg-rig movies against the immutable commit that produced their report.
 * node tools/rig-media.mjs --record <full-producer-sha>   (requires identical working files)
 * node tools/rig-media.mjs --check                      (also verifies historical Git blobs)
 */
import {execFileSync} from 'node:child_process';
import {readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {prepareRigMedia, rigDigest} from '../designer/rig-media.js';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const REPORT = 'exports/leg/rig-results.json', RECEIPT = 'exports/leg/rig-media.json';
const gitBytes = (directory, revision, file) => execFileSync('git', ['show', `${revision}:${file}`], {cwd: directory, maxBuffer: 64 << 20});

export async function verifyRigFiles(directory, {historical = false} = {}) {
  const record = JSON.parse(await readFile(path.join(directory, RECEIPT), 'utf8'));
  const report = await readFile(path.join(directory, REPORT));
  const media = await prepareRigMedia(report, record, file => readFile(path.join(directory, file)));
  if (historical) {
    for (const item of [record.report, ...record.clips]) {
      if (await rigDigest(gitBytes(directory, record.producer_revision, item.path)) !== item.sha256)
        throw new Error(`Recorded producer does not match ${item.path}`);
    }
  }
  return media;
}

export async function recordRigMedia(directory, revision) {
  if (!/^[0-9a-f]{40}$/.test(revision)) throw new Error('Use a full immutable producer commit SHA.');
  const reportBytes = gitBytes(directory, revision, REPORT), report = JSON.parse(reportBytes);
  const scenarios = Object.keys(report.scenarios || {});
  if (!scenarios.length || scenarios.some(name => !/^[a-z0-9_]+$/.test(name))) throw new Error('Invalid producer scenarios.');
  const record = {schema: 1, producer_revision: revision, report: {path: REPORT, sha256: await rigDigest(reportBytes)}, clips: []};
  for (const scenario of scenarios) {
    const file = `exports/leg/rig_${scenario}.mp4`;
    record.clips.push({scenario, path: file, sha256: await rigDigest(gitBytes(directory, revision, file))});
  }
  // Validate the working bytes against the producer before writing anything: this never reseals changed pixels.
  await prepareRigMedia(await readFile(path.join(directory, REPORT)), record, file => readFile(path.join(directory, file)));
  await writeFile(path.join(directory, RECEIPT), JSON.stringify(record, null, 2) + '\n');
  return record;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv[2] === '--record' && process.argv.length === 4) {
    const record = await recordRigMedia(root, process.argv[3]);
    console.log(`Recorded ${record.clips.length} unchanged movies from ${record.producer_revision}.`);
  } else if (process.argv[2] === '--check' && process.argv.length === 3) {
    const media = await verifyRigFiles(root, {historical: true});
    console.log(`Verified report and all ${media.clips.length} movies against producer ${media.revision}.`);
  } else throw new Error('Use --record <full-producer-sha> or --check.');
}
