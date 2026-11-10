/** Browser-serialized observer: retry may briefly have a bodyless document. */
export function currentRobotReady(hash){
  return document.body?.dataset.ready==='1'&&window.__sim?.state?.robot?.presentation?.collectionSha256===hash;
}
