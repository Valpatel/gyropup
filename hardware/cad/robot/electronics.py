"""Where every electronic part sits, and the printed front bay that holds the power electronics.

The tub holds the battery on its cradle, one wheel driver in each side slot beside the battery (next to its wheel:
short phase leads), the IMU and the balance MCU in the side slots' ends. Everything else of the power chain (the 24 V
and 12 V converters, the fuse block, the contactor, the anti-spark switch, the regen clamp) goes in a printed bay on
the tub's front wall, under the face; its depth comes from what it has to hold. The e-stop sits on the tub's rear
wall where a grown-up can reach it.

Sizes come from the catalogue (specs.dimensions_mm or length/width/height); a part without them gets an estimate,
flagged 'estimate' in the layout so it shows up in the report until its datasheet size is in. Robot frame, mm.

    items, bay, report = electronics.layout(L, design, catalog)
"""
from __future__ import annotations

import cadquery as cq

BAY_WALL = 3.0           # printed PETG bay walls
GAP = 2.0                # between parts, and to walls
# sizes used until the catalogue has them (L along x, W along y, H along z as placed; mm) and masses (g)
ESTIMATES = {
    'battery_adapter': ((120.0, 85.0, 30.0), 150), 'fuse': ((50.8, 63.5, 35.0), 120), 'contactor': ((62.0, 62.0, 80.0), 400),
    'regen_clamp': ((90.0, 60.0, 35.0), 180), 'balance_mcu': ((53.0, 40.0, 15.0), 15), 'can_transceiver': ((25.0, 15.0, 8.0), 4),
    'estop': ((40.0, 40.0, 55.0), 60), 'motor_driver': ((85.0, 50.7, 33.8), 160),
}
COLORS = {'motor_driver': '#2b6cb0', 'dcdc_compute': '#a0aec0', 'dcdc_12v': '#a0aec0', 'fuse': '#1a202c', 'contactor': '#4a5568',
          'power_switch': '#2d3748', 'regen_clamp': '#718096', 'balance_mcu': '#276749', 'can_transceiver': '#2f855a',
          'imu': '#c53030', 'estop': '#e53e3e', 'battery_adapter': '#f6e05e'}


def size_of(slot: str, item: dict | None):
    """(L, W, H, mass_g, estimate?) from the catalogue, else the estimate table."""
    s = (item or {}).get('specs', {})
    d = s.get('dimensions_mm')
    dims = tuple(d) if d and len(d) == 3 and all(d) else (s.get('length_mm'), s.get('width_mm'), s.get('height_mm'))
    est = not all(dims)
    if est:
        dims = ESTIMATES.get(slot, ((60.0, 40.0, 30.0), 100))[0]
    mass = s.get('mass_g') or s.get('mass_g_estimate') or ESTIMATES.get(slot, (None, 100))[1]
    return tuple(float(v) for v in dims), float(mass), est or not (s.get('mass_g') or s.get('mass_g_estimate'))


def _box(c, d):
    return cq.Workplane('XY').box(*d).translate(c)


def layout(L: dict, design: dict, catalog: dict, floor_t: float = 4.0, wall_t: float = 5.0):
    """Every electronic part as a placed box (centre, size along x/y/z), the bay shape, and a fit report."""
    T = L['tray']
    D, W = T['depth'], T['width']
    z0, z1 = L['trayBottom'] + floor_t, L['bodyBottom'] - 2.0           # inside the tub, under the J501 box
    part = lambda slot: catalog.get(design['parts'].get(slot) or '')
    items, notes = [], []

    def put(name, slot, center, dims, mass, est, qty_note=''):
        items.append({'name': name, 'slot': slot, 'center': [round(v, 2) for v in center], 'size': [round(v, 2) for v in dims],
                      'mass_g': mass, 'estimate': est, 'color': COLORS.get(slot, '#4a5568'), 'zone': '', 'note': qty_note})

    # --- the tub: the battery's side slots
    bl, bw, bh = (L.get('battery') or {}).get('dims', (157, 110, 92))
    slot_y0, slot_y1 = bw / 2 + GAP, W / 2 - wall_t - GAP                 # between the battery and the wall
    if design['parts'].get('motor_driver'):
        (l, w, h), m, est = size_of('motor_driver', part('motor_driver'))
        dims = (l, min(w, h), max(w, h))                                   # standing on its long edge, thin side across
        if dims[1] > slot_y1 - slot_y0:
            notes.append(f"the wheel drivers ({dims[1]:.0f} mm thick) do not fit the {slot_y1 - slot_y0:.0f} mm side slots")
        for side, tag in ((1, 'l'), (-1, 'r')):
            put(f'motor_driver_{tag}', 'motor_driver', (0.0, side * (slot_y0 + dims[1] / 2), z0 + dims[2] / 2), dims, m, est)
    ends_x = (D / 2 - wall_t - GAP, (l if design['parts'].get('motor_driver') else 0) / 2 + GAP)   # slot ends beyond the drivers
    if design['parts'].get('imu'):
        (l, w, h), m, est = size_of('imu', part('imu'))
        put('imu', 'imu', (-(ends_x[0] + ends_x[1]) / 2, slot_y0 + w / 2, z0 + h / 2), (l, w, h), m, est)
    for slot, x_sign, name in (('balance_mcu', -1, 'balance_mcu'),):
        (l, w, h), m, est = size_of(slot, part(slot))
        dims = (l, h, w)                                                   # board on edge, against the wall
        put(name, slot, (x_sign * (ends_x[0] + ends_x[1]) / 2, -(slot_y1 - dims[1] / 2), z0 + 10 + dims[2] / 2), dims, m, est)
    nc = (design.get('part_qty') or {}).get('can_transceiver', 2)
    (l, w, h), m, est = size_of('can_transceiver', part('can_transceiver'))
    for k in range(nc):                                                    # on the floor at the front of the right slot
        put(f'can_transceiver_{k + 1}', 'can_transceiver', ((ends_x[0] + ends_x[1]) / 2, -(slot_y0 + w / 2 + k * (w + 3)), z0 + h / 2), (l, w, h), m, est)

    # --- the front bay: a 3D packing (extreme points): each part, biggest first, tries every orientation at every free
    # corner and goes where the bay stays shallowest (then lowest, then leftmost); the bay is as deep as the result
    bx0 = D / 2 + BAY_WALL                                                   # inside the bay, from the tub's front wall
    yl, yr = -(W / 2 - BAY_WALL - GAP), W / 2 - BAY_WALL - GAP
    import itertools
    want = [s_ for s_ in ('regen_clamp', 'dcdc_compute', 'dcdc_12v', 'contactor', 'power_switch', 'fuse') if design['parts'].get(s_)]
    todo = []
    for slot in want:
        (l, w, h), m, est = size_of(slot, part(slot))
        todo.append((l * w * h, slot, (l, w, h), m, est))
    placed = []                                                          # (x0, y0, z0, x1, y1, z1)
    points = [(bx0, yl, z0)]
    depth = 0.0

    def free(b):
        if b[1] < yl - 1e-6 or b[4] > yr + 1e-6 or b[2] < z0 - 1e-6 or b[5] > z1 + 1e-6 or b[0] < bx0 - 1e-6:
            return False
        return all(b[3] <= q[0] + 1e-6 or b[0] >= q[3] - 1e-6 or b[4] <= q[1] + 1e-6 or b[1] >= q[4] - 1e-6
                   or b[5] <= q[2] + 1e-6 or b[2] >= q[5] - 1e-6 for q in placed)

    for _, slot, size, m, est in sorted(todo, reverse=True):
        best = None
        for dims in set(itertools.permutations(size)):
            for (x, y, z) in points:
                b = (x, y, z, x + dims[0] + GAP, y + dims[1] + GAP, z + dims[2] + GAP)
                if not free(b):
                    continue
                key = (round(max(depth, b[3] - GAP - bx0), 1), round(z, 1), round(x, 1), round(y, 1))
                if best is None or key < best[0]:
                    best = (key, b, dims)
        if best is None:
            notes.append(f'{slot} does not fit the bay')
            continue
        _, b, dims = best
        placed.append(b)
        put(slot, slot, (b[0] + dims[0] / 2, b[1] + dims[1] / 2, b[2] + dims[2] / 2), dims, m, est)
        items[-1]['zone'] = 'bay'
        depth = max(depth, b[3] - GAP - bx0)
        points += [(b[3], b[1], b[2]), (b[0], b[4], b[2]), (b[0], b[1], b[5])]
    bay_depth = depth + GAP + BAY_WALL
    # the e-stop on the rear wall, the button outside, high up
    if design['parts'].get('estop'):
        (l, w, h), m, est = size_of('estop', part('estop'))
        put('estop', 'estop', (-D / 2 - h / 2, 0.0, z1 - 25.0), (h, l, w), m, est)
    for it in items:
        it['zone'] = it['zone'] or ('tub' if abs(it['center'][0]) < D / 2 else 'outside')
    shape = bay(L, bay_depth, floor_t)
    report = {'bay_depth_mm': round(bay_depth, 1), 'notes': notes, 'estimates': sorted({i['slot'] for i in items if i['estimate']}),
              'count': len(items)}
    return items, shape, report


def bay(L: dict, depth: float, floor_t: float = 4.0):
    """The printed front bay (PETG): an open-backed box on the tub's front wall, as wide and tall as the tub, a
    flange with 4 x M4 into the tub wall's inserts, a lid in its front for the face, cable passes into the tub."""
    T = L['tray']
    D, W = T['depth'], T['width']
    z0, z1 = L['trayBottom'], L['bodyBottom']
    H = z1 - z0
    outer = cq.Workplane('XY').box(depth, W, H).translate((D / 2 + depth / 2, 0, z0 + H / 2))
    inner = cq.Workplane('XY').box(depth - BAY_WALL, W - 2 * BAY_WALL, H - floor_t).translate((D / 2 + (depth - BAY_WALL) / 2 - 0.01, 0, z0 + floor_t + (H - floor_t) / 2 + 0.01))
    b = outer.cut(inner)
    for (y, z) in [(-W / 2 + 12, z0 + 12), (W / 2 - 12, z0 + 12), (-W / 2 + 12, z1 - 12), (W / 2 - 12, z1 - 12)]:
        b = b.union(cq.Workplane('YZ', origin=(D / 2, 0, 0)).center(y, z).circle(6).extrude(8))
        b = b.cut(cq.Workplane('YZ', origin=(D / 2 - 1, 0, 0)).center(y, z).circle(2.25).extrude(12))
    for z in (z0 + 25, z0 + 60):                                          # cable passes through the tub's front wall
        b = b.cut(cq.Workplane('YZ', origin=(D / 2 - 1, 0, 0)).center(0, z).rect(60, 18).extrude(6))
    return b
