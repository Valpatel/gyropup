// Existing product five-bar solver, shared by current and recorded presentations.
// the five-bar in the leg's plane (mm, x forward, z up): motors at (+-D/2, 0), upper links l1, lower links l2
export function fiveBar(D, l1, l2) {
  const A = [D / 2, 0], B = [-D / 2, 0];
  const ik = (x, z) => {
    const out = [];
    for (const [P, side] of [[A, 1], [B, -1]]) {
      const vx = x - P[0], vz = z - P[1], r = Math.hypot(vx, vz);
      if (r > l1 + l2 || r < Math.abs(l1 - l2)) return null;
      const a = (l1 * l1 - l2 * l2 + r * r) / (2 * r), h = Math.sqrt(Math.max(0, l1 * l1 - a * a));
      const mx = P[0] + (a * vx) / r, mz = P[1] + (a * vz) / r;
      const c1 = [mx - (h * vz) / r, mz + (h * vx) / r], c2 = [mx + (h * vz) / r, mz - (h * vx) / r];
      const C = (c1[0] - c2[0]) * side > 0 ? c1 : c2;
      let ang = Math.atan2(C[1] - P[1], C[0] - P[0]);
      if (side < 0 && ang > 0) ang -= 2 * Math.PI;                    // the rear link's angles run continuously
      out.push({ ang, C });
    }
    return out;
  };
  return { A, B, ik };
}
