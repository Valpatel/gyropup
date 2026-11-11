// Existing feature suites exercise an acknowledged research session. The separate
// prototype-notice suite covers fresh entry, explicit acknowledgement and storage failures.
export async function acknowledgePrototypeNotice(contextOrPage,intendedURL=process.env.SITE_URL) {
  const intendedOrigin=intendedURL?new URL(intendedURL).origin:null;
  await contextOrPage.addInitScript(expectedOrigin=>{
    // Init scripts also run on opaque initial/about:blank documents and child frames.
    // Read no storage there, or on another HTTP origin. Matching-origin failures
    // remain errors: an unavailable store must not be silently acknowledged.
    const actualOrigin=globalThis.origin;
    if(!/^https?:$/.test(location.protocol)||!actualOrigin||actualOrigin==='null'
        ||(expectedOrigin&&actualOrigin!==expectedOrigin))return;
    sessionStorage.setItem('gyropup.prototype-notice','2026-10-29-v1');
  },intendedOrigin);
}
