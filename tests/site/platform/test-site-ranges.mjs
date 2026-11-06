/** Local media seeking must use actual HTTP byte ranges, as production does. */
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createSiteServer} from './serve-site.mjs';

test('media GET, HEAD, seek ranges and cache validators',async()=>{
 const root=await mkdtemp(join(tmpdir(),'gyropup-range-'));
 await writeFile(join(root,'clip.mp4'),Buffer.from('0123456789'));
 const server=createSiteServer(root);
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const url=`http://127.0.0.1:${server.address().port}/clip.mp4`;
 try{
  const full=await fetch(url),etag=full.headers.get('etag');
  assert.equal(full.status,200);assert.equal(await full.text(),'0123456789');
  assert.equal(full.headers.get('content-type'),'video/mp4');
  assert.equal(full.headers.get('accept-ranges'),'bytes');
  const head=await fetch(url,{method:'HEAD',headers:{Range:'bytes=2-4'}});
  assert.equal(head.status,200);assert.equal(head.headers.get('content-length'),'10');assert.equal(await head.text(),'');
  for(const [range,body,contentRange] of [
   ['bytes=0-1','01','bytes 0-1/10'],['bytes=4-','456789','bytes 4-9/10'],
   ['bytes=-3','789','bytes 7-9/10'],['bytes=7-100','789','bytes 7-9/10'],
   ['bytes=-100','0123456789','bytes 0-9/10']]){
   const response=await fetch(url,{headers:{Range:range}});
   assert.equal(response.status,206);assert.equal(response.headers.get('content-range'),contentRange);
   assert.equal(response.headers.get('content-length'),String(body.length));assert.equal(await response.text(),body);
  }
  for(const range of ['bytes=10-','bytes=-0','bytes=8-3']){
   const response=await fetch(url,{headers:{Range:range}});
   assert.equal(response.status,416);assert.equal(response.headers.get('content-range'),'bytes */10');assert.equal(await response.text(),'');
  }
  for(const range of ['bytes=0-1,4-5','nonsense','bytes=-']){
   const response=await fetch(url,{headers:{Range:range}});
   assert.equal(response.status,200);assert.equal(await response.text(),'0123456789');
  }
  const cached=await fetch(url,{headers:{Range:'bytes=0-1','If-None-Match':etag}});
  assert.equal(cached.status,304);assert.equal(await cached.text(),'');
  const valid=await fetch(url,{headers:{Range:'bytes=0-1','If-Range':etag}});
  assert.equal(valid.status,206);assert.equal(await valid.text(),'01');
  const stale=await fetch(url,{headers:{Range:'bytes=0-1','If-Range':'"old"'}});
  assert.equal(stale.status,200);assert.equal(await stale.text(),'0123456789');
 }finally{await new Promise(resolve=>server.close(resolve));await rm(root,{recursive:true,force:true});}
});
