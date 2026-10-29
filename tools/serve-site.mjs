import http from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { SITE_CACHE_CONTROL } from './site-cache.mjs';
const root = path.resolve(import.meta.dirname, '../dist');
const types = {'.html':'text/html; charset=utf-8','.md':'text/markdown; charset=utf-8','.txt':'text/plain; charset=utf-8','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.webp':'image/webp','.mp4':'video/mp4','.webm':'video/webm','.woff2':'font/woff2','.stl':'application/octet-stream','.wasm':'application/wasm'};
export function createSiteServer(directory = root, preview = null) {
return http.createServer(async (req,res)=>{
  try {
    const pathname = decodeURIComponent(new URL(req.url,'http://localhost').pathname);
    if (preview && pathname === '/_gyropup/preview') {
      if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405); res.end(); return; }
      res.writeHead(200, {'Content-Type':'application/json', 'Cache-Control':'no-store'});
      res.end(req.method === 'HEAD' ? undefined : JSON.stringify(preview)); return;
    }
    let file = path.resolve(directory,'.'+pathname);
    if (!file.startsWith(directory+path.sep) && file!==directory) throw new Error('Invalid path');
    try { if ((await stat(file)).isDirectory()) file = path.join(file,'index.html'); }
    catch { if (!path.extname(file)) file += '.html'; }
    const data = await readFile(file);
    const etag = '"' + createHash('sha256').update(data).digest('hex') + '"';
    const headers = {'Content-Type':types[path.extname(file)] || 'application/octet-stream', 'Cache-Control':SITE_CACHE_CONTROL, ETag:etag, 'Accept-Ranges':'bytes'};
    if (req.headers['if-none-match'] === etag) { res.writeHead(304, headers); res.end(); return; }
    // Seeking/replaying MP4 in WebKit requires the same byte-range behavior as
    // static production hosting. Ignore unsupported multi-ranges and validators.
    const range = req.method === 'GET' && (!req.headers['if-range'] || req.headers['if-range'] === etag)
      ? /^bytes=(\d*)-(\d*)$/.exec(req.headers.range?.trim() || '') : null;
    if (range && (range[1] || range[2])) {
      const start = range[1] ? Number(range[1]) : Math.max(0, data.length - Number(range[2]));
      const end = range[1] && range[2] ? Math.min(Number(range[2]), data.length - 1) : data.length - 1;
      if (start >= data.length || end < start) {
        res.writeHead(416, {...headers, 'Content-Range':`bytes */${data.length}`, 'Content-Length':0});res.end();return;
      }
      const body = data.subarray(start, end + 1);
      res.writeHead(206, {...headers, 'Content-Range':`bytes ${start}-${end}/${data.length}`, 'Content-Length':body.length});
      res.end(body);return;
    }
    res.writeHead(200,{...headers,'Content-Length':data.length});res.end(req.method==='HEAD'?undefined:data);
  } catch { res.writeHead(404,{'Content-Type':'text/plain'}); res.end('Not found'); }
});
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const {previewCLI} = await import('./site-preview.mjs');
  try { await previewCLI(createSiteServer, root); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}
