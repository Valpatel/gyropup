"""Architecture arithmetic only. No native circuit, waveform, thermal or fit approval."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CANDIDATE = ROOT / 'hardware/carrier-pan-protection'
sys.path.insert(0, str(CANDIDATE))
spec = importlib.util.spec_from_file_location('reviewed_pan_calculation', CANDIDATE / 'calculate.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
INPUT = HERE / 'carrier-practical-architecture.inputs.json'
OUTPUT = HERE / 'carrier-practical-architecture.results.json'


def positive(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError('positive finite number required')
    return value


def compare(data):
    a, c, m = data['design_assumptions'], data['contract'], data['manufacturer_values']
    if c != {'steady_sources_V': [[15, 20.5], [30, 42]], 'servo_nominal_V': 12,
             'screen_output_A': 3.25, 'raw_reverse_V': -42, 'charged_front_output_V': 55}:
        raise ValueError('source/servo contract changed: requires a new reviewed comparison')
    expected_gaps = {'architecture_selected', 'native_circuit_transcribed', 'charged_reverse_waveform',
                     'clamp_temperature_pulse', 'startup_gate_bodydiode', 'thermal', 'carrier_fit',
                     'output_regeneration', 'production_supply'}
    if set(data['qualifications']) != expected_gaps or any(value is not False for value in data['qualifications'].values()):
        raise ValueError('this comparison cannot claim qualification')
    b = baseline.static_screen()
    r = positive(a['front_FET_hot_ohm'])
    ambient = a['ambient_screen_C']
    target = a['FET_junction_target_C']
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (ambient, target)) or target <= ambient:
        raise ValueError('invalid thermal scenario')
    # Same conservative enabled-load current and onset budget as candidate B;
    # only the already-enhanced series element is exchanged here.
    load = b['startup_load_input_A']
    budget_current = b['input_trip_A']['forward_startup_at_Vout_0'][0]
    gain = b['assumptions']['D1_forward_drop_max_V'] - budget_current * r
    loss = load**2 * r
    theta_required = (target - ambient) / loss
    voltage = c['charged_front_output_V'] - c['raw_reverse_V']
    rec = m['RP60Q-11012SRUWB/P']
    if rec['input_min_V'] != 14 or rec['UVLO_on_max_V'] != 14:
        raise ValueError('exact B/P module 14 V specification changed; do not substitute the older variant')
    accuracy = sum(positive(rec[k]) for k in ('set_fraction', 'line_fraction', 'load_fraction'))
    accuracy += positive(rec['temperature_fraction_per_K']) * positive(rec['temperature_delta_K'])
    vout = positive(rec['output_V']) * (1 + accuracy)
    pout = vout * c['screen_output_A']
    thermal = []
    for eta in a['converter_efficiency_scenarios']:
        if positive(eta) >= 1:
            raise ValueError('efficiency scenario must be below unity')
        dissipated = pout * (1 / eta - 1)
        required = (rec['baseplate_max_C'] - ambient) / dissipated
        thermal.append({'efficiency_assumption': eta, 'loss_W': dissipated,
                        'required_theta_at_ambient_C_per_W': required,
                        'ambient_ceiling_with_datasheet_6_3K_per_W_C': rec['baseplate_max_C'] - dissipated * rec['theta_no_heatsink_C_per_W'],
                        'stock_thermal_condition_satisfies_scenario': required >= rec['theta_no_heatsink_C_per_W']})
    return {
        'status': 'ARCHITECTURE_RECOMMENDATION_ONLY_UNSELECTED_UNQUALIFIED',
        'baseline_candidate_B': {'15V_enable_margin_V': b['15V_enable_margin_V'],
                                 'series_loss_W': b['D1_steady_loss_screen_W'],
                                 'load_input_A': load, 'startup_budget_current_A': budget_current},
        'enhanced_low_loss_direction': {
            'front_hot_resistance_is_assumption_ohm': r,
            '15V_enable_margin_after_gate_enhancement_V': b['15V_enable_margin_V'] + gain,
            'front_loss_screen_W': loss, 'theta_required_C_per_W': theta_required,
            '6cm2_copper_condition_satisfies_scenario': m['IPB200N25N3G']['theta_JA_6cm2_C_per_W'] <= theta_required,
            'minimal_footprint_condition_satisfies_scenario': m['IPB200N25N3G']['theta_JA_minimal_footprint_C_per_W'] <= theta_required,
            'power_FET_VDS_static_margin_V': m['IPB200N25N3G']['VDS_V'] - voltage,
            'startup_before_gate_enhancement': None, 'actual_charged_reverse_pin_peaks': None,
            'clamp_energy_and_temperature_margin': None, 'assembled_thermal_result': None},
        'raw_charged_reverse_stress_V': voltage,
        'bare_controller_rejection': {
            'LTC4359_raw_IN_absolute_margin_V': c['raw_reverse_V'] - m['LTC4359']['raw_IN_min_V'],
            'LM7480_differential_margin_V': m['LM7480']['C_minus_A_absolute_V'] - voltage,
            'LM74910H_differential_margin_V': m['LM74910H']['C_minus_A_absolute_V'] - voltage},
        'larger_converter_direction': {
            'mpn': 'RP60Q-11012SRUWB/P', 'output_corner_V': vout,
            'output_screen_W': pout, 'power_margin_W': rec['power_W'] - pout,
            'body_plan_area_ratio_to_legacy_board': rec['body_mm'][0] * rec['body_mm'][1] / (a['legacy_board_mm'][0] * a['legacy_board_mm'][1]),
            '15V_input_headroom_before_all_path_drops_V': 15 - rec['input_min_V'],
            'OVP_range_V': [rec['output_V'] * f for f in rec['OVP_fraction']],
            'thermal_scenarios': thermal,
            'startup_with_selected_front_end': None, 'reverse_input_protection': None,
            'actual_15V_efficiency': None, 'output_regeneration': None},
        'qualifications': data['qualifications']}


def artifact():
    data = json.loads(INPUT.read_text())
    bindings = [INPUT, Path(__file__), HERE / 'carrier-practical-architecture.md',
                HERE / 'test_practical_architecture.py', CANDIDATE / 'calculate.py', CANDIDATE / 'circuit_design.py']
    return {'inputs_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in bindings},
            'comparison': compare(data)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    content = json.dumps(artifact(), indent=2, sort_keys=True, allow_nan=False) + '\n'
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text() != content:
            raise SystemExit('stale architecture receipt; regenerate and review')
        print('Architecture receipt current; qualification remains false.')
    else:
        OUTPUT.write_text(content)
        print(OUTPUT.relative_to(ROOT))
