// Side view of the current design as an SVG string, drawn to scale (1 unit = 1 mm). Knees bend backwards, which keeps
// the wheel under the hip. `crouch` 0..1 goes from standing (knee_max_deg) to the deepest crouch (knee_min_deg).

import { legPose } from './model.js';

export function robotSvg(design, catalog, { crouch = 0.35, color = '#f5b82e', width = 360 } = {}) {
  const g = design.geometry;
  const knee = g.knee_max_deg - crouch * (g.knee_max_deg - g.knee_min_deg);
  const { hip_height } = legPose(g.thigh_mm, g.shin_mm, knee);
  const r = g.wheel_diameter_mm / 2;
  const axleZ = r, hipZ = axleZ + hip_height;
  // knee position: rotate the thigh back from the hip-wheel line by the triangle angle at the hip
  const a = g.thigh_mm, b = g.shin_mm, h = hip_height;
  const hipAngle = Math.acos(Math.min(1, Math.max(-1, (a * a + h * h - b * b) / (2 * a * h))));
  const kx = -a * Math.sin(hipAngle), kz = hipZ - a * Math.cos(hipAngle);

  const body = g.body;                       // compute box: depth along x, height along z
  const trayH = g.battery_tray_mm ?? 45;
  const bodyBottom = hipZ - 25, bodyTop = bodyBottom + trayH + body.height_mm;
  const bx0 = -body.depth_mm / 2, bx1 = body.depth_mm / 2;

  const parts = design.parts;
  const has = (slot) => Boolean(parts[slot] && catalog[parts[slot]]);
  let headTop = bodyTop;
  const head = [];
  if (has('stereo')) {
    head.push(`<rect x="${bx1 - 40}" y="${-(bodyTop + 32)}" width="36" height="30" rx="8" class="sensor"/>`
      + `<circle cx="${bx1 - 6}" cy="${-(bodyTop + 17)}" r="6" class="lens"/>`);
    headTop = Math.max(headTop, bodyTop + 32);
  }
  if (has('lidar')) {
    const mount = design.lidar_mount ?? 'top';
    if (mount === 'under') {
      const lz = bodyBottom - 6;  // hangs below the tray, between the legs
      head.push(`<rect x="-52" y="${-lz}" width="104" height="72" rx="10" class="lidar"/>`
        + `<rect x="-52" y="${-(lz - 44)}" width="104" height="14" class="lidar-band"/>`);
    } else {
      const mast = mount === 'mast' ? 50 : 8, lz = bodyTop + mast;
      if (mount === 'mast') head.push(`<rect x="-8" y="${-lz}" width="16" height="${mast}" class="mast"/>`);
      head.push(`<rect x="-52" y="${-(lz + 72)}" width="104" height="72" rx="10" class="lidar"/>`
        + `<rect x="-52" y="${-(lz + 44)}" width="104" height="14" class="lidar-band"/>`
        + `<path d="M -64 ${-(lz + 2)} V ${-(lz + 84)} Q 0 ${-(lz + 104)} 64 ${-(lz + 84)} V ${-(lz + 2)}" class="crown"/>`);
      headTop = lz + 100;
    }
  }
  if (has('depth_front')) {
    head.push(`<rect x="${bx1 - 4}" y="${-(bodyBottom + trayH + 30)}" width="14" height="26" rx="4" class="sensor"/>`);
  }
  if (has('depth_rear')) {
    head.push(`<rect x="${bx0 - 10}" y="${-(bodyBottom + trayH + 30)}" width="14" height="26" rx="4" class="sensor"/>`);
  }

  // face on the front of the body: friendly eyes with a little smile
  const eyeZ = bodyBottom + trayH + body.height_mm * 0.62;
  const face = `<circle cx="${bx1 - 2}" cy="${-eyeZ}" r="11" class="eye"/><circle cx="${bx1 + 1}" cy="${-eyeZ}" r="5" class="pupil"/>`
    + `<path d="M ${bx1 - 3} ${-(eyeZ - 26)} q 8 7 0 14" class="smile"/>`;

  const minX = Math.min(bx0, kx - 30, -r) - 30, maxX = Math.max(bx1 + 40, r) + 30;
  const top = headTop + 30, bottom = -10;
  const vb = `${minX} ${-top} ${maxX - minX} ${top - bottom}`;
  const wheelSpokes = [0, 60, 120].map((d) => {
    const t = (d * Math.PI) / 180;
    return `<line x1="${-r * 0.75 * Math.cos(t)}" y1="${-(axleZ + r * 0.75 * Math.sin(t))}" x2="${r * 0.75 * Math.cos(t)}" y2="${-(axleZ - r * 0.75 * Math.sin(t))}" class="spoke"/>`;
  }).join('');

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb}" width="${width}" role="img" aria-label="Side view of your gyropup">
  <style>
    .ground{stroke:var(--line,#c9c3b8);stroke-width:3}
    .tyre{fill:#2c2f36}.hub{fill:#8a9099}.spoke{stroke:#5d636c;stroke-width:5}
    .limb{stroke:${color};stroke-width:30;stroke-linecap:round;fill:none}
    .joint{fill:#3b3f46}
    .body{fill:${color};stroke:#00000022;stroke-width:3}
    .box{fill:#2f343c}.tray{fill:#6b717a}
    .sensor{fill:#2f343c}.lens{fill:#6fb4ff}.mast{fill:#6b717a}
    .lidar{fill:#3b3f46}.crown{fill:none;stroke:${color};stroke-width:9;stroke-linejoin:round}.lidar-band{fill:#20242a}
    .eye{fill:#fff;stroke:#2f343c;stroke-width:3}.pupil{fill:#20242a}.smile{fill:none;stroke:#20242a;stroke-width:3;stroke-linecap:round}
  </style>
  <line x1="${minX}" y1="0" x2="${maxX}" y2="0" class="ground"/>
  <rect x="${bx0}" y="${-(bodyBottom + trayH)}" width="${body.depth_mm}" height="${trayH}" rx="10" class="tray"/>
  <rect x="${bx0 + 6}" y="${-bodyTop}" width="${body.depth_mm - 12}" height="${body.height_mm}" rx="16" class="body"/>
  ${head.join('\n  ')}
  ${face}
  <path d="M 0 ${-hipZ} L ${kx} ${-kz} L 0 ${-axleZ}" class="limb"/>
  <circle cx="0" cy="${-axleZ}" r="${r}" class="tyre"/><circle cx="0" cy="${-axleZ}" r="${r * 0.55}" class="hub"/>${wheelSpokes}
  <circle cx="0" cy="${-hipZ}" r="22" class="joint"/><circle cx="${kx}" cy="${-kz}" r="18" class="joint"/>
</svg>`;
}
