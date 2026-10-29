// Progress page: the status and log (docs/progress.json, written as the work goes), leg v2 (pictures, the test rig's
// physics, the strength studies with their overload videos and 3D viewer, what to print and what to buy with a picture
// of every part and its alternate sources), the turret on its bench stand (the same for its parts).
import { mountAppNav } from './kit/appnav.js';
import { createLoadingStatus } from './kit/loading.js';
import { createPortalParts } from './portal-parts.js';
import { createDataReader, isRecord } from './kit/portal-data.js';
import { mountStudyMedia, matchingStudyMedia } from './kit/study-media.js';

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const reader=createDataReader(fetch);
const getJson=(url,options={})=>reader.json(url,{validate:isRecord,...options});
const $ = (id) => document.getElementById(id);
const partsUI=createPortalParts($('progress-tools'));
const studyPlayer=mountStudyMedia($('fea-media'));
const tag = (ok, warn) => `<span class="tag ${ok ? 'pass' : warn ? 'warn' : 'fail'}">${ok ? 'PASS' : warn ? 'CLOSE' : 'FAIL'}</span>`;
const LEG = '../exports/leg/';

void mountAppNav({ root: '../', current: 'progress' });

// leg v2: the pictures from cad/build_leg.py
// the test rig (sim/leg_rig.py)
// the joints the whole-leg study bonds, checked on their own (cad/leg_studies.py joint_checks): each check's worst rare
// case against its own target (rolling bearings by their static safety s0 = C0/P0, printed parts and pins by SF)
const JOINT_NAMES = { knee_rear: 'rear knee', knee_front: 'front knee', apex_61812: 'apex 61812s', hub_rear: 'rear hub joint', hub_front: 'front hub joint' };
const jointValue = (j, c) => ({ '6201 s0': () => `${j['6201'].load_n} N`, pin: () => `${j.pin.stress_mpa} MPa`, 'eye pressure': () => `${j.eye_pressure.mpa} MPa`,
  s0: () => `${j.load_n} N`, tipping: () => `${j.out_of_plane_nm} N·m (tips at ${j.tips_at_nm})`, 'dowel bearing': () => `${j.dowel_bearing_mpa} MPa` }[c.check] || (() => ''))();
const jointRows = (J) => {
  const worst = {};
  for (const c of J.checks) { const k = `${c.joint}|${c.check}`; if (!worst[k] || c.sf / c.target < worst[k].sf / worst[k].target) worst[k] = c; }
  return Object.values(worst).map((c) => `<tr><td>${esc(JOINT_NAMES[c.joint]||c.joint)}</td><td>${esc(c.check)} (${esc(c.case)})</td><td>Joint check</td><td data-sort-value="${c.sf}">${c.sf}</td><td data-sort-value="${c.target}">${c.target}</td>`
    + `<td data-sort-value="">${esc(jointValue(J[c.case][c.joint], c))}</td><td>${tag(c.sf >= c.target, c.sf < c.target && c.sf >= 0.8 * c.target)}</td><td></td></tr>`).join('');
};

// strength (cad/leg_studies.py)
// parts lists: a picture of every line (catalog/images.json, tools/part_images.py: product photos, renders of our printed
// parts), its part number and its alternate sources (catalog/alternates.json). A line that names its part in words gets
// its catalogue key from catalog/sourcing.json, which also holds the parts no catalogue file has yet.
let media,mediaPromise;
function loadMedia(){if(!mediaPromise){
mediaPromise=(async () => {
  const [images, alternates, sourcing, index] = await Promise.all(['images', 'alternates', 'sourcing', 'index'].map((f) => getJson(`../catalog/${f}.json`)));
  if(!Array.isArray(index.files))throw new Error('The catalog index has an unexpected format.');
  const items = {};
  for (const list of await Promise.all([...new Set(['hardware.json', ...((index && index.files) || [])])].map((f) => getJson(`../catalog/${f}`,{validate:value=>Array.isArray(value)&&value.every(isRecord)})))) {
    for (const it of list || []) for (const k of [it.key, it.id]) if (k && !items[k]) items[k] = it;
  }
  for (const it of (sourcing && sourcing.parts) || []) for (const k of [it.key, it.id]) if (k && !items[k]) items[k] = { ...it, pending: true };
  return { images: images || {}, alternates: alternates || {}, sourcing: sourcing || {}, items };
})().then(value=>media=value).catch(error=>{mediaPromise=null;throw error;});
}
return mediaPromise;
}
const keysOf = (r) => {
  if (r.media_key) return [r.media_key, ...(r.also || []).map((a) => a.media_key)];
  for (const c of [r.key, r.id]) if (c && media.items[c]) return [c];
  const names = media.sourcing.names || {};
  for (const c of [r.item, r.name, r.for, r.key]) if (c && names[c] !== undefined) return [].concat(names[c]);
  return [];
};
const money = (v) => (v != null ? `$${Number(v).toFixed(2)}` : '—');
// Historical shopping notes store explicit USD text; other formats remain unknown.
const noteUSD=value=>/^~?\$[\d,]+(?:\.\d+)?$/.test(String(value))?Number(String(value).replace(/[~$,]/g,'')):'';
const noPic = new Map();                                  // section -> keys without a picture (none, or it failed to load)
const showMissing=sec=>{const el=$(`${sec}-nopic`),count=noPic.get(sec)?.size||0;if(el)el.textContent=count?`${count} part photos are pending. Supplier and design links remain available.`:'';};
const markMissing=(sec,key,now=false)=>{if(!noPic.has(sec))noPic.set(sec,new Set());noPic.get(sec).add(key);if(now)showMissing(sec);};
window.__thumbMissing=img=>{const a=img.closest('.thumb');markMissing(a.dataset.sec,a.dataset.key,true);a.classList.add('source');a.textContent='View source ↗';};
const thumb=(sec,key,label,small=false)=>{
 const scope=['print','buy'].includes(sec)?'leg':sec.startsWith('turret')?'turret':sec;
 key=media.images[`${scope}/${key}`]?`${scope}/${key}`:key;
 const im=media.images[key],src=im?.path?'../'+im.path:im?.verification?.status==='verified'?im.image_url:null,source=im?.source_url,href=source?(/^(?:[a-z]+:|\/)/i.test(source)?source:'../'+source):(im?.path?'../'+im.path:null),cls=`thumb${small?' sm':''}`;
 if(!src){markMissing(sec,key||label);return href?`<a class="${cls} source" href="${esc(href)}">View source ↗</a>`:`<span class="${cls} unavailable">Photo pending</span>`;}
 return `<a class="${cls}" href="${esc(href||src)}" data-sec="${esc(sec)}" data-key="${esc(key)}" title="${esc(im.kind==='render'?'Rendered from the published CAD':'Product image · '+(im.seller||'supplier'))}"><img src="${esc(src)}" alt="${esc(label||key)}" loading="lazy" onerror="__thumbMissing(this)"></a>`;
};
const partRef = (key, row = {}) => {
  const it = media.items[key] || {};
  const mc = it.vendor === 'McMaster-Carr';
  const pn = it.model || (row.key === key ? row.part_number : null) || null;
  const buy = (it.buy || [])[0] || {};
  const url = mc ? `https://www.mcmaster.com/${it.model}/` : (buy.url || null);
  const seller = mc ? 'McMaster-Carr' : (buy.seller || it.vendor || row.vendor || '');
  const av = (media.images[key] || {}).availability;
  if (!pn && !url) return '<span class="tag warn">TO SOURCE</span>';
  return `${url ? `<a href="${esc(url)}">${esc(pn || 'product page')}</a>` : esc(pn)}<br><span style="color:var(--muted)">${esc(seller)}</span>`
    + `${it.pending ? ' <span class="tag warn" title="chosen in catalog/sourcing.json, not in a catalogue file yet">PROPOSED</span>' : ''}`
    + `${av ? `<span class="avail" title="what the product page said on ${esc(media.images[key].fetched)}">${esc(av)} <span style="color:var(--dim)">(${esc(media.images[key].fetched)})</span></span>` : ''}`;
};
const altList = (key) => {
  const alts = media.alternates[key] || [];
  if (!alts.length) return '<span class="tag fail">NO ALTERNATE</span>';
  const n = alts.filter((a) => a.drop_in).length;
  return `<details class="alts"><summary>${alts.length} alternate${alts.length > 1 ? 's' : ''} · ${n ? `${n} drop-in` : 'none drop-in'}</summary><ul>`
    + alts.map((a) => `<li>${a.drop_in ? '<span class="tag pass">DROP-IN</span>' : '<span class="tag warn">CHANGES</span>'} <b>${esc(a.supplier)}</b> `
      + `${a.url ? `<a href="${esc(a.url)}">${esc(a.part_number || 'product page')}</a>` : esc(a.part_number || '')}`
      + `${a.price ? ` · ${esc(a.price)}` : ''}${a.stock ? ` · <span style="color:var(--mint)">${esc(a.stock)}</span>` : ''}`
      + `${a.changes ? `<div class="chg">${esc(a.changes)}</div>` : ''}<div class="chk">checked ${esc(a.checked || '?')}</div></li>`).join('')
    + '</ul></details>';
};
const RISK = { high: ['fail', 'HARD TO BUY'], medium: ['warn', 'CHECK STOCK'], cost: ['warn', 'CHEAPER OPTION'],
  fit: ['fail', "DOESN'T FIT AS DRAWN"], missing: ['fail', 'PARTS MISSING'], check: ['warn', 'TO CHECK'] };
const riskTag = (key) => {
  const rk = (media.sourcing.risk || {})[key];
  if (!rk) return '';
  const [cls, label] = RISK[rk.level] || ['warn', String(rk.level || 'NOTE').toUpperCase()];
  return `<div class="risk"><span class="tag ${cls}">${label}</span> ${esc(rk.note)}${rk.checked ? ` <span class="chk">(${esc(rk.checked)})</span>` : ''}</div>`;
};
const partRow=(sec,r)=>{
 const keys=keysOf(r),k=keys[0],it=media.items[k]||{},name=r.name||it.name||r.item||r.key||'Part',each=r.price_usd_each??it.price_usd;
 return `<tr data-part-key="buy/${esc(r.identity)}" data-part-label="${esc(name)}"><td>${keys.length?keys.map(x=>thumb(sec,x,name,true)).join(''):thumb(sec,null,name)}</td><td class="part-main"><b>${esc(name)}</b><details><summary>Uses and sourcing notes</summary>${esc(r.for||'')}${keys.map(riskTag).join('')}</details></td><td>${keys.length?keys.map(x=>partRef(x,r)).join('<br>'):'Source pending'}</td><td data-sort-value="${Number.isFinite(r.qty)?r.qty:''}">${esc(r.qty)}</td><td data-sort-value="${each??''}">${money(each)}${each!=null&&r.qty>1?`<small>${money(each*r.qty)} for this line</small>`:''}</td><td>${keys.map(altList).join('')||'No alternate recorded'}</td></tr>`;
};
const partList=(sec,rows)=>{
 const grouped=new Map();
 for(const r of rows){const identity=keysOf(r).join('+')||`${sec}/${r.key||r.item||r.name}`;if(grouped.has(identity)){const existing=grouped.get(identity);existing.qty+=r.qty;existing.for=[existing.for,r.for].filter(Boolean).join('; ');}else grouped.set(identity,{...r,identity});}
 return `<div class="mediasum" id="${sec}-nopic"></div><table class="cmp" data-track="buy" data-label="${sec==='buy'?'Leg parts':'Turret parts'}"><thead><tr><th>Picture</th><th>Part</th><th>Supplier part number</th><th>Quantity</th><th>Unit price</th><th>Alternates</th></tr></thead><tbody>${[...grouped.values()].map(r=>partRow(sec,r)).join('')}</tbody></table>`;
};
const coverage = (rows) => {
  const keys = [...new Set(rows.flatMap(keysOf))];
  const pics = keys.filter(k=>media.images[k]?.path||media.images[k]?.verification?.status==='verified').length;
  const alts = keys.filter((k) => (media.alternates[k] || []).length).length;
  const noKey = rows.filter((r) => !keysOf(r).length).length;
  const hard = keys.filter((k) => ((media.sourcing.risk || {})[k] || {}).level === 'high');
  return `${keys.length} different parts: <b>${pics}</b> with a picture, <b>${alts}</b> with an alternate source`
    + `${noKey ? `, <span class="tag fail">${noKey} WITHOUT A CATALOGUE KEY</span>` : ''}.`
    + `${hard.length ? ` <span class="tag fail">${hard.length} HARD TO BUY</span> Check their sourcing notes.` : ''}`;
};

// what to print and what to buy (cad/build_leg.py)
// parts machined to order from our STEP at an instant price (D40, D46): cad/build_leg.py -> exports/leg/cnc/
const madeToOrder = (rows) => (!rows || !rows.length ? '' : `<h3 style="margin-top:22px">Machined to order</h3>`
  + '<p class="lede">Upload the STEP for the instant price and enter the callouts (threads, fits, tolerances) the order form asks for; the callouts page doubles as the drawing.</p>'
  + '<table class="cmp" data-track="buy" data-label="Leg made parts"><thead><tr><th>Picture</th><th>Part</th><th>Material</th><th>Quantity</th><th>Grams each</th><th>Supplier</th><th>Unit price</th></tr></thead><tbody>'
  + rows.map((r) => `<tr data-part-key="made/leg/${esc(r.key)}" data-part-label="${esc(r.key)}"><td class="th">${thumb('buy', r.key, r.key, true)}</td><td><a href="../${esc(r.step)}">${esc(r.key)}.step</a> · <a href="../exports/leg/cnc/README.md">callouts</a></td>`
    + `<td>${esc(r.material)}</td><td data-sort-value="${r.qty}">${r.qty}</td><td data-sort-value="${r.mass_g_each}">${r.mass_g_each}</td><td>${esc(r.vendor)}<br><span style="color:var(--muted)">backup ${esc(r.backup)}</span></td>`
    + `<td data-sort-value="${r.price_usd_each??r.price_estimate_usd_each??''}">${r.price_usd_each != null ? money(r.price_usd_each) : `<span title="${esc(r.price_note)}">~${money(r.price_estimate_usd_each)} (estimate)</span>`}</td></tr>`).join('')
  + '</tbody></table>');
// the turret on its bench stand (cad/build_turret.py)
const TB = '../exports/turret/bench/';

const validPrint=value=>isRecord(value)&&isRecord(value.parts)&&isRecord(value.by_material)&&Array.isArray(value.too_big);
const updatedIntro=$('updated').innerHTML;
$('progress-loading')?.remove();
window.__portalLoads={};
function sectionLoad(id,target,label,render){
 const host=document.createElement('div');host.dataset.reportStatus=id;$(target).before(host);
 const status=createLoadingStatus(host,{id:'load-'+id,onRetry:retry});let request=0,shown=false;
 async function retry(){
  const own=++request,token=status.begin('Loading '+label.toLowerCase()+'…');updatePageState();
  try{const present=await render(()=>own===request);if(own!==request)return;
   if(present){shown=true;status.ready(token);}else status.unavailable(shown?label+' is unavailable; the previous report remains shown.':label+' has not been published yet.',{token,onRetry:retry});
  }catch(error){if(own===request)status.fail((shown?'The previous report remains shown. ':'')+error.message,{token,onRetry:retry});}
  finally{updatePageState();}
 }
 window.__portalLoads[id]={retry,status};return retry();
}
function updatePageState(){
 const states=Object.values(window.__portalLoads).map(load=>load.status.element.dataset.state);
 const failed=states.includes('error'),pending=states.includes('loading');
 document.body.dataset.ready=states.length&&states.every(state=>state==='ready'||state==='unavailable')?'1':'0';
 document.body.dataset.loadState=pending?'loading':failed?'partial':'ready';
}
await Promise.all([
sectionLoad('progress','status','Progress report',async isCurrent=>{
const prog = await getJson('../docs/progress.json',{optional:false,validate:value=>isRecord(value)&&Array.isArray(value.status)&&Array.isArray(value.log),label:'Progress report'});
if(!isCurrent())return false;
if (prog) {
  $('updated').innerHTML=updatedIntro+` Last update: <b>${esc(prog.updated)}</b>.`;
  $('status').innerHTML = (prog.status || []).map((s) => `<div class="card"><b>${esc(s.title)}</b><div class="k">${esc(s.value)}</div><span>${esc(s.note || '')}</span></div>`).join('');
  $('log').innerHTML = (prog.log || []).slice().reverse().map((e) => `<li><time>${esc(e.time)}</time><b>${esc(e.title)}</b><p>${esc(e.text)}`
    + `${(e.links || []).map((l) => ` <a href="${esc(l.href)}">${esc(l.title)}</a>`).join(' ·')}</p></li>`).join('');
  partsUI.replace($('shop'), prog.shopping ? `<table class="cmp" data-label="Motor order notes"><thead><tr><th>item</th><th>qty</th><th>each</th><th>total</th><th>notes</th></tr></thead><tbody>`
    + prog.shopping.items.map((i) => `<tr><td>${i.href ? `<a href="${esc(i.href)}">${esc(i.item)}</a>` : esc(i.item)}</td><td data-sort-value="${/^\d+$/.test(String(i.qty))?Number(i.qty):''}">${esc(i.qty)}</td><td data-sort-value="${noteUSD(i.each)}">${esc(i.each)}</td><td data-sort-value="${noteUSD(i.total)}">${esc(i.total)}</td><td>${esc(i.notes)}</td></tr>`).join('')
    + `</tbody></table><p class="lede">${esc(prog.shopping.note || '')}</p>` : '');
}


return !!prog;
}),
sectionLoad('leg','leglede','Leg design',async isCurrent=>{
const leg = await getJson(`${LEG}leg.json`,{optional:true,validate:value=>isRecord(value)&&isRecord(value.mass_g)&&Array.isArray(value.leg_range_mm),label:'Leg design'});
if(!isCurrent())return false;
if (leg) {
  const m = leg.mass_g;
  $('leglede').innerHTML = `Two RS-04s 150 mm apart in one printed hip frame drive two upper links; two lower links meet at the wheel's axle.`
    + ` Leg <b>${leg.leg_range_mm[0]}-${leg.leg_range_mm[1]} mm</b> (hip line to axle), track <b>${leg.track_mm_two_legs_back_to_back} mm</b> for two legs back to back,`
    + ` <b>${(m.total / 1000).toFixed(2)} kg</b> per leg (${(m.printed / 1000).toFixed(2)} kg printed).`
    + ` Clashes over the whole range: <b>${leg.clashes ? leg.clashes.filter((c) => c[0] !== 'out of range').length : '—'}</b>.`
    + ` <a href="../exports/leg/leg_stand.step">leg_stand.step</a> (bought parts as envelopes).`;
  const cap = { 'leg-stand-iso': 'Standing, 300 mm', 'leg-stand-outside': 'From outside: the five-bar', 'leg-stand-inside': 'From inside: both motors in the frame',
    'leg-stand-front': 'From the front: the layers', 'leg-exploded': 'Exploded: frame, bearings, links, knee cartridges, wheel',
    'leg-crouch-outside': 'Deepest crouch, 130 mm', 'leg-crouch-iso': 'Crouched', 'leg-tall-outside': 'Tallest, 380 mm' };
  $('leg').innerHTML = (leg.pictures || []).map((f) => `<figure><a href="${LEG}${esc(f)}"><img src="${LEG}${esc(f)}" alt="${esc(f)}"></a>`
    + `<figcaption><b>${esc(cap[f.replace('.png', '')] || f)}</b></figcaption></figure>`).join('');
}


return !!leg;
}),
sectionLoad('rig','riglede','Leg test results',async isCurrent=>{
const rig = await getJson(`${LEG}rig-results.json`,{optional:true,validate:value=>isRecord(value)&&isRecord(value.model)&&isRecord(value.scenarios),label:'Leg test results'});
if(!isCurrent())return false;
if (rig) {
  const S = rig.scenarios;
  $('riglede').innerHTML = `One leg on a vertical rail carrying half the robot (<b>${rig.half_mass_kg} kg</b>), RS-04s capped at <b>${rig.model.leg_cap_nm} N·m</b>`
    + ` (peak ${rig.model.leg_peak_nm}), the stops as stiff as their TPU sleeves. The leg is driven like a RoboMaster balance robot's: a virtual spring on the hip-to-axle line.`;
  // the joints' real forces and the gearbox torque come from every step of the simulation; statics on the axle's peak
  // force (in grey) overstates a landing's knee load about twice: the links' and the body's inertia take the spike
  const jf = (r) => (r.peak_joint_force_n ? Math.round(Math.max(r.peak_joint_force_n.knee_f, r.peak_joint_force_n.knee_r)) : null);
  partsUI.replace($('rigtable'), `<table class="cmp" data-label="Leg test results"><thead><tr><th>scenario</th><th>motor peak</th><th>gearbox</th><th>wheel force</th><th>knee pin</th><th>stop</th><th>leg range</th><th>jump</th></tr></thead><tbody>`
    + Object.values(S).map((r) => `<tr><td><b>${esc(r.scenario)}</b><br><span style="color:var(--muted)">${esc(r.title)}</span></td><td data-sort-value="${r.peak_motor_nm??''}">${r.peak_motor_nm} N·m</td>`
      + `<td data-sort-value="${r.peak_gearbox_nm??''}">${r.peak_gearbox_nm != null ? `${r.peak_gearbox_nm} N·m ${tag(r.peak_gearbox_nm <= rig.model.leg_peak_nm)}` : '—'}</td><td data-sort-value="${r.peak_wheel_force_n??''}">${r.peak_wheel_force_n} N</td>`
      + `<td data-sort-value="${jf(r)??r.peak_knee_pin_n??''}">${jf(r) != null ? `${jf(r)} N <span style="color:var(--muted)">(statics ${Math.round(r.peak_knee_pin_n)})</span>` : `${r.peak_knee_pin_n} N`}</td>`
      + `<td data-sort-value="${r.peak_stop_nm??''}">${r.peak_stop_nm} N·m</td><td>${r.L_range_mm.join('-')} mm</td><td data-sort-value="${r.jump_height_mm??''}">${r.jump_height_mm != null ? r.jump_height_mm + ' mm' : '—'}</td></tr>`).join('')
    + '</tbody></table>');
  $('rig').innerHTML = Object.values(S).map((r) => `<figure><video src="${LEG}rig_${esc(r.scenario)}.mp4" controls loop muted playsinline preload="metadata"></video>`
    + `<figcaption><b>${esc(r.scenario)}</b> ${esc(r.title)}</figcaption></figure>`).join('');
}


return !!rig;
}),
sectionLoad('fea','fea','Structural reports',async isCurrent=>{
const fea = await getJson(`${LEG}fea/summary.json`,{optional:true,validate:value=>isRecord(value)&&Array.isArray(value.results),label:'Structural reports'});
if(!isCurrent())return false;
if (fea) {
  let mediaIndex=null,mediaProblem='';
  try { mediaIndex=await getJson(`${LEG}fea/media.json`,{optional:true,validate:value=>isRecord(value)&&value.schema===1&&isRecord(value.cases),label:'Structural animation metadata'}); }
  catch(error) { mediaProblem=error.message; }
  if(!isCurrent())return false;
  const mediaFor=r=>{try{return matchingStudyMedia(r,mediaIndex);}catch{return null;}};
  const rows = fea.results.map((r) => ({ r, ok: r.safety_factor >= r.target, warn: r.safety_factor < r.target && r.safety_factor >= 0.8 * r.target }));
  const viewerHref = r=>{const file=mediaFor(r)?.fields||r.viewer;return file?`kit/fea.html?case=${encodeURIComponent(`../../${file}`)}&title=${encodeURIComponent(`${r.part} ${r.case}`)}&current=progress`:null;};
  const b = fea.front_link_buckling;
  partsUI.replace($('fea'), `<table class="cmp" data-label="Structural reports"><thead><tr><th>part</th><th>case</th><th>material</th><th>SF</th><th>need</th><th>deflection</th><th></th><th>3D</th></tr></thead><tbody>`
    + rows.map(({ r, ok, warn }, i) => `<tr class="click" data-i="${i}"><td>${esc(r.part)}</td><td>${esc(r.case)}</td><td>${esc(r.material)}</td>`
      + `<td data-sort-value="${r.safety_factor??''}">${r.safety_factor}</td><td data-sort-value="${r.target??''}">${r.target}</td><td data-sort-value="${r.probe_displacement_mm?Math.hypot(...r.probe_displacement_mm):''}">${r.probe_displacement_mm ? Math.hypot(...r.probe_displacement_mm).toFixed(2) : '—'} mm</td><td>${tag(ok, warn)}</td>`
      + `<td>${viewerHref(r) ? `<a class="open3d" href="${esc(viewerHref(r))}" title="Interactive: load slider, hot spots, section cut">open ↗</a>` : '—'}</td></tr>`).join('')
    + (b ? `<tr><td>front lower link</td><td>buckling (${esc(b.note)})</td><td>Structural check</td><td data-sort-value="${b.sf}">${b.sf}</td><td data-sort-value="3">3</td><td data-sort-value="">${b.P_cr_n} N</td><td>${tag(b.sf >= 3)}</td><td></td></tr>` : '')
    + (fea.joints && fea.joints.checks ? jointRows(fea.joints) : '')
    + '</tbody></table>');
  const show = (i) => {
    const r = rows[i].r;
    let media=null,problem=mediaProblem;
    try { media=matchingStudyMedia(r,mediaIndex); } catch(error) { problem=error.message; }
    studyPlayer.show(r,media,{problem});
    const href = viewerHref(r);
    $('feanote').innerHTML = `${href ? `<a class="hud-btn primary" href="${esc(href)}">Open ${esc(r.part)} ${esc(r.case)} in 3D ↗</a> ` : ''}`
      + `${esc(r.part)} ${esc(r.case)}: ${esc(r.load_from)}. `
      + `<b>Safety factor ${esc(r.safety_factor)} / required ${esc(r.target)}${r.safety_factor<r.target?' — below target':''}.</b>`;
    document.querySelectorAll('#fea tr.click').forEach((tr) => tr.classList.toggle('on', +tr.dataset.i === i));
  };
  document.querySelectorAll('#fea tr.click').forEach((tr) => tr.addEventListener('click', (e) => { if (!e.target.closest('a')) show(+tr.dataset.i); }));
  if (rows.length) show(rows.reduce((a, x, i) => (x.r.safety_factor / x.r.target < rows[a].r.safety_factor / rows[a].r.target ? i : a), 0));
}


return !!fea;
}),
sectionLoad('print','printlede','Leg print plan',async isCurrent=>{
const pp = await getJson(`${LEG}print-plan.json`,{optional:true,validate:validPrint,label:'Leg print plan'});
if(!isCurrent())return false;
if (pp) {
  await loadMedia();
  if(!isCurrent())return false;
  const bm = Object.entries(pp.by_material).map(([m, t]) => `${m}: ${(t.grams / 1000).toFixed(2)} kg, ~${Math.round(t.hours)} h, $${Math.round(t.cost_usd)}`).join(' · ');
  $('printlede').innerHTML = `${pp.too_big.length ? `<b class="tag fail">TOO BIG: ${esc(pp.too_big.join(', '))}</b> ` : 'Every part fits the 256 mm bed. '}`
    + `One leg: ~<b>${Math.round(pp.total_hours)} h</b> of printing (${esc(bm)}). Hours are rough.`;
  partsUI.replace($('print'), `<div class="mediasum" id="print-nopic"></div><table class="cmp" data-track="print" data-label="Leg print queue"><thead><tr><th></th><th>part</th><th>material</th><th>qty</th><th>size on the bed</th><th>placement</th><th>g each</th><th>hours (all)</th><th>infill</th><th>how</th></tr></thead><tbody>`
    + Object.entries(pp.parts).sort((a, b) => b[1].hours - a[1].hours).map(([n, r]) => `<tr data-part-key="print/leg/${esc(n)}" data-part-label="${esc(n)}"><td class="th">${thumb('print', n, n, true)}</td><td><a href="${LEG}${esc(n)}.stl">${esc(n)}</a></td><td>${esc(r.material)}</td><td data-sort-value="${r.qty??''}">${r.qty}</td>`
      + `<td>${r.size_mm.join(' × ')}</td><td>${esc(r.placement)}</td><td data-sort-value="${r.grams_each??''}">${r.grams_each}</td><td data-sort-value="${r.hours??''}">${r.hours}</td><td>${esc(r.infill)}</td><td>${esc(r.how)}</td></tr>`).join('') + '</tbody></table>');
  showMissing('print');
}

return !!pp;
}),
sectionLoad('buy','buylede','Leg parts list',async isCurrent=>{
const bom = await getJson(`${LEG}bom.json`,{optional:true,validate:value=>isRecord(value)&&Array.isArray(value.per_leg)&&Array.isArray(value.to_source),label:'Leg parts list'});
if(!isCurrent())return false;
if (bom) {
  await loadMedia();
  if(!isCurrent())return false;
  const mto = bom.made_to_order || [];
  $('buylede').innerHTML = `About <b>$${Math.round(bom.price_usd_per_leg)}</b> per leg for what has a price`
    + (mto.length ? `, plus about <b>$${Math.round(bom.made_to_order_estimate_usd_per_leg)}</b> machined to order (below)` : '') + `. ${coverage(bom.per_leg)}`
    + (bom.to_source.length ? ` <span class="tag warn">TO SOURCE</span> ${esc(bom.to_source.join(', '))}` : ' Every part has a part number.')
    + ' Click a picture for the page it came from; open <b>alternates</b> for other places to buy each part and what would change.';
  partsUI.replace($('buy'), partList('buy', bom.per_leg) + madeToOrder(mto));
  showMissing('buy');
}


return !!bom;
}),
sectionLoad('turret','turretlede','Turret design',async isCurrent=>{
const tb=await getJson(`${TB}bench.json`,{optional:true,validate:value=>isRecord(value)&&Array.isArray(value.stand_mm),label:'Turret design'});
if(!isCurrent())return false;
if (tb) {
  $('turretlede').innerHTML = `The turret (cad/turret.py: a 30-ball hopper over an 8-pocket dial, twin flywheels, a 100 mm barrel that never points above level)`
    + ` on a printed stand (${tb.stand_mm.join(' × ')} mm) with a 24 V inlet, fuse and switch, a USB-CAN adapter for a laptop and a hold-to-run pendant:`
    + ` the turret will not spin up or feed a ball unless the pendant's button is held. <b>${(tb.printed_g / 1000).toFixed(2)} kg</b> printed, ~<b>${Math.round(tb.print_hours)} h</b>`
    + `${tb.too_big?.length ? ` <span class="tag fail">TOO BIG: ${esc(tb.too_big.join(', '))}</span>` : ', every part fits the bed'}.`;
  const caps = { 'turret-bench-level-iso': 'On the bench, level', 'turret-bench-level-front': 'From the front', 'turret-bench-aimed-iso': 'Panned 35°, tilted 20° down' };
  $('turret').innerHTML = (tb.pictures || []).map((f) => `<figure><a href="${TB}${esc(f)}"><img src="${TB}${esc(f)}" alt="${esc(f)}"></a>`
    + `<figcaption><b>${esc(caps[f.replace('.png', '')] || f)}</b></figcaption></figure>`).join('')
    + ['turret.png', 'turret-section.png'].map((f) => `<figure><a href="../exports/turret/${f}"><img src="../exports/turret/${f}" alt="${f}"></a>`
    + `<figcaption><b>${f === 'turret.png' ? 'Every part, labelled' : 'The ball path: hopper, dial, chute, flywheels, barrel'}</b></figcaption></figure>`).join('');
}

return !!tb;
}),
sectionLoad('turretbuy','turretbuylede','Turret parts list',async isCurrent=>{
const tbom=await getJson(`${TB}bom.json`,{optional:true,validate:value=>isRecord(value)&&Array.isArray(value.bench_turret),label:'Turret parts list'});
if(!isCurrent())return false;
if (tbom) {
  await loadMedia();
  if(!isCurrent())return false;
  const rows = tbom.bench_turret;
  // bought parts the turret's CAD draws (exports/turret/turret.json) that its list leaves out
  const tj = await getJson('../exports/turret/turret.json');
  if(!isCurrent())return false;
  const listed = new Set(rows.map((r) => r.for));
  const skip = new Set(media.sourcing.skip || []);
  const drawn = Object.keys((tj && tj.bought) || {}).filter((n) => !listed.has(n) && !skip.has(n));
  const all = [...rows, ...drawn.map((n) => ({ item: n, for: `${n}: drawn in cad/turret.py, not on the bench list yet`, qty: 1 }))];
  $('turretbuylede').innerHTML = `About <b>$${Math.round(tbom.price_usd_known)}</b> for what has a price. ${coverage(all)}`
    + (drawn.length ? ` <span class="tag warn">DRAWN, NOT ON THE LIST</span> ${esc(drawn.join(', '))}.` : '')
    + (tbom.note ? ` ${esc(tbom.note.charAt(0).toUpperCase() + tbom.note.slice(1))}.` : '');
  partsUI.replace($('turretbuy'), partList('turretbuy', all));
  showMissing('turretbuy');
}

return !!tbom;
}),
sectionLoad('turretprint','turretprintlede','Turret print plan',async isCurrent=>{
const tpp=await getJson(`${TB}print-plan.json`,{optional:true,validate:validPrint,label:'Turret print plan'});
if(!isCurrent())return false;
if (tpp) {
  await loadMedia();
  if(!isCurrent())return false;
  $('turretprintlede').innerHTML = `${Object.keys(tpp.parts).length} printed parts for the turret and its stand, ~<b>${Math.round(tpp.total_hours)} h</b> of printing. Hours are rough.`;
  partsUI.replace($('turretprint'), `<div class="mediasum" id="turretprint-nopic"></div><table class="cmp" data-track="print" data-label="Turret print queue"><thead><tr><th></th><th>part</th><th>material</th><th>qty</th><th>size on the bed</th><th>g each</th><th>hours (all)</th><th>how</th></tr></thead><tbody>`
    + Object.entries(tpp.parts).map(([n, r]) => `<tr data-part-key="print/turret/${esc(n)}" data-part-label="${esc(n)}"><td class="th">${thumb('turretprint', n, n, true)}</td><td>${esc(n)}</td><td>${esc(r.material)}</td><td data-sort-value="${r.qty??''}">${r.qty}</td>`
      + `<td>${(r.size_mm || []).join(' × ')}</td><td data-sort-value="${r.grams_each??''}">${r.grams_each}</td><td data-sort-value="${r.hours??''}">${r.hours}</td><td>${esc(r.how)}</td></tr>`).join('') + '</tbody></table>');
  showMissing('turretprint');
}

return !!tpp;
})
]);
updatePageState();
