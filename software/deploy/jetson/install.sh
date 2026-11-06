#!/usr/bin/env bash
# Gyropup on the robot's Jetson (JetPack Linux: an AGX Orin on the J501 carrier or an AGX Thor): SocketCAN for USB
# CAN adapters at 1 Mbit/s, stable adapter names, and the RS-04 configuration bridge as a systemd service.
#
#   sudo hardware/deploy/jetson/install.sh                  # install or update; safe to run again (it changes only what differs)
#   hardware/deploy/jetson/install.sh --dry-run             # say what would change, change nothing (no root needed)
#   hardware/deploy/jetson/install.sh --root /tmp/stage     # install into a staging tree (tests, images); runs no systemctl
#   sudo hardware/deploy/jetson/install.sh --list-can       # the CAN interfaces with driver, USB path and serial (for names)
#   sudo hardware/deploy/jetson/install.sh --enable-bridge  # also enable and start the bridge (127.0.0.1:8765)
#   sudo hardware/deploy/jetson/install.sh --lan            # opt-in: the bridge on every interface, with a token
#   sudo hardware/deploy/jetson/install.sh --local          # back to 127.0.0.1 only
#
# What it installs (see hardware/deploy/jetson/README.md):
#   /etc/modules-load.d/gyropup-can.conf                  can, can_raw, peak_usb, gs_usb at boot
#   /etc/systemd/system/gyropup-can@.service              ip link up at $BITRATE when an adapter appears
#   /etc/udev/rules.d/70-gyropup-can-names.rules          stable names from /etc/gyropup/can-names.conf
#   /etc/udev/rules.d/80-gyropup-can.rules                start gyropup-can@<name> for every USB CAN adapter
#   /etc/sysusers.d/gyropup.conf                          the unprivileged gyropup-bridge user
#   /etc/systemd/system/gyropup-rs04-bridge.service       the bridge, run from this checkout
#   /etc/gyropup/can.env, /etc/gyropup/rs04-bridge.env    settings: written once, never overwritten
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
checkout="$(cd "$here/../../.." && pwd)"
root=/
dry=0
enable_bridge=0
lan=""
names=""
list=0

usage() { awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "$0"; }
die() { echo "install.sh: $*" >&2; exit 2; }

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) dry=1 ;;
    --root) root="${2:?--root needs a directory}"; shift ;;
    --checkout) checkout="${2:?--checkout needs a directory}"; shift ;;
    --names) names="${2:?--names needs a file}"; shift ;;
    --enable-bridge) enable_bridge=1 ;;
    --lan) lan=on ;;
    --local) lan=off ;;
    --list-can) list=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option $1 (--help)" ;;
  esac
  shift
done

if [ "$list" = 1 ]; then
  found=0
  for dev in /sys/class/net/*; do
    [ -e "$dev/type" ] && [ "$(cat "$dev/type")" = 280 ] || continue   # ARPHRD_CAN
    found=1
    name="$(basename "$dev")"
    driver="$(basename "$(readlink -f "$dev/device/driver" 2>/dev/null || echo none)")"
    props="$(udevadm info --query=property --path="$dev" 2>/dev/null || true)"
    path="$(printf '%s\n' "$props" | sed -n 's/^ID_PATH=//p')"
    serial="$(printf '%s\n' "$props" | sed -n 's/^ID_SERIAL_SHORT=//p')"
    state="$(cat "$dev/operstate" 2>/dev/null || echo ?)"
    printf '%-12s driver=%-10s state=%-5s path=%s serial=%s\n' "$name" "$driver" "$state" "${path:-?}" "${serial:-none}"
  done
  [ "$found" = 1 ] || echo "no CAN interfaces (is the adapter plugged in? modprobe peak_usb / gs_usb)"
  exit 0
fi

[ -f "$checkout/rig/rs04_bridge.py" ] || die "$checkout is not a Gyropup checkout (no rig/rs04_bridge.py)"
case "$checkout" in /*) ;; *) die "--checkout must be an absolute path" ;; esac
root="${root%/}/"
live=0
if [ "$root" = "/" ] && [ "$dry" = 0 ]; then
  live=1
  [ "$(id -u)" = 0 ] || die "installing on this system needs root: run it again with sudo (or --dry-run, or --root DIR)"
fi
[ -n "$names" ] || names="${root}etc/gyropup/can-names.conf"

changed=0
say() { if [ "$dry" = 1 ]; then echo "would $*"; else echo "$*"; fi; }

# put CONTENT at PATH (under the root) with MODE, only if it differs
put() {
  local rel="$1" mode="$2" content="$3" dest="${root}${1#/}"
  if [ -f "$dest" ] && [ "$(cat "$dest")" = "$content" ] && [ "$(stat -c %a "$dest")" = "$mode" ]; then
    echo "unchanged  $rel"
    return 0
  fi
  if [ -f "$dest" ]; then say "update     $rel"; else say "install    $rel"; fi
  changed=$((changed + 1))
  [ "$dry" = 1 ] && return 0
  mkdir -p "$(dirname "$dest")"
  local tmp; tmp="$(mktemp "$(dirname "$dest")/.gyropup.XXXXXX")"
  printf '%s\n' "$content" > "$tmp"
  chmod "$mode" "$tmp"
  mv -f "$tmp" "$dest"
}
# write once: settings the owner may edit are never overwritten
put_once() {
  local rel="$1" dest="${root}${1#/}"
  if [ -f "$dest" ]; then echo "kept       $rel (yours: not overwritten)"; return 0; fi
  put "$1" "$2" "$3"
}
remove() {
  local rel="$1" dest="${root}${1#/}"
  [ -e "$dest" ] || return 0
  say "remove     $rel"
  changed=$((changed + 1))
  [ "$dry" = 1 ] || rm -f "$dest"
}

# ---------------------------------------------------------------------------------------------- stable names
# No "-": systemd escapes it in the device unit gyropup-can@.service binds to, so a hyphenated name never comes up.
valid_name() { [[ "$1" =~ ^[A-Za-z][A-Za-z0-9_]{0,14}$ ]] && ! [[ "$1" =~ ^can[0-9]+$ ]]; }
name_rules="# Gyropup (hardware/deploy/jetson/install.sh): stable names for USB CAN adapters, from /etc/gyropup/can-names.conf.
# Generated: edit can-names.conf and run install.sh again."
if [ -f "$names" ]; then
  seen=" " seen_match=" "
  while read -r name match rest || [ -n "${name:-}" ]; do     # the last line counts without a newline too
    case "$name" in ''|'#'*) continue ;; esac
    [ -z "${rest:-}" ] || die "$names: one name and one match a line: '$name $match $rest'"
    valid_name "$name" || die "$names: '$name' is not a usable interface name (1-15 of A-Z a-z 0-9 _, a letter first, not canN)"
    case "$seen" in *" $name "*) die "$names: '$name' is named twice" ;; esac
    case "$seen_match" in *" $match "*) die "$names: '$match' is given two names" ;; esac
    seen="$seen$name " seen_match="$seen_match$match "
    key="${match%%=*}" value="${match#*=}"
    [[ "$value" =~ ^[A-Za-z0-9._:+-]+$ ]] || die "$names: '$match' has characters a udev match cannot take"
    case "$key" in
      path) name_rules="$name_rules
SUBSYSTEM==\"net\", ACTION==\"add\", ATTR{type}==\"280\", IMPORT{builtin}=\"path_id\", ENV{ID_PATH}==\"$value\", NAME=\"$name\"" ;;
      serial) name_rules="$name_rules
SUBSYSTEM==\"net\", ACTION==\"add\", ATTR{type}==\"280\", IMPORT{builtin}=\"usb_id\", ENV{ID_SERIAL_SHORT}==\"$value\", NAME=\"$name\"" ;;
      *) die "$names: '$match': use path=... or serial=..." ;;
    esac
  done < "$names"
else
  name_rules="$name_rules
# (no can-names.conf yet: adapters keep their kernel names, can0, can1, ...)"
fi

# ---------------------------------------------------------------------------------------------- files
f="$here/files"
put /etc/modules-load.d/gyropup-can.conf 644 "$(cat "$f/gyropup-can.conf")"
put /etc/systemd/system/gyropup-can@.service 644 "$(cat "$f/gyropup-can@.service")"
put /etc/udev/rules.d/70-gyropup-can-names.rules 644 "$name_rules"
put /etc/udev/rules.d/80-gyropup-can.rules 644 '# Gyropup (hardware/deploy/jetson/install.sh): bring every USB CAN adapter (PEAK peak_usb, candleLight gs_usb) up at the
# configured bit rate as it appears, under its stable name if it has one. The Jetson'"'"'s own mttcan controllers are left alone.
SUBSYSTEM=="net", ACTION=="add", ATTR{type}=="280", DRIVERS=="peak_usb|gs_usb", TAG+="systemd", ENV{SYSTEMD_WANTS}+="gyropup-can@$name.service"'
put /etc/sysusers.d/gyropup.conf 644 "$(cat "$f/gyropup-sysusers.conf")"
put /etc/systemd/system/gyropup-rs04-bridge.service 644 "$(sed "s#@CHECKOUT@#$checkout#" "$f/gyropup-rs04-bridge.service")"
put_once /etc/gyropup/can.env 644 "$(cat "$f/can.env")"
put_once /etc/gyropup/rs04-bridge.env 644 "$(cat "$f/rs04-bridge.env")"

dropin=/etc/systemd/system/gyropup-rs04-bridge.service.d/lan.conf
token=/etc/gyropup/bridge-token
if [ "$lan" = on ]; then
  put "$dropin" 644 '# Gyropup (hardware/deploy/jetson/install.sh --lan): the RS-04 bridge on every interface, with a token. Remove with --local.
[Service]
Environment="BRIDGE_LAN=--lan --token-file /etc/gyropup/bridge-token"'
  if [ ! -f "${root}${token#/}" ]; then
    say "install    $token (a new random token, readable by gyropup-bridge only)"
    changed=$((changed + 1))
    if [ "$dry" = 0 ]; then
      mkdir -p "${root}etc/gyropup"
      ( umask 077; head -c 24 /dev/urandom | base64 | tr -d '/+=\n' > "${root}${token#/}" )
      chmod 640 "${root}${token#/}"
      [ "$live" = 1 ] && chgrp gyropup-bridge "$token" 2>/dev/null || true
    fi
  else
    echo "kept       $token"
  fi
elif [ "$lan" = off ]; then
  remove "$dropin"
fi

# ---------------------------------------------------------------------------------------------- activate
if [ "$live" = 1 ]; then
  systemd-sysusers /etc/sysusers.d/gyropup.conf
  [ -f "$token" ] && chgrp gyropup-bridge "$token" && chmod 640 "$token"
  for m in can can_raw peak_usb gs_usb; do
    modprobe "$m" 2>/dev/null || echo "note: kernel module $m is not available on this kernel (modinfo $m)"
  done
  if [ "$changed" -gt 0 ]; then
    systemctl daemon-reload
    udevadm control --reload
    udevadm trigger --subsystem-match=net --attr-match=type=280 --action=add   # CAN interfaces only
    echo "note: a new or changed name applies when the adapter is next plugged in (unplug it and plug it back)"
  fi
  if [ "$enable_bridge" = 1 ]; then
    systemctl enable --now gyropup-rs04-bridge.service
  fi
  if systemctl is-active --quiet gyropup-rs04-bridge.service && [ "$changed" -gt 0 ]; then
    systemctl restart gyropup-rs04-bridge.service
  fi
fi

if [ "$dry" = 1 ]; then
  echo "dry run: $changed change(s) would be made under $root; nothing was written"
else
  echo "done: $changed change(s) under $root"
  [ "$live" = 1 ] && [ "$enable_bridge" = 0 ] && ! systemctl is-enabled --quiet gyropup-rs04-bridge.service 2>/dev/null \
    && echo "the bridge is installed but not enabled: sudo systemctl enable --now gyropup-rs04-bridge (or --enable-bridge)"
fi
exit 0
