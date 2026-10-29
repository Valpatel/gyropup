"""Validate the bounded inventory/reference checkpoint; never emits fit readiness."""
import copy
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('packaging_inventory', HERE / 'inventory.py')
I = importlib.util.module_from_spec(spec)
spec.loader.exec_module(I)
spec = importlib.util.spec_from_file_location('packaging_allocation', HERE / 'allocation.py')
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)


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
    candidate = document['packaging_candidates']['I.COUT']
    if (candidate['mpn'], candidate['selected_mpn'], candidate['capacitance_nf'],
        candidate['rated_voltage_v'], candidate['tolerance_percent'], candidate['dielectric'], candidate['qualification']) != (
            'C1206C473F1GECAUTO', None, 47, 100, 1, 'C0G', False):
        raise ValueError('COUT unselected packaging identity/limits changed')
    return {'reference_items':len(pins), 'electrically_qualified':False}


def validate_package_limits(document):
    p = document['packages']
    fuse = p['bourns_mfr300']
    if (fuse['maximum_body_mm'] is not None or fuse['formed_flat_envelope_mm'] is not None
            or fuse['maximum_coated_span_mm'] != {'width_A':12,'top_to_coating_end_B':18.3,'thickness_E':3}
            or fuse['bare_lead_length_min_mm'] != 7.6):
        raise ValueError('MF-R300 coating span/minimum lead is not a body/formed maximum')
    tvs = p['littelfuse_smcj150a']
    if (tvs['maximum_body_mm'] != [8.13,6.22,2.62] or tvs['land_outer_mm'] is not None
            or tvs['land_constraints_mm'] != {'pad_width_min':3.3,'each_pad_length_min':2.4,'inner_gap_max':4.2}):
        raise ValueError('SMCJ height uses axisD; mixed pad limits do not give a maximum land envelope')
    diode = p['diodes_s1b']
    if diode['maximum_body_mm'] != [5.59,2.92,2.4] or diode['minimum_body_land_union_mm'] != [6.5,2.92]:
        raise ValueError('exact S1B SMA revision/body-plus-land envelope changed')
    cap = p['tdk_fg24']
    if (cap['maximum_body_mm'] is not None or cap['complete_installed_envelope_mm'] is not None
            or cap['incoming_pitch_range_mm'] != [4,6]
            or cap['older_individual_sheet_text_pitch_range_mm'] != [4.8,5.8]
            or cap['top_to_formed_lead_datum_max_mm'] != 5.5):
        raise ValueError('TDK formed-lead datum/revision-specific pitch is not a complete body bound')
    return {'exact_package_axis_controls':4}


def validate_allocation(document):
    if document != A.allocation():
        raise ValueError('paper assignment differs from current exact sources and declared candidate')
    boards = _unique_rows(document['assemblies'], 'assembly')
    if set(boards) != {'CONTROL_TERMINATION','PAN_POWER'}:
        raise ValueError('two explicit assemblies required')
    assigned = [ref for row in boards.values() for ref in row['electronic_members']]
    inventory = I.inventory()
    expected = {r['id'] for r in inventory['rows']}
    if len(assigned) != len(set(assigned)) or set(assigned) != expected:
        raise ValueError('every electronic item must be assigned exactly once')
    if set(boards['CONTROL_TERMINATION']['electronic_members']) != {r for r in expected if r.startswith('L.')}:
        raise ValueError('legacy control assignment must be explicit')
    controls = _unique_rows(boards['CONTROL_TERMINATION']['wire_pad_candidates'], 'control pad')
    power = _unique_rows(boards['PAN_POWER']['wire_pad_candidates'], 'power pad')
    if len(controls) != 19 or len(power) != 4:
        raise ValueError('physical pad candidates must account for bypasses and four interboard wires')
    for pin in ('BUS_IN','GND_IN','12V_OUT','GND_OUT'):
        if controls['CTRL.POWER.'+pin]['net'] != power['POWER.'+pin]['net']:
            raise ValueError('interboard endpoint nets differ')
    cap = document['height_screens']['capacitor']
    cap_margin = cap['available_top_z_mm']-cap['pcb_top_z_mm']-cap['body_max_mm']-cap['vent_free_min_mm']
    module = document['height_screens']['converter']
    module_top = module['candidate_module_pcb_bottom_z_mm']+module['nominal_module_pcb_mm']+module['nominal_top_parts_mm']
    lower_gap = module['candidate_module_pcb_bottom_z_mm']-module['nominal_bottom_parts_mm']-module['base_pcb_top_z_mm']-module['candidate_under_module_part_height_max_mm']
    if cap['qualified'] is not False or module['qualified'] is not False:
        raise ValueError('unknown stack tolerances cannot produce qualification')
    return {'paper_assigned_electronics':len(assigned),'control_wire_pad_candidates':len(controls),
            'power_wire_pad_candidates':len(power),'cap_margin_before_unknown_allowances_mm':round(cap_margin,6),
            'module_nominal_top_z_mm':round(module_top,6),'module_nominal_under_clearance_mm':round(lower_gap,6),
            'physical_allocation_qualified':False}


def _unique_rows(rows, label):
    result = {}
    for row in rows:
        key = row['id']
        if key in result:
            raise ValueError(f'duplicate {label}: {key}')
        result[key] = row
    return result


def validate_terminals(document):
    # Independent source contract, not a count derived from whichever rows remain.
    expected_interfaces = {
        'C2-P.module': {'+':'BUS_HEAD_FUSED', '-':'GND'},
        'C2-S.module': {'1':'CAN_H', '2':'CAN_L', '3':'SAFETY_A', '4':'SAFETY_B'},
        'C3.module': {'1':'BUS_HEAD_FUSED', '2':'BUS_HEAD_FUSED', '3':'GND', '4':'GND',
                      '5':'CAN_H', '6':'CAN_L', '7':'SAFETY_PULSE', '8':'GND',
                      '9':'PAN_TTL', '10':'GND', '11':'BUS_HEAD_FUSED', '12':'GND'},
        'C3.fixed': {},  # Existing mate/contact identity; not additional carrier terminals.
        'PAN.servo': {'datasheet1':'GND', 'datasheet2':'SERVO_12V_AFTER_F1', 'datasheet3':'PAN_TTL'},
    }
    interfaces = _unique_rows(document['existing_interfaces'], 'interface')
    if {k:v.get('pins', {}) for k,v in interfaces.items()} != expected_interfaces:
        raise ValueError('exact interface IDs, pin sets and nets are required')
    expected_legacy = {
        'L.U1': {'1':'GND','2':'TIMING','3':'OSC_OUT','4':'SAFETY_B','5':'CTRL','6':'TIMING','7':'DISCHARGE','8':'SAFETY_B'},
        'L.R1': {'1':'SAFETY_B','2':'DISCHARGE'},
        'L.R2': {'1':'DISCHARGE','2':'TIMING'},
        'L.C1': {'1':'TIMING','2':'GND'}, 'L.C2': {'1':'CTRL','2':'GND'},
        'L.C3': {'1':'SAFETY_B','2':'GND'},
        'L.D1': {'A':'OSC_OUT','K':'PULSE_LIMIT_IN'},
        'L.R3': {'1':'PULSE_LIMIT_IN','2':'SAFETY_PULSE'},
        'L.F1': {'1':'12V_PAN','2':'SERVO_12V_AFTER_F1'},
    }
    if document['legacy_control_pins'] != expected_legacy:
        raise ValueError('legacy control component/pin/net contract changed')
    adjacent = _unique_rows(document['adjacent_protection'], 'adjacent protection')
    expected_adjacent = {
        'H.F4': {'1':'12V_PAN','2':'SAFETY_A'},
        'H.D8': {'A':'GND','K':'BUS_HEAD_FUSED'},
        'H.D14': {'A':'GND','K':'BUS_HEAD_FUSED'}, 'HEAD_FUSE_HOLDER': {},
    }
    if {k:v.get('pins', {}) for k,v in adjacent.items()} != expected_adjacent:
        raise ValueError('adjacent protection identities/pins/nets changed')
    proposal = document['protection_external_terminal_proposal']
    expected_ports = {'BUS_IN':'BUS_HEAD_FUSED', 'GND':'GND', '12V_OUT':'12V_PAN'}
    if proposal['ports'] != list(expected_ports) or proposal['port_nets'] != expected_ports:
        raise ValueError('protection external port contract changed')
    # Logical boundaries do not allocate a physical pad or splice.
    endpoints = {'LEGACY.GND':'GND'}
    for group in (expected_interfaces, expected_legacy, expected_adjacent, {'PROTECTION':expected_ports}):
        for component,pins in group.items():
            for pin,net in pins.items():
                key = component + '.' + pin
                if key in endpoints:
                    raise ValueError('duplicate endpoint: ' + key)
                endpoints[key] = net
    expected_bypasses = [
        ['C2-S.module.1','C3.module.5','CAN_H'],
        ['C2-S.module.2','C3.module.6','CAN_L'],
        ['C3.module.9','PAN.servo.datasheet3','PAN_TTL'],
    ]
    if sorted(document['continuous_bypasses']) != sorted(expected_bypasses):
        raise ValueError('exact unique CAN/TTL bypasses required')
    for a,b,net in document['continuous_bypasses']:
        if endpoints.get(a) != net or endpoints.get(b) != net:
            raise ValueError('bypass endpoint missing or on different net')
    expected_junctions = {
        'J_BUS': ('BUS_HEAD_FUSED', ['C2-P.module.+','C3.module.1','C3.module.2','C3.module.11',
                                    'PROTECTION.BUS_IN','H.D8.K','H.D14.K']),
        'J_RETURN': ('GND', ['C2-P.module.-','C3.module.3','C3.module.4','C3.module.8',
                            'C3.module.10','C3.module.12','PROTECTION.GND','LEGACY.GND',
                            'PAN.servo.datasheet1','H.D8.A','H.D14.A']),
        'J_12V': ('12V_PAN', ['PROTECTION.12V_OUT','L.F1.1','H.F4.1']),
    }
    junctions = _unique_rows(document['junctions'], 'junction')
    if set(junctions) != set(expected_junctions):
        raise ValueError('exact junction identity set required')
    for name,(net,members) in expected_junctions.items():
        row = junctions[name]
        if row['net'] != net or sorted(row['logical_members']) != sorted(members):
            raise ValueError('exact unique junction members and net required: ' + name)
        if any(endpoints.get(member) != net for member in row['logical_members']):
            raise ValueError('junction endpoint missing or on different net')
        if row['hardware'] is not None or row['position'] is not None:
            raise ValueError('junction physical allocation requires a reviewed contract revision')
    count = sum(len(pins) for pins in expected_interfaces.values())
    counts = document['physical_end_count']
    if {k:v for k,v in counts.items() if k != 'note'} != {
            'C2_module':6, 'C3_module':12, 'servo':3, 'total_external_positions':count}:
        raise ValueError('external position count does not match complete interface contract')
    fixed = interfaces['C3.fixed']
    if (fixed['contacts'], fixed['wire_awg'], fixed['contact_awg_range'], fixed['contact_max_insulation_od_mm']) != (
            '12x43030-0010', 28, [26,30], 1.27):
        raise ValueError('original ring contact/lead variant changed without source qualification')
    for name,contact in [('C2-S.module','4x43031-0001'), ('C3.module','12x43031-0001')]:
        if interfaces[name]['contacts'] != contact or interfaces[name]['wire_awg'] != 24:
            raise ValueError('module contact/lead variant changed without source qualification')
    if document['frozen'] is not False or document['all_terminals_allocated'] is not False:
        raise ValueError('logical endpoints cannot claim physical termination readiness')
    for key in ('mount_zone','pad_geometry','terminal_type','wire_strain_relief'):
        if proposal[key] is not None:
            raise ValueError('protection physical allocation requires a reviewed contract revision')
    for wire in document['wire_candidates_not_selected']:
        calculated = max(wire['od_in']) * 25.4 * wire['published_bend_multiple']
        if abs(calculated-wire['derived_radius_at_max_od_mm']) > 1e-9:
            raise ValueError('wire-specific bend arithmetic changed')
    return {'external_positions':count,'all_terminals_allocated':False}


if __name__ == '__main__':
    result = validate_inventory(json.loads((HERE / 'component-inventory.json').read_text()))
    result.update(validate_reference(json.loads((HERE / 'front-reference-contract.json').read_text())))
    result.update(validate_allocation(json.loads((HERE / 'allocation-proposal.json').read_text())))
    result.update(validate_package_limits(json.loads((HERE / 'package-envelopes.json').read_text())))
    result.update(validate_terminals(json.loads((HERE / 'terminal-contract.json').read_text())))
    print(json.dumps(result, indent=2, sort_keys=True))
