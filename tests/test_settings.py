"""Tests for load_settings() and get_credentials() (punch_gui.py)."""

import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
#  Mock GTK imports
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_gtk(monkeypatch):
    gi_mod = MagicMock()
    gi_repo = MagicMock()
    monkeypatch.setitem(sys.modules, "gi", gi_mod)
    monkeypatch.setitem(sys.modules, "gi.repository", gi_repo)
    monkeypatch.setitem(sys.modules, "gi.repository.Adw", gi_repo.Adw)
    monkeypatch.setitem(sys.modules, "gi.repository.Gtk", gi_repo.Gtk)
    monkeypatch.setitem(sys.modules, "gi.repository.GLib", gi_repo.GLib)
    monkeypatch.setitem(sys.modules, "gi.repository.Gio", gi_repo.Gio)
    monkeypatch.setitem(sys.modules, "gi.repository.Gdk", gi_repo.Gdk)


def _load_mod():
    import importlib
    with patch("punch_gui.SETTINGS_PATH", "/dev/null"), \
         patch("punch_gui.CREDS_PATH", "/dev/null"):
        return importlib.import_module("punch_gui")


# ===========================================================================
#  load_settings
# ===========================================================================

class TestLoadSettings:
    def test_valid_json(self, tmp_path):
        settings = {"chromedriver_path": "/usr/bin/chromedriver", "headless": True}
        (tmp_path / "settings.json").write_text(json.dumps(settings))
        mod = _load_mod()
        with patch("punch_gui.SETTINGS_PATH", str(tmp_path / "settings.json")):
            result = mod.load_settings()
        assert result == settings

    def test_missing_file_returns_empty(self):
        mod = _load_mod()
        with patch("punch_gui.SETTINGS_PATH", "/nonexistent/path/settings.json"):
            result = mod.load_settings()
        assert result == {}

    def test_malformed_json_returns_empty(self, tmp_path):
        (tmp_path / "settings.json").write_text("{bad json!!")
        mod = _load_mod()
        with patch("punch_gui.SETTINGS_PATH", str(tmp_path / "settings.json")):
            result = mod.load_settings()
        assert result == {}

    def test_empty_object(self, tmp_path):
        (tmp_path / "settings.json").write_text("{}")
        mod = _load_mod()
        with patch("punch_gui.SETTINGS_PATH", str(tmp_path / "settings.json")):
            result = mod.load_settings()
        assert result == {}

    def test_permission_error_returns_empty(self, tmp_path):
        (tmp_path / "settings.json").write_text('{"key": "val"}')
        mod = _load_mod()
        with patch("punch_gui.SETTINGS_PATH", str(tmp_path / "settings.json")), \
             patch("builtins.open", side_effect=PermissionError("denied")):
            result = mod.load_settings()
        assert result == {}


# ===========================================================================
#  get_credentials
# ===========================================================================

class TestGetCredentials:
    def test_missing_file_returns_empty(self):
        mod = _load_mod()
        with patch("punch_gui.CREDS_PATH", "/nonexistent/credentials.json"):
            login, password = mod.get_credentials({})
        assert login == ""
        assert password == ""

    def test_valid_plaintext(self, tmp_path):
        creds = {"login": "alice", "password": "s3cret"}
        (tmp_path / "credentials.json").write_text(json.dumps(creds))
        mod = _load_mod()
        with patch("punch_gui.CREDS_PATH", str(tmp_path / "credentials.json")):
            login, password = mod.get_credentials({})
        assert login == "alice"
        assert password == "s3cret"

    def test_missing_keys_returns_empty(self, tmp_path):
        (tmp_path / "credentials.json").write_text("{}")
        mod = _load_mod()
        with patch("punch_gui.CREDS_PATH", str(tmp_path / "credentials.json")):
            login, password = mod.get_credentials({})
        assert login == ""
        assert password == ""

    def test_malformed_json_returns_empty(self, tmp_path):
        (tmp_path / "credentials.json").write_text("not json")
        mod = _load_mod()
        with patch("punch_gui.CREDS_PATH", str(tmp_path / "credentials.json")):
            login, password = mod.get_credentials({})
        assert login == ""
        assert password == ""

    def test_gpg_enabled_but_no_key_returns_empty(self, tmp_path):
        creds = {"login": "bob", "password": "pw"}
        (tmp_path / "credentials.json").write_text(json.dumps(creds))
        mod = _load_mod()
        with patch("punch_gui.CREDS_PATH", str(tmp_path / "credentials.json")):
            login, password = mod.get_credentials({"encrypt_credentials": True})
        assert login == "bob"
        assert password == "pw"

    def test_gpg_decrypt_success(self, tmp_path):
        creds_json = json.dumps({"login": "gpguser", "password": "gpgpass"})
        (tmp_path / "credentials.json").write_text("encrypted binary blob")
        mod = _load_mod()

        mock_result = MagicMock()
        mock_result.stdout = creds_json
        with patch("punch_gui.CREDS_PATH", str(tmp_path / "credentials.json")), \
             patch("subprocess.run", return_value=mock_result) as mock_run:
            login, password = mod.get_credentials({
                "encrypt_credentials": True,
                "gpg_key": "ABCDEF01",
            })
        assert login == "gpguser"
        assert password == "gpgpass"
        mock_run.assert_called_once()

    def test_gpg_decrypt_failure_returns_empty(self, tmp_path):
        (tmp_path / "credentials.json").write_text("encrypted")
        mod = _load_mod()
        with patch("punch_gui.CREDS_PATH", str(tmp_path / "credentials.json")), \
             patch("subprocess.run", side_effect=Exception("gpg error")):
            login, password = mod.get_credentials({
                "encrypt_credentials": True,
                "gpg_key": "ABCDEF01",
            })
        assert login == ""
        assert password == ""
