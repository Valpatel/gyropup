"""Bound arithmetic for a design comparison, never a hardware qualification.

Run --write to regenerate the receipt, or --check to compare committed bytes.
All current, thermal and transient assumptions remain explicit in the input file.
"""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
INPUT = HERE / 'carrier-input-protection.inputs.json'
OUTPUT = HERE / 'carrier-input-protection.results.json'


def positive(value, name):
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f'{name} must be finite and positive')
    return value


def energy(capacitance_f, low_v, high_v):
    positive(capacitance_f, 'capacitance')
    if not all(math.isfinite(v) and v >= 0 for v in (low_v, high_v)) or high_v < low_v:
        raise ValueError('capacitor voltage bounds must be finite, nonnegative and increasing')
    return 0.5 * capacitance_f * (high_v**2 - low_v**2)


def power_load(output_v, output_a, input_v, efficiency):
    for name, value in [('output voltage', output_v), ('output current', output_a),
                        ('input voltage', input_v)]:
        positive(value, name)
    if not math.isfinite(efficiency) or not 0 < efficiency <= 1:
        raise ValueError('efficiency must be in (0,1]')
    output_w = output_v * output_a
    input_w = output_w / efficiency
    return {'output_w': output_w, 'input_w': input_w,
            'input_a': input_w / input_v, 'loss_w': input_w - output_w}


def threshold_corners(top, bottom, tolerance, refs, leakage, hysteresis=(0.0,)):
    for name, value in [('top resistance', top), ('bottom resistance', bottom)]:
        positive(value, name)
    if not 0 <= tolerance < 1:
        raise ValueError('resistor tolerance outside [0,1)')
    values = []
    # Independent divider for OV; an eventual shared UV/OV ladder needs its own model.
    for rt, rb, ref, bias, hyst in itertools.product(
            [top*(1-tolerance), top*(1+tolerance)],
            [bottom*(1-tolerance), bottom*(1+tolerance)], refs,
            [-leakage, leakage], hysteresis):
        values.append((ref-hyst)*(1+rt/rb)+bias*rt)
    return [min(values), max(values)]


def calculate(a):
    s, d, active = a['steady'], a['d14'], a['active_example']
    v = s['vout_nominal_v']
    published_a = s['servo_stall_a'] + s['aux_estimate_a']
    screening_a = s['servo_stall_a'] * (1+s['stall_contingency_fraction']) + s['aux_estimate_a']
    result = {'status': 'no_architecture_selected_or_qualified',
              'load': {'published_stall_plus_estimated_aux_a': published_a,
                       'analyst_contingency_a': screening_a,
                       'nominal_stall_plus_aux_w': v*published_a},
              'converter_screening': {}, 'load_sensitivity': [],
              'active_threshold_examples': [], 'current_breaker_examples': []}
    for name, c in a['converters'].items():
        static_fraction = c['set_accuracy_fraction']
        if name == 'wide_candidate':
            delta = max(abs(t-c['reference_c']) for t in c['specified_ambient_c'])
            static_fraction += c['line_fraction'] + c['load_fraction'] + delta*c['temp_fraction_per_k']
        max_static_v = v*(1+static_fraction)
        result['converter_screening'][name] = {
            'static_output_max_v': max_static_v,
            'static_headroom_to_servo_max_v': s['servo_max_v']-max_static_v,
            'input_headroom_above_steady_robot_v': c['input_max_v']-s['robot_max_v'],
            'input_margin_to_d14_specified_clamp_v': c['input_max_v']-d['clamp_max_v'],
            'input_margin_to_d14_max_breakdown_v': c['input_max_v']-d['breakdown_max_v'],
            'stand_minimum_input_margin_before_drops_v': s['stand_min_v']-c['input_min_v'],
            'contingency_output_w_at_static_max': screening_a*max_static_v,
            'energy_headroom_per_100uf_to_servo_max_j': energy(
                a['energy_examples']['output_capacitance_f'], max_static_v, s['servo_max_v']),
            'guaranteed_dynamic_input_or_output_peak_v': None,
        }
    for eta, input_v in itertools.product(s['efficiency_scenarios'],
            [s['stand_min_v'], s['robot_min_v'], s['robot_max_v']]):
        entry = power_load(v, published_a, input_v, eta)
        result['load_sensitivity'].append({'efficiency_assumed': eta, 'input_v': input_v, **entry})
    thermal = a['thermal_sensitivity']
    result['thermal_sensitivity'] = [
        {'efficiency_assumed': eta,
         'estimated_case_c_at_assumed_ambient': thermal['ambient_c'] +
         power_load(v, published_a, s['robot_max_v'], eta)['loss_w'] *
         thermal['wide_module_case_to_ambient_k_per_w'],
         'qualified_enclosure_temperature': False}
        for eta in s['efficiency_scenarios']]
    for top in active['top_examples_ohm']:
        rise = threshold_corners(top, active['bottom_ohm'], active['resistor_tolerance'],
                                 active['ov_ref_range_v'], active['leakage_abs_a'])
        fall = threshold_corners(top, active['bottom_ohm'], active['resistor_tolerance'],
                                 active['ov_ref_range_v'], active['leakage_abs_a'],
                                 active['hysteresis_range_v'])
        gain_max = 1+top*(1+active['resistor_tolerance'])/(active['bottom_ohm']*(1-active['resistor_tolerance']))
        timed_voltage = rise[1]+active['timing_overdrive_v']*gain_max
        result['active_threshold_examples'].append({
            'top_ohm': top, 'bottom_ohm': active['bottom_ohm'],
            'nominal_rising_v': active['ov_ref_nominal_v']*(1+top/active['bottom_ohm']),
            'rising_range_v': rise, 'recovery_range_v': fall,
            'guaranteed_static_recovery_above_42v': fall[0] > s['robot_max_v'],
            'worst_input_at_50mv_comparator_overdrive_v': timed_voltage,
            'remaining_to_50v_before_gate_delay_v': 50-timed_voltage,
            'remaining_to_55v_design_target_before_gate_delay_v': 55-timed_voltage,
            'guaranteed_transient_output_peak_v': None,
        })
    for resistance in active['sense_examples_ohm']:
        rmin, rmax = resistance*(1-active['sense_tolerance']), resistance*(1+active['sense_tolerance'])
        result['current_breaker_examples'].append({
            'sense_ohm': resistance,
            'steady_forward_trip_range_a': [active['forward_sense_range_v'][0]/rmax,
                                           active['forward_sense_range_v'][1]/rmin],
            'limit_note': 'Circuit breaker, not a current limiter; startup threshold differs and current flows during delay',
        })
    cmax = active['downstream_bank_f']*(1+active['bank_cap_tolerance_scenario'])
    gate_min = active['gate_cap_example_f']*(1-active['gate_cap_tolerance'])
    result['startup'] = {
        'bank_energy_at_42v_j': energy(active['downstream_bank_f'], 0, s['robot_max_v']),
        'bank_energy_with_20pct_cap_scenario_j': energy(cmax, 0, s['robot_max_v']),
        'inrush_a_at_max_gate_current_min_gate_cap_max_bank_cap': cmax/gate_min*max(active['gate_up_range_a']),
        'note': 'Charging current excludes running loads; resistor-isolated gate capacitor, MOSFET SOA and actual board capacitance remain unqualified',
    }
    result['mosfet_conduction_scenarios'] = [
        {'current_a': i, 'pair_loss_25c_w': i*i*2*active['fet_rds_25c_max_ohm'],
         'pair_loss_with_assumed_hot_multiplier_w': i*i*2*active['fet_rds_25c_max_ohm']*active['fet_hot_multiplier_scenario']}
        for i in [1, 3, 10]]
    e = a['energy_examples']
    result['unmeasured_energy_sensitivity'] = [
        {'inductance_h': l, 'current_a': i, 'stored_j': 0.5*l*i*i}
        for l, i in itertools.product(e['inductance_h'], e['current_a'])]
    result['fixed_clamp_assumption_counterexamples'] = [
        {'source_v': e['source_pulse_v'], 'source_r_ohm': r,
         'current_if_clamp_stayed_at_specified_voltage_a': (e['source_pulse_v']-d['clamp_max_v'])/r,
         'within_d14_specified_test_current': (e['source_pulse_v']-d['clamp_max_v'])/r <= d['clamp_test_a'],
         'not_a_predicted_waveform': True}
        for r in e['source_r_scenarios_ohm']]
    result['unknowns'] = a['unknowns']
    return result


def receipt():
    raw = INPUT.read_bytes()
    a = json.loads(raw)
    repo = HERE.parents[1]
    for binding in a['source_bindings']:
        data = subprocess.check_output(['git', 'show', f"{a['source_commit']}:{binding['path']}"], cwd=repo)
        if hashlib.sha256(data).hexdigest() != binding['sha256']:
            raise ValueError('source binding changed: '+binding['path'])
    return {'inputs_sha256': hashlib.sha256(raw).hexdigest(),
            'calculator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'source_commit': a['source_commit'], 'results': calculate(a)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--write', action='store_true')
    mode.add_argument('--check', action='store_true')
    args = parser.parse_args()
    rendered = json.dumps(receipt(), indent=2, allow_nan=False)+'\n'
    if args.write:
        OUTPUT.write_text(rendered)
        print('Wrote comparison receipt; no architecture selected or qualified')
    elif args.check:
        if not OUTPUT.exists() or OUTPUT.read_text() != rendered:
            raise SystemExit('FAIL: missing or stale calculation receipt; run --write and review the changes')
        print('PASS: source bindings and deterministic calculation receipt; no build qualification')
    else:
        print(rendered, end='')
