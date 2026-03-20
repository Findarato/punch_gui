#!/usr/bin/env python3

# License Information
# ==================
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.



import gi
gi.require_version('Adw', '1')
from gi.repository import Adw
from datetime import datetime

def show_about(parent):
    about = Adw.AboutWindow.new()
    about.set_application_name("Punch Tracker")
    about.set_version("1.0 (2026-03-20)")
    about.set_comments(f"Made by Joseph Harry with the help of an AI.")
    about.set_copyright("\n\n Copyright 2026 Joseph Harry")
    about.set_website("https://github.com/findarato/Punch-GUI")
    about.set_icon_name("punch-gui")
    about.set_developers(["Joseph Harry", "GitHub Copilot"])
    about.add_credit_section("Developers", ["Joseph Harry"])
    about.add_credit_section("Contributors", ["GitHub Copilot"])
    about.add_credit_section("Licenses", ["GNU General Public License v3.0 (GPL-3.0)\n\n" +
                       "This program is free software: you can redistribute it and/or modify\n" +
                       "it under the terms of the GNU General Public License as published by\n" +
                       "the Free Software Foundation, either version 3 of the License, or\n" +
                       "(at your option) any later version.\n\n" +
                       "This program is distributed in the hope that it will be useful,\n" +
                       "but WITHOUT ANY WARRANTY; without even the implied warranty of\n" +
                       "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the\n" +
                       "GNU General Public License for more details.\n\n" +
                       "You should have received a copy of the GNU General Public License\n" +
                       "along with this program. If not, see <http://www.gnu.org/licenses/>"])
    about.set_transient_for(parent)
    about.present()