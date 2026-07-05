# Changelog

## Commit `cffbba1` — Add GitHub Action to build Flatpak with GNOME 47 runtime
**Date:** 2026-07-05 17:43

Files changed:
- **A** `.github/workflows/flatpak.yml` — GitHub Actions workflow that builds the Flatpak on push/PR to `main` or manual dispatch; uses `bilelmoussaoui/flatpak-github-actions:gnome-47` container with `flatpak-builder`; outputs `punch-gui.flatpak` bundle
- **A** `space.mcharryville.PunchGUI.desktop` — desktop entry file with app name, icon, and categories for Flatpak export
- **A** `space.mcharryville.PunchGUI.svg` — SVG application icon (blue rounded rect with white clock face and hands)
- **M** `space.mcharryville.PunchGUI.json`:
  - `app-id`: `space.mcharryville.punch_gui` → `space.mcharryville.PunchGUI`
  - `runtime-version`: `41` → `47`
  - `command`: `punch-gui` → `punch_gui.py`
  - `sources`: removed `git` remote, replaced with local `type: dir, path: .`
  - `build-commands`: removed `python3 setup.py install --prefix=/app`, replaced with three `install -D` commands that copy `punch_gui.py`, `about.py`, the desktop file, and the SVG icon into `/app`
  - `finish-args`: removed `--share=network` and `--socket=xwayland`; added `--share=ipc`, `--socket=x11`, `--socket=wayland`, `--device=dri`, `--share=network`
  - removed broken `python-runtime` module

## Commit `a9303c2` — Updated from a while ago
**Date:** 2026-07-05 16:58

Files changed:
- **A** `IDEA.md` — project description: "I am creating a python based GTK app that allows me to punch in at work."
- **M** `punch_gui.py`:
  - Selenium: SSO URL changed from hardcoded `https://methodisthospitals-sso.prd.mykronos.com/wfd/home` to `settings.get('work_sso_location', '')`
  - New class `SettingsDialog(Adw.Dialog)` added:
    - JSON settings editor with `Adw.PreferencesPage` layout
    - Groups: Paths (ChromeDriver path, VPN interface, SSO URL), Timing (antifarm sleep, deviation), Browser (headless, maximize, incognito, mute toggles), Login (auto-login toggle)
    - Uses `Adw.EntryRow` for strings, `Adw.ActionRow` + `Gtk.SpinButton` for ints, `Adw.ActionRow` + `Gtk.Switch` for bools
    - `_make_spin_row()` and `_make_switch_row()` static factory helpers
    - Save writes `settings.json`, Cancel discards changes
    - Falls back to `stderr` print on save failure
    - Default settings dict with all keys
  - Hamburger menu: added `Settings` entry between `Super Cool…` and `About Punch Tracker`
  - New action `win.settings` registered with `on_settings_activated()` callback that opens `SettingsDialog`
  - `populate_test_data()` call restored after refactor removal
  - `on_super_cool_activated()` now opens `SuperCoolDialog` (was inline console sequence)
- **M** `settings.json.default`:
  - Added `"vpn_interface": "/sys/class/net/vpn0/operstate"` (was missing)
  - Added `"work_sso_location": "https://work.mykronos.com/wfd/home"`
  - Added `"VPN Update Path": "http://work.domain.site"`
- **M** `.gitignore`: added `notes.md` entry
- **M** `space.mcharryville.PunchGUI.json`: removed `--socket=x11` from finish-args, leaving only `--socket=xwayland` and `--share=network`

## Commit `14c08a7` — Forgot to include the creds
**Date:** 2026-03-20 15:29

Files changed:
- **M** `credentials.json.default`: filled with `{"login": "username", "password": "password"}` (was empty file)

## Commit `d7738c4` — Pulled in some things from the CLI version
**Date:** 2026-03-20 15:28

Files changed:
- **A** `.gitignore` — ignores: `punch`, `.venv`, `.continue/*`, `.continue`, `.flatpak*`, `build-dir`, `settings.json`, `credentials.json`
- **A** `credentials.json.default` — empty placeholder file
- **A** `requirements.txt` — 24 pinned Python dependencies including `selenium==4.1.3`, `PyGObject==3.56.1`, `pycairo==1.29.0`, `pytest==9.0.2`, plus trio, cryptography, urllib3, and others
- **A** `settings.json.default` — default config: chromedriver path, antifarm sleep 8, deviation 5, maximize on, headless off, incognito on, auto-login on, mute on, VPN interface path
- **M** `punch_gui.py` — major expansion (+493 lines):
  - New imports: `random`, `threading`, `time`, `os`, `json`, `sys`
  - `get_settings()` — loads `settings.json` from the script directory, returns dict or `(None, error)`
  - `get_credentials()` — loads `credentials.json`, returns `(login, password)` tuple or `('', '')`
  - `run_punch_in(log_cb, done_cb, error_cb)` — blocking Selenium worker:
    - Heavy selenium imports done inside the function (kept off main thread)
    - VPN wait loop: polls `vpn_interface` sysfs file every 10 s until `up`
    - Chrome options: user-agent spoofing, incognito, mute, headless, maximize, disable automation flags
    - ChromeDriver launched via `ChromeService` with configurable path
    - Navigates to `https://methodisthospitals-sso.prd.mykronos.com/wfd/home`
    - Detects login page via `brandingWrapper` element
    - Auto-fills `userNameInput` / `passwordInput` and clicks `submitButton` if auto-login enabled
    - Waits up to 60 s for `punchSubmitBtnId` and clicks it
    - Reports progress via `GLib.idle_add` callbacks
    - Cleanup: `driver.quit()` in `finally` block
  - `Particle` class — firework particle with physics: position, velocity, gravity (120 px/s²), drag (0.985), hue-based coloration, life/decay, trail rendering (up to 6 history points)
  - `FireworkShell` class — spawns 60–110 particles at random position, 40% chance of secondary complementary-color burst
  - `SuperCoolDialog(Adw.Dialog)` — full fireworks animation dialog:
    - 60 fps canvas with `Gtk.DrawingArea`
    - New shell launched every 38 frames, occasional double launches
    - Dark background (`#050510`), particle trails with alpha fade
    - Close button ("✨  Dismiss") centered at bottom
    - Optional auto-close after 5 s
    - Cleanup: source removal on dialog close
  - Punch button now integrates with Selenium:
    - `_set_punching_in_state()` — disables button, sets "Connecting…" UI state
    - `_on_punch_success()` — called via idle_add on Selenium success; toggles to punched-in state, opens `SuperCoolDialog` with auto_close
    - `_on_punch_error(msg)` — called via idle_add on failure; re-enables button, shows error
    - `on_punch_clicked()` — starts background thread calling `run_punch_in()` for punch-in; punch-out is local only (no Selenium)
  - `on_super_cool_activated()` now opens `SuperCoolDialog` (was inline sequence)
  - Removed inline super-cool sequence buttons from header bar area
  - Removed `__pycache__/about.cpython-314.pyc` — not tracked (it's a pyc file)

## Commit `6a76a7e` — More Gnomey
**Date:** 2026-03-20 15:04

Files changed:
- **M** `punch_gui.py` — major refactor (+144/-87 lines):
  - Layout: `Gtk.Box(vertical)` → `Adw.ToolbarView` with `add_top_bar(headerbar)` and `add_bottom_bar(action_bar)`
  - Title: plain `Gtk.Label` → `Adw.WindowTitle` with subtitle ("Clocked out")
  - Punch button: moved from inline box into `headerbar.pack_end()`, uses `suggested-action` / `destructive-action` CSS classes for in/out states
  - Menu: inline `Gtk.Button` for about/super-cool → `Gtk.MenuButton` with `Gio.Menu` model and `Gio.SimpleAction` actions
  - Log view: `ScrolledWindow` gets `frame` CSS class (HIG sunken border), `TextView` becomes non-editable, no cursor, `WORD_CHAR` wrap, 8 px internal margins
  - CSS: simplified to only `.log-view { font-family: monospace; font-size: 13px; }`
  - `Adw.Clamp(maximum_size=800, tightening_threshold=600)` wraps the scrolled window for responsive width
  - Clock: moved from inline label to `action_bar.set_center_widget()`, shows `%H:%M:%S` instead of full datetime
  - Status labels: use `caption` and `dim-label` CSS classes
  - Status dot colors: GNOME green `(0.35, 0.63, 0.12)` / gray `(0.50, 0.50, 0.50)`
  - Window default size: 400×500 → 480×560
  - `import math` moved to top of file
  - `append_to_console()` returns `False` (safe for `GLib.idle_add`)
  - Punch out log format: `▶  Punched in {ts}` / `■  Punched out {ts} ({duration})`
  - Section comment blocks reorganized
  - `populate_test_data()` removed from `__init__`
  - Formatting: `Adw.Clamp(maximum_size=800, tightening_threshold=600)` constructor style

## Commit `93eb906` — Added a footer
**Date:** 2026-03-20 15:01

Files changed:
- **A** `start.sh` — bash script to `source .venv/bin/activate` for virtual environment entry
- **M** `.continue/rules` — added `*.py` to project architecture description
- **M** `about.py`:
  - Developers: added "Claude AI"
  - Contributors: "GitHub Copilot" → "GitHub Copilot, Claude AI"
- **M** `punch_gui.py` (+92/-24 lines):
  - `import math` added
  - `_punched_in` and `_session_start` instance variables added
  - `_draw_status_dot()` — Cairo drawing function: green dot when punched in, gray dot when clocked out
  - `on_punch_clicked()` — now toggles between punch in/out with:
    - Session start timestamp tracking
    - Elapsed duration calculation (hours/minutes/seconds)
    - Button label toggle (Punch In / Punch Out)
    - Status label updates
    - `status_dot.queue_draw()` on state change
  - Layout: `Gtk.Grid` → `Gtk.Box(orientation=vertical)`
  - Action bar footer added with `Gtk.ActionBar` containing:
    - Status dot (`Gtk.DrawingArea`, 10×10 px)
    - Status label ("Status: Clocked out" / "Status: Punched in")
    - Session label ("Session: —" / "Session: in progress" / duration display)
  - Header bar: `Adw.HeaderBar.new()` with about button (`help-about-symbolic`) and "Punch Tracker" label
  - Clock label shows full datetime `%Y-%m-%d %H:%M:%S`
  - Test data: 1000 rows loaded on startup via `populate_test_data()`
  - Console scrolled window bottom margin: 20 → 6
  - CSS provider formatting broken across multiple lines

## Commit `2e0383e` — First Commit (initial skeleton)
**Date:** 2026-03-20 11:26

Files added:
- **A** `punch_gui.py` — 175-line GTK4/Adwaita application stub:
  - `PunchTrackerWindow(Adw.ApplicationWindow)` with:
    - Window title "Punch Tracker", default size 400×500
    - `Gtk.Grid` layout with header bar area, punch button row, and scrolled console
    - Punch In button (no-op, just logs timestamp)
    - Clock label updating every second
    - Console `Gtk.TextView` with word wrap and scroll
    - CSS provider: bordered text view with white text on transparent background
    - About button opening `about.show_about()`
  - `PunchTrackerApplication(Adw.Application)` with `application_id='org.example.PunchTracker'`
- **A** `about.py` — 49-line `show_about()` function using `Adw.AboutWindow` with:
  - App name "Punch Tracker", developer "Joseph Harry", version/icon/website/credits
  - GPL-3.0 license text
- **A** `metadata/app.toml` — TOML metadata: application name, description, icon path, desktop entry stub
- **A** `space.mcharryville.PunchGUI.json` — draft Flatpak manifest:
  - `app-id`: `space.mcharryville.punch_gui`
  - `runtime-version`: `41` (outdated)
  - `command`: `punch-gui` (non-existent)
  - `sources`: git remote to placeholder URL
  - `build-commands`: `python3 setup.py install` (no setup.py exists)
  - Extra `python-runtime` module with broken build commands
  - `finish-args`: `--share=network`, `--socket=x11`, `--socket=xwayland`
- **A** `LICENSE` — GNU General Public License v2
- **A** `README.md` — minimal placeholder
- **A** `.continue/rules` — editor configuration rules
- **A** `__pycache__/about.cpython-314.pyc` — compiled bytecode for about.py (not normally tracked)
