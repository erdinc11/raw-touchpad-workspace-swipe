#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install_user=${SUDO_USER:-$(id -un)}
user_id=$(id -u "$install_user")
user_home=$(getent passwd "$install_user" | cut -d: -f6)
device_link=/dev/input/by-path/platform-i8042-serio-1-event-mouse

if [ ! -e "$device_link" ]; then
    echo "Touchpad device not found at $device_link" >&2
    exit 1
fi

device_node=$(readlink -f "$device_link")
if [ ! -c "$device_node" ]; then
    echo "Resolved touchpad path is not a character device: $device_node" >&2
    exit 1
fi

service_file=$(mktemp)
trap 'rm -f "$service_file"' EXIT

sed \
    -e "s|@USER@|$install_user|g" \
    -e "s|@UID@|$user_id|g" \
    -e "s|@HOME@|$user_home|g" \
    -e "s|@DEVICE@|$device_node|g" \
    "$project_dir/three-finger-workspace.service.in" > "$service_file"

install -Dm755 "$project_dir/three-finger-workspace.py" \
    "$user_home/.local/bin/three-finger-workspace.py"
sudo install -Dm644 "$service_file" \
    /etc/systemd/system/three-finger-workspace.service
sudo systemctl daemon-reload
sudo systemctl enable --now three-finger-workspace.service

echo "Installed three-finger-workspace.service for $install_user."
echo "Touchpad node: $device_node"
