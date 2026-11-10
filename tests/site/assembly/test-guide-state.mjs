import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync}from'node:fs';
import {readLocation,stepFor,validateIndex,matchSnapshot,progressKey,readProgress,saveProgress,writeLocation,snapshotsFor} from '../../../software/site/designer/assembly/state.js';
const read=n=>JSON.parse(readFileSync(new URL('./fixtures/'+n+'.json',import.meta.url)));
const a=read('version-one'),b=read('version-two'),ha='a'.repeat(64),hb='b'.repeat(64);
test('two frozen versions differ in membership, instructions, source and storage identity',()=>{
 assert.notDeepEqual(a.steps[1].parts,b.steps[1].parts);assert.notEqual(a.steps[0].text,b.steps[0].text);assert.notEqual(a.snapshot.source_commit,b.snapshot.source_commit);assert.notEqual(progressKey(a,ha),progressKey(b,hb));
 const values=new Map(),store={getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v)};
 saveProgress(store,a,new Set(['base','cover','foreign']),ha);assert.deepEqual([...readProgress(store,a,ha)],['base','cover']);assert.deepEqual([...readProgress(store,b,hb)],[]);
 const changed=structuredClone(a);changed.steps[0].text='Different instruction, same geometry';assert.equal(changed.model.sha256,a.model.sha256);assert.deepEqual([...readProgress(store,changed,hb)],[]);
});
test('exact WIP, direct step and chapter routes round trip; unavailable choices reject',()=>{
 const wip=JSON.parse(readFileSync(new URL('../../../software/site/assets/build-guides/turret-wip-4866459e2abd/guide.json',import.meta.url)));
 const index=validateIndex(JSON.parse(readFileSync(new URL('../../../software/site/assets/build-guides/index.json',import.meta.url))));
 assert.equal(wip.snapshot.source_commit,'4866459e2abdb6c7f5f25e9448156b6615593499');assert.equal(snapshotsFor(index,'turret').length,1);assert.equal(index.snapshots[0].status,'wip');
 const location={href:'https://gyropup.com/designer/build.html?other=kept',search:''};let url;writeLocation(location,{replaceState:(a,b,c)=>url=c},wip,wip.steps[7]);
 assert.equal(url.searchParams.get('other'),'kept');assert.equal(stepFor(wip,readLocation(url,index)).id,'step-08');
 assert.equal(stepFor(wip,{chapter:'cartridge'}).id,'step-10');
 assert.throws(()=>stepFor(wip,{step:'old-version-step'}));assert.throws(()=>readLocation({search:'?snapshot=invented-release'},index));
});
test('broken storage and stale step IDs do not erase other meanings',()=>{
 assert.deepEqual([...readProgress({getItem(){throw Error('denied')}},a,ha)],[]);
 assert.deepEqual([...readProgress({getItem:()=>'{bad'},a,ha)],[]);
 assert.deepEqual([...readProgress({getItem:()=>JSON.stringify(['base','old'])},a,ha)],['base']);
 assert.throws(()=>saveProgress({setItem(){throw Error('denied')}},a,new Set(['base']),ha));
});
test('index rejects duplicate identities and external/escaping files',()=>{
 const index={schema:'gyropup.build-guides/1',snapshots:[{id:'one',title:'One',status:'wip',file:'one/guide.json',sha256:'a'.repeat(64)}]};
 assert.equal(validateIndex(index),index);
 for(const file of ['https://wrong.test/guide.json','../other.json','//other.test/guide.json']){const x=structuredClone(index);x.snapshots[0].file=file;assert.throws(()=>validateIndex(x));}
 const duplicate=structuredClone(index);duplicate.snapshots.push(duplicate.snapshots[0]);assert.throws(()=>validateIndex(duplicate));
});
test('actual generated guide passes shared reader with cumulative prior chapters; bad ownership rejects',async()=>{
 const {validateGuide}=await import('../../../software/site/designer/kit/assembly/guide.js');
 const base=new URL('../../../software/site/assets/build-guides/turret-wip-4866459e2abd/',import.meta.url),g=JSON.parse(readFileSync(new URL('guide.json',base))),m=JSON.parse(readFileSync(new URL('view.json',base)));
 validateGuide(g,m);assert.ok(g.steps[6].parts.includes('pan_base'));assert.ok(!g.subassemblies[1].parts.includes('pan_base'));assert.ok(g.steps[9].parts.includes('pan_base'));
 const bad=structuredClone(g);bad.steps[6].highlight.push('pan_base');assert.throws(()=>validateGuide(bad,m),/Highlighted subassembly members/);
 const wrongUnits=structuredClone(m);wrongUnits.units='m';assert.throws(()=>validateGuide(g,wrongUnits),/units/);
});

test('index cannot redirect one snapshot identity to another correctly hashed guide',()=>{
 assert.equal(matchSnapshot({id:a.snapshot.id,status:a.snapshot.status},a),a);
 assert.throws(()=>matchSnapshot({id:b.snapshot.id,status:b.snapshot.status},a),/index does not match/);
 assert.throws(()=>matchSnapshot({id:a.snapshot.id,status:'wip'},a),/index does not match/);
});

test('assembly identity filters independently from snapshot revision labels',()=>{const base={schema:'gyropup.build-guides/1',snapshots:[{id:'old',title:'Legacy turret',status:'wip',file:'old/guide.json',sha256:'a'.repeat(64)},{id:'rA',assembly:'robot',title:'Fixture A',status:'wip',file:'rA/guide.json',sha256:'b'.repeat(64)},{id:'rB',assembly:'robot',title:'Fixture B',status:'wip',file:'rB/guide.json',sha256:'c'.repeat(64)}]};const index=validateIndex(base);assert.deepEqual(snapshotsFor(index,'turret').map(x=>x.id),['old']);assert.deepEqual(snapshotsFor(index,'robot').map(x=>x.id),['rA','rB']);assert.equal(readLocation({search:'?snapshot=old&assembly=combined'},index).assembly,'combined');const invalid=structuredClone(base);invalid.snapshots[1].assembly='guessed';assert.throws(()=>validateIndex(invalid));assert.throws(()=>readLocation({search:'?snapshot=old&assembly=guessed'},index));});
