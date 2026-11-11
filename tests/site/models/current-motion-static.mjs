/** The owned static motion fixture does not implement the kit development poller. */
export function prepareStaticMotionDocument(ownedOrigin) {
  if (globalThis.origin !== ownedOrigin) return;
  window.__cadagentLive = true;
  window.sessionStorage.setItem('gyropup.prototype-notice','2026-10-29-v1');
  window.localStorage.setItem('gyropup.probe','off');
  window.localStorage.setItem('gyropup-sfx','0');
}

export function isStaticMotionChangeRequest(url, ownedOrigin) {
  const request = new URL(url);
  return request.origin === ownedOrigin && request.pathname === '/_cadagent/changes';
}
