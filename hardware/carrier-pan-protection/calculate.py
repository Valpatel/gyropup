"""Static corner screening of circuit values. Not a waveform/SOA model or a safety pass."""
import itertools
import json
import math
from pathlib import Path
import circuit_design as D
HERE=Path(__file__).resolve().parent

def resistance(ref):
    value=D.PARTS[ref]['value'].split()[0]
    multiplier={'k':1000,'mR':0.001}
    for suffix,mul in multiplier.items():
        if value.endswith(suffix):
            result=float(value[:-len(suffix)])*mul; break
    else: result=float(value)
    if not math.isfinite(result) or result<=0: raise ValueError('resistance must be positive and finite')
    return result

def capacitance(ref):
    value=D.PARTS[ref]['value'].split()[0]
    for suffix,scale in (('nF',1e-9),('uF',1e-6)):
        if value.endswith(suffix):
            result=float(value[:-len(suffix)])*scale
            if math.isfinite(result) and result>0:return result
    raise ValueError('capacitance must be positive and finite with nF/uF units')

def bounds(values):
    values=list(values)
    if not values or not all(math.isfinite(v) for v in values): raise ValueError('finite corners required')
    return [round(min(values),9),round(max(values),9)]

def divider(top,bottom,kind):
    tol=.001+25e-6*65
    values={k:[] for k in ('trip_V','recover_V','overdrive_50mV_V')}
    for a,b,ref,leak,hyst in itertools.product((-1,1),(-1,1),(.4925,.5075),(-10e-9,10e-9),(.020,.032)):
        rt=top*(1+a*tol); rb=bottom*(1+b*tol)
        f=lambda t:t*(1+rt/rb)+leak*rt
        values['trip_V'].append(f(ref))
        values['recover_V'].append(f(ref+(-hyst if kind=='OV' else hyst)))
        values['overdrive_50mV_V'].append(f(ref+(.050 if kind=='OV' else -.050)))
    return {k:bounds(v) for k,v in values.items()}

def supervisor_window():
    # TI TPS3760 revA p21 explicitly applies ±1.5% to the hysteresis voltage,
    # not ±1.5 percentage points. Reference, leakage and resistor corners remain independent.
    tol=.001+25e-6*65
    fall=[];rise=[]
    for a,b,ref,leak,h in itertools.product((-1,1),(-1,1),(.792,.808),(-100e-9,100e-9),(-.015,.015)):
        rt=resistance('R12')*(1+a*tol); rb=resistance('R13')*(1+b*tol)
        f=lambda t:t*(1+rt/rb)+leak*rt
        fall.append(f(ref));rise.append(f(ref+.8*.02*(1+h)))
    return {'fall_V':bounds(fall),'rise_V':bounds(rise)}

def static_screen(*, cin_uF=500, efficiency=.8, diode_drop_V=1.5, fet_pair_ohm=.030,
                  clamp_min_V=-2, charged_output_V=55, raw_reverse_V=-42,
                  measured_slew_V_per_s=None):
    # These are proposed acceptance bounds, NOT measurements or guaranteed device performance.
    for x in (cin_uF,efficiency,diode_drop_V,fet_pair_ohm,charged_output_V):
        if not math.isfinite(x) or x<=0:raise ValueError('positive finite scenario required')
    if efficiency>1 or not math.isfinite(clamp_min_V) or not math.isfinite(raw_reverse_V):raise ValueError('invalid scenario')
    st=.01+75e-6*65
    sense=1/(1/resistance('R1')+1/resistance('R10'))
    sr=(sense*(1-st),sense*(1+st))
    trips=lambda lo,hi:bounds(v/r for v,r in itertools.product((lo,hi),sr))
    # Every ramp-bank value is parsed from source, so removing/reducing a capacitor cannot hide.
    bank=sum(capacitance(r) for r in ('C2','C6','C7','C8'))
    cap_min=bank*(1-.01-30e-6*65)
    slew=60e-6/cap_min if measured_slew_V_per_s is None else measured_slew_V_per_s
    if not math.isfinite(slew) or slew<=0:raise ValueError('positive finite slew required')
    en=supervisor_window()
    # Use minimum falling threshold, conservatively covering the complete enabled static interval.
    load=12*1.03*3.25/(en['fall_V'][0]*efficiency)
    charging=cin_uF*1e-6*slew
    controller_aux=.005 # design allowance, not a measured module standby current
    total=load+charging+controller_aux
    startup=trips(.030,.070)
    available=15-diode_drop_V-startup[0]*(fet_pair_ohm+sr[1])
    max_before_valid=2.7+.002*slew
    gates={
      'startup_current_budget':total<startup[0],
      '15V_enable_headroom':available>en['rise_V'][1],
      '15V_input_UV_recovery':15-diode_drop_V>divider(resistance('R4'),resistance('R5'),'UV')['recover_V'][1],
      'supervisor_valid_before_module_minimum':max_before_valid<3.5,
      'U1_negative_absolute':clamp_min_V>=-40,
      'U1_charged_reverse_differential':clamp_min_V-charged_output_V>=-60,
      'barrier_reverse_rating':charged_output_V-raw_reverse_V<200,
      'U3_VDD_recommended':charged_output_V<=65,
      'U2_input_rating':charged_output_V<=60,
    }
    return {'assumptions':{'Cin_total_max_uF':cin_uF,'efficiency_min':efficiency,'D1_forward_drop_max_V':diode_drop_V,
             'FET_pair_hot_resistance_max_ohm':fet_pair_ohm,'protected_input_min_V':clamp_min_V,
             'charged_output_max_V':charged_output_V,'raw_reverse_V':raw_reverse_V,'auxiliary_input_allowance_A':controller_aux},
      'sense_nominal_ohm':sense,'input_trip_A':{'forward_steady':trips(.040,.060),'forward_startup_at_Vout_0':startup,'reverse_magnitude':trips(.001,.005)},
      'EN':en,'ramp_bank_min_F':cap_min,'ramp_slew_model_V_per_s':slew,
      'startup_load_input_A':load,'capacitor_charge_A':charging,'startup_total_A':total,'startup_margin_A':startup[0]-total,
      'PAN_INPUT_available_at15V_V':available,'15V_enable_margin_V':available-en['rise_V'][1],
      'supervisor_voltage_at_max_startup_delay_V':max_before_valid,
      'charged_reverse_U1_differential_V':clamp_min_V-charged_output_V,
      'D1_reverse_screen_V':charged_output_V-raw_reverse_V,
      'D1_steady_loss_screen_W':diode_drop_V*load,
      'D1_required_theta_JA_at85C_125C_target_C_per_W':40/(diode_drop_V*load),
      'gates':gates,'all_conditional_static_gates_pass':all(gates.values()),'qualified':False}

def require_static_screen(**kwargs):
    result=static_screen(**kwargs)
    if not result['all_conditional_static_gates_pass']:
        raise ValueError('conditional screen failed: '+','.join(k for k,v in result['gates'].items() if not v))
    return result

def calculate():
    r=static_screen();tol=.001+25e-6*65
    # CTR timing: datasheet p23 min -ln(.31)*877k*Cmin; max -ln(.25)*1.147M*Cmax+40us.
    cdelay=capacitance('C9');ctol=.05+30e-6*65
    return {
      'status':'UNSELECTED_UNQUALIFIED_STATIC_SCREENING',
      'temperature_scenario_C':[-40,85],'reference_temperature_C':25,
      'divider_initial_plus_temperature_fraction':tol,
      'OV':divider(resistance('R2'),resistance('R3'),'OV'),
      'UV':divider(resistance('R4'),resistance('R5'),'UV'),
      'revision_B_conditional_screen':r,
      'legacy_unprotected_U1_differential_V':{'raw_minus42_output42':-84,'raw_minus42_output55':-97},
      'legacy_10mohm_startup_min_A':.030/(.010*(1+.01+75e-6*65)),
      'EN_release_delay_s':[-math.log(.31)*877e3*cdelay*(1-ctol),-math.log(.25)*1.147e6*cdelay*(1+ctol)+40e-6],
      'sense_each_loss_W_at60mV':[.060**2/(resistance(x)*(1-.01-75e-6*65)) for x in ('R1','R10')],
      'local_C1_only_energy_at42V_max_tolerance_J':.5*22e-6*1.2*42**2,
      'bleeder_42V_to5V_seconds_capacitance_scenarios':{str(u)+'uF':round(resistance('R9')*(1+tol)*u*1e-6*math.log(42/5),9) for u in (22,100,500)},
      'FET_pair_loss_W_at3_25A_max25C_Rds':2*.0064*3.25**2,
      'U2_static_max_V':12*1.03,'servo_12_6V_static_margin_V':round(12.6-12*1.03,9),
      'unqualified':['source_fault_envelope','negative_hot_insertion_clamp_and_energy','PAN_INPUT_55V_peak','12V_regeneration',
         'startup_Cin_efficiency_dropout_and_slew','FET_SOA_and_thermal','D1_loss_and_cold_drop','C1_cold_and_ripple',
         'reset_arming_and_backfeed','PCB_and_carrier_fit']}
if __name__=='__main__':
    (HERE/'reports/calculations.json').write_text(json.dumps(calculate(),indent=2,sort_keys=True)+'\n')
    print(json.dumps(calculate(),indent=2,sort_keys=True))
