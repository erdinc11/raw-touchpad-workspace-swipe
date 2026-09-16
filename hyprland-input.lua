-- Add this snippet to the user's Hyprland Lua input configuration.
-- The raw service handles three-finger workspace swipes.
hl.config({
  input = {
    touchpad = {
      tap_to_click = true,
      disable_while_typing = false,
    },
  },
})

-- libinput maps a three-finger tap to the middle mouse button. Consume it
-- without disabling one- or two-finger tap-to-click.
hl.bind("mouse:274", hl.dsp.exec_cmd("true"), { mouse = true })

-- If Hyprgrass is installed, consume its three-finger tap gesture as well.
if hl.plugin.hyprgrass then
  hl.plugin.hyprgrass.bind {
    pattern = { kind = "tap", fingers = 3 },
    action = hl.dsp.exec_cmd("true"),
  }
end
