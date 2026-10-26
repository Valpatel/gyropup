// Wobbit design model: design + catalog -> BOM, mass, performance and checks.
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
  const frameVol = (2 * (body.length_mm + body.width_mm) * 60 * 4 + body.length_mm * body.width_mm * 3) / 1000;
  return [
    { id: 'body_frame', name: 'Body frame', qty: 1, ...{ volume_cm3: frameVol, area_cm2: frameVol * 6.5 }, load: 'body' },
    { id: 'hip_mount', name: 'Hip motor mount', qty: 2, volume_cm3: 120, area_cm2: 400, load: 'motor', hot: true },
    { id: 'thigh', name: 'Thigh', qty: 2, ...link(g.thigh_mm), load: 'link', length_mm: g.thigh_mm, section: sec },
    { id: 'shin', name: 'Shin', qty: 2, ...link(g.shin_mm), load: 'link', length_mm: g.shin_mm, section: sec },
    { id: 'wheel_mount', name: 'Wheel motor mount', qty: 2, volume_cm3: 60, area_cm2: 220, load: 'motor', hot: true },
    { id: 'sensor_head', name: 'Sensor head', qty: 1, volume_cm3: 260, area_cm2: 1400, load: 'light' },
    { id: 'battery_tray', name: 'Battery tray', qty: 1, volume_cm3: 110, area_cm2: 700, load: 'light' },
  ].map((p) => ({ ...p, estimate: true }));
}

// ----------------------------------------------------------------------------- the model

export function evaluate(design, catalog, materials, opts = {}) {
  const o = { ...DEFAULTS, ...opts };
  const d = design;
  const pick = (slot) => resolvePart(d.parts[slot], catalog);
  const checks = [];
  const check = (id, level, text) => checks.push({ id, level, text });

  // --- BOM: catalogue parts
  const slots = [
    ['compute', 1], ['lidar', 1], ['stereo', 1], ['depth', 1],
    ['leg_actuator', 4], ['wheel_motor', 2], ['motor_driver', d.parts.motor_driver ? 2 : 0],
    ['battery', d.battery_count ?? 1], ['dcdc', 1], ['estop', 1], ['can_adapter', 1], ['imu', 1],
  ];
  const lines = [];
  for (const [slot, qty] of slots) {
    const item = pick(slot);
    if (!item || !qty) continue;
    lines.push({ slot, id: item.id, name: `${item.vendor} ${item.model}`, qty, group: bomGroup(item),
                 unit_usd: item.price_usd, mass_g: spec(item, 'mass_g'), source: item.buy?.[0]?.url ?? item.sources?.[0] ?? null,
                 price_checked: item.price_checked ?? null });
    if (item.price_usd == null) check(`price-${slot}`, 'warn', `${item.vendor} ${item.model} has no public price; it is left out of the total.`);
    if (spec(item, 'mass_g') == null) check(`mass-${slot}`, 'warn', `${item.vendor} ${item.model} has no published mass; it is left out of the mass budget.`);
  }

  // --- BOM: printed parts
  const parts = printedParts(d).map((p) => {
    const matId = d.materials?.parts?.[p.id] ?? d.materials?.default ?? 'pla';
    const m = materials[matId];
    const grams = printedMassG(p.volume_cm3, p.area_cm2, m, d.print);
    return { ...p, material: matId, mass_g: grams, filament_usd: (grams / 1000) * m.price_usd_per_kg };
  });
  const filamentG = parts.reduce((s, p) => s + p.mass_g * p.qty, 0);
  const filamentUsd = parts.reduce((s, p) => s + p.filament_usd * p.qty, 0);
  lines.push({ slot: 'printed', id: 'printed-parts', name: `Printed parts (${parts.reduce((s, p) => s + p.qty, 0)} parts, ${Math.round(filamentG)} g filament)`,
               qty: 1, group: 'chassis_actuators', unit_usd: filamentUsd, mass_g: filamentG, estimate: true });
  const hardware = d.hardware_allowance ?? { usd: 60, mass_g: 400, note: 'bearings, fasteners, inserts, wiring' };
  lines.push({ slot: 'hardware', id: 'hardware-allowance', name: `Hardware allowance (${hardware.note})`, qty: 1,
               group: 'chassis_actuators', unit_usd: hardware.usd, mass_g: hardware.mass_g, estimate: true });

  const total = (group) => lines.filter((l) => !group || l.group === group)
    .reduce((s, l) => s + (l.unit_usd ?? 0) * l.qty, 0);
  const massOf = (pred) => lines.filter(pred).reduce((s, l) => s + (l.mass_g ?? 0) * l.qty, 0);
  const cost = { sensors_compute_usd: total('sensors_compute'), chassis_actuators_usd: total('chassis_actuators'), total_usd: total() };

  // --- mass budget: what each leg carries
  const legAct = pick('leg_actuator'), wheel = pick('wheel_motor');
  const thighShin = parts.filter((p) => p.id === 'thigh' || p.id === 'shin' || p.id === 'wheel_mount')
    .reduce((s, p) => s + p.mass_g * p.qty, 0);
  const wheelMass = 2 * (spec(wheel, 'mass_g', 0));
  const kneeAtKnee = d.leg.topology === 'serial_knee_at_knee';
  const legMovingG = thighShin + wheelMass + (kneeAtKnee ? 2 * spec(legAct, 'mass_g', 0) : 0);
  const totalG = massOf(() => true);
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
    const rpm = spec(legAct, 'no_load_speed_rpm');
    const vCap = rpm ? ((rpm * 2 * Math.PI) / 60) * leverM * 0.6 : Infinity;
    const speedLimited = v > vCap;
    v = Math.min(v, vCap);
    legs.jump_height_mm = (v * v) / (2 * G) * 1000;
    legs.jump_speed_limited = speedLimited;
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
  const wRpm = spec(wheel, 'no_load_speed_rpm');
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
    const vEmpty = spec(batt, 'voltage_min_v') ?? (vNom ? vNom * 0.85 : null);
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
    if (cRange && vFull && (vFull > cRange[1] || vEmpty < cRange[0]) && !pick('dcdc')) {
      check('volts-compute', 'fail', `The compute box takes ${cRange[0]}–${cRange[1]} V; a ${vFull.toFixed(1)} V full battery needs a DC-DC converter.`);
    }
    const sensorsW = ['compute', 'lidar', 'stereo', 'depth'].reduce((s, k) => s + spec(pick(k), 'power_typical_w', 0), 0);
    const legsW = 4 * o.power.legs_standing_w, wheelsW = o.power.wheels_rolling_w;
    power.average_w = sensorsW + legsW + wheelsW + o.power.electronics_w;
    power.sensors_compute_w = sensorsW;
    if (wh) power.runtime_min = ((wh * o.efficiency) / power.average_w) * 60;
    const maxA = spec(batt, 'max_continuous_a');
    const peakDraw = 4 * spec(legAct, 'peak_current_a', 0) * 0.5 + 2 * spec(wheel, 'peak_current_a', 0);
    if (maxA && peakDraw > maxA) check('battery-current', 'warn', `Peak motor current could reach ${Math.round(peakDraw)} A; the battery is rated ${maxA} A continuous.`);
  }

  // --- printed part strength and heat
  for (const p of parts) {
    const m = materials[p.material];
    if (p.hot && m.max_service_c != null && m.max_service_c < 70) {
      check(`heat-${p.id}`, 'warn', `${p.name} in ${m.name}: it softens near ${m.max_service_c} °C and actuators can run hotter. Use ${m.next ?? 'a higher-temperature material'} or a metal spacer.`);
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
            sensors_compute_kg: massOf((l) => l.group === 'sensors_compute') / 1000 },
    legs, wheels, power,
    verdict: checks.some((c) => c.level === 'fail') ? 'fail' : checks.some((c) => c.level === 'warn') ? 'warn' : 'ok',
  };
}
