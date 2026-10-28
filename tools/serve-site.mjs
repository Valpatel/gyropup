import http from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
const root = path.resolve(import.meta.dirname, '../dist');
const types = {'.html':'text/html; charset=utf-8','.md':'text/markdown; charset=utf-8','.txt':'text/plain; charset=utf-8','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.mp4':'video/mp4','.woff2':'font/woff2','.stl':'application/octet-stream'};
const port = Number(process.env.PORT || 8644);
const server = http.createServer(async (req,res)=>{
  try {
    const pathname = decodeURIComponent(new URL(req.url,'http://localhost').pathname);
    let file = path.resolve(root,'.'+pathname);
    if (!file.startsWith(root+path.sep) && file!==root) throw new Error('Invalid path');
    try { if ((await stat(file)).isDirectory()) file = path.join(file,'index.html'); }
    catch { if (!path.extname(file)) file += '.html'; }
    const data = await readFile(file);
    res.writeHead(200,{'Content-Type':types[path.extname(file)] || 'application/octet-stream'});res.end(req.method==='HEAD'?undefined:data);
  } catch { res.writeHead(404,{'Content-Type':'text/plain'}); res.end('Not found'); }
}).listen(port,'127.0.0.1',()=>console.log(`Gyropup: http://127.0.0.1:${server.address().port}`));
