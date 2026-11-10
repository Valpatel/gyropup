/** Browser-serialized observer: retry may briefly have a bodyless document. */
export function currentRobotReady(hash){
  return document.body?.dataset.ready==='1'&&window.__sim?.state?.robot?.presentation?.collectionSha256===hash;
}

/** Logical readiness precedes the product fade and first rendered frame. */
export function currentRobotCanvasReady(hash){
  const sim=window.__sim,robot=sim?.state?.robot,renderer=sim?.stage?.renderer,canvas=renderer?.domElement;
  if(document.body?.dataset.ready!=='1'||robot?.presentation?.collectionSha256!==hash||!canvas?.isConnected)return false;
  const style=getComputedStyle(canvas),rect=canvas.getBoundingClientRect(),draw=renderer.info?.render;
  if(Number(style.opacity)!==1||style.display==='none'||style.visibility!=='visible'||rect.width<=0||rect.height<=0||canvas.width<=0||canvas.height<=0)return false;
  if(!draw||![draw.frame,draw.calls,draw.triangles].every(value=>Number.isFinite(value)&&value>0)||robot.parts?.length!==228)return false;
  let ancestor=robot.group,attached=false; if(!ancestor||!sim.stage.scene)return false;
  while(ancestor){if(!ancestor.visible)return false;if(ancestor===sim.stage.scene)attached=true;ancestor=ancestor.parent;}
  if(!attached)return false;
  return {collectionSha256:robot.presentation.collectionSha256,parts:robot.parts.length,
    opacity:Number(style.opacity),display:style.display,visibility:style.visibility,
    rect:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},buffer:{width:canvas.width,height:canvas.height},
    render:{frame:draw.frame,calls:draw.calls,triangles:draw.triangles}};
}
