import http from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { SITE_CACHE_CONTROL } from './site-cache.mjs';
const root = path.resolve(import.meta.dirname, '../dist');
const types = {'.html':'text/html; charset=utf-8','.md':'text/markdown; charset=utf-8','.txt':'text/plain; charset=utf-8','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.mp4':'video/mp4','.webm':'video/webm','.woff2':'font/woff2','.stl':'application/octet-stream','.wasm':'application/wasm'};
const port = Number(process.env.PORT || 8644);
export function createSiteServer(directory = root) {
return http.createServer(async (req,res)=>{
  try {
    const pathname = decodeURIComponent(new URL(req.url,'http://localhost').pathname);
    let file = path.resolve(directory,'.'+pathname);
    if (!file.startsWith(directory+path.sep) && file!==directory) throw new Error('Invalid path');
    try { if ((await stat(file)).isDirectory()) file = path.join(file,'index.html'); }
    catch { if (!path.extname(file)) file += '.html'; }
    const data = await readFile(file);
    const etag = '"' + createHash('sha256').update(data).digest('hex') + '"';
    const headers = {'Content-Type':types[path.extname(file)] || 'application/octet-stream', 'Cache-Control':SITE_CACHE_CONTROL, ETag:etag};
    if (req.headers['if-none-match'] === etag) { res.writeHead(304, headers); res.end(); return; }
    res.writeHead(200,headers);res.end(req.method==='HEAD'?undefined:data);
  } catch { res.writeHead(404,{'Content-Type':'text/plain'}); res.end('Not found'); }
});
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const server = createSiteServer().listen(port,'127.0.0.1',()=>console.log(`Gyropup: http://127.0.0.1:${server.address().port}`));
}
