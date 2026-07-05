"""
   Title: src/about.py
   Description: About dialog for Punch Tracker
   Author: Joseph Harry
   Copyright (C): Joseph Harry 2026
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw


def show_about(parent):
    dialog = Adw.AboutDialog()
    dialog.set_application_name('Punch Tracker')
    dialog.set_version('1.2.0')
    dialog.set_developer_name('Joseph Harry')
    dialog.set_copyright('© 2026 Joseph Harry')
    dialog.set_license_type(2)   # GTK_LICENSE_GPL_2_0
    dialog.set_comments(
        'A desktop punch-in/out tool that automates logging in to your '
        'organisation\'s timekeeping portal via Selenium.'
    )
    dialog.set_website('https://github.com/josephharry/punch-tracker')
    dialog.present(parent)
