"""Circuit candidate, not a released board. All coordinates are schematic mm, not PCB placement."""
NAME = 'pan-cutoff'
DATE = '2026-10-29'
LTC = 'https://www.analog.com/media/en/technical-documentation/data-sheets/ltc4368.pdf'
TI = 'https://www.ti.com/lit/ds/symlink/csd19531q5a.pdf'
POLOLU = 'https://www.pololu.com/product/5577'
TNPW = 'https://www.vishay.com/docs/28758/tnpw_e3.pdf'
WSL = 'https://www.vishay.com/docs/30100/wsl.pdf'
KEMET = 'https://yageogroup.com/content/datasheet/asset/file/KEM_C1003_C0G_SMD'
DIODE = 'https://www.vishay.com/docs/89316/v10p20.pdf'
SUPERVISOR = 'https://www.ti.com/lit/ds/symlink/tps3760.pdf'
X7R = 'https://yageogroup.com/content/datasheet/asset/file/KEM_C1002_X7R_SMD'
KEMET_AUTO = 'https://yageogroup.com/content/datasheet/asset/file/KEM_C1091_C0G_ESD'
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
 'D_SERIES': {'box':[2.54,2.54], 'length':5.08, 'pins':[pin(1,'A','passive',-7.62,0,0),pin(2,'A','passive',-7.62,0,0),pin('K','K','passive',7.62,0,180)]},
 'D_CLAMP': {'box':[2.54,2.54], 'length':5.08, 'pins':[pin(1,'A','passive',0,-7.62,90),pin(2,'A','passive',0,-7.62,90),pin('K','K','passive',0,7.62,270)]},
 'TPS3760A012': {'box':[15.24,35.56], 'pins':[pin(1,'VDD','power_in',-20.32,20.32,0),pin(3,'SENSE','input',-20.32,7.62,0),pin(6,'RESET','open_collector',20.32,20.32,180),pin(8,'GND','power_in',-20.32,-22.86,0),pin(13,'GND','passive',-20.32,-22.86,0),pin(9,'CTR','passive',20.32,0,180),pin(10,'CTS','passive',20.32,-12.7,180),*[pin(n,'NC','passive',x,40.64,270) for n,x in zip((2,4,5,7,11,12,14),(-15.24,-10.16,-5.08,0,5.08,10.16,15.24))]]},
 'FLAG': {'box':[0,0], 'pins':[pin(1,'~','power_out',0,0,0)]},
}
PARTS = {}
def part(ref, sym, value, mpn, pins, xy, source, note='', footprint=''):
    PARTS[ref] = dict(symbol=sym,value=value,mpn=mpn,pins={str(k):v for k,v in pins.items()},xy=xy,
                      datasheet=source,note=note,footprint=footprint)
part('Q1','Q_IN','100V N-MOS','CSD19531Q5AT',
     {**{str(n):'VIN_PROTECTED' for n in (5,6,7,8)},**{str(n):'COMMON_SOURCE' for n in (1,2,3)},'4':'GATE'},(76.2,48.26),TI,
     'Body diode anode=COMMON_SOURCE, cathode=VIN_PROTECTED. Drain exposed metal belongs to D, not a new pin9.')
part('Q2','Q_OUT','100V N-MOS','CSD19531Q5AT',
     {**{str(n):'SENSE_HI' for n in (5,6,7,8)},**{str(n):'COMMON_SOURCE' for n in (1,2,3)},'4':'GATE'},(144.78,48.26),TI,
     'Body diode anode=COMMON_SOURCE, cathode=SENSE_HI. Common-source pair; no PCB footprint qualified.')
part('R1','R','10mR 1% 1W','WSL2512R0100FEA',{1:'SENSE_HI',2:'PAN_INPUT'},(241.3,45.72),WSL,
     'Kelvin sense routing at pad edges required. 2-terminal part; current and sense share the pads.', 'Resistor_SMD:R_2512_6332Metric')
part('U1','LTC4368IMS2','LTC4368IMS-2','LTC4368IMS-2#PBF',
     {1:'VIN_PROTECTED',2:'UV_DIV',3:'OV_DIV',4:'GND',5:'GND',6:'SHDN_DIV',7:None,8:'PAN_INPUT',9:'SENSE_HI',10:'GATE'},
     (180.34,139.7),LTC,'MSOP-10 pin map, revC p2. RETRY grounded: forward OC latch; UV/OV still auto-recover.',
     'Package_SO:MSOP-10_3x3mm_P0.5mm')
part('U2','D42V55F12','D42V55F12 / 5577','Pololu 5577',
     {'A4':'PAN_INPUT','B4':'PAN_INPUT', **{n:'GND' for n in ('A2','A3','B2','B3')},
      'A1':'12V_PAN','B1':'12V_PAN','A5':None,'B5':None,'A6':None,'B6':'PAN_ENABLE'},
     (335.28,58.42),POLOLU,
     'Project pad IDs A/B from manufacturer top view, see pins.md. EN driven by U3 UV supervisor; internal pullup retained. VRP never used as input. PG unused; not a servo OVP.')
for ref,val,mpn,n1,n2,xy,note in [
 ('R2','464k 0.1%','TNPW0805464KBEEN','VIN_PROTECTED','OV_DIV',(91.44,130.81),'OV top; stock quantity unresolved'),
 ('R3','4.99k 0.1%','TNPW08054K99BEEN','OV_DIV','GND',(91.44,148.59),'OV bottom'),
 ('R4','100k 0.1%','TNPW0805100KBEEN','VIN_PROTECTED','UV_DIV',(127,110.49),'UV top; converter brownout is separately gated by U3'),
 ('R5','4.99k 0.1%','TNPW08054K99BEEN','UV_DIV','GND',(127,128.27),'UV bottom'),
 ('R6','499k 0.1%','TNPW0805499KBEEN','VIN_PROTECTED','SHDN_DIV',(55.88,151.13),'SHDN top: limits pin current; not an arm circuit'),
 ('R7','100k 0.1%','TNPW0805100KBEEN','SHDN_DIV','GND',(55.88,168.91),'SHDN bottom; default ON when source valid'),
 ('R8','22k 0.1%','TNPW080522K0BEEN','GATE','GATE_RC',(241.3,134.62),'Series with CGATE only; NOT in series with MOSFET gates'),
 ('R9','100k 0.1%','TNPW0805100KBEEN','PAN_INPUT','GND',(307.34,100.33),'Bleeder; decay depends on unmeasured module Cin'),
]: part(ref,'R_V',val,mpn,{1:n1,2:n2},xy,TNPW,note,'Resistor_SMD:R_0805_2012Metric')
part('C1','C_POL_V','22uF 100V 20%','EEU-FC2A220',{1:'PAN_INPUT',2:'GND'},(279.4,100.33),FC,
     'Local VOUT decoupling; positive terminal to PAN_INPUT. 8mm diameter x11.5mm nominal body exceeds U2 height reservation.',
     'Capacitor_THT:CP_Radial_D8.0mm_P3.50mm')
part('C2','C_V','47nF 100V 1%','C1206C473F1GECAUTO',{1:'GATE_RC',2:'GND'},(241.3,160.02),KEMET_AUTO,
     'One of four parallel 47nF C0G ramp capacitors. Conditional slew screen, not measured inrush/SOA.', 'Capacitor_SMD:C_1206_3216Metric')
part('C3','C_GS','6.8nF 50V 5%','C0805C682J5GACTU',{1:'GATE',2:'COMMON_SOURCE'},(110.49,60.96),KEMET,
     'Gate-to-common-source hotswap capacitor, ADI p15-16; NOT gate-to-ground.', 'Capacitor_SMD:C_0805_2012Metric')
# Revision B adds only circuitry; no connector, PCB, pad placement or area is allocated.
part('D1','D_SERIES','200V series barrier','V10P20-M3/87A',{1:'BUS_HEAD_FUSED',2:'BUS_HEAD_FUSED','K':'VIN_PROTECTED'},(35.56,45.72),DIODE,
     'K is project ID for manufacturer cathode pad; anode leads1/2 are numbered in the drawing. Multiwatt loss; copper/thermal unqualified.')
part('D2','D_CLAMP','200V negative clamp','V10P20-M3/87A',{1:'GND',2:'GND','K':'VIN_PROTECTED'},(43.18,279.4),DIODE,
     'Local anode GND / cathode protected input. Negative pulse current, loop inductance and cold clamp remain qualification gates.')
part('R10','R','20mR 1% 1W','WSL2512R0200FEA',{1:'SENSE_HI',2:'PAN_INPUT'},(241.3,60.96),WSL,
     'Parallel R1: nominal effective6.667mOhm. Shared Kelvin endpoints, symmetric low-inductance layout not yet provided.', 'Resistor_SMD:R_2512_6332Metric')
for ref,value,mpn,n1,n2,xy,note in [
 ('R11','100k 0.1%','TNPW0805100KBEEN','VIN_PROTECTED','GND',(139.7,279.4),'Protected-input bleeder; does not qualify negative transient clamp'),
 ('R12','150k 0.1%','TNPW0805150KBEEN','PAN_INPUT','EN_SENSE',(398.78,165.1),'U3 UV divider top'),
 ('R13','10k 0.1%','TNPW080510K0BEEN','EN_SENSE','GND',(398.78,190.5),'U3 UV divider bottom'),
 ('R14','499k 0.1%','TNPW0805499KBEEN','PAN_INPUT','PAN_ENABLE',(525.78,144.78),'External RESET pullup plus module internal nominal1M pullup'),
]:part(ref,'R_V',value,mpn,{1:n1,2:n2},xy,TNPW,note,'Resistor_SMD:R_0805_2012Metric')
for ref,n1,n2,xy in [('C4','VIN_PROTECTED','GND',(88.9,279.4)),('C5','PAN_INPUT','GND',(358.14,238.76))]:
    part(ref,'C_V','100nF 100V 10% X7R','C0805C104K1RACTU',{1:n1,2:n2},xy,X7R,'Local decoupling. DC-bias/temperature minimum and pulse response not qualified.','Capacitor_SMD:C_0805_2012Metric')
for ref,x in [('C6',279.4),('C7',317.5),('C8',355.6)]:
    part(ref,'C_V','47nF 100V 1%','C1206C473F1GECAUTO',{1:'GATE_RC',2:'GND'},(x,175.26),KEMET_AUTO,
         'Parallel ramp bank, total188nF nominal; C0G30ppm/K screen.','Capacitor_SMD:C_1206_3216Metric')
part('U3','TPS3760A012','UV / OD active-low','TPS3760A012DYYR',
     {1:'PAN_INPUT',3:'EN_SENSE',6:'PAN_ENABLE',8:'GND',13:'GND',9:None,10:None,**{n:None for n in (2,4,5,7,11,12,14)}},
     (457.2,185.42),SUPERVISOR,'A012 is adjustable UV with2% hysteresis and active-low open drain. E012 is OV, NOT a substitute. CTR and CTS open; no added timing capacitor.',
     '')
for i,net,xy in [(1,'BUS_HEAD_FUSED',(20.32,45.72)),(2,'GND',(149.86,180.34)),(3,'PAN_INPUT',(269.24,45.72)),(4,'VIN_PROTECTED',(55.88,45.72))]:
    part(f'#FLG0{i}','FLAG','PWR_FLAG','',{1:net},xy,'','ERC declaration only; not physical proof.')

# These are real schematic wires, not a separate intended-connectivity netlist.
# Local labels are retained for the two Kelvin sense taps and distributed ground/BUS.
WIRE_PATHS = [
 ('BUS_HEAD_FUSED',[(20.32,45.72),(27.94,45.72)]),
 ('VIN_PROTECTED',[(43.18,45.72),(55.88,45.72),(63.5,45.72)]),
 ('SENSE_HI',[(220.98,45.72),(220.98,60.96),(232.41,60.96)]),
 ('PAN_INPUT',[(250.19,60.96),(261.62,60.96),(261.62,45.72)]),
 ('COMMON_SOURCE',[(88.9,45.72),(110.49,45.72),(132.08,45.72)]),
 ('COMMON_SOURCE',[(110.49,45.72),(110.49,54.61)]),
 ('SENSE_HI',[(157.48,45.72),(220.98,45.72),(232.41,45.72)]),
 ('PAN_INPUT',[(250.19,45.72),(261.62,45.72),(269.24,45.72),(279.4,45.72),(307.34,45.72),(312.42,45.72)]),
 ('PAN_INPUT',[(279.4,45.72),(279.4,93.98)]),
 ('PAN_INPUT',[(307.34,45.72),(307.34,95.25)]),
 ('GND',[(279.4,106.68),(279.4,121.92),(307.34,121.92),(307.34,105.41)]),
 ('GATE',[(76.2,60.96),(76.2,76.2),(110.49,76.2),(144.78,76.2),(215.9,76.2),(215.9,114.3),(200.66,114.3)]),
 ('GATE',[(144.78,60.96),(144.78,76.2)]),
 ('GATE',[(110.49,67.31),(110.49,76.2)]),
 ('GATE',[(215.9,114.3),(241.3,114.3),(241.3,129.54)]),
 ('GATE_RC',[(241.3,139.7),(241.3,147.32),(241.3,153.67)]),
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
WIRE_PATHS += [
 ('GATE_RC',[(241.3,147.32),(279.4,147.32),(317.5,147.32),(355.6,147.32),(355.6,168.91)]),
 ('GATE_RC',[(279.4,147.32),(279.4,168.91)]),('GATE_RC',[(317.5,147.32),(317.5,168.91)]),
 ('GND',[(279.4,181.61),(279.4,195.58),(317.5,195.58),(355.6,195.58),(355.6,181.61)]),
 ('GND',[(317.5,181.61),(317.5,195.58)]),
 ('VIN_PROTECTED',[(43.18,271.78),(43.18,261.62),(88.9,261.62),(139.7,261.62),(139.7,274.32)]),
 ('VIN_PROTECTED',[(88.9,261.62),(88.9,273.05)]),
 ('GND',[(43.18,287.02),(43.18,297.18),(88.9,297.18),(139.7,297.18),(139.7,284.48)]),
 ('GND',[(88.9,285.75),(88.9,297.18)]),
 ('EN_SENSE',[(398.78,170.18),(398.78,177.8),(398.78,185.42)]),
 ('EN_SENSE',[(398.78,177.8),(436.88,177.8)]),
 ('PAN_INPUT',[(398.78,160.02),(398.78,119.38),(426.72,119.38),(525.78,119.38),(525.78,139.7)]),
 ('PAN_INPUT',[(426.72,119.38),(426.72,165.1),(436.88,165.1)]),
 ('PAN_ENABLE',[(477.52,165.1),(525.78,165.1),(525.78,149.86)]),
 ]
WIRE_LABELS = [
 ('COMMON_SOURCE',(93.98,45.72)),('SENSE_HI',(187.96,45.72)),('PAN_INPUT',(254,45.72)),
 ('GATE',(175.26,76.2)),('GATE_RC',(241.3,147.32)),
 ('UV_DIV',(139.7,119.38)),('OV_DIV',(139.7,139.7)),('SHDN_DIV',(139.7,160.02)),
 ('GND',(241.3,180.34)),('GND',(279.4,121.92)),('GND',(149.86,180.34)),
]
WIRE_LABELS += [('BUS_HEAD_FUSED',(20.32,45.72)),('VIN_PROTECTED',(48.26,45.72)),('VIN_PROTECTED',(43.18,261.62)),('GND',(43.18,297.18)),('GND',(279.4,195.58)),('EN_SENSE',(411.48,177.8)),('PAN_ENABLE',(492.76,165.1)),('PAN_INPUT',(426.72,119.38))]
JUNCTIONS = [(220.98,45.72),(261.62,45.72),(241.3,147.32),(279.4,147.32),(317.5,147.32),(317.5,195.58),(88.9,261.62),(88.9,297.18),(398.78,177.8),(426.72,119.38),(110.49,45.72),(279.4,45.72),(307.34,45.72),(110.49,76.2),(144.78,76.2),
             (215.9,114.3),(127,119.38),(91.44,139.7),(55.88,160.02),(149.86,170.18)]
NOTES = [
 (20.32,15.24,'PAN SUPPLY CANDIDATE B | UNSELECTED / UNQUALIFIED | NOT FOR FABRICATION OR ENERGIZATION'),
 (20.32,25.4,'U2-only tap. Shared C2/C3 BUS bypasses this sheet; existing D8/D14 and head fuse receive NO protection credit.'),
 (20.32,88.9,'INPUT WINDOW / FORWARD-FAULT LATCH'),
 (20.32,93.98,'15-20.5 V stand / 30-42 V steady BUS. Source transients are unknown.'),
 (381,96.52,'CONVERTER STARTUP / BROWNOUT INHIBIT'),
 (381,104.14,'U3 actively pulls EN low until PAN_INPUT exceeds ~13 V.'),
 (381,111.76,'Four C0G capacitors slow the U1 ramp; verify actual slew and Cin.'),
 (20.32,241.3,'LOCAL NEGATIVE CLAMP / INPUT DECOUPLING'),
 (20.32,248.92,'Place at U1 VIN/Q1 drain. Pulse and layout qualification remains open.'),
 (200.66,261.62,'Series D1 blocks raw negative BUS; D2 limits local negative coupling.'),
 (200.66,269.24,'VIN_PROTECTED >= -2 V and PAN_INPUT <=55 V are test acceptance bounds,'),
 (200.66,276.86,'not guaranteed waveforms. Charged-output VIN-VOUT >= -57 V in that envelope.'),
 (200.66,292.1,'12V_PAN feeds existing F1 PAN PTC and F4 pendant/NE555 path.'),
 (200.66,299.72,'No extra PCB, power junction, external solder pad or carrier area allocated.'),
 (20.32,325.12,'R1 || R10 =6.667mOhm nominal. Both sense connections require shared Kelvin endpoints; no fuse coordination is established.'),
 (20.32,332.74,'R8 is in the ramp-capacitor branch only. Q1/Q2 share SOURCE/GATE; intrinsic diode cathodes face outer drains.'),
 (20.32,340.36,'RETRY=GND latches forward OC; UV/OV and U3 automatically recover. SHDN_DIV service reset is NOT ARM or emergency stop.'),
 (20.32,355.6,'OPEN GATES: hot insertion, source surge energy/impedance, diode/MOSFET SOA and thermal, converter startup/dropout/efficiency.'),
 (20.32,363.22,'Output regeneration/12.6 V servo limit, C1 ripple, solder/copper and physical fit remain unqualified. No energization authorized.'),
 (20.32,370.84,'See README.md, pins.md, fault-review.md and source-bound calculations. Zero ERC is connectivity evidence only.'),
]
