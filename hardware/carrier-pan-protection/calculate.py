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

def calculate():
    sense=resistance('R1'); st=.01+75e-6*65
    sense_range=(sense*(1-st),sense*(1+st))
    def trips(lo,hi):return bounds(v/r for v,r in itertools.product((lo,hi),sense_range))
    tol=.001+25e-6*65
    shutdown={}
    for vin in (15,42,100):
        shutdown[str(vin)]=bounds((vin-ileak*resistance('R6')*(1+a*tol))/(1+resistance('R6')*(1+a*tol)/(resistance('R7')*(1+b*tol)))
                                   for a,b,ileak in itertools.product((-1,1),(-1,1),(-15e-9,15e-9)))
    return {
      'status':'UNSELECTED_UNQUALIFIED_STATIC_SCREENING',
      'temperature_scenario_C':[-40,85], 'reference_temperature_C':25,
      'divider_initial_plus_temperature_fraction':tol,
      'OV':divider(resistance('R2'),resistance('R3'),'OV'),
      'UV':divider(resistance('R4'),resistance('R5'),'UV'),
      'input_trip_A':{'forward_steady':trips(.040,.060),'forward_startup_at_Vout_0':trips(.030,.070),'reverse_magnitude':trips(.001,.005)},
      'SHDN_divider_V_scenario_not_full_leakage_characterization':shutdown,
      'screening_load':{'servo_plus_aux_A':2.71,'assumed_contingency_A':3.25,
          'Vin15_eta80_input_A':12*3.25/(15*.8),'Vin42_eta80_input_A':12*3.25/(42*.8)},
      'startup_margin_A_before_capacitance_at_15V80pct':round(trips(.030,.070)[0]-3.25,9),
      'gate_slew_inrush_A_total_capacitance_scenarios':{str(u)+'uF':round(u*1e-6*60e-6/(3.3e-9*.95),9) for u in (22,100,500)},
      'local_C1_only_energy_at42V_max_tolerance_J':.5*22e-6*1.2*42**2,
      'bleeder_42V_to5V_seconds_capacitance_scenarios':{str(u)+'uF':round(resistance('R9')*(1+tol)*u*1e-6*math.log(42/5),9) for u in (22,100,500)},
      'FET_pair_loss_W_at3_25A_max25C_Rds':2*.0064*3.25**2,
      'sense_loss_W_at_maxsteadytrip':round(trips(.040,.060)[1]**2*sense_range[0],9),
      'U2_static_max_V':12*1.03,'servo_12_6V_static_margin_V':round(12.6-12*1.03,9),
      'unqualified':['source_fault_envelope','negative_42V','PAN_INPUT_55V_peak','12V_regeneration','startup_Cin_and_load','FET_SOA_and_thermal','C1_cold_and_ripple','reset_arming_and_backfeed','PCB_and_carrier_fit']}
if __name__=='__main__':
    (HERE/'reports/calculations.json').write_text(json.dumps(calculate(),indent=2,sort_keys=True)+'\n')
    print(json.dumps(calculate(),indent=2,sort_keys=True))
