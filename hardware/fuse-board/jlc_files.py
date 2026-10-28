"""JLCPCB's assembly files from KiCad's BOM and position exports (build.sh runs this):

    python3 jlc_files.py BOM.csv POS.csv fab/bom-jlcpcb.csv fab/cpl-jlcpcb.csv

The BOM keeps the parts that are in the placement file (top-side SMD, not DNP) and carry an LCSC number, in JLCPCB's
columns (Comment, Designator, Footprint, LCSC Part #); the CPL is Designator, Mid X, Mid Y, Layer, Rotation. Check the
rotations in JLCPCB's placement preview before paying (the shunt, the 2512 and the GH connector especially).
"""
from __future__ import annotations

import csv
import sys


def main(bom_in, pos_in, bom_out, cpl_out):
    with open(pos_in, newline='') as f:
        pos = list(csv.DictReader(f))
    placed = {p['Ref'] for p in pos}
    rows = []
    with open(bom_in, newline='') as f:
        for r in csv.DictReader(f):
            refs = [x.strip() for x in r['Designator'].split(',') if x.strip() in placed]
            if refs and r.get('LCSC', '').strip():
                rows.append({'Comment': r['Comment'], 'Designator': ','.join(refs), 'Footprint': r['Footprint'].split(':')[-1],
                             'LCSC Part #': r['LCSC'].strip()})
    missing = placed - {x for r in rows for x in r['Designator'].split(',')}
    if missing:
        raise SystemExit(f'placed parts with no LCSC number: {sorted(missing)}')
    with open(bom_out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        w.writeheader()
        w.writerows(rows)
    with open(cpl_out, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for p in sorted(pos, key=lambda p: p['Ref']):
            w.writerow([p['Ref'], f"{float(p['PosX']):.3f}mm", f"{float(p['PosY']):.3f}mm",
                        'Top' if p['Side'].lower().startswith('top') else 'Bottom', f"{float(p['Rot']):.1f}"])
    print(f'{bom_out}: {len(rows)} lines; {cpl_out}: {len(pos)} parts')


if __name__ == '__main__':
    main(*sys.argv[1:5])
