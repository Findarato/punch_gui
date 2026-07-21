# Unit Test Plan — Punch GUI

## Overview

Punch GUI is a GTK4/Adwaita desktop app that automates clocking in/out at work
via Selenium (ChromeDriver). It navigates to an SSO timekeeping portal, logs in,
and clicks the "punch in" button. The project currently has **zero tests**.

## Strategy

1. **Pure logic first** — `Particle`, `FireworkShell`, `load_settings()`,
   `get_credentials()`, and the credentials-dialog helpers are all testable
   without a display server.
2. **Mock the GTK/Selenium layers** — GUI classes and `run_punch_in()` are tested
   with `unittest.mock` to avoid requiring a running X11/Wayland session or a real
   ChromeDriver.
3. **Filesystem fixtures via `tmp_path`** — settings/credentials I/O uses pytest's
   built-in `tmp_path` fixture so tests never touch real user files.
4. **No headless-display tests** — integration tests with real GTK widgets or
   Selenium are out of scope for this initial suite.

## Test Files

| File | Covers | Key scenarios |
|---|---|---|
| `tests/test_particle.py` | `Particle`, `FireworkShell` | init ranges, step physics, trail cap, life decay, shell particle count, complementary hue, step-all-dead |
| `tests/test_settings.py` | `load_settings()`, `get_credentials()` | valid JSON, missing file, malformed JSON, GPG decrypt path, missing GPG, empty creds |
| `tests/test_credentials_dialog.py` | `_load_settings`, `_save_settings`, `_load_credentials`, `_save_credentials`, `_list_gpg_keys` | round-trip write/read, GPG encrypt+decrypt, gpg not found, key parsing |
| `tests/test_run_punch_in.py` | `run_punch_in()` | no settings, no selenium, VPN check loops, cancellation, login flow, punch click, error handling, driver cleanup |

## Scenarios per module

### Particle (punch_gui.py:288-320)

- `__init__`: position set, velocity magnitude in [60, 260], life == 1.0, decay in [0.018, 0.038], radius in [2.5, 5.0], trail empty
- `step`: gravity applied (vy += 120*dt), drag applied (0.985), position updated, life decremented, trail grows then caps at 6, returns False when life <= 0

### FireworkShell (punch_gui.py:323-339)

- `__init__`: 60-110 particles created, x/y within bounds, hue in [0,1), 40% chance of complementary burst (n//3 extra particles)
- `step`: dead particles removed, returns False when all dead

### load_settings / get_credentials (punch_gui.py:56-89)

- valid settings.json → returns dict
- missing file → returns {}
- malformed JSON → returns {}
- get_credentials: missing file → ('', '')
- get_credentials: valid plaintext → (login, password)
- get_credentials: GPG enabled but gpg fails → ('', '')
- get_credentials: GPG decrypt success → (login, password)

### credentials_dialog helpers (src/credentials_dialog.py:28-122)

- `_load_settings`: same as load_settings
- `_save_settings` + `_load_settings`: round-trip
- `_load_credentials`: plaintext read, GPG decrypt, missing file
- `_save_credentials`: plaintext write, GPG encrypt, error returns
- `_list_gpg_keys`: parse colons output, empty keyring, gpg not found

### run_punch_in (punch_gui.py:100-281)

- no settings → error callback
- selenium not installed → error callback
- VPN URL check: success on first try
- VPN URL check: cancel during retry
- VPN interface check: file says "up"
- Chrome start failure → error callback
- Login page detected, auto_login enabled → fills credentials
- No login page → waits for manual
- Punch button clicked → done callback
- Exception during flow → error callback
- Driver always quit in finally

## Files created

- `pyproject.toml` — pytest configuration
- `tests/__init__.py` — package marker
- `tests/conftest.py` — shared fixtures (tmp_settings, tmp_creds, sample_settings, sample_creds)
- `tests/test_particle.py`
- `tests/test_settings.py`
- `tests/test_credentials_dialog.py`
- `tests/test_run_punch_in.py`
