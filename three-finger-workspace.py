#!/usr/bin/env python3
"""Minimal raw three-finger swipe recognizer for a PS/2 touchpad.

It observes the touchpad event stream without grabbing it, so libinput keeps
handling scrolling and tap-to-click.  Once a horizontal three-finger movement
passes the threshold, it asks Hyprland to change workspace immediately.
"""

import glob
import os
import struct
import subprocess
import time


DEVICE = "/dev/input/by-path/platform-i8042-serio-1-event-mouse"
EVENT = struct.Struct("<qqHHi")

EV_SYN = 0
EV_ABS = 3
EV_KEY = 1
SYN_REPORT = 0

ABS_X = 0
ABS_Y = 1
ABS_MT_SLOT = 47
ABS_MT_POSITION_X = 53
ABS_MT_POSITION_Y = 54
ABS_MT_TRACKING_ID = 57
BTN_TOOL_TRIPLETAP = 334

# This is deliberately small enough to trigger early, while requiring real
# horizontal motion.  The values are in the touchpad's raw coordinate units.
MIN_X_DELTA = 15
MAX_Y_DELTA = 260
HORIZONTAL_DOMINANCE = 1.20


def find_device():
    while True:
        if os.access(DEVICE, os.R_OK):
            return DEVICE
        time.sleep(1)


def hyprland_env():
    env = os.environ.copy()
    if env.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return env

    runtime = env.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    candidates = []
    for directory in glob.glob(os.path.join(runtime, "hypr", "*")):
        if os.path.exists(os.path.join(directory, ".socket.sock")):
            candidates.append(directory)
    if candidates:
        latest = max(candidates, key=os.path.getmtime)
        env["HYPRLAND_INSTANCE_SIGNATURE"] = os.path.basename(latest)
    return env


def set_tap_to_click(enabled):
    value = "true" if enabled else "false"
    code = (
        "hl.config({ input = { touchpad = { tap_to_click = "
        f"{value} }} }})"
    )
    try:
        result = subprocess.run(
            ["/usr/bin/hyprctl", "eval", code],
            env=hyprland_env(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=0.5,
            check=False,
        )
        if result.returncode != 0:
            print(
                f"tap-to-click toggle failed rc={result.returncode} "
                f"out={result.stdout.strip()!r}",
                flush=True,
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("tap-to-click toggle unavailable or timed out", flush=True)


def change_workspace(delta):
    # With Hyprland's usual swipe direction, moving fingers left means next
    # workspace and moving fingers right means previous workspace.
    # `r` walks workspace IDs including empty workspaces.  `e` would wrap
    # from the last existing workspace back to the first one.
    target = "r+1" if delta < 0 else "r-1"
    try:
        result = subprocess.run(
            [
                "/usr/bin/hyprctl",
                "eval",
                f'hl.dispatch(hl.dsp.focus({{ workspace = "{target}" }}))',
            ],
            env=hyprland_env(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=0.5,
            check=False,
        )
        print(
            f"raw 3f swipe dx={delta:.0f} target={target} "
            f"rc={result.returncode} out={result.stdout.strip()!r} err={result.stderr.strip()!r}",
            flush=True,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("raw 3f swipe: hyprctl unavailable or timed out", flush=True)


def run():
    slots = {}
    slot = 0
    sequence_started = False
    sequence_finished = False
    triggered = False
    start = None
    last_x = None
    direction_sign = 0
    direction_steps = 0
    tripletap = False
    tap_suppressed = False

    # Restore the normal state after a service restart during a touch.
    set_tap_to_click(True)

    while True:
        device = find_device()
        try:
            fd = os.open(device, os.O_RDONLY | os.O_CLOEXEC)
        except OSError:
            time.sleep(1)
            continue

        buffer = b""
        try:
            while True:
                chunk = os.read(fd, EVENT.size * 32)
                if not chunk:
                    break
                buffer += chunk
                usable = len(buffer) - (len(buffer) % EVENT.size)
                data, buffer = buffer[:usable], buffer[usable:]

                for offset in range(0, len(data), EVENT.size):
                    _, _, event_type, code, value = EVENT.unpack_from(data, offset)

                    if event_type == EV_ABS:
                        if code == ABS_MT_SLOT:
                            slot = value
                            slots.setdefault(slot, {"tracking": -1, "x": 0, "y": 0})
                        elif code == ABS_MT_TRACKING_ID:
                            slots.setdefault(slot, {"tracking": -1, "x": 0, "y": 0})
                            slots[slot]["tracking"] = value
                        elif code == ABS_MT_POSITION_X:
                            slots.setdefault(slot, {"tracking": -1, "x": 0, "y": 0})["x"] = value
                        elif code == ABS_MT_POSITION_Y:
                            slots.setdefault(slot, {"tracking": -1, "x": 0, "y": 0})["y"] = value
                    elif event_type == EV_KEY and code == BTN_TOOL_TRIPLETAP:
                        tripletap = value > 0
                        if tripletap:
                            if not tap_suppressed:
                                set_tap_to_click(False)
                                tap_suppressed = True
                            print("raw 3f contact", flush=True)

                    if event_type != EV_SYN or code != SYN_REPORT:
                        continue

                    active = [point for point in slots.values() if point["tracking"] >= 0]
                    # This device briefly reports one slot while the second
                    # slot is being updated. Do not use that incomplete frame
                    # as the gesture origin or cancel an already started one.
                    if tripletap and len(active) < 2:
                        continue

                    finger_count = 3 if tripletap else len(active)
                    if not tripletap and finger_count == 0:
                        if tap_suppressed:
                            set_tap_to_click(True)
                            tap_suppressed = False
                        sequence_started = False
                        sequence_finished = False
                        triggered = False
                        start = None
                        last_x = None
                        direction_sign = 0
                        direction_steps = 0
                        continue

                    # This Synaptics PS/2 device exposes only two MT slots,
                    # while BTN_TOOL_TRIPLETAP tells us that three fingers
                    # are down.  The reported slots still move with the
                    # gesture, so their centroid is sufficient here.
                    if finger_count != 3 or not active:
                        if sequence_started:
                            sequence_finished = True
                        continue

                    if sequence_finished:
                        continue

                    center_x = sum(point["x"] for point in active) / len(active)
                    center_y = sum(point["y"] for point in active) / len(active)
                    if not sequence_started:
                        sequence_started = True
                        start = (center_x, center_y)
                        last_x = center_x
                        direction_sign = 0
                        direction_steps = 0
                        print(
                            f"raw 3f start x={center_x:.0f} y={center_y:.0f} slots={len(active)}",
                            flush=True,
                        )
                        continue

                    if triggered or start is None:
                        continue

                    delta_x = center_x - start[0]
                    delta_y = center_y - start[1]
                    step_x = center_x - last_x
                    last_x = center_x
                    if abs(step_x) >= 8:
                        step_sign = 1 if step_x > 0 else -1
                        if direction_sign != step_sign:
                            # A slot-transition jump changed direction. Use
                            # the current frame as a fresh gesture origin.
                            direction_sign = step_sign
                            direction_steps = 1
                            start = (center_x, center_y)
                            delta_x = 0
                        else:
                            direction_steps += 1
                    if tripletap:
                        print(
                            f"raw 3f move dx={delta_x:.0f} dy={delta_y:.0f} slots={len(active)}",
                            flush=True,
                        )
                    # Synaptics' second reported slot can cause large Y
                    # jumps even during a horizontal swipe.  X displacement
                    # is the reliable signal on this device.
                    if direction_steps >= 2 and abs(delta_x) >= MIN_X_DELTA:
                        change_workspace(delta_x)
                        triggered = True
        finally:
            os.close(fd)
            time.sleep(0.2)


if __name__ == "__main__":
    run()
