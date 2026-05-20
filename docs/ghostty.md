# Ghostty Configuration

Optimized setup for `mqlaunch`, `mq-mcp`, and macOS workflows.

## Configuration File

Save the following content to `~/.config/ghostty/config` or `~/Library/Application Support/com.mitchellh.ghostty/config.ghostty`.

```ini
# ==================================================
# Ghostty — HAL / mqlaunch Full Setup
# macOS
# Optimized for:
# - mqlaunch
# - HAL workflows
# - repo-signal
# - mq-mcp
# - dropdown / quake terminal
# ==================================================

# ==================================================
# TYPOGRAPHY
# ==================================================

font-size = 14

# Recommended fonts:
# font-family = JetBrains Mono
# font-family = Berkeley Mono
# font-family = SF Mono

adjust-cell-height = 0%
adjust-cell-width = 0%

# ==================================================
# WINDOW / LAYOUT
# ==================================================

window-width = 138
window-height = 40

window-step-resize = true
window-save-state = always

window-padding-x = 6
window-padding-y = 4
window-padding-balance = true

window-theme = auto
window-colorspace = srgb

# ==================================================
# macOS WINDOW STYLE
# ==================================================

macos-titlebar-style = transparent
macos-window-buttons = hidden

# Alternative:
# macos-titlebar-style = hidden

macos-option-as-alt = true

# ==================================================
# QUICK TERMINAL / DROPDOWN
# ==================================================
#
# This is the Quake-style dropdown terminal.
# Use via:
# Ghostty → Settings → Quick Terminal
#
# Suggested hotkeys:
# - F12
# - CMD + `
#

quick-terminal-position = top
quick-terminal-size = 42%
quick-terminal-animation-duration = 0.12

# ==================================================
# BACKGROUND / VISUALS
# ==================================================

background-opacity = 0.96
background-opacity-cells = false
background-blur = true

unfocused-split-opacity = 0.92

# ==================================================
# CURSOR / INTERACTION
# ==================================================

cursor-style = block
cursor-style-blink = false

mouse-hide-while-typing = true

copy-on-select = clipboard
clipboard-paste-protection = true

link-url = true
confirm-close-surface = true

# ==================================================
# SHELL / WORKING DIRECTORY
# ==================================================

shell-integration = detect
shell-integration-features = no-cursor,sudo,title,ssh-env

working-directory = home

window-inherit-working-directory = true
tab-inherit-working-directory = true
split-inherit-working-directory = true

# ==================================================
# STARTUP COMMAND
# ==================================================
#
# Starts mqlaunch automatically.
# Comment this out if you want normal shell startup.
#

command = /bin/zsh -lc mqlaunch

# ==================================================
# SCROLLBACK / OVERLAYS
# ==================================================

scrollback-limit = 50000000

resize-overlay = after-first
resize-overlay-position = bottom-right
resize-overlay-duration = 600ms

# ==================================================
# TABS / SPLITS
# ==================================================

maximize = false

# ==================================================
# KEYBINDS
# ==================================================

# Config
keybind = cmd+shift+o=open_config
keybind = cmd+shift+r=reload_config

# New window / tabs
keybind = cmd+t=new_tab
keybind = cmd+w=close_surface

# Splits
keybind = cmd+shift+d=new_split:right
keybind = cmd+shift+enter=new_split:down

# Move between splits
keybind = cmd+alt+left=goto_split:left
keybind = cmd+alt+right=goto_split:right
keybind = cmd+alt+up=goto_split:up
keybind = cmd+alt+down=goto_split:down

# Resize splits
keybind = cmd+ctrl+left=resize_split:left,20
keybind = cmd+ctrl+right=resize_split:right,20
keybind = cmd+ctrl+up=resize_split:up,10
keybind = cmd+ctrl+down=resize_split:down,10

# Split helpers
keybind = cmd+alt+e=equalize_splits
keybind = cmd+alt+z=toggle_split_zoom
keybind = cmd+alt+0=reset_window_size

# Font size
keybind = cmd+plus=increase_font_size:1
keybind = cmd+minus=decrease_font_size:1
keybind = cmd+0=reset_font_size

# ==================================================
# THEME — ICE HAL
# ==================================================

background = 0f1419
foreground = d8e2eb

cursor-color = 7dd3fc
cursor-text = 0f1419

selection-background = 233041
selection-foreground = e6edf3

palette = 0=11161c
palette = 1=ff7b72
palette = 2=7ee787
palette = 3=e3b341
palette = 4=79c0ff
palette = 5=d2a8ff
palette = 6=7ee7ff
palette = 7=c9d1d9
palette = 8=6e7681
palette = 9=ffa198
palette = 10=56d364
palette = 11=e3b341
palette = 12=79c0ff
palette = 13=bc8cff
palette = 14=39c5cf
palette = 15=f0f6fc

# ==================================================
# PERFORMANCE
# ==================================================

gtk-single-instance = true

# ==================================================
# RECOMMENDED mqlaunch ALIASES
# ==================================================
#
# Add these to ~/.zshrc if desired:
#
# alias hal="mqlaunch"
# alias doctor="mqlaunch doctor"
# alias ask="mqlaunch ask"
# alias review="mqlaunch review"
# alias repo="repo-signal"
#
# ==================================================
# END
# ==================================================
```

## Verification

After saving the file, run the following command to verify that Ghostty loads the correct configuration:

```bash
ghostty +show-config
```
