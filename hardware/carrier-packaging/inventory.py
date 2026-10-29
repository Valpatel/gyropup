"""Enumerate packaging candidates without importing CAD or generating a circuit/layout."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CIRCUIT = ROOT / 'hardware/carrier-pan-protection/circuit_design.py'
BOARDS = ROOT / 'cad/turret_boards.py'
CATALOG = ROOT / 'catalog/turret.json'
SPEC = importlib.util.spec_from_file_location('retained_pan_candidate', CIRCUIT)
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)

# Figure10 labels are namespaced I.* so no legacy designator is silently reused.
# This is an inventory, NOT an inferred or connected circuit. Exact pin/net
# transcription is separately bound to actual manufacturer pixels and pin drawings.
FRONT = [
    ('U1', 'LTC4359IDCB#TRPBF', 'ideal diode controller', 'DFN6 DCB with exposed pad'),
    ('Q1', 'IPB200N25N3GATMA1', '250V N-MOS', 'PG-TO263-3'),
    ('D1', 'SMAT70A-13-F', '70V TVS', 'SMA'),
    ('D2', 'MMSZ5231B-7-F', '5.1V zener', 'SOD123'),
    ('D3', 'BZG03C75-M3_A-08', '75V zener; modern grade equivalence open', 'SMA'),
    ('D4', 'DDZ9699T-7', '12V gate zener; supply not confirmed', 'SOD523'),
    ('D5', 'S1B-13-F', 'floating-reference return diode', 'SMA'),
    ('D6', 'SMCJ150A', '150V TVS, Littelfuse candidate manufacturer', 'SMC'),
    ('R2', 'CRCW12062K00FKEAHP', '2kohm pulse resistor candidate; pulse acceptance open', '1206'),
    ('COUT', None, '47nF reference capacitor; exact voltage/MPN pending topology check', None),
]


def inventory():
    rows = []
    for ref, part in D.PARTS.items():
        if ref.startswith('#') or ref == 'D1':
            continue
        rows.append({'id': 'P.' + ref, 'group': 'retained_cutoff_converter', 'mpn': part['mpn'],
                     'value': part['value'], 'source': str(CIRCUIT.relative_to(ROOT)),
                     'pins_from_reviewed_candidate': part['pins'], 'datasheet': part['datasheet'],
                     'prior_candidate_footprint': part['footprint'] or None,
                     'placement': None, 'maximum_envelope': None})
    for ref, mpn, value, package in FRONT:
        rows.append({'id': 'I.' + ref, 'group': 'complete_ideal_diode_reference_inventory',
                     'mpn': mpn, 'value': value, 'package': package,
                     'source': 'https://www.analog.com/media/en/technical-documentation/data-sheets/ltc4359.pdf#page=12',
                     'pins_from_reviewed_candidate': None, 'placement': None, 'maximum_envelope': None})
    front_contract = json.loads((HERE / 'front-reference-contract.json').read_text())
    packages = json.loads((HERE / 'package-envelopes.json').read_text())['packages']
    catalog = {r.get('key', r.get('id')): r for r in json.loads(CATALOG.read_text())}
    tree = ast.parse(BOARDS.read_text())
    assignment = next(n for n in tree.body if isinstance(n, ast.Assign) and
                      any(isinstance(t, ast.Name) and t.id == 'COMPONENTS' for t in n.targets))
    def literal_rows(node):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            yield from literal_rows(node.left)
            yield from literal_rows(node.right)
        elif isinstance(node, ast.List):
            yield from node.elts
        elif isinstance(node, ast.ListComp):
            # Generated cartridge rows are out of scope; refuse any new generated
            # base/harness expression rather than silently omit it.
            if not isinstance(node.elt, ast.Tuple) or len(node.elt.elts) < 2:
                raise ValueError('unreviewed generated board row')
            if ast.literal_eval(node.elt.elts[1]) != 'cartridge':
                raise ValueError('generated non-cartridge rows require inventory review')
        else:
            raise ValueError('unreviewed component list expression')

    for node in literal_rows(assignment.value):
        if not isinstance(node, ast.Tuple):
            raise ValueError('unexpected board component source')
        ref, board, value = (ast.literal_eval(n) for n in node.elts[:3])
        if board != 'base' or ref == 'U2':
            continue
        keynode = node.elts[3]
        if isinstance(keynode, ast.Constant):
            key = keynode.value
        elif isinstance(keynode, ast.Call) and isinstance(keynode.func, ast.Attribute) and isinstance(keynode.func.value, ast.Name) and keynode.func.value.id == 'R14W' and keynode.func.attr == 'format':
            key = 'yageo-mfr-25fbf52-' + ast.literal_eval(keynode.args[0])
        else:
            raise ValueError('unreviewed catalog key expression')
        part = catalog[key]
        rows.append({'id': 'L.' + ref, 'group': 'retained_legacy_control_board', 'mpn': part['model'],
                     'value': value, 'catalog_key': key, 'source': str(BOARDS.relative_to(ROOT)),
                     'prior_sources': part.get('sources', []), 'placement': 'existing envelope only; exact leads/pads not established',
                     'maximum_envelope': None})
    for row in rows:
        if row['id'].startswith('I.'):
            row['reference_pin_contract'] = front_contract['component_pins'][row['id']]
        matches = [(name, data) for name, data in packages.items()
                   if row['mpn'] in data.get('match', []) or
                   (data.get('prefix') and (row['mpn'] or '').startswith(data['prefix']))]
        if len(matches) > 1:
            raise ValueError('ambiguous exact package match: ' + row['id'])
        if matches:
            row['package_evidence_id'], row['maximum_envelope'] = matches[0]

    retained_offers = json.loads((ROOT / 'hardware/carrier-pan-protection/availability.json').read_text())
    front_offers = json.loads((ROOT / 'research/protection/carrier-practical-architecture.inputs.json').read_text())
    for row in rows:
        row['supplier_observation'] = None
        source = ('hardware/carrier-pan-protection/availability.json' if row['id'].startswith('P.')
                  else 'research/protection/carrier-practical-architecture.inputs.json')
        if row['id'].startswith('P.'):
            matches = [(n, offer) for n, offer in enumerate(retained_offers['rows']) if offer['mpn'] == row['mpn']]
            if matches:
                row['supplier_observation'] = {'source': source, 'row_index': matches[0][0],
                    'observed_on': retained_offers['observed_date'], 'readiness': False,
                    'limit': 'Carry-forward dated observation only; see exact stock/pack/lead caveats at source.'}
        elif row['id'].startswith('I.'):
            matches = [(n, offer) for n, offer in enumerate(front_offers['supplier_observations']) if offer[0] == row['mpn']]
            if matches:
                row['supplier_observation'] = {'source': source, 'row_index': matches[0][0],
                    'observed_on': front_offers['observed_on'], 'readiness': False,
                    'limit': 'Carry-forward dated observation only; DDZ9699T scarce/unconfirmed, modern clamp equivalence and pulse qualification open.'}

    if len([r for r in rows if r['group'] == 'retained_cutoff_converter']) != 28:
        raise ValueError('retained protection inventory changed; review new complete scope')
    if len([r for r in rows if r['group'] == 'retained_legacy_control_board']) != 9:
        raise ValueError('retained legacy control inventory changed; review scope')
    return {'status': 'WIP_INVENTORY_NOT_A_FROZEN_LAYOUT',
            'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (Path(__file__), CIRCUIT, BOARDS, CATALOG, HERE / 'front-reference-contract.json', HERE / 'package-envelopes.json', HERE / 'primary-envelope-sources.json', HERE / 'terminal-contract.json', ROOT / 'docs/base-board-interfaces.md', ROOT / 'docs/carrier-service-connectors.md', ROOT / 'hardware/carrier-pan-protection/pins.md', ROOT / 'hardware/carrier-pan-protection/availability.json', ROOT / 'research/protection/carrier-practical-architecture.inputs.json')},
            'inventory_count': len(rows), 'rows': rows,
            'package_evidence_count': sum(r['maximum_envelope'] is not None for r in rows),
            'excluded_replaced_parts': ['P.D1: V10P20 series barrier replaced by complete I.* inventory',
                                        'L.U2: old D36V50F12 replaced functionally by P.U2 D42V55F12'],
            'remaining_physical_inventory': ['external F4, D8, D14 and exact upstream fuse/holder boundary',
                                            'C2/C3/servo housings, contacts, crimps and actual leads',
                                            'BUS and GND junction hardware and every solder/PCB terminal',
                                            'mounting/retention, insulation, heat path and strain relief'],
            'frozen': False, 'complete_physical_inventory': False, 'fit_qualified': False}


if __name__ == '__main__':
    p = HERE / 'component-inventory.json'
    p.write_text(json.dumps(inventory(), indent=2, sort_keys=True) + '\n')
    print('Packaging inventory:', inventory()['inventory_count'], 'electronic items; physical inventory incomplete.')
