// Existing feature suites exercise an acknowledged research session. The separate
// prototype-notice suite covers fresh entry, explicit acknowledgement and storage failures.
export async function acknowledgePrototypeNotice(contextOrPage) {
  await contextOrPage.addInitScript(() => {
    sessionStorage.setItem('gyropup.prototype-notice', '2026-10-29-v1');
  });
}
