"""The rig node: an Adafruit Feather M4 CAN Express in the pod (docs/leg-rig-wiring.md, plan task T11). It reads the
pendant, the motors' bus voltage, the carriage's height and the load plate (or the bench's load cell), and puts them
on the CAN bus for the laptop (rig/node.py decodes them). It never commands a motor.

Install (once): CircuitPython 9 for "Feather M4 CAN Express" (circuitpython.org/board/feather_m4_can/), then the
libraries from the Adafruit bundle with circup:
    circup install adafruit_vl53l1x adafruit_hx711 neopixel
and copy code.py, rig_frames.py and settings.json from rig/firmware/feather_rig/ onto the CIRCUITPY drive.

Pins:
- D5: the pendant's 12 V through 10k / 2.2k; high while the pendant is held.
- A2: the motors' bus (after the contactor) through 100k / 4.7k.
- STEMMA QT: the VL53L1X.
- D6 (DT) and D9 (SCK): the HX711.
- The CAN terminal: the bus (1 Mbit/s; the motors' 29-bit frames pass by untouched).

Frames: RUN 0x700 at 100 Hz (0x5A only while D5 is high, 0x00 the moment it drops), SENSE 0x701 at 50 Hz, VBUS 0x702
at 100 Hz (the max, min and mean of the bus voltage sampled as fast as the loop runs, a few kHz, over the last 10 ms).
It listens for HOST 0x708 (the laptop's state) for the LED.

The USB serial prints "F <newtons>" ten times a second (the bench tests read the load cell there) and "S <status>"
once a second. Typing "t" re-tares the load cell (nothing on it).

settings.json: {"vbus_ratio": divider ratio, "vbus_trim": multiplier, "load_n_per_count": the load cell's scale,
"load_sign": 1 or -1}.
"""
import json
import sys
import time

import analogio
import board
import canio
import digitalio
import supervisor

import rig_frames as F

try:
    import neopixel
    PIX = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.15)
except Exception:                                   # noqa: BLE001 - the LED is a nicety
    PIX = None

SETTINGS = {'vbus_ratio': (100.0 + 4.7) / 4.7, 'vbus_trim': 1.0, 'load_n_per_count': 0.0, 'load_sign': 1}
try:
    with open('/settings.json') as f:
        SETTINGS.update(json.load(f))
except OSError:
    pass

# ---------------------------------------------------------------------------------------------------- the hardware
if hasattr(board, 'CAN_STANDBY'):
    standby = digitalio.DigitalInOut(board.CAN_STANDBY)
    standby.switch_to_output(False)                 # the transceiver awake
if hasattr(board, 'BOOST_ENABLE'):
    boost = digitalio.DigitalInOut(board.BOOST_ENABLE)
    boost.switch_to_output(True)                    # its 5 V
can = canio.CAN(rx=board.CAN_RX, tx=board.CAN_TX, baudrate=1_000_000, auto_restart=True)
host_in = can.listen(matches=[canio.Match(F.HOST)], timeout=0)

pendant = digitalio.DigitalInOut(board.D5)
pendant.switch_to_input(pull=digitalio.Pull.DOWN)
vbus_adc = analogio.AnalogIn(board.A2)
VREF = vbus_adc.reference_voltage or 3.3

tof = None
try:
    import adafruit_vl53l1x
    i2c = board.STEMMA_I2C() if hasattr(board, 'STEMMA_I2C') else board.I2C()
    tof = adafruit_vl53l1x.VL53L1X(i2c)
    tof.distance_mode = 1                           # short (to 1.3 m): the target is 60-750 mm away
    tof.timing_budget = 20                          # ms: 50 Hz (short mode only)
    tof.start_ranging()
except Exception as e:                              # noqa: BLE001
    print('S no ToF:', e)
    tof = None

hx = None
try:
    from adafruit_hx711.analog_in import AnalogIn as HXIn
    from adafruit_hx711.hx711 import HX711
    hx_data = digitalio.DigitalInOut(board.D6)
    hx_data.direction = digitalio.Direction.INPUT
    hx_clock = digitalio.DigitalInOut(board.D9)
    hx_clock.direction = digitalio.Direction.OUTPUT
    hx = HXIn(HX711(hx_data, hx_clock), HX711.CHAN_A_GAIN_128)
except Exception as e:                              # noqa: BLE001
    print('S no HX711:', e)
    hx = None

# ---------------------------------------------------------------------------------------------------- state
NS = 1_000_000
t_run = t_vbus = t_sense = t_print = t_status = time.monotonic_ns()
seq_run = seq_vbus = seq_sense = 0
v_max, v_min, v_sum, v_n = 0.0, 1e9, 0.0, 0
height_mm, tof_status = 0, 255
load_raw, load_zero, load_ok = 0, None, False
host_state = 0
was_closed = False
sent = errors = 0


def read_vbus():
    return vbus_adc.value / 65535 * VREF * SETTINGS['vbus_ratio'] * SETTINGS['vbus_trim']


def force_n():
    if load_zero is None or not SETTINGS['load_n_per_count']:
        return 0.0
    return (load_raw - load_zero) * SETTINGS['load_n_per_count'] * SETTINGS['load_sign']


def send(cid, data):
    global sent, errors
    try:
        can.send(canio.Message(id=cid, data=data, extended=False))
        sent += 1
    except Exception:                               # noqa: BLE001 - a bus-off or a full queue: keep the loop alive
        errors += 1


def led():
    if PIX is None:
        return
    closed = pendant.value
    colour = {0: (0, 40, 0), 1: (60, 40, 0), 2: (80, 0, 0), 3: (80, 0, 80)}.get(host_state, (0, 0, 40))
    PIX[0] = colour if closed or host_state == 0 else tuple(c // 4 for c in colour)


# ---------------------------------------------------------------------------------------------------- the loop
while True:
    now = time.monotonic_ns()
    closed = pendant.value
    # the bus voltage, as often as the loop runs
    v = read_vbus()
    v_max, v_min, v_sum, v_n = max(v_max, v), min(v_min, v), v_sum + v, v_n + 1
    # RUN: on the schedule, and at once when the pendant is let go
    if now - t_run >= 10 * NS or (was_closed and not closed):
        # bit1, the coil: the off-delay relay closes it whenever the pendant is held (not sensed separately)
        flags = (1 if closed else 0) | (2 if closed else 0) | (4 if tof is not None and tof_status == 0 else 0) | (8 if load_ok else 0)
        send(F.RUN, F.pack_run(closed, seq_run, flags))
        seq_run += 1
        t_run = now
    was_closed = closed
    if now - t_vbus >= 10 * NS and v_n:
        send(F.VBUS, F.pack_vbus(v_max, v_min, v_sum / v_n, seq_vbus))
        seq_vbus += 1
        v_max, v_min, v_sum, v_n = 0.0, 1e9, 0.0, 0
        t_vbus = now
    # the sensors, when they have something
    if tof is not None:
        try:
            if tof.data_ready:
                d = tof.distance                    # cm, or None when out of range
                tof_status = getattr(tof, 'range_status', 0) if d is not None else 255
                height_mm = int(d * 10) if d is not None else 0
                tof.clear_interrupt()
        except Exception:                           # noqa: BLE001
            tof_status = 254
    if hx is not None and not hx_data.value:        # DOUT low: a conversion is ready, so the read does not wait
        try:
            load_raw = hx.value
            if load_zero is None:
                load_zero = load_raw                # tare at power-up: nothing on the cell
            load_ok = True
        except Exception:                           # noqa: BLE001
            load_ok = False
    if now - t_sense >= 20 * NS:
        send(F.SENSE, F.pack_sense(height_mm, tof_status, force_n(), seq_sense))
        seq_sense += 1
        t_sense = now
    # the laptop's state, for the LED
    m = host_in.receive()
    if m is not None and len(m.data) >= 1:
        host_state = m.data[0]
    # the serial: the force for the bench, a status line, a tare on request
    if now - t_print >= 100 * NS:
        print('F %.1f' % force_n())
        t_print = now
    if now - t_status >= 1000 * NS:
        print('S pendant %d vbus %.2f height %d tof %d raw %d sent %d errors %d host %d' %
              (closed, v, height_mm, tof_status, load_raw, sent, errors, host_state))
        led()
        t_status = now
    if supervisor.runtime.serial_bytes_available:   # one character at a time: never waits for a whole line
        if sys.stdin.read(1) == 't':
            load_zero = load_raw
            print('S tared at', load_zero)
