// Pure visibility oracle plus a serializable passive DOM collector. No scrolling here.
export function viewportSupport(s){
 const reasons=[],v=s.viewport,roots=s.ancestors.filter(a=>a.role==='viewport'),root=roots[0];
 if(s.documentMode!=='CSS1Compat'||s.scrollingElement!=='HTML')reasons.push('unsupported document/root scrolling mode');
 if(roots.length!==1||root?.tagName!=='HTML'||root.overflowX!=='hidden'||root.overflowY!=='auto')reasons.push('unsupported root overflow profile/body propagation');
 if(!(v.clientWidth>0&&v.clientHeight>0&&v.clientWidth<=v.width&&v.clientHeight<=v.height))reasons.push('invalid root viewport dimensions');
 const visual=v.visualViewport;
 if(!visual||visual.scale!==1||visual.left!==0||visual.top!==0||Math.abs(visual.width-v.clientWidth)>1||Math.abs(visual.height-v.clientHeight)>1)reasons.push('unsupported visual viewport/zoom/offset');
 return {pass:reasons.length===0,reasons};
}
export function clippingRegion(s){
 const support=viewportSupport(s);if(!support.pass)return null;
 const region={left:0,right:s.viewport.clientWidth,top:Math.max(0,s.navBottom),bottom:s.viewport.clientHeight};
 for(const a of s.ancestors){
  // Root overflow belongs to this viewport; its document box is telemetry only.
  // Every ordinary ancestor, including BODY, retains its actual padding-box clip.
  const clip=a.role==='viewport'?{left:0,top:0,right:s.viewport.clientWidth,bottom:s.viewport.clientHeight}:a.clip;
  if(a.clipX){region.left=Math.max(region.left,clip.left);region.right=Math.min(region.right,clip.right);}
  if(a.clipY){region.top=Math.max(region.top,clip.top);region.bottom=Math.min(region.bottom,clip.bottom);}
 }
 return region;
}
export function framing(s){
 const support=viewportSupport(s);if(!support.pass)return {pass:false,status:'unsupported',reasons:support.reasons,region:null};
 const region=clippingRegion(s),h=s.header,identity=s.identity;
 const vertical=r=>r.height>0&&r.top>=region.top-1&&r.bottom<=region.bottom+1;
 const intersects=r=>r.width>0&&Math.min(r.right,region.right)>Math.max(r.left,region.left)+2;
 const textVisible=identity?.textRects.some(r=>r.height>0&&r.bottom>region.top&&r.top<region.bottom&&intersects(r));
 const reasons=[];
 if(!(region.right>region.left&&region.bottom>region.top))reasons.push('empty clipped viewport');
 if(!vertical(h)||!intersects(h))reasons.push('identity header outside clipped viewport');
 if(!textVisible)reasons.push('no main-part identity text visible');
 if(!s.headerHit)reasons.push('header hit test is occluded');
 if(!s.identityHit)reasons.push('identity hit test is occluded');
 return {pass:reasons.length===0,status:reasons.length?'invalid-framing':'available',reasons,region};
}
export function horizontalOffsets(s){return [['window',s.viewport.scrollX],...s.ancestors.map(a=>[a.key,a.scrollLeft])];}

// Evaluated against the selected real table. Reads only; no app/bootstrap data writes.
export function collectGeometry(table,expectedHeader){
 if(!table.isConnected)throw Error('Target table disconnected');
 const rect=e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height};};
 const ancestors=[];
 for(let e=table.parentElement,n=0;e;e=e.parentElement,n++){
  const style=getComputedStyle(e),r=rect(e),role=e===document.documentElement?'viewport':'element',clip=role==='viewport'?{left:0,top:0,right:document.documentElement.clientWidth,bottom:document.documentElement.clientHeight}:{left:r.left+e.clientLeft,top:r.top+e.clientTop,right:r.left+e.clientLeft+e.clientWidth,bottom:r.top+e.clientTop+e.clientHeight};
  ancestors.push({role,tagName:e.tagName,key:n+':'+e.tagName+'#'+e.id+'.'+String(e.className),rect:r,clip,clipX:/^(auto|scroll|hidden|clip)$/.test(style.overflowX),clipY:/^(auto|scroll|hidden|clip)$/.test(style.overflowY),overflowX:style.overflowX,overflowY:style.overflowY,scrollTop:e.scrollTop,scrollLeft:e.scrollLeft,scrollHeight:e.scrollHeight,clientHeight:e.clientHeight,scrollWidth:e.scrollWidth,clientWidth:e.clientWidth});
 }
 const headerElement=table.querySelector('thead th.cad-part-identity');
 if(!headerElement)throw Error('Missing source Part identity header');
 if(expectedHeader&&headerElement!==expectedHeader){const error=Error('Pinned header was replaced');error.name='TargetChangedError';throw error;}
 const visibleRows=[...table.tBodies[0].rows].filter(r=>!r.hidden&&!r.hasAttribute('data-fixed'));
 const cells=visibleRows.slice(0,3).map(row=>{
  const cell=row.querySelector('td.cad-part-identity');if(!cell)throw Error('Missing main identity cell');
  const text=cell.querySelector('b')||cell;
  const range=document.createRange();range.selectNodeContents(text);
  return {id:row.dataset.partKey,element:cell,rect:rect(cell),textRects:[...range.getClientRects()].map(r=>({left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height}))};
 });
 const navBottom=document.querySelector('.appnav')?.getBoundingClientRect().bottom||0;
 const region={left:0,right:document.documentElement.clientWidth,top:Math.max(0,navBottom),bottom:document.documentElement.clientHeight};
 for(const a of ancestors){if(a.clipX){region.left=Math.max(region.left,a.clip.left);region.right=Math.min(region.right,a.clip.right);}if(a.clipY){region.top=Math.max(region.top,a.clip.top);region.bottom=Math.min(region.bottom,a.clip.bottom);}}
 const sample=(element,r)=>{
  const left=Math.max(region.left,r.left),right=Math.min(region.right,r.right),top=Math.max(region.top,r.top),bottom=Math.min(region.bottom,r.bottom);
  if(right-left<=2||bottom-top<=2)return {pass:false,point:null};
  const point={x:(left+right)/2,y:(top+bottom)/2},hit=document.elementFromPoint(point.x,point.y);
  return {pass:Boolean(hit&&(element===hit||element.contains(hit))),point,hit:hit?{tag:hit.tagName,id:hit.id,class:String(hit.className)}:null};
 };
 const identity=cells.find(c=>c.textRects.some(r=>r.bottom>region.top&&r.top<region.bottom&&r.right>region.left&&r.left<region.right))||cells[0];
 const textRect=identity?.textRects.find(r=>r.bottom>region.top&&r.top<region.bottom&&r.right>region.left&&r.left<region.right);
 const header=rect(headerElement),headerProbe=sample(headerElement,header),identityProbe=identity&&textRect?sample(identity.element,textRect):{pass:false};
 const box=e=>e?{rect:rect(e),scrollTop:e.scrollTop,scrollLeft:e.scrollLeft,scrollHeight:e.scrollHeight,clientHeight:e.clientHeight}:null;
 return {atMs:performance.now(),documentMode:document.compatMode,documentId:performance.timeOrigin,target:{headerPinned:Boolean(expectedHeader),sameHeader:!expectedHeader||headerElement===expectedHeader,tableConnected:table.isConnected,headerConnected:headerElement.isConnected,sameDocument:table.ownerDocument===document&&headerElement.ownerDocument===document},url:location.href,viewport:{width:innerWidth,height:innerHeight,clientWidth:document.documentElement.clientWidth,clientHeight:document.documentElement.clientHeight,scrollX,scrollY,visualViewport:visualViewport?{left:visualViewport.offsetLeft,top:visualViewport.offsetTop,width:visualViewport.width,height:visualViewport.height,scale:visualViewport.scale}:null},navBottom,root:box(document.documentElement),body:box(document.body),scrollingElement:document.scrollingElement?.tagName,detailsOpen:document.querySelector('#build-details').open,panel:table.closest('[data-build-panel]')?.dataset.buildPanel,table:rect(table),header,identity:identity?{id:identity.id,rect:identity.rect,textRects:identity.textRects}:null,firstRows:cells.map(({element,...data})=>data),ancestors,headerHit:headerProbe.pass,identityHit:identityProbe.pass,headerProbe,identityProbe};
}

// Same horizontal edge contract used by the actual public grid measurement.
export function gridAlignment(actual){
 const reasons=[];if(actual.overflow!==false)reasons.push('document horizontal overflow');
 if(!actual.columns?.length)reasons.push('missing columns');
 for(const col of actual.columns??[]){if(!(col.width>0)||!col.cells?.length)reasons.push('zero/missing header or body width');for(const cell of col.cells??[])if(!(cell.width>0&&Math.abs(cell.left)<1&&Math.abs(cell.right)<1))reasons.push('header/body edge mismatch');}
 return {pass:reasons.length===0,reasons};
}
