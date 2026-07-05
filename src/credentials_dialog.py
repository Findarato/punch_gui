"""
   Title: src/credentials_dialog.py
   Description: Edit credentials.json (login / password) with optional GPG encryption
   Author: Joseph Harry
   Copyright (C): Joseph Harry 2026
"""

import gi
import os
import json
import subprocess
import sys

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, GLib, Gio


# ------------------------------------------------------------------ #
#  Helpers                                                             #
# ------------------------------------------------------------------ #

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDS_PATH = os.path.join(BASE_DIR, 'credentials.json')
SETTINGS_PATH = os.path.join(BASE_DIR, 'settings.json')


def _load_settings():
    try:
        with open(SETTINGS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_settings(data):
    try:
        with open(SETTINGS_PATH, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f'Could not save settings: {e}', file=sys.stderr)


def _load_credentials(settings):
    """Return (login, password) decrypting if needed."""
    if not os.path.exists(CREDS_PATH):
        return '', ''

    use_gpg = settings.get('encrypt_credentials', False)
    gpg_key = settings.get('gpg_key', '')

    if use_gpg and gpg_key:
        try:
            result = subprocess.run(
                ['gpg', '--quiet', '--batch', '--yes',
                 '--decrypt', CREDS_PATH],
                capture_output=True, text=True, check=True
            )
            creds = json.loads(result.stdout)
        except Exception as e:
            print(f'GPG decrypt failed: {e}', file=sys.stderr)
            return '', ''
    else:
        try:
            with open(CREDS_PATH) as f:
                creds = json.load(f)
        except Exception:
            return '', ''

    return creds.get('login', ''), creds.get('password', '')


def _save_credentials(login, password, settings):
    """Write credentials.json, encrypting with GPG if configured."""
    use_gpg = settings.get('encrypt_credentials', False)
    gpg_key = settings.get('gpg_key', '')

    data = json.dumps({'login': login, 'password': password}, indent=4)

    if use_gpg and gpg_key:
        try:
            result = subprocess.run(
                ['gpg', '--quiet', '--batch', '--yes',
                 '--recipient', gpg_key,
                 '--output', CREDS_PATH,
                 '--encrypt'],
                input=data, capture_output=True, text=True, check=True
            )
        except subprocess.CalledProcessError as e:
            return False, f'GPG encrypt failed: {e.stderr.strip()}'
        except FileNotFoundError:
            return False, 'gpg not found — is GnuPG installed?'
    else:
        try:
            with open(CREDS_PATH, 'w') as f:
                f.write(data)
        except Exception as e:
            return False, str(e)

    return True, ''


def _list_gpg_keys():
    """Return list of (key_id, uid) tuples from the user's GPG keyring."""
    try:
        result = subprocess.run(
            ['gpg', '--list-keys', '--with-colons'],
            capture_output=True, text=True, check=True
        )
        keys = []
        current_id = None
        for line in result.stdout.splitlines():
            parts = line.split(':')
            if parts[0] == 'pub':
                current_id = parts[4][-8:] if len(parts) > 4 else None
            elif parts[0] == 'uid' and current_id:
                uid = parts[9] if len(parts) > 9 else '(unknown)'
                keys.append((current_id, uid))
                current_id = None
        return keys
    except Exception:
        return []


# ------------------------------------------------------------------ #
#  Dialog                                                              #
# ------------------------------------------------------------------ #

class CredentialsDialog(Adw.Dialog):
    """Edit login/password stored in credentials.json with optional GPG encryption."""

    def __init__(self, parent):
        super().__init__()
        self.set_title('Sign-in Credentials')
        self.set_content_width(580)

        self._settings = _load_settings()
        login, password = _load_credentials(self._settings)

        # ---- header bar ----
        headerbar = Adw.HeaderBar()

        cancel_btn = Gtk.Button(label='Cancel')
        cancel_btn.connect('clicked', lambda _: self.close())
        headerbar.pack_start(cancel_btn)

        save_btn = Gtk.Button(label='Save')
        save_btn.add_css_class('suggested-action')
        save_btn.connect('clicked', self._on_save)
        headerbar.pack_end(save_btn)

        # ---- page ----
        page = Adw.PreferencesPage()

        # --- Credentials group ---
        creds_group = Adw.PreferencesGroup(title='Credentials')
        page.add(creds_group)

        self._login_row = Adw.EntryRow(title='Username')
        self._login_row.set_text(login)
        creds_group.add(self._login_row)

        # Password row with visibility toggle
        self._password_row = Adw.PasswordEntryRow(title='Password')
        self._password_row.set_text(password)
        creds_group.add(self._password_row)

        # --- Encryption group ---
        enc_group = Adw.PreferencesGroup(
            title='Encryption',
            description='When enabled, credentials.json is GPG-encrypted on disk.'
        )
        page.add(enc_group)

        self._encrypt_switch = self._make_switch_row(
            enc_group,
            'Encrypt credentials file',
            'Use a GPG key to encrypt credentials.json',
            self._settings.get('encrypt_credentials', False)
        )
        self._encrypt_switch.connect('state-set', self._on_encrypt_toggled)

        # GPG key selector — uses a full-width layout inside a PreferencesRow
        # so the dropdown isn't crammed into a narrow ActionRow suffix slot.
        self._gpg_row = Adw.PreferencesRow()
        gpg_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        gpg_box.set_margin_start(12)
        gpg_box.set_margin_end(12)
        gpg_box.set_margin_top(10)
        gpg_box.set_margin_bottom(10)

        gpg_label = Gtk.Label(label='GPG Key')
        gpg_label.set_halign(Gtk.Align.START)
        gpg_label.add_css_class('caption')

        self._gpg_string_list = Gtk.StringList()
        self._gpg_dropdown = Gtk.DropDown(model=self._gpg_string_list)
        self._gpg_dropdown.set_hexpand(True)
        self._populate_gpg_dropdown()

        gpg_box.append(gpg_label)
        gpg_box.append(self._gpg_dropdown)
        self._gpg_row.set_child(gpg_box)
        enc_group.add(self._gpg_row)

        self._gpg_row.set_visible(self._settings.get('encrypt_credentials', False))

        # ---- layout ----
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(headerbar)
        toolbar_view.set_content(page)
        self.set_child(toolbar_view)

        self.present(parent)

    # ---- helpers --------------------------------------------------- #

    @staticmethod
    def _make_switch_row(group, title, subtitle, active):
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        switch = Gtk.Switch(active=active)
        switch.set_valign(Gtk.Align.CENTER)
        row.add_suffix(switch)
        row.set_activatable_widget(switch)
        group.add(row)
        return switch

    def _populate_gpg_dropdown(self):
        self._gpg_string_list.splice(0, self._gpg_string_list.get_n_items(), [])
        self._gpg_keys = _list_gpg_keys()
        current = self._settings.get('gpg_key', '')
        active_idx = 0
        if self._gpg_keys:
            for i, (key_id, uid) in enumerate(self._gpg_keys):
                short_uid = uid[:30] + '…' if len(uid) > 30 else uid
                self._gpg_string_list.append(f'{key_id}  {short_uid}')
                if key_id == current:
                    active_idx = i
            self._gpg_dropdown.set_selected(active_idx)
        else:
            self._gpg_string_list.append('No GPG keys found')
            self._gpg_dropdown.set_selected(0)

    def _on_encrypt_toggled(self, switch, state):
        self._gpg_row.set_visible(state)

    def _on_save(self, _btn):
        login    = self._login_row.get_text().strip()
        password = self._password_row.get_text()
        use_gpg  = self._encrypt_switch.get_active()

        # Resolve selected GPG key
        gpg_key = ''
        if use_gpg and self._gpg_keys:
            idx = self._gpg_dropdown.get_selected()
            if 0 <= idx < len(self._gpg_keys):
                gpg_key = self._gpg_keys[idx][0]

        # Persist encryption preference and key into settings.json
        self._settings['encrypt_credentials'] = use_gpg
        self._settings['gpg_key'] = gpg_key
        _save_settings(self._settings)

        ok, err = _save_credentials(login, password, self._settings)
        if ok:
            self.close()
        else:
            # Surface error as a banner inside the dialog
            self._show_error(err)

    def _show_error(self, message):
        banner = Adw.Banner(title=f'Error: {message}', revealed=True)
        # Re-parent into the toolbar view's content area isn't straightforward
        # for a bare Adw.Dialog, so we fall back to a simple message dialog.
        msg = Adw.MessageDialog(heading='Could not save credentials',
                                body=message)
        msg.add_response('ok', 'OK')
        msg.present(self)
