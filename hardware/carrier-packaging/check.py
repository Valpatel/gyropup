"""Validate the bounded inventory/reference checkpoint; never emits fit readiness."""
import copy
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('packaging_inventory', HERE / 'inventory.py')
I = importlib.util.module_from_spec(spec)
spec.loader.exec_module(I)


def validate_inventory(document, expected=None):
    expected = I.inventory() if expected is None else expected
    if document != expected:
        raise ValueError('inventory differs from current complete inputs; regenerate and review')
    if any(document[k] for k in ('frozen', 'complete_physical_inventory', 'fit_qualified')):
        raise ValueError('incomplete checkpoint cannot claim readiness')
    ids = [r['id'] for r in document['rows']]
    if len(ids) != len(set(ids)) or len(ids) != 47:
        raise ValueError('expected 47 unique electronic items')
    if 'P.D1' in ids or 'L.U2' in ids:
        raise ValueError('replaced parts must not survive as duplicate physical hardware')
    return {'electronic_items': len(ids), 'package_evidence_items': document['package_evidence_count'],
            'fit_qualified': False, 'complete_physical_inventory': False}


def validate_reference(document):
    pins = document['component_pins']
    # Independently stated physical/topological conditions from actual RevF Fig10.
    expected = {
        'I.U1': {'1':'FRONT_OUT_SENSE','2':'FRONT_GATE','3':'BUS_HEAD_FUSED','4':'BUS_HEAD_FUSED','5':None,'6':'FLOATING_VSS','7':None},
        'I.Q1': {'1':'FRONT_GATE','2':'VIN_PROTECTED','3':'BUS_HEAD_FUSED'},
        'I.D1': {'K':'BUS_HEAD_FUSED','A':'INPUT_CLAMP_MID'},
        'I.D2': {'K':'FLOATING_VSS','A':'INPUT_CLAMP_MID'},
        'I.D3': {'K':'FRONT_OUT_SENSE','A':'FLOATING_VSS'},
        'I.D4': {'K':'FRONT_GATE','A':'BUS_HEAD_FUSED'},
        'I.D5': {'K':'GND','A':'FLOATING_VSS'},
        'I.D6': {'K':'VIN_PROTECTED','A':'BUS_HEAD_FUSED'},
        'I.R2': {'1':'VIN_PROTECTED','2':'FRONT_OUT_SENSE'},
        'I.COUT': {'1':'FRONT_OUT_SENSE','2':'FLOATING_VSS'},
    }
    if pins != expected:
        raise ValueError('front reference differs from visually checked polarity/pin/net contract')
    if document['reference']['pdf_sha256'] != '8d05e6ba4259028463bbdb751d639715506ef28d1bd5eabac1b012786ea7d970':
        raise ValueError('reference document identity changed; visual re-review required')
    if document['native_circuit_generated'] or document['frozen'] or document['electrically_qualified']:
        raise ValueError('reference transcription is not a qualified new circuit')
    load = document['interfaces']['load_capacitance']
    if load['dedicated_front_capacitor'] is not None:
        raise ValueError('new front capacitor requires a deliberate contract revision')
    return {'reference_items':len(pins), 'electrically_qualified':False}


def validate_terminals(document):
    interfaces = {r['id']:r for r in document['existing_interfaces']}
    for pin in ('1','2','11'):
        if interfaces['C3.module']['pins'][pin] != 'BUS_HEAD_FUSED':
            raise ValueError('C3 must retain raw head BUS, never protected PAN rail')
    count = sum(len(interfaces[k]['pins']) for k in ('C2-P.module','C2-S.module','C3.module','PAN.servo'))
    if count != 21 or document['physical_end_count']['total_external_positions'] != count:
        raise ValueError('external physical positions omitted or duplicated')
    junctions = {r['id']:set(r['logical_members']) for r in document['junctions']}
    if not {'H.D8.K','H.D14.K'} <= junctions['J_BUS'] or not {'H.D8.A','H.D14.A'} <= junctions['J_RETURN']:
        raise ValueError('existing shunt leads must remain in physical-junction obligations')
    fixed = interfaces['C3.fixed']
    if fixed['contacts'] != '12x43030-0010' or fixed['wire_awg'] != 28:
        raise ValueError('original ring contact/lead variant changed without source qualification')
    if not fixed['contact_awg_range'][0] <= fixed['wire_awg'] <= fixed['contact_awg_range'][1]:
        raise ValueError('wire gauge does not meet exact contact range')
    if document['frozen'] or document['all_terminals_allocated']:
        raise ValueError('logical endpoints cannot claim physical termination readiness')
    for wire in document['wire_candidates_not_selected']:
        calculated = max(wire['od_in']) * 25.4 * wire['published_bend_multiple']
        if abs(calculated-wire['derived_radius_at_max_od_mm']) > 1e-9:
            raise ValueError('wire-specific bend arithmetic changed')
    return {'external_positions':count,'all_terminals_allocated':False}


if __name__ == '__main__':
    result = validate_inventory(json.loads((HERE / 'component-inventory.json').read_text()))
    result.update(validate_reference(json.loads((HERE / 'front-reference-contract.json').read_text())))
    result.update(validate_terminals(json.loads((HERE / 'terminal-contract.json').read_text())))
    print(json.dumps(result, indent=2, sort_keys=True))
