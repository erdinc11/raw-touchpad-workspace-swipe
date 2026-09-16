# Raw Touchpad Workspace Swipe

A dependency-free raw Linux input recognizer for fast three-finger workspace
swipes on older Synaptics PS/2 touchpads.

The recognizer observes the touchpad without grabbing it. Libinput therefore
continues to provide pointer movement, scrolling, and normal one- and
two-finger tap-to-click. The service reads `BTN_TOOL_TRIPLETAP` plus the
touchpad's multitouch coordinates and dispatches a workspace change as soon as
horizontal movement is detected.

## Features

- Fast three-finger horizontal workspace switching.
- Supports Synaptics devices that expose two MT slots plus
  `BTN_TOOL_TRIPLETAP`.
- Creates at most one empty workspace and reuses it for forward swipes.
- Does not require Python packages.
- Leaves normal one- and two-finger tap-to-click enabled.
- Temporarily disables tap-to-click during a three-finger contact, preventing
  a swipe release from clicking the underlying window.

## Install

The installer needs `sudo` because the service must read the raw touchpad
event device. It grants the service read-only access to the detected touchpad
node through a systemd device policy; it does not change global device
permissions.

```sh
chmod +x install.sh
./install.sh
```

The installer detects the current user, UID, stable touchpad path, and event
node, then enables `three-finger-workspace.service`.

Add [`hyprland-input.lua`](hyprland-input.lua) to the user's Hyprland Lua
input configuration. It keeps normal tap-to-click enabled and consumes the
middle-button event used by three-finger taps.

## Uninstall

```sh
sudo systemctl disable --now three-finger-workspace.service
sudo rm /etc/systemd/system/three-finger-workspace.service
sudo systemctl daemon-reload
rm -f "$HOME/.local/bin/three-finger-workspace.py"
```

## Configuration

Edit `MIN_X_DELTA` in `three-finger-workspace.py` to change the horizontal
trigger distance. Lower values trigger sooner but can make small finger
movements count as swipes.

The default mapping is:

- Fingers moving left: next workspace (`r+1`)
- Fingers moving right: previous workspace (`r-1`)

When moving left from a non-empty workspace, an existing empty workspace is
reused. If none exists, one is created. Moving left while already on an empty
workspace is ignored, so repeated swipes cannot create more empty workspaces.

## Development checks

```sh
python3 -m py_compile three-finger-workspace.py
systemctl status three-finger-workspace.service
journalctl -u three-finger-workspace.service -n 50 --no-pager
```

## Security notes

The service runs as the desktop user with the `input` supplementary group, no
Linux capabilities, a read-only system view, and a closed systemd device
policy allowing only the detected touchpad event node. Do not add broad raw
input permissions unless the device policy must be changed for a particular
hardware layout.

See [AGENTS.md](AGENTS.md) for repository instructions.
