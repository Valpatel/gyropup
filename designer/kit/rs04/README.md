# RS-04 in the browser

A configuration tool for RobStride RS-04 actuators, and the pieces it is made of: the RS-04's private CAN protocol as
ES modules, a safety guard on every frame, a software motor, a bus client and three transports. Plain ES modules, no
build step, no dependencies, nothing from the page that uses them. MIT licensed (`LICENSE` in this folder).

```html
<link rel="stylesheet" href="kit/rs04/tool.css">
<div id="tool"></div>
<script type="module">
  import { mountMotorTool, createEmulatorTransport, createBridgeTransport } from './kit/rs04/index.js';
  mountMotorTool(document.getElementById('tool'), {
    profiles: [myProfile],                                   // limits: see "Profiles" below
    joints: [{ id: 1, key: 'hip', name: 'Hip' }],            // the CAN id each joint gets
    poses: [{ key: 'stop', name: 'On the stop', text: 'Hold the link on its stop.', source: 'my-doc.md' }],
    transports: {
      bridge: { label: 'SocketCAN bridge', open: () => createBridgeTransport(`ws://${location.host}/ws`) },
      emu: { label: 'Emulator', open: async () => createEmulatorTransport({ motors: [{ id: 127 }] }) },
    },
  });
</script>
```

Gyropup's page is [`designer/motor-tool.html`](../../motor-tool.html) with [`motor-tool.js`](../../motor-tool.js);
how to run it on real motors is in [docs/rs04-motor-tool.md](../../../docs/rs04-motor-tool.md).

| File | What it gives you |
|---|---|
| `protocol.js` | Frames: `packGetId`, `packEnable`, `packStop`, `packVersion`, `packZero`, `packSetId`, `packMit`, `packRead`, `packWrite`, `packSave`, `packReport`; `parse` (motor -> host) and `parseRequest` (host -> motor); the parameter table `PARAMS` with the manual's ranges; `f2u`/`u2f` (the manual's float_to_uint). A port of `rig/rs04.py` |
| `guard.js` | `createGuard(limits)`: `check(frame)` refuses what the tool must never send, `observe(frame)` learns from replies, `arm(ids)`/`disarm()`, `stopTargets()`. The same rules as `rig/rs04_guard.py` |
| `emulator.js` | `EmulatedRS04` (a port of `rig/rs04_emu.py`: MIT law, `limit_torque` clip, canTimeout watchdog, a small plant) and `VirtualBus` |
| `client.js` | `createClient(transport, {limits})`: `scan`, `read`, `readAll`, `write`, `writeCheck`, `save`, `zero`, `setId`, `version`, `enable`, `mit`, `stopAll`, `arm`. Every frame goes through the guard |
| `transports.js` | `createBridgeTransport(url)` (the SocketCAN bridge, `rig/rs04_bridge.py`), `createEmulatorTransport({motors})`, `createSlcanTransport(port)` (Web Serial, slcan firmware; untested on hardware) |
| `tool.js`, `tool.css` | `mountMotorTool(el, options)`: the page. `diffParams(live, want)` for config comparisons |
| `plot.js` | `createStrip(parent, {title, unit})`: a canvas strip chart |
| `vectors.json` | Golden vectors generated from the Python (`python -m rig.rs04_vectors`): frames, scaling, parsing, the guard's verdicts and a scripted emulator session |
| `rs04.test.mjs` | `node --test designer/kit/rs04/rs04.test.mjs` |

## Profiles

A profile's `limits` are what the guard enforces: `limit_torque_nm` (no write above it), `jog_torque_nm`,
`jog_speed_rad_s`, `jog_kp_max`, `jog_kd_max` (an armed motor's limits), `can_timeout_ticks` and
`can_timeout_max_ticks` (the CAN watchdog stays on, at most this long). `motor_config` is what a configured motor holds.
Gyropup's are in `hardware/actuators/rs04/profiles/`.

## The safety rules

- Nothing is enabled without `arm(ids)`, and only after the motor answered a scan and read back, within 10 s, run mode 0
  (MIT), `limit_torque` at or under the jog torque and `canTimeout` on.
- Jog frames stay inside the jog torque, speed and gains; no write sets `limit_torque` over the cap, turns `canTimeout`
  off, selects another run mode or sets a current, speed or position command; nothing is written to, zeroed,
  renumbered or saved on an armed motor; bit-rate and protocol changes are never sent.
- STOP (the button, Space or Esc while connected) sends a stop to every motor seen; hiding the tab, a failed jog frame,
  a speed past 1.5x the jog speed or a motor leaving run mode does too. The bridge stops every motor it has seen when
  the tab closes, its connection drops or it goes quiet for 1 s while armed; the motor's own `canTimeout` stops it
  after 0.1 s without a frame.

## Adopt or build (surveyed 2026-11-03)

| Candidate | What it is | Licence | Choice |
|---|---|---|---|
| [RobStride Motor Studio](https://github.com/RobStride/MotorStudio) | The vendor's Windows tool: parameters, firmware upgrades | none stated (all rights reserved), binary | Reference only. Use it for a firmware upgrade if RobStride asks for one |
| [RobStride/Python_Sample](https://github.com/RobStride/Python_Sample) | The vendor's Python sample | MIT | Already the cross-check of `rig/rs04.py`; the port follows `rig/rs04.py`, nothing to vendor |
| [sirwart/robstride](https://github.com/sirwart/robstride), [ROBSTRIDE-DYNAMICS Python SDK](https://github.com/ROBSTRIDE-DYNAMICS/Robstride-Dynamics-Python-SDK), [kscalelabs/robstride](https://github.com/kscalelabs/robstride) | Python drivers on python-can | MIT | Not adopted: `rig/rs04.py` covers the protocol with tests, and python-can would be one more dependency on the robot |
| [jgillick/CyberGearDashboard](https://github.com/jgillick/CyberGearDashboard) | Qt desktop dashboard for the Xiaomi CyberGear (RobStride's earlier motor) | MIT | Ideas only (the parameter table, live plots); desktop Python, another motor |
| [xiaomi_cybergear_web_simple_control](https://github.com/xuchengithub/xiaomi_cybergear_web_simple_control) | A web control page for the CyberGear | none | Not usable |
| [python-can-remote](https://github.com/christiansandberg/python-can-remote) | CAN over a websocket for python-can, with a traffic view | MIT | The closest fit. Not adopted: it relays raw frames with no safety filter or origin check and needs python-can; the bridge here is standard-library Python with the guard |
| [socketcand](https://github.com/linux-can/socketcand) | SocketCAN over TCP, ASCII | BSD-3-Clause / GPL-2.0 | A browser cannot open TCP; it would need a websocket proxy as well |
| [DearFDCAN_Web](https://github.com/Pe3ucTop/DearFDCAN_Web) | WebUSB gs_usb viewer (C++, WASM) | Apache-2.0 | Not adopted: on Linux the gs_usb driver holds the adapter, so WebUSB cannot claim it, and a PEAK adapter has no WebUSB path |
| [webserial_slcan](https://github.com/sicrisembay/webserial_slcan) | Web Serial slcan (Dart) | none | Not usable; slcan is a one-page ASCII protocol, written in `transports.js` |
| [uPlot](https://github.com/leeoniya/uPlot) | Canvas charts | MIT | Not adopted: five strip charts are 60 lines (`plot.js`) |
| PEAK PCAN-View, PCAN-Basic | The vendor's tools and API | proprietary | Not needed: Linux's mainline `peak_usb` driver makes a PCAN-USB a SocketCAN interface |

No third-party code is vendored here.

## Credits

The protocol follows the RS04 User Manual (RobStride, 260713) and RobStride's MIT-licensed Python_Sample, through
`rig/rs04.py`, which records where each layout comes from and the two places the sources differ.
