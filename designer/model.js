// Gyropup design model: design + catalog -> BOM, mass, performance and checks.
//
// Pure functions, no DOM, so the same file runs in the browser (designer) and in Node (tools/derive.mjs, tests).
// Every derived number says where it came from: "catalog" (a cited part spec), "formula" (computed from
// those), or "estimate" (a rule of thumb, flagged in the UI until the CAD or a real test replaces it).
//
// Frames: side view, x forward, z up, wheel axle at z = wheel radius. Lengths in mm unless named _m; masses in g
// unless named _kg; torques N m; power W.

export const G = 9.81;

// Leg layouts. torque_share: fraction of the serial-leg knee torque each actuator carries in the worst pose.
export const LEG_TOPOLOGIES = {
  serial_knee_at_hip: {
    name: 'Stacked hip motors, four-bar knee (Diablo style)',
    torque_share: 1.0,
    note: 'Hip and knee motors sit together on the body; a four-bar link drives the knee. Light, quick legs. '
      + 'This is how the Diablo is built (DDT sim model).',
  },
  five_bar: {
    name: 'Five-bar parallel leg',
    torque_share: 0.6,
    note: 'Two hip motors share the load through a closed linkage. Stronger per motor, but less range and the '
      + 'loop needs an equivalent serial model in simulation.',
  },
  serial_knee_at_knee: {
    name: 'Motor at the knee',
    torque_share: 1.0,
    note: 'Simplest to build, but the knee motor swings with the leg, so the leg is heavy and slow to move.',
  },
};

const DEFAULTS = {
  dynamic_factor: 2.5,      // squat-to-stand and landing loads over static (estimate; Upkie/Ascento practice)
  jump_factor: 1.0,         // fraction of peak torque usable through the stroke (estimate)
  efficiency: 0.85,         // battery to useful energy (estimate)
  power: { legs_standing_w: 6, wheels_rolling_w: 15, electronics_w: 5 },  // per actuator / total (estimate)
  printed_creep_factor: 0.3,  // sustained-load allowable as a fraction of tensile strength for printed polymers (estimate)
};

// ----------------------------------------------------------------------------- catalog helpers

export function indexCatalog(lists) {
  const byId = {};
  for (const list of lists) for (const item of list) byId[item.id] = item;
  return byId;
}

const SENSOR_COMPUTE = new Set(['compute', 'sensor']);

export function bomGroup(item) {
  return SENSOR_COMPUTE.has(item.category) ? 'sensors_compute' : 'chassis_actuators';
}

function spec(item, key, fallback = null) {
  const v = item?.specs?.[key];
  return v === undefined || v === null ? fallback : v;
}

// Mass in grams: the published mass, else a labelled estimate.
function massOf(item) {
  return spec(item, 'mass_g') ?? spec(item, 'mass_g_estimate');
}

// Typical power in W: the published typical figure, else the middle of a published range.
function powerOf(item) {
  const r = spec(item, 'system_power_w') ?? spec(item, 'power_range_w');
  return spec(item, 'power_typical_w') ?? (Array.isArray(r) ? (r[0] + r[1]) / 2 : 0);
}

// No-load speed at the actual bus voltage: speed scales with voltage for a BLDC motor.
function speedAt(item, busV) {
  const rpm = spec(item, 'no_load_speed_rpm'), vNom = spec(item, 'voltage_nominal_v');
  return rpm && vNom && busV ? (rpm * busV) / vNom : rpm;
}

// A design names a catalog part by id, or carries a custom part inline:
//   {"custom": true, "category": "leg_actuator", "vendor": "Custom", "model": "My motor", "price_usd": 300,
//    "specs": {"mass_g": 900, "peak_torque_nm": 40, ...}}
export function resolvePart(ref, catalog) {
  if (!ref) return null;
  if (typeof ref === 'object') return { id: `custom-${ref.model ?? 'part'}`, vendor: 'Custom', ...ref };
  return catalog[ref] ?? null;
}

// ----------------------------------------------------------------------------- geometry

// Serial two-link leg with the wheel directly under the hip. Returns hip height above the axle and the knee's
// horizontal offset from the hip-wheel line (the lever the knee torque works against).
export function legPose(thigh, shin, kneeInteriorDeg) {
  const g = (kneeInteriorDeg * Math.PI) / 180;
  const h = Math.sqrt(thigh * thigh + shin * shin - 2 * thigh * shin * Math.cos(g));
  const area = 0.5 * thigh * shin * Math.sin(g);
  return { hip_height: h, knee_lever: (2 * area) / h };
}

export function heightRange(d) {
  const { thigh_mm: a, shin_mm: b, knee_min_deg, knee_max_deg, wheel_diameter_mm: w } = d.geometry;
  const lo = legPose(a, b, knee_min_deg), hi = legPose(a, b, knee_max_deg);
  return { crouch_hip_mm: lo.hip_height + w / 2, stand_hip_mm: hi.hip_height + w / 2,
           stroke_mm: hi.hip_height - lo.hip_height, crouch_knee_lever_mm: lo.knee_lever };
}

// ----------------------------------------------------------------------------- printed parts

// Mass of a printed part from its solid volume: solid shell, sparse core (matches cadagent.robot.printed_fill).
export function printedMassG(volumeCm3, areaCm2, material, print = { wall_mm: 1.6, infill: 0.15 }) {
  const shell = Math.min(volumeCm3, (areaCm2 * print.wall_mm) / 10);
  return material.density_g_cm3 * (shell + print.infill * (volumeCm3 - shell));
}

// Hollow rectangular link section: width w, depth h, wall t (mm). Returns I (mm^4) and c (mm).
function boxSection(w, h, t) {
  const wi = Math.max(0, w - 2 * t), hi = Math.max(0, h - 2 * t);
  return { I: (w * h ** 3 - wi * hi ** 3) / 12, c: h / 2, area: w * h - wi * hi, perim: 2 * (w + h) };
}

// Parametric printed parts for the current design. Each has an estimated solid volume and surface area;
// the CAD build replaces these with exact numbers (exports/mass-properties.json) when the design matches.
export function printedParts(d) {
  const g = d.geometry, s = d.geometry.link_section;
  const sec = boxSection(s.width_mm, s.depth_mm, s.wall_mm);
  const link = (len) => ({ volume_cm3: (sec.area * len) / 1000 + 2 * 40, area_cm2: (sec.perim * len) / 100 + 2 * 60 });
  const body = d.geometry.body;
  const frameVol = (2 * (body.depth_mm + body.width_mm) * 60 * 4 + body.depth_mm * body.width_mm * 3) / 1000;
  return [
    { id: 'body_frame', name: 'Body frame', qty: 1, ...{ volume_cm3: frameVol, area_cm2: frameVol * 6.5 }, load: 'body' },
    { id: 'hip_mount', name: 'Hip motor mount', qty: 2, volume_cm3: 120, area_cm2: 400, load: 'motor', hot: true },
    { id: 'thigh', name: 'Thigh', qty: 2, ...link(g.thigh_mm), load: 'link', length_mm: g.thigh_mm, section: sec },
    { id: 'shin', name: 'Shin', qty: 2, ...link(g.shin_mm), load: 'link', length_mm: g.shin_mm, section: sec },
    { id: 'wheel_mount', name: 'Wheel motor mount', qty: 2, volume_cm3: 60, area_cm2: 220, load: 'motor', hot: true },
    { id: 'sensor_head', name: 'Sensor head', qty: 1, volume_cm3: 260, area_cm2: 1400, load: 'light' },
    { id: 'battery_tray', name: 'Battery tray', qty: 1, volume_cm3: 110, area_cm2: 700, load: 'light' },
    { id: 'lidar_crown', name: 'Lidar crown (fall guard)', qty: d.parts.lidar && d.lidar_mount !== 'under' ? 1 : 0, volume_cm3: 140, area_cm2: 900, load: 'impact' },
    ...(d.parts.tail_pitch ? [
      { id: 'tail_mount', name: 'Tail motor mount', qty: 1, volume_cm3: 70, area_cm2: 260, load: 'motor', hot: true },
      { id: 'tail_clamp', name: 'Tail tube clamp (on the wag motor)', qty: 1, volume_cm3: 25, area_cm2: 110, load: 'motor', hot: true },
      { id: 'tail_shoe', name: 'Tail skid shoe', qty: 1, volume_cm3: 30, area_cm2: 120, load: 'impact', material: 'tpu95' },
    ] : []),
    { id: 'camera_cradle', name: 'Depth camera cradle (D415/D435)', qty: (d.parts.depth_front ? 1 : 0) + (d.parts.depth_rear ? 1 : 0), volume_cm3: 18, area_cm2: 110, load: 'light' },
    ...(d.wheel_from_motor ? [] : [
      { id: 'wheel_hub', name: 'Wheel hub', qty: 2, volume_cm3: 0.12 * g.wheel_diameter_mm, area_cm2: 0.9 * g.wheel_diameter_mm, load: 'motor' },
      { id: 'tyre', name: 'Tyre', qty: 2, volume_cm3: 0.35 * g.wheel_diameter_mm, area_cm2: 1.5 * g.wheel_diameter_mm, load: 'light', material: 'tpu95' },
    ]),
  ].filter((p) => p.qty > 0).map((p) => ({ ...p, estimate: true }));
}

// ----------------------------------------------------------------------------- the model

// The wheel size comes from the wheel motor when it has its own tyre; otherwise the design's size is used and a
// printed hub and TPU tyre are added.
export function effectiveDesign(design, catalog) {
  const wheel = resolvePart(design.parts.wheel_motor, catalog);
  const dia = wheel?.specs?.diameter_mm;
  const d = JSON.parse(JSON.stringify(design));
  d.wheel_from_motor = dia != null;
  if (dia != null) d.geometry.wheel_diameter_mm = dia;
  return d;
}

// Where things sit, in mm, in the hip-axis frame (x right, y up, z forward). The 3D page and the physics model both
// use this, so they always agree.
export function layout(design, catalog) {
  const d = effectiveDesign(design, catalog), g = d.geometry;
  const part = (slot) => resolvePart(d.parts[slot], catalog);
  const act = part('leg_actuator'), wheel = part('wheel_motor'), compute = part('compute'), batt = part('battery');
  const motorD = act?.specs?.diameter_mm ?? 100, motorL = act?.specs?.length_mm ?? 50;
  const lw = g.link_section?.width_mm ?? 40, ld = g.link_section?.depth_mm ?? 30;
  const wheelW = wheel?.specs?.width_mm ?? 45;
  // the body is the compute box: its enclosure size when the catalog has one, else the design's own
  const cd = compute?.specs?.enclosure_dimensions_mm ?? compute?.specs?.dimensions_mm;
  const B = cd?.length === 3 && cd.every(Boolean) ? { width_mm: cd[0], depth_mm: cd[1], height_mm: cd[2] } : g.body;
  // the battery tray fits the pack(s): lying flat, long side front to back, packs side by side
  const packs = (batt?.specs?.packs ?? 1) * (d.battery_count ?? 1);
  const pd = batt?.specs?.pack_dimensions_mm ?? [batt?.specs?.length_mm, batt?.specs?.width_mm, batt?.specs?.height_mm];
  const dims = pd.every((x) => x) ? [...pd].sort((p, q) => q - p) : null;
  const tray = dims
    ? { width: Math.max(B.width_mm, packs * dims[1] + 10 * packs), depth: Math.max(B.depth_mm, dims[0] + 10), height: Math.max(g.battery_tray_mm ?? 40, dims[2] + 12) }
    : { width: B.width_mm, depth: B.depth_mm, height: g.battery_tray_mm ?? 60 };
  const trayBottom = -25;
  const bodyW = Math.max(B.width_mm, tray.width);
  const hipX = bodyW / 2 + motorL + 8;
  const bodyBottom = trayBottom + tray.height;
  return {
    motorD, motorL, linkW: lw, linkD: ld, wheelW, wheelR: g.wheel_diameter_mm / 2, thigh: g.thigh_mm, shin: g.shin_mm,
    hipX, wheelX: hipX + lw / 2 + wheelW / 2 + 6, trayBottom, trayH: tray.height, tray, bodyBottom, bodyTop: bodyBottom + B.height_mm,
    body: { width: B.width_mm, depth: B.depth_mm, height: B.height_mm }, frameWidth: bodyW,
    battery: dims ? { packs, dims, vendor: batt?.vendor ?? '' } : null,
    kneeMinDeg: g.knee_min_deg, kneeMaxDeg: g.knee_max_deg, lidarMount: d.lidar_mount ?? 'top',
    // the tail: pitch motor under the back of the tray (clear of the lidar and the rear camera), arm to the skid shoe
    tail: d.parts.tail_pitch ? {
      pivotX: -(tray.depth / 2 + 20), pivotZ: trayBottom - 45, length: g.tail_mm ?? 360,
      pitchD: part('tail_pitch')?.specs?.diameter_mm ?? 88, pitchL: part('tail_pitch')?.specs?.length_mm ?? 49,
      yawD: part('tail_yaw')?.specs?.diameter_mm ?? 57, yawL: part('tail_yaw')?.specs?.length_mm ?? 51,
      tubeD: part('tail_tube')?.specs?.od_mm ?? 20, shoeR: 22,
      tubeDrop: Math.round((part('tail_yaw')?.specs?.length_mm ?? 51) / 2 + (part('tail_tube')?.specs?.od_mm ?? 20) / 2 + 4),   // clamp under the wag motor's output
      yawOffset: Math.ceil((part('tail_pitch')?.specs?.diameter_mm ?? 88) / 2 + (part('tail_yaw')?.specs?.diameter_mm ?? 57) / 2 + 8),   // wag motor clear of the pitch motor
    } : null,
  };
}

export function evaluate(design, catalog, materials, opts = {}) {
  const o = { ...DEFAULTS, ...opts };
  const d = effectiveDesign(design, catalog);
  const pick = (slot) => resolvePart(d.parts[slot], catalog);
  const checks = [];
  const perception = {};
  const check = (id, level, text) => checks.push({ id, level, text });

  // --- BOM: catalogue parts
  // Every filled slot is a BOM line, so a design can add any part. Quantities for the paired parts:
  const QTY = { leg_actuator: 4, wheel_motor: 2, motor_driver: 2, battery: d.battery_count ?? 1 };
  const slots = Object.keys(d.parts).map((slot) => [slot, QTY[slot] ?? d.part_qty?.[slot] ?? 1]);
  const lines = [];
  for (const [slot, qty] of slots) {
    const item = pick(slot);
    if (!item || !qty) continue;
    const grams = item.category === 'cf_tube' && spec(item, 'mass_g_per_m')            // tubes are cut to length
      ? spec(item, 'mass_g_per_m') * ((slot === 'tail_tube' ? d.geometry.tail_mm ?? 360 : 1000) - 40) / 1000 : massOf(item);
    lines.push({ slot, id: item.id, name: `${item.vendor} ${item.model}`, qty, group: bomGroup(item),
                 unit_usd: item.price_usd, mass_g: grams, mass_estimate: spec(item, 'mass_g') == null && massOf(item) != null, source: item.buy?.[0]?.url ?? item.sources?.[0] ?? null,
                 price_checked: item.price_checked ?? null });
    if (item.price_usd == null) check(`price-${slot}`, 'warn', `${item.vendor} ${item.model} has no public price; it is left out of the total.`);
    if (massOf(item) == null) check(`mass-${slot}`, 'warn', `${item.vendor} ${item.model} has no published mass; it is left out of the mass budget.`);
    else if (spec(item, 'mass_g') == null) check(`mass-${slot}`, 'warn', `${item.vendor} ${item.model}: mass is an estimate (${massOf(item)} g). Weigh it.`);
  }

  // --- BOM: printed parts
  const parts = printedParts(d).map((p) => {
    const matId = d.materials?.parts?.[p.id] ?? p.material ?? d.materials?.default ?? 'pla';
    const m = materials[matId];
    const grams = printedMassG(p.volume_cm3, p.area_cm2, m, d.print);
    return { ...p, material: matId, mass_g: grams, filament_usd: (grams / 1000) * m.price_usd_per_kg };
  });
  const filamentG = parts.reduce((s, p) => s + p.mass_g * p.qty, 0);
  const filamentUsd = parts.reduce((s, p) => s + p.filament_usd * p.qty, 0);
  lines.push({ slot: 'printed', id: 'printed-parts', name: `Printed parts (${parts.reduce((s, p) => s + p.qty, 0)} parts, ${Math.round(filamentG)} g filament)`,
               qty: 1, group: 'chassis_actuators', unit_usd: filamentUsd, mass_g: filamentG, estimate: true });
  if (d.head_payload?.mass_g) {          // a head payload developed elsewhere (the turret): counts for mass and power, not cost
    lines.push({ slot: 'head_payload', id: 'head-payload', name: `${d.head_payload.name ?? 'Head payload'} (budget)`, qty: 1,
                 group: 'chassis_actuators', unit_usd: 0, mass_g: d.head_payload.mass_g, estimate: true });
  }
  const hardware = d.hardware_allowance ?? { usd: 60, mass_g: 400, note: 'bearings, fasteners, inserts, wiring' };
  lines.push({ slot: 'hardware', id: 'hardware-allowance', name: `Hardware allowance (${hardware.note})`, qty: 1,
               group: 'chassis_actuators', unit_usd: hardware.usd, mass_g: hardware.mass_g, estimate: true });

  const total = (group) => lines.filter((l) => !group || l.group === group)
    .reduce((s, l) => s + (l.unit_usd ?? 0) * l.qty, 0);
  const massWhere = (pred) => lines.filter(pred).reduce((s, l) => s + (l.mass_g ?? 0) * l.qty, 0);
  const cost = { sensors_compute_usd: total('sensors_compute'), chassis_actuators_usd: total('chassis_actuators'), total_usd: total() };

  // --- mass budget: what each leg carries
  const legAct = pick('leg_actuator'), wheel = pick('wheel_motor');
  const busV = spec(pick('battery'), 'voltage_nominal_v');  // motor speeds scale with this
  const thighShin = parts.filter((p) => p.id === 'thigh' || p.id === 'shin' || p.id === 'wheel_mount')
    .reduce((s, p) => s + p.mass_g * p.qty, 0);
  const wheelMass = 2 * (massOf(wheel) ?? 0);
  const kneeAtKnee = d.leg.topology === 'serial_knee_at_knee';
  const legMovingG = thighShin + wheelMass + (kneeAtKnee ? 2 * (massOf(legAct) ?? 0) : 0);
  const totalG = massWhere(() => true);
  const supportedKg = (totalG - wheelMass) / 1000;    // everything above the wheels (approx.: shins carried too)
  const totalKg = totalG / 1000;

  // --- legs
  const topo = LEG_TOPOLOGIES[d.leg.topology];
  const hr = heightRange(d);
  const perLegN = (supportedKg * G) / 2;
  const kneeStatic = (perLegN * hr.crouch_knee_lever_mm) / 1000;
  const perActStatic = kneeStatic * topo.torque_share;
  const perActDynamic = perActStatic * o.dynamic_factor;
  const legRated = spec(legAct, 'rated_torque_nm'), legPeak = spec(legAct, 'peak_torque_nm');
  const legs = {
    topology: d.leg.topology, ...hr,
    static_torque_nm: perActStatic, dynamic_torque_nm: perActDynamic,
    rated_margin: legRated ? legRated / perActStatic : null, peak_margin: legPeak ? legPeak / perActDynamic : null,
  };
  if (legs.rated_margin != null) {
    if (legs.rated_margin < 1) check('leg-hold', 'fail', `The leg actuators cannot hold a deep crouch continuously: ${perActStatic.toFixed(1)} N·m needed, ${legRated} N·m rated.`);
    else if (legs.rated_margin < 1.5) check('leg-hold', 'warn', `Holding a deep crouch uses ${Math.round(100 / legs.rated_margin)}% of rated torque; the motors will run warm.`);
    else check('leg-hold', 'ok', `Deep crouch uses ${Math.round(100 / legs.rated_margin)}% of the leg actuators' rated torque.`);
  }
  if (legs.peak_margin != null && legs.peak_margin < 1) check('leg-dynamic', 'fail', `Standing up fast or landing needs about ${perActDynamic.toFixed(1)} N·m per actuator; peak is ${legPeak} N·m.`);

  // jump: average leg force over the stroke, capped by joint speed
  if (legPeak) {
    const strokeM = hr.stroke_mm / 1000;
    const leverM = (hr.crouch_knee_lever_mm / 1000) * 0.7;           // mean lever over the stroke (estimate)
    const forceN = (2 * legPeak * o.jump_factor) / (leverM * topo.torque_share);
    const accel = forceN / totalKg - G;
    let v = accel > 0 ? Math.sqrt(2 * accel * strokeM) : 0;
    const rpm = speedAt(legAct, busV);
    legs.no_load_rpm_at_bus = rpm;
    const vCap = rpm ? ((rpm * 2 * Math.PI) / 60) * leverM * 0.6 : Infinity;
    const speedLimited = v > vCap;
    v = Math.min(v, vCap);
    legs.jump_height_mm = (v * v) / (2 * G) * 1000;
    legs.jump_speed_limited = speedLimited;
    const vNom = spec(legAct, 'voltage_nominal_v');
    if (busV && vNom && busV < 0.75 * vNom) {
      check('leg-speed', 'warn', `The leg actuators are rated at ${vNom} V; on a ${busV} V battery they reach about ${Math.round(rpm)} rpm instead of ${spec(legAct, 'no_load_speed_rpm')}, so jumps and fast squats are slower.`);
    }
  }

  // --- wheels
  const r = d.geometry.wheel_diameter_mm / 2000;
  const wPeak = spec(wheel, 'peak_torque_nm'), wRated = spec(wheel, 'rated_torque_nm');
  const wheels = {};
  if (wPeak) {
    wheels.max_force_n = (2 * wPeak) / r;
    wheels.max_accel_mps2 = wheels.max_force_n / totalKg;
    wheels.catch_lean_deg = (Math.atan(wheels.max_accel_mps2 / G) * 180) / Math.PI;
    if (wheels.catch_lean_deg < 15) check('balance', 'fail', `The wheels can only catch a ${wheels.catch_lean_deg.toFixed(0)}° lean; pick stronger wheel motors or a lighter build.`);
    else if (wheels.catch_lean_deg < 25) check('balance', 'warn', `The wheels can catch a ${wheels.catch_lean_deg.toFixed(0)}° lean; a push or a bump could tip it.`);
    else check('balance', 'ok', `The wheels can catch a ${wheels.catch_lean_deg.toFixed(0)}° lean.`);
  }
  if (wRated) wheels.max_slope_deg = (Math.asin(Math.min(1, (2 * wRated) / r / (totalKg * G))) * 180) / Math.PI;
  const wRpm = speedAt(wheel, busV);
  if (wRpm) wheels.top_speed_kmh = ((wRpm * 0.8 * Math.PI * d.geometry.wheel_diameter_mm) / 1000) * 60 / 1000;
  const enc = String(spec(wheel, 'encoder', '')).toLowerCase();
  if (wheel && /hall/.test(enc) && !/magnetic|absolute|bit/.test(enc)) {
    check('wheel-encoder', 'warn', 'Hall sensors only: balancing at low speed is rough without a finer encoder (add a magnetic encoder or pick another motor).');
  }

  // --- power and voltage
  const batt = pick('battery');
  const power = {};
  if (batt) {
    const vNom = spec(batt, 'voltage_nominal_v'), vFull = spec(batt, 'voltage_max_v') ?? spec(batt, 'voltage_full_v');
    const cells = spec(batt, 'cells_series');
    const lfp = /lifepo4|lfp/i.test(String(spec(batt, 'chemistry', '')));
    const cutoff = lfp ? 2.5 : 3.0;  // V per cell at the BMS cut-off: LiFePO4 2.5, Li-ion 3.0
    const vEmpty = spec(batt, 'voltage_min_v') ?? (cells ? cells * cutoff : vNom ? vNom * 0.83 : null);
    power.chemistry = spec(batt, 'chemistry');
    const wh = spec(batt, 'energy_wh') * (d.battery_count ?? 1);
    power.bus_v = [vEmpty, vFull];
    for (const [slot, label] of [['leg_actuator', 'leg actuators'], ['wheel_motor', 'wheel motors'], ['motor_driver', 'motor drivers']]) {
      const range = spec(pick(slot), 'voltage_range_v');
      if (range && vFull && vEmpty && (vFull > range[1] || vEmpty < range[0])) {
        check(`volts-${slot}`, 'fail', `The battery runs ${vEmpty.toFixed(1)}–${vFull.toFixed(1)} V but the ${label} accept ${range[0]}–${range[1]} V.`);
      }
    }
    const compute = pick('compute');
    const cRange = spec(compute, 'voltage_range_v');
    if (cRange && vFull && (vFull > cRange[1] || vEmpty < cRange[0]) && !pick('dcdc_compute')) {
      check('volts-compute', 'fail', `The compute box takes ${cRange[0]}–${cRange[1]} V; a ${vFull.toFixed(1)} V full battery needs a DC-DC converter.`);
    }
    for (const slot of ['dcdc_compute', 'dcdc_12v']) {    // a converter must work across the whole battery range
      const inR = spec(pick(slot), 'input_voltage_range_v');
      if (inR && vFull && vEmpty && (vEmpty < inR[0] || vFull > inR[1])) {
        check(`dcdc-${slot}`, 'fail', `${pick(slot).vendor} ${pick(slot).model} takes ${inR[0]}–${inR[1]} V in; the battery runs ${vEmpty.toFixed(1)}–${vFull.toFixed(1)} V.`);
      }
    }
    for (const [slot, label] of [['leg_actuator', 'leg actuators'], ['wheel_motor', 'wheel motors'], ['motor_driver', 'motor drivers']]) {
      const range = spec(pick(slot), 'voltage_range_v');      // braking pushes the bus above full charge
      if (range && vFull && vFull <= range[1] && vFull > 0.92 * range[1] && spec(pick('regen_clamp'), 'trip_voltage_v') == null) {
        check(`regen-${slot}`, 'warn', `A full battery (${vFull.toFixed(1)} V) is within 8% of the ${label}' ${range[1]} V limit; braking energy can push the bus over it. Add a brake resistor or use a lower voltage.`);
      }
    }
    const clampV = spec(pick('regen_clamp'), 'trip_voltage_v');
    if (clampV && vFull) {
      const limits = ['leg_actuator', 'wheel_motor', 'motor_driver'].map((k) => spec(pick(k), 'voltage_range_v')?.[1]).filter(Boolean);
      if (limits.some((v) => clampV >= v)) check('regen-clamp', 'fail', `The regen clamp trips at ${clampV} V, at or above a motor limit (${Math.min(...limits)} V).`);
    }
    const lidarV = spec(pick('lidar'), 'voltage_range_v');
    if (lidarV && vFull > lidarV[1] && !pick('dcdc_12v')) {
      check('volts-lidar', 'fail', `The lidar takes ${lidarV[0]}–${lidarV[1]} V; it needs a regulated 12 V supply from a ${vFull.toFixed(1)} V battery.`);
    }
    const sensorsW = ['compute', 'lidar', 'stereo', 'depth_front', 'depth_rear', 'imu', 'balance_mcu', 'headlights', 'eyes'].reduce((s, k) => s + powerOf(pick(k)), 0);
    const legsW = 4 * o.power.legs_standing_w, wheelsW = o.power.wheels_rolling_w;
    power.average_w = sensorsW + legsW + wheelsW + o.power.electronics_w + (d.head_payload?.power_w ?? 0) * 0.3;  // payload duty ~30 % (estimate)
    power.sensors_compute_w = sensorsW;
    if (wh) power.runtime_min = ((wh * o.efficiency) / power.average_w) * 60;
    const maxA = spec(batt, 'max_continuous_a') ?? spec(batt, 'continuous_discharge_a');
    const peakDraw = 4 * spec(legAct, 'peak_current_a', 0) * 0.5 + 2 * spec(wheel, 'peak_current_a', 0);
    if (maxA && peakDraw > maxA) check('battery-current', 'warn', `Peak motor current could reach ${Math.round(peakDraw)} A; the battery is rated ${maxA} A continuous.`);
  }

  // --- lidar mount: view and falls
  if (pick('lidar')) {
    const mount = d.lidar_mount ?? 'top';
    if (mount === 'under') {
      // From the lidar between the legs, each wheel disc hides an arc to the side; the legs add a little more.
      const g = d.geometry, r = g.wheel_diameter_mm / 2, side = g.track_mm / 2 - (spec(wheel, 'width_mm', 45) / 2);
      const blocked = 2 * ((2 * Math.atan(r / side) * 180) / Math.PI + 10);
      perception.lidar_blocked_deg = blocked;
      check('lidar-view', 'warn', `Under the body, the wheels and legs hide about ${Math.round(blocked)}° of the lidar's 360° view, and its downward beams reach the floor within about 0.75 m.`);
    } else {
      perception.lidar_blocked_deg = 0;
      check('lidar-view', 'ok', `On ${mount === 'mast' ? 'a mast' : 'top of the body'}, the lidar has a clear 360° view. It is the highest part, so the crown takes the hit in a fall.`);
    }
  }

  // --- printed part strength and heat
  for (const p of parts) {
    const m = materials[p.material];
    if (p.hot && m.max_service_c != null && m.max_service_c < 70) {
      check(`heat-${p.id}`, 'warn', `${p.name} in ${m.name}: it softens near ${m.max_service_c} °C and actuators can run hotter. Use ${m.next_name ?? 'a higher-temperature material'} or a metal spacer.`);
    }
    if (p.load === 'link' && p.section) {
      // worst case: the full leg load at the end of the link, link horizontal
      const M = perLegN * o.dynamic_factor * p.length_mm;     // N mm
      const stress = (M * p.section.c) / p.section.I;          // MPa
      const allow = m.tensile_mpa * o.printed_creep_factor * (m.layer_factor ?? 1);
      p.stress_mpa = stress; p.allowable_mpa = allow;
      const lvl = stress > allow * 1.5 ? 'fail' : stress > allow ? 'warn' : 'ok';
      check(`strength-${p.id}`, lvl, `${p.name}: ${stress.toFixed(1)} MPa peak bending vs ${allow.toFixed(1)} MPa allowable in ${m.name}.`);
    }
  }

  return {
    lines, parts, cost, checks,
    mass: { total_kg: totalKg, supported_kg: supportedKg, leg_moving_kg: legMovingG / 1000,
            sensors_compute_kg: massWhere((l) => l.group === "sensors_compute") / 1000 },
    legs, wheels, power, perception, layout: layout(design, catalog),
    verdict: checks.some((c) => c.level === 'fail') ? 'fail' : checks.some((c) => c.level === 'warn') ? 'warn' : 'ok',
  };
}
