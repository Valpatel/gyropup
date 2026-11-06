/** Consumer assertions shared by isolated-player and real-hero playback tests. */
import assert from 'node:assert/strict';

export async function assertHighlightControls(page, action, { restart = false } = {}) {
  const controls = await page.locator('.highlight-controls').evaluate(element => [...element.querySelectorAll('button')].map(button => ({
    label: button.getAttribute('aria-label'), text: button.textContent.replace(/\s+/g, ' ').trim(),
    primary: button.classList.contains('highlight-toggle'), restart: button.classList.contains('highlight-restart'),
    hidden: button.hidden, disabled: button.disabled,
    visible: button.getClientRects().length > 0 && getComputedStyle(button).visibility !== 'hidden',
    controls: button.getAttribute('aria-controls'),
  })));
  const primary = controls.filter(button => button.primary);
  assert.equal(primary.length, 1, 'One persistent primary playback control');
  assert.equal(primary[0].visible, true, 'Primary action remains visible');
  assert.equal(primary[0].disabled, false, 'Primary action remains operable');
  assert.equal(primary[0].label, action === 'Try again' ? 'Try loading highlights again' :
    action === 'Play now' ? 'Play highlights while the robot is still loading' : `${action} highlights`);
  assert.equal(primary[0].controls, 'highlight-video');
  const secondary = controls.filter(button => button.restart);
  assert.equal(secondary.length, 1, 'A distinct restart action has one owner');
  assert.equal(secondary[0].label, 'Restart highlights from the beginning');
  assert.equal(secondary[0].visible, restart, 'Restart visibility follows its usefulness');
  assert.equal(secondary[0].hidden, !restart, 'Unavailable restart is removed from keyboard and accessibility navigation');
  assert.equal(secondary[0].disabled, !restart, 'Unavailable restart cannot activate');
  assert.equal(controls.filter(button => button.visible).length, restart ? 2 : 1, 'No duplicate or hidden-but-painted controls');
  assert.equal(await page.locator('#highlight-video').evaluate(video => video.controls), false, 'Only the declared custom controls are shown');
  return controls;
}
