import assert from 'node:assert/strict';
import {test, before, after} from 'node:test';
import {mkdtemp, mkdir, writeFile, cp, rm} from 'node:fs/promises';
import {spawn, execFileSync} from 'node:child_process';
import {once} from 'node:events';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

let directory, driver, cli, a, b;
const children = new Set();
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(check, message) {
  const deadline = Date.now() + 5000;
  while (Date.now() < deadline) { if (await check()) return; await delay(25); }
  throw new Error(message);
}
async function freePort() {
  const server = http.createServer(); server.listen(0, '127.0.0.1'); await once(server, 'listening');
  const port = server.address().port; await new Promise(resolve => server.close(resolve)); return port;
}
function child(file, env = {}, args = []) {
  const p = spawn(process.execPath, [file, ...args], {env:{...process.env, ...env}, stdio:['ignore','pipe','pipe']});
  children.add(p); p.output = ''; p.done = false;
  p.stdout.on('data', data => { p.output += data; }); p.stderr.on('data', data => { p.output += data; });
  p.on('exit', () => { p.done = true; children.delete(p); });
  p.on('error', error => { p.output += error.message; p.done = true; });
  return p;
}
async function ready(p) {
  await until(() => p.output.includes('Gyropup: http:') || p.done, 'preview did not announce readiness');
  assert.equal(p.done, false, p.output);
  return p.output.match(/http:\/\/127\.0\.0\.1:\d+/)[0];
}
async function stopped(p) { await until(() => p.done, 'preview did not stop'); }
async function stop(p) { if (!p.done) { p.kill('SIGTERM'); await stopped(p); } }
const envFor = (port, root = a, extra = {}) => ({PORT:String(port), ROOT:root, REPOSITORY:directory, ...extra});

before(async () => {
  directory = await mkdtemp(path.join(os.tmpdir(), 'gyropup-preview-test-'));
  a = path.join(directory, 'a'); b = path.join(directory, 'b');
  for (const [root, text] of [[a,'checkout A'],[b,'checkout B']]) {
    await mkdir(root); await writeFile(path.join(root, 'index.html'), text);
  }
  driver = path.join(directory, 'driver.mjs');
  await writeFile(driver, `import {createSiteServer} from ${JSON.stringify(pathToFileURL(path.join(import.meta.dirname,'serve-site.mjs')).href)};
import {startPreview} from ${JSON.stringify(pathToFileURL(path.join(import.meta.dirname,'site-preview.mjs')).href)};
try { await startPreview({createServer:createSiteServer, directory:process.env.ROOT,
repository:process.env.REPOSITORY, port:Number(process.env.PORT), temporary:process.env.TEMPORARY==='1',
ttlMs:Number(process.env.TTL || 1800000)}); } catch (error) { console.error(error.message); process.exitCode=1; }
`);
  cli = path.join(directory, 'cli'); await mkdir(path.join(cli,'tools'), {recursive:true});
  await mkdir(path.join(cli,'dist')); await writeFile(path.join(cli,'dist','index.html'),'CLI fixture');
  for (const file of ['serve-site.mjs','site-preview.mjs','site-cache.mjs']) await cp(path.join(import.meta.dirname,file),path.join(cli,'tools',file));
  execFileSync('git',['init','-q',cli]);
});
after(async () => {
  await Promise.all([...children].map(stop));
  await rm(directory,{recursive:true,force:true});
});

test('same checkout reuses the incumbent and a different checkout cannot replace it', async () => {
  const port = await freePort(), first = child(driver, envFor(port)), url = await ready(first);
  try {
    const status = await (await fetch(url+'/_gyropup/preview')).json();
    assert.equal(status.pid,first.pid); assert.equal(status.directory,a);
    const again = child(driver,envFor(port)); await stopped(again);
    assert.equal(again.exitCode,0,again.output); assert.match(again.output,/Reusing Gyropup/);
    const different = child(driver,envFor(port,b)); await stopped(different);
    assert.equal(different.exitCode,1); assert.match(different.output,/already serves/);
    assert.equal(await (await fetch(url)).text(),'checkout A');
    assert.equal((await fetch(url+'/_gyropup/preview',{method:'POST'})).status,405);
  } finally { await stop(first); }
  const next = child(driver,envFor(port,b));
  try { assert.equal(await (await fetch(await ready(next))).text(),'checkout B'); }
  finally { await stop(next); }
});

test('concurrent launches leave exactly one listening process', async () => {
  const port = await freePort(), racers = Array.from({length:5},()=>child(driver,envFor(port)));
  try {
    await until(()=>racers.filter(p=>!p.done).length===1 && racers.some(p=>p.output.includes('Gyropup: http:')), 'concurrent launch did not converge');
    const winner = racers.find(p=>!p.done);
    assert.equal((await (await fetch(`http://127.0.0.1:${port}/_gyropup/preview`)).json()).pid,winner.pid);
    for (const p of racers.filter(p=>p!==winner)) assert.equal(p.exitCode,0,p.output);
  } finally { await Promise.all(racers.map(stop)); }
});

test('an unrelated port owner is never stopped or reused', async () => {
  const server = http.createServer((req,res)=>res.end('unrelated'));
  server.listen(0,'127.0.0.1'); await once(server,'listening'); const port=server.address().port;
  try {
    const p=child(driver,envFor(port)); await stopped(p);
    assert.equal(p.exitCode,1); assert.match(p.output,/unrecognized server/);
    assert.equal(await (await fetch(`http://127.0.0.1:${port}`)).text(),'unrelated');
  } finally { server.closeAllConnections(); await new Promise(resolve=>server.close(resolve)); }
});

test('a bounded temporary server expires even while polled', async () => {
  const p=child(driver,envFor(0,a,{TEMPORARY:'1',TTL:'650'})), url=await ready(p);
  const poll=setInterval(()=>fetch(url).catch(()=>{}),50);
  try { await stopped(p); assert.equal(p.exitCode,0,p.output); await assert.rejects(fetch(url)); }
  finally { clearInterval(poll); await stop(p); }
});

test('temporary server exits when its actual launching parent disappears', async () => {
  const ownerFile=path.join(directory,'owner.mjs');
  await writeFile(ownerFile,`import {spawn} from 'node:child_process'; spawn(process.execPath,[${JSON.stringify(driver)}],{stdio:'inherit',env:process.env});`);
  const owner=child(ownerFile,envFor(0,a,{TEMPORARY:'1',TTL:'10000'})), url=await ready(owner);
  try {
    await stop(owner);
    await until(async()=>{try{await fetch(url);return false;}catch{return true;}},'orphan preview still accepts connections');
  } finally { await stop(owner); }
});

test('CLI rejects arbitrary persistent ports and supports PORT=0 test cleanup', async () => {
  const script=path.join(cli,'tools','serve-site.mjs');
  const wrong=child(script,{PORT:String(await freePort())}); await stopped(wrong);
  assert.equal(wrong.exitCode,1); assert.match(wrong.output,/Persistent previews use port 8899/);
  const temporary=child(script,{PORT:'0'}); await ready(temporary); await stop(temporary);
  const tooLong=child(script,{PORT:'0'},['--ttl-seconds','1801']); await stopped(tooLong);
  assert.equal(tooLong.exitCode,1); assert.match(tooLong.output,/between 0 and 1800/);
});

test('CLI fixed-port ephemeral mode preserves CI startup and signal cleanup', async () => {
  const port=await freePort(), p=child(path.join(cli,'tools','serve-site.mjs'),{PORT:String(port)},['--ephemeral']);
  const url=await ready(p); assert.equal(url,`http://127.0.0.1:${port}`);
  await stop(p); await assert.rejects(fetch(url));
});
