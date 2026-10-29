"""Check the dated carrier audit against its frozen Git sources, without importing CAD.

Run from repository root. The source commit must be fetched (PR #67 history).
This checks evidence coverage/identity, not current supplier stock or engineering safety.
"""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

path = Path(sys.argv[1] if len(sys.argv) > 1 else
            'research/supply/turret-carrier-2026-10-29.json')
audit = json.loads(path.read_text())
source = audit['source_commit']
assert len(source) == 40 and all(c in '0123456789abcdef' for c in source)
files = {}
for binding in audit['source_bindings']:
    name = binding['path']
    assert name not in files, f'duplicate source {name}'
    data = subprocess.check_output(['git', 'show', f'{source}:{name}'])
    assert hashlib.sha256(data).hexdigest() == binding['sha256'], name
    blob = subprocess.check_output(['git', 'rev-parse', f'{source}:{name}'], text=True).strip()
    assert blob == binding['git_blob'], name
    files[name] = data
rows = audit['rows']
by_key = {row['key']: row for row in rows}
assert len(by_key) == len(rows), 'duplicate catalog key'
for row in rows:
    assert row['observed_on'] == audit['observed_on']
    assert row['supplier_url'].startswith('https://')
    assert row['notes'] is not None
    count, status = row['stock_quantity'], row['stock_status']
    assert status in {'listed_in_stock', 'unverified', 'no_stock', 'rationed_backorders_allowed'}
    if status == 'no_stock':
        assert count == 0
    elif status == 'listed_in_stock':
        assert count is None or count > 0
    else:
        assert count is None, 'unknown stock must not become a zero/count'
    if 'required_length_m' in row:
        assert abs(row['cut_length_m'] - row['required_length_m'] *
                   (1 + row['cut_allowance_fraction'])) < 1e-10
    assert row['required_quantity'] is None or row['required_quantity'] > 0

# Read just literal component tuples, never execute CAD imports or module code.
tree = ast.parse(files['cad/turret_boards.py'])
constants = {n.targets[0].id: n.value.value for n in tree.body
             if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
             and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)}
components = next(n.value for n in tree.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'COMPONENTS' for t in n.targets))
expected = {}
for node in ast.walk(components):
    if not isinstance(node, ast.Tuple) or len(node.elts) != 5:
        continue
    if not isinstance(node.elts[1], ast.Constant) or node.elts[1].value not in {'base', 'harness'}:
        continue
    # Other harness components D7 (Feather USB) and C23 (hall sensor) are outside this carrier.
    if node.elts[1].value == 'harness' and ast.literal_eval(node.elts[0]) not in {'F4', 'D8', 'D14'}:
        continue
    key_node = node.elts[3]
    if isinstance(key_node, ast.Constant):
        key = ast.literal_eval(key_node)
    else:
        assert isinstance(key_node, ast.Call) and isinstance(key_node.func, ast.Attribute)
        assert key_node.func.attr == 'format' and isinstance(key_node.func.value, ast.Name)
        key = constants[key_node.func.value.id].format(*(ast.literal_eval(v) for v in key_node.args))
    expected[ast.literal_eval(node.elts[0])] = key
actual = {d: row['key'] for row in rows for d in row.get('designators', [])}
assert sum(len(row.get('designators', [])) for row in rows) == len(actual), 'duplicate designator'
assert actual == expected, (actual, expected)
assert len(expected) == 13, 'carrier scope changed; review the audit rather than silently extending it'
for d, key in expected.items():
    assert by_key[key]['required_quantity'] == 1, d

# Explicit non-circuit boundary of this dated audit, agreed with the carrier owner.
# Changing the current design does not silently rewrite this historical snapshot.
non_circuit = {
    'screw_m3x6': 4, 'turret_screw_m3x8': 4, 'insert_m3': 8,
    'fuse_mini58_10a': 1, 'littelfuse-0fhm0001zxj': 1,
    'molex-43020-1200': 1, 'molex-43031-0001': 12,
    'molex-43025-1200': 1, 'molex-43030-0010': 12,
    'te-dt04-12pa-l012': 1, 'te-w12p': 1, 'te-0460-202-16141': 12,
    'proto-board-52x50': 1, 'pololu-ul1007-24awg-60ft': None,
    'remington-18ptfestr-25ft': None, 'pa6-cf': None,
}
assert set(by_key) == set(expected.values()) | set(non_circuit), 'incomplete or expanded scoped rows'
for key, quantity in non_circuit.items():
    assert by_key[key]['required_quantity'] == quantity, key

# Cross-check all keys against the catalog files bound above (including nested sourcing).
def catalog_keys(value):
    if isinstance(value, dict):
        if isinstance(value.get('key'), str):
            yield value['key']
        for item in value.values():
            yield from catalog_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from catalog_keys(item)
keys = set()
for name, data in files.items():
    if name.startswith('catalog/'):
        value = json.loads(data)
        keys.update(catalog_keys(value))
        if name.endswith('materials.json'):
            keys.update(value)
assert set(by_key) <= keys, f'unknown catalog keys: {set(by_key) - keys}'
assert sum(row['required_quantity'] for row in rows if row['group'] == 'carrier_hardware') == 16
assert all(candidate['selected'] is False for candidate in audit['correction_candidates'])
print(f'PASS: {len(files)} frozen source hashes, {len(rows)} unique catalog keys, '
      f'{len(expected)} circuit designators, 16 mounting instances, wire arithmetic; no build qualification')
