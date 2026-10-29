"""Circuit candidate, not a released board. All coordinates are schematic mm, not PCB placement."""
NAME = 'pan-cutoff'
DATE = '2026-10-29'
LTC = 'https://www.analog.com/media/en/technical-documentation/data-sheets/ltc4368.pdf'
TI = 'https://www.ti.com/lit/ds/symlink/csd19531q5a.pdf'
POLOLU = 'https://www.pololu.com/product/5577'
TNPW = 'https://www.vishay.com/docs/28758/tnpw_e3.pdf'
WSL = 'https://www.vishay.com/docs/30100/wsl.pdf'
KEMET = 'https://yageogroup.com/content/datasheet/asset/file/KEM_C1003_C0G_SMD'
FC = 'https://industrial.panasonic.com/ww/products/pt/aluminum-cap-lead/models/EEUFC2A220'
# Symbol pins: number, name, electrical type, x, y (up), orientation. Stacked pins keep every real lead in netlist.
def pin(n, name, kind, x, y, angle):
    return [str(n), name, kind, x, y, angle]
SYMBOLS = {
 'LTC4368IMS2': {'box': [15.24, 33.02], 'pins': [
   pin(1,'VIN','power_in',-20.32,25.4,0), pin(2,'UV','input',-20.32,20.32,0),
   pin(3,'OV','input',-20.32,0,0), pin(4,'RETRY','input',-20.32,-25.4,0),
   pin(5,'GND','power_in',-20.32,-30.48,0), pin(6,'SHDN','input',-20.32,-20.32,0),
   pin(7,'FAULT','open_collector',20.32,-25.4,180), pin(8,'VOUT','passive',20.32,5.08,180),
   pin(9,'SENSE','input',20.32,15.24,180), pin(10,'GATE','output',20.32,25.4,180)]},
 'Q_IN': {'box':[7.62,10.16], 'pins': [*[pin(n,'D','passive',-12.7,2.54,0) for n in (5,6,7,8)],
   *[pin(n,'S','passive',12.7,2.54,180) for n in (1,2,3)],pin(4,'G','input',0,-12.7,90)]},
 'Q_OUT': {'box':[7.62,10.16], 'pins': [*[pin(n,'S','passive',-12.7,2.54,0) for n in (1,2,3)],
   *[pin(n,'D','passive',12.7,2.54,180) for n in (5,6,7,8)],pin(4,'G','input',0,-12.7,90)]},
 'D42V55F12': {'box':[17.78,17.78], 'pins': [
   *[pin(n,'VIN','power_in',-22.86,12.7,0) for n in ('A4','B4')],
   *[pin(n,'GND','power_in',-22.86,-12.7,0) for n in ('A2','A3','B2','B3')],
   pin('B6','EN','input',-22.86,0,0),
   *[pin(n,'VOUT','power_out',22.86,12.7,180) for n in ('A1','B1')],
   *[pin(n,'VRP','passive',22.86,0,180) for n in ('A5','B5')],pin('A6','PG','open_collector',22.86,-12.7,180)]},
 'R': {'box':[3.81,1.27], 'pins':[pin(1,'~','passive',-8.89,0,0),pin(2,'~','passive',8.89,0,180)]},
 'R_V': {'box':[1.27,2.54], 'length':2.54, 'pins':[pin(1,'~','passive',0,5.08,270),pin(2,'~','passive',0,-5.08,90)]},
 'C': {'box':[1.27,2.54], 'pins':[pin(1,'~','passive',-6.35,0,0),pin(2,'~','passive',6.35,0,180)]},
 'C_POL': {'box':[1.27,2.54], 'pins':[pin(1,'+','passive',-6.35,0,0),pin(2,'-','passive',6.35,0,180)]},
 'C_V': {'box':[2.54,1.27], 'pins':[pin(1,'~','passive',0,6.35,270),pin(2,'~','passive',0,-6.35,90)]},
 'C_POL_V': {'box':[2.54,1.27], 'pins':[pin(1,'+','passive',0,6.35,270),pin(2,'-','passive',0,-6.35,90)]},
 'C_GS': {'box':[2.54,1.27], 'pins':[pin(1,'~','passive',0,-6.35,90),pin(2,'~','passive',0,6.35,270)]},
 'FLAG': {'box':[0,0], 'pins':[pin(1,'~','power_out',0,0,0)]},
}
PARTS = {}
def part(ref, sym, value, mpn, pins, xy, source, note='', footprint=''):
    PARTS[ref] = dict(symbol=sym,value=value,mpn=mpn,pins={str(k):v for k,v in pins.items()},xy=xy,
                      datasheet=source,note=note,footprint=footprint)
part('Q1','Q_IN','100V N-MOS','CSD19531Q5AT',
     {**{str(n):'BUS_HEAD_FUSED' for n in (5,6,7,8)},**{str(n):'COMMON_SOURCE' for n in (1,2,3)},'4':'GATE'},(76.2,48.26),TI,
     'Body diode anode=COMMON_SOURCE, cathode=BUS_HEAD_FUSED. Drain exposed metal belongs to D, not a new pin9.')
part('Q2','Q_OUT','100V N-MOS','CSD19531Q5AT',
     {**{str(n):'SENSE_HI' for n in (5,6,7,8)},**{str(n):'COMMON_SOURCE' for n in (1,2,3)},'4':'GATE'},(144.78,48.26),TI,
     'Body diode anode=COMMON_SOURCE, cathode=SENSE_HI. Common-source pair; no PCB footprint qualified.')
part('R1','R','10mR 1% 1W','WSL2512R0100FEA',{1:'SENSE_HI',2:'PAN_INPUT'},(241.3,45.72),WSL,
     'Kelvin sense routing at pad edges required. 2-terminal part; current and sense share the pads.', 'Resistor_SMD:R_2512_6332Metric')
part('U1','LTC4368IMS2','LTC4368IMS-2','LTC4368IMS-2#PBF',
     {1:'BUS_HEAD_FUSED',2:'UV_DIV',3:'OV_DIV',4:'GND',5:'GND',6:'SHDN_DIV',7:None,8:'PAN_INPUT',9:'SENSE_HI',10:'GATE'},
     (180.34,139.7),LTC,'MSOP-10 pin map, revC p2. RETRY grounded: forward OC latch; UV/OV still auto-recover.',
     'Package_SO:MSOP-10_3x3mm_P0.5mm')
part('U2','D42V55F12','D42V55F12 / 5577','Pololu 5577',
     {'A4':'PAN_INPUT','B4':'PAN_INPUT', **{n:'GND' for n in ('A2','A3','B2','B3')},
      'A1':'12V_PAN','B1':'12V_PAN','A5':None,'B5':None,'A6':None,'B6':None},
     (335.28,58.42),POLOLU,
     'Project pad IDs A/B from manufacturer top view, see pins.md. EN left open uses internal pullup. VRP never used as input. PG unused; not a servo OVP.')
for ref,val,mpn,n1,n2,xy,note in [
 ('R2','464k 0.1%','TNPW0805464KBEEN','BUS_HEAD_FUSED','OV_DIV',(91.44,130.81),'OV top; stock quantity unresolved'),
 ('R3','4.99k 0.1%','TNPW08054K99BEEN','OV_DIV','GND',(91.44,148.59),'OV bottom'),
 ('R4','127k 0.1%','TNPW0805127KBEEN','BUS_HEAD_FUSED','UV_DIV',(127,110.49),'UV top; listed nonstock/reel order'),
 ('R5','4.99k 0.1%','TNPW08054K99BEEN','UV_DIV','GND',(127,128.27),'UV bottom'),
 ('R6','499k 0.1%','TNPW0805499KBEEN','BUS_HEAD_FUSED','SHDN_DIV',(55.88,151.13),'SHDN top: limits pin current; not an arm circuit'),
 ('R7','100k 0.1%','TNPW0805100KBEEN','SHDN_DIV','GND',(55.88,168.91),'SHDN bottom; default ON when source valid'),
 ('R8','22k 0.1%','TNPW080522K0BEEN','GATE','GATE_RC',(241.3,134.62),'Series with CGATE only; NOT in series with MOSFET gates'),
 ('R9','100k 0.1%','TNPW0805100KBEEN','PAN_INPUT','GND',(307.34,100.33),'Bleeder; decay depends on unmeasured module Cin'),
]: part(ref,'R_V',val,mpn,{1:n1,2:n2},xy,TNPW,note,'Resistor_SMD:R_0805_2012Metric')
part('C1','C_POL_V','22uF 100V 20%','EEU-FC2A220',{1:'PAN_INPUT',2:'GND'},(279.4,100.33),FC,
     'Local VOUT decoupling; positive terminal to PAN_INPUT. 8mm diameter x11.5mm nominal body exceeds U2 height reservation.',
     'Capacitor_THT:CP_Radial_D8.0mm_P3.50mm')
part('C2','C_V','3.3nF 100V 5%','C0805C332J1GACTU',{1:'GATE_RC',2:'GND'},(241.3,160.02),KEMET,
     'ADI CGATE example value; actual U2 capacitance/inrush and SOA not qualified.', 'Capacitor_SMD:C_0805_2012Metric')
part('C3','C_GS','6.8nF 50V 5%','C0805C682J5GACTU',{1:'GATE',2:'COMMON_SOURCE'},(110.49,60.96),KEMET,
     'Gate-to-common-source hotswap capacitor, ADI p15-16; NOT gate-to-ground.', 'Capacitor_SMD:C_0805_2012Metric')
# No additional connector is selected: these are named solder/interface nodes, with separate contract in pins.md.
# SHDN_DIV is a bare test/reset pad in this checkpoint. Temporary short to GND resets OC, never an emergency stop.
for i,net,xy in [(1,'BUS_HEAD_FUSED',(63.5,45.72)),(2,'GND',(149.86,180.34)),(3,'PAN_INPUT',(269.24,45.72))]:
    part(f'#FLG0{i}','FLAG','PWR_FLAG','',{1:net},xy,'','ERC power-network declaration only; not a protection proof.')

# These are real schematic wires, not a separate intended-connectivity netlist.
# Local labels are retained for the two Kelvin sense taps and distributed ground/BUS.
WIRE_PATHS = [
 ('COMMON_SOURCE',[(88.9,45.72),(110.49,45.72),(132.08,45.72)]),
 ('COMMON_SOURCE',[(110.49,45.72),(110.49,54.61)]),
 ('SENSE_HI',[(157.48,45.72),(232.41,45.72)]),
 ('PAN_INPUT',[(250.19,45.72),(269.24,45.72),(279.4,45.72),(307.34,45.72),(312.42,45.72)]),
 ('PAN_INPUT',[(279.4,45.72),(279.4,93.98)]),
 ('PAN_INPUT',[(307.34,45.72),(307.34,95.25)]),
 ('GND',[(279.4,106.68),(279.4,121.92),(307.34,121.92),(307.34,105.41)]),
 ('GATE',[(76.2,60.96),(76.2,76.2),(110.49,76.2),(144.78,76.2),(215.9,76.2),(215.9,114.3),(200.66,114.3)]),
 ('GATE',[(144.78,60.96),(144.78,76.2)]),
 ('GATE',[(110.49,67.31),(110.49,76.2)]),
 ('GATE',[(215.9,114.3),(241.3,114.3),(241.3,129.54)]),
 ('GATE_RC',[(241.3,139.7),(241.3,153.67)]),
 ('GND',[(241.3,166.37),(241.3,180.34)]),
 ('UV_DIV',[(127,115.57),(127,119.38),(127,123.19)]),
 ('UV_DIV',[(127,119.38),(160.02,119.38)]),
 ('OV_DIV',[(91.44,135.89),(91.44,139.7),(91.44,143.51)]),
 ('OV_DIV',[(91.44,139.7),(160.02,139.7)]),
 ('SHDN_DIV',[(55.88,156.21),(55.88,160.02),(55.88,163.83)]),
 ('SHDN_DIV',[(55.88,160.02),(160.02,160.02)]),
 ('GND',[(160.02,165.1),(149.86,165.1),(149.86,170.18),(149.86,180.34)]),
 ('GND',[(160.02,170.18),(149.86,170.18)]),
]
WIRE_LABELS = [
 ('COMMON_SOURCE',(93.98,45.72)),('SENSE_HI',(187.96,45.72)),('PAN_INPUT',(254,45.72)),
 ('GATE',(175.26,76.2)),('GATE_RC',(241.3,147.32)),
 ('UV_DIV',(139.7,119.38)),('OV_DIV',(139.7,139.7)),('SHDN_DIV',(139.7,160.02)),
 ('GND',(241.3,180.34)),('GND',(279.4,121.92)),('GND',(149.86,180.34)),
]
JUNCTIONS = [(110.49,45.72),(279.4,45.72),(307.34,45.72),(110.49,76.2),(144.78,76.2),
             (215.9,114.3),(127,119.38),(91.44,139.7),(55.88,160.02),(149.86,170.18)]
NOTES = [
 (20.32,15.24,'PAN SUPPLY CANDIDATE | UNSELECTED / UNQUALIFIED | NOT FOR FABRICATION OR ENERGIZATION'),
 (20.32,25.4,'U2-only tap after the existing head fuse. Shared C2/C3 BUS bypasses this circuit; upstream D8/D14 remain external.'),
 (20.32,88.9,'INPUT LIMITS / RESET'),
 (20.32,93.98,'Steady source: 15-20.5 V stand / 30-42 V robot BUS. Transient envelope is unknown.'),
 (269.24,139.7,'U2 EN: OPEN (internal pullup)'),
 (269.24,144.78,'PG and both VRP pads: NC'),
 (269.24,154.94,'12V_PAN feeds existing F1 PAN PTC'),
 (269.24,160.02,'and F4 pendant/NE555 path.'),
 (269.24,170.18,'Local C1: 8 x 11.5 mm body;'),
 (269.24,175.26,'exceeds legacy U2 height reservation.'),
 (20.32,198.12,'Q1/Q2: common SOURCE and GATE; intrinsic diode cathodes face the outer drains. Every real package lead is exported.'),
 (20.32,205.74,'SENSE/VOUT labels are Kelvin taps at R1 pad edges. R8 is in the C2 ramp branch only, not in series with the MOSFET gates.'),
 (20.32,213.36,'RETRY=GND latches forward overcurrent only. SHDN_DIV defaults ON; UV/OV recovery is AUTOMATIC. FAULT is unused.'),
 (20.32,220.98,'Grounding SHDN_DIV clears a forward fault. This service/reset node is NOT the ARM line or an emergency stop.'),
 (20.32,236.22,'OPEN RELEASE GATES: +BUS surge envelope, -42V reverse fault (controller limit -40V), startup current/SOA, thermal and EMI.'),
 (20.32,241.3,'No 12V regeneration clamp is selected; the 12.6V servo limit is NOT proven. PAN_INPUT <=55V is a target, not a guarantee.'),
 (20.32,246.38,'No PCB, extra-board location, qualified pad layout or service-clearance approval. Read README.md, pins.md and fault-review.md.'),
]
