import assert from 'node:assert/strict';
import test from 'node:test';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {createDataReader,validateSTLBytes} from '../designer/kit/portal-data.js';

test('HTTP readers bound both headers and body without disguising absent data', {timeout:5000}, async()=>{
  let bodyStarted=false;
  const server=createServer((request,response)=>{
    if(request.url==='/headers')return;
    if(request.url==='/body'){bodyStarted=true;response.writeHead(200,{'Content-Type':'application/json'});response.flushHeaders();response.write('{"pending":');return;}
    if(request.url==='/missing'){response.writeHead(404);response.end('Not published');return;}
    if(request.url==='/failure'){response.writeHead(503);response.end('Unavailable');return;}
    response.writeHead(200,{'Content-Type':'application/json'});response.end(request.url==='/html'?'<html>Not JSON</html>':'{"ready":true}');
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base=`http://127.0.0.1:${server.address().port}`,reader=createDataReader();
  try{
    assert.deepEqual(await reader.json(base+'/valid'),{ready:true});
    assert.equal(await reader.json(base+'/missing',{optional:true}),null);
    await assert.rejects(reader.json(base+'/missing'),/HTTP 404/);
    await assert.rejects(reader.json(base+'/failure',{optional:true}),/HTTP 503/);
    await assert.rejects(reader.json(base+'/html'),/could not be read/);
    await assert.rejects(reader.json(base+'/headers',{timeout:150,label:'Headers'}),/Headers: the request timed out/);
    await assert.rejects(reader.json(base+'/body',{timeout:150,label:'Body'}),/Body: the request timed out/);
    assert.equal(bodyStarted,true,'The body timeout occurs after actual response headers and partial JSON');
  }finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

test('STL admission agrees with the renderer before any parser allocation',async()=>{
  const file=await readFile(new URL('../exports/sim/turret_box/barrel.stl',import.meta.url));
  assert.doesNotThrow(()=>validateSTLBytes(file.buffer.slice(file.byteOffset,file.byteOffset+file.byteLength)));
  for(const source of [' '.repeat(80)+'solid invalid\nendsolid invalid\n','SOLID invalid\n'+' '.repeat(100),'solid empty\nendsolid empty','<html>'+'.'.repeat(100)]){
    assert.throws(()=>validateSTLBytes(new TextEncoder().encode(source).buffer),/not STL|not STL geometry/);
  }
  const forged=new ArrayBuffer(84);new DataView(forged).setUint32(80,0xffffffff,true);
  assert.throws(()=>validateSTLBytes(forged),/not STL geometry/);
});
