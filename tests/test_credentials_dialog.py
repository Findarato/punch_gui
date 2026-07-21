"""Tests for credentials_dialog helper functions (src/credentials_dialog.py)."""

import json
import os
import sys
from unittest.mock import patch, MagicMock, call

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


def _import_helpers(tmp_path):
    """Import the credentials_dialog module with paths pointing at tmp_path."""
    creds_path = str(tmp_path / "credentials.json")
    settings_path = str(tmp_path / "settings.json")

    import importlib
    # Force re-import so module-level constants are patchable
    if "credentials_dialog" in sys.modules:
        del sys.modules["credentials_dialog"]

    with patch.dict(os.environ):
        pass

    # We need to insert src/ into path for the import
    src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    mod = importlib.import_module("credentials_dialog")

    # Patch the module-level path constants
    mod.CREDS_PATH = creds_path
    mod.SETTINGS_PATH = settings_path
    return mod


# ===========================================================================
#  _load_settings
# ===========================================================================

class TestLoadSettings:
    def test_valid_json(self, tmp_path):
        settings = {"key": "value", "number": 42}
        (tmp_path / "settings.json").write_text(json.dumps(settings))
        mod = _import_helpers(tmp_path)
        result = mod._load_settings()
        assert result == settings

    def test_missing_file(self, tmp_path):
        mod = _import_helpers(tmp_path)
        result = mod._load_settings()
        assert result == {}

    def test_malformed_json(self, tmp_path):
        (tmp_path / "settings.json").write_text("{{{")
        mod = _import_helpers(tmp_path)
        result = mod._load_settings()
        assert result == {}


# ===========================================================================
#  _save_settings
# ===========================================================================

class TestSaveSettings:
    def test_round_trip(self, tmp_path):
        mod = _import_helpers(tmp_path)
        data = {"chromedriver_path": "/usr/bin/chromedriver", "headless": True}
        mod._save_settings(data)
        result = mod._load_settings()
        assert result == data

    def test_overwrites_existing(self, tmp_path):
        mod = _import_helpers(tmp_path)
        mod._save_settings({"old": True})
        mod._save_settings({"new": True})
        result = mod._load_settings()
        assert result == {"new": True}

    def test_permission_error_prints_stderr(self, tmp_path):
        mod = _import_helpers(tmp_path)
        with patch("builtins.open", side_effect=PermissionError("denied")):
            # Should not raise, just print to stderr
            mod._save_settings({"key": "val"})


# ===========================================================================
#  _load_credentials
# ===========================================================================

class TestLoadCredentials:
    def test_missing_file(self, tmp_path):
        mod = _import_helpers(tmp_path)
        login, password = mod._load_credentials({})
        assert login == ""
        assert password == ""

    def test_plaintext_read(self, tmp_path):
        creds = {"login": "user1", "password": "pass1"}
        (tmp_path / "credentials.json").write_text(json.dumps(creds))
        mod = _import_helpers(tmp_path)
        login, password = mod._load_credentials({})
        assert login == "user1"
        assert password == "pass1"

    def test_gpg_decrypt_success(self, tmp_path):
        creds_json = json.dumps({"login": "gpg_user", "password": "gpg_pass"})
        (tmp_path / "credentials.json").write_text("encrypted")
        mod = _import_helpers(tmp_path)

        mock_result = MagicMock()
        mock_result.stdout = creds_json
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            login, password = mod._load_credentials({
                "encrypt_credentials": True,
                "gpg_key": "ABCDEF01",
            })
        assert login == "gpg_user"
        assert password == "gpg_pass"
        mock_run.assert_called_once()

    def test_gpg_decrypt_failure(self, tmp_path):
        (tmp_path / "credentials.json").write_text("encrypted")
        mod = _import_helpers(tmp_path)
        with patch("subprocess.run", side_effect=Exception("gpg error")):
            login, password = mod._load_credentials({
                "encrypt_credentials": True,
                "gpg_key": "KEY123",
            })
        assert login == ""
        assert password == ""

    def test_gpg_enabled_no_key_falls_to_plaintext(self, tmp_path):
        creds = {"login": "fallback", "password": "fpw"}
        (tmp_path / "credentials.json").write_text(json.dumps(creds))
        mod = _import_helpers(tmp_path)
        login, password = mod._load_credentials({"encrypt_credentials": True})
        assert login == "fallback"
        assert password == "fpw"

    def test_malformed_json(self, tmp_path):
        (tmp_path / "credentials.json").write_text("not json")
        mod = _import_helpers(tmp_path)
        login, password = mod._load_credentials({})
        assert login == ""
        assert password == ""


# ===========================================================================
#  _save_credentials
# ===========================================================================

class TestSaveCredentials:
    def test_plaintext_write(self, tmp_path):
        mod = _import_helpers(tmp_path)
        ok, err = mod._save_credentials("alice", "pw123", {})
        assert ok is True
        assert err == ""

        # Verify the file was written correctly
        with open(tmp_path / "credentials.json") as f:
            data = json.load(f)
        assert data == {"login": "alice", "password": "pw123"}

    def test_plaintext_overwrite(self, tmp_path):
        mod = _import_helpers(tmp_path)
        mod._save_credentials("old", "oldpw", {})
        mod._save_credentials("new", "newpw", {})
        with open(tmp_path / "credentials.json") as f:
            data = json.load(f)
        assert data == {"login": "new", "password": "newpw"}

    def test_gpg_encrypt_success(self, tmp_path):
        (tmp_path / "credentials.json").write_text("")
        mod = _import_helpers(tmp_path)

        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            ok, err = mod._save_credentials("bob", "secret", {
                "encrypt_credentials": True,
                "gpg_key": "ABCD1234",
            })
        assert ok is True
        assert err == ""
        mock_run.assert_called_once()

    def test_gpg_encrypt_failure(self, tmp_path):
        mod = _import_helpers(tmp_path)
        import subprocess as sp
        with patch("subprocess.run", side_effect=sp.CalledProcessError(2, "gpg", stderr="encrypt error")):
            ok, err = mod._save_credentials("bob", "secret", {
                "encrypt_credentials": True,
                "gpg_key": "ABCD1234",
            })
        assert ok is False
        assert "encrypt error" in err

    def test_gpg_not_installed(self, tmp_path):
        mod = _import_helpers(tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError("gpg not found")):
            ok, err = mod._save_credentials("bob", "secret", {
                "encrypt_credentials": True,
                "gpg_key": "ABCD1234",
            })
        assert ok is False
        assert "gpg not found" in err

    def test_write_permission_error(self, tmp_path):
        mod = _import_helpers(tmp_path)
        with patch("builtins.open", side_effect=PermissionError("denied")):
            ok, err = mod._save_credentials("alice", "pw", {})
        assert ok is False
        assert "denied" in err


# ===========================================================================
#  _list_gpg_keys
# ===========================================================================

class TestListGpgKeys:
    def test_parses_colon_output(self, tmp_path):
        mod = _import_helpers(tmp_path)
        gpg_output = (
            "tru::1:1610000000:0:3:1:5\n"
            "pub:u:2048:1:ABCDEF0123456789:1610000000:::u:::scESC:\n"
            "fpr:::::::::ABCDEF0123456789ABCDEF0123456789ABCDEF01:\n"
            "uid:u::::1610000000::ABCDEF0123456789::Test User <test@example.com>:\n"
        )
        mock_result = MagicMock()
        mock_result.stdout = gpg_output
        with patch("subprocess.run", return_value=mock_result):
            keys = mod._list_gpg_keys()
        assert len(keys) == 1
        key_id, uid = keys[0]
        # parts[4] = "ABCDEF0123456789", [-8:] = "23456789"
        assert key_id == "23456789"
        assert "Test User" in uid

    def test_empty_keyring(self, tmp_path):
        mod = _import_helpers(tmp_path)
        mock_result = MagicMock()
        mock_result.stdout = "tru::1:1610000000:0:3:1:5\n"
        with patch("subprocess.run", return_value=mock_result):
            keys = mod._list_gpg_keys()
        assert keys == []

    def test_gpg_not_installed(self, tmp_path):
        mod = _import_helpers(tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError("gpg not found")):
            keys = mod._list_gpg_keys()
        assert keys == []

    def test_gpg_command_fails(self, tmp_path):
        mod = _import_helpers(tmp_path)
        import subprocess as sp
        with patch("subprocess.run", side_effect=sp.CalledProcessError(1, "gpg")):
            keys = mod._list_gpg_keys()
        assert keys == []

    def test_multiple_keys(self, tmp_path):
        mod = _import_helpers(tmp_path)
        gpg_output = (
            "pub:u:2048:1:AAAAAAAAAAAAAAAA:1610000000:::u:::scESC:\n"
            "uid:u::::1610000000::AAAAAAAAAAAAAAAA::User One <one@example.com>:\n"
            "pub:u:2048:1:BBBBBBBBBBBBBBBB:1610000000:::u:::scESC:\n"
            "uid:u::::1610000000::BBBBBBBBBBBBBBBB::User Two <two@example.com>:\n"
        )
        mock_result = MagicMock()
        mock_result.stdout = gpg_output
        with patch("subprocess.run", return_value=mock_result):
            keys = mod._list_gpg_keys()
        assert len(keys) == 2
        assert "User One" in keys[0][1]
        assert "User Two" in keys[1][1]
