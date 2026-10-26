"""Build catalog/materials.json (what the designer and the CAD build use) from the cited filament data in
catalog/fabrication.json.

    python tools/build_materials.py

Each material keeps the source's numbers and adds the designer's fields: a short id, the next step up the ladder,
the highest service temperature (HDT at 1.8 MPa from the vendor TDS), and whether it runs on a stock Bambu P1S
(the stock P1S has a stainless nozzle and an unheated enclosure; carbon-fibre filaments need a hardened nozzle).
"""
from pathlib import Path
import json

R = Path(__file__).resolve().parents[1]

# (id, name in fabrication.json, next rung, P1S needs)
LADDER = [
    ('pla', 'PLA Basic', 'petg', 'stock'),
    ('pla-tough', 'PLA Tough+', 'petg', 'stock'),
    ('petg', 'PETG Basic', 'asa', 'stock'),
    ('asa', 'ASA', 'pet-cf', 'stock'),
    ('pla-cf', 'PLA-CF', 'petg-cf', 'hardened nozzle'),
    ('petg-cf', 'PETG-CF', 'pet-cf', 'hardened nozzle'),
    ('pet-cf', 'PET-CF', 'pa6-cf', 'hardened nozzle'),
    ('pa6-cf', 'PA6-CF', 'paht-cf', 'hardened nozzle'),
    ('paht-cf', 'PAHT-CF', 'ppa-cf', 'hardened nozzle'),
    ('ppa-cf', 'PPA-CF', None, 'heated chamber (not a P1S)'),
    ('tpu95', 'TPU 95A HF', None, 'stock'),
]


def main():
    fab = json.loads((R / 'catalog/fabrication.json').read_text())
    by_name = {f['name']: f for f in fab['filaments'] if f.get('brand') == 'Bambu Lab'}
    out = {}
    for mid, name, nxt, p1s in LADDER:
        f = by_name[name]
        out[mid] = {
            'kind': 'filament', 'name': f'{f["brand"]} {name}',
            'density_g_cm3': f['density_g_cm3'], 'price_usd_per_kg': f['price_usd_per_kg'],
            'tensile_mpa': f['tensile_mpa'], 'tensile_z_mpa': f.get('tensile_z_mpa'),
            'modulus_gpa': f.get('modulus_gpa'), 'flexural_strength_xy_mpa': f.get('flexural_strength_xy_mpa'),
            'max_service_c': f.get('hdt_c'), 'next': nxt, 'p1s': p1s,
            'hardened_nozzle_required': f.get('hardened_nozzle_required'),
            'price_checked': f.get('price_checked'), 'source': f.get('source'),
        }
    for mid, m in out.items():
        if m['next']:
            m['next_name'] = out[m['next']]['name']
    (R / 'catalog/materials.json').write_text(json.dumps(out, indent=1) + '\n')
    print(f'wrote catalog/materials.json: {len(out)} materials')


if __name__ == '__main__':
    main()
