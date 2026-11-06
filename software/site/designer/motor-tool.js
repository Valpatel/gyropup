// Gyropup's page for the RS-04 configuration tool (designer/motor-tool.html): the reusable tool is designer/kit/rs04/
// (MIT); this gives it Gyropup's build profiles, its four leg joints and the zero poses. On the public site it offers
// the emulator only; served by the bridge (rig/rs04_bridge.py, ?bridge=1) it talks to the real bus.
import { createBridgeTransport, createEmulatorTransport, createSlcanTransport, mountMotorTool } from './kit/rs04/index.js';

const q = new URLSearchParams(location.search);
const viaBridge = q.has('bridge');
const local = viaBridge || ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
const get = async (url) => { const r = await fetch(url, { cache: 'no-store' }); if (!r.ok) throw new Error(`${url}: ${r.status}`); return r.json(); };

// The four leg motors: docs/body-firmware.md (bus A: 1 left front, 2 left rear; bus B: 3 right front, 4 right rear).
// The five-bar leg has two hip motors, front and rear, and no knee motor. The bench leg uses 1 (front) and 2 (rear).
const joints = [
  { id: 1, key: 'left-front', name: 'Left leg, front hip' }, { id: 2, key: 'left-rear', name: 'Left leg, rear hip' },
  { id: 3, key: 'right-front', name: 'Right leg, front hip' }, { id: 4, key: 'right-rear', name: 'Right leg, rear hip' }];
const poses = [
  { key: 'knee-out-bare', name: 'Upper link on its bare knee-out stop post',
    text: 'Hold the motor\'s upper link against its knee-out stop post, bare: the TPU sleeve is not on yet (steel on PA6-CF is a repeatable contact, a sleeve would squeeze). This is the zero the firmware\'s placeholder calibration assumes.',
    source: 'rig/calibrate.py (leg assembly step 11); docs/body-firmware.md, the calibration placeholder' },
  { key: 'bench-bare', name: 'Bare motor on the bench (commissioning only)',
    text: 'A motor on its own with nothing on its output, as in C1-C6. A zero set here is only for commissioning: set it again on the leg at the knee-out post.',
    source: 'docs/leg-bench-tests.md, C1-C6' }];

const index = await get('../hardware/actuators/rs04/profiles/index.json');
const profiles = await Promise.all(index.profiles.map(n => get(`../hardware/actuators/rs04/profiles/${n}.json`)));

// The PLA bench's thermal limits come from the motor heat model's export, read live (never copied into the profile).
async function describeProfile(p) {
  const ref = (p.references || []).find(r => r.file.endsWith('motor_thermal.json'));
  if (!ref) return [];
  try {
    const bench = (await get('../' + ref.file)).bench;
    const room = bench.limits.find(l => l.room_c === 25) || bench.limits[0];
    return [`Motor heat model (${ref.file}): stop when a motor's case passes ${bench.face_limit_c} °C; about ${room.torque_nm} N m held per motor indefinitely in a ${room.room_c} °C room.`];
  } catch { return [`Motor heat model: ${ref.file} is not published yet${ref.pending ? ` (${ref.pending})` : ''}.`]; }
}

const transports = {};
if (viaBridge) {
  const token = q.get('token');
  transports.bridge = { label: 'SocketCAN bridge (real bus)', open: () => createBridgeTransport(
    `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws${token ? '?token=' + encodeURIComponent(token) : ''}`) };
}
transports.emu1 = { label: 'Emulator: one new motor (id 127)', open: async () => createEmulatorTransport({ motors: [{ id: 127 }] }) };
transports.emu4 = { label: 'Emulator: the four leg motors (ids 1-4)', open: async () => createEmulatorTransport({ motors: joints.map(j => ({ id: j.id })) }) };
if (local && 'serial' in navigator)
  transports.slcan = { label: 'Web Serial slcan adapter (untested)', open: async () => createSlcanTransport(await navigator.serial.requestPort()) };

const tool = mountMotorTool(document.getElementById('tool'), { profiles, joints, poses, transports, describeProfile });
window.gyropupMotorTool = tool;
document.body.dataset.ready = '1';
if (q.get('connect')) tool.connect(q.get('connect'));
