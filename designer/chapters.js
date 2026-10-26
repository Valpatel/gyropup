// The guide: chapters in order. A chapter may be skipped (when) and offers options that either set a catalog part
// (slot + catalog filter) or apply a change to the design (apply). The narrative is a function of the design so
// the story follows the choices.

import { LEG_TOPOLOGIES } from './model.js';

const byCat = (cat) => (item) => item.category === cat;

export const SIZES = {
  compact: { name: 'Compact', blurb: 'Short legs, low centre of mass. Easiest to balance and to print.',
             geometry: { thigh_mm: 160, shin_mm: 160, wheel_diameter_mm: 165 } },
  sturdy: { name: 'Sturdy', blurb: 'Diablo-like proportions. A good default for the sensor payload.',
            geometry: { thigh_mm: 200, shin_mm: 200, wheel_diameter_mm: 180 } },
  tall: { name: 'Tall', blurb: 'Long legs for a high sensor view and big jumps; needs the strongest motors.',
          geometry: { thigh_mm: 240, shin_mm: 240, wheel_diameter_mm: 200 } },
};

export const COLORS = [
  { id: 'duckling', name: 'Duckling yellow', hex: '#f5b82e' },
  { id: 'tangerine', name: 'Tangerine', hex: '#ef7d32' },
  { id: 'mint', name: 'Mint', hex: '#5cc8a8' },
  { id: 'sky', name: 'Sky', hex: '#5aa9e6' },
  { id: 'charcoal', name: 'Charcoal', hex: '#3b3f46' },
];

export const CHAPTERS = [
  {
    id: 'size', title: 'Meet your gyropup',
    story: () => `Every gyropup balances on two wheels and crouches, stands and hops on two legs, like the Diablo. `
      + `It carries a real brain and real senses, so it is a working robot, not a toy, but it should still be fun `
      + `to be around. First: how big is it?`,
    options: () => Object.entries(SIZES).map(([id, s]) => ({
      id, name: s.name, blurb: s.blurb,
      chips: [`thigh ${s.geometry.thigh_mm} mm`, `shin ${s.geometry.shin_mm} mm`, `wheel ${s.geometry.wheel_diameter_mm} mm`],
      selected: (d) => d.size === id,
      apply: (d) => { d.size = id; Object.assign(d.geometry, s.geometry); },
    })),
  },
  {
    id: 'brain', title: 'A brain to think with',
    story: () => `Your gyropup thinks with a Jetson AGX Orin 32GB in the J501 compute box. It is the heaviest single `
      + `part on the robot, so everything else is sized around it.`,
    slot: 'compute', filter: (i) => i.category === 'compute' && /orin|jetson|raspberry/i.test(i.model + i.id), optional: false,
  },
  {
    id: 'lidar', title: 'Eyes that see all around',
    story: () => `A spinning lidar sees 360° around the robot. It sits on top so nothing blocks its view. `
      + `It is heavy and high up, which makes balancing harder, so the legs and wheels must be stronger.`,
    slot: 'lidar', filter: (i) => i.category === 'sensor' && /lidar/i.test(i.specs?.type ?? i.model + i.notes), optional: true,
  },
  {
    id: 'stereo', title: 'Eyes that see depth',
    story: () => `A stereo camera gives colour, depth and visual odometry for mapping.`,
    slot: 'stereo', filter: (i) => i.category === 'sensor' && /zed/i.test(i.model), optional: true,
  },
  {
    id: 'depth_front', title: 'A depth camera looking ahead',
    story: () => `A RealSense depth camera sees close obstacles and the ground just ahead of the wheels. It sits in a `
      + `cradle on a 1/4-20 screw that fits a D415 or a D435, so cameras swap in a minute.`,
    slot: 'depth_front', filter: (i) => i.category === 'sensor' && /realsense/i.test(i.vendor + i.model), optional: true,
  },
  {
    id: 'depth_rear', title: 'Eyes in the back of its head',
    story: () => `A second depth camera, facing backwards, lets gyropup reverse safely. It uses the same cradle as the front one.`,
    slot: 'depth_rear', filter: (i) => i.category === 'sensor' && /realsense/i.test(i.vendor + i.model), optional: true,
  },
  {
    id: 'imu', title: 'A sense of balance',
    story: () => `Balancing needs a fast, rigidly mounted IMU on the body near the centre of mass, not on the lidar `
      + `mast, which flexes and carries a spinning rotor.`,
    slot: 'imu', filter: (i) => i.category === 'imu', optional: true,
  },
  {
    id: 'topology', title: 'How the legs bend',
    story: () => `The legs carry the body and soak up bumps. Where the motors sit decides how quick and strong `
      + `the legs are.`,
    options: () => Object.entries(LEG_TOPOLOGIES).map(([id, t]) => ({
      id, name: t.name, blurb: t.note,
      selected: (d) => d.leg.topology === id,
      apply: (d) => { d.leg.topology = id; },
    })),
  },
  {
    id: 'leg_actuator', title: 'Muscles for the legs',
    story: (d, r) => `Four actuators move the legs. In a deep crouch each one holds about `
      + `${r.legs.static_torque_nm.toFixed(1)} N·m, and standing up quickly or landing a hop takes about `
      + `${r.legs.dynamic_torque_nm.toFixed(1)} N·m. Pick one with room to spare.`,
    slot: 'leg_actuator', filter: byCat('leg_actuator'),
  },
  {
    id: 'wheel_motor', title: 'Wheels to balance on',
    story: () => `The wheel motors do the balancing: they drive under the body to keep it upright. They need `
      + `strong torque from a standstill and a fine encoder for smooth slow balancing.`,
    slot: 'wheel_motor', filter: byCat('wheel_motor'),
  },
  {
    id: 'motor_driver', title: 'A driver for the wheels',
    when: (d, cat) => d.parts.wheel_motor && cat[d.parts.wheel_motor]?.specs?.integrated_driver === false,
    story: () => `Your wheel motors don't have a driver built in, so each one needs a motor controller.`,
    slot: 'motor_driver', filter: byCat('motor_driver'),
  },
  {
    id: 'battery', title: 'Energy',
    story: (d, r) => `The battery sets the voltage for everything. Your build draws about `
      + `${Math.round(r.power.average_w ?? 0)} W on average, and the compute box accepts 12–36 V.`,
    slot: 'battery', filter: byCat('battery'),
  },
  {
    id: 'dcdc_compute', title: 'Taming the voltage',
    when: (d, cat, r) => r.checks.some((c) => c.id === 'volts-compute') || d.parts.dcdc_compute,
    story: () => `Your battery's full-charge voltage is higher than the compute box accepts, so it needs a DC-DC converter.`,
    slot: 'dcdc_compute', filter: byCat('dcdc'), optional: true,
  },
  {
    id: 'dcdc_12v', title: 'A steady 12 volts for the lidar',
    when: (d) => Boolean(d.parts.lidar),
    story: () => `The VLP-16 accepts only 9–18 V and surges about 3 A when it spins up, so it runs from a regulated 12 V converter.`,
    slot: 'dcdc_12v', filter: (i) => i.category === 'dcdc' && /12/.test(i.model + i.id), optional: true,
  },
  {
    id: 'safety', title: 'A big red button',
    story: () => `Every gyropup has an emergency stop that cuts motor power while the computer keeps running.`,
    slot: 'estop', filter: (i) => i.category === 'estop', optional: true,
  },
  {
    id: 'can', title: 'Talking to the motors',
    story: () => `The motors talk over CAN. The adapter connects them to the Jetson.`,
    slot: 'can_adapter', filter: byCat('can_adapter'), optional: true,
  },
  {
    id: 'materials', title: 'What it is made of',
    story: () => `Everything starts as PLA printed on a P1S: cheap, and fast to change. Parts that get hot or `
      + `carry the most load can move up the ladder to PETG or carbon-fibre-filled filament, or be swapped for `
      + `SendCutSend aluminium or carbon-fibre tube. The strength checks below show which parts need it.`,
    kind: 'materials',
  },
  {
    id: 'character', title: 'Give it a personality',
    story: () => `Like Open Duck Mini, a gyropup should be fun to watch: a friendly colour, a face, and motion `
      + `with a little bounce. The lidar and antennas make a natural tuft on top.`,
    kind: 'character',
  },
  { id: 'summary', title: 'Your gyropup', story: () => `Here is your robot: what it costs, what it weighs, what it can do, `
      + `and what to print.`, kind: 'summary' },
];

export function visibleChapters(design, catalog, result) {
  return CHAPTERS.filter((c) => !c.when || c.when(design, catalog, result));
}
