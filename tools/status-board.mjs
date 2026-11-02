/** The design status board: one panel a subsystem, every number read from a committed record when the site is built.
 * tools/build-site.mjs writes it into the landing page and Progress (at their <!-- status-board --> markers) and
 * publishes the same data as /site/status.json. tools/test-status-board.mjs recomputes the numbers from the records on
 * its own, so a board that disagrees with its records fails CI.
 *
 * Honest by construction: a below-target study is amber, one under 1.0 (or a fix the records ask for) is red, and
 * anything with no committed measurement is a grey "not yet measured" state. A record that is missing shows as missing.
 * Numbers and the words beside them are built from the records; what is typed in is which record answers which
 * question, and the plain-language name of each check.
 */
import { execFileSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
/** "1 Nov 2026" from an ISO date, in the date's own offset (git's committer date). */
export const shortDate = iso => { const [y, m, d] = iso.slice(0, 10).split('-').map(Number); return `${d} ${MONTHS[m - 1]} ${y}`; };
/** The notebook page the build renders a Markdown source to (tools/build-site.mjs pagePath). */
export const docPage = file => `/site/pages/${file.toLowerCase().replace(/[^a-z0-9]+/g, '-')}.html`;
const num = (v, digits = 2) => Number(v).toFixed(digits).replace(/\.?0+$/, '');
/** Kilograms: two decimals, trailing zeros dropped, but always one (37.0, 36.77). */
const kg = v => { const t = num(v); return t.includes('.') ? t : `${t}.0`; };
const plural = (n, one, many = one + 's') => `${n} ${n === 1 ? one : many}`;

/** Reads records under `root`. `git` is false when the history is unavailable (a shallow clone). */
export function createReader(root, { git = true } = {}) {
  const abs = p => path.join(root, p);
  return {
    root,
    exists: p => existsSync(abs(p)),
    text: p => readFileSync(abs(p), 'utf8'),
    json: p => JSON.parse(readFileSync(abs(p), 'utf8')),
    /** The files in a directory whose names match `pattern`, sorted, as repository paths. */
    list: (dir, pattern) => readdirSync(abs(dir)).filter(f => pattern.test(f)).sort().map(f => `${dir}/${f}`),
    /** The newest commit that touched any of `paths`: { date, commit } or null without history. */
    changed(paths) {
      if (!git) return null;
      const out = execFileSync('git', ['log', '-1', '--format=%cI %H', '--', ...paths], { cwd: root }).toString().trim();
      if (!out) return null;
      const [date, commit] = out.split(' ');
      return { date, commit };
    },
  };
}

/** True when the checkout's history is cut short, so git dates would be wrong. */
export function shallowHistory(root) {
  try { return execFileSync('git', ['rev-parse', '--is-shallow-repository'], { cwd: root }).toString().trim() === 'true'; } catch { return true; }
}

// --- What each record says --------------------------------------------------------------------------------------

/** FEA studies against each record's own verdict. A study under 1.0 on its governing safety factor is red. */
export function feaCount(summary) {
  const results = Array.isArray(summary.results) ? summary.results : Object.values(summary.results);
  const out = { studies: results.length, pass: 0, below: 0, under1: 0, worst: null };
  for (const r of results) {
    const ok = r.ok ?? r.pass;
    const sf = r.sf_by_part ?? r.verdict_sf ?? r.safety_factor;
    const target = r.target ?? r.target_sf;
    if (ok) { out.pass++; continue; }
    if (sf < 1) out.under1++; else out.below++;
    // The worst: the lowest safety factor among those under 1.0 if any, else the smallest margin to target.
    const rank = x => x.sf < 1 ? [0, x.sf] : [1, x.sf / x.target];
    const [a, b] = [rank({ sf, target }), out.worst && rank(out.worst)];
    if (!b || a[0] < b[0] || (a[0] === b[0] && a[1] < b[1])) out.worst = { part: r.part, case: r.case, sf, target };
  }
  return out;
}

/** cad-agent gate verdict files: pass, pass with a warning, fail. */
export function gateCount(records) {
  const out = { gates: records.length, pass: 0, warn: 0, fail: 0, names: {} };
  for (const g of records) { out[g.status === 'pass' ? 'pass' : g.status === 'warn' ? 'warn' : 'fail']++; out.names[g.gate] = g.status; }
  return out;
}

/** The insert-joint inventory's verdicts for the joints of some assemblies, and its open findings by level. */
export const JOINT_LEVELS = ['ok', 'note', 'check', 'owner', 'fix'];
export function jointCount(inventory, assemblies) {
  const joints = inventory.joints.filter(j => assemblies.includes(j.assembly));
  const ids = new Set(joints.map(j => j.id));
  const verdicts = Object.fromEntries(JOINT_LEVELS.map(l => [l, 0]));
  for (const j of joints) verdicts[j.verdict]++;
  const findings = { fix: 0, owner: 0, check: 0 };
  for (const f of inventory.findings) if (ids.has(f.joint)) findings[f.level]++;
  return { joints: joints.length, inserts: joints.reduce((n, j) => n + (j.qty_robot || 0), 0), verdicts, findings };
}

/** A measurement sheet: rows, and the rows with any measured value. A measured value is a cell in a column with a unit
 * (…_mm, …_n, …_nm, …_g, …_deg, …_mpa, …_c, …_s), other than the drawn (cad_/nominal_) values the sheet starts with. */
export const MEASURED_UNIT = /_(mm|um|n|nm|g|kg|deg|mpa|kn|c|s|ms|v|a|ma|w|rpm|hz|pct|ohm|mohm)$/;
const NOT_MEASURED = /^(cad_|nominal|calculated_|predicted_|expected_|target_|measurement_uncertainty)/;
/** Columns of a measurement sheet that hold a reading. */
export const measuredColumns = head => head.map(h => MEASURED_UNIT.test(h) && !NOT_MEASURED.test(h));
/** CSV rows, honouring double quotes (a note may hold a comma). */
export function csvRows(text) {
  const rows = [[]];
  let cell = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) { if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; } else if (c === '"') quoted = false; else cell += c; continue; }
    if (c === '"') quoted = true;
    else if (c === ',') { rows.at(-1).push(cell); cell = ''; }
    else if (c === '\n' || c === '\r') { if (c === '\r' && text[i + 1] === '\n') i++; rows.at(-1).push(cell); cell = ''; rows.push([]); }
    else cell += c;
  }
  rows.at(-1).push(cell);
  return rows.filter(r => r.some(v => v.trim() !== ''));
}
export function sheetCount(csv) {
  const [head, ...rows] = csvRows(csv.trim());
  const measured = measuredColumns(head);
  return { rows: rows.length, columns: measured.filter(Boolean).length, measured: rows.filter(r => r.some((v, i) => measured[i] && v.trim() !== '')).length };
}

/** The leg's pre-print screen (research/leg-preprint): the across-the-layers check and the printed press fits. */
export function screenCount(screen) {
  const layers = { rows: screen.layers.rows.length, pass: 0, below: 0, under1: 0 };
  for (const r of screen.layers.rows) { if (r.ok) layers.pass++; else if (r.layer_sf < 1) layers.under1++; else layers.below++; }
  const fits = { rows: screen.fits.rows.length, tight: 0, coupon: 0 };
  for (const r of screen.fits.rows) { if (/too tight/.test(r.verdict)) fits.tight++; else fits.coupon++; }
  return { layers, fits, coupons: screen.coupons.map(c => ({ id: c.id, name: c.name, sheet: c.sheet })), status: screen.status };
}

/** A print plan: parts, the ones that fit the bed, hours and grams. */
export function printCount(plan) {
  const parts = Object.values(plan.parts);
  return { parts: parts.length, prints: parts.reduce((n, p) => n + (p.qty ?? 1), 0), fit: parts.filter(p => p.fits).length, hours: plan.total_hours, grams: plan.total_grams, bed: plan.bed_mm };
}

// --- The panels --------------------------------------------------------------------------------------------------

/** A meter's bar: segments in a fixed order, each { k, n }; `of` is the whole. */
const bar = (of, segments) => ({ of, segments: segments.filter(s => s.n > 0) });
const SOURCE = (file, label = path.posix.basename(file)) => ({ href: '/' + file, label });

function feaMeter(r, file, what) {
  const s = r.json(file), c = feaCount(s);
  const parts = [];
  if (c.below) parts.push(`${c.below} below target`);
  if (c.under1) parts.push(`${c.under1} under 1.0`);
  return {
    id: 'fea', label: 'Strength studies', value: `${c.pass} of ${c.studies}`, unit: 'meet their own target',
    state: c.under1 ? 'fail' : c.below ? 'warn' : 'pass',
    bar: bar(c.studies, [{ k: 'pass', n: c.pass }, { k: 'warn', n: c.below }, { k: 'fail', n: c.under1 }]),
    note: parts.length ? `${parts.join(', ')}; ${c.worst.sf < 1 ? 'lowest' : 'least margin'}: ${c.worst.part.replace(/_/g, ' ')} ${c.worst.case}, ${num(c.worst.sf)} against ${Number(c.worst.target).toFixed(1)}` : `${what}, all at or above target`,
    source: SOURCE(file), data: c,
  };
}

function jointMeter(r, assemblies) {
  const file = 'research/insert-joints/joints.json';
  const inventory = r.json(file), c = jointCount(inventory, assemblies);
  const v = c.verdicts;
  return {
    id: 'joints', label: 'Insert joints', value: `${c.joints}`, unit: `joint ${c.joints === 1 ? 'family' : 'families'}, ${plural(c.inserts, 'insert')}`,
    state: v.fix ? 'fail' : v.owner ? 'warn' : v.check ? 'unknown' : 'pass',
    bar: bar(c.joints, [{ k: 'pass', n: v.ok }, { k: 'note', n: v.note }, { k: 'unknown', n: v.check }, { k: 'warn', n: v.owner }, { k: 'fail', n: v.fix }]),
    note: [v.fix && `${v.fix} to fix`, v.owner && `${v.owner} owner’s call`, v.check && `${v.check} to check at assembly`, v.note && `${v.note} noted`, v.ok && `${v.ok} clear`].filter(Boolean).join(' · ') + ` (${inventory.status.split(':')[0]})`,
    source: SOURCE(file), data: c,
  };
}

function sheetMeter(r, files, label, what) {
  const counts = files.map(f => sheetCount(r.text(f)));
  const rows = counts.reduce((n, c) => n + c.rows, 0), measured = counts.reduce((n, c) => n + c.measured, 0);
  return {
    id: 'bench', label, value: `${measured} of ${rows}`, unit: 'rows measured',
    state: measured === rows ? 'pass' : measured ? 'warn' : 'unknown',
    bar: bar(rows, [{ k: 'pass', n: measured }, { k: 'unknown', n: rows - measured }]),
    note: measured ? `${what}: ${rows - measured} rows still blank` : `No row filled in yet: ${what}`,
    source: SOURCE(files[0], files.length > 1 ? `${files.length} measurement sheets` : path.posix.basename(files[0])), data: { rows, measured, files },
  };
}

/** `released`: true or false from a release record, or null when the subsystem has no release record. */
function printMeter(r, file, released) {
  const c = printCount(r.json(file));
  const bed = Array.isArray(c.bed) ? c.bed.join(' x ') : c.bed;
  return {
    id: 'print', label: 'Print plan', value: `${c.parts}`, unit: `${c.parts === 1 ? 'design' : 'designs'}, ${plural(c.prints, 'print')} · ${num(c.hours, 0)} h · ${num(c.grams / 1000, 1)} kg`,
    state: released ? 'pass' : 'unknown',
    bar: bar(c.parts, [{ k: released ? 'pass' : 'unknown', n: c.fit }, { k: 'fail', n: c.parts - c.fit }]),
    note: `${c.fit === c.parts ? `All ${c.parts}` : `${c.fit} of ${c.parts}`} fit the ${bed} mm bed · ${released === null ? 'no print release recorded' : released ? 'released for print' : 'not released for print'}`,
    source: SOURCE(file), data: { ...c, released },
  };
}

function massMeter({ label, kg: mass, limit, file, basis, note }) {
  return {
    id: 'mass', label, value: `${kg(mass)} kg`, unit: `of ${kg(limit)} kg`,
    state: mass <= limit ? 'pass' : 'fail',
    bar: bar(limit, [{ k: mass <= limit ? 'pass' : 'fail', n: Math.min(mass, limit) }]),
    note: note || `${basis}: ${mass <= limit ? `${kg(limit - mass)} kg under` : `${kg(mass - limit)} kg over`}`,
    source: SOURCE(file), data: { kg: mass, limit },
  };
}

const GATE_NAMES = { 'turret-path': 'ball path', 'turret-ammo': 'ammo range', 'dossier-lint': 'dossier lint' };

/** Every panel, in a fixed order. Each lists the records it reads (its "changed" date is the newest of them). */
export function collectStatus(r) {
  const massRecord = r.json('exports/body/mass.json'), mass = massRecord.P3;
  // D72's product ceiling, from the decision's own words ("100 lb (45.359237 kg)").
  const d72 = r.text('docs/decisions.yaml').match(/- id: D72\n[\s\S]*?\((\d+(?:\.\d+)?) kg\)/);
  if (!d72) throw new Error('docs/decisions.yaml: D72 no longer states the ceiling in kg');
  const ceiling = Number(d72[1]);
  const inventory = 'research/insert-joints/joints.json';
  const panels = [];

  // Leg: the strength studies, the pre-print screen, the inventory's leg joints, the print plan and the bench sheets.
  {
    const records = ['exports/leg/fea/summary.json', inventory, 'exports/leg/print-plan.json', 'exports/leg/rs04-fit-job', 'exports/body/mass.json'];
    const meters = [feaMeter(r, 'exports/leg/fea/summary.json', 'leg studies')];
    const screenFile = 'research/leg-preprint/screen.json';
    if (r.exists(screenFile)) {
      records.push('research/leg-preprint');
      const s = screenCount(r.json(screenFile));
      meters.push({
        id: 'layers', label: 'Across the layers', value: `${s.layers.pass} of ${s.layers.rows}`, unit: 'load cases pass the layer check',
        state: s.layers.under1 ? 'fail' : s.layers.below ? 'warn' : 'pass',
        bar: bar(s.layers.rows, [{ k: 'pass', n: s.layers.pass }, { k: 'warn', n: s.layers.below }, { k: 'fail', n: s.layers.under1 }]),
        note: `The pre-print screen: ${s.layers.under1} cases under 1.0 where the layers could peel apart, ${s.layers.below} below target`,
        source: SOURCE(screenFile), data: s.layers,
      });
      meters.push({
        id: 'fits', label: 'Press fits, as printed', value: `${s.fits.tight} of ${s.fits.rows}`, unit: 'too tight as drawn',
        state: s.fits.tight ? 'fail' : 'unknown',
        bar: bar(s.fits.rows, [{ k: 'fail', n: s.fits.tight }, { k: 'unknown', n: s.fits.coupon }]),
        note: `${s.fits.coupon} more decided by the bore coupon (${s.coupons[0]?.id}), which is not printed yet`,
        source: SOURCE(screenFile), data: s.fits,
      });
    } else {
      meters.push({ id: 'layers', label: 'Pre-print screen', value: '—', unit: 'no record yet', state: 'unknown', bar: bar(1, [{ k: 'unknown', n: 1 }]), note: 'No pre-print screen in this revision (research/leg-preprint/screen.json)', source: null, data: null });
    }
    meters.push(jointMeter(r, ['leg']));
    meters.push(massMeter({ label: 'Mass, each leg', kg: mass.gate.leg_each_kg, limit: mass.budget.legs_kg_each, file: 'exports/body/mass.json', basis: 'D71’s leg budget, P3 ledger' }));
    const job = r.json('exports/leg/rs04-fit-job/job.json');
    meters.push(printMeter(r, 'exports/leg/print-plan.json', job.qualification.full_leg_print_released === true));
    const sheets = ['exports/leg/rs04-fit-job/measurements.csv'];
    if (r.exists(screenFile)) for (const c of screenCount(r.json(screenFile)).coupons) sheets.push(`research/leg-preprint/sheets/${c.sheet}`);
    meters.push(sheetMeter(r, sheets, 'Bench coupons', sheets.length > 1 ? `the RS-04 seat coupon and coupons ${screenCount(r.json(screenFile)).coupons.map(c => c.id).join(', ')}` : 'the RS-04 seat coupon'));
    panels.push({ id: 'leg', name: 'Leg', blurb: 'Five-bar leg, both motors in the body', image: { src: '/exports/leg/leg-stand-iso.png', alt: 'The five-bar leg standing, rendered from its CAD', width: 1600, height: 1100 },
      model: '/exports/leg/leg_stand.step', docs: 'research/leg-preprint/README.md', records, meters });
  }

  // Turret: cad-agent's gates, its strength studies, its joints (with its bench stand) and the shaft-survey gauge.
  {
    const gateFiles = r.list('exports/gates', /\.json$/);
    const gates = gateFiles.map(f => r.json(f));
    const g = gateCount(gates);
    const records = ['exports/gates', 'exports/turret/fea/summary.json', inventory, 'exports/turret/print/print.json', 'exports/turret/shaft-survey-fit-job'];
    const print = r.json('exports/turret/print/print.json');
    panels.push({ id: 'turret', name: 'Turret', blurb: 'Foam-ball launcher on its pan and tilt', image: { src: '/exports/turret/turret.png', alt: 'The foam-ball turret, rendered from its CAD', width: 1600, height: 1150 },
      model: null, docs: 'docs/turret-sections.md', records, gates: gates.map((x, i) => ({ name: GATE_NAMES[x.gate] || x.gate, status: x.status, file: r.exists(gateFiles[i].replace(/\.json$/, '.md')) ? gateFiles[i].replace(/\.json$/, '.md') : gateFiles[i] })), meters: [
        {
          id: 'gates', label: 'cad-agent gates', value: `${g.pass + g.warn} of ${g.gates}`, unit: 'pass',
          state: g.fail ? 'fail' : g.warn ? 'warn' : 'pass',
          bar: bar(g.gates, [{ k: 'pass', n: g.pass }, { k: 'warn', n: g.warn }, { k: 'fail', n: g.fail }]),
          note: `${g.warn} of the passes carry a warning; ${g.fail} to fix: ${gates.filter(x => x.status === 'fail').map(x => GATE_NAMES[x.gate] || x.gate).join(', ')}`,
          source: { href: '/exports/gates/', label: `${g.gates} gate records` }, data: g,
        },
        feaMeter(r, 'exports/turret/fea/summary.json', 'turret studies'),
        jointMeter(r, ['turret', 'turret stand']),
        {
          id: 'print', label: 'Print kit', value: print.publication.status, unit: 'estimates',
          state: print.publication.status === 'current' ? 'pass' : 'unknown',
          bar: bar(1, [{ k: print.publication.status === 'current' ? 'pass' : 'unknown', n: 1 }]),
          note: print.publication.reason.split('. ').slice(-1)[0].replace(/\.$/, ''),
          source: SOURCE('exports/turret/print/print.json'), data: print.publication,
        },
        sheetMeter(r, ['exports/turret/shaft-survey-fit-job/measurements.csv'], 'Shaft-survey gauge', 'the flywheel motor shaft gauge (sliced, not printed)'),
      ] });
  }

  // Body: its strength studies, the joint and connectivity checks, the inventory's body joints, mass and print plan.
  {
    const integrity = r.json('exports/body/integrity.json').summary;
    const conn = r.json('exports/body/gates/connectivity-P3.json');
    const records = ['exports/body/fea/summary.json', 'exports/body/integrity.json', 'exports/body/gates', inventory, 'exports/body/mass.json', 'exports/body/print-plan.json'];
    const withProblems = integrity.joints_with_problems.length;
    panels.push({ id: 'body', name: 'Body', blurb: 'Aluminium box, battery bay and compute', image: { src: '/exports/body/body-p3-iso.png', alt: 'The body at stage P3 with its shell, rendered from its CAD', width: 1600, height: 1100 },
      model: null, docs: 'docs/body-sections.md', records, meters: [
        feaMeter(r, 'exports/body/fea/summary.json', 'body studies'),
        {
          id: 'integrity', label: 'Screwed joints', value: `${integrity.joints - withProblems} of ${integrity.joints}`, unit: `joints clear (${integrity.screws} screws)`,
          state: withProblems || integrity.clashes ? 'fail' : conn.status === 'warn' ? 'warn' : 'pass',
          bar: bar(integrity.joints, [{ k: 'pass', n: integrity.joints - withProblems }, { k: 'fail', n: withProblems }]),
          note: `${plural(integrity.clashes, 'clash', 'clashes')}; connectivity gate at P3: ${conn.status === 'warn' ? 'pass, with a warning' : conn.status}`,
          source: SOURCE('exports/body/integrity.json'), data: { ...integrity, connectivity: conn.status },
        },
        jointMeter(r, ['body', 'body / turret']),
        massMeter({ label: 'Mass, body and head', kg: mass.body_and_head_kg, limit: mass.budget.body_and_head_kg, file: 'exports/body/mass.json',
          note: `P3 ledger against D71’s ${kg(mass.budget.body_and_head_kg)} kg budget; ${kg(mass.gate.body_and_head_with_levers_kg)} kg with the scheduled savings` }),
        printMeter(r, 'exports/body/print-plan.json', null),
      ] });
  }

  // Wheels: the kerb study and fit check for D69's 10 in wheel. Nothing is bought or measured yet.
  {
    const curb = r.json('exports/wheels/summary_curb.json').hb10;
    const fit = r.json('exports/wheels/fit_clashes.json').hb10;
    const heights = Object.entries(curb.heights);
    const passed = heights.filter(([, h]) => h.pass).length;
    const clashes = fit.clashes.length + fit.wheel_clashes.length + fit.out_of_range.length;
    const cleared = heights.filter(([, h]) => h.pass).map(([mm]) => Number(mm)), failed = heights.filter(([, h]) => !h.pass).map(([mm]) => Number(mm));
    const kerbNote = !failed.length ? `Clears every height up to ${Math.max(...cleared)} mm at ${curb.speed_mps} m/s`
      : !cleared.length ? `Clears none of ${failed.map(mm => `${mm} mm`).join(', ')} at ${curb.speed_mps} m/s`
      : `Up to ${Math.max(...cleared)} mm at ${curb.speed_mps} m/s; ${failed.map(mm => `${mm} mm`).join(', ')} ${failed.length === 1 ? 'fails' : 'fail'}`;
    const fitNote = clashes ? [fit.clashes.length && plural(fit.clashes.length, 'clash', 'clashes'), fit.wheel_clashes.length && plural(fit.wheel_clashes.length, 'wheel clash', 'wheel clashes'), fit.out_of_range.length && plural(fit.out_of_range.length, 'out-of-range pose')].filter(Boolean).join(', ') + ' in the fit check'
      : 'No clash or out-of-range pose in the fit check';
    panels.push({ id: 'wheels', name: 'Wheels', blurb: curb.wheel.title, image: null,
      model: null, docs: 'research/air-tyre-hub-wheels.md', records: ['exports/wheels'], meters: [
        {
          id: 'kerb', label: 'Kerb climbs (sim)', value: `${passed} of ${heights.length}`, unit: 'heights cleared',
          state: passed === heights.length ? 'pass' : passed ? 'warn' : 'fail',
          bar: bar(heights.length, heights.map(([, h]) => ({ k: h.pass ? 'pass' : 'fail', n: 1 }))),
          note: kerbNote,
          source: SOURCE('exports/wheels/summary_curb.json'), data: { heights: Object.fromEntries(heights.map(([mm, h]) => [mm, h.pass])) },
        },
        {
          id: 'fit', label: 'Fit in the leg', value: `${clashes}`, unit: clashes === 1 ? 'clash' : 'clashes',
          state: clashes ? 'fail' : 'pass', bar: bar(1, [{ k: clashes ? 'fail' : 'pass', n: 1 }]),
          note: `${fitNote}; track ${num(fit.track_mm, 0)} mm`, source: SOURCE('exports/wheels/fit_clashes.json'), data: { clashes },
        },
        { id: 'bench', label: 'Bought and measured', value: '—', unit: 'no wheel yet', state: 'unknown', bar: bar(1, [{ k: 'unknown', n: 1 }]),
          note: 'No wheel bought or measured on the bench in this revision', source: null, data: null },
      ] });
  }

  // Rig: the single-leg test rig's checks, the fault drills in simulation, its joints, print plan and recorded runs.
  {
    const integrity = r.json('exports/rig/integrity.json');
    const faults = r.json('exports/rig/faults.json');
    const runs = r.list('exports/rig/runs', /\.json$/).map(f => r.json(f));
    const physical = runs.filter(x => x.meta?.backend && x.meta.backend !== 'sim').length;
    const screwsOk = integrity.screws.filter(s => s.ok).length;
    const drills = Object.values(faults.faults), drillsOk = drills.filter(f => f.ok).length;
    panels.push({ id: 'rig', name: 'Leg rig', blurb: 'One leg on a drop tower, before the robot', image: { src: '/exports/rig/rig-side.png', alt: 'The single-leg test rig, rendered from its CAD', width: 1600, height: 1100 },
      model: null, docs: 'docs/leg-rig-sections.md', records: ['exports/rig/integrity.json', 'exports/rig/faults.json', 'exports/rig/runs', inventory, 'exports/rig/print-plan.json'], meters: [
        {
          id: 'integrity', label: 'Screws and clearances', value: `${screwsOk} of ${integrity.screws.length}`, unit: 'screw stacks clear',
          state: integrity.ok ? 'pass' : 'fail', bar: bar(integrity.screws.length, [{ k: 'pass', n: screwsOk }, { k: 'fail', n: integrity.screws.length - screwsOk }]),
          note: `${integrity.interference.poses} poses swept, ${plural(integrity.interference.hits.length, 'hit')}`, source: SOURCE('exports/rig/integrity.json'), data: { screws: integrity.screws.length, screwsOk, poses: integrity.interference.poses },
        },
        {
          id: 'faults', label: 'Fault drills (sim)', value: `${drillsOk} of ${drills.length}`, unit: 'stop safely',
          state: drillsOk === drills.length ? 'pass' : 'fail', bar: bar(drills.length, [{ k: 'pass', n: drillsOk }, { k: 'fail', n: drills.length - drillsOk }]),
          note: `Injected during a ${faults.test} in simulation at ${num(faults.half_mass_kg)} kg`, source: SOURCE('exports/rig/faults.json'), data: { drills: drills.length, ok: drillsOk },
        },
        jointMeter(r, ['leg rig', 'J501 box']),
        printMeter(r, 'exports/rig/print-plan.json', null),
        {
          id: 'bench', label: 'Runs on the real rig', value: `${physical}`, unit: `of ${plural(runs.length, 'recorded run')}`,
          state: physical ? 'pass' : 'unknown', bar: bar(Math.max(runs.length, 1), [{ k: 'pass', n: physical }, { k: 'unknown', n: Math.max(runs.length, 1) - physical }]),
          note: physical ? `${physical} measured on hardware` : `The ${plural(runs.length, 'recorded run')} ${runs.length === 1 ? 'is' : 'are'} simulated`,
          source: { href: '/exports/rig/runs/', label: 'exports/rig/runs' }, data: { runs: runs.length, physical },
        },
      ] });
  }

  // Electronics: the fuse board's checks and the PAN cutoff candidate's own status.
  {
    const drc = r.text('hardware/fuse-board/reports/drc.rpt');
    const found = what => Number(drc.match(new RegExp(`Found (\\d+) ${what}`))?.[1]);
    const analysis = r.json('hardware/fuse-board/reports/analysis.json');
    const within = analysis.branches.filter(b => b.within_ipc2221_limits).length;
    const pan = r.json('hardware/carrier-pan-protection/reports/calculations.json');
    const violations = found('DRC violations'), unconnected = found('unconnected pads');
    const drcRead = Number.isFinite(violations) && Number.isFinite(unconnected); // a report the reader cannot parse is not a pass
    panels.push({ id: 'electronics', name: 'Electronics', blurb: 'Fuse board and the turret’s power cutoff', image: { src: '/hardware/fuse-board/pictures/top.png', alt: 'The fuse board’s top side, rendered from its KiCad layout', width: 1376, height: 1208 },
      model: null, docs: 'docs/body-fuse-board.md', records: ['hardware/fuse-board/reports', 'hardware/carrier-pan-protection/reports'], meters: [
        {
          id: 'drc', label: 'Fuse board DRC', value: drcRead ? `${violations + unconnected}` : '—', unit: drcRead ? 'violations' : 'report not read',
          state: !drcRead ? 'unknown' : violations + unconnected ? 'fail' : 'pass', bar: bar(1, [{ k: !drcRead ? 'unknown' : violations + unconnected ? 'fail' : 'pass', n: 1 }]),
          note: drcRead ? `${plural(violations, 'design-rule violation')}, ${plural(unconnected, 'unconnected pad')} (KiCad)` : 'The KiCad report’s counts could not be read', source: SOURCE('hardware/fuse-board/reports/drc.rpt'), data: { violations, unconnected },
        },
        {
          id: 'copper', label: 'Fused branches', value: `${within} of ${analysis.branches.length}`, unit: 'within IPC-2221',
          state: within === analysis.branches.length ? 'pass' : 'fail', bar: bar(analysis.branches.length, [{ k: 'pass', n: within }, { k: 'fail', n: analysis.branches.length - within }]),
          note: 'Copper width and temperature rise at each fuse’s rating', source: SOURCE('hardware/fuse-board/reports/analysis.json'), data: { within, branches: analysis.branches.length },
        },
        {
          id: 'pan', label: 'Turret power cutoff', value: `${pan.unqualified.length}`, unit: 'screens still open',
          state: pan.unqualified.length ? 'unknown' : 'pass', bar: bar(pan.unqualified.length || 1, [{ k: pan.unqualified.length ? 'unknown' : 'pass', n: pan.unqualified.length || 1 }]),
          note: `${pan.status.toLowerCase().replace(/_/g, ' ')}; open: ${pan.unqualified.map(u => u.replace(/_/g, ' ')).join(', ')}`, source: SOURCE('hardware/carrier-pan-protection/reports/calculations.json'), data: { status: pan.status, open: pan.unqualified.length },
        },
      ] });
  }

  for (const p of panels) p.changed = r.changed(p.records);
  const all = panels.flatMap(p => p.meters);
  const fea = all.filter(m => m.id === 'fea').map(m => m.data);
  const benchRows = all.filter(m => m.id === 'bench' && m.data?.rows).reduce((a, m) => ({ rows: a.rows + m.data.rows, measured: a.measured + m.data.measured }), { rows: 0, measured: 0 });
  const summary = {
    mass: { kg: mass.total_kg, gate: mass.budget.robot_kg, design: mass.budget.design_mass_kg, ceiling, weighed: /weigh/i.test(JSON.stringify(Object.keys(massRecord.P3))), file: 'exports/body/mass.json' },
    fea: { studies: fea.reduce((n, c) => n + c.studies, 0), pass: fea.reduce((n, c) => n + c.pass, 0), below: fea.reduce((n, c) => n + c.below, 0), under1: fea.reduce((n, c) => n + c.under1, 0) },
    gates: panels.find(p => p.id === 'turret').meters[0].data,
    fixes: jointCount(r.json(inventory), r.json(inventory).joints.map(j => j.assembly)).findings.fix,
    bench: benchRows,
    changed: panels.map(p => p.changed).filter(Boolean).sort((a, b) => b.date.localeCompare(a.date))[0] || null,
  };
  return { panels, summary };
}

// --- HTML --------------------------------------------------------------------------------------------------------

const STATE_WORD = { pass: 'on target', warn: 'below target', fail: 'needs a fix', unknown: 'not yet measured', note: 'noted' };
const LEGEND = [['pass', 'Meets its target'], ['note', 'Noted, no action'], ['warn', 'Below target / owner’s call'], ['fail', 'Under 1.0 / to fix'], ['unknown', 'Not yet measured']];

function meterHTML(m) {
  const segments = m.bar.segments.map(s => `<i data-k="${s.k}" style="--w:${num(s.n / m.bar.of * 100, 3)}%"></i>`).join('');
  const src = m.source ? ` <a class="sb-src" href="${esc(m.source.href)}">${esc(m.source.label)}</a>` : '';
  return `<li class="sb-meter" data-meter="${m.id}" data-state="${m.state}"><p class="sb-meter-head"><span class="sb-label">${esc(m.label)}</span><span class="sb-reading"><b class="sb-value">${esc(m.value)}</b> <span class="sb-unit">${esc(m.unit)}</span></span></p>`
    + `<span class="sb-bar" aria-hidden="true">${segments}</span><p class="sb-note"><span class="sb-state">${STATE_WORD[m.state]}</span> · ${esc(m.note)}.${src}</p></li>`;
}

function panelHTML(p, { compact }) {
  const meters = compact ? p.meters.slice(0, 3) : p.meters;
  const when = p.changed
    ? `<p class="sb-when" data-changed="${esc(p.changed.date)}"><span class="sb-pulse" aria-hidden="true"></span>Records changed <time datetime="${esc(p.changed.date)}">${shortDate(p.changed.date)}</time><span class="sb-ago"></span> · <a href="https://github.com/Valpatel/gyropup/commit/${p.changed.commit}" aria-label="commit ${p.changed.commit.slice(0, 7)}">${p.changed.commit.slice(0, 7)}</a></p>`
    : '<p class="sb-when" data-changed="">Change date not available in this build</p>';
  const shot = p.image
    ? `<a class="sb-shot" href="${esc(p.image.src)}"><img src="${esc(p.image.src)}" width="${p.image.width}" height="${p.image.height}" loading="lazy" decoding="async" alt="${esc(p.image.alt)}"></a>`
    : `<div class="sb-shot sb-noshot" role="img" aria-label="No render of this part yet"><svg viewBox="0 0 120 80" aria-hidden="true"><circle cx="60" cy="40" r="30"/><circle cx="60" cy="40" r="11"/><path d="M60 10v19M60 51v19M30 40h19M71 40h19"/></svg><span>No render yet</span></div>`;
  const gates = !compact && p.gates ? `<ul class="sb-gates" aria-label="Gate verdicts">${p.gates.map(g => `<li data-status="${g.status}"><a href="/${esc(g.file)}">${esc(g.name)}</a><span class="vh"> (${g.status === 'warn' ? 'pass, with a warning' : g.status})</span></li>`).join('')}</ul>` : '';
  const more = compact && p.meters.length > meters.length ? `<a class="sb-more" href="/designer/progress.html#board-${p.id}">${p.meters.length - meters.length} more on Progress →</a>` : '';
  const worst = p.meters.some(m => m.state === 'fail') ? 'fail' : p.meters.some(m => m.state === 'warn') ? 'warn' : p.meters.every(m => m.state === 'unknown') ? 'unknown' : 'pass';
  return `<article class="sb-panel" id="board-${p.id}${compact ? '-landing' : ''}" data-subsystem="${p.id}" data-state="${worst}" data-visual aria-labelledby="sb-${p.id}${compact ? '-l' : ''}">${shot}`
    + `<div class="sb-body"><header><h3 id="sb-${p.id}${compact ? '-l' : ''}"><a href="${esc(docPage(p.docs))}">${esc(p.name)}</a></h3><p class="sb-blurb">${esc(p.blurb)}</p>${when}</header>`
    + `<ul class="sb-meters">${meters.map(meterHTML).join('')}</ul>${gates}${more}</div></article>`;
}

/** The board's HTML. `compact` (the landing page) shows each panel's first three meters and links to the rest. */
export function renderBoard({ panels, summary }, { compact = false, heading = 'h2' } = {}) {
  const s = summary;
  const massPct = v => num(v / s.mass.ceiling * 100, 3);
  const strip = `<div class="sb-strip" data-visual>`
    + `<div class="sb-stat sb-mass"><p class="sb-stat-label">Robot mass, P3 ledger</p><p class="sb-stat-value"><b>${kg(s.mass.kg)}</b> kg</p>`
    + `<span class="sb-scale" aria-hidden="true"><i class="sb-fill" style="--w:${massPct(s.mass.kg)}%"></i><i class="sb-tick" style="--x:${massPct(s.mass.gate)}%"></i><i class="sb-tick is-design" style="--x:${massPct(s.mass.design)}%"></i><i class="sb-tick is-end" style="--x:100%"></i></span>`
    + `<p class="sb-ticks"><span class="is-gate">${kg(s.mass.gate)} as-built gate</span><span class="is-design">${kg(s.mass.design)} design mass</span><span class="is-end">${kg(s.mass.ceiling)} ceiling</span></p>`
    + `<p class="sb-stat-note">${s.mass.kg <= s.mass.gate ? 'Under' : 'Over'} D71’s ${kg(s.mass.gate)} kg as-built gate; the product ceiling is ${kg(s.mass.ceiling)} kg (D72).${s.mass.weighed ? '' : ' A CAD ledger: nothing weighed yet.'}</p></div>`
    + `<div class="sb-stat"><p class="sb-stat-label">Strength studies on target</p><p class="sb-stat-value"><b>${s.fea.pass}</b> of ${s.fea.studies}</p><span class="sb-bar" aria-hidden="true"><i data-k="pass" style="--w:${num(s.fea.pass / s.fea.studies * 100, 3)}%"></i><i data-k="warn" style="--w:${num(s.fea.below / s.fea.studies * 100, 3)}%"></i><i data-k="fail" style="--w:${num(s.fea.under1 / s.fea.studies * 100, 3)}%"></i></span><p class="sb-stat-note">${s.fea.below} below target, ${s.fea.under1} under 1.0, across the leg, turret and body.</p></div>`
    + `<div class="sb-stat"><p class="sb-stat-label">Insert-joint fixes open</p><p class="sb-stat-value"><b>${s.fixes}</b></p><p class="sb-stat-note">Clear corrections the joint inventory found; the CAD fixes clear them when they land.</p></div>`
    + `<div class="sb-stat${s.bench.measured ? '' : ' sb-unknown'}"><p class="sb-stat-label">Bench rows measured</p><p class="sb-stat-value"><b>${s.bench.measured}</b> of ${s.bench.rows}</p><span class="sb-bar" aria-hidden="true"><i data-k="pass" style="--w:${num(s.bench.measured / s.bench.rows * 100, 3)}%"></i><i data-k="unknown" style="--w:${num((s.bench.rows - s.bench.measured) / s.bench.rows * 100, 3)}%"></i></span><p class="sb-stat-note">${s.bench.measured ? `${s.bench.rows - s.bench.measured} rows of the coupon and gauge sheets still blank.` : 'Coupons and gauges are designed and sliced; no sheet has a reading yet.'}</p></div>`
    + `</div>`;
  const legend = `<ul class="sb-legend" aria-hidden="true">${LEGEND.map(([k, t]) => `<li data-k="${k}">${t}</li>`).join('')}</ul>`;
  const latest = s.changed ? ` The newest record changed <time datetime="${esc(s.changed.date)}">${shortDate(s.changed.date)}</time>.` : '';
  return `<section id="board" class="status-board${compact ? ' is-compact' : ''}" aria-labelledby="board-title" data-generated="tools/status-board.mjs">`
    + `<div class="sb-heading"><div><p class="eyebrow"><span class="status-dot"></span> FROM THE RECORDS, AT BUILD</p><${heading} id="board-title">The design, <span>right now.</span></${heading}></div>`
    + `<p class="sb-lede">Every bar is read from a committed check, study or measurement sheet when the site is built. Amber and red are real shortfalls; grey is not measured yet.${latest}</p></div>`
    + strip + legend + (compact ? '<p class="sb-swipe" aria-hidden="true">Swipe for every subsystem →</p>' : '') + `<div class="sb-grid"${compact ? ' tabindex="0" role="group" aria-label="Subsystem panels"' : ''}>${panels.map(p => panelHTML(p, { compact })).join('')}</div>`
    + `<p class="sb-foot">Checks and simulations are predictions; a green bar is not physical proof. Data: <a href="/site/status.json">status.json</a>.</p></section>`;
}
