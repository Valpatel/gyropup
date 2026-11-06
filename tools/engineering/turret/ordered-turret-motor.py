#!/usr/bin/env python3
"""Acquire exact-part claims and check a delivered sample's interface survey.

No CAD kernel is imported. cad-agent provides the common verdict format. A
complete survey is input to design review, never a motor/retention qualification.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ASIN = 'B0GJNX17YX'
PART = 'Deeahdah PRO3115-900KV'
URL = f'https://www.amazon.com/dp/{ASIN}'
SCHEMA = 'gyropup.ordered-motor-survey/1'
DATUM = 'mounting face z=0; shaft axis +z; +x toward lead exit; right-handed frame'
CLAIMS = {
    'body_diameter': 'Motor Diameter(mm)',
    'overall_length': 'Motor Length (mm)',
    'shaft_thread': 'Prop Adapter Shaft Thread',
    'mount_pattern': 'Bolt Pattern',
    'bearing': 'Bearing',
    'mass': 'Weight',
}
# Product-specific acquisition fields. Bounds reject corrupt units/data, not
# qualify tolerances. Zero is permitted for explicitly absent protrusions/pilots.
NUMERIC = {
    'body_diameter_mm': (1, 100),
    'mount_face_to_bell_top_mm': (1, 100),
    'mount_face_to_shaft_tip_mm': (1, 150),
    'rear_protrusion_mm': (0, 30),
    'rear_protrusion_diameter_mm': (0, 40),
    'shaft_thread_major_diameter_mm': (1, 20),
    'shaft_thread_pitch_mm': (.1, 3),
    'shaft_thread_usable_length_mm': (.1, 60),
    'shaft_shoulder_diameter_mm': (0, 30),
    'shaft_shoulder_length_mm': (0, 30),
    'shaft_seating_face_diameter_mm': (1, 60),
    'mount_thread_major_diameter_mm': (1, 10),
    'mount_thread_pitch_mm': (.1, 3),
    'mount_thread_usable_depth_mm': (.1, 20),
    'lead_outer_diameter_mm': (.1, 10),
    'lead_free_length_mm': (1, 1000),
    'mass_with_leads_g': (1, 1000),
}
ENUMS = {
    'shaft_thread_hand': ('right', 'left'),
    'mount_thread_hand': ('right', 'left'),
}
POINT_FIELDS = {'mount_hole_centres_xy_mm', 'lead_exit_xyz_mm'}
FIELDS = set(NUMERIC) | set(ENUMS) | POINT_FIELDS
BLOCKED_FLAGS = ('physical_fit_verified', 'mount_design_released', 'hub_design_released',
                 'slicer_run', 'powered_operation_qualified')
SOURCES = ('tools/ordered-turret-motor.py', 'research/ordered-turret-motor/seller-claims.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


class ListingParser(HTMLParser):
    """Read semantic table cells and selected ASIN; never infer from photo pixels."""
    def __init__(self):
        super().__init__()
        self.asins, self.rows, self.titles, self.byline = [], [], [], []
        self.cells = self.cell = None
        self.capture = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('id') == 'ASIN':
            self.asins.append(attrs.get('value'))
        if attrs.get('id') in ('productTitle', 'bylineInfo'):
            self.capture = (tag, attrs['id'])
        if tag == 'tr':
            self.cells = []
        if tag in ('td', 'th') and self.cells is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)
        if self.capture:
            (self.titles if self.capture[1] == 'productTitle' else self.byline).append(data)

    def handle_endtag(self, tag):
        if self.capture and tag == self.capture[0]:
            self.capture = None
        if tag in ('td', 'th') and self.cell is not None:
            self.cells.append(' '.join(' '.join(self.cell).split()))
            self.cell = None
        if tag == 'tr' and self.cells is not None:
            self.rows.append(self.cells)
            self.cells = None


def acquire(html_path, observed_date):
    date.fromisoformat(observed_date)
    parser = ListingParser()
    parser.feed(Path(html_path).read_text())
    if set(parser.asins) != {ASIN}:
        raise ValueError(f'Expected selected ASIN {ASIN}, found {parser.asins!r}')
    title = ' '.join(parser.titles).lower()
    brand = ' '.join(parser.byline).lower()
    if not re.search(r'pro\s*3115[-\s]*900\s*kv', title) or 'deeahdah' not in brand:
        raise ValueError('Selected product title/brand does not identify the ordered motor')
    claims = {}
    for key, label in CLAIMS.items():
        values = {r[1] for r in parser.rows if len(r) == 2 and r[0] == label}
        if len(values) != 1 or not next(iter(values)):
            raise ValueError(f'Missing or conflicting exact-listing table row: {label}')
        claims[key] = {'label': label, 'value': values.pop(), 'status': 'seller_claim_unmeasured'}
    return {'schema': 'gyropup.motor-seller-claims/1', 'part': PART, 'asin': ASIN,
            'source_url': URL, 'observed_date': observed_date, 'source_html_sha256': sha(html_path),
            'claims': claims,
            'limits': ['Not a manufacturer drawing or delivered-sample measurement.',
                       'M5 does not establish pitch, handedness, seating datum or usable length.',
                       'M3(19X19mm) does not establish hole coordinates, pitch or usable thread depth.',
                       'Listing photos include multiple colour variants; no dimensions inferred from pixels.']}


def template():
    return {'schema': SCHEMA, 'part': PART, 'asin': ASIN, 'sample_id': None,
            'observed_date': None, 'operator': None, 'datum': DATUM,
            'identity_evidence': [], 'measurement_notes': None,
            'measurements': {key: {'value': None, 'method': None, 'instrument': None,
                                   'uncertainty': None, 'evidence': []}
                             for key in sorted(FIELDS)},
            **{key: False for key in BLOCKED_FLAGS}}


def safe_evidence(value):
    """Invalid non-finite inputs remain inspectable in a strict JSON failure report."""
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, list):
        return [safe_evidence(v) for v in value]
    if isinstance(value, dict):
        return {k: safe_evidence(v) for k, v in value.items()}
    return value


def evidence_ok(entries, base):
    if not isinstance(entries, list) or not entries:
        return False
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'path', 'sha256'}:
            return False
        if not isinstance(entry['path'], str) or not isinstance(entry['sha256'], str):
            return False
        path = (base / entry['path']).resolve()
        if Path(entry['path']).is_absolute() or not path.is_relative_to(base.resolve()):
            return False
        if not path.is_file() or path.stat().st_size == 0 or sha(path) != entry['sha256']:
            return False
    return True


def value_ok(key, value):
    if key in NUMERIC:
        lo, hi = NUMERIC[key]
        return finite(value) and lo <= value <= hi
    if key in ENUMS:
        return value in ENUMS[key]
    if key == 'mount_hole_centres_xy_mm':
        return (isinstance(value, list) and len(value) == 4
                and all(isinstance(p, list) and len(p) == 2
                        and all(finite(x) and abs(x) <= 50 for x in p) for p in value)
                and len({tuple(p) for p in value}) == 4
                and all(math.hypot(*p) >= 1 for p in value))
    return (isinstance(value, list) and len(value) == 3
            and all(finite(x) and abs(x) <= 100 for x in value))


def survey_verdict(data, base, input_path=None):
    from cadagent.gates.verdict import Check, verdict
    checks = []
    def check(key, ok, message, evidence=None):
        checks.append(Check(key, 'pass' if ok else 'fail', message, evidence=evidence or {}))
    identity = (data.get('schema') == SCHEMA and data.get('part') == PART and data.get('asin') == ASIN)
    check('exact-part', identity, 'Survey must identify the exact ordered part and schema.')
    try:
        observed = date.fromisoformat(data.get('observed_date'))
        dated = date(2026, 10, 30) <= observed <= date.today()
    except (ValueError, TypeError):
        dated = False
    check('sample-identity', dated and all(isinstance(data.get(k), str) and data[k].strip()
                                         for k in ('sample_id', 'operator'))
          and evidence_ok(data.get('identity_evidence'), base),
          'Record the delivered sample ID, operator, observation date and hashed identity photographs.')
    check('datum', data.get('datum') == DATUM, 'Coordinates must use the declared mounting-face / shaft-axis datum.')
    check('qualification-flags', all(data.get(k) is False for k in BLOCKED_FLAGS),
          'Survey completeness cannot declare fit, a design release, slicing or powered qualification.')
    rows = data.get('measurements')
    rows = rows if isinstance(rows, dict) else {}
    check('field-membership', set(rows) == FIELDS, 'Every interface field is required; unexpected fields are rejected.')
    valid = {}
    for key in sorted(FIELDS):
        row = rows.get(key)
        row = row if isinstance(row, dict) else {}
        measured = (set(row) == {'value', 'method', 'instrument', 'uncertainty', 'evidence'}
                    and value_ok(key, row.get('value'))
                    and all(isinstance(row.get(k), str) and row[k].strip() for k in ('method', 'instrument'))
                    and evidence_ok(row.get('evidence'), base))
        if key in ENUMS:
            measured = measured and row.get('uncertainty') is None
        else:
            uncertainty = row.get('uncertainty')
            measured = measured and finite(uncertainty) and 0 < uncertainty <= .25
        valid[key] = bool(measured)
        check(f'measured:{key}', measured,
              'Provide a sample observation, method, instrument, uncertainty and hashed evidence.',
              {'value': safe_evidence(row.get('value')), 'uncertainty': safe_evidence(row.get('uncertainty'))})
    def v(key):
        return rows[key]['value']
    required = ['mount_face_to_bell_top_mm', 'mount_face_to_shaft_tip_mm', 'shaft_thread_usable_length_mm',
                'shaft_shoulder_diameter_mm', 'shaft_shoulder_length_mm', 'rear_protrusion_mm',
                'rear_protrusion_diameter_mm', 'shaft_thread_major_diameter_mm', 'shaft_thread_pitch_mm',
                'mount_thread_major_diameter_mm', 'mount_thread_pitch_mm']
    consistent = all(valid[k] for k in required)
    if consistent:
        consistent = (v('mount_face_to_shaft_tip_mm') > v('mount_face_to_bell_top_mm')
                      and v('shaft_thread_usable_length_mm') <= v('mount_face_to_shaft_tip_mm') - v('mount_face_to_bell_top_mm')
                      and ((v('shaft_shoulder_diameter_mm') == 0) == (v('shaft_shoulder_length_mm') == 0))
                      and ((v('rear_protrusion_diameter_mm') == 0) == (v('rear_protrusion_mm') == 0))
                      and v('shaft_thread_pitch_mm') < v('shaft_thread_major_diameter_mm')
                      and v('mount_thread_pitch_mm') < v('mount_thread_major_diameter_mm'))
    check('interface-consistency', consistent, 'Check axial order, explicit absence pairs and thread dimensions.')
    sources = {p: sha(ROOT / p) for p in SOURCES}
    return verdict('ordered-turret-motor-survey', checks,
                   assumptions=['Checks survey completeness and internal consistency, not truth of physical observations.',
                                'Seller claims never populate sample measurements.',
                                'One packet describes one individually identified motor; repeat for every delivered motor.',
                                'No mount/hub design, fastener stack, cable route, rotating retention or powered test is released.'],
                   extra={'survey_complete': all(c.status == 'pass' for c in checks),
                          'source_sha256': sources, 'survey_sha256': sha(input_path) if input_path else None,
                          **{k: False for k in BLOCKED_FLAGS if k != 'physical_fit_verified'}})


def survey_sheet():
    # Survey overlays are labelled hypotheses, not drill templates. Physical SVG
    # millimetres and viewBox match; 100 mm bars allow print-scale verification.
    body = ['<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">',
            '<rect width="210" height="297" fill="white"/>',
            '<g fill="#111" font-family="sans-serif">',
            '<text x="15" y="17" font-size="6">Ordered motor interface survey</text>',
            '<text x="15" y="26" font-size="4">Deeahdah PRO3115-900KV · B0GJNX17YX</text>',
            '<text x="15" y="35" font-size="4" font-weight="bold">MEASUREMENT AID ONLY — NOT A DRILL TEMPLATE</text>',
            '<text x="15" y="45" font-size="3.6">Print at 100%; measure both scale bars before using the sheet.</text>',
            '<text x="15" y="53" font-size="3.6">Seller “M3(19X19mm)” is ambiguous. Measure all four actual centres.</text>',
            '<text x="15" y="61" font-size="3.6">Do not select an interpretation from photographs or visual resemblance.</text>']
    patterns = [('19 mm square hypothesis', [(x, y) for x in (-9.5, 9.5) for y in (-9.5, 9.5)]),
                ('19 mm opposite-span hypothesis', [(-9.5, 0), (0, -9.5), (9.5, 0), (0, 9.5)])]
    for (label, points), cx in zip(patterns, (55, 150)):
        cy = 100
        body += [f'<text x="{cx}" y="78" text-anchor="middle" font-size="3.4">{label}</text>',
                 f'<g transform="translate({cx} {cy})" stroke="#666" stroke-width=".2" fill="none">',
                 '<path d="M-22 0H22 M0 -22V22"/>', '<circle r="18.55" stroke-dasharray="1 1"/>']
        for x, y in points:
            body.append(f'<circle cx="{x}" cy="{y}" r="1.5"/><path d="M{x-2} {y}h4 M{x} {y-2}v4"/>')
        body += ['</g>', f'<text x="{cx}" y="130" text-anchor="middle" font-size="3.2">Circle: seller nominal Ø37.1 mm only</text>']
    body += ['<text x="15" y="145" font-size="3.8">Datum: mounting face z=0, shaft +z, +x toward lead exit.</text>',
             '<text x="15" y="154" font-size="3.8">Record x/y coordinates, thread pitch/hand and usable depth separately.</text>',
             '<text x="15" y="168" font-size="4">Sample ID: __________________  Date / operator: __________________</text>',
             '<text x="15" y="180" font-size="4">Instrument / uncertainty: _______________________________________</text>',
             '<text x="15" y="192" font-size="4">Photos / notes: ________________________________________________</text>',
             '<text x="15" y="212" font-size="3.6">No motor power, no forced fit, no screw-depth probe into windings.</text>',
             '<text x="15" y="221" font-size="3.6">A completed survey still needs design review and separate physical acceptance.</text>',
             '<path d="M20 255h100 M20 252v6 M120 252v6 M180 170v100 M177 170h6 M177 270h6"',
             ' stroke="#111" stroke-width=".3" fill="none"/>',
             '<text x="70" y="250" text-anchor="middle" font-size="4">100 mm horizontal</text>',
             '<text transform="translate(189 220) rotate(-90)" text-anchor="middle" font-size="4">100 mm vertical</text>',
             '</g></svg>']
    return '\n'.join(body) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    acquire_cmd = commands.add_parser('acquire')
    acquire_cmd.add_argument('--html', type=Path, required=True)
    acquire_cmd.add_argument('--observed', required=True)
    acquire_cmd.add_argument('--out', type=Path, required=True)
    for command in ('template', 'sheet'):
        sub = commands.add_parser(command)
        sub.add_argument('--out', type=Path, required=True)
    check = commands.add_parser('check')
    check.add_argument('survey', type=Path)
    check.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'acquire':
        write_json(args.out, acquire(args.html, args.observed))
    elif args.command == 'template':
        write_json(args.out, template())
    elif args.command == 'sheet':
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(survey_sheet())
    else:
        result = survey_verdict(json.loads(args.survey.read_text()), args.survey.parent, args.survey)
        write_json(args.out, result)
        print(json.dumps({'survey_complete': result['survey_complete'], 'counts': result['counts'],
                          'physical_fit_verified': False, 'report': str(args.out)}))
        return 0 if result['pass'] else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
