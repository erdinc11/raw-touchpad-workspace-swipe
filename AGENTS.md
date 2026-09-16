# Agent Instructions

## Scope

This repository contains a small raw Linux input daemon and its systemd
installer for three-finger touchpad workspace swipes.

## Editing rules

- Keep all source, comments, documentation, and commit messages in English.
- Keep the runtime dependency-free unless there is a strong reason to add a
  package dependency.
- Preserve normal pointer movement, scrolling, and one/two-finger tap-to-click.
- Keep tap-to-click disabled only for the lifetime of a three-finger contact;
  restore it after release.
- Do not grab the touchpad unless the design also preserves all normal pointer
  behavior.
- Keep raw-device access read-only and limited to the detected touchpad node.
- Do not hard-code a username, UID, event number, or Hyprland instance
  signature in tracked files. Resolve them during installation or runtime.
- Do not store passwords, tokens, or machine-specific logs in the repository.

## Validation

Run `python3 -m py_compile three-finger-workspace.py` after code changes.
When testing on a Hyprland host, verify the service status and journal, then
test both swipe directions and one/two-finger tap-to-click.

## Behavior contract

- A leftward three-finger swipe selects `r+1`.
- A rightward three-finger swipe selects `r-1`.
- The gesture should trigger once per contact sequence.
- A transient one-slot report from Synaptics hardware must not cancel an
  otherwise valid three-finger gesture.
