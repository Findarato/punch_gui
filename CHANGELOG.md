# Changelog

## [Unreleased]

### Added
- GitHub Action workflow (`.github/workflows/flatpak.yml`) to build Flatpak on push/PR to `main`, using `flatpak-github-actions` with GNOME 47 runtime
- Desktop entry file (`space.mcharryville.PunchGUI.desktop`) for Flatpak export
- SVG application icon (`space.mcharryville.PunchGUI.svg`)

### Changed
- Updated `space.mcharryville.PunchGUI.json`:
  - App ID: `space.mcharryville.punch_gui` → `space.mcharryville.PunchGUI`
  - Runtime: `org.gnome.Platform` 41 → 47
  - Command: `punch-gui` → `punch_gui.py`
  - Sources: `git` remote → local `dir` source
  - Build commands: `python3 setup.py install` → `install -D` to copy scripts, desktop file, and icon into `/app`
  - Finish args: `--share=network, --socket=xwayland` → `--share=ipc, --socket=x11, --socket=wayland, --device=dri, --share=network`
  - Removed broken `python-runtime` module

## 2026-07-05 — "Updated from a while ago"

### Added
- `IDEA.md` with project description
- `credentials.json.default` with login/password template
- `settings.json.default` now includes `work_sso_location` and `VPN Update Path` keys
- Settings dialog (`SettingsDialog`) as an `Adw.Dialog` with:
  - Path editor rows (ChromeDriver path, VPN interface, SSO URL)
  - Timing spin buttons (antifarm sleep, deviation)
  - Browser toggle switches (headless, maximize, incognito, mute audio)
  - Auto-login toggle
  - Save writes `settings.json`; Cancel discards
- Settings entry added to the hamburger menu
- `notes.md` added to `.gitignore`

### Changed
- Selenium punch-in now reads `work_sso_location` from settings instead of hardcoded URL
- Test data loading re-enabled on startup

## 2026-03-20 15:29 — "Forgot to include the creds"

### Added
- Filled `credentials.json.default` with login/password JSON template

## 2026-03-20 15:28 — "Pulled in some things from the CLI version"

### Added
- Selenium-based punch worker (`run_punch_in`) on a background thread that:
  - Loads settings from `settings.json` and credentials from `credentials.json`
  - Waits for VPN interface to be `up`
  - Launches Chrome via `chromedriver` (configurable path, headless/incognito/mute/maximize options)
  - Navigates to the Kronos SSO portal
  - Detects login page; auto-fills credentials if `auto_login` is enabled
  - Waits for punch button and clicks it
  - Reports progress back to the UI thread via `GLib.idle_add`
- Particle system and fireworks (`SuperCoolDialog`) with:
  - `Particle` class with physics (gravity, drag, hue, decay, trail rendering)
  - `FireworkShell` class spawning 60–110 particles with optional dual-color bursts
  - Full-screen `Adw.Dialog` with 60 fps canvas animation, auto-close support
- Fireworks entry in the hamburger menu
- `requirements.txt` with selenium, trio, PyGObject, pycairo, pytest, and dependencies
- `settings.json.default` with default configuration values
- `credentials.json.default` (empty file, placeholder)
- `.gitignore` entries for `punch`, `.venv`, `.continue`, `.flatpak*`, `build-dir`, config files

### Changed
- Main window restructured extensively:
  - Punch logic now tracks session state (`_punched_in`, `_session_start`)
  - Punch Out calculates and displays elapsed duration
  - Status dot (green/gray) drawn with Cairo on a `Gtk.DrawingArea`
  - Status label and session label in action bar footer
  - Console log uses monospace font via CSS class
  - Overall layout: 480×560 default size

## 2026-03-20 15:04 — "More Gnomey"

### Changed
- Major UI refactor to follow GNOME HIG:
  - `Adw.ToolbarView` as root content with `add_top_bar` / `add_bottom_bar`
  - `Adw.WindowTitle` for title/subtitle in the header bar
  - Punch button moved into header bar (single primary action pattern)
  - Hamburger menu (`Gtk.MenuButton`) replaces inline about/super-cool buttons
  - `Gio.SimpleAction` registered for menu items
  - `Adw.Clamp` wraps the log view for responsive width constraints
  - `Gtk.ScrolledWindow` uses `frame` CSS class for HIG-standard sunken border
  - Log view: non-editable, no cursor, proper margins, `WORD_CHAR` wrapping
  - Action bar footer with centre-aligned clock, caption-style labels
  - Cleaner CSS (only monospace font for the log view, no custom borders)
  - Window default size increased from 400×500 to 480×560

## 2026-03-20 15:01 — "Added a footer"

### Added
- `start.sh` helper script to activate the `.venv` virtual environment

### Changed
- Implemented punch in/out toggle with session duration tracking
- Added action bar footer with:
  - Status dot (drawn via Cairo, green when punched in, gray when clocked out)
  - Status label ("Clocked out" / "Punched in")
  - Session label (duration display on punch out)
- Real-time clock display updates every second
- Test data generation (1000 lines) for console
- Helper `_draw_status_dot` using Cairo arcs and colors
- Header bar with about button
- Layout uses `Gtk.Grid` → `Gtk.Box(vertical)`
- Proper CSS class for header bar
- Added Claude AI to about credits

## 2026-03-20 11:26 — Initial Commit

### Added
- `punch_gui.py` — basic GTK4/Adwaita window stub with:
  - Punch In/Out button (no-op)
  - Clock label
  - Console `Gtk.TextView` with scroll
  - CSS styling for bordered text view
- `about.py` — standalone `show_about()` using `Adw.AboutWindow`
- `metadata/app.toml` — application metadata
- `space.mcharryville.PunchGUI.json` — draft Flatpak manifest (broken: wrong runtime 41, no setup.py, dummy git source)
- `LICENSE` — GPL v2
- `README.md` — initial placeholder
- `.continue/rules` — editor rules
