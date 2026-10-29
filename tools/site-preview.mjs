/** One normal preview per host. Temporary test listeners have a bounded lifetime. */
import path from 'node:path';
import {realpath, access} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';

export const SHARED_PORT = 8899;
export const STATUS_PATH = '/_gyropup/preview';
export const MAX_TEMPORARY_MS = 30 * 60 * 1000;

export async function inspectPreview(port = SHARED_PORT) {
  const response = await fetch(`http://127.0.0.1:${port}${STATUS_PATH}`, {signal: AbortSignal.timeout(1500), redirect: 'error'});
  if (!response.ok) throw new Error('No managed Gyropup preview at the shared address.');
  const text = await response.text();
  if (text.length > 8192) throw new Error('Invalid preview status.');
  const value = JSON.parse(text);
  if (value?.schema !== 'gyropup-preview/1' || !Number.isSafeInteger(value.pid) || value.pid <= 0 ||
      !path.isAbsolute(value.directory || '') || !path.isAbsolute(value.repository || '') ||
      value.url !== `http://127.0.0.1:${port}` || value.temporary !== false) {
    throw new Error('The shared address belongs to an unrelated server; leave it running.');
  }
  return value;
}

export async function startPreview({createServer, directory, repository, port = SHARED_PORT,
  temporary = false, ttlMs = MAX_TEMPORARY_MS, parentPid = process.ppid}) {
  if (temporary && (!Number.isSafeInteger(parentPid) || parentPid <= 0)) throw new Error('Invalid temporary preview parent PID.');
  if (temporary && process.ppid !== parentPid) throw new Error('Temporary preview parent exited before startup.');
  directory = await realpath(directory);
  await access(path.join(directory, 'index.html'));
  if (!Number.isInteger(port) || port < 0 || port > 65535 || (!temporary && port === 0)) throw new Error('Invalid preview port.');
  if (temporary && (!Number.isFinite(ttlMs) || ttlMs <= 0 || ttlMs > MAX_TEMPORARY_MS)) throw new Error('Temporary preview lifetime must be between 0 and 1800 seconds.');
  const metadata = {schema:'gyropup-preview/1', pid:process.pid, repository, directory, temporary,
    startedAt:new Date().toISOString(), expiresAt:temporary ? new Date(Date.now() + ttlMs).toISOString() : null};
  const server = createServer(directory, metadata);
  try {
    await new Promise((resolve, reject) => {
      server.once('error', reject);
      server.listen(port, '127.0.0.1', () => { server.removeListener('error', reject); resolve(); });
    });
  } catch (error) {
    if (error.code !== 'EADDRINUSE' || temporary) throw error;
    let current;
    try { current = await inspectPreview(port); }
    catch { throw new Error(`Port ${port} is occupied by an unrecognized server. Leave it running; do not choose another persistent port.`); }
    if (current.repository !== repository || current.directory !== directory) {
      throw new Error(`The shared preview already serves ${current.directory} at ${current.url} (PID ${current.pid}). Use that checkout, or coordinate with its owner and stop it before switching. No second server was started.`);
    }
    console.log(`Reusing Gyropup: ${current.url} (PID ${current.pid}, ${current.directory})`);
    return {reused:true, metadata:current};
  }
  metadata.url = `http://127.0.0.1:${server.address().port}`;
  let timer, parentWatch, closing = false;
  const stop = () => {
    if (closing) return;
    closing = true;
    clearTimeout(timer); clearInterval(parentWatch);
    server.close(); server.closeAllConnections();
  };
  const onSignal = () => stop();
  process.once('SIGINT', onSignal); process.once('SIGTERM', onSignal);
  server.once('close', () => {
    clearTimeout(timer); clearInterval(parentWatch);
    process.removeListener('SIGINT', onSignal); process.removeListener('SIGTERM', onSignal);
  });
  if (temporary) {
    timer = setTimeout(stop, ttlMs);
    parentWatch = setInterval(() => { if (process.ppid !== parentPid) stop(); }, 250);
  }
  console.log(`Gyropup: ${metadata.url} (PID ${metadata.pid}, ${directory}${temporary ? ', temporary until ' + metadata.expiresAt : ', shared preview'})`);
  return {server, metadata, stop, reused:false};
}

export async function previewCLI(createServer, root, args = process.argv.slice(2), initialParentPid = process.ppid) {
  if (args.length === 1 && args[0] === '--status') {
    console.log(JSON.stringify(await inspectPreview(), null, 2));
    return;
  }
  let temporary = process.env.PORT === '0', ttlMs = MAX_TEMPORARY_MS;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--ephemeral') temporary = true;
    else if (args[i] === '--ttl-seconds') ttlMs = Number(args[++i]) * 1000;
    else throw new Error('Usage: node tools/serve-site.mjs [--status | --ephemeral [--ttl-seconds N]]');
  }
  if (!temporary && ttlMs !== MAX_TEMPORARY_MS) throw new Error('--ttl-seconds requires --ephemeral.');
  const port = Number(process.env.PORT ?? (temporary ? 0 : SHARED_PORT));
  if (!temporary && port !== SHARED_PORT) throw new Error(`Persistent previews use port ${SHARED_PORT}. Reuse it; tests may use --ephemeral with cleanup.`);
  const repository = execFileSync('git', ['-C', path.dirname(root), 'rev-parse', '--path-format=absolute', '--git-common-dir'], {encoding:'utf8'}).trim();
  const parentPid = Number(process.env.GYROPUP_PREVIEW_PARENT_PID ?? initialParentPid);
  return startPreview({createServer, directory:root, repository:await realpath(repository), port, temporary, ttlMs, parentPid});
}
