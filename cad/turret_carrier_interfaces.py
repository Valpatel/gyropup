"""Reviewable C2 layout requirements, not a qualified harness or electrical schematic.

Coordinates are turret T millimetres. Vendor-derived dimensions and design
reservations are intentionally separate. No CAD kernel or network is needed.
"""
from __future__ import annotations
from math import dist
import print_provenance as provenance

SOURCES = {
    'amass': 'https://www.china-amass.com/public/upload/20240608/810c62b3f7ace2287989748538eb2a6b.pdf',
    'molex_plug': 'https://definum.ru/system/files/430200400_sd.pdf',
    'molex_receptacle': 'https://www.100y.com.tw/pdf_file/10-molex-430251400.pdf',
    'molex_spec': 'https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/productspecificationpdf/430/43045/PS-43045-001.pdf',
    'splice': 'https://www.te.com/en/product-320559.html',
    'splice_application': 'https://www.te.com/commerce/DocumentDelivery/DDEController?Action=srchrtrv&DocFormat=pdf&DocLang=English&DocNm=114-2157&DocType=Specification+Or+Standard&PartCntxt=320559',
    'wire': 'https://www.remingtonindustries.com/content/PTFE%20Hook%20Up%20Wire%20Data%20Sheet.pdf',
}

POWER = {
    'source': 'XT30U-F.G.Y', 'module': 'XT30U-M.G.Y',
    'pin_map': {'+': 'BUS_HEAD_FUSED', '-': 'GND'},
    'operating_domains_v': [[15.,20.5],[30.,42.]],
    'upstream_fuse_a': 10., 'connector_test_current_a': 15.,
    'connector_test_wire_awg': 16, 'connector_test_temperature_rise_k': 30.,
    'tail_wire_awg': 16, 'trunk_wire_awg': 18,
    'tail_wire_od_mm': 2.032, 'trunk_wire_od_mm': 1.7526,
    'withstand_vdc': 500., 'working_voltage_rating_v': None,
    'mating_cycles_manufacturer': 100,
    'centre_xz_mm': [65.,11.5],
    'module_body_y_mm': [-13.7,0.], 'source_body_y_mm': [0.,12.4],
    'body_xz_mm': [5.6,10.2],
    'mated_length_mm': None,  # Separate full lengths are reserved without shrinking.
    'unmate_travel_mm': 14.,  # design clearance stroke, NOT a datasheet wipe dimension
    'straight_exit_design_mm': 16., 'straight_exit_manufacturer_mm': None,
    'bend_radius_mm': None,
}
SIGNAL = {
    'source': '43025-0400', 'module': '43020-0400',
    'source_contacts': {'part':'43030-0001','quantity':4},
    'module_contacts': {'part':'43031-0001','quantity':4},
    'wire_awg': 24, 'wire_od_mm': 1.4, 'max_wire_od_mm': 1.85,
    'pin_map': {
        '1': {'net':'CAN_H','fixed':'DT12.5','module':'C3.5','domain':'CAN bus; 5 V powered transceiver'},
        '2': {'net':'CAN_L','fixed':'DT12.6','module':'C3.6','domain':'CAN bus; 5 V powered transceiver'},
        '3': {'net':'SAFETY_A','fixed':'DT12.7','module':'12V_PAN after F4','domain':'12 V pendant dry-contact loop'},
        '4': {'net':'SAFETY_B','fixed':'DT12.8','module':'U1 NE555 pin8 and pin4','domain':'12 V pendant dry-contact return'},
    },
    'centre_xz_mm': [68.,29.],
    'plug_length_mm': 16.89, 'receptacle_length_mm': 14., 'mated_length_mm': 24.77,
    'module_body_y_mm': [-16.89,0.], 'source_body_y_mm': [-6.12,7.88],
    'drawing_body_width_mm': 6.85, 'drawing_receptacle_height_mm': 10.81,
    # Includes allowance for panel ears/latch; not a validated manufacturer BREP.
    'reservation_xz_mm': [12.,14.],
    'unmate_travel_mm': 16., 'straight_exit_manufacturer_mm': 12.7,
    'bend_radius_mm': None, 'working_voltage_v': 600.,
    'mating_cycles_manufacturer': 30,
}

ANCHORS = {'fixed':[54.,40.,13.], 'module':[57.,-30.5,21.]}
MODULE_TRAVEL_MM = 45.  # layout pose only; complete installed-module sweep remains pending


def tail_requirements(kind, side, *, retained_mm=None, module_travel=0., steps=32):
    """Straight exit + Euclidean remainder: necessary length, never a routed fit.

    Both required stroke endpoints and intermediate states are measured. This is
    a lower bound: it omits bend arcs, tie wrap and obstacles. The source is
    unplugged BEFORE moving the module. Passing this calculation cannot qualify
    an unknown bend radius, a solder joint or a tie.
    """
    c = POWER if kind == 'power' else SIGNAL
    if kind not in ('power','signal') or side not in ('fixed','module'):
        raise ValueError('unknown connector or tail side')
    if steps < 1:
        raise ValueError('at least one travel interval is required')
    x,z = c['centre_xz_mm']
    sign = 1 if side == 'fixed' else -1
    y = c['source_body_y_mm'][1] if side == 'fixed' else c['module_body_y_mm'][0]
    straight = c.get('straight_exit_design_mm',c.get('straight_exit_manufacturer_mm'))
    anchor = list(ANCHORS[side])
    if side == 'module':
        anchor[0] += module_travel
    samples=[]
    for i in range(steps+1):
        unmate = c['unmate_travel_mm']*i/steps if side=='fixed' else 0.
        exit_point=[x+module_travel,y+unmate,z]
        free_exit=[exit_point[0],exit_point[1]+sign*straight,z]
        bound=straight+dist(anchor,free_exit)
        samples.append({'unmate_mm':unmate,'exit_mm':exit_point,'free_exit_end_mm':free_exit,'lower_bound_mm':bound})
    retained = retained_mm if retained_mm is not None else (55. if side=='fixed' else 40.)
    required=max(s['lower_bound_mm'] for s in samples)
    return {'connector':kind,'side':side,'anchor_mm':anchor,'retained_free_length_mm':retained,
            'required_geometric_lower_bound_mm':required,'reserve_above_lower_bound_mm':retained-required,
            'length_lower_bound_pass':retained>=required,'samples':samples,
            'bend_radius_mm':c['bend_radius_mm'],'route_qualified':False}


def readiness(evidence):
    """Unknown/missing coverage stays red, even with a green space reservation."""
    required=('geometry','connector_models','latch_and_retention','bend_radius','solder_and_insulation',
              'c3_and_servo_disconnect','source_protection','physical_fit')
    return all(evidence.get(k) is True for k in required)


def validate_source_receipt(root,receipt):
    """Kernel-free identity guard; CI need not install the recorded CAD runtime.

    Compare the entire closure, so altered/deleted/new geometry inputs all fail.
    Runtime versions/source fingerprint are recorded and compared by the CAD run.
    """
    recorded=receipt.get('inputs',{})
    if receipt.get('input_fingerprint')!=provenance.fingerprint(recorded):
        raise ValueError('Carrier input fingerprint is inconsistent')
    current=provenance.snapshot(root)
    for field in ('files','GYROPUP_CAD_PARAMS_sha256'):
        if recorded.get(field)!=current[field]:
            raise ValueError('Carrier CAD/config input closure changed: '+field)
    if receipt.get('source_sha256')!=recorded.get('files'):
        raise ValueError('Carrier source-file binding differs from its input snapshot')
