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


class PunchTrackerWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'PunchTrackerWindow'

    def __init__(self, **kwargs):
        super().__init__(title='Punch Tracker', **kwargs)
        
        # Set up the main layout
        self.set_default_size(400, 500)

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
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        grid = Gtk.Grid(column_spacing=6, row_spacing=6)

        # Header placeholder row (Adw-style header bar in content area)
        headerbar = Adw.HeaderBar.new()
        headerbar.set_title_widget(Gtk.Label(label='Punch Tracker'))
        headerbar.add_css_class('header-bar')
        headerbar.set_halign(Gtk.Align.FILL)
        headerbar.set_hexpand(True)
        headerbar.set_valign(Gtk.Align.START)

        # About button in headerbar
        about_button = Gtk.Button.new_from_icon_name('help-about-symbolic')
        about_button.connect('clicked', self.on_about_clicked)
        headerbar.pack_start(about_button)

        grid.attach(headerbar, 0, 0, 2, 1)

        self.set_content(grid)

        # Punch row: button + clock label
        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self.punch_button = Gtk.Button(label='Punch In')
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
        grid.attach(top_box, 0, 1, 2, 1)

        # Console text view with padding
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
        scrolled_window.set_margin_bottom(20)
        scrolled_window.set_vexpand(True)
        grid.attach(scrolled_window, 0, 2, 2, 1)

        self.start_clock()
        self.populate_test_data()

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
        # Simulate punching in
        timestamp = GLib.DateTime.new_now_local().format('%Y-%m-%d %H:%M:%S')
        output = f"Punched in at {timestamp}\n"
        self.append_to_console(output)

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