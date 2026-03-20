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

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, GLib, Gio, Gdk


class PunchTrackerWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'PunchTrackerWindow'

    def __init__(self, **kwargs):
        super().__init__(title='Punch Tracker', **kwargs)
        self.set_default_size(480, 560)

        self._punched_in = False
        self._session_start = None

        # --- Minimal CSS: monospace font for the log view only ---
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
        # Adw.ApplicationWindow expects Adw.ToolbarView as content, with the
        # header bar registered via add_top_bar(). This gives correct CSD chrome
        # and the flat/raised header transition on scroll.
        headerbar = Adw.HeaderBar()

        # Use Adw.WindowTitle for a proper title + subtitle pairing
        self.window_title = Adw.WindowTitle(
            title='Punch Tracker',
            subtitle='Clocked out'
        )
        headerbar.set_title_widget(self.window_title)

        # Primary action: punch button lives in the header bar (HIG pattern for
        # single primary actions in utility windows)
        self.punch_button = Gtk.Button(label='Punch In')
        self.punch_button.add_css_class('suggested-action')
        self.punch_button.connect('clicked', self.on_punch_clicked)
        headerbar.pack_end(self.punch_button)

        # Overflow menu for secondary actions (keeps toolbar uncluttered)
        menu = Gio.Menu()
        menu.append('Super Cool…', 'win.super-cool')
        menu.append('About Punch Tracker', 'win.about')

        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name('open-menu-symbolic')
        menu_button.set_menu_model(menu)
        headerbar.pack_start(menu_button)

        # Register actions for the menu items
        super_cool_action = Gio.SimpleAction.new('super-cool', None)
        super_cool_action.connect('activate', self.on_super_cool_activated)
        self.add_action(super_cool_action)

        about_action = Gio.SimpleAction.new('about', None)
        about_action.connect('activate', self.on_about_activated)
        self.add_action(about_action)

        # --- Log view ---
        # ScrolledWindow with the 'frame' CSS class gives the HIG-standard
        # sunken border around scrollable content areas
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

        # Adw.Clamp constrains content to a comfortable reading/interaction
        # width and handles responsive narrowing automatically
        clamp = Adw.Clamp()
        clamp.set_maximum_size(800)
        clamp.set_tightening_threshold(600)
        clamp.set_child(scrolled_window)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        clamp.set_margin_top(12)
        clamp.set_margin_bottom(12)

        # --- Action bar (footer) ---
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

        # Clock in the centre of the action bar
        self.clock_label = Gtk.Label()
        self.clock_label.add_css_class('caption')
        self.clock_label.add_css_class('dim-label')
        action_bar.set_center_widget(self.clock_label)

        # --- Adw.ToolbarView wires everything together correctly ---
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(headerbar)
        toolbar_view.add_bottom_bar(action_bar)
        toolbar_view.set_content(clamp)

        self.set_content(toolbar_view)

        self.start_clock()
        self.populate_test_data()

    # ------------------------------------------------------------------ #
    #  Drawing                                                             #
    # ------------------------------------------------------------------ #

    def _draw_status_dot(self, area, cr, width, height):
        if self._punched_in:
            cr.set_source_rgb(0.35, 0.63, 0.12)   # GNOME green
        else:
            cr.set_source_rgb(0.50, 0.50, 0.50)   # neutral gray
        cr.arc(width / 2, height / 2, min(width, height) / 2, 0, 2 * math.pi)
        cr.fill()

    # ------------------------------------------------------------------ #
    #  Clock                                                               #
    # ------------------------------------------------------------------ #

    def start_clock(self):
        self.update_clock()
        GLib.timeout_add_seconds(1, self.update_clock)

    def update_clock(self):
        now = GLib.DateTime.new_now_local()
        self.clock_label.set_text(now.format('%H:%M:%S'))
        return True

    # ------------------------------------------------------------------ #
    #  Log helpers                                                         #
    # ------------------------------------------------------------------ #

    def append_to_console(self, text):
        end_iter = self.console_buffer.get_end_iter()
        self.console_buffer.insert(end_iter, text)
        self.console_text_view.scroll_to_mark(
            self.console_buffer.get_insert(), 0.0, True, 0.5, 1.0
        )

    def populate_test_data(self):
        import random
        self.console_buffer.set_text('')
        for i in range(1, 1001):
            value = random.random() * 100
            self.append_to_console(f"[{i:04d}]  {value:7.2f}\n")
        self.append_to_console('\n— Test data loaded (1 000 rows) —\n')

    # ------------------------------------------------------------------ #
    #  Actions                                                             #
    # ------------------------------------------------------------------ #

    def on_punch_clicked(self, button):
        timestamp = GLib.DateTime.new_now_local()
        ts_str = timestamp.format('%Y-%m-%d %H:%M:%S')

        if not self._punched_in:
            self._punched_in = True
            self._session_start = timestamp

            # Switch to destructive style so "Punch Out" reads as a strong action
            self.punch_button.remove_css_class('suggested-action')
            self.punch_button.add_css_class('destructive-action')
            self.punch_button.set_label('Punch Out')

            self.window_title.set_subtitle('Punched in')
            self.status_label.set_label('Punched in')
            self.session_label.set_label('Session in progress')
            self.append_to_console(f'▶  Punched in  {ts_str}\n')
        else:
            self._punched_in = False
            elapsed = timestamp.difference(self._session_start) // 1_000_000
            hours, rem = divmod(elapsed, 3600)
            mins, secs = divmod(rem, 60)
            duration = f'{hours}h {mins:02d}m {secs:02d}s'

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
        import random
        colors = ['RED', 'GREEN', 'BLUE', 'YELLOW', 'MAGENTA', 'CYAN', 'ORANGE', 'PINK']
        symbols = ['✨', '⚡', '🔥', '💥', '🚀', '🌀', '🌟', '🥳']

        self.append_to_console('🚨 SUPER COOL SEQUENCE ACTIVATED 🚨\n')
        for idx in range(1, 51):
            color = random.choice(colors)
            symbol = random.choice(symbols)
            self.append_to_console(f"[{idx:02d}] {symbol} FLASH {color} {symbol}\n")
            if idx % 10 == 0:
                self.append_to_console(f"---- DOUBLE RAINBOW 2.0: {idx} 🔥🔥🔥 ----\n")
        self.append_to_console('🎉 SUPER COOL SEQUENCE COMPLETE 🎉\n\n')

    def on_about_activated(self, action, param):
        from about import show_about
        show_about(self)


# ------------------------------------------------------------------ #
#  Application                                                        #
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