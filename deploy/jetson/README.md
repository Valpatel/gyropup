# Deployment on the robot's Jetson

What runs on the robot's computer, installed by one command. Written for JetPack Linux in general (Ubuntu with
systemd and SocketCAN), so it works on either module the robot may carry: the J501 carrier's Jetson AGX Orin
(JetPack 6, Ubuntu 22.04, Python 3.10) or a Jetson AGX Thor (JetPack 7). **Which Jetson is the robot's computer is an
open question for the owner** ([hardware/compute/robot-computer](../../hardware/compute/robot-computer/README.md)).

```bash
git clone https://github.com/Valpatel/gyropup.git /opt/gyropup     # or wherever: the units point at this checkout
cd /opt/gyropup
deploy/jetson/install.sh --dry-run          # what it would change; changes nothing
sudo deploy/jetson/install.sh               # install or update; run it again after every pull
sudo deploy/jetson/install.sh --list-can    # the CAN adapters, their USB paths and serials
sudo deploy/jetson/install.sh --enable-bridge   # start the RS-04 bridge now and at boot (127.0.0.1:8765)
```

It is idempotent: a second run reports `0 change(s)`, and the two settings files in `/etc/gyropup/` are written once
and never overwritten. CI runs its dry run, a staged install, the idempotence, the name rules and shellcheck
(`python3 deploy/jetson/test_install.py`, workflow `jetson-deploy`).

## What it installs

| File | What it does |
|---|---|
| `/etc/modules-load.d/gyropup-can.conf` | loads `can`, `can_raw`, `peak_usb` (PEAK PCAN-USB) and `gs_usb` (candleLight) at boot |
| `/etc/udev/rules.d/80-gyropup-can.rules` | when a `peak_usb` or `gs_usb` CAN interface appears, starts `gyropup-can@<name>` |
| `/etc/systemd/system/gyropup-can@.service` | `ip link set <name> type can bitrate 1000000 restart-ms 100`, `txqueuelen 1000`, up |
| `/etc/udev/rules.d/70-gyropup-can-names.rules` | stable names from `/etc/gyropup/can-names.conf` (by USB port or serial) |
| `/etc/sysusers.d/gyropup.conf` | the unprivileged `gyropup-bridge` user |
| `/etc/systemd/system/gyropup-rs04-bridge.service` | `python3 -m rig.rs04_bridge` from this checkout, hardened, restarted on failure; installed, enabled only with `--enable-bridge` |
| `/etc/gyropup/can.env` | `BITRATE=1000000`, `RESTART_MS=100`, `TXQUEUELEN=1000` (yours to edit) |
| `/etc/gyropup/rs04-bridge.env` | `IFACE`, `PROFILE` (`pla-bench`), `PORT` (yours to edit) |

The Jetson's own CAN controllers (mttcan, on the module) are left alone: on the J501 the robot's bus C is its `can0`
(docs/body-electrical.md 4), which the Jetson's software brings up itself.

## Stable names

A USB adapter is `can0`, `can1`… in the order it appears, after the module's own ports. To give each a fixed name,
run `sudo deploy/jetson/install.sh --list-can`, copy [`can-names.conf.example`](can-names.conf.example) to
`/etc/gyropup/can-names.conf`, name each adapter by its USB port (`path=`) or its serial (`serial=`), and run
install.sh again. Then set `IFACE=` in `/etc/gyropup/rs04-bridge.env` to that name.

## The RS-04 bridge on the robot

The leg motors are on the balance MCU's buses A and B, not on the Jetson's CAN. Configuring them from the Jetson
means the MCU powered off and a PCAN-USB on the leg's bus (see the [RS-04 bring-up](../../hardware/actuators/rs04/bring-up.md)).
The bridge listens on 127.0.0.1 only. From a laptop, reach it through SSH:
`ssh -L 8765:127.0.0.1:8765 <the robot>`, then open `http://127.0.0.1:8765/` on the laptop.

**LAN mode (opt-in):** `sudo deploy/jetson/install.sh --lan` adds a drop-in that runs the bridge on every interface
with a random token (`/etc/gyropup/bridge-token`, readable by the bridge's user only); open
`http://<the robot>:8765/?token=<the token>`. A page from any other site is refused either way. `--local` removes it.

## Checks on the robot

```bash
systemctl status 'gyropup-can@*' gyropup-rs04-bridge
ip -details -statistics link show type can        # bit rate 1000000, state ERROR-ACTIVE, no bus-off
journalctl -u gyropup-rs04-bridge -f               # connections, refusals, STOPs
```

## Not yet

- Never run on a Jetson: whether JetPack's kernel ships `peak_usb` is to check (`modinfo peak_usb`); the install
  prints a note if a module is missing.
- No service for the robot's own software yet (the balance MCU link, the people detector): this folder is where it
  goes.
