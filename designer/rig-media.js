// Exact report and clip identities for the small recorded leg-rig gallery.
// Browser and static Markdown use the same published matcher; no simulation runs here.
const REPORT = 'exports/leg/rig-results.json';
const requireIdentity = (ok, message) => { if (!ok) throw new Error(message); };
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

export async function rigDigest(bytes) {
  requireIdentity(!!globalThis.crypto?.subtle, 'This connection cannot verify recorded movie identity.');
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(v => v.toString(16).padStart(2, '0')).join('');
}

export async function prepareRigMedia(reportBytes, record, readClip, {format = 'all'} = {}) {
  requireIdentity(['all','mp4','webm'].includes(format), 'Invalid recorded movie format selection.');
  requireIdentity(record?.schema === 2 && /^[0-9a-f]{40}$/.test(record.producer_revision), 'Recorded movie provenance is unavailable.');
  requireIdentity(record.report?.path === REPORT && /^[0-9a-f]{64}$/.test(record.report.sha256), 'Recorded report identity is invalid.');
  requireIdentity(await rigDigest(reportBytes) === record.report.sha256, 'Recorded movies belong to a different report.');
  const report = JSON.parse(new TextDecoder().decode(reportBytes));
  const scenarios = Object.keys(report.scenarios || {});
  requireIdentity(scenarios.length > 0 && scenarios.every(name => /^[a-z0-9_]+$/.test(name)
    && report.scenarios[name]?.scenario === name), 'Recorded scenario identities are invalid.');
  requireIdentity(Number.isFinite(report.half_mass_kg) && Number.isFinite(report.bus_v), 'Recorded study conditions are unavailable.');
  requireIdentity(Array.isArray(record.clips) && record.clips.length === scenarios.length
    && record.clips.every(clip => clip && typeof clip === 'object')
    && new Set(record.clips.map(clip => clip.scenario)).size === scenarios.length
    && record.clips.every(clip => scenarios.includes(clip.scenario)
      && clip.path === `exports/leg/rig_${clip.scenario}.mp4` && /^[0-9a-f]{64}$/.test(clip.sha256)
      && clip.companion?.path === `exports/leg/rig_${clip.scenario}.webm`
      && clip.companion.source_sha256 === clip.sha256 && /^[0-9a-f]{64}$/.test(clip.companion.sha256)),
  'Recorded movie paths or scenario membership are invalid.');
  const clips = await Promise.all(record.clips.map(async clip => {
    let bytes,companionBytes;
    if (format !== 'webm') {
      bytes = await readClip(clip.path);
      requireIdentity(bytes != null && await rigDigest(bytes) === clip.sha256,
        `Recorded movie identity does not match: ${clip.scenario}.`);
    }
    if (format !== 'mp4') {
      companionBytes = await readClip(clip.companion.path);
      requireIdentity(companionBytes != null && await rigDigest(companionBytes) === clip.companion.sha256,
        `Recorded companion identity does not match: ${clip.scenario}.`);
    }
    return {...clip, bytes, companionBytes, title: report.scenarios[clip.scenario].title || clip.scenario};
  }));
  return {report, revision: record.producer_revision, clips, format};
}

export function mountRigMedia(host, media, {staticRender = false} = {}) {
  const urls = [];
  try {
    const reportURL = `https://github.com/Valpatel/gyropup/blob/${media.revision}/${REPORT}`;
    const avc = media.format === 'all' ? (staticRender || !!host.ownerDocument.createElement('video').canPlayType('video/mp4; codecs="avc1.64001f"')) : media.format === 'mp4';
    const figures = media.clips.map(clip => {
      const original = '../' + clip.path;
      const bytes = avc ? clip.bytes : clip.companionBytes;
      requireIdentity(staticRender || bytes != null, 'The selected recorded movie bytes were not verified.');
      const source = staticRender ? original : URL.createObjectURL(new Blob([bytes], {type: avc ? 'video/mp4' : 'video/webm'}));
      if (!staticRender) urls.push(source);
      return `<figure><video src="${esc(source)}" data-rig-format="${avc ? 'mp4' : 'webm'}" controls loop muted playsinline preload="metadata"></video>`
        + `<figcaption><b>${esc(clip.scenario)}</b> ${esc(clip.title)} · <a href="${esc(original)}">Original movie</a>`
        + ` · <a href="${esc('../' + clip.companion.path)}">VP9 companion</a></figcaption></figure>`;
    }).join('');
    host.innerHTML = `<p data-rig-media-state="verified" style="grid-column:1/-1">Recorded leg simulation · ${esc(media.report.half_mass_kg)} kg · `
      + `${esc(media.report.bus_v)} V. <a href="${reportURL}">Recorded source report</a>. Model prediction, not a hardware test.</p>` + figures;
  } catch (error) { for (const url of urls) URL.revokeObjectURL(url); throw error; }
  return () => { host.replaceChildren(); for (const url of urls) URL.revokeObjectURL(url); };
}
