"""Reproduce the bounded paper assignment, without generating PCB/CAD.

All coordinates are candidate reservations; none are qualified placement.
"""
from pathlib import Path
import json,hashlib
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def allocation():
 b = HERE
 inv=json.loads((b/'component-inventory.json').read_text());terminal=json.loads((b/'terminal-contract.json').read_text())
 by_id={r['id']:r for r in terminal['existing_interfaces']}; pads=[]
 bypass={end for row in terminal['continuous_bypasses'] for end in row[:2]}
 for name in ('C2-P.module','C2-S.module','C3.module','PAN.servo'):
  for pin,net in by_id[name]['pins'].items():
   endpoint=name+'.'+pin
   if endpoint not in bypass:pads.append({'id':'CTRL.'+endpoint,'endpoint':endpoint,'net':net,'position':None,'hole_land_wire_qualification':None})
 interboard=[('BUS_IN','BUS_HEAD_FUSED'),('GND_IN','GND'),('12V_OUT','12V_PAN'),('GND_OUT','GND')]
 for pin,net in interboard:pads.append({'id':'CTRL.POWER.'+pin,'endpoint':'POWER.'+pin,'net':net,'position':None,'hole_land_wire_qualification':None})
 d={'status':'PAPER_ALLOCATION_ONLY_NOT_COMPONENT_PLACEMENT','observed':'2026-10-29','frozen':False,'physical_inventory_complete':False,'fit_qualified':False,'native_circuit_or_layout_generated':False,
 'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),b/'component-inventory.json',b/'terminal-contract.json',b/'mechanical-envelope.md',ROOT/'catalog/hardware.json']},
 'assemblies':[
  {'id':'CONTROL_TERMINATION','proposal':'Replacement custom control/termination PCB within existing outline, not reuse of an assumed empty perfboard area. All legacy parts require new exact placement/formed leads.','candidate_outline_mm':[50.8,30,1.6],'existing_world_region_mm':{'x':[46.4,48],'y':[-25.4,25.4],'z':[6,36]},'component_face_direction':[-1,0,0],'preserved_mount_holes_board_local_mm':[[3,3],[47.8,3],[3,27],[47.8,27]],'preserved_pcb_hole_diameter_mm':3.2,'electronic_members':[r['id'] for r in inv['rows'] if r['id'].startswith('L.')],'additional_unassigned_parts':['H.F4','H.D8','H.D14','physical BUS/return connections and retention'],'wire_pad_candidates':pads,'placement':None},
  {'id':'PAN_POWER','proposal':'One candidate power PCB with retained cutoff plus complete ideal-diode reference, Pololu module as an explicitly mounted daughterboard only after actual underside/heat/interconnect review.','candidate_outline_mm':[40,36,1.6],'candidate_world_xy_mm':{'x':[6,46],'y':[55,91]},'candidate_pcb_z_mm':[24.4,26],
  'trial_assembly_region_mm':{'x':[4,48],'y':[53,93],'z':[23,41]},'electronic_members':[r['id'] for r in inv['rows'] if not r['id'].startswith('L.')],'wire_pad_candidates':[{'id':'POWER.'+pin,'net':net,'position':None,'hole_land_wire_qualification':None} for pin,net in interboard],'placement':None}],
 'ground_boundary':'GND_IN and GND_OUT are separate proposed physical pads/wires on the same electrical GND. They do not imply isolation or validated star routing/noise performance; both join the logical return network. Three logical protection ports are unchanged.',
 'height_screens':{'capacitor':{'pcb_top_z_mm':26,'body_max_mm':12.5,'vent_free_min_mm':2,'available_top_z_mm':41,'mount_gap_mm':None,'tolerance_and_insulation_mm':None,'qualified':False},
  'converter':{'base_pcb_top_z_mm':26,'candidate_module_pcb_bottom_z_mm':30,'nominal_bottom_parts_mm':1.4,'nominal_module_pcb_mm':1.57,'nominal_top_parts_mm':6.1,'candidate_under_module_part_height_max_mm':1.8,'available_top_z_mm':41,'profile_tolerance_mm':None,'mounting_interconnect_insulation':None,'qualified':False}},
 'not_allocated':['All electronic XY positions, routes and real lands','All19 control-board and4 power-board wire-pad positions, strain relief and hole sizes','Four-wire interboard harness gauge/length/route/retention','Exact servo connector and conductor identity; conditional3A connector is not3.25A qualified','Raw10A head-bus/return copper, splice and fault-temperature capacity','Legacy F1 forming, all through-hole lead stacks and shunt/fuse coordination','Power PCB retention, screw/insert/collar/insulation volumes and heat path','C2 release, sector-bolt access, practical bumper seam/support/tolerance path and C3 quarter-turn lead routing','Source/charged-reversal/startup/transient/regen/thermal qualification']}
 return d

if __name__ == '__main__':
 (HERE/'allocation-proposal.json').write_text(json.dumps(allocation(),indent=2,sort_keys=True)+'\n')
 print('Paper assignment:47 electronics; no component placement or fit qualification.')
