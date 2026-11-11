import test from 'node:test';
import assert from 'node:assert/strict';
import {framing,horizontalOffsets,clippingRegion,viewportSupport,gridAlignment} from './clip-geometry.mjs';
import {readFileSync} from 'node:fs';
const rect=(left,top,width,height)=>({left,top,right:left+width,bottom:top+height,width,height});
function fixture(){return {documentMode:'CSS1Compat',scrollingElement:'HTML',viewport:{width:1280,height:900,clientWidth:1280,clientHeight:900,scrollX:0,visualViewport:{left:0,top:0,width:1280,height:900,scale:1}},navBottom:64,header:rect(100,120,180,44),identity:{textRects:[rect(100,180,160,20)]},headerHit:true,identityHit:true,ancestors:[{key:'panel',role:'element',clipX:true,clipY:true,clip:rect(30,100,1200,700),scrollLeft:0},{key:'root',role:'viewport',tagName:'HTML',overflowX:'hidden',overflowY:'auto',clipX:true,clipY:true,clip:rect(0,-1890,1280,900),scrollLeft:0}]};}
test('valid desktop header and identity inside every clip pass',()=>assert.equal(framing(fixture()).pass,true));
test('positive-size aligned boxes below a nested planner clip are rejected',()=>{const s=fixture();s.header=rect(100,830,180,44);s.identity.textRects=[rect(100,880,160,20)];assert.equal(framing(s).pass,false);});
test('nested table wrapper clipping is independent from root viewport',()=>{const s=fixture();s.ancestors.push({key:'table',clipX:true,clipY:true,clip:rect(30,170,1200,480),scrollLeft:0});assert.equal(framing(s).pass,false);});
test('offscreen or appnav-covered positive header is rejected',()=>{for(const top of [-200,10,950]){const s=fixture();s.header=rect(100,top,180,44);assert.equal(framing(s).pass,false);}});
test('real header/identity hit occlusion and missing visible text are rejected',()=>{for(const key of ['headerHit','identityHit']){const s=fixture();s[key]=false;assert.equal(framing(s).pass,false);}const s=fixture();s.identity.textRects=[rect(100,820,100,20)];assert.equal(framing(s).pass,false);});
test('phone overflow may preserve a visible sticky Part identity',()=>{const s=fixture();s.viewport.width=320;s.viewport.clientWidth=320;s.viewport.visualViewport.width=320;s.header=rect(0,120,120,44);s.identity.textRects=[rect(12,180,100,20)];s.ancestors[0].clip=rect(0,100,320,700);assert.equal(framing(s).pass,true);});
test('horizontal offsets compare every ancestor and window, not only table wrapper',()=>{const a=fixture(),b=fixture();assert.deepEqual(horizontalOffsets(a),horizontalOffsets(b));b.ancestors[0].scrollLeft=12;assert.notDeepEqual(horizontalOffsets(a),horizontalOffsets(b));});

const retained=JSON.parse(readFileSync(new URL('fixtures/v2-geometry.json',import.meta.url)));
// V2 did not record compatMode/role: explicit profile annotation only, never a claim it did.
function annotated(g){const s=structuredClone(g);s.documentMode='CSS1Compat';for(const a of s.ancestors){a.tagName=a.key.split(':')[1].split('#')[0];a.role=a.tagName==='HTML'?'viewport':'element';}const root=s.ancestors.find(a=>a.role==='viewport');s.viewport.clientWidth=root.clientWidth;s.viewport.clientHeight=root.clientHeight;return s;}
test('actual retained V2 rows keep both genuine nested clipping failures after root correction',()=>{
 const expected=[[2487.875,900],[1240.875,454.8125]];
 retained.snapshots.forEach((row,index)=>{const s=annotated(row.geometry),region=clippingRegion(s);assert.deepEqual([region.top,region.bottom],expected[index]);assert.ok(s.header.top>region.bottom);assert.equal(framing(s).pass,false);});
});
test('actual negative root document offsets never become viewport bottom coordinates',()=>{
 for(const row of retained.snapshots){const s=annotated(row.geometry),root=s.ancestors.find(a=>a.role==='viewport');assert.equal(root.clip.bottom,900-s.viewport.scrollY);const before=clippingRegion(s);root.clip.bottom=-9999;root.rect.top=-9999;assert.deepEqual(clippingRegion(s),before);}
});
test('controlled visible target passes with retained negative root offset while ordinary clips remain',()=>{const s=fixture();assert.equal(s.ancestors[1].clip.bottom,-990);assert.equal(framing(s).pass,true);});
test('ordinary BODY clipping is never dropped with root viewport correction',()=>{const s=fixture();s.ancestors.push({key:'body',role:'element',tagName:'BODY',clipX:true,clipY:true,clip:rect(0,0,1280,150),scrollLeft:0});assert.equal(framing(s).pass,false);assert.equal(clippingRegion(s).bottom,150);});
test('unsupported document, overflow propagation, zoom and viewport profiles fail closed',()=>{
 for(const change of [s=>s.documentMode='BackCompat',s=>s.scrollingElement='BODY',s=>s.ancestors[1].overflowX='visible',s=>s.viewport.visualViewport.scale=2,s=>s.viewport.visualViewport.left=1,s=>s.viewport.visualViewport=null,s=>s.viewport.clientHeight=0]){const s=fixture();change(s);assert.equal(viewportSupport(s).pass,false);assert.equal(framing(s).status,'unsupported');}
});

test('positive actual-edge contract accepts aligned visible-width cells',()=>assert.equal(gridAlignment({overflow:false,columns:[{width:150,cells:[{width:150,left:0,right:0}]}]}).pass,true));
test('seeded 12px header translation fails the actual public alignment oracle',()=>assert.equal(gridAlignment({overflow:false,columns:[{width:150,cells:[{width:150,left:12,right:12}]}]}).pass,false));
test('equal zero-width hidden-table deltas never count as alignment',()=>assert.equal(gridAlignment({overflow:false,columns:[{width:0,cells:[{width:0,left:0,right:0}]}]}).pass,false));
