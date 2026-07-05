#!/usr/bin/env python3

"""
   Title: punch_gui/punch_gui.py
   Description: Main GUI for Punch Tracker
   Author: Joseph Harry
   Copyright (C): Joseph Harry 2026
   Date: 2026-03-20 10:56:00

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; either version 2 of the License, or
   (at your option) any later version.
   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.
   You should have received a copy of the GNU General Public License along
   with this program; if not, write to the Free Software Foundation, Inc.
   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""

import gi
import math
import random
import threading
import argparse
import time
import os
import json
import sys

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, GLib, Gio, Gdk

# Ensure src/ is importable regardless of cwd
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


# ------------------------------------------------------------------ #
#  Paths                                                               #
# ------------------------------------------------------------------ #

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH  = os.path.join(BASE_DIR, 'settings.json')
CREDS_PATH     = os.path.join(BASE_DIR, 'credentials.json')


# ------------------------------------------------------------------ #
#  Settings / credentials helpers                                      #
# ------------------------------------------------------------------ #

def load_settings():
    try:
        with open(SETTINGS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def get_credentials(settings):
    """Return (login, password), decrypting via GPG if configured."""
    if not os.path.exists(CREDS_PATH):
        return '', ''

    use_gpg = settings.get('encrypt_credentials', False)
    gpg_key = settings.get('gpg_key', '')

    if use_gpg and gpg_key:
        import subprocess
        try:
            result = subprocess.run(
                ['gpg', '--quiet', '--batch', '--yes', '--decrypt', CREDS_PATH],
                capture_output=True, text=True, check=True
            )
            creds = json.loads(result.stdout)
        except Exception as e:
            return '', ''
    else:
        try:
            with open(CREDS_PATH) as f:
                creds = json.load(f)
        except Exception:
            return '', ''

    return creds.get('login', ''), creds.get('password', '')


# ------------------------------------------------------------------ #
#  Selenium punch worker                                               #
# ------------------------------------------------------------------ #

# Shared cancellation flag — set to True to abort the running login
_cancel_flag = threading.Event()


def run_punch_in(log_cb, done_cb, error_cb, cancel_cb):
    """
    Blocking Selenium flow. Must be called on a background thread.
    Communicates with the UI exclusively via GLib.idle_add().

    cancel_cb() — called when the user cancels mid-flight
    """

    def log(msg):
        GLib.idle_add(log_cb, msg + '\n')

    def done():
        GLib.idle_add(done_cb)

    def error(msg):
        GLib.idle_add(error_cb, msg + '\n')

    def cancelled():
        GLib.idle_add(cancel_cb)

    def check_cancel():
        return _cancel_flag.is_set()

    # --- selenium imports ---
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import WebDriverException
    except ImportError as e:
        error(f'❌  Selenium not installed: {e}')
        return

    settings = load_settings()
    if not settings:
        error('❌  Could not load settings.json')
        return

    login, password = get_credentials(settings)

    # --- VPN check ---
    vpn_url   = settings.get('VPN Update Path', '')
    vpn_iface = settings.get('vpn_interface', '')

    if vpn_url:
        # Check VPN via a URL reachable only on the VPN
        log('🪐  Checking VPN via URL…')
        import urllib.request
        while True:
            if check_cancel():
                cancelled()
                return
            try:
                urllib.request.urlopen(vpn_url, timeout=5)
                log('✅  VPN is up (URL reachable)')
                break
            except Exception:
                log('😴  VPN not ready — retrying in 10 s')
                for _ in range(10):
                    if check_cancel():
                        cancelled()
                        return
                    time.sleep(1)
    elif vpn_iface:
        log('🪐  Waiting for VPN (interface)…')
        while True:
            if check_cancel():
                cancelled()
                return
            try:
                with open(vpn_iface) as f:
                    if f.read().strip() == 'up':
                        log('✅  VPN is up')
                        break
            except Exception:
                pass
            log('😴  VPN not ready — retrying in 10 s')
            for _ in range(10):
                if check_cancel():
                    cancelled()
                    return
                time.sleep(1)

    if check_cancel():
        cancelled()
        return

    # --- Chrome setup ---
    chrome_options = Options()
    chrome_options.add_argument(
        'user-agent=Mozilla/5.0 (X11; Fedora; Linux x86_64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) 96.0.4664.113 Safari/537.36'
    )
    chrome_options.add_argument('--log-level=3')
    chrome_options.add_argument('--disable-infobars')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    if settings.get('incognito'):      chrome_options.add_argument('--incognito')
    if settings.get('mute_audio'):     chrome_options.add_argument('--mute-audio')
    if settings.get('maximize_window'):chrome_options.add_argument('start-maximized')
    if settings.get('headless'):       chrome_options.add_argument('--headless')

    try:
        service = ChromeService(executable_path=settings.get('chromedriver_path', 'chromedriver'))
        driver  = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        error(f'❌  Could not start Chrome: {e}')
        return

    try:
        sso_url = settings.get('work_sso_location', 'https://methodisthospitals-sso.prd.mykronos.com/wfd/home')
        log(f'🌐  Navigating to {sso_url}…')
        driver.get(sso_url)

        if check_cancel():
            cancelled()
            return

        # --- Login detection ---
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(('id', 'brandingWrapper'))
            )
            log('🔐  Login page detected')

            if settings.get('auto_login') and login and password:
                log('🔑  Entering credentials…')
                user_field = WebDriverWait(driver, 60).until(
                    EC.presence_of_element_located(('id', 'userNameInput'))
                )
                if check_cancel():
                    cancelled()
                    return
                user_field.send_keys(login)
                driver.find_element('id', 'passwordInput').send_keys(password)
                # Interruptible sleep before submit
                for _ in range(55):
                    if check_cancel():
                        cancelled()
                        return
                    time.sleep(0.1)
                driver.find_element('id', 'submitButton').click()
                log('⏳  Waiting for portal to load…')
            else:
                log('ℹ️   Auto-login disabled — waiting for manual login…')

        except Exception:
            log('ℹ️   No login page — already authenticated?')

        if check_cancel():
            cancelled()
            return

        # --- Wait for punch button ---
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located(('id', 'punchSubmitBtnId'))
        )
        log('✅  Logged in to SSO')

        if check_cancel():
            cancelled()
            return

        log('⏱️   Punching in…')
        driver.find_element('id', 'punchSubmitBtnId').click()
        log('🎉  Punched in successfully!')
        done()

    except Exception as e:
        if not check_cancel():
            error(f'❌  Error: {e}')
        else:
            cancelled()
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ------------------------------------------------------------------ #
#  Firework particle                                                   #
# ------------------------------------------------------------------ #

class Particle:
    def __init__(self, x, y, hue):
        angle       = random.uniform(0, 2 * math.pi)
        speed       = random.uniform(60, 260)
        self.x      = x;  self.y  = y
        self.vx     = math.cos(angle) * speed
        self.vy     = math.sin(angle) * speed
        self.hue    = hue
        self.life   = 1.0
        self.decay  = random.uniform(0.018, 0.038)
        self.radius = random.uniform(2.5, 5.0)
        self.trail  = []

    def step(self, dt):
        self.trail.append((self.x, self.y))
        if len(self.trail) > 6:
            self.trail.pop(0)
        self.vy += 120 * dt;  self.vx *= 0.985;  self.vy *= 0.985
        self.x  += self.vx * dt;  self.y += self.vy * dt
        self.life -= self.decay
        return self.life > 0

    def draw(self, cr):
        import colorsys as cs
        for i, (tx, ty) in enumerate(self.trail):
            alpha = (i / len(self.trail)) * self.life * 0.4
            cr.set_source_rgba(*cs.hls_to_rgb(self.hue, 0.65, 1.0), alpha)
            cr.arc(tx, ty, max(self.radius * (i / len(self.trail)) * 0.6, 0.5), 0, 2 * math.pi)
            cr.fill()
        cr.set_source_rgba(*cs.hls_to_rgb(self.hue, 0.80, 1.0), self.life)
        cr.arc(self.x, self.y, self.radius * self.life, 0, 2 * math.pi);  cr.fill()
        cr.set_source_rgba(1, 1, 1, self.life * 0.7)
        cr.arc(self.x, self.y, self.radius * self.life * 0.4, 0, 2 * math.pi);  cr.fill()


class FireworkShell:
    def __init__(self, w, h):
        self.x = random.uniform(w * 0.2, w * 0.8)
        self.y = random.uniform(h * 0.15, h * 0.55)
        self.hue = random.random()
        n = random.randint(60, 110)
        self.particles = [Particle(self.x, self.y, self.hue) for _ in range(n)]
        if random.random() < 0.4:
            h2 = (self.hue + 0.5) % 1.0
            self.particles += [Particle(self.x, self.y, h2) for _ in range(n // 3)]

    def step(self, dt):
        self.particles = [p for p in self.particles if p.step(dt)]
        return bool(self.particles)

    def draw(self, cr):
        for p in self.particles:  p.draw(cr)


# ------------------------------------------------------------------ #
#  Super Cool Dialog                                                   #
# ------------------------------------------------------------------ #

class SuperCoolDialog(Adw.Dialog):
    _FPS = 60;  _INTERVAL = 1000 // _FPS;  _DT = 1 / _FPS
    _SHELL_GAP = 38;  _WIDTH = 480;  _HEIGHT = 360

    def __init__(self, parent, auto_close=False):
        super().__init__()
        self.set_title('Super Cool!')
        self.set_content_width(self._WIDTH)
        self.set_content_height(self._HEIGHT)
        self._shells = [];  self._frame = 0;  self._timer_id = None
        self._auto_close = auto_close;  self._w = self._WIDTH;  self._h = self._HEIGHT

        tv = Adw.ToolbarView()
        hb = Adw.HeaderBar();  hb.add_css_class('flat');  tv.add_top_bar(hb)

        ov = Gtk.Overlay()
        self.canvas = Gtk.DrawingArea()
        self.canvas.set_draw_func(self._on_draw)
        self.canvas.set_hexpand(True);  self.canvas.set_vexpand(True)
        ov.set_child(self.canvas)

        btn = Gtk.Button(label='✨  Dismiss')
        btn.add_css_class('suggested-action');  btn.add_css_class('pill')
        btn.set_halign(Gtk.Align.CENTER);  btn.set_valign(Gtk.Align.END)
        btn.set_margin_bottom(24);  btn.connect('clicked', lambda _: self.close())
        ov.add_overlay(btn)

        tv.set_content(ov);  self.set_child(tv)
        self.connect('closed', self._on_closed)

        css = Gtk.CssProvider()
        css.load_from_data(b'.firework-bg { background-color: #050510; }')
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.canvas.add_css_class('firework-bg')

        self.present(parent)
        self._launch_shell()
        self._timer_id = GLib.timeout_add(self._INTERVAL, self._tick)
        if auto_close:
            GLib.timeout_add_seconds(5, self._auto_close_cb)

    def _tick(self):
        self._frame += 1
        self._shells = [s for s in self._shells if s.step(self._DT)]
        if self._frame % self._SHELL_GAP == 0:
            self._launch_shell()
            if random.random() < 0.35:  self._launch_shell()
        self.canvas.queue_draw()
        return True

    def _launch_shell(self):   self._shells.append(FireworkShell(self._w, self._h))
    def _auto_close_cb(self):  self.close();  return False

    def _on_draw(self, area, cr, w, h):
        self._w = w;  self._h = h
        cr.set_source_rgb(0.02, 0.02, 0.06);  cr.paint()
        cr.set_source_rgba(0.02, 0.02, 0.06, 0.18);  cr.paint()
        for s in self._shells:  s.draw(cr)

    def _on_closed(self, _):
        if self._timer_id:
            GLib.source_remove(self._timer_id);  self._timer_id = None


# ------------------------------------------------------------------ #
#  Settings Dialog                                                     #
# ------------------------------------------------------------------ #

class SettingsDialog(Adw.Dialog):

    _DEFAULTS = {
        'chromedriver_path':  '/usr/bin/chromedriver',
        'antifarm_sleep':     8,
        'deviation':          5,
        'maximize_window':    True,
        'headless':           False,
        'incognito':          True,
        'auto_login':         True,
        'mute_audio':         True,
        'vpn_interface':      '/sys/class/net/vpn0/operstate',
        'work_sso_location':  'https://work.mykronos.com/wfd/home',
        'VPN Update Path':    'http://work.domain.site',
    }

    def __init__(self, parent):
        super().__init__()
        self.set_title('Settings')
        self.set_content_width(540)
        self._parent = parent

        try:
            with open(SETTINGS_PATH) as f:
                self._current = json.load(f)
        except Exception:
            self._current = dict(self._DEFAULTS)

        # ---- header bar ----
        headerbar = Adw.HeaderBar()
        cancel_btn = Gtk.Button(label='Cancel')
        cancel_btn.connect('clicked', lambda _: self.close())
        headerbar.pack_start(cancel_btn)
        save_btn = Gtk.Button(label='Save')
        save_btn.add_css_class('suggested-action')
        save_btn.connect('clicked', self._on_save)
        headerbar.pack_end(save_btn)

        page = Adw.PreferencesPage()

        # --- Paths group ---
        paths_group = Adw.PreferencesGroup(title='Paths')
        page.add(paths_group)

        # ChromeDriver — file picker row
        cd_row = Adw.ActionRow(title='ChromeDriver', subtitle='Path to chromedriver binary')
        self._chromedriver_label = Gtk.Label(
            label=self._current.get('chromedriver_path', ''),
            ellipsize=3,   # PANGO_ELLIPSIZE_END
            max_width_chars=28
        )
        self._chromedriver_label.set_valign(Gtk.Align.CENTER)
        pick_btn = Gtk.Button(icon_name='document-open-symbolic')
        pick_btn.set_valign(Gtk.Align.CENTER)
        pick_btn.add_css_class('flat')
        pick_btn.connect('clicked', self._pick_chromedriver)
        cd_row.add_suffix(self._chromedriver_label)
        cd_row.add_suffix(pick_btn)
        paths_group.add(cd_row)

        self._vpn_iface_row = Adw.EntryRow(title='VPN interface state file')
        self._vpn_iface_row.set_text(self._current.get('vpn_interface', ''))
        paths_group.add(self._vpn_iface_row)

        # --- Network group ---
        net_group = Adw.PreferencesGroup(title='Network')
        page.add(net_group)

        self._sso_row = Adw.EntryRow(title='SSO / portal URL')
        self._sso_row.set_text(self._current.get('work_sso_location', ''))
        net_group.add(self._sso_row)

        self._vpn_url_row = Adw.EntryRow(title='VPN check URL')
        self._vpn_url_row.set_text(self._current.get('VPN Update Path', ''))
        net_group.add(self._vpn_url_row)

        # --- Timing group ---
        timing_group = Adw.PreferencesGroup(title='Timing')
        page.add(timing_group)

        self._sleep_spin, _ = self._spin_row(
            timing_group, 'Antifarm sleep', 'seconds', 0, 120,
            self._current.get('antifarm_sleep', 8))
        self._deviation_spin, _ = self._spin_row(
            timing_group, 'Deviation', 'seconds', 0, 60,
            self._current.get('deviation', 5))

        # --- Browser group ---
        browser_group = Adw.PreferencesGroup(title='Browser')
        page.add(browser_group)

        self._headless_sw  = self._switch_row(browser_group, 'Headless mode',    'Run Chrome without a visible window', self._current.get('headless', False))
        self._maximize_sw  = self._switch_row(browser_group, 'Maximize window',  'Start Chrome maximized',              self._current.get('maximize_window', True))
        self._incognito_sw = self._switch_row(browser_group, 'Incognito mode',   'Open Chrome in a private window',     self._current.get('incognito', True))
        self._mute_sw      = self._switch_row(browser_group, 'Mute audio',       'Silence Chrome during automation',    self._current.get('mute_audio', True))

        # --- Login group ---
        login_group = Adw.PreferencesGroup(title='Login')
        page.add(login_group)

        self._auto_login_sw = self._switch_row(login_group, 'Auto login', 'Fill credentials automatically', self._current.get('auto_login', True))

        # ---- layout ----
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(headerbar)
        toolbar_view.set_content(page)
        self.set_child(toolbar_view)
        self.present(parent)

    # ---- row factories -------------------------------------------- #

    @staticmethod
    def _spin_row(group, title, subtitle, lo, hi, val):
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        adj = Gtk.Adjustment(value=val, lower=lo, upper=hi, step_increment=1, page_increment=10)
        spin = Gtk.SpinButton(adjustment=adj, numeric=True)
        spin.set_valign(Gtk.Align.CENTER)
        row.add_suffix(spin);  row.set_activatable_widget(spin)
        group.add(row)
        return spin, row

    @staticmethod
    def _switch_row(group, title, subtitle, active):
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        sw = Gtk.Switch(active=active)
        sw.set_valign(Gtk.Align.CENTER)
        row.add_suffix(sw);  row.set_activatable_widget(sw)
        group.add(row)
        return sw

    # ---- file picker ---------------------------------------------- #

    def _pick_chromedriver(self, _btn):
        dialog = Gtk.FileDialog()
        dialog.set_title('Select chromedriver binary')
        dialog.open(self._parent, None, self._chromedriver_picked, None)

    def _chromedriver_picked(self, dialog, result, _data):
        try:
            f = dialog.open_finish(result)
            if f:
                path = f.get_path()
                self._chromedriver_label.set_text(path)
                self._chromedriver_label.set_tooltip_text(path)
        except Exception:
            pass

    # ---- save ----------------------------------------------------- #

    def _on_save(self, _btn):
        data = dict(self._current)
        data.update({
            'chromedriver_path': self._chromedriver_label.get_text(),
            'vpn_interface':     self._vpn_iface_row.get_text(),
            'work_sso_location': self._sso_row.get_text(),
            'VPN Update Path':   self._vpn_url_row.get_text(),
            'antifarm_sleep':    int(self._sleep_spin.get_value()),
            'deviation':         int(self._deviation_spin.get_value()),
            'headless':          self._headless_sw.get_active(),
            'maximize_window':   self._maximize_sw.get_active(),
            'incognito':         self._incognito_sw.get_active(),
            'mute_audio':        self._mute_sw.get_active(),
            'auto_login':        self._auto_login_sw.get_active(),
        })
        try:
            with open(SETTINGS_PATH, 'w') as f:
                json.dump(data, f, indent=4)
            self.close()
        except Exception as e:
            print(f'Could not save settings: {e}', file=sys.stderr)


# ------------------------------------------------------------------ #
#  Main window                                                         #
# ------------------------------------------------------------------ #

class PunchTrackerWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'PunchTrackerWindow'

    def __init__(self, auto_login=False, **kwargs):
        super().__init__(title='Punch Tracker', **kwargs)
        self.set_default_size(640, 560)

        self._punched_in    = False
        self._session_start = None
        self._auto_login    = auto_login

        provider = Gtk.CssProvider()
        provider.load_from_data(b'.log-view { font-family: monospace; font-size: 13px; }')
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # --- Header bar ---
        headerbar = Adw.HeaderBar()
        self.window_title = Adw.WindowTitle(title='Punch Tracker', subtitle='Clocked out')
        headerbar.set_title_widget(self.window_title)

        self.punch_button = Gtk.Button(label='Punch In')
        self.punch_button.add_css_class('suggested-action')
        self.punch_button.connect('clicked', self.on_punch_clicked)
        headerbar.pack_end(self.punch_button)

        # Cancel button — hidden until a login is in progress
        self.cancel_button = Gtk.Button(label='Cancel')
        self.cancel_button.add_css_class('destructive-action')
        self.cancel_button.connect('clicked', self._on_cancel_clicked)
        self.cancel_button.set_visible(False)
        headerbar.pack_end(self.cancel_button)

        menu = Gio.Menu()
        menu.append('Super Cool…',         'win.super-cool')
        menu.append('Settings',            'win.settings')
        menu.append('Sign-in Credentials', 'win.credentials')
        menu.append('About Punch Tracker', 'win.about')
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name('open-menu-symbolic')
        menu_button.set_menu_model(menu)
        headerbar.pack_start(menu_button)

        for name, cb in [('super-cool',   self.on_super_cool_activated),
                         ('settings',     self.on_settings_activated),
                         ('credentials',  self.on_credentials_activated),
                         ('about',        self.on_about_activated)]:
            action = Gio.SimpleAction.new(name, None)
            action.connect('activate', cb)
            self.add_action(action)

        # --- Log view ---
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.ALWAYS)
        scrolled_window.add_css_class('frame')
        scrolled_window.set_vexpand(True)

        self.console_text_view = Gtk.TextView()
        self.console_text_view.add_css_class('log-view')
        self.console_text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.console_text_view.set_editable(False)
        self.console_text_view.set_cursor_visible(False)
        self.console_text_view.set_left_margin(8);  self.console_text_view.set_right_margin(8)
        self.console_text_view.set_top_margin(8);   self.console_text_view.set_bottom_margin(8)
        self.console_buffer = self.console_text_view.get_buffer()
        scrolled_window.set_child(self.console_text_view)

        clamp = Adw.Clamp(maximum_size=800, tightening_threshold=600)
        clamp.set_child(scrolled_window)
        clamp.set_margin_start(12);  clamp.set_margin_end(12)
        clamp.set_margin_top(12);    clamp.set_margin_bottom(12)

        # --- Action bar ---
        action_bar = Gtk.ActionBar()

        self.status_dot = Gtk.DrawingArea()
        self.status_dot.set_content_width(10);  self.status_dot.set_content_height(10)
        self.status_dot.set_draw_func(self._draw_status_dot)

        self.status_label = Gtk.Label(label='Clocked out')
        self.status_label.set_margin_start(6);  self.status_label.add_css_class('caption')
        action_bar.pack_start(self.status_dot);  action_bar.pack_start(self.status_label)

        self.session_label = Gtk.Label(label='')
        self.session_label.add_css_class('caption');  self.session_label.add_css_class('dim-label')
        action_bar.pack_end(self.session_label)

        self.clock_label = Gtk.Label()
        self.clock_label.add_css_class('caption');  self.clock_label.add_css_class('dim-label')
        action_bar.set_center_widget(self.clock_label)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(headerbar)
        toolbar_view.add_bottom_bar(action_bar)
        toolbar_view.set_content(clamp)
        self.set_content(toolbar_view)

        self.start_clock()

        # Auto-punch if launched with --login
        if self._auto_login:
            GLib.idle_add(self._trigger_auto_login)

    # ---- drawing --------------------------------------------------- #

    def _draw_status_dot(self, area, cr, width, height):
        cr.set_source_rgb(0.35, 0.63, 0.12 if self._punched_in else 0.50)
        if not self._punched_in:
            cr.set_source_rgb(0.50, 0.50, 0.50)
        cr.arc(width / 2, height / 2, min(width, height) / 2, 0, 2 * math.pi)
        cr.fill()

    # ---- clock ----------------------------------------------------- #

    def start_clock(self):
        self.update_clock()
        GLib.timeout_add_seconds(1, self.update_clock)

    def update_clock(self):
        self.clock_label.set_text(GLib.DateTime.new_now_local().format('%H:%M:%S'))
        return True

    # ---- log ------------------------------------------------------- #

    def append_to_console(self, text):
        end_iter = self.console_buffer.get_end_iter()
        self.console_buffer.insert(end_iter, text)
        self.console_text_view.scroll_to_mark(
            self.console_buffer.get_insert(), 0.0, True, 0.5, 1.0)
        return False

    # ---- punch-in state -------------------------------------------- #

    def _trigger_auto_login(self):
        """Fired via idle_add after the window is presented."""
        self.on_punch_clicked(self.punch_button)
        return False

    def _set_connecting_state(self):
        self.punch_button.set_sensitive(False)
        self.punch_button.set_label('Connecting…')
        self.cancel_button.set_visible(True)
        self.window_title.set_subtitle('Connecting…')
        self.status_label.set_label('Connecting…')

    def _on_punch_success(self):
        timestamp           = GLib.DateTime.new_now_local()
        self._punched_in    = True
        self._session_start = timestamp

        self.punch_button.set_sensitive(True)
        self.punch_button.remove_css_class('suggested-action')
        self.punch_button.add_css_class('destructive-action')
        self.punch_button.set_label('Punch Out')
        self.cancel_button.set_visible(False)

        self.window_title.set_subtitle('Punched in')
        self.status_label.set_label('Punched in')
        self.session_label.set_label('Session in progress')
        self.status_dot.queue_draw()
        SuperCoolDialog(self, auto_close=True)

    def _on_punch_error(self, message):
        self.punch_button.set_sensitive(True)
        self.punch_button.set_label('Punch In')
        self.cancel_button.set_visible(False)
        self.window_title.set_subtitle('Error')
        self.status_label.set_label('Error')
        self.append_to_console(message)

    def _on_punch_cancelled(self):
        self.punch_button.set_sensitive(True)
        self.punch_button.set_label('Punch In')
        self.cancel_button.set_visible(False)
        self.window_title.set_subtitle('Clocked out')
        self.status_label.set_label('Clocked out')
        self.append_to_console('🚫  Login cancelled\n')

    def _on_cancel_clicked(self, _btn):
        _cancel_flag.set()
        self.cancel_button.set_sensitive(False)
        self.append_to_console('⏹️   Cancelling…\n')

    # ---- actions --------------------------------------------------- #

    def on_punch_clicked(self, button):
        timestamp = GLib.DateTime.new_now_local()
        ts_str    = timestamp.format('%Y-%m-%d %H:%M:%S')

        if not self._punched_in:
            _cancel_flag.clear()
            self._set_connecting_state()
            self.append_to_console(f'▶  Starting punch-in at {ts_str}…\n')
            threading.Thread(
                target=run_punch_in,
                args=(self.append_to_console,
                      self._on_punch_success,
                      self._on_punch_error,
                      self._on_punch_cancelled),
                daemon=True
            ).start()
        else:
            self._punched_in = False
            elapsed      = timestamp.difference(self._session_start) // 1_000_000
            h, rem       = divmod(elapsed, 3600)
            m, s         = divmod(rem, 60)
            duration     = f'{h}h {m:02d}m {s:02d}s'
            self.punch_button.remove_css_class('destructive-action')
            self.punch_button.add_css_class('suggested-action')
            self.punch_button.set_label('Punch In')
            self.window_title.set_subtitle('Clocked out')
            self.status_label.set_label('Clocked out')
            self.session_label.set_label(f'Last: {duration}')
            self.append_to_console(f'■  Punched out {ts_str}  ({duration})\n\n')
            self._session_start = None
            self.status_dot.queue_draw()

    def on_settings_activated(self, action, param):
        SettingsDialog(self)

    def on_credentials_activated(self, action, param):
        from credentials_dialog import CredentialsDialog
        CredentialsDialog(self)

    def on_super_cool_activated(self, action, param):
        SuperCoolDialog(self)

    def on_about_activated(self, action, param):
        from about import show_about
        show_about(self)


# ------------------------------------------------------------------ #
#  Application                                                         #
# ------------------------------------------------------------------ #

class PunchTrackerApplication(Adw.Application):
    def __init__(self, auto_login=False, **kwargs):
        super().__init__(
            application_id='org.example.PunchTracker',
            flags=Gio.ApplicationFlags.FLAGS_NONE,
            **kwargs
        )
        self._auto_login = auto_login

    def do_activate(self):
        win = PunchTrackerWindow(application=self, auto_login=self._auto_login)
        win.present()


# ------------------------------------------------------------------ #
#  Entry point                                                         #
# ------------------------------------------------------------------ #

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Punch Tracker')
    parser.add_argument(
        '--login',
        action='store_true',
        help='Launch and automatically trigger punch-in on startup'
    )
    args, remaining = parser.parse_known_args()

    app = PunchTrackerApplication(auto_login=args.login)
    app.run(remaining or None)
