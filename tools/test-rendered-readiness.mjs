/** Shared native stylesheet and actual-text font readiness; callers own navigation, core and media checks. */
export async function installRenderedReadiness(context) {
  await context.addInitScript(() => {
    window.__emptySpaceStylesheets = new WeakMap();
    const record = (event, state) => {
      const element = event.target;
      if (element?.localName === 'style' || (element?.localName === 'link' && element.relList.contains('stylesheet'))) window.__emptySpaceStylesheets.set(element, state);
    };
    document.addEventListener('load', event => record(event, 'loaded'), true);
    document.addEventListener('error', event => record(event, 'error'), true);
  });
}

export async function waitForRenderedText(page) {
  // Native stylesheet load includes its imports and works for CSS whose rules are opaque to this origin.
  await page.waitForFunction(() => {
    const states = window.__emptySpaceStylesheets;
    if (!states) throw new Error('Stylesheet readiness observer is missing');
    return [...document.querySelectorAll('link[rel~="stylesheet"], style')].every(element => {
      if (element.disabled || (element.media && !matchMedia(element.media).matches)) return true;
      const state = states.get(element);
      if (state === 'error') throw new Error(`Stylesheet failed to load: ${element.href || 'inline imports'}`);
      // Inline rules are parsed synchronously; importing styles and linked sheets require their real load event.
      return element.localName === 'style' && !/@import/i.test(element.textContent) ? !!element.sheet : state === 'loaded';
    });
  }, null, { timeout: 30000 });
  // FontFaceSet.ready can wait for document load even when only an unrelated image is pending.
  // Load the actual rendered text fonts explicitly, including the characters selecting Unicode subsets.
  await page.evaluate(() => {
    const state = window.__renderedTextFonts = { done: false, error: null, faces: [] };
    const used = new Map(), walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const element = node.parentElement;
      if (!node.textContent.trim() || !element?.getClientRects().length) continue;
      const style = getComputedStyle(element);
      if (style.visibility === 'hidden' || style.display === 'none') continue;
      const font = style.font || `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
      if (!used.has(font)) used.set(font, new Set());
      for (const character of node.textContent) used.get(font).add(character);
    }
    Promise.all([...used].map(([font, characters]) => document.fonts.load(font, [...characters].join(''))))
      .then(results => { state.faces = [...new Set(results.flat())]; state.done = true; }, error => { state.error = String(error.message || error); });
  });
  await page.waitForFunction(() => {
    const state = window.__renderedTextFonts;
    if (state?.error) throw new Error(`Rendered font failed: ${state.error}`);
    const faces = [...document.fonts, ...(state?.faces || [])];
    const failed = faces.find(face => face.status === 'error');
    if (failed) throw new Error(`Rendered font face failed: ${failed.family}`);
    // FontFaceSet.status can remain loading solely because the document has an unrelated pending image.
    return state?.done && state.faces.every(face => face.status === 'loaded') && !faces.some(face => face.status === 'loading');
  }, null, { timeout: 30000 });
}
