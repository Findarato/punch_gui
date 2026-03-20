#!/usr/bin/env python3

"""
   Title: punch_gui/punch_gui.py
   Description: Main GUI for my Punch Tracker app
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
import time
import os
import json
import sys

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, GLib, Gio, Gdk


# ------------------------------------------------------------------ #
#  Selenium punch worker                                               #
#  Runs entirely on a background thread. Communicates back to the UI  #
#  exclusively via GLib.idle_add() — never touches GTK directly.      #
# ------------------------------------------------------------------ #

def get_settings():
    try:
        path = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(path, 'settings.json')) as f:
            return json.load(f)
    except Exception as e:
        return None, str(e)


def get_credentials():
    try:
        path = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(path, 'credentials.json')) as f:
            creds = json.load(f)
        return creds.get('login', ''), creds.get('password', '')
    except Exception:
        return '', ''


def run_punch_in(log_cb, done_cb, error_cb):
    """
    Blocking Selenium flow. Must be called from a background thread.

    log_cb(str)  — append a line to the console (scheduled via idle_add)
    done_cb()    — called when punch-in succeeds
    error_cb(str)— called on any fatal error
    """

    def log(msg):
        GLib.idle_add(log_cb, msg + '\n')

    def done():
        GLib.idle_add(done_cb)

    def error(msg):
        GLib.idle_add(error_cb, msg + '\n')

    # --- imports (heavy, kept off the main thread) ---
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service as ChromeService
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import WebDriverException
    except ImportError as e:
        error(f'❌  Selenium not installed: {e}')
        return

    # --- settings ---
    settings = get_settings()
    if settings is None:
        error('❌  Could not load settings.json')
        return

    login, password = get_credentials()

    # --- VPN check ---
    log('🪐  Waiting for VPN…')
    vpn_iface = settings.get('vpn_interface', '')
    while True:
        try:
            with open(vpn_iface) as f:
                status = f.read().strip()
            if status == 'up':
                log('✅  VPN is up')
                break
        except Exception:
            pass
        log('😴  VPN not ready — retrying in 10 s')
        time.sleep(10)

    # --- Chrome ---
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

    if settings.get('incognito'):
        chrome_options.add_argument('--incognito')
    if settings.get('mute_audio'):
        chrome_options.add_argument('--mute-audio')
    if settings.get('maximize_window'):
        chrome_options.add_argument('start-maximized')
    if settings.get('headless'):
        chrome_options.add_argument('--headless')

    try:
        service = ChromeService(executable_path=settings['chromedriver_path'])
        driver  = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        error(f'❌  Could not start Chrome: {e}')
        return

    try:
        log('🌐  Navigating to timekeeping portal…')
        driver.get('https://methodisthospitals-sso.prd.mykronos.com/wfd/home')

        # --- Login page detection ---
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
                user_field.send_keys(login)
                driver.find_element('id', 'passwordInput').send_keys(password)
                time.sleep(5.5)
                driver.find_element('id', 'submitButton').click()
                log('⏳  Waiting for portal to load…')
            else:
                log('ℹ️   Auto-login disabled — waiting for manual login…')

        except WebDriverException:
            log('ℹ️   No login page detected — already authenticated?')

        # --- Wait for punch button ---
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located(('id', 'punchSubmitBtnId'))
        )
        log('✅  Logged in to SSO')

        # --- Punch in ---
        log('⏱️   Punching in…')
        driver.find_element('id', 'punchSubmitBtnId').click()
        log('🎉  Punched in successfully!')
        done()

    except WebDriverException as e:
        error(f'❌  WebDriver error: {e}')
    except Exception as e:
        error(f'❌  Unexpected error: {e}')
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
        self.x      = x
        self.y      = y
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
        self.vy += 120 * dt
        self.vx *= 0.985
        self.vy *= 0.985
        self.x  += self.vx * dt
        self.y  += self.vy * dt
        self.life -= self.decay
        return self.life > 0

    def draw(self, cr):
        import colorsys
        for i, (tx, ty) in enumerate(self.trail):
            alpha = (i / len(self.trail)) * self.life * 0.4
            cr.set_source_rgba(*colorsys.hls_to_rgb(self.hue, 0.65, 1.0), alpha)
            r = self.radius * (i / len(self.trail)) * 0.6
            cr.arc(tx, ty, max(r, 0.5), 0, 2 * math.pi)
            cr.fill()
        import colorsys as cs
        cr.set_source_rgba(*cs.hls_to_rgb(self.hue, 0.80, 1.0), self.life)
        cr.arc(self.x, self.y, self.radius * self.life, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgba(1, 1, 1, self.life * 0.7)
        cr.arc(self.x, self.y, self.radius * self.life * 0.4, 0, 2 * math.pi)
        cr.fill()


# ------------------------------------------------------------------ #
#  Firework shell                                                      #
# ------------------------------------------------------------------ #

class FireworkShell:
    def __init__(self, w, h):
        self.x         = random.uniform(w * 0.2, w * 0.8)
        self.y         = random.uniform(h * 0.15, h * 0.55)
        self.hue       = random.random()
        count          = random.randint(60, 110)
        self.particles = [Particle(self.x, self.y, self.hue) for _ in range(count)]
        if random.random() < 0.4:
            hue2 = (self.hue + 0.5) % 1.0
            self.particles += [Particle(self.x, self.y, hue2) for _ in range(count // 3)]

    def step(self, dt):
        self.particles = [p for p in self.particles if p.step(dt)]
        return bool(self.particles)

    def draw(self, cr):
        for p in self.particles:
            p.draw(cr)


# ------------------------------------------------------------------ #
#  Super Cool Dialog                                                   #
# ------------------------------------------------------------------ #

class SuperCoolDialog(Adw.Dialog):
    _FPS       = 60
    _INTERVAL  = 1000 // _FPS
    _DT        = 1 / _FPS
    _SHELL_GAP = 38
    _WIDTH     = 480
    _HEIGHT    = 360

    def __init__(self, parent, auto_close=False):
        super().__init__()
        self.set_title('Super Cool!')
        self.set_content_width(self._WIDTH)
        self.set_content_height(self._HEIGHT)

        self._shells     = []
        self._frame      = 0
        self._timer_id   = None
        self._auto_close = auto_close
        self._w          = self._WIDTH
        self._h          = self._HEIGHT

        toolbar_view = Adw.ToolbarView()
        headerbar    = Adw.HeaderBar()
        headerbar.add_css_class('flat')
        toolbar_view.add_top_bar(headerbar)

        overlay    = Gtk.Overlay()
        self.canvas = Gtk.DrawingArea()
        self.canvas.set_draw_func(self._on_draw)
        self.canvas.set_hexpand(True)
        self.canvas.set_vexpand(True)
        overlay.set_child(self.canvas)

        close_btn = Gtk.Button(label='✨  Dismiss')
        close_btn.add_css_class('suggested-action')
        close_btn.add_css_class('pill')
        close_btn.set_halign(Gtk.Align.CENTER)
        close_btn.set_valign(Gtk.Align.END)
        close_btn.set_margin_bottom(24)
        close_btn.connect('clicked', lambda _: self.close())
        overlay.add_overlay(close_btn)

        toolbar_view.set_content(overlay)
        self.set_child(toolbar_view)
        self.connect('closed', self._on_closed)

        css = Gtk.CssProvider()
        css.load_from_data(b'.firework-bg { background-color: #050510; }')
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.canvas.add_css_class('firework-bg')

        self.present(parent)
        self._start_animation()
        if self._auto_close:
            GLib.timeout_add_seconds(5, self._auto_close_cb)

    def _start_animation(self):
        self._launch_shell()
        self._timer_id = GLib.timeout_add(self._INTERVAL, self._tick)

    def _tick(self):
        self._frame += 1
        self._shells = [s for s in self._shells if s.step(self._DT)]
        if self._frame % self._SHELL_GAP == 0:
            self._launch_shell()
            if random.random() < 0.35:
                self._launch_shell()
        self.canvas.queue_draw()
        return True

    def _launch_shell(self):
        self._shells.append(FireworkShell(self._w, self._h))

    def _on_draw(self, area, cr, width, height):
        self._w = width
        self._h = height
        cr.set_source_rgb(0.02, 0.02, 0.06)
        cr.paint()
        cr.set_source_rgba(0.02, 0.02, 0.06, 0.18)
        cr.paint()
        for shell in self._shells:
            shell.draw(cr)

    def _auto_close_cb(self):
        self.close()
        return False

    def _on_closed(self, _):
        if self._timer_id is not None:
            GLib.source_remove(self._timer_id)
            self._timer_id = None


# ------------------------------------------------------------------ #
#  Main window                                                         #
# ------------------------------------------------------------------ #

class PunchTrackerWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'PunchTrackerWindow'

    def __init__(self, **kwargs):
        super().__init__(title='Punch Tracker', **kwargs)
        self.set_default_size(480, 560)

        self._punched_in    = False
        self._session_start = None

        provider = Gtk.CssProvider()
        provider.load_from_data(b"""
            .log-view {
                font-family: monospace;
                font-size: 13px;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # --- Header bar ---
        headerbar = Adw.HeaderBar()
        self.window_title = Adw.WindowTitle(title='Punch Tracker', subtitle='Clocked out')
        headerbar.set_title_widget(self.window_title)

        self.punch_button = Gtk.Button(label='Punch In')
        self.punch_button.add_css_class('suggested-action')
        self.punch_button.connect('clicked', self.on_punch_clicked)
        headerbar.pack_end(self.punch_button)

        menu = Gio.Menu()
        menu.append('Super Cool…', 'win.super-cool')
        menu.append('About Punch Tracker', 'win.about')
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name('open-menu-symbolic')
        menu_button.set_menu_model(menu)
        headerbar.pack_start(menu_button)

        for name, cb in [('super-cool', self.on_super_cool_activated),
                         ('about',      self.on_about_activated)]:
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
        self.console_text_view.set_left_margin(8)
        self.console_text_view.set_right_margin(8)
        self.console_text_view.set_top_margin(8)
        self.console_text_view.set_bottom_margin(8)
        self.console_buffer = self.console_text_view.get_buffer()
        scrolled_window.set_child(self.console_text_view)

        clamp = Adw.Clamp(maximum_size=800, tightening_threshold=600)
        clamp.set_child(scrolled_window)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        clamp.set_margin_top(12)
        clamp.set_margin_bottom(12)

        # --- Action bar ---
        action_bar = Gtk.ActionBar()

        self.status_dot = Gtk.DrawingArea()
        self.status_dot.set_content_width(10)
        self.status_dot.set_content_height(10)
        self.status_dot.set_draw_func(self._draw_status_dot)

        self.status_label = Gtk.Label(label='Clocked out')
        self.status_label.set_margin_start(6)
        self.status_label.add_css_class('caption')

        action_bar.pack_start(self.status_dot)
        action_bar.pack_start(self.status_label)

        self.session_label = Gtk.Label(label='')
        self.session_label.add_css_class('caption')
        self.session_label.add_css_class('dim-label')
        action_bar.pack_end(self.session_label)

        self.clock_label = Gtk.Label()
        self.clock_label.add_css_class('caption')
        self.clock_label.add_css_class('dim-label')
        action_bar.set_center_widget(self.clock_label)

        # --- Toolbar view ---
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(headerbar)
        toolbar_view.add_bottom_bar(action_bar)
        toolbar_view.set_content(clamp)

        self.set_content(toolbar_view)

        self.start_clock()

    # ---- drawing --------------------------------------------------- #

    def _draw_status_dot(self, area, cr, width, height):
        if self._punched_in:
            cr.set_source_rgb(0.35, 0.63, 0.12)
        else:
            cr.set_source_rgb(0.50, 0.50, 0.50)
        cr.arc(width / 2, height / 2, min(width, height) / 2, 0, 2 * math.pi)
        cr.fill()

    # ---- clock ----------------------------------------------------- #

    def start_clock(self):
        self.update_clock()
        GLib.timeout_add_seconds(1, self.update_clock)

    def update_clock(self):
        now = GLib.DateTime.new_now_local()
        self.clock_label.set_text(now.format('%H:%M:%S'))
        return True

    # ---- log ------------------------------------------------------- #

    def append_to_console(self, text):
        end_iter = self.console_buffer.get_end_iter()
        self.console_buffer.insert(end_iter, text)
        self.console_text_view.scroll_to_mark(
            self.console_buffer.get_insert(), 0.0, True, 0.5, 1.0
        )
        return False   # safe to use as idle_add callback

    def populate_test_data(self):
        self.console_buffer.set_text('')
        for i in range(1, 1001):
            value = random.random() * 100
            self.append_to_console(f"[{i:04d}]  {value:7.2f}\n")
        self.append_to_console('\n— Test data loaded (1 000 rows) —\n')

    # ---- punch-in state -------------------------------------------- #

    def _set_punching_in_state(self):
        """UI state while Selenium is running — button disabled."""
        self.punch_button.set_sensitive(False)
        self.punch_button.set_label('Connecting…')
        self.window_title.set_subtitle('Connecting…')
        self.status_label.set_label('Connecting…')

    def _on_punch_success(self):
        """Called from background thread via idle_add when Selenium succeeds."""
        timestamp           = GLib.DateTime.new_now_local()
        self._punched_in    = True
        self._session_start = timestamp

        self.punch_button.set_sensitive(True)
        self.punch_button.remove_css_class('suggested-action')
        self.punch_button.add_css_class('destructive-action')
        self.punch_button.set_label('Punch Out')

        self.window_title.set_subtitle('Punched in')
        self.status_label.set_label('Punched in')
        self.session_label.set_label('Session in progress')
        self.status_dot.queue_draw()

        SuperCoolDialog(self, auto_close=True)

    def _on_punch_error(self, message):
        """Called from background thread via idle_add on Selenium failure."""
        self.punch_button.set_sensitive(True)
        self.punch_button.set_label('Punch In')
        self.window_title.set_subtitle('Clocked out — error occurred')
        self.status_label.set_label('Error')
        self.append_to_console(message)

    # ---- actions --------------------------------------------------- #

    def on_punch_clicked(self, button):
        timestamp = GLib.DateTime.new_now_local()
        ts_str    = timestamp.format('%Y-%m-%d %H:%M:%S')

        if not self._punched_in:
            # Disable UI immediately, then hand off to background thread
            self._set_punching_in_state()
            self.append_to_console(f'▶  Starting punch-in at {ts_str}…\n')

            t = threading.Thread(
                target=run_punch_in,
                args=(self.append_to_console,
                      self._on_punch_success,
                      self._on_punch_error),
                daemon=True
            )
            t.start()

        else:
            # Punch out is local only — no Selenium needed
            self._punched_in = False
            elapsed       = timestamp.difference(self._session_start) // 1_000_000
            hours, rem    = divmod(elapsed, 3600)
            mins, secs    = divmod(rem, 60)
            duration      = f'{hours}h {mins:02d}m {secs:02d}s'

            self.punch_button.remove_css_class('destructive-action')
            self.punch_button.add_css_class('suggested-action')
            self.punch_button.set_label('Punch In')
            self.window_title.set_subtitle('Clocked out')
            self.status_label.set_label('Clocked out')
            self.session_label.set_label(f'Last: {duration}')
            self.append_to_console(f'■  Punched out {ts_str}  ({duration})\n\n')
            self._session_start = None
            self.status_dot.queue_draw()

    def on_super_cool_activated(self, action, param):
        SuperCoolDialog(self)

    def on_about_activated(self, action, param):
        from about import show_about
        show_about(self)


# ------------------------------------------------------------------ #
#  Application                                                         #
# ------------------------------------------------------------------ #

class PunchTrackerApplication(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(
            application_id='org.example.PunchTracker',
            flags=Gio.ApplicationFlags.FLAGS_NONE,
            **kwargs
        )

    def do_activate(self):
        win = PunchTrackerWindow(application=self)
        win.present()


if __name__ == '__main__':
    app = PunchTrackerApplication()
    app.run(None)