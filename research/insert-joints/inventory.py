#!/usr/bin/env python3
"""Inventory of Gyropup's heat-set insert joints and printed parts clamped by metal (issue #137 / cad-agent #230).

Kernel-free: reads the repository's source constants (bound by pattern, so a change to a bound line fails the check
and asks for a regeneration), its generated exports (body joint integrity, leg loads, FEA summaries, the turret's mount
contract) and the hardware catalogue, then screens each joint against the insert maker's hole and depth limits,
Spirol's boss rule, its screw stack, its print orientation, what it clamps and the loads the repository's own studies
give it. It writes joints.json and joints.md beside it.

    python3 research/insert-joints/inventory.py           # regenerate
    python3 research/insert-joints/inventory.py --check   # exit 1 if joints.json / joints.md are stale
    python3 research/insert-joints/inventory.py --cad-agent PATH/src   # also cross-check the formulas against cadagent

Everything here is a screen with stated assumptions, not a qualification: pull-out capacities are scaled from published
M3 tests, bearing allowables are the repository's own creep screens, and no part has been printed or tested for this.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT_JSON = HERE / 'joints.json'
OUT_MD = HERE / 'joints.md'

# ---------------------------------------------------------------------------------------------------- basis

K_NUT = 0.2            # nut factor when the condition is not stated (cadagent.formulas.screws NUT_FACTORS['unstated'])
ENGAGE_MIN_D = 1.2     # x d into an insert: cad/body_joints.py ENGAGE['insert'] (the insert's pull-out governs)
SPIROL_BOSS = 2.0      # boss diameter at least 2 x the insert's diameter (Spirol, 'How to design the proper hole')
TIP_ROOM = 0.5         # mm: a screw tip this close to a blind hole's floor is reported (tolerance of print + screw)
SOURCES = {
    'spirol': 'https://uk.spirol.com/assets/files/ins-wp-how-to-design-the-proper-hole-for-heat-ultrasonic-inserts-uk.pdf',
    'cnck_petg': 'https://www.cnckitchen.com/blog/helicoils-threaded-insets-and-embedded-nuts-in-3d-prints-strength-amp-strength-assessment',
    'cnck_pla': 'https://www.cnckitchen.com/blog/threaded-inserts-for-3d-prints-cheap-vs-expensive',
    'cnck_hole': 'https://www.cnckitchen.com/blog/are-our-heat-set-insert-datasheets-wrong',
    'mcmaster': 'https://www.mcmaster.com/94459A775/',
}
# CNC Kitchen, M3 x 5.7 Ruthex insert in PETG (4 perimeters, 100 % infill): 119 kgf pull-out (the insert ripped out),
# 3 N m torque-out. In Ø4.0 (Ruthex's hole) that is a mean shear of 1167 N / (pi 4.0 x 5.7) on the knurl's cylinder.
PETG_TEST = {'kgf': 119.0, 'hole_mm': 4.0, 'length_mm': 5.7, 'torque_out_nm': 3.0, 'source': 'cnck_petg'}
PLA_TEST = {'kgf': 181.0, 'hole_mm': 4.0, 'length_mm': 5.7, 'torque_out_nm': 3.5, 'source': 'cnck_pla'}
G0 = 9.80665


def tau_petg():
    t = PETG_TEST
    return t['kgf'] * G0 / (math.pi * t['hole_mm'] * t['length_mm'])


class Stale(RuntimeError):
    pass


class Repo:
    """Reads the repository and records every bound source line, so a regeneration notices changes."""

    def __init__(self, root: Path):
        self.root = root
        self.bindings = []
        self._text = {}
        self._json = {}

    def text(self, rel):
        if rel not in self._text:
            self._text[rel] = (self.root / rel).read_text()
        return self._text[rel]

    def json(self, rel):
        if rel not in self._json:
            self._json[rel] = json.loads((self.root / rel).read_text())
        return self._json[rel]

    def num(self, rel, pattern, group=1):
        m = re.search(pattern, self.text(rel), re.M)
        if not m:
            raise Stale(f'{rel}: no match for {pattern!r}; the source changed, so update research/insert-joints/inventory.py')
        v = float(m.group(group))
        self.bindings.append({'file': rel, 'pattern': pattern, 'value': v})
        return v

    def has(self, rel, literal):
        """A literal quoted from a source (a stale note, a torque line): returned while it is still there."""
        t = self.text(rel)
        if literal not in t:
            raise Stale(f'{rel}: {literal!r} is gone; update research/insert-joints/inventory.py (and drop a fixed finding)')
        self.bindings.append({'file': rel, 'literal': literal})
        return literal


# ---------------------------------------------------------------------------------------------------- formulas

def preload(torque_nm, d_mm, k=K_NUT):
    """Fi = T / (K d) (cadagent.formulas.screws.preload_from_torque)."""
    return torque_nm / (k * d_mm / 1000.0)


def torque_for(preload_n, d_mm, k=K_NUT):
    return k * preload_n * d_mm / 1000.0


def annulus(od, idd):
    return math.pi / 4.0 * (od ** 2 - idd ** 2)


def pullout(tau, hole_mm, length_mm):
    return tau * math.pi * hole_mm * length_mm


def r(v, n=1):
    if v is None:
        return None
    return int(round(float(v))) if n == 0 else round(float(v), n)


def q(s):
    """A quoted source literal, without the source's escaping."""
    return '"' + s.replace("\\'", "'") + '"'


# ---------------------------------------------------------------------------------------------------- inputs

def inserts(repo):
    """The four McMaster 94459A inserts in use: catalogue length, maximum hole, minimum material, knurl OD."""
    hw = repo.json('catalog/hardware.json')
    tu = repo.json('catalog/turret.json')

    def find(items, key):
        stack = [items]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                if x.get('key') == key:
                    return x
                stack.extend(x.values())
            elif isinstance(x, list):
                stack.extend(x)
        raise Stale(f'catalogue item {key} not found')

    def mm(s):
        return float(str(s).split()[0])

    out = {}
    for key, cat, pitch in (('insert_m3', hw, 0.5), ('insert_m5', hw, 0.8), ('turret_insert_m4', tu, 0.7),
                            ('turret_insert_m3_short', tu, 0.5)):
        it = find(cat, key)
        raw = it['specs']['mcmaster']['raw']
        bb = ((it.get('cad') or {}).get('bbox_mm') or {}).get('size')
        out[key] = {'pn': it['id'].split('-')[-1].upper(), 'thread': raw['Thread Size'], 'pitch_mm': pitch,
                    'length_mm': mm(raw['Installed Length']), 'max_hole_mm': mm(raw['For Maximum Hole Diameter']),
                    'min_material_mm': mm(raw['For Minimum Material Thickness']),
                    'od_mm': round(bb[0], 2) if bb else None,
                    'od_basis': 'McMaster STEP bounding box (catalog/hardware.json cad.bbox_mm)' if bb else None}
    # no STEP for these two: the M3 short has the M3's hole (same knurl), the M4 the same 0.7 mm over its hole as M3/M5
    out['turret_insert_m3_short']['od_mm'] = out['insert_m3']['od_mm']
    out['turret_insert_m3_short']['od_basis'] = 'assumed equal to 94459A140 (same 4.0 mm maximum hole)'
    over = (out['insert_m3']['od_mm'] - out['insert_m3']['max_hole_mm'] + out['insert_m5']['od_mm'] - out['insert_m5']['max_hole_mm']) / 2
    out['turret_insert_m4']['od_mm'] = round(out['turret_insert_m4']['max_hole_mm'] + over, 2)
    out['turret_insert_m4']['od_basis'] = f'estimate: maximum hole + {over:.2f} mm (the M3 and M5 STEPs); no STEP cached'
    return out


def materials(repo):
    """Across-layer strengths for the pull-out scaling and the bearing screens (the repository's own values)."""
    m = repo.json('catalog/materials.json')
    pa_z_dry = float(m['pa6-cf']['tensile_z_mpa'])
    petg_z = float(m['petg']['tensile_z_mpa'])
    wet = 25.5 / 54.0    # Polymaker PA6-CF20 V1.1, Z tensile wet / dry (the humid factor cad/turret_studies.py uses)
    tp = tau_petg()
    pa_z = pa_z_dry * wet
    return {
        'petg': {'z_mpa': petg_z, 'tau_mpa': round(tp, 2), 'basis': 'CNC Kitchen M3 x 5.7 in PETG (measured)'},
        'pa6-cf': {'z_mpa': round(pa_z, 2), 'tau_mpa': round(tp * pa_z / petg_z, 2),
                   'basis': f'PETG test x humid PA6-CF / PETG across-layer strength ({pa_z:.1f} / {petg_z:g} MPa: Bambu TDS Z '
                            f'{pa_z_dry:g} MPa x Polymaker wet/dry 25.5/54)'},
        'bearing_sustained_mpa': repo.num('cad/studies.py', r"'washer_mpa': ([\d.]+),"),
        'bearing_humid_mpa': repo.num('cad/studies.py', r"'bearing_mpa': ([\d.]+),"),
    }


# screw heads: nominal head diameters (ISO 4762 socket, ISO 7380 button, ISO 7045 pan, DIN 464 thumb collar)
HEAD_D = {('socket', 3): 5.5, ('socket', 4): 7.0, ('socket', 5): 8.5, ('socket', 6): 10.0,
          ('button', 3): 5.7, ('button', 4): 7.6, ('button', 5): 9.5, ('pan', 3): 5.6, ('thumb', 3): 6.0, ('thumb', 4): 8.0}


# ---------------------------------------------------------------------------------------------------- the screen

def screen(j, ins, mat, F):
    """Generic checks of one joint family. Each finding: (code, level, text). level: fix | owner | check | note."""
    out = []
    d = j.get('d_mm')
    if j.get('insert'):
        i = ins[j['insert']]
        L, p = i['length_mm'], i['pitch_mm']
        hole = j['hole']
        if hole['d'] > i['max_hole_mm'] + 0.01:
            out.append(('hole-oversize', 'fix', f"pilot Ø{hole['d']:g} over the maker's maximum Ø{i['max_hole_mm']:g}"))
        elif hole['d'] < i['max_hole_mm'] - 0.25:
            out.append(('hole-undersize', 'check', f"pilot Ø{hole['d']:g} is {i['max_hole_mm'] - hole['d']:.2f} under the maximum"))
        if not hole.get('through'):
            if hole['depth'] < L - 0.05:
                out.append(('pilot-shorter-than-insert', 'fix',
                            f"blind pilot {hole['depth']:g} deep for a {L:g} mm insert: it cannot seat flush"))
            elif hole['depth'] < L + 2 * p - 0.01:
                out.append(('pilot-below-spirol', 'note', f"blind pilot {hole['depth']:g} < insert + 2 pitches = {L + 2 * p:g} "
                            f"(Spirol: room for displaced melt; {hole['depth'] - L:.1f} mm below the insert)"))
        if j.get('material_mm') is not None and j['material_mm'] < i['min_material_mm'] - 0.01:
            out.append(('material-thin', 'note', f"{j['material_mm']:g} mm of part at the insert < the maker's "
                        f"{i['min_material_mm']:g} mm minimum material"))
        boss = j.get('boss_mm')
        if boss:
            ratio = boss / i['od_mm']
            j['boss_ratio'] = r(ratio, 2)
            j['boss_wall_mm'] = r((boss - i['od_mm']) / 2, 2)
            if ratio < SPIROL_BOSS - 0.005:
                out.append(('boss-thin', 'note', f"boss Ø{boss:g} is {ratio:.2f} x the insert's Ø{i['od_mm']:g} "
                            f"(wall {j['boss_wall_mm']:g} mm; Spirol asks 2-3 x)"))
        tip = j.get('tip_depth_mm')
        if tip is not None:
            eng = min(tip, L)
            j['thread_engaged_mm'] = r(eng, 2)
            if not hole.get('through'):
                clear = hole['depth'] - tip
                j['tip_clear_mm'] = r(clear, 2)
                if clear < 0:
                    out.append(('screw-bottoms', 'fix', f"the screw tip reaches {tip:g} mm below the insert's face but the blind "
                                f"pilot is {hole['depth']:g} deep: it bottoms {-clear:.1f} mm early and jacks the insert out "
                                f"(Spirol) instead of clamping"))
                elif clear < TIP_ROOM:
                    out.append(('tip-near-floor', 'check', f"tip {clear:.2f} mm off the pilot floor"))
            if eng < ENGAGE_MIN_D * d - 0.01:
                out.append(('engagement-low', 'fix' if j.get('longer_screw_fits') else 'note',
                            f"{eng:g} mm of thread engaged = {eng / d:.2f} d (the body checks ask {ENGAGE_MIN_D:g} d)"))
        if j.get('axis') == 'layer-plane':
            out.append(('axis-in-layer-plane', 'note', 'insert axis lies in the layer plane: installation and pull-out hoop '
                        'stress opens the layer bonds through the axis (an axis along the print z is the strong way)'))
        if j.get('mating_hole_mm') and j['mating_hole_mm'] >= i['od_mm']:
            out.append(('mating-hole-over-insert', 'owner', f"the clamped part's Ø{j['mating_hole_mm']:g} hole is not smaller than "
                        f"the insert (Ø{i['od_mm']:g}): tightening pulls the insert (Spirol's jack-out)"))
        tau = mat[j['material']]['tau_mpa']
        cap = pullout(tau, hole['d'], L)
        j['pullout_est_n'] = r(cap, 0)
        if j.get('pullout_repo_n'):
            cap = min(cap, j['pullout_repo_n'])
        j['capacity_n'] = r(cap, 0)
        loads = j.get('loads') or []
        worst = max((x['per_insert_n'] for x in loads if x.get('tension')), default=None)
        if worst:
            sf = cap / worst
            j['sf_pullout'] = r(sf, 2)
            if sf < 2.0:
                out.append(('pullout-margin', 'owner', f"pull-out estimate {cap:.0f} N / {worst:.0f} N = {sf:.2f}"))
            elif sf < 4.0:
                out.append(('pullout-margin', 'check', f"pull-out estimate {cap:.0f} N / {worst:.0f} N = {sf:.2f}: qualify with "
                            "the B4 pull-out coupon in this material and orientation"))
        pre = j.get('preload_n')
        if pre and pre > 0.5 * cap:
            out.append(('preload-vs-pullout', 'check', f"{pre:.0f} N of preload is {pre / cap:.2f} x the pull-out estimate: the "
                        "clamped part must bear on the insert's brass face (insert flush to 0.13 mm proud, Spirol), or "
                        "the knurl carries the preload too"))
    c = j.get('clamp')
    if c and c.get('printed_mm', 0) > 0 and not c.get('limiter') and c.get('bearing_od_mm'):
        pre = j.get('preload_n')
        area = annulus(c['bearing_od_mm'], c['bearing_id_mm'])
        c['bearing_area_mm2'] = r(area, 1)
        if pre:
            s = pre / area
            c['bearing_mpa'] = r(s, 1)
            allow_s, allow_h = mat['bearing_sustained_mpa'], mat['bearing_humid_mpa']
            c['preload_at_sustained_n'] = r(allow_s * area, 0)
            c['torque_at_sustained_nm'] = r(torque_for(allow_s * area, d), 2)
            if s > allow_h:
                out.append(('printed-clamp-crush', c.get('level', 'owner'), f"{pre:.0f} N on {area:.0f} mm2 of printed "
                            f"{c['material']} under the {c['bearing']} = {s:.0f} MPa (> {allow_h:g} humid, {allow_s:g} sustained); "
                            f"{c['printed_mm']:g} mm of plastic in the clamp, no limiter"))
            elif s > allow_s:
                out.append(('printed-clamp-creep', 'check', f"{s:.0f} MPa under the {c['bearing']} (> {allow_s:g} MPa sustained): "
                            f"{c['printed_mm']:g} mm of printed {c['material']} will creep and shed preload"))
    for code, level, text in j.pop('extra', []):
        out.append((code, level, text))
    j['findings'] = [{'code': a, 'level': b, 'text': t} for a, b, t in out]
    lv = [b for _, b, _ in out]
    j['verdict'] = ('fix' if 'fix' in lv else 'owner' if 'owner' in lv else 'check' if 'check' in lv
                    else 'note' if 'note' in lv else 'ok')
    return j


# ---------------------------------------------------------------------------------------------------- the joints

def body_families(repo):
    """Every insert joint of the P3 body from exports/body/integrity.json, grouped by receiving part family."""
    integ = repo.json('exports/body/integrity.json')
    seen, fam = set(), {}
    for jt in integ['joints']:
        if jt['receiver'][0] != 'insert' or jt['stage'] != 'P3' or jt['joint'] in seen:
            continue
        seen.add(jt['joint'])
        part = jt['receiver'][1]
        size = int(jt['screw'].split()[0][1:])
        key = re.sub(r'_\d$', '', part.replace('leg.left_', '').replace('leg.right_', ''))
        key = re.sub(r'_[lr]$', '', key)
        key = re.sub(r'^(d435_cradle)_(front|rear)$', r'\1', key)
        if key == 'post':
            key = 'post_m5' if size == 5 else 'post_m3'
        if key == 'bay_rail':
            key = 'bay_rail_door' if 'thumb' in jt['screw'] else 'bay_rail_side'
        if key == 'riser':
            key = 'riser_feet'
        f = fam.setdefault(key, {'joints': [], 'count': 0, 'screws': set(), 'tip': [], 'grip': []})
        f['joints'].append(jt['joint'])
        f['count'] += jt['count']
        f['screws'].add(jt['screw'])
        f['tip'] += jt['engagement_mm']
        f['grip'] += jt['grip_mm']
    for f in fam.values():
        f['screws'] = sorted(f['screws'])
        f['tip_max'] = max(f['tip'])
        f['tip_min'] = min(f['tip'])
    return fam


def build(repo):
    ins = inserts(repo)
    mat = materials(repo)
    fast = repo.json('cad/interfaces.json')['fasteners']
    J = []

    def add(**kw):
        J.append(kw)

    # ------------------------------------------------------------------ loads used more than once
    LL = repo.json('exports/body/leg-loads.json')
    rare_m, rare_s = LL['rare_body']
    fault_m, fault_s = LL['fault_body']
    sc = LL['scenarios']
    turret_hc = repo.json('exports/turret/fea/summary.json')['hand_checks']
    hub = repo.json('exports/leg/fea/summary.json')['joints']
    mount = repo.json('exports/turret/mount.json')

    # ================================================================== LEG (two legs on the robot)
    fm_depth = repo.num('cad/fivebar.py', r"'thread': 'M5', 'pilot_depth': ([\d.]+), 'boss_r'")
    fm_boss_r = repo.num('cad/fivebar.py', r"'pilot_depth': [\d.]+, 'boss_r': ([\d.]+), 'boss_len'")
    flange_t = repo.num('cad/fivebar.py', r'^FLANGE_T, FLANGE_X = ([\d.]+), ')
    row_dz = 140.0   # the two rows of three at z = +-70 (frame_mounts(): ring 62 + 1.5 + FLANGE_T / 2)
    repo.num('cad/fivebar.py', r"\(zf \+ FLANGE_T / 2 \+ (1\.5)\)\) for s in \(1, -1\)")
    b4_torque = repo.num('cad/rig_assembly.py', r"'\| Plate to hip frame \(M5 x 16 into heat-set inserts\) \| the B4 torque \(([\d.]+) N m until B4\) \|'")
    integ = body_families(repo)
    hf = integ.pop('hip_frame')

    def frame_tension(M, Fg):
        return 1000.0 * M / (3 * row_dz) + 0.10 * Fg / 6

    rare_t = frame_tension(rare_m, sc[rare_s]['body']['with_ground_n'])
    fault_t = frame_tension(fault_m, sc[fault_s]['body']['with_ground_n'])
    add(id='leg.hip_frame_mount', assembly='leg', where='hip frame flange ends (PA6-CF), the body cheek / rig plate',
        qty_robot=hf['count'], insert='insert_m5', d_mm=5, material='pa6-cf', infill='100 %',
        hole={'d': fast['M5']['insert_pilot'], 'depth': fm_depth}, boss_mm=2 * fm_boss_r, material_mm=None,
        axis='print-z', orientation='frame printed web-down: the insert axis (y) is the build direction',
        screw=f"body: {', '.join(hf['screws'])} from the cheek side; rig: M5 x 16 + washer through the 6.35 plate",
        screw_side='open end: the screw pulls the insert out of its pilot under load', mating_hole_mm=fast['M5']['clear'],
        tip_depth_mm=hf['tip_max'],
        clamp={'stack': '4.75 mm aluminium cheek (body) / 6.35 mm 6061 plate (rig) only', 'printed_mm': 0, 'limiter': 'n/a'},
        torque_nm=b4_torque, torque_source='docs/leg-rig-assembly.md (cad/rig_assembly.py): "the B4 torque (1.5 N m until B4)"',
        preload_n=r(preload(b4_torque, 5), 0),
        loads=[{'case': f"rare ({rare_s}): {rare_m:g} N m roll on the 140 mm row pair + 10 % side grip", 'per_insert_n': r(rare_t, 0),
                'tension': True, 'source': 'exports/body/leg-loads.json rare_body; cad/body_studies.py rare_leg_load()'},
               {'case': f"fault ({fault_s}): {fault_m:g} N m roll + 10 % side grip", 'per_insert_n': r(fault_t, 0), 'tension': True,
                'source': 'exports/body/leg-loads.json fault_body'}],
        pullout_repo_n=turret_hc['tm_bolts']['m5_insert_pullout_n_est'],
        notes='The leg hangs on these six inserts. Row tension = M / (3 x 140 mm), a rigid-flange screen. The flange is '
              f'{flange_t:g} mm thick at the top row, so the Ø14 boss is the wall. Body joints: ' + ', '.join(hf['joints']) + '.')

    hub_cb = (repo.num('cad/fivebar.py', r'^HUB_HEAD_CB = \(([\d.]+), [\d.]+\)'),
              repo.num('cad/fivebar.py', r'^HUB_HEAD_CB = \([\d.]+, ([\d.]+)\)'))
    upper_t = repo.num('cad/fivebar.py', r"'upper_t': ([\d.]+), 'upper_w0'")
    hub_pre = repo.num('cad/leg_studies.py', r'^HUB_PRELOAD_N = ([\d.]+)')
    up_torque = repo.num('cad/rig_assembly.py', r"'\| Upper link to adapter \(M5 x 40 into tapped 6061, heads on the printed link\) \| the B4 torque \(([\d.]+) N m until B4\) \|'")
    hr, h3 = hub['R1']['hub_rear'], hub['R3']['hub_rear']
    add(id='leg.upper_link_hub', assembly='leg', where="upper link hub (PA6-CF, 30 mm) onto the CNC 6061 output adapter",
        qty_robot=32, insert=None, d_mm=5, material='pa6-cf', infill='100 %', receiver='tapped 6061 (D46), 16 mm thread',
        screw='M5 x 40 ISO 4762, 8 per upper link, heads in Ø10 x 5.5 counterbores, no washer',
        screw_side='n/a (tapped metal)', axis='print-z', orientation='link printed flat: the screw axis is the build direction',
        clamp={'stack': f"{upper_t - hub_cb[1]:g} mm printed PA6-CF between the head and the adapter",
               'printed_mm': upper_t - hub_cb[1], 'limiter': None, 'material': 'PA6-CF', 'bearing': 'Ø8.5 socket head',
               'bearing_od_mm': HEAD_D[('socket', 5)], 'bearing_id_mm': fast['M5']['clear']},
        torque_nm=up_torque, torque_source='docs/leg-rig-assembly.md: "the B4 torque (1.5 N m until B4)"',
        preload_n=r(preload(up_torque, 5), 0),
        loads=[{'case': f"R1 out-of-plane {hr['out_of_plane_nm']:g} N m vs the edge lifting at {hr['edge_lifts_at_nm']:g} "
                        f"(tips at {hr['tips_at_nm']:g})", 'per_insert_n': None,
                'source': 'exports/leg/fea/summary.json joints.R1.hub_rear'},
               {'case': f"R3 out-of-plane {h3['out_of_plane_nm']:g} N m (sf_tip {h3['sf_tip']:g})", 'per_insert_n': None,
                'source': 'exports/leg/fea/summary.json joints.R3.hub_rear'}],
        notes=f"cad/leg_studies.py assumes {hub_pre:g} N per screw; K = 0.2 at {up_torque:g} N m gives "
              f"{preload(up_torque, 5):.0f} N. Both open the hub's edge in R1 and R3 (the FEA summary), and the head's "
              "bearing on the plastic is over the creep screen: the joint needs more clamp than the plastic can hold.",
        extra=[('hub-edge-lifts', 'owner', f"at the assumed {hub_pre:g} N the hub's edge lifts at {hr['edge_lifts_at_nm']:g} N m; "
                f"R1 puts {hr['out_of_plane_nm']:g} and R3 {h3['out_of_plane_nm']:g} N m on it")])

    lug_cb = repo.num('cad/fivebar.py', r'^LUG_CB = ([\d.]+)')
    frame_t = 24.1
    repo.has('cad/fivebar.py', '# 24.1 mm frame - 8.5 mm counterbore = 15.6 mm nominal grip;')
    lug_r = 53.0   # research/rs04-lug-stacks/README.md: the factory recesses at r 57.6 sit 4.6 mm outboard of the M4 axes
    peak_motor = max(v['peak_motor_nm'] for v in sc.values())
    shear = 1000.0 * peak_motor / (10 * lug_r)
    add(id='leg.hip_frame_lugs', assembly='leg', where='hip frame web (PA6-CF, 24.1 mm) onto each RS-04 case',
        qty_robot=40, insert=None, d_mm=4, material='pa6-cf', infill='100 %', receiver='RS-04 case, 5 mm guaranteed thread',
        screw='M4 x 20 ISO 4762 12.9, 10 per motor, heads in Ø8.55 x 8.5 counterbores, no washer',
        screw_side='n/a (motor thread)', axis='print-z', orientation='frame printed web-down: the screw axis is the build direction',
        clamp={'stack': f"{frame_t - lug_cb:.1f} mm printed PA6-CF", 'printed_mm': round(frame_t - lug_cb, 1), 'limiter': None,
               'material': 'PA6-CF', 'bearing': 'Ø7 socket head', 'bearing_od_mm': HEAD_D[('socket', 4)],
               'bearing_id_mm': fast['M4']['clear']},
        torque_nm=None, torque_source='not established (docs/leg-rig-assembly.md; issue #116)', preload_n=None,
        loads=[{'case': f"peak motor torque {peak_motor:g} N m on 10 lugs at r {lug_r:g} mm", 'per_insert_n': r(shear, 0),
                'shear': True, 'source': 'exports/body/leg-loads.json scenarios peak_motor_nm'}],
        notes=f"No torque is set (issue #116). The plastic under the head sets it: {mat['bearing_sustained_mpa']:g} MPa on "
              f"{annulus(7.0, fast['M4']['clear']):.1f} mm2 is {mat['bearing_sustained_mpa'] * annulus(7.0, fast['M4']['clear']):.0f} N. "
              f"At that preload friction (mu 0.15) carries {0.15 * mat['bearing_sustained_mpa'] * annulus(7.0, fast['M4']['clear']):.0f} N "
              f"a lug against {shear:.0f} N of shear at peak torque, so the lugs slip into bearing on their shanks.",
        extra=[('lug-preload-plastic-limited', 'owner', f"{frame_t - lug_cb:.1f} mm of PA6-CF under each Ø7 head with no limiter: "
                f"{mat['bearing_sustained_mpa']:g} MPa allows {mat['bearing_sustained_mpa'] * annulus(7.0, fast['M4']['clear']):.0f} N "
                f"({torque_for(mat['bearing_sustained_mpa'] * annulus(7.0, fast['M4']['clear']), 4):.2f} N m), and friction then "
                f"carries {0.15 * mat['bearing_sustained_mpa'] * annulus(7.0, fast['M4']['clear']):.0f} of the {shear:.0f} N per lug")])

    sleeve = (repo.num('cad/fivebar.py', r'^EYE_SLEEVE = \(([\d.]+), [\d.]+, [\d.]+\)'),
              repo.num('cad/fivebar.py', r'^EYE_SLEEVE = \([\d.]+, ([\d.]+), [\d.]+\)'),
              repo.num('cad/fivebar.py', r'^EYE_SLEEVE = \([\d.]+, [\d.]+, ([\d.]+)\)'))
    knee_t = repo.num('cad/rig_assembly.py', r"'\| Knee nut \(M10 nyloc onto the steel sleeves\) \| ([\d.]+) N m \|'")
    knee_pre = preload(knee_t, 10)
    ring = annulus(20.0, sleeve[0])
    add(id='leg.knee_eye_sleeves', assembly='leg', where="upper link knee eye: two DIN 179 18 x 12 x 20 steel sleeves (pressed)",
        qty_robot=4, insert=None, d_mm=10, material='pa6-cf', infill='100 %', receiver='M10 nyloc on the inner sleeve',
        screw='ISO 7379 Ø12 shoulder screw, M10 nyloc', screw_side='n/a', axis='print-z',
        clamp={'stack': 'washer DIN 433 (Ø20) | sleeves 2 x 20 | nut: all steel if the outer sleeve is flush or proud',
               'printed_mm': 0, 'limiter': 'the sleeves (40 mm)'},
        torque_nm=knee_t, torque_source='docs/leg-rig-assembly.md: knee nut 20 N m (steel on steel)',
        preload_n=r(knee_pre, 0), loads=[],
        notes=f"A working limiter only while the sleeve's end is not below the printed face: the Ø20 washer overhangs the Ø18 "
              f"sleeve by 1 mm, so a recessed sleeve puts {knee_pre:.0f} N on {ring:.0f} mm2 of PA6-CF "
              f"({knee_pre / ring:.0f} MPa).",
        extra=[('limiter-flush', 'check', f"press the outer sleeve 0.1-0.2 mm proud of the link's outer face (or relieve the face "
                f"to Ø21 x 0.3) and check it before torquing: recessed, the {knee_t:g} N m nut crushes the face at "
                f"{knee_pre / ring:.0f} MPa")])

    add(id='leg.knee_spacer', assembly='leg', where='lower link knee boss: the 6061 tube between the two bearings\' inner races',
        qty_robot=4, insert=None, d_mm=10, material='pa6-cf', infill='100 %', receiver='the knee pin stack',
        screw='the same knee pin and nut', screw_side='n/a', axis='print-z',
        clamp={'stack': 'washer | 6301 inner | knee_spacer (5/8 in 6061 tube) | 6301 inner | washer', 'printed_mm': 0,
               'limiter': 'knee_spacer'},
        torque_nm=knee_t, torque_source='as the knee nut', preload_n=r(knee_pre, 0), loads=[],
        notes=f"The spacer must be at least the printed web gap between the two bearing seats; short, the {knee_pre:.0f} N clamp "
              "goes through the balls into the outer races and the printed seats. catalog/hardware.json knee_spacer also records "
              "issue #29 (the Ø15.9 tube is under the 6301's 17.6 mm minimum abutment).",
        extra=[('spacer-length', 'check', 'cut each spacer to the measured web gap (+0 / +0.05 mm) and check the bearings turn '
                'freely after torquing')])

    wheel_t = repo.num('cad/fivebar.py', r"'wheel_t': ([\d.]+), 'wheel_w0'")
    play = repo.num('cad/fivebar.py', r'^WHEEL_RECESS_PLAY = ([\d.]+)')
    wt = repo.num('cad/rig_assembly.py', r"'\| Wheel \(M6 x 30 into the BotWheel\) \| ([\d.]+) N m, threadlocker \|'")
    bw = repo.json('catalog/interfaces.json')['odrive-botwheel']
    pcd, wheel_d = bw['case']['bolts']['pcd'], bw['envelope']['outer_diameter']
    y_flange, y_tyre = 80.0, 104.8   # wheel link outer face; tyre mid-plane (fivebar Y['wheel_link'][1], Y['wheel'])
    yb = pcd / 2 * math.sin(math.radians(45))

    def wheel_bolt(name):
        s = sc[name]
        M = s['peak_axle_force_n'] * (y_tyre - y_flange) / 1000.0 + 0.10 * s['peak_wheel_force_n'] * wheel_d / 2000.0
        return M, 1000.0 * M * yb / (4 * yb ** 2)

    m_rare, t_rare = wheel_bolt(rare_s)
    m_fault, t_fault = wheel_bolt(fault_s)
    w_area = annulus(HEAD_D[('socket', 6)], fast['M6']['clear'])
    add(id='leg.wheel_botwheel', assembly='leg', where="wheel link foot (PA6-CF) onto the BotWheel's stator flange",
        qty_robot=8, insert=None, d_mm=6, material='pa6-cf', infill='100 %', receiver='BotWheel M6 (depth not published)',
        screw='M6 x 30 ISO 4762 from inside the hub, no washer', screw_side='n/a', axis='print-z',
        orientation='wheel link printed flat on its outer face: the screw axis is the build direction',
        clamp={'stack': f"{wheel_t:g} mm printed PA6-CF foot (head on the hub's floor to the flange on the outer face)",
               'printed_mm': wheel_t, 'limiter': None, 'material': 'PA6-CF', 'bearing': 'Ø10 socket head',
               'bearing_od_mm': HEAD_D[('socket', 6)], 'bearing_id_mm': fast['M6']['clear'], 'level': 'owner'},
        torque_nm=wt, torque_source='docs/leg-rig-assembly.md: "8 N m, threadlocker" (no source given)',
        preload_n=r(preload(wt, 6), 0),
        loads=[{'case': f"rare ({rare_s}): axle {sc[rare_s]['peak_axle_force_n']:g} N at {y_tyre - y_flange:.1f} mm + 10 % grip at the "
                        f"tyre: {m_rare:.0f} N m on 4 x M6 at PCD {pcd:g}", 'per_insert_n': r(t_rare, 0), 'tension': True,
                'source': 'exports/body/leg-loads.json'},
               {'case': f"fault ({fault_s}): {m_fault:.0f} N m", 'per_insert_n': r(t_fault, 0), 'tension': True,
                'source': 'exports/body/leg-loads.json'}],
        notes=f"Keeping the flange closed needs about {max(t_rare, t_fault):.0f} N a screw; the plastic under a bare Ø10 head holds "
              f"{mat['bearing_sustained_mpa'] * w_area:.0f} N at {mat['bearing_sustained_mpa']:g} MPa. No torque satisfies both "
              "without a spreader or limiter. A DIN 9021 washer (catalog/hardware.json lists 8 for these screws) does not fit: "
              f"on PCD {pcd:g} its Ø18 reaches r {pcd / 2 + 9:g}, past the hub's Ø48 bore.",
        extra=[('wheel-clamp', 'owner', f"{wt:g} N m ~ {preload(wt, 6):.0f} N on {w_area:.0f} mm2 = {preload(wt, 6) / w_area:.0f} MPa "
                f"on PA6-CF; the flange needs >= {max(t_rare, t_fault):.0f} N a screw, the plastic holds "
                f"{mat['bearing_sustained_mpa'] * w_area:.0f} N"),
               ('note-vs-joint', 'fix', f"cad/fivebar.py wheel_link() docstring: {q(repo.has('cad/fivebar.py', 'its 4 x M6 x 40'))}; "
                'the joint and BOM are M6 x 30, and catalog/hardware.json screw_m6x40 still lists this joint')])

    add(id='leg.stop_posts', assembly='leg', where='hip frame stop posts', qty_robot=8, insert=None, d_mm=8, material='pa6-cf',
        infill='100 %', receiver='none: Ø16 steel pins in blind holes since D53', screw='none', axis='print-z',
        clamp=None, loads=[], notes='No insert any more. The generated assembly page still instructs one.',
        extra=[('note-vs-joint', 'fix', 'cad/rig_assembly.py (docs/leg-rig-assembly.md) still says '
                f"{q(repo.has('cad/rig_assembly.py', 'the B4 torque into the M8 insert, 5 N m until B4'))} and "
                f"{q(repo.has('cad/rig_assembly.py', 'Stop posts (M8 into heat-set inserts)'))}: the posts are pins (D53)")])

    # ================================================================== BODY (P3)
    f = integ.pop('post_m5')
    post_w = repo.num('cad/body_params.py', r'^POST_W = ([\d.]+)')
    post_depth = repo.num('cad/body_frame.py', r"s = s\.cut\(cyl_z\(3\.2, -1\.0, ([\d.]+)\)\)\.cut\(cyl_z\(3\.2, h - 11\.0, h \+ 1\.0\)\)")
    post_n = repo.num('cad/body_frame.py', r'it carries (\d+) N at')
    add(id='body.post_m5', assembly='body', where='deck posts (PA6-CF 22 x 22, standing), both ends', qty_robot=f['count'],
        insert='insert_m5', d_mm=5, material='pa6-cf', infill='100 %', hole={'d': fast['M5']['insert_pilot'], 'depth': post_depth},
        boss_mm=post_w, axis='print-z', orientation='printed standing: the insert axis is the build direction',
        screw=', '.join(f['screws']) + ' through the tray (3.17) and the deck (2.54)', screw_side='open end (foot: from below)',
        mating_hole_mm=fast['M5']['clear'], tip_depth_mm=f['tip_max'],
        clamp={'stack': 'aluminium tray / deck only', 'printed_mm': 0, 'limiter': 'n/a'},
        torque_nm=b4_torque, preload_n=r(preload(b4_torque, 5), 0), torque_source='the M5-insert B4 torque (assumed)',
        loads=[{'case': "the landing's 8.65 g on a post (cad/body_frame.py post())", 'per_insert_n': post_n, 'tension': True,
                'source': 'cad/body_frame.py post() docstring'}],
        pullout_repo_n=turret_hc['tm_bolts']['m5_insert_pullout_n_est'], notes='Body joints: ' + ', '.join(f['joints']) + '.')

    f = integ.pop('post_m3')
    m3p = repo.num('cad/body_frame.py', r'^POST_M3_PILOT = ([\d.]+)')
    add(id='body.post_m3', assembly='body', where="deck posts' side and face bosses (9 x 9) for the P3 shell", qty_robot=f['count'],
        insert='insert_m3', d_mm=3, material='pa6-cf', infill='100 %',
        hole={'d': fast['M3']['insert_pilot'], 'depth': m3p, 'through': True},
        boss_mm=2 * repo.num('cad/body_frame.py', r'core = core\.cut\(box\(-([\d.]+), 4\.5, \*sorted\(\(sy \* w / 2'), axis='layer-plane',
        orientation='post printed standing: these inserts are horizontal', screw=', '.join(f['screws']) + ' through the PETG shell',
        screw_side='open end', mating_hole_mm=fast['M3']['clear'], tip_depth_mm=f['tip_max'],
        clamp={'stack': 'PETG shell boss (9.4 mm) under a pan head', 'printed_mm': 9.4, 'limiter': None, 'material': 'PETG',
               'bearing': 'Ø5.6 pan head', 'bearing_od_mm': HEAD_D[('pan', 3)], 'bearing_id_mm': fast['M3']['clear']},
        loads=[{'case': 'a shell panel (light)', 'per_insert_n': 20, 'tension': True, 'source': 'estimate'}],
        notes='The pilot runs 0.5 mm past the 7.5 mm boss into the post\'s hollow, so it is open at the bottom. Light duty. '
              'Body joints: ' + ', '.join(f['joints']) + '.')

    f = integ.pop('plate_post')
    pp_w = repo.num('cad/body_frame.py', r'^PLATE_POST_W = ([\d.]+)')
    add(id='body.plate_post', assembly='body', where='power plate posts (PA6-CF 16 x 16, standing), both ends', qty_robot=f['count'],
        insert='insert_m5', d_mm=5, material='pa6-cf', infill='100 %', hole={'d': fast['M5']['insert_pilot'], 'depth': repo.num('cad/body_frame.py', r'return s\.cut\(cyl_z\(3\.2, -1\.0, ([\d.]+)\)\)\.cut\(cyl_z\(3\.2, h - 11\.0')},
        boss_mm=pp_w, axis='print-z', orientation='printed standing', screw=', '.join(f['screws']), screw_side='open end',
        mating_hole_mm=fast['M5']['clear'], tip_depth_mm=f['tip_min'],
        clamp={'stack': 'aluminium tray / power plate only', 'printed_mm': 0, 'limiter': 'n/a'},
        loads=[{'case': 'the power plate and its electronics (est. 1.5 kg) at 10 g over 4 posts', 'per_insert_n': 37,
                'tension': True, 'source': 'estimate'}],
        notes='The foot screws (M5 x 10 through 3.17) use the shortest engagement in the body. Body joints: '
              + ', '.join(f['joints']) + '.')

    f = integ.pop('riser_feet')
    rfp = repo.num('cad/body_frame.py', r'^RISER_FOOT_PILOT = ([\d.]+)')
    add(id='body.riser_feet', assembly='body', where="turret riser's four feet (PA6-CF, printed on its top face)",
        qty_robot=f['count'], insert='insert_m5', d_mm=5, material='pa6-cf', infill='100 %',
        hole={'d': 2 * repo.num('cad/body_frame.py', r's = s\.cut\(cyl_z\(([\d.]+), -1\.0, RISER_FOOT_PILOT, x, y\)\)'), 'depth': rfp},
        boss_mm=2 * repo.num('cad/body_frame.py', r'^RISER_LEG_R = ([\d.]+)'), axis='print-z',
        orientation='printed on its top face: insert axes along the build direction', screw=', '.join(f['screws']) + ' from below',
        screw_side='open end (from below)', mating_hole_mm=fast['M5']['clear'], tip_depth_mm=f['tip_max'],
        clamp={'stack': 'turret plate + deck (aluminium)', 'printed_mm': 0, 'limiter': 'n/a'},
        loads=[{'case': "the turret's 30 g sideways TM moment, carried down the riser's legs",
                'per_insert_n': turret_hc['tm_bolts']['tension_per_bolt_n'], 'tension': True,
                'source': 'exports/turret/fea/summary.json hand_checks.tm_bolts'}],
        pullout_repo_n=turret_hc['tm_bolts']['m5_insert_pullout_n_est'], notes='Body joints: ' + ', '.join(f['joints']) + '.')

    riser_top = repo.num('cad/body_frame.py', r's = s\.cut\(cyl_z\(3\.2, H - ([\d.]+), H \+ 1\.0, x, y\)\)\s+# M5 insert from the top')
    riser_dowel = repo.num('cad/body_frame.py', r's = s\.cut\(cyl_z\(2\.5 - 0\.03, H - ([\d.]+), H \+ 1\.0, x, y\)\)')
    plinth_t = repo.num('cad/turret.py', r"^PLINTH = \{'h': [\d.]+, 'r': [\d.]+, 'wall': [\d.]+, 'tray_t': ([\d.]+),")
    plinth_cb = repo.num('cad/turret.py', r"'cbore': \([\d.]+, ([\d.]+)\)")
    tm_len = float(mount['tm']['bolt_screw'].split('x')[1].split(',')[0])
    tip_tray = tm_len - (plinth_t - plinth_cb)
    pin_l = float(mount['tm']['dowel_pin'].split('x')[1].split(',')[0])
    tray_dowel = repo.num('cad/turret.py', r's = s\.cut\(through_z\(x, y, 5\.0, z0 - 1, z0 \+ ([\d.]+)\)\)')
    add(id='body.riser_top_tm', assembly='body / turret', where="turret riser's top ring: the TM face's 4 M5 inserts",
        qty_robot=4, insert='insert_m5', d_mm=5, material='pa6-cf', infill='100 %',
        hole={'d': fast['M5']['insert_pilot'], 'depth': riser_top}, boss_mm=None, axis='print-z',
        orientation='riser printed on its top face', screw=f"{mount['tm']['bolt_screw']} down through the compute plinth's "
        f"{plinth_t:g} mm tray (Ø9.5 x {plinth_cb:g} counterbores, D66)", screw_side='open end (from above)',
        mating_hole_mm=fast['M5']['clear'], tip_depth_mm=tip_tray,
        clamp={'stack': f"{plinth_t - plinth_cb:g} mm printed PA6-CF tray under each head (40 % gyroid per docs/turret-sections.md)",
               'printed_mm': plinth_t - plinth_cb, 'limiter': None, 'material': 'PA6-CF', 'bearing': 'Ø8.5 socket head',
               'bearing_od_mm': HEAD_D[('socket', 5)], 'bearing_id_mm': fast['M5']['clear']},
        loads=[{'case': 'R: 30 g sideways on the whole turret', 'per_insert_n': turret_hc['tm_bolts']['tension_per_bolt_n'],
                'tension': True, 'source': 'exports/turret/fea/summary.json hand_checks.tm_bolts'}],
        pullout_repo_n=turret_hc['tm_bolts']['m5_insert_pullout_n_est'],
        notes=f"exports/turret/mount.json (the turret's contract with the robot) asks the head for "
              f"{mount['riser']['bolt_hole_depth_min_mm']:g} mm bolt holes; the riser cuts {riser_top:g}. Its dowel holes are "
              f"{riser_dowel:g} deep against the contract's {mount['riser']['dowel_holes'].split('at least ')[1].split(' mm')[0]} mm.",
        extra=[('contract-depth', 'fix', f"riser TM pilots {riser_top:g} deep vs mount.json bolt_hole_depth_min_mm "
                f"{mount['riser']['bolt_hole_depth_min_mm']:g} (and {tip_tray:g} with the D66 tray): deepen to >= {tip_tray + 1.5:g}, "
                f"or use M5 x 12 (tip {12 - (plinth_t - plinth_cb):g}, 1.5 d engaged)"),
               ('contract-dowel', 'fix', f"a {pin_l:g} mm TM dowel goes {tray_dowel:g} into the D66 tray, so it needs "
                f"{pin_l - tray_dowel + 0.5:g} mm in the riser, which cuts {riser_dowel:g} (mount.json, written for the 4 mm "
                f"pan-base holes, asks {mount['riser']['dowel_holes'].split('at least ')[1].split(' mm')[0]})")])

    f = integ.pop('dcdc_bracket')
    dwt = repo.num('cad/body_frame.py', r'^DCDC_FOOT_T, DCDC_WALL_T = [\d.]+, ([\d.]+)')
    add(id='body.dcdc_bracket', assembly='body', where="DC-DC bracket's upright (PA6-CF): the converter's four M3",
        qty_robot=f['count'], insert='insert_m3', d_mm=3, material='pa6-cf', infill='100 %',
        hole={'d': fast['M3']['insert_pilot'], 'depth': dwt, 'through': True}, material_mm=dwt, boss_mm=None,
        axis='layer-plane', orientation='printed upright: these inserts are horizontal', screw=', '.join(f['screws']),
        screw_side='open end', mating_hole_mm=fast['M3']['clear'], tip_depth_mm=f['tip_max'],
        clamp={'stack': "the converter's flange", 'printed_mm': 0, 'limiter': 'n/a'},
        loads=[{'case': 'the converter (est. 0.3 kg) at 10 g on 4', 'per_insert_n': 7, 'tension': False, 'source': 'estimate'}],
        notes='Body joints: ' + ', '.join(f['joints']) + '.',
        extra=[('note-vs-joint', 'fix', 'part note ' + q(repo.has('cad/body_frame.py', "two M4 x 10 down into the tray\\'s nuts; the converter on four M3 x 8"))
                + ' vs the joints: 2 x M4 x 12 into the power plate\'s PEM nuts, 4 x M3 x 6 (exports/body/integrity.json)')])

    f = integ.pop('bus_insulator')
    add(id='body.bus_insulator', assembly='body', where='bus bar insulators (PETG): bars from above, plate from below',
        qty_robot=f['count'], insert='insert_m3', d_mm=3, material='petg', infill='print plan: 2 mm walls, 40 % gyroid',
        hole={'d': fast['M3']['insert_pilot'], 'depth': repo.num('cad/body_frame.py', r's = s\.cut\(cyl_z\(2\.0, H - ([\d.]+), H \+ 0\.1, u, BUS_W / 2\)\)')},
        boss_mm=repo.num('cad/body_frame.py', r'^BUS_L, BUS_W = [\d.]+, ([\d.]+)'), axis='print-z', orientation='printed flat',
        screw=', '.join(f['screws']), screw_side='open end',
        mating_hole_mm=fast['M3']['clear'], tip_depth_mm=f['tip_max'],
        clamp={'stack': 'copper bar / aluminium plate', 'printed_mm': 0, 'limiter': 'n/a'},
        loads=[{'case': 'bus bar and lugs (light)', 'per_insert_n': 15, 'tension': True, 'source': 'estimate'}],
        notes='Body joints: ' + ', '.join(f['joints']) + '.',
        extra=[('note-vs-plan', 'fix', 'part note says ' + q(repo.has('cad/body_frame.py', "note='PETG, 100 % (never a carbon-filled filament")[6:]) +
                '; exports/body/print-plan.json prints it "2 mm walls, 40 % gyroid"')])

    f = integ.pop('bay_rail_side')
    rail_w = repo.num('cad/body_battery.py', r'^RAIL_W, RAIL_H = ([\d.]+), [\d.]+')
    rail_h = repo.num('cad/body_battery.py', r'^RAIL_W, RAIL_H = [\d.]+, ([\d.]+)')
    side_d = repo.num('cad/body_battery.py', r"r = r\.cut\(_cyl_y\(2\.0, \*sorted\(\(yo, yo - sy \* ([\d.]+)\)\), x, zc\)\)")
    add(id='body.bay_rail_side', assembly='body', where="battery bay rails (PA6-CF 8 x 10): the side plates' top row",
        qty_robot=f['count'], insert='insert_m3', d_mm=3, material='pa6-cf', infill='100 %',
        hole={'d': fast['M3']['insert_pilot'], 'depth': side_d}, material_mm=rail_w, boss_mm=rail_h, axis='layer-plane',
        orientation='rail printed flat: side inserts horizontal', screw=', '.join(f['screws']) + ' through the 1.6 side plate',
        screw_side='open end (shear duty)', mating_hole_mm=3.4, tip_depth_mm=f['tip_max'],
        clamp={'stack': 'aluminium side plate', 'printed_mm': 0, 'limiter': 'n/a'},
        loads=[{'case': 'the bay and two packs (est. 3.5 kg) at 10 g on 10, in shear', 'per_insert_n': 34, 'shear': True,
                'source': 'estimate'}], notes='Body joints: ' + ', '.join(f['joints']) + '.')

    f = integ.pop('bay_rail_door')
    end_d = repo.num('cad/body_battery.py', r"r = r\.cut\(_cyl_x\(2\.0, \*sorted\(\(xe, xe \+ d \* ([\d.]+)\)\), yc, zc\)\)")
    add(id='body.bay_rail_door', assembly='body', where="battery bay rails' ends: the doors' thumbscrews",
        qty_robot=f['count'], insert='insert_m3', d_mm=3, material='pa6-cf', infill='100 %',
        hole={'d': fast['M3']['insert_pilot'], 'depth': end_d}, boss_mm=rail_w, axis='layer-plane',
        orientation='rail printed flat: end inserts horizontal', screw=', '.join(f['screws']) + ' through the PETG door',
        screw_side='open end: a pack pushing the door pulls the insert', mating_hole_mm=3.4, tip_depth_mm=f['tip_max'],
        clamp={'stack': '4 mm PETG door under a thumb head (hand tight)', 'printed_mm': 4.0, 'limiter': None},
        loads=[{'case': 'a pack (est. 1.5 kg) at 10 g on a door\'s 2 screws', 'per_insert_n': 74, 'tension': True,
                'source': 'estimate'}],
        notes='Body joints: ' + ', '.join(f['joints']) + '.',
        extra=[('note-vs-joint', 'fix', "bay_rail part note " + q(repo.has('cad/body_battery.py', "four M4 x 16 up into the belly\\'s nuts")) +
                " vs the joint M4 x 20 (bay_rail_l/r); adapter plates " +
                q(repo.has('cad/body_battery.py', "four M4 x 8 up into the belly\\'s nuts")) + " vs M4 x 12")])

    f = integ.pop('d435_cradle')
    add(id='body.d435_cradle', assembly='body', where="D435 cradles' feet (PA6-CF 8 x 8), from the shell apron",
        qty_robot=f['count'], insert='insert_m3', d_mm=3, material='pa6-cf', infill='100 %',
        hole={'d': repo.num('cad/body_shell.py', r'plate = plate\.cut\(_hole_x\(y, z, ([\d.]+), \*sorted\(\(sx \* XI, sx \* \(XI - 7\.5\)\)\)\)\)'),
              'depth': repo.num('cad/body_shell.py', r'plate = plate\.cut\(_hole_x\(y, z, 4\.0, \*sorted\(\(sx \* XI, sx \* \(XI - ([\d.]+)\)\)\)\)\)')},
        boss_mm=2 * repo.num('cad/body_shell.py', r'plate = plate\.union\(box\(fa, fb, y - ([\d.]+), y \+ 4, z0 - 2, z0 \+ 6\)\)'),
        axis='layer-plane', orientation='cradle printed flat: the feet inserts horizontal',
        screw=', '.join(f['screws']), screw_side='open end', mating_hole_mm=3.4, tip_depth_mm=f['tip_max'],
        clamp={'stack': 'the 2 mm PETG apron', 'printed_mm': 2.0, 'limiter': None},
        loads=[{'case': 'a D435 (72 g) at 30 g on 2', 'per_insert_n': 11, 'tension': True, 'source': 'estimate'}],
        notes='Body joints: ' + ', '.join(f['joints']) + '.')

    f = integ.pop('shell_front')
    eyes_t = repo.num('cad/body_shell.py', r"^EYES = \{.*'board': \([\d.]+, [\d.]+, ([\d.]+)\)\}")
    add(id='body.eyes_clip', assembly='body', where="shell front's two bosses (PETG Ø8) for the eyes' clip", qty_robot=f['count'],
        insert='insert_m3', d_mm=3, material='petg', infill='2 mm walls, 40 % gyroid',
        hole={'d': fast['M3']['insert_pilot'], 'depth': repo.num('cad/body_shell.py', r"\.center\(y, z\)\.circle\(2\.0\)\.extrude\(([\d.]+)\)\)")},
        material_mm=eyes_t, boss_mm=2 * repo.num('cad/body_shell.py', r"\.center\(y, z\)\.circle\(([\d.]+)\)\.extrude\(EYES\['board'\]\[2\] \+ 0\.01\)\)"),
        axis='print-z', orientation='shell printed on its outer face',
        screw=', '.join(f['screws']), screw_side='open end', mating_hole_mm=3.4, tip_depth_mm=f['tip_max'],
        clamp={'stack': 'the PETG clip', 'printed_mm': 2.0, 'limiter': None},
        loads=[{'case': 'the DualEye board (light)', 'per_insert_n': 5, 'tension': True, 'source': 'estimate'}],
        notes='Body joints: ' + ', '.join(f['joints']) + '.')
    if integ:
        raise Stale(f'new body insert joints not inventoried: {sorted(integ)}')

    # body parts clamped without an insert (printed in the clamp, no limiter)
    printed = set(repo.json('exports/body/print-plan.json')['parts']) | set(repo.json('exports/body/shell/print-plan.json')['parts'])
    pc, seen = {}, set()
    for jt in repo.json('exports/body/integrity.json')['joints']:
        if jt['stage'] != 'P3' or jt['joint'] in seen or jt['receiver'][0] == 'insert':
            continue
        seen.add(jt['joint'])
        if any(m in printed or re.sub(r'_\d$', '', m) in printed for m in jt['stack']):
            pc[jt['joint']] = jt['count']
    add(id='body.printed_clamps', assembly='body', where='printed parts clamped by screws into PEM nuts / nuts / tapped holes',
        qty_robot=sum(pc.values()), joints=sorted(pc), insert=None, d_mm=4, material='pa6-cf', infill='mixed',
        receiver='PEM / nyloc / nut / tapped', screw='see notes', screw_side='n/a', axis='print-z',
        clamp={'stack': 'see notes', 'printed_mm': 0, 'limiter': None}, loads=[],
        notes='isolators (TPU, M4 x 20, snug by design: the foot is the compliance); bay rails (M4 x 20 through 10 mm PA6-CF '
              'into the belly PEMs); adapter plates (M4 x 12 through 4 mm PA6-CF); DC-DC bracket (M4 x 12 through its 4 mm foot); '
              'ear brackets (M5 x 14 through PA6-CF + the 2 mm PETG wall, nyloc inside); shell door / hatch / splices (M3 x 8 '
              'into nuts in PETG); fan duct (M3 x 6 into the tapped turret plate). None has a stated torque or a limiter; each '
              'is snug-only duty. The ear brackets\' nylocs bear on bare 2 mm PETG.',
        extra=[('ear-nyloc-on-petg', 'check', 'put an M5 washer under each ear bracket nyloc on the 2 mm PETG wall and '
                'tighten snug (no torque is stated)'),
               ('note-vs-joint', 'fix', 'body_shell.py part notes ' + q(repo.has('cad/body_shell.py', 'four M3 x 16 into the wall')) +
                ' / two M3 x 16 vs the joints M3 x 8; fan duct ' + q(repo.has('cad/body_shell.py', 'three M3 x 5 up into the turret plate')) +
                ' vs M3 x 6'),
               ('door-side', 'fix', 'cad/body_shell.py ' + q(repo.has('cad/body_shell.py', "DOOR_SIDE = 'l'")) +
                " but door()'s docstring says " + q(repo.has('cad/body_shell.py', "The right side's service door")))])

    # ================================================================== TURRET
    ins_depth = repo.num('cad/turret.py', r'^INSERT_DEPTH = ([\d.]+)')
    ball_d = repo.num('cad/turret.py', r'def __init__\(self, ball_d: float = ([\d.]+),')
    repo.has('cad/turret.py', 'self.bore = ball_d + 1.5')
    foot_t = repo.num('cad/turret.py', r'self\.foot_t = ([\d.]+)')
    col_r = repo.num('cad/turret.py', r"'col_r': ([\d.]+), 'cbore'")
    add(id='turret.plinth_columns', assembly='turret', where="compute plinth shell's four column tops (PETG): the pan base's TM",
        qty_robot=4, insert='insert_m5', d_mm=5, material='petg', infill='not in exports/turret/print/print.json yet',
        hole={'d': fast['M5']['insert_pilot'], 'depth': ins_depth}, boss_mm=2 * col_r, axis='print-z',
        orientation='shell printed upside down', screw=f"{mount['tm']['bolt_screw']} through the pan base's {foot_t:g} mm foot",
        screw_side='open end (from above)', mating_hole_mm=fast['M5']['clear'], tip_depth_mm=tm_len - foot_t,
        clamp={'stack': f"{foot_t:g} mm PA6-CF foot (40 % gyroid) under each head", 'printed_mm': foot_t, 'limiter': None,
               'material': 'PA6-CF', 'bearing': 'Ø8.5 socket head', 'bearing_od_mm': HEAD_D[('socket', 5)],
               'bearing_id_mm': fast['M5']['clear']},
        loads=[{'case': 'R: 30 g sideways on the turret', 'per_insert_n': turret_hc['tm_bolts']['tension_per_bolt_n'],
                'tension': True, 'source': 'exports/turret/fea/summary.json hand_checks.tm_bolts'}],
        notes="The column is solid PETG for 8 mm under the pilot (its hollow starts at z -16), so the deeper pilot fits.",
        extra=[('screw-bottoms-fix', 'fix', f"deepen the column pilots {ins_depth:g} -> {tm_len - foot_t + 1.5:g} (solid to 16), or "
                f"use M5 x 12 (tip {12 - foot_t:g}, {12 - foot_t:g} mm engaged)")])
    add(id='turret.plinth_tray_m4', assembly='turret', where="compute plinth tray (PA6-CF): the shell's four feet",
        qty_robot=4, insert='turret_insert_m4', d_mm=4, material='pa6-cf', infill='40 % gyroid (docs/turret-sections.md)',
        hole={'d': fast['M4']['insert_pilot'], 'depth': ins_depth}, axis='print-z', orientation='tray printed flat',
        screw="M4 x 10 down through the shell's 5 mm PETG foot", screw_side='open end (from above)',
        mating_hole_mm=fast['M4']['clear'], tip_depth_mm=10 - 5.0,
        clamp={'stack': '5 mm PETG foot', 'printed_mm': 5.0, 'limiter': None}, loads=[],
        notes='The shell foot is ' + q(repo.has('cad/turret.py', 'y - 6.0, y + 6.0, zt, zt + 5.0)')) + ' (5 mm).')

    hz = repo.num('cad/turret.py', r"s = s\.cut\(insert_hole\(x, y, hz1, 'M3', ([\d.]+)\)\)")
    clamp_t = repo.num('cad/turret.py', r'^CLAMP_T = ([\d.]+)')
    up = turret_hc['journal_lip']['force_n']
    add(id='turret.pan_base_clamp_ears', assembly='turret', where="pan base housing ears (PA6-CF): the 61810's clamp ring",
        qty_robot=5, insert='insert_m3', d_mm=3, material='pa6-cf', infill='40 % gyroid inside 4 walls',
        hole={'d': fast['M3']['insert_pilot'], 'depth': hz}, axis='print-z', orientation='printed on its foot',
        screw=f"M3 x 8 through the {clamp_t:g} mm 6061 clamp ring", screw_side='open end (from above)',
        mating_hole_mm=fast['M3']['clear'], tip_depth_mm=8 - clamp_t,
        clamp={'stack': 'aluminium ring', 'printed_mm': 0, 'limiter': 'n/a'},
        loads=[{'case': 'R: 30 g with the turret upside down (the pan group on the ring)', 'per_insert_n': r(up / 5, 0),
                'tension': True, 'source': 'exports/turret/fea/summary.json hand_checks.journal_lip'}],
        pullout_repo_n=turret_hc['plate_inserts']['m3_insert_pullout_n_est'],
        notes='The capacity basis is a 100 % solid test; this part is 40 % gyroid inside 4 walls (unqualified).')
    add(id='turret.pan_base_carrier_tabs', assembly='turret', where="pan base tab pockets (from below): the ring carrier",
        qty_robot=3, insert='insert_m3', d_mm=3, material='pa6-cf', infill='40 % gyroid inside 4 walls',
        hole={'d': fast['M3']['insert_pilot'], 'depth': repo.num('cad/turret.py', r"C\['tab_t'\] - 0\.1, C\['tab_t'\] \+ ([\d.]+), x, y\)\)\s+# M3 insert from below")},
        axis='print-z', orientation='printed on its foot', screw="M3 x 10 flat heads up through the carrier's 4 mm tabs",
        screw_side='open end (from below)', mating_hole_mm=fast['M3']['clear'], tip_depth_mm=10 - 4.0,
        clamp={'stack': 'PA6-CF carrier tab, countersunk', 'printed_mm': 4.0, 'limiter': None}, loads=[],
        notes='Light: the carrier and the slip ring hang on it.')
    add(id='turret.base_board_carrier', assembly='turret', where='pan base anchor and the base-board carrier',
        qty_robot=8, insert='insert_m3', d_mm=3, material='pa6-cf', infill='carrier solid; anchor 40 % gyroid',
        hole={'d': repo.num('cad/turret_base_board.py', r'^INSERT_PILOT = ([\d.]+)'),
              'depth': round(repo.num('cad/turret_base_board.py', r's = s\.cut\(cx\(INSERT_PILOT/2,[\d.]+,([\d.]+),y,z\)\)')
                             - repo.num('cad/turret_base_board.py', r's = s\.cut\(cx\(INSERT_PILOT/2,([\d.]+),[\d.]+,y,z\)\)'), 2)}, axis='layer-plane',
        orientation='anchor horizontal, carrier boss vertical', screw='M3 (see research/carrier-insert-fit)', screw_side='open end',
        mating_hole_mm=repo.num('cad/turret_base_board.py', r'^M3_CLEAR = ([\d.]+)'), tip_depth_mm=None,
        clamp=None, loads=[], notes='Covered by research/carrier-insert-fit (fit specimens for both orientations) and the '
                                    'base-board receipts; not re-screened here.')
    add(id='turret.pan_base_dt_pad', assembly='turret', where="pan base wall (PA6-CF): the DT12 receptacle's flange",
        qty_robot=4, insert='turret_insert_m4', d_mm=4, material='pa6-cf', infill='40 % gyroid inside 4 walls',
        hole={'d': fast['M4']['insert_pilot'], 'depth': repo.num('cad/turret.py', r"s = s\.cut\(cyl_y\(FAST\['M4'\]\['insert_pilot'\] / 2, -G\.dt_y - 0\.1, -G\.dt_y \+ ([\d.]+), x, z\)\)")},
        axis='layer-plane', orientation='pan base printed on its foot: these are horizontal', screw="the receptacle's flange screws",
        screw_side='open end', mating_hole_mm=None, tip_depth_mm=None, clamp=None,
        loads=[{'case': 'plug mating / unmating (est. 60 N on 4)', 'per_insert_n': 15, 'tension': True, 'source': 'estimate'}],
        notes='Horizontal in a 40 % gyroid part, light duty.')
    add(id='turret.pan_base_bumper_tabs', assembly='turret', where="pan base's 6 mm bumper tabs: the TPU bumper ring",
        qty_robot=5, insert='turret_insert_m3_short', d_mm=3, material='pa6-cf', infill='40 % gyroid inside 4 walls',
        hole={'d': fast['M3']['insert_pilot'], 'depth': repo.num('cad/turret.py', r"s = s\.cut\(insert_hole\(x, y, G\.bumper_z\[0\], 'M3', ([\d.]+)\)\)")},
        material_mm=6.0, axis='print-z', orientation='printed on its foot', screw='M3 with washers through the TPU ring',
        screw_side='open end', mating_hole_mm=None, tip_depth_mm=None, clamp={'stack': 'TPU ring + washer', 'printed_mm': 0,
        'limiter': None}, loads=[], notes='The TPU is the compliance; snug only.')
    add(id='turret.pan_ring_yoke', assembly='turret', where="pan ring (PA6-CF turntable): the tilt yoke's four M4",
        qty_robot=4, insert='turret_insert_m4', d_mm=4, material='pa6-cf', infill='100 %',
        hole={'d': fast['M4']['insert_pilot'], 'depth': ins_depth}, axis='print-z', orientation='printed upside down',
        screw='M4 x 10, heads 6 mm down in the yoke\'s 12 mm bridge (' + q(repo.has('cad/turret.py', 'the heads sit 6 mm above the bridge')) + ')',
        screw_side='open end (from above)',
        mating_hole_mm=fast['M4']['clear'], tip_depth_mm=10 - 6.0, longer_screw_fits=True,
        clamp={'stack': '6 mm PA6-CF bridge', 'printed_mm': 6.0, 'limiter': None},
        loads=[{'case': 'R: 30 g sideways on the yoke and all it carries', 'per_insert_n': turret_hc['yoke_inserts']['tension_per_insert_n'],
                'tension': True, 'source': 'exports/turret/fea/summary.json hand_checks.yoke_inserts'}],
        pullout_repo_n=turret_hc['yoke_inserts']['m4_insert_pullout_n_est'],
        notes=repo.has('cad/turret.py', 'so an M4 x 10 keeps 4 mm in the turntable\'s insert') +
              f'. An M4 x 12 keeps 6 mm (1.5 d) and stops {ins_depth - 6:g} mm off the pilot floor.')
    add(id='turret.ring_carrier', assembly='turret', where="ring carrier (PA6-CF): the slip ring's flange", qty_robot=3,
        insert='insert_m3', d_mm=3, material='pa6-cf', infill='100 %',
        hole={'d': fast['M3']['insert_pilot'], 'depth': repo.num('cad/turret.py', r"rg\['seat'\] - ([\d.]+), rg\['seat'\] \+ 0\.1, x, y\)\)\s+# flange screws")},
        axis='print-z', orientation='printed on its top face', screw="M3 x 8 + washers through the ring's flange",
        screw_side='open end', mating_hole_mm=None, tip_depth_mm=None, clamp=None, loads=[], notes='Light.')
    add(id='turret.yoke_board_bay', assembly='turret', where="tilt yoke -y arm (PA6-CF): the board bay", qty_robot=4,
        insert='insert_m3', d_mm=3, material='pa6-cf', infill='100 %',
        hole={'d': fast['M3']['insert_pilot'], 'depth': repo.num('cad/turret.py', r"-a1 - 0\.1, -a1 \+ ([\d.]+), x, z\)\)")},
        axis='layer-plane', orientation='yoke printed on its back: the arm inserts lie in the layers',
        screw="M3 x 8 flat heads through the bay's 3 mm back", screw_side='open end', mating_hole_mm=fast['M3']['clear'],
        tip_depth_mm=8 - 3.0, clamp={'stack': '3 mm PETG, countersunk', 'printed_mm': 3.0, 'limiter': None},
        loads=[{'case': 'R: 30 g down on the bay', 'per_insert_n': turret_hc['board_bay']['tension_per_screw_n'], 'tension': True,
                'source': 'exports/turret/fea/summary.json hand_checks.board_bay'}], notes='')
    add(id='turret.board_bay_boards', assembly='turret', where="board bay back (PETG Ø10 bosses): the boards", qty_robot=4,
        insert='insert_m3', d_mm=3, material='petg', infill='5 walls, 40 % gyroid',
        hole={'d': fast['M3']['insert_pilot'], 'depth': repo.num('cad/turret.py', r"y1 - 0\.1, y1 \+ ([\d.]+), x, z\)\)\s+# 5\.7 mm insert")},
        boss_mm=2 * repo.num('cad/turret.py', r's = s\.union\(cyl_y\(([\d.]+), y1, -a1 - t \+ 0\.01, x, z\)\)'), axis='print-z',
        orientation='printed on its back',
        screw='M3 through the boards', screw_side='open end', mating_hole_mm=None, tip_depth_mm=None, clamp=None, loads=[],
        notes='Light.')
    side = repo.num('cad/turret.py', r'^INSERT_M3_SIDE = ([\d.]+)')
    plate_t = 3.175
    add(id='turret.cradle_plates', assembly='turret', where="cradle rail frame rebates (PA6-CF): the two 6061 cheek plates",
        qty_robot=8, insert='insert_m3', d_mm=3, material='pa6-cf', infill='4 walls, 100 %',
        hole={'d': fast['M3']['insert_pilot'], 'depth': side}, axis='layer-plane',
        orientation='frame printed flat: inserts put in from the side', screw=f'M3 x 8 buttons through the {plate_t:g} mm plates',
        screw_side='open end', mating_hole_mm=fast['M3']['clear'], tip_depth_mm=8 - plate_t,
        clamp={'stack': 'aluminium plate', 'printed_mm': 0, 'limiter': 'n/a'},
        loads=[{'case': 'R: 30 g sideways, the frame pulling one plate\'s foot',
                'per_insert_n': turret_hc['plate_inserts']['tension_per_insert_n'], 'tension': True,
                'source': 'exports/turret/fea/summary.json hand_checks.plate_inserts'}],
        pullout_repo_n=turret_hc['plate_inserts']['m3_insert_pullout_n_est'],
        notes=f"PLATE foot_holes_x has 4 a plate ({repo.has('cad/turret.py', chr(39) + 'foot_holes_x' + chr(39) + ': (-3.0, 33.0, 58.0, 77.0)')}).",
        extra=[('note-vs-joint', 'fix', 'cad/turret.py comment ' + q(repo.has('cad/turret.py', 'and their 3 x M3 inserts, put in from the rebate')) +
                ': PLATE foot_holes_x has four a plate')])
    add(id='turret.cartridge_board', assembly='turret', where="cartridge cage plate standoffs (PA6-CF): the cartridge board",
        qty_robot=4, insert='insert_m3', d_mm=3, material='pa6-cf', infill='100 %',
        hole={'d': fast['M3']['insert_pilot'], 'depth': repo.num('cad/turret.py', r"G\.plate_z1 \+ cb\['boss_h'\] \+ cb\['standoff'\], 'M3', ([\d.]+)\)\)")},
        axis='print-z', orientation='printed on its base', screw='M3 through the board', screw_side='open end',
        mating_hole_mm=None, tip_depth_mm=None, clamp=None, loads=[], notes='Light (30 g board).')
    add(id='turret.laser_foot', assembly='turret', where="barrel socket pad: the laser holder (gated)", qty_robot=2,
        insert='insert_m3', d_mm=3, material='pa6-cf', infill='100 %',
        hole={'d': fast['M3']['insert_pilot'], 'depth': repo.num('cad/turret.py', r"s = s\.cut\(insert_hole\(x, y, SOCKET_PAD_Z, 'M3', ([\d.]+)\)\)")},
        axis='print-z', orientation='printed on its base', screw='M3 x 10 (turret fastener gate)', screw_side='open end',
        mating_hole_mm=fast['M3']['clear'], tip_depth_mm=None, clamp={'stack': 'PETG laser foot', 'printed_mm': 6.0, 'limiter': None},
        loads=[], notes='Engagement and tip are checked by cadagent.gates.fasteners (exports/turret/gates.json).')
    add(id='turret.barrel_set_screw', assembly='turret', where="barrel socket pad: the barrel's M3 set screw", qty_robot=1,
        insert='insert_m3', d_mm=3, material='pa6-cf', infill='100 %',
        hole={'d': fast['M3']['insert_pilot'], 'through': True,
              'depth': round(repo.num('cad/turret.py', r'^SOCKET_PAD_Z = ([\d.]+)') - ((ball_d + 1.5) / 2), 2)},
        axis='print-z', orientation='printed on its base', screw='M3 set screw onto the PETG barrel',
        screw_side='reaction pushes the insert out (jack-out by design)', mating_hole_mm=None, tip_depth_mm=None, clamp=None,
        torque_nm=0.2, preload_n=r(preload(0.2, 3), 0), torque_source='recommended here (snug)',
        loads=[{'case': 'the set screw\'s own thrust at 0.2 N m', 'per_insert_n': r(preload(0.2, 3), 0), 'tension': True,
                'source': 'K = 0.2'}],
        notes='The set screw\'s thrust on the barrel is reacted by the insert in pull-out. Snug only.',
        extra=[('set-screw-torque', 'check', f"limit the set screw to ~0.2 N m ({preload(0.2, 3):.0f} N); at 0.5 N m it pushes "
                f"{preload(0.5, 3):.0f} N on the insert, about its whole estimated pull-out")])
    repo.has('cad/turret.py', 'self.base_z0 = -(self.br + 3.0)')
    base_z0 = -((ball_d + 1.5) / 2 + 3.0)                          # Geo(): bore = ball + 1.5, br = bore / 2
    cap_z = repo.num('cad/turret.py', r"bz0 - 1, (-[\d.]+), \*ct_latch\)\)\s+# insert from below, 1 mm cap")
    ct_depth = cap_z - base_z0
    add(id='turret.ct_latch', assembly='turret', where="cartridge base (PA6-CF): the CT latch's one M4 (Ø10 boss, from below)",
        qty_robot=1, insert='turret_insert_m4', d_mm=4, material='pa6-cf', infill='100 %',
        hole={'d': fast['M4']['insert_pilot'], 'depth': round(ct_depth, 2)}, boss_mm=10.0, axis='print-z',
        orientation='printed on its base', screw='DIN 464 M4 x 12 knurled thumbscrew up through the cradle rail (hand tight)',
        screw_side='open end (from below): a tumble pulls the cartridge off it', mating_hole_mm=fast['M4']['clear'],
        tip_depth_mm=repo.num('cad/turret.py', r'the M4 x 12 keeps (\d+) mm in the cartridge'),
        clamp={'stack': '7 mm PA6-CF rail under the collar (hand tight)', 'printed_mm': 7.0, 'limiter': None},
        loads=[{'case': 'R: 30 g, the cartridge (0.64 kg) pulled off the rails', 'per_insert_n': 188, 'tension': True,
                'source': 'exports/turret/fea/summary.json (cradle R-fall-down load 188 N, reversed)'},
               {'case': 'E: a 50 N push on the muzzle', 'per_insert_n': 88, 'tension': True,
                'source': 'cad/turret_studies.py T_latch (FEA cradle E-push-up)'}],
        pullout_repo_n=turret_hc['yoke_inserts']['m4_insert_pullout_n_est'],
        notes='One screw holds the cartridge. The pilot ends 0.2 mm past the 6.4 mm insert under a 1 mm cap; most of the '
              'insert sits in the free-standing Ø10 boss above the 3 mm plate.')
    add(id='turret.hopper_lugs', assembly='turret', where="cartridge housing top: the hopper's three lugs (gated)", qty_robot=3,
        insert='insert_m3', d_mm=3, material='pa6-cf', infill='100 %',
        hole={'d': fast['M3']['insert_pilot'], 'depth': repo.num('cad/turret.py', r"G\.housing_top, 'M3', ([\d.]+)\)\)")},
        axis='print-z', orientation='printed on its base', screw='M3 x 8 through the PETG lugs (turret fastener gate)',
        screw_side='open end', mating_hole_mm=fast['M3']['clear'], tip_depth_mm=None, clamp=None, loads=[],
        notes='Checked by cadagent.gates.fasteners.')

    # ------------------------------------------------------------------ stand, box (bench furniture)
    top = repo.num('cad/turret_stand.py', r'^WALL, TOP, BOT = [\d.]+, ([\d.]+), [\d.]+')
    dock = repo.num('cad/turret_stand.py', r"s = s\.cut\(_cyl_z\(FAST\['M3'\]\['insert_pilot'\] / 2, -TOP - 0\.01, -TOP \+ ([\d.]+), dx0")
    add(id='stand.tm', assembly='turret stand', where="stand top plate (PETG, 3 walls 20 % gyroid): the plinth's TM",
        qty_robot=4, insert='insert_m5', d_mm=5, material='petg', infill='3 walls, 20 % gyroid',
        hole={'d': fast['M5']['insert_pilot'], 'depth': top + repo.num('cad/turret_stand.py', r"s = s\.cut\(_cyl_z\(FAST\['M5'\]\['insert_pilot'\] / 2, -TOP - ([\d.]+), 0\.1, x, y\)\)")},
        boss_mm=2 * repo.num('cad/turret_stand.py', r's = s\.union\(_cyl_z\(([\d.]+), -TOP - 8\.0, -TOP \+ 0\.01, x, y\)\)'),
        axis='print-z', orientation='printed upside down', screw=mount['tm']['bolt_screw'] + ' through the plinth tray',
        screw_side='open end', mating_hole_mm=fast['M5']['clear'], tip_depth_mm=tip_tray, clamp=None, loads=[],
        notes='Bench duty.')
    add(id='stand.dock', assembly='turret stand', where="stand top plate underside: the dock adapter's 2 x M3", qty_robot=2,
        insert='insert_m3', d_mm=3, material='petg', infill='3 walls, 20 % gyroid',
        hole={'d': fast['M3']['insert_pilot'], 'depth': dock}, material_mm=top, axis='print-z', orientation='printed upside down',
        screw='2 x M3 up through the adapter (drilled on arrival)', screw_side='open end', mating_hole_mm=None, tip_depth_mm=None,
        clamp=None, loads=[], notes=f"The {top:g} mm plate leaves {top - dock:g} mm over the {dock:g} mm pilot.",
        extra=[('pilot-fix', 'fix', f"a {dock:g} mm blind pilot takes neither M3 insert (5.7 or 4.3): use 94459A130 (4.3) in a "
                f"{4.3 + 1.0:g} mm pilot ({top - 5.3:.1f} mm skin), or a boss under the plate for 94459A140")])
    add(id='stand.corners', assembly='turret stand', where="stand corner bosses (PETG Ø12): the bottom's 4 x M3", qty_robot=4,
        insert='insert_m3', d_mm=3, material='petg', infill='3 walls, 20 % gyroid',
        hole={'d': fast['M3']['insert_pilot'], 'depth': repo.num('cad/turret_stand.py', r"-H - 1, -H \+ ([\d.]+), x, y\)\)")},
        boss_mm=2 * repo.num('cad/turret_stand.py', r'^BOSS_R = ([\d.]+)'), axis='print-z', orientation='printed upside down', screw='M3 through the bottom', screw_side='open end',
        mating_hole_mm=None, tip_depth_mm=None, clamp=None, loads=[], notes='')
    deck_t = repo.num('cad/turret_box.py', r'^TM_PILOT_DEPTH = DECK_T \+ ([\d.]+)')
    add(id='box.tm', assembly='J501 box', where="J501 box deck (PETG): the turret's TM, through the 8 mm deck", qty_robot=4,
        insert='insert_m5', d_mm=5, material='petg', infill='see exports/turret/box', hole={'d': fast['M5']['insert_pilot'],
        'depth': 8.0 + deck_t, 'through': True}, axis='print-z', orientation='deck printed upside down',
        screw='M5 x 12 buttons through the 5 mm foot (cad/turret_box.py)', screw_side='open end', mating_hole_mm=fast['M5']['clear'],
        tip_depth_mm=repo.num('cad/turret_box.py', r'^TM_SCREW_LEN = ([\d.]+)') - foot_t, clamp=None, loads=[],
        notes='Through pilot: the insert fills the 8 mm deck and the screw ends 1 mm short of its underside. With the D66 '
              'plinth\'s M5 x 16 instead, the tip would stand 3.5 mm below the deck.')
    add(id='box.small', assembly='J501 box', where='box shroud tabs (M3 x 4.3 from below) and pod bosses (M3)', qty_robot=10,
        insert='turret_insert_m3_short', d_mm=3, material='petg', infill='see exports/turret/box',
        hole={'d': fast['M3']['insert_pilot'], 'depth': repo.num('cad/turret_box.py', r"DECK_Z0 - 0\.1, DECK_Z0 \+ ([\d.]+), x, y\)\)")},
        axis='print-z', orientation='deck printed upside down', screw='M3', screw_side='open end', mating_hole_mm=None,
        tip_depth_mm=None, clamp=None, loads=[], notes='Light. The pod bosses take the 5.7 mm M3 in 8.1 mm pilots.')

    # ================================================================== RIG (bench)
    contactor_t = repo.num('cad/rig_assembly.py', r'the contactor on its two M4 inserts \(([\d.]+) N m\)')
    add(id='rig.pod_m4', assembly='leg rig', where="rig pod (PETG Ø10 bosses): contactor, relay, pendant clip", qty_robot=5,
        insert='turret_insert_m4', d_mm=4, material='petg', infill='PETG (rig parts)',
        hole={'d': fast['M4']['insert_pilot'], 'depth': repo.num('cad/rig_parts.py', r"FAST\['M4'\]\['insert_pilot'\] / 2, 'z', t - ([\d.]+), t \+ 6\.1, c\['x'\]")
              + repo.num('cad/rig_parts.py', r"FAST\['M4'\]\['insert_pilot'\] / 2, 'z', t - 3\.0, t \+ ([\d.]+), c\['x'\]")},
        boss_mm=2 * repo.num('cad/rig_parts.py', r"s = s\.union\(cyl\(([\d.]+), 'z', t - 0\.01, t \+ 6\.0, c\['x'\]"),
        axis='print-z', orientation='pod printed on its floor',
        screw='M4 (contactor, relay); M4 x 10 (pendant clip)', screw_side='open end', mating_hole_mm=None, tip_depth_mm=None,
        clamp=None, torque_nm=contactor_t, torque_source="docs/leg-rig-assembly.md: 'the contactor on its two M4 inserts (2.3 N m)'",
        preload_n=r(preload(contactor_t, 4), 0), loads=[],
        notes="TE's 2.3 N m is a mounting torque for a metal panel; into a PETG insert it is about the insert's whole pull-out.",
        extra=[('insert-torque', 'check', f"{contactor_t:g} N m on an M4 ~ {preload(contactor_t, 4):.0f} N; the PETG M4 insert's "
                f"pull-out estimate is {pullout(mat['petg']['tau_mpa'], 5.6, 6.4):.0f} N: set it flush so the base bears on the "
                f"brass and tighten to ~1 N m ({preload(1.0, 4):.0f} N)")])
    add(id='rig.tof_arm', assembly='leg rig', where="ToF arm (PETG Ø10 bosses) on the carriage plate", qty_robot=2,
        insert='turret_insert_m4', d_mm=4, material='petg', infill='PETG (rig parts)',
        hole={'d': fast['M4']['insert_pilot'], 'depth': repo.num('cad/rig_parts.py', r"'y', Y_PLATE_FRONT - 1, Y_PLATE_FRONT \+ ([\d.]+), x, z\)\)")},
        boss_mm=2 * repo.num('cad/rig_parts.py', r"s = s\.union\(cyl\(([\d.]+), 'y', Y_PLATE_FRONT, Y_PLATE_FRONT \+ 10\.0, x, z\)\)"), axis='print-z', orientation='', screw='M4 x 10 from the plate\'s back', screw_side='open end',
        mating_hole_mm=fast['M4']['clear'], tip_depth_mm=10 - repo.num('cad/rig_parts.py', r'^PLATE_T = ([\d.]+)'), clamp=None, loads=[],
        notes='Light.')

    for j in J:
        screen(j, ins, mat, None)
    return J, ins, mat


def findings(J):
    out = []
    for j in J:
        for f in j['findings']:
            if f['level'] in ('fix', 'owner', 'check'):
                out.append({'joint': j['id'], **f})
    order = {'fix': 0, 'owner': 1, 'check': 2}
    return sorted(out, key=lambda f: (order[f['level']], f['joint']))


def document(repo):
    J, ins, mat = build(repo)
    F = findings(J)
    counts = {}
    for j in J:
        counts[j['verdict']] = counts.get(j['verdict'], 0) + 1
    return {
        'schema': 1,
        'generator': 'research/insert-joints/inventory.py',
        'status': 'screen, not qualification: no part printed or tested for this inventory',
        'basis': {'nut_factor': K_NUT, 'engage_min_d': ENGAGE_MIN_D, 'spirol_boss_ratio': SPIROL_BOSS, 'tip_room_mm': TIP_ROOM,
                  'pullout': {'formula': 'tau x pi x hole x insert length (the knurl cylinder)', 'petg_test': PETG_TEST,
                              'pla_test': PLA_TEST, 'materials': {k: v for k, v in mat.items() if isinstance(v, dict)},
                              'repo_estimates_win_when_lower': True},
                  'bearing': {'sustained_mpa': mat['bearing_sustained_mpa'], 'humid_mpa': mat['bearing_humid_mpa'],
                              'source': 'cad/studies.py JOINT (washer_mpa, bearing_mpa)'},
                  'sources': SOURCES},
        'inserts': ins,
        'joints': J,
        'findings': F,
        'summary': {'families': len(J), 'inserts_on_robot': sum(j['qty_robot'] for j in J if j.get('insert')
                                                                 and not j['assembly'].startswith(('turret stand', 'J501', 'leg rig'))),
                    'verdicts': counts, 'fix': sum(f['level'] == 'fix' for f in F), 'owner': sum(f['level'] == 'owner' for f in F),
                    'check': sum(f['level'] == 'check' for f in F)},
        'bindings': repo.bindings,
    }


# ---------------------------------------------------------------------------------------------------- markdown

def markdown(doc):
    L = ['# Insert and clamped-plastic joint inventory', '',
         'Generated by `research/insert-joints/inventory.py` from the bound sources in `joints.json` (do not edit; run the '
         'generator). A screen, not a qualification: nothing here has been printed or tested. See [README.md](README.md) '
         'for the method and its limits.', '',
         f"**{doc['summary']['families']} joint families**, {doc['summary']['inserts_on_robot']} heat-set inserts on the robot "
         f"(legs, body, turret). Findings: **{doc['summary']['fix']} clear fixes**, **{doc['summary']['owner']} owner "
         f"decisions**, {doc['summary']['check']} assembly / qualification checks.", '',
         '| Joint | Qty | Insert | Pilot Ø x depth | Boss / insert | Axis | Screw tip / clear | Clamped plastic | Worst load | SF | Verdict |',
         '|---|---:|---|---|---|---|---|---|---:|---:|---|']
    for j in doc['joints']:
        i = doc['inserts'].get(j['insert']) if j.get('insert') else None
        h = j.get('hole')
        pil = f"{h['d']:g} x {h['depth']:g}{' thru' if h.get('through') else ''}" if h else '-'
        boss = f"{j['boss_ratio']:g}" if j.get('boss_ratio') else '-'
        tip = (f"{j['tip_depth_mm']:g} / {j['tip_clear_mm']:g}" if j.get('tip_clear_mm') is not None
               else f"{j['tip_depth_mm']:g}" if j.get('tip_depth_mm') is not None else '-')
        c = j.get('clamp') or {}
        cl = (f"{c['printed_mm']:g} mm" + (f", {c['bearing_mpa']:g} MPa" if c.get('bearing_mpa') else '')) if c.get('printed_mm') else '-'
        loads = [x['per_insert_n'] for x in j.get('loads') or [] if x.get('per_insert_n')]
        L.append(f"| `{j['id']}` | {j['qty_robot']} | {i['pn'] + ' ' + i['thread'] if i else j.get('receiver', '-')} | {pil} | "
                 f"{boss} | {j.get('axis', '-')} | {tip} | {cl} | {max(loads) if loads else '-'} | "
                 f"{j.get('sf_pullout', '-')} | {j['verdict']} |")
    L += ['', '## Findings', '']
    for lvl, title in (('fix', 'Clear fixes'), ('owner', 'Owner decisions'), ('check', 'Assembly and qualification checks')):
        rows = [f for f in doc['findings'] if f['level'] == lvl]
        if rows:
            L += [f'### {title}', '']
            L += [f"- `{f['joint']}` ({f['code']}): {f['text']}" for f in rows]
            L.append('')
    L += ['## Per joint', '']
    for j in doc['joints']:
        L.append(f"### `{j['id']}`")
        L.append('')
        L.append(f"{j['where']}. Material {j['material']} ({j.get('infill', '')}). Screw: {j.get('screw', '-')}.")
        if j.get('orientation'):
            L.append(f"Orientation: {j['orientation']}.")
        if j.get('screw_side'):
            L.append(f"Screw side: {j['screw_side']}.")
        c = j.get('clamp')
        if c:
            s = f"Clamp: {c['stack']}; limiter: {c.get('limiter') or 'none'}."
            if c.get('bearing_mpa'):
                s += (f" {j['preload_n']:g} N on {c['bearing_area_mm2']:g} mm2 = {c['bearing_mpa']:g} MPa; the "
                      f"{doc['basis']['bearing']['sustained_mpa']:g} MPa screen allows {c['preload_at_sustained_n']:g} N "
                      f"({c['torque_at_sustained_nm']:g} N m at K 0.2).")
            L.append(s)
        if j.get('torque_nm') is not None:
            L.append(f"Torque {j['torque_nm']:g} N m ({j.get('torque_source', '')}) ~ {j.get('preload_n')} N at K 0.2.")
        if j.get('capacity_n'):
            L.append(f"Pull-out estimate {j['pullout_est_n']:g} N" + (f" (repository estimate {j['pullout_repo_n']:g} N; the "
                     f"lower is used)" if j.get('pullout_repo_n') else '') + '.')
        for x in j.get('loads') or []:
            L.append(f"Load: {x['case']}: {x['per_insert_n'] if x.get('per_insert_n') is not None else '-'} N ({x['source']}).")
        if j.get('notes'):
            L.append(j['notes'])
        for f in j['findings']:
            L.append(f"- **{f['level']}** `{f['code']}`: {f['text']}")
        L.append('')
    return '\n'.join(L).rstrip() + '\n'


def cross_check(src, doc):
    """Optional: every stack and preload again through cadagent (a checkout's src directory), compared to ours."""
    sys.path.insert(0, str(src))
    from cadagent.formulas import screws
    from cadagent.mechanical.fasteners import blind_insert_stack
    out = {'stacks': 0, 'preloads': 0, 'disagree': []}
    for j in doc['joints']:
        if j.get('torque_nm') and j.get('preload_n'):
            ca = screws.preload_from_torque(j['torque_nm'], j['d_mm'] / 1000.0)
            out['preloads'] += 1
            if abs(ca - j['preload_n']) > 1.0:
                out['disagree'].append((j['id'], 'preload', ca, j['preload_n']))
        h, i = j.get('hole'), doc['inserts'].get(j.get('insert') or '')
        if h and i and j.get('tip_depth_mm') is not None and not h.get('through'):
            # one datum: the insert's face at 0, the head 10 mm above it, the pilot's floor at -depth
            st = blind_insert_stack(head_seat=10.0, screw_length=10.0 + j['tip_depth_mm'], insert_top=0.0,
                                    insert_length=i['length_mm'], hole_bottom=-max(h['depth'], i['length_mm']))
            out['stacks'] += 1
            ours = j.get('tip_clear_mm')
            theirs = st['tip_clearance_mm'] if h['depth'] >= i['length_mm'] else None
            if theirs is not None and abs(theirs - ours) > 0.01:
                out['disagree'].append((j['id'], 'tip', theirs, ours))
            if abs(st['engagement_mm'] - j['thread_engaged_mm']) > 0.01:
                out['disagree'].append((j['id'], 'engagement', st['engagement_mm'], j['thread_engaged_mm']))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true', help='exit 1 if the committed outputs are stale')
    ap.add_argument('--cad-agent', type=Path, help='a cad-agent src directory to cross-check the formulas against')
    a = ap.parse_args(argv)
    doc = document(Repo(ROOT))
    js = json.dumps(doc, indent=1, ensure_ascii=False) + '\n'
    md = markdown(doc)
    if a.cad_agent:
        cc = cross_check(a.cad_agent, doc)
        print(json.dumps(cc, indent=1))
        if cc['disagree']:
            return 1
    if a.check:
        stale = [p.name for p, t in ((OUT_JSON, js), (OUT_MD, md)) if not p.exists() or p.read_text() != t]
        if stale:
            print('stale: ' + ', '.join(stale) + ' (run python3 research/insert-joints/inventory.py)')
            return 1
        print(f"insert-joints: {doc['summary']['families']} families current")
        return 0
    OUT_JSON.write_text(js)
    OUT_MD.write_text(md)
    s = doc['summary']
    print(f"wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}: {s['families']} families, "
          f"{s['inserts_on_robot']} inserts on the robot, {s['fix']} fixes, {s['owner']} owner decisions, {s['check']} checks")
    return 0


if __name__ == '__main__':
    sys.exit(main())
