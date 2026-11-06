#!/usr/bin/env python3
"""Phase 2 of issue #137: the insert joints through cad-agent's released insert and compression-limiter checks.

Reads joints.json (inventory.py's output; it is not regenerated here) and runs every joint the toolkit has a check for
through a pinned cad-agent release: ``cadagent.formulas.inserts`` (pull-out, torque-out, displaced and overflow volume,
the clamp path, the insert-limited torque), ``cadagent.formulas.limiters`` (bearing area, proof load) and
``cadagent.mechanical.inserts`` (``check_joint`` for a screw into an insert, ``check_clamp`` for printed plastic
clamped into metal). Each result is set beside inventory.py's own number or verdict, with a stated tolerance, and
every disagreement says why. Writes phase2.json and phase2.md beside it.

    python3 research/insert-joints/phase2.py --cad-agent PATH        # regenerate (PATH: a cad-agent checkout at the pin)
    python3 research/insert-joints/phase2.py --check                  # exit 1 if phase2.json / phase2.md are stale
    python3 research/insert-joints/phase2.py --check --cad-agent PATH # also regenerate in memory and compare

The toolkit's formulas are SI (metres, newtons, pascals); its joint checks take millimetres, newtons and N m, as their
docstrings say. Both are recorded with the joints.json field each input came from. This is a screen, not a
qualification: nothing here was printed or pulled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = (HERE.parents[2])
JOINTS = HERE / 'joints.json'
OUT_JSON = HERE / 'phase2.json'
OUT_MD = HERE / 'phase2.md'
GENERATOR = 'docs/research/insert-joints/phase2.py'

PIN = 'v0.18.2'          # the cad-agent release this was run on
MODULES = ('cadagent.formulas.inserts', 'cadagent.formulas.limiters', 'cadagent.mechanical.inserts')
MM = 1e-3

# joints.json's materials and inserts, as the toolkit names them
MATERIALS = {
    'petg': ('petg-bambu-basic', 'catalog/materials.json petg is Bambu Lab PETG Basic, the same sheet (Z 35 MPa)'),
    'pa6-cf': ('pa6-cf20-polymaker-wet', "catalog/materials.json pa6-cf is Bambu Lab PA6-CF, which the toolkit's table "
               "lacks; inventory.py takes it humid with Polymaker's wet / dry ratio, so Polymaker's PA6-CF20 wet sheet "
               "stands in"),
}
INSERTS = {'insert_m3': 'mcmaster-94459A140', 'insert_m5': 'mcmaster-94459A775',
           'turret_insert_m4': 'mcmaster-94459A160', 'turret_insert_m3_short': 'mcmaster-94459A130'}
AXES = {'print-z': 'upright', 'layer-plane': 'lying'}
# a limit joints.json records that the toolkit's fix ladder does not know (typed here from the joint's notes)
CONSTRAINTS = {
    'leg.wheel_botwheel': {'washer_outside_max_mm': 12.0,
                           'source': "joints.json leg.wheel_botwheel.notes: on PCD 36 a washer must stay inside the hub's "
                                     'Ø48 bore (r 24), so its outside is at most 2 x (24 - 18) = 12 mm; the Ø18 DIN 9021 '
                                     'does not fit, the Ø11 DIN 433 does'},
}
BAMBU_PA6CF_XY_MPA = 102.0   # typed from catalog/materials.json pa6-cf tensile_mpa, for the along-layer error only
ASSUMED = [
    "screw class 12.9 (check_joint's default) where joints.json names none; it sets only the screw's own ceiling",
    'the insert flush with the joint face (recess 0), as inventory.py assumes and its preload-vs-pullout check asks',
    "a head joints.json does not size is the toolkit's default ISO 4762 socket head",
    'the worst tension load per insert in joints.json is the separating load (pull_n)',
    "a printed hole comes out 0.25 mm under the drawn pilot (the middle of cad-agent's CAD_ALLOWANCE_MM, 0.2-0.3 mm, "
    "which it adds for that reason): the melt volume is taken at that as-printed hole, and the drawn hole is recorded",
]
TOL = {
    'class': 'the same class (pass, warn or fail; or the same clamp path)',
    'band': "the inventory's value inside the toolkit's low-high band",
    'side': 'the same side of a safety factor of 2 (inventory: its capacity / the load; toolkit: its low capacity / '
            'the load, against its margin of 2)',
    'flag': 'both flag the documented torque, or neither does',
    'pct25': "within 25 % (the preload scatter the toolkit's nut-factor band gives, insert_limited_torque's limits)",
}
SKIP = {
    'leg.stop_posts': 'no screw: steel pins in blind holes since D53, which no insert or limiter check covers',
    'body.battery_adapter': "the adapter's insert pattern is not published, so joints.json records no insert, hole or "
                            'load per screw to check',
    'body.printed_clamps': "a group of {n} body joints with no stack per joint in joints.json ('see notes'); the body's "
                           'own joint check (exports/body/integrity.json) carries them',
    'leg.knee_eye_sleeves': 'the clamp is all steel (washer, sleeves, nut): joints.json records no printed thickness '
                            'beside the sleeves, so the limiter checks have no plastic to set them against',
    'leg.knee_spacer': "the spacer clamps two bearings' inner races, metal on metal: joints.json records no printed "
                       'thickness for a limiter check',
}
# check_joint's rows that depend on the clamped part; dropped where joints.json does not record it
CLAMP_ROWS = ('tightening torque', 'insert face', 'clamped on insert', 'clamped on washer', 'head bearing', 'preload kept',
              'insert thread')
FLAG_CODES = ('preload-vs-pullout', 'insert-torque', 'set-screw-torque', 'printed-clamp-crush', 'printed-clamp-creep')


def sig(v, n=6):
    """A float to n significant figures (stable JSON); other values unchanged."""
    if isinstance(v, bool) or not isinstance(v, float) or v == 0 or not math.isfinite(v):
        return v
    return float(f'{v:.{n}g}')


def clean(x):
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    return sig(x)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def src_dir(path: Path) -> Path:
    path = Path(path).resolve()
    return path / 'src' if (path / 'src' / 'cadagent').is_dir() else path


def toolkit_id(path: Path):
    """(tag, commit) of a cad-agent checkout; the tag only where HEAD is exactly on one."""
    top = src_dir(path).parent

    def git(*a):
        r = subprocess.run(['git', '-C', str(top), *a], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    return git('describe', '--tags', '--exact-match', 'HEAD'), git('rev-parse', 'HEAD')


class Toolkit:
    def __init__(self, path: Path):
        sys.path.insert(0, str(src_dir(path)))
        from cadagent import formulas as fx
        from cadagent.formulas import inserts as fi, limiters as fl
        from cadagent.mechanical import inserts as mi
        self.fx, self.fi, self.fl, self.mi = fx, fi, fl, mi


# ---------------------------------------------------------------------------------------------------- inputs

def jf(jid, field):
    return f'joints.json {jid}.{field}'


def clamp_material(j):
    """The clamped part's material and where it was read: a toolkit key, 'metal', or None (not recorded)."""
    c = j.get('clamp')
    if not c:
        return None, 'clamp: not recorded'
    text = (c.get('material') or '') + ' ' + c.get('stack', '')
    if (c.get('printed_mm') or 0) > 0:
        for name, key in (('PETG', 'petg'), ('PA6-CF', 'pa6-cf')):
            if name in text:
                field = 'clamp.material' if c.get('material') else 'clamp.stack'
                return MATERIALS[key][0], f'{jf(j["id"], field)} ({name})'
        return None, 'clamp: printed, material not named'
    if c.get('printed_mm') == 0 and c.get('limiter') == 'n/a':
        return 'metal', f'{jf(j["id"], "clamp")} (printed_mm 0, limiter n/a: no printed part in the clamp)'
    return None, f'{jf(j["id"], "clamp.stack")}: {c.get("stack")!r}, not a material the toolkit has'


def head_args(j):
    """The head for check_joint / check_clamp: (kwargs, source)."""
    c = j.get('clamp') or {}
    bearing = c.get('bearing', '')
    if 'socket' in bearing:
        return {'head': 'socket'}, jf(j['id'], 'clamp.bearing')
    if 'washer' in bearing and 'ISO 4762' in j.get('screw', ''):
        return {'head': 'socket', 'head_washer': 'iso7089'}, (
            f"{jf(j['id'], 'clamp.bearing')} ({bearing}) under an ISO 4762 head ({jf(j['id'], 'screw')}): the toolkit "
            f"lists no DIN 433, so ISO 7089 stands in (its outside larger than the {c.get('bearing_od_mm'):g} mm "
            'DIN 433)')
    if c.get('bearing_od_mm'):
        return {'head_mm': c['bearing_od_mm']}, jf(j['id'], 'clamp.bearing_od_mm')
    if 'button' in j.get('screw', ''):
        return {'head': 'button'}, jf(j['id'], 'screw')
    return {'head': 'socket'}, "assumed: the toolkit's default socket head"


def worst_tension(j):
    xs = [x['per_insert_n'] for x in j.get('loads') or [] if x.get('tension') and x.get('per_insert_n')]
    return max(xs) if xs else None


def finding_level(j, *codes):
    lv = [f['level'] for f in j['findings'] if f['code'] in codes]
    return lv[0] if lv else None


# ---------------------------------------------------------------------------------------------------- comparisons

def cmp(check, tol, inventory, toolkit, agree, why=None, ratio=None, si=None):
    out = {'check': check, 'tolerance': tol, 'inventory': inventory, 'toolkit': toolkit,
           'status': 'agree' if agree else 'disagree'}
    if ratio is not None:
        out['ratio'] = sig(ratio, 4)
    if si:
        out['si'] = si
    if why:
        out['why'] = why
    return out


def row(result, name):
    return next((r for r in result['checks'] if r['check'] == name), None)


def inv_class(level):
    """An inventory finding level as the toolkit's verdict classes."""
    return {'fix': 'fail', 'owner': 'warn', 'check': 'warn', 'note': 'warn', None: 'pass'}[level]


def insert_joint(j, doc, tk):
    jid, I = j['id'], doc['inserts'][j['insert']]
    key = INSERTS[j['insert']]
    ins = tk.mi.insert(key)
    mat = MATERIALS[j['material']][0]
    hole = j['hole']
    through = bool(hole.get('through'))
    cmat, cmat_src = clamp_material(j)
    head, head_src = head_args(j)
    set_screw = 'set screw' in j.get('screw', '')
    pull = worst_tension(j) or 0.0
    kw = {'insert': key, 'material': mat, 'axis': AXES[j['axis']], 'hole_mm': hole['d'], 'through': through,
          'pull_n': pull, **head}
    src = {'insert': f"{jf(jid, 'insert')} ({I['pn']})", 'material': f"{jf(jid, 'material')} ({j['material']}; see mapping.materials)",
           'axis': jf(jid, 'axis'), 'hole_mm': jf(jid, 'hole.d'), 'through': jf(jid, 'hole.through'),
           'pull_n': f"{jf(jid, 'loads')} (worst per_insert_n in tension)" if pull else 'no tension load recorded: 0',
           **{k: head_src for k in head}}
    if not through:
        kw['hole_depth_mm'], src['hole_depth_mm'] = hole['depth'], jf(jid, 'hole.depth')
    if j.get('boss_mm'):
        kw['boss_outside_mm'], src['boss_outside_mm'] = j['boss_mm'], jf(jid, 'boss_mm')
    if j.get('mating_hole_mm'):
        kw['clearance_mm'], src['clearance_mm'] = j['mating_hole_mm'], jf(jid, 'mating_hole_mm')
    if j.get('tip_depth_mm') is not None:
        kw['screw_depth_mm'], src['screw_depth_mm'] = j['tip_depth_mm'], jf(jid, 'tip_depth_mm')
    if j.get('torque_nm') and not set_screw:
        kw['torque_nm'], src['torque_nm'] = j['torque_nm'], jf(jid, 'torque_nm')
    if cmat == 'metal':
        kw['clamped'], src['clamped'] = {'material': 'metal'}, cmat_src
    elif cmat:
        kw['clamped'] = {'material': cmat, 'thickness_mm': j['clamp']['printed_mm']}
        src['clamped'] = f"{cmat_src}; thickness {jf(jid, 'clamp.printed_mm')}"
    else:
        # check_joint reads a missing clamped part as the insert's own plastic; the clamp-dependent rows are dropped
        kw['clamped'], src['clamped'] = {'material': 'metal'}, f'{cmat_src}: run as metal, clamp rows not compared'
    res = tk.mi.check_joint(**kw)
    cap = res['capacity']
    C, notes = [], []

    # the pilot: diameter, depth and the melt it must hold
    inv = inv_class(finding_level(j, 'hole-oversize', 'hole-undersize'))
    r_ = row(res, 'hole diameter')
    C.append(cmp('pilot diameter', TOL['class'], {'verdict': inv, 'field': 'hole.d', 'value_mm': hole['d'],
                                                  'rule_mm': [I['max_hole_mm'] - 0.25, I['max_hole_mm']]},
                 {'verdict': r_['verdict'], 'value_mm': r_['value'], 'rule_mm': r_['limit']}, inv == r_['verdict'],
                 None if inv == r_['verdict'] else
                 f"the toolkit wants the CAD pilot {r_['limit'][0]:g}-{r_['limit'][1]:g} mm: the maker's "
                 f"{ins.hole_mm:g} mm hole plus CNC Kitchen's 0.2-0.3 mm allowance, as a printed hole comes out about "
                 f"0.25 mm small. inventory.py holds it to the maker's maximum ({I['max_hole_mm']:g} mm, no more than "
                 f"0.25 under) as drawn. The fit specimens (research/carrier-insert-fit) settle which the printer needs"))
    if not through:
        inv = inv_class(finding_level(j, 'pilot-shorter-than-insert', 'pilot-below-spirol'))
        r_ = row(res, 'hole depth')
        rules = res['hole']['depth_rules_mm']
        C.append(cmp('pilot depth', TOL['class'],
                     {'verdict': inv, 'field': 'hole.depth', 'value_mm': hole['depth'],
                      'rule_mm': round(I['length_mm'] + 2 * I['pitch_mm'], 3), 'rule': 'L + 2 pitches (Spirol)'},
                     {'verdict': r_['verdict'], 'value_mm': r_['value'], 'rule_mm': r_['limit'], 'rules_mm': rules},
                     inv == r_['verdict'], None if inv == r_['verdict'] else
                     f"inventory.py asks L + 2 pitches ({I['length_mm'] + 2 * I['pitch_mm']:g} mm); the toolkit asks "
                     f"the deepest of {', '.join(f'{k} {v:g}' for k, v in rules.items())}, so {r_['limit']:g} mm" +
                     (f"; {hole['depth']:g} mm is between the two" if inv != r_['verdict'] else '')))
        if ins.volume_mm3 and ins.cad_bore_mm:
            shrink = sum(tk.mi.CAD_ALLOWANCE_MM) / 2.0
            printed = hole['d'] - shrink
            si = {'insert_volume_m3': {'value': sig(ins.volume_mm3 * MM ** 3), 'source': f'cad-agent INSERTS[{key!r}].volume_mm3 '
                                       "(McMaster's STEP)"},
                  'hole_diameter_m': {'value': sig(printed * MM), 'source': f"{jf(jid, 'hole.d')} ({hole['d']:g} mm "
                                      f"drawn) less {shrink:g} mm: as printed (cad-agent CAD_ALLOWANCE_MM, its middle)"},
                  'bore_diameter_m': {'value': sig(ins.cad_bore_mm * MM), 'source': f'cad-agent INSERTS[{key!r}].cad_bore_mm'},
                  'length_m': {'value': sig(ins.length_mm * MM), 'source': f'cad-agent INSERTS[{key!r}].length_mm'},
                  'depth_m': {'value': sig(hole['depth'] * MM), 'source': jf(jid, 'hole.depth')}}
            vol = {}
            for name, dh in (('printed', printed), ('drawn', hole['d'])):
                vol[name] = (tk.fi.insert_displaced_volume(ins.volume_mm3 * MM ** 3, dh * MM, ins.cad_bore_mm * MM,
                                                           ins.length_mm * MM),
                             tk.fi.overflow_volume(dh * MM, hole['depth'] * MM, ins.length_mm * MM))
            disp, pocket = vol['printed']
            tv = 'pass' if disp <= pocket else 'warn'
            tv_drawn = 'pass' if vol['drawn'][0] <= vol['drawn'][1] else 'warn'
            inv = inv_class(finding_level(j, 'pilot-below-spirol'))
            C.append(cmp('melt volume', TOL['class'], {'verdict': inv, 'finding': 'pilot-below-spirol (note)' if inv != 'pass'
                                                       else None},
                         {'verdict': tv, 'hole_mm': sig(printed), 'displaced_m3': sig(disp), 'pocket_m3': sig(pocket),
                          'as_drawn': {'hole_mm': hole['d'], 'verdict': tv_drawn, 'displaced_m3': sig(vol['drawn'][0]),
                                       'pocket_m3': sig(vol['drawn'][1])},
                          'functions': ['insert_displaced_volume', 'overflow_volume']}, inv == tv,
                         None if inv == tv else
                         f"at the as-printed hole ({printed:g} mm: the drawn {hole['d']:g} less {shrink:g}) McMaster's "
                         f"STEP volumes give {disp / MM ** 3:.1f} mm3 displaced against a {pocket / MM ** 3:.1f} mm3 "
                         'pocket, ' + ('so the toolkit passes what inventory.py notes from its L + 2 pitches rule '
                                       f"({I['length_mm'] + 2 * I['pitch_mm']:g} mm deep)" if tv == 'pass' else
                                       'so the toolkit warns where inventory.py does not'), si=si))
        else:
            notes.append(f"melt volume: the toolkit has no STEP volume for {key} (cad-agent INSERTS)")

    # the screw's tip against the pilot's floor
    if j.get('tip_depth_mm') is not None and not through:
        inv = inv_class(finding_level(j, 'screw-bottoms', 'tip-near-floor'))
        r_ = row(res, 'screw tip')
        C.append(cmp('screw tip', TOL['class'], {'verdict': inv, 'tip_mm': j['tip_depth_mm'], 'clear_mm': j.get('tip_clear_mm')},
                     {'verdict': r_['verdict'], 'tip_mm': r_['value'], 'limit_mm': r_['limit']}, inv == r_['verdict'],
                     None if inv == r_['verdict'] else
                     (f"the tip ({j['tip_depth_mm']:g} mm) passes the insert's end ({ins.length_mm:g} mm) into the room "
                      "left below it for the melt, which the toolkit warns of (the melt may have filled it and the "
                      f"screw then bottoms); inventory.py checks only the floor, {j.get('tip_clear_mm'):g} mm away"
                      if r_['verdict'] == 'warn' and inv == 'pass' else r_['detail'])))

    # the boss
    if j.get('boss_mm'):
        inv = 'warn' if finding_level(j, 'boss-thin') else 'pass'
        r_ = row(res, 'boss wall')
        tv = 'pass' if r_['verdict'] == 'pass' else 'warn'
        knurl, basis = tk.mi._knurl(ins)
        C.append(cmp('boss', TOL['class'] + '; warn and fail taken together', {
            'verdict': inv, 'ratio': j.get('boss_ratio'), 'insert_od_mm': I['od_mm'], 'od_basis': I['od_basis']},
            {'verdict': r_['verdict'], 'wall_mm': r_['value'], 'limit': r_['limit'], 'knurl_mm': knurl,
             'knurl_basis': basis}, inv == tv,
            None if inv == tv else
            f"inventory.py takes boss / insert OD ({j['boss_mm']:g} / {I['od_mm']:g} = {j['boss_mm'] / I['od_mm']:.2f}) "
            f"against 2; the toolkit takes the boss against 2 x the knurl ({knurl:g} mm, {basis}): "
            f"{j['boss_mm'] / knurl:.2f}"))
    # the insert's axis against the layers
    inv = 'warn' if finding_level(j, 'axis-in-layer-plane') else 'pass'
    r_ = row(res, 'insert axis')
    tv = r_['verdict'] if r_ else 'pass'
    C.append(cmp('insert axis', TOL['class'], {'verdict': inv, 'axis': j['axis']}, {'verdict': tv, 'axis': kw['axis']},
                 inv == tv, None if inv == tv else 'the two read the axis differently'))

    # the clamp path: does the clamped part bear on the brass, or does the screw jack the insert out
    if j.get('mating_hole_mm') and cmat:
        inv = 'jack-out' if finding_level(j, 'mating-hole-over-insert') else 'through-insert'
        tp = res['clamp']['path']
        C.append(cmp('clamp path', TOL['class'], {'path': inv, 'mating_hole_mm': j['mating_hole_mm'], 'insert_od_mm': I['od_mm']},
                     {'path': tp, 'function': 'insert_clamp_path', 'why': res['clamp']['why']}, inv == tp,
                     None if inv == tp else res['clamp']['why']))
    elif not j.get('mating_hole_mm'):
        notes.append('clamp path: joints.json records no mating hole')

    # pull-out: the shear model, by hand from the toolkit's own inputs, and against the load
    D, basis = tk.mi._knurl(ins)
    si = {'outer_diameter_m': {'value': sig(D * MM), 'source': f'cad-agent INSERTS[{key!r}] ({basis})'},
          'length_m': {'value': sig(ins.length_mm * MM), 'source': f'cad-agent INSERTS[{key!r}].length_mm'},
          'shear_strength_pa': {'value': sig(cap['shear_strength_pa']), 'source': f"half {mat}'s across-layer "
                                "strength (cadagent.mechanical.inserts.shear_strength)"},
          'calibration': {'value': {k: sig(v) for k, v in cap['c'].items()}, 'source': f"c fitted on '{cap['calibrated_on']}' "
                          '(cadagent.mechanical.inserts.calibration)'}}
    sheet = {k: tk.fi.insert_shear_force(D * MM, ins.length_mm * MM, cap['shear_strength_pa'], cap['c'][k])
             for k in ('low', 'mid', 'high')}
    assert all(abs(sheet[k] - cap['pull_out'][k]) < 1e-6 * sheet[k] for k in sheet), (jid, 'capacity() != formula')
    # the toolkit's sheet scaled to the inventory's own across-layer basis (1 for PETG; below 1 for PA6-CF)
    z_inv = doc['basis']['pullout']['materials'][j['material']]['z_mpa']
    scale = z_inv / tk.mi.PRINTED[mat].strength('across')
    si['basis_scale'] = {'value': sig(scale), 'source': f"joints.json basis.pullout.materials.{j['material']}.z_mpa "
                         f"({z_inv:g}) / {mat}'s across-layer strength ({tk.mi.PRINTED[mat].strength('across'):g} MPa)"}
    band = {k: v * scale for k, v in sheet.items()}
    est = j['pullout_est_n']
    tau_inv = doc['basis']['pullout']['materials'][j['material']]['tau_mpa']
    inside = band['low'] <= est <= band['high']
    C.append(cmp('pull-out capacity', TOL['band'], {'value_n': est, 'field': 'pullout_est_n', 'tau_mpa': tau_inv,
                                                    'diameter_mm': hole['d'], 'length_mm': I['length_mm']},
                 {'low_n': sig(band['low']), 'mid_n': sig(band['mid']), 'high_n': sig(band['high']),
                  'sheet_n': {k: sig(v) for k, v in sheet.items()}, 'basis_scale': sig(scale),
                  'function': 'insert_shear_force', 'calibrated_on': cap['calibrated_on'],
                  'outside_fit': cap['outside_fit'] or None}, inside,
                 None if inside else
                 f"{'above' if est > band['high'] else 'below'} the band: inventory.py takes CNC Kitchen's PETG test "
                 f"as a mean shear on the hole ({tau_inv:g} MPa x pi x {hole['d']:g} x {I['length_mm']:g} mm"
                 + (', scaled to humid PA6-CF' if j['material'] == 'pa6-cf' else '') +
                 f"); the toolkit fits c to {cap['calibrated_on']} tests on each test filament's datasheet and applies "
                 f"it to {mat}'s ({cap['shear_strength_pa'] / 1e6:g} MPa shear) on {D:g} mm ({basis}), so a "
                 'filament weaker across its layers than the tested one comes out lower; '
                 f"{est / band['mid']:.2f} x its mid, {est / band['high']:.2f} x its high end",
                 ratio=est / band['mid'], si=si))
    C[-1]['ratio_to_high'] = sig(est / band['high'], 4)
    if pull:
        cap_inv = j['capacity_n']
        sf_inv, sf_tk = cap_inv / pull, band['low'] / pull
        same = (sf_inv >= 2.0) == (sf_tk >= 2.0)
        C.append(cmp('pull-out margin', TOL['side'], {'sf': sig(sf_inv, 3), 'capacity_n': cap_inv, 'field': 'capacity_n',
                                                      'load_n': pull},
                     {'sf_low': sig(sf_tk, 3), 'low_n': sig(band['low']), 'verdict': row(res, 'pull-out')['verdict']}, same,
                     None if same else
                     f"inventory.py's capacity {cap_inv:g} N gives {sf_inv:.2f}; the toolkit holds the load to its low "
                     f"end, {band['low']:.0f} N, which gives {sf_tk:.2f}"
                     + (f" ({sheet['low']:.0f} N and {sheet['low'] / pull:.2f} on {mat}'s own sheet, scaled by "
                        f"{scale:.3f} to the inventory's across-layer basis)" if abs(scale - 1) > 1e-6 else '')))

    # the torque the documents give: the preload it makes, and whether it is safe for the insert
    if j.get('torque_nm') and set_screw:
        notes.append("tightening torque: a set screw has no head, so the toolkit's thread / collar split does not apply")
    elif j.get('torque_nm'):
        T, d = j['torque_nm'], ins.diameter_mm * MM
        k = res['torque']['nut_factor']
        lo, hi = T / (k['high'] * d), T / (k['low'] * d)
        ok = lo <= j['preload_n'] <= hi
        C.append(cmp('preload at torque', TOL['band'], {'preload_n': j['preload_n'], 'nut_factor': doc['basis']['nut_factor']},
                     {'low_n': sig(lo), 'high_n': sig(hi), 'nut_factor': {a: sig(b) for a, b in k.items()},
                      'function': 'nut_factor (thread in brass, collar band of the clamp)'}, ok,
                     None if ok else f"K 0.2 against the toolkit's {k['low']:.3f}-{k['high']:.3f} for this thread and collar",
                     ratio=j['preload_n'] / ((lo + hi) / 2)))
        ceilings = res['torque']['ceilings']
        if not cmat:
            ceilings = {a: b for a, b in ceilings.items() if a in ('screw', 'torque_out', 'jack_out', 'insert_thread')}
        gov = min(ceilings, key=ceilings.get)
        allowed = ceilings[gov]
        tv = 'pass' if T <= allowed * (1 + 1e-9) else 'warn' if T <= 2 * allowed else 'fail'
        inv_flag = any(f['code'] in FLAG_CODES for f in j['findings'])
        same = inv_flag == (tv != 'pass')
        C.append(cmp('tightening torque', TOL['flag'],
                     {'torque_nm': T, 'flagged': inv_flag,
                      'findings': [f['code'] for f in j['findings'] if f['code'] in FLAG_CODES]},
                     {'allowed_nm': sig(allowed), 'governed_by': gov, 'verdict': tv,
                      'ceilings_nm': {a: sig(b) for a, b in ceilings.items()},
                      'function': 'insert_limited_torque + check_joint caps'
                                  + ('' if cmat else ' (insert limits only: the clamped part is not recorded)')}, same,
                     None if same else
                     (f"the toolkit allows {allowed:.2f} N m, set by {gov.replace('_', ' ')}, at its least nut factor "
                      f"({k['low']:.3f}); inventory.py flags only a preload over half the pull-out estimate"
                      if tv != 'pass' else
                      f"inventory.py flags the preload against half its pull-out estimate; the toolkit's ceilings all "
                      f"pass at {T:g} N m (the lowest {allowed:.2f} N m, {gov.replace('_', ' ')})"),
                     ratio=T / allowed))

    # the printed part under the head
    c = j.get('clamp') or {}
    if c.get('bearing_area_mm2') and res['torque']['preload_caps_n'].get('head_bearing'):
        C.append(head_bearing(j, doc, res['torque']['preload_caps_n']['head_bearing'], res['head']['on_plastic']))

    caps = res['torque']['preload_caps_n']
    rows = {r['check']: r['verdict'] for r in res['checks']
            if cmat or r['check'] not in CLAMP_ROWS}
    only = {'verdict': 'fail' if 'fail' in rows.values() else 'warn' if 'warn' in rows.values() else 'pass',
            'rows': rows,
            'allowed_torque_nm': sig(res['torque']['allowed_nm']) if cmat else None,
            'governed_by': res['torque']['governed_by'] if cmat else None,
            'preload_caps_n': {a: sig(b) for a, b in caps.items()} if cmat else None,
            'torque_out_nm': {a: sig(b) for a, b in cap['torque_out'].items()},
            'confidence': cap['confidence']}
    if res.get('fixes') and cmat:
        only['fixes'] = fixes(res, tk, jid, f'M{ins.diameter_mm:g}')
    return {'id': jid, 'status': 'evaluated', 'kind': 'insert',
            'call': {'function': 'cadagent.mechanical.inserts.check_joint', 'units': 'mm, N, N m (its docstring)',
                     'kwargs': clean(kw), 'sources': src},
            'comparisons': C, 'toolkit_only': clean(only), 'not_compared': notes}


def fixes(res, tk, jid, thread):
    """The toolkit's fix ladder (#292) when the printed part's bearing sets the torque: each option, what it allows,
    and whether it fits a limit joints.json records (CONSTRAINTS; otherwise not checked against the geometry)."""
    out, limit = [], CONSTRAINTS.get(jid, {})
    for f in res['fixes']['options']:
        o = {'fix': f['fix'], 'what': f.get('what'), 'named': f['named']}
        if 'allowed_nm' in f:
            o.update(allowed_nm=sig(f['allowed_nm']), preload_n=sig(f['preload_n']), governed_by=f['governed_by'])
        if f.get('why'):
            o['why'] = f['why']
        washers = [v for k, v in (f.get('set') or {}).items() if k in ('head_washer', 'insert_washer') and v]
        if limit.get('washer_outside_max_mm') and washers:
            od = max(tk.mi.washer(w, thread)['d2_mm'] for w in washers)
            o['fits'] = od <= limit['washer_outside_max_mm']
            if not o['fits']:
                o['conflict'] = (f"its Ø{od:g} washer is over the Ø{limit['washer_outside_max_mm']:g} mm this joint "
                                 f"allows ({limit['source']})")
        out.append(o)
    return out


def head_bearing(j, doc, cap_n, face):
    """The preload the printed part under the head allows: the inventory's creep screen on its annulus, the toolkit's
    compressive strength / margin on the head's least bearing face."""
    c = j['clamp']
    s = doc['basis']['bearing']['sustained_mpa']
    inv = s * c['bearing_area_mm2']
    ok = abs(inv / cap_n - 1.0) <= 0.25
    return cmp('head bearing preload', TOL['pct25'],
               {'preload_n': sig(inv, 4), 'basis': f"{s:g} MPa sustained (basis.bearing) x clamp.bearing_area_mm2 "
                                                  f"{c['bearing_area_mm2']:g} (Ø{c['bearing_od_mm']:g} on Ø{c['bearing_id_mm']:g})"},
               {'preload_n': sig(cap_n, 4), 'area_mm2': sig(face['area_mm2'], 4), 'face': face['text']}, ok,
               None if ok else
               f"inventory.py allows {s:g} MPa (cad/studies.py's creep screen) on the nominal {c['bearing_od_mm']:g} mm "
               f"annulus ({c['bearing_area_mm2']:g} mm2); the toolkit allows its compressive strength / 2 on "
               f"{face['text']}", ratio=inv / cap_n)


def clamp_joint(j, doc, tk):
    jid, c = j['id'], j['clamp']
    mat = MATERIALS[j['material']][0]
    head, head_src = head_args(j)
    thread = f"M{j['d_mm']:g}"
    kw = {'thread': thread, 'material': mat, 'thickness_mm': c['printed_mm'], 'clearance_mm': c['bearing_id_mm'], **head}
    src = {'thread': jf(jid, 'd_mm'), 'material': f"{jf(jid, 'clamp.material')} ({c.get('material')}; see mapping.materials)",
           'thickness_mm': jf(jid, 'clamp.printed_mm'), 'clearance_mm': jf(jid, 'clamp.bearing_id_mm'),
           **{k: head_src for k in head}}
    if j.get('torque_nm'):
        kw['torque_nm'], src['torque_nm'] = j['torque_nm'], jf(jid, 'torque_nm')
    res = tk.mi.check_clamp(**kw)
    k = res['torque']['nut_factor']
    d = j['d_mm'] * MM
    cap_n, face = res['torque']['preload_caps_n']['head_bearing'], res['head']['on_plastic']
    allowed, gov, din = res['torque']['allowed_nm'], res['torque']['governed_by'], None
    if kw.get('head_washer'):
        # the joint's own washer, which the toolkit's tables lack: its real face through the toolkit's formulas, with
        # the friction of a head turning on a steel washer (the stand-in run's nut factor)
        area = tk.fl.bearing_area(c['bearing_od_mm'] * MM, c['bearing_id_mm'] * MM)
        strength = tk.mi.bearing_strength(mat)
        cap_n = strength / tk.mi.MARGIN * area
        face = {'area_mm2': area / MM ** 2,
                'text': f"the joint's own Ø{c['bearing_od_mm']:g} washer on a Ø{c['bearing_id_mm']:g} hole "
                        f"({area / MM ** 2:.2f} mm2, bearing_area), pressed flat, at {strength / 1e6:g} / "
                        f"{tk.mi.MARGIN:g} MPa"}
        ceil = {'screw': res['torque']['ceilings']['screw'], 'head_bearing': k['low'] * d * cap_n}
        gov = min(ceil, key=ceil.get)
        allowed = ceil[gov]
        need = worst_tension(j)
        lo, hi = allowed / (k['high'] * d), allowed / (k['low'] * d)
        din = {'washer': f"Ø{c['bearing_od_mm']:g} (joints.json clamp.bearing_od_mm)", 'area_m2': sig(area),
               'bearing_strength_pa': sig(strength), 'preload_cap_n': sig(cap_n), 'allowed_nm': sig(allowed),
               'governed_by': gov, 'preload_at_allowed_n': {'low': sig(lo), 'high': sig(hi)}, 'need_n': need,
               'stand_in_run': {'allowed_nm': sig(res['torque']['allowed_nm']),
                                'preload_cap_n': sig(res['torque']['preload_caps_n']['head_bearing']),
                                'washer': 'iso7089'}}
        ladder = fixes(res, tk, jid, thread) if res.get('fixes') else []
        fitting = [f for f in ladder if f['named'] and f.get('fits', True)]
        if need and lo < need:
            din['owner_note'] = (f"At the toolkit's {allowed:.2f} N m the preload is {lo:.0f}-{hi:.0f} N against the "
                                 f"{need:g} N a screw the flange needs (joints.json loads): not assured. "
                                 + (f"The toolkit's {fitting[0]['fix']} would allow {fitting[0]['allowed_nm']:.2f} N m"
                                    if fitting else "No fix in the toolkit's ladder fits the joint (see fixes)")
                                 + ", so the torque, the washer and the joint's need are an owner decision")
    C = [head_bearing(j, doc, cap_n, face)]
    if j.get('torque_nm'):
        T = j['torque_nm']
        lo, hi = T / (k['high'] * d), T / (k['low'] * d)
        ok = lo <= j['preload_n'] <= hi
        C.append(cmp('preload at torque', TOL['band'], {'preload_n': j['preload_n'], 'nut_factor': doc['basis']['nut_factor']},
                     {'low_n': sig(lo), 'high_n': sig(hi), 'nut_factor': {a: sig(b) for a, b in k.items()},
                      'function': "nut_factor (the toolkit's thread and collar friction bands)"}, ok,
                     None if ok else f"K 0.2 against the toolkit's {k['low']:.3f}-{k['high']:.3f} for this thread and collar",
                     ratio=j['preload_n'] / ((lo + hi) / 2)))
        tv = 'pass' if T <= allowed * (1 + 1e-9) else 'warn' if T <= tk.mi.MARGIN * allowed else 'fail'
        inv_flag = any(f['code'] in FLAG_CODES for f in j['findings'])
        same = inv_flag == (tv != 'pass')
        C.append(cmp('tightening torque', TOL['flag'],
                     {'torque_nm': T, 'flagged': inv_flag, 'findings': [f['code'] for f in j['findings'] if f['code'] in FLAG_CODES],
                      'torque_at_sustained_nm': c.get('torque_at_sustained_nm')},
                     {'allowed_nm': sig(allowed), 'governed_by': gov, 'verdict': tv}, same,
                     None if same else
                     (f"the toolkit allows {allowed:.2f} N m ({gov.replace('_', ' ')}): it takes the least nut factor "
                      f"({k['low']:.3f}), where a torque makes the most preload, and its compressive strength / 2; "
                      f"inventory.py's screen passes {c.get('torque_at_sustained_nm')} N m at K 0.2 and 25 MPa"
                      + (f". {din['owner_note']}" if din and din.get('owner_note') else '')),
                     ratio=T / allowed))
    only = {'verdict': res['verdict'], 'rows': {r['check']: r['verdict'] for r in res['checks']},
            'allowed_torque_nm': sig(allowed), 'governed_by': gov,
            'preload_caps_n': {a: sig(b) for a, b in res['torque']['preload_caps_n'].items()}}
    if din:
        only['own_washer'] = din
        if din.get('owner_note'):
            only['owner_note'] = din['owner_note']
    if res.get('fixes'):
        only['fixes'] = fixes(res, tk, jid, thread)
    return {'id': jid, 'status': 'evaluated', 'kind': 'clamp',
            'call': {'function': 'cadagent.mechanical.inserts.check_clamp', 'units': 'mm, N, N m (its docstring)',
                     'kwargs': clean(kw), 'sources': src},
            'comparisons': C, 'toolkit_only': clean(only), 'not_compared': []}


# ---------------------------------------------------------------------------------------------------- the document

def materials(doc, tk):
    """The material mapping, with which way each stand-in sheet errs against the inventory's own basis."""
    out = {}
    for k, (key, why) in MATERIALS.items():
        z_inv = doc['basis']['pullout']['materials'][k]['z_mpa']
        sheet = tk.mi.PRINTED[key]
        across = sheet.strength('across') / z_inv
        e = {'toolkit': key, 'why': why, 'across_mpa': {'toolkit': sheet.strength('across'), 'inventory': z_inv},
             'across_ratio': sig(across, 4)}
        if abs(across - 1) > 1e-6:
            dry = tk.mi.PRINTED[key.replace('-wet', '-dry')]
            along_inv = BAMBU_PA6CF_XY_MPA * sheet.strength('along') / dry.strength('along')
            e['along_ratio'] = sig(sheet.strength('along') / along_inv, 4)
            e['errs'] = (f"the stand-in sheet is {across:.2f} x the inventory's humid across-layer basis "
                         f"({sheet.strength('across'):g} / {z_inv:g} MPa) and about {e['along_ratio']:.2f} x along the "
                         f"layers ({sheet.strength('along'):g} against Bambu's {BAMBU_PA6CF_XY_MPA:g} MPa x "
                         f"{sheet.strength('along'):g} / {dry.strength('along'):g} wet / dry = {along_inv:.1f}): the "
                         'unsafe side. The pull-out bands and margins here are scaled by '
                         f"{1 / across:.3f} to the inventory's basis; the torque-out, torque ceilings and bearing caps "
                         'are the sheet\'s own and read that much high')
        out[k] = e
    return out


def flat_heads(doc):
    """Joints the toolkit sees as a flat head on solid plastic although joints.json records otherwise."""
    cs = [j['id'] for j in doc['joints'] if 'countersunk' in ((j.get('clamp') or {}).get('stack') or '')]
    gy = [j['id'] for j in doc['joints'] if 'gyroid' in ((j.get('clamp') or {}).get('stack') or '')
          and (j['clamp'].get('printed_mm') or 0) > 0]
    return [f"countersunk heads ({', '.join(cs)}) reach the toolkit as a flat socket head on solid plastic: their "
            'head-bearing rows do not model the cone',
            f"a 40 % gyroid clamped part ({', '.join(gy)}) reaches the toolkit as solid plastic: its bearing and "
            'clamped-on-insert ceilings read high']


def document(joints_path: Path, tk: Toolkit, tag: str, commit: str):
    doc = json.loads(joints_path.read_text())
    out = []
    for j in doc['joints']:
        jid = j['id']
        if jid in SKIP:
            out.append({'id': jid, 'status': 'skipped', 'reason': SKIP[jid].format(n=len(j.get('joints') or []))})
        elif j.get('insert'):
            out.append(insert_joint(j, doc, tk))
        elif (j.get('clamp') or {}).get('bearing_od_mm') and (j['clamp'].get('printed_mm') or 0) > 0:
            out.append(clamp_joint(j, doc, tk))
        else:
            out.append({'id': jid, 'status': 'skipped', 'reason': 'no insert and no printed clamp the toolkit can size'})
    by = {}
    for e in out:
        for c in e.get('comparisons', []):
            b = by.setdefault(c['check'], {'agree': 0, 'disagree': 0})
            b[c['status']] += 1
    allc = [c for e in out for c in e.get('comparisons', [])]
    return {
        'schema': 1,
        'generator': GENERATOR,
        'generator_sha256': sha256(Path(__file__)),
        'issue': 'Valpatel/gyropup#137, phase 2',
        'status': 'screen, not qualification: the toolkit set beside inventory.py; nothing printed or tested',
        'joints_json': {'path': 'docs/research/insert-joints/joints.json', 'sha256': sha256(joints_path),
                        'summary': doc['summary']},
        'toolkit': {'repo': 'Valpatel/cad-agent', 'tag': tag, 'commit': commit, 'modules': list(MODULES),
                    'material_status': tk.mi.STATUS, 'margin': tk.mi.MARGIN},
        'mapping': {'materials': materials(doc, tk), 'inserts': INSERTS, 'axes': AXES,
                    'assumed': ASSUMED + flat_heads(doc), 'constraints': CONSTRAINTS},
        'tolerances': TOL,
        'summary': {'joints': len(out), 'evaluated': sum(e['status'] == 'evaluated' for e in out),
                    'skipped': sum(e['status'] == 'skipped' for e in out), 'comparisons': len(allc),
                    'agree': sum(c['status'] == 'agree' for c in allc),
                    'disagree': sum(c['status'] == 'disagree' for c in allc), 'by_check': by},
        'joints': out,
    }


# ---------------------------------------------------------------------------------------------------- markdown

def short(why, n=260):
    return why if len(why) <= n else why[:n].rsplit(' ', 1)[0] + ' ...'


def markdown(doc):
    """phase2.md from phase2.json alone (no toolkit), so a check can rebuild it anywhere."""
    s, t = doc['summary'], doc['toolkit']
    L = ['# Insert joints, phase 2: inventory.py against cad-agent', '',
         f"Generated by `{doc['generator']}` from `joints.json` (sha256 `{doc['joints_json']['sha256'][:12]}`) with "
         f"cad-agent `{t['tag']}` (`{t['commit'][:10]}`): {', '.join(f'`{m}`' for m in t['modules'])}. Do not edit; "
         'run the generator. A screen, not a qualification.', '',
         f"**{s['evaluated']} of {s['joints']} joints evaluated** ({s['skipped']} skipped, each with its reason in "
         f"`phase2.json`). **{s['agree']} comparisons agree, {s['disagree']} disagree.** Tolerances: "
         + '; '.join(f'*{k}*: {v}' for k, v in doc['tolerances'].items()) + '.', '',
         '| Check | Agree | Disagree |', '|---|---:|---:|']
    for k, v in doc['summary']['by_check'].items():
        L.append(f"| {k} | {v['agree']} | {v['disagree']} |")
    L += ['', '## Per joint', '',
          '| Joint | Compared | Disagree | Toolkit verdict | Toolkit torque (N m, set by) |', '|---|---:|---|---|---|']
    for e in doc['joints']:
        if e['status'] != 'evaluated':
            continue
        o = e['toolkit_only']
        dis = [c['check'] for c in e['comparisons'] if c['status'] == 'disagree']
        tq = (f"{o['allowed_torque_nm']:.2f}, {o['governed_by'].replace('_', ' ')}" if o.get('allowed_torque_nm') else '-')
        L.append(f"| `{e['id']}` | {len(e['comparisons'])} | {', '.join(dis) or '-'} | {o['verdict']} | {tq} |")
    L += ['', '## Disagreements', '']
    groups = {}
    for e in doc['joints']:
        for c in e.get('comparisons', []):
            if c['status'] == 'disagree':
                key = (c['check'], re.sub(r'[\d.]+', '#', c['why']))
                groups.setdefault(key, []).append((e['id'], c))
    for (check, _), items in sorted(groups.items(), key=lambda kv: (kv[0][0], -len(kv[1]))):
        ids = ', '.join(f'`{i}`' for i, _ in items)
        c = items[0][1]
        def span(key):
            v = [x[key] for _, x in items]
            return f'{min(v):g}' + (f'-{max(v):g}' if len(v) > 1 and min(v) != max(v) else '')
        ratio = (f" Inventory / toolkit: {span('ratio')} x its mid, {span('ratio_to_high')} x its high end."
                 if all('ratio_to_high' in x for _, x in items) else
                 f" Ratio inventory / toolkit {span('ratio')}." if all('ratio' in x for _, x in items) else '')
        L.append(f"- **{check}** ({len(items)}: {ids}). `{items[0][0]}`: {short(c['why'])}{ratio}")
    L += ['', '## What only the toolkit checks', '']
    over = [(e, c) for e in doc['joints'] for c in e.get('comparisons', [])
            if c['check'] == 'tightening torque' and c['toolkit']['verdict'] != 'pass']
    if over:
        L.append('The documented torques over its ceiling: ' + '; '.join(
            f"`{e['id']}` {c['inventory']['torque_nm']:g} N m against {c['toolkit']['allowed_nm']:.2f} "
            f"({c['toolkit']['governed_by'].replace('_', ' ')})" for e, c in over) + '.')
        L.append('')
    gov = {}
    for e in doc['joints']:
        o = e.get('toolkit_only') or {}
        if o.get('governed_by') in ('clamped_on_insert', 'head_bearing', 'insert_face'):
            gov.setdefault(o['governed_by'], []).append((e['id'], o))
    for g, items in sorted(gov.items()):
        tq = [o['allowed_torque_nm'] for _, o in items]
        named = [(i, next((f for f in o.get('fixes') or [] if f['named'] and f.get('fits', True)), None))
                 for i, o in items]
        L.append(f"- **{g.replace('_', ' ')}** sets the most torque on {len(items)} joints ({min(tq):.2f}-{max(tq):.2f} N m)"
                 + (': ' + '; '.join(f"`{i}` {f['fix']} {f['allowed_nm']:.2f} N m" for i, f in named if f)
                    if any(f for _, f in named) else '') + '.')
    L.append('')
    notes = [(e['id'], e['toolkit_only']['owner_note']) for e in doc['joints']
             if (e.get('toolkit_only') or {}).get('owner_note')]
    for i, n in notes:
        L.append(f"- **Owner decision, `{i}`:** {n}.")
    for e in doc['joints']:
        for f in (e.get('toolkit_only') or {}).get('fixes') or []:
            if f.get('conflict'):
                L.append(f"- `{e['id']}`: the toolkit's {f['fix']} does not fit: {f['conflict']}.")
    L.append('')
    L.append('The fix ladder is checked against a joint\'s geometry only where joints.json records a limit '
             '(`mapping.constraints`). What the toolkit sees differently from joints.json is listed in `mapping.assumed`, '
             'and which way the PA6-CF stand-in errs in `mapping.materials`.')
    L.append('')
    L.append('Per joint in `phase2.json` (`toolkit_only`): every row, the preload caps, the torque-out band and the '
             "toolkit's fix ladder (a larger head, a washer, a large washer, a limiter) where the plastic sets the torque.")
    L += ['', '## Skipped', '']
    L += [f"- `{e['id']}`: {e['reason']}" for e in doc['joints'] if e['status'] == 'skipped']
    return '\n'.join(L).rstrip() + '\n'


def dumps(doc):
    return json.dumps(doc, indent=1, ensure_ascii=False) + '\n'


def stale(joints_path=JOINTS, out_json=OUT_JSON, out_md=OUT_MD, generator=Path(__file__)):
    """What makes the committed outputs stale, without the toolkit: a list of reasons (empty when current)."""
    if not out_json.exists():
        return [f'{out_json.name} is missing']
    doc = json.loads(out_json.read_text())
    why = []
    if doc.get('joints_json', {}).get('sha256') != sha256(joints_path):
        why.append('joints.json changed since phase2.json was generated')
    if doc.get('generator_sha256') != sha256(generator):
        why.append('phase2.py changed since phase2.json was generated')
    if not out_md.exists() or out_md.read_text() != markdown(doc):
        why.append('phase2.md does not match phase2.json')
    return why


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true', help='exit 1 if phase2.json / phase2.md are stale')
    ap.add_argument('--cad-agent', type=Path, help=f'a cad-agent checkout (or its src) at {PIN}')
    a = ap.parse_args(argv)
    if a.check:
        why = stale()
        if not why and a.cad_agent:
            tag, commit = toolkit_id(a.cad_agent)
            fresh = dumps(document(JOINTS, Toolkit(a.cad_agent), tag, commit))
            if fresh != OUT_JSON.read_text():
                why.append(f'phase2.json differs from a fresh run on {tag or commit}')
        if why:
            print('stale: ' + '; '.join(why) + ' (run python3 research/insert-joints/phase2.py --cad-agent PATH)')
            return 1
        print('insert-joints phase 2: current')
        return 0
    if not a.cad_agent:
        ap.error(f'--cad-agent PATH is needed to generate (a cad-agent checkout at {PIN})')
    tag, commit = toolkit_id(a.cad_agent)
    if tag != PIN:
        ap.error(f'the cad-agent checkout is at {tag or commit}, not the pinned {PIN}: check it out, or move PIN')
    doc = document(JOINTS, Toolkit(a.cad_agent), tag, commit)
    OUT_JSON.write_text(dumps(doc))
    OUT_MD.write_text(markdown(doc))
    s = doc['summary']
    print(f"wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}: {s['evaluated']} joints evaluated, "
          f"{s['skipped']} skipped, {s['agree']} agree, {s['disagree']} disagree")
    return 0


if __name__ == '__main__':
    sys.exit(main())
