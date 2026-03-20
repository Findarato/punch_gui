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

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, GLib, Gio, Gdk
import math


class PunchTrackerWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'PunchTrackerWindow'

    def __init__(self, **kwargs):
        super().__init__(title='Punch Tracker', **kwargs)

        self.set_default_size(400, 500)

        self._punched_in = False
        self._session_start = None

        provider = Gtk.CssProvider()
        provider.load_from_data(b"""
            textview.with-border, .textview-border {
                border: 2px solid #888;
                border-radius: 8px;
                padding: 4px;
                background-color: transparent;
            }
            textview.with-border text, .textview-border text {
                color: white;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Header bar
        headerbar = Adw.HeaderBar.new()
        headerbar.set_title_widget(Gtk.Label(label='Punch Tracker'))
        headerbar.add_css_class('header-bar')

        about_button = Gtk.Button.new_from_icon_name('help-about-symbolic')
        about_button.connect('clicked', self.on_about_clicked)
        headerbar.pack_start(about_button)

        outer_box.append(headerbar)

        # Punch row: button + clock label
        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self.punch_button = Gtk.Button(label='Punch In')
        self.punch_button.add_css_class('suggested-action')
        self.punch_button.connect('clicked', self.on_punch_clicked)
        top_box.append(self.punch_button)

        self.super_cool_button = Gtk.Button(label='Super Cool')
        self.super_cool_button.connect('clicked', self.on_super_cool_clicked)
        top_box.append(self.super_cool_button)

        self.clock_label = Gtk.Label(label='00:00:00')
        self.clock_label.set_valign(Gtk.Align.CENTER)
        top_box.append(self.clock_label)

        top_box.set_margin_start(12)
        top_box.set_margin_end(12)
        top_box.set_margin_top(6)
        top_box.set_margin_bottom(6)
        outer_box.append(top_box)

        # Console text view
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)
        self.console_text_view = Gtk.TextView()
        self.console_text_view.add_css_class('textview-border')
        self.console_text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.console_buffer = self.console_text_view.get_buffer()
        scrolled_window.set_child(self.console_text_view)
        scrolled_window.set_margin_start(12)
        scrolled_window.set_margin_end(12)
        scrolled_window.set_margin_top(6)
        scrolled_window.set_margin_bottom(6)
        scrolled_window.set_vexpand(True)
        outer_box.append(scrolled_window)

        # Action bar (GNOME HIG footer)
        action_bar = Gtk.ActionBar()

        self.status_dot = Gtk.DrawingArea()
        self.status_dot.set_content_width(10)
        self.status_dot.set_content_height(10)
        self.status_dot.set_draw_func(self._draw_status_dot)

        self.status_label = Gtk.Label(label='Status: Clocked out')
        self.status_label.set_margin_start(4)

        action_bar.pack_start(self.status_dot)
        action_bar.pack_start(self.status_label)

        self.session_label = Gtk.Label(label='Session: —')
        action_bar.pack_end(self.session_label)

        outer_box.append(action_bar)

        self.set_content(outer_box)

        self.start_clock()
        self.populate_test_data()

    def _draw_status_dot(self, area, cr, width, height):
        if self._punched_in:
            cr.set_source_rgb(0.39, 0.60, 0.13)  # green
        else:
            cr.set_source_rgb(0.55, 0.55, 0.55)  # gray
        cr.arc(width / 2, height / 2, min(width, height) / 2, 0, 2 * math.pi)
        cr.fill()

    def start_clock(self):
        self.update_clock()
        GLib.timeout_add_seconds(1, self.update_clock)

    def update_clock(self):
        now = GLib.DateTime.new_now_local()
        self.clock_label.set_text(now.format('%Y-%m-%d %H:%M:%S'))
        return True

    def populate_test_data(self):
        import random

        self.console_buffer.set_text('')
        for i in range(1, 1001):
            value = random.random() * 100
            self.append_to_console(f"Test data [{i:04d}] = {value:0.2f}\n")

        self.append_to_console('\n-- Test data loaded (1000 rows) --\n')

    def on_punch_clicked(self, button):
        timestamp = GLib.DateTime.new_now_local()
        ts_str = timestamp.format('%Y-%m-%d %H:%M:%S')

        if not self._punched_in:
            self._punched_in = True
            self._session_start = timestamp
            self.punch_button.set_label('Punch Out')
            self.status_label.set_label('Status: Punched in')
            self.session_label.set_label('Session: in progress')
            self.append_to_console(f'Punched in at {ts_str}\n')
        else:
            self._punched_in = False
            elapsed = timestamp.difference(self._session_start) // 1_000_000  # microseconds → seconds
            hours, rem = divmod(elapsed, 3600)
            mins, secs = divmod(rem, 60)
            duration = f'{hours}h {mins}m {secs}s'
            self.punch_button.set_label('Punch In')
            self.status_label.set_label('Status: Clocked out')
            self.session_label.set_label(f'Last session: {duration}')
            self.append_to_console(f'Punched out at {ts_str} (duration: {duration})\n')
            self._session_start = None

        self.status_dot.queue_draw()

    def append_to_console(self, text):
        end_iter = self.console_buffer.get_end_iter()
        self.console_buffer.insert(end_iter, text)
        self.console_text_view.scroll_to_mark(self.console_buffer.get_insert(), 0.0, True, 0.5, 1.0)

    def on_super_cool_clicked(self, button):
        import random

        colors = ['RED', 'GREEN', 'BLUE', 'YELLOW', 'MAGENTA', 'CYAN', 'ORANGE', 'PINK']
        symbols = ['✨', '⚡', '🔥', '💥', '🚀', '🌀', '🌟', '🥳']

        self.clock_label.set_text('SUPER COOL MODE')
        self.append_to_console('🚨 SUPER COOL SEQUENCE ACTIVATED 🚨\n')

        for idx in range(1, 51):
            color = random.choice(colors)
            symbol = random.choice(symbols)
            self.append_to_console(f"[{idx:02d}] {symbol} FLASH {color} {symbol} \n")
            if idx % 10 == 0:
                self.append_to_console(f"---- DOUBLE RAINBOW 2.0: {idx} 🔥 🔥 🔥 ----\n")

        self.append_to_console('🎉 SUPER COOL SEQUENCE COMPLETE 🎉\n\n')
        self.clock_label.set_text(GLib.DateTime.new_now_local().format('%Y-%m-%d %H:%M:%S'))

    def on_about_clicked(self, button):
        from about import show_about
        show_about(self)


class PunchTrackerApplication(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(application_id='org.example.PunchTracker',
                         flags=Gio.ApplicationFlags.FLAGS_NONE, **kwargs)

    def do_activate(self):
        win = PunchTrackerWindow(application=self)
        win.present()


if __name__ == '__main__':
    app = PunchTrackerApplication()
    app.run(None)