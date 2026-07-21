"""Tests for run_punch_in() (punch_gui.py)."""

import importlib
import json
import sys
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
#  Mock GTK at import time so punch_gui can be loaded headlessly.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_cancel_flag():
    """Ensure the shared cancel flag is clear before every test."""
    mod = sys.modules.get("punch_gui")
    if mod and hasattr(mod, "_cancel_flag"):
        mod._cancel_flag.clear()
    yield
    if mod and hasattr(mod, "_cancel_flag"):
        mod._cancel_flag.clear()


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


def _ensure_mod():
    """Ensure punch_gui is imported (with mocked GTK). Returns the module."""
    if "punch_gui" in sys.modules:
        return sys.modules["punch_gui"]
    with patch("punch_gui.SETTINGS_PATH", "/dev/null"), \
         patch("punch_gui.CREDS_PATH", "/dev/null"):
        return importlib.import_module("punch_gui")


def _build_selenium():
    mock_selenium = MagicMock()
    mock_wd = mock_selenium.webdriver
    mock_chrome = mock_wd.chrome
    mock_options = mock_chrome.options
    mock_service_mod = mock_chrome.service
    mock_support = mock_selenium.webdriver.support
    mock_ui = mock_support.ui
    mock_ec_mod = mock_support.expected_conditions
    mock_common = mock_selenium.common
    mock_exceptions = mock_common.exceptions

    mods = {
        "selenium": mock_selenium,
        "selenium.webdriver": mock_wd,
        "selenium.webdriver.chrome": mock_chrome,
        "selenium.webdriver.chrome.options": mock_options,
        "selenium.webdriver.chrome.service": mock_service_mod,
        "selenium.webdriver.support": mock_support,
        "selenium.webdriver.support.ui": mock_ui,
        "selenium.webdriver.support.expected_conditions": mock_ec_mod,
        "selenium.common": mock_common,
        "selenium.common.exceptions": mock_exceptions,
    }
    return mods, mock_wd, mock_options, mock_service_mod, mock_ui, mock_ec_mod, mock_exceptions


# ===========================================================================
#  run_punch_in — early exits
# ===========================================================================

class TestRunPunchInNoSettings:
    def test_error_when_no_settings(self):
        mod = _ensure_mod()
        cbs = [MagicMock() for _ in range(4)]
        mock_glib = MagicMock()
        mock_glib.idle_add.side_effect = lambda cb, *a, **kw: cb(*a, **kw)

        with patch("punch_gui.load_settings", return_value={}), \
             patch("punch_gui.GLib", mock_glib):
            mod.run_punch_in(*cbs)

        cbs[2].assert_called_once()  # error_cb
        assert "settings" in cbs[2].call_args[0][0].lower()


class TestRunPunchInNoSelenium:
    def test_error_when_selenium_missing(self):
        mod = _ensure_mod()
        cbs = [MagicMock() for _ in range(4)]
        settings = {"chromedriver_path": "/usr/bin/chromedriver"}
        mock_glib = MagicMock()
        mock_glib.idle_add.side_effect = lambda cb, *a, **kw: cb(*a, **kw)

        with patch("punch_gui.load_settings", return_value=settings), \
             patch("punch_gui.GLib", mock_glib), \
             patch.dict("sys.modules", {"selenium": None}):
            mod.run_punch_in(*cbs)

        cbs[2].assert_called_once()  # error_cb
        assert "selenium" in cbs[2].call_args[0][0].lower()


# ===========================================================================
#  run_punch_in — VPN checks
# ===========================================================================

class TestRunPunchInVpnCheck:
    def test_vpn_url_success(self):
        mod = _ensure_mod()
        log_cb, done_cb, error_cb, cancel_cb = [MagicMock() for _ in range(4)]

        settings = {
            "VPN Update Path": "http://vpn.internal/health",
            "vpn_interface": "",
            "chromedriver_path": "/usr/bin/chromedriver",
            "work_sso_location": "https://sso.example.com",
        }

        mock_glib = MagicMock()
        mock_glib.idle_add.side_effect = lambda cb, *a, **kw: cb(*a, **kw)

        sel_mocks, mock_wd, mock_opts, mock_svc, mock_ui, mock_ec, mock_exc = _build_selenium()
        mock_driver = MagicMock()

        with patch("punch_gui.load_settings", return_value=settings), \
             patch("punch_gui.get_credentials", return_value=("u", "p")), \
             patch("punch_gui.GLib", mock_glib), \
             patch("urllib.request.urlopen", return_value=MagicMock()), \
             patch.dict("sys.modules", sel_mocks), \
             patch("time.sleep"):
            mock_wd.Chrome.return_value = mock_driver
            mock_ui.WebDriverWait.return_value.until.side_effect = [
                Exception("no login page"),
                MagicMock(),
            ]
            mod.run_punch_in(log_cb, done_cb, error_cb, cancel_cb)

        log_msgs = [c.args[0] for c in log_cb.call_args_list]
        assert any("VPN is up" in msg for msg in log_msgs)

    def test_vpn_cancel_during_retry(self):
        mod = _ensure_mod()
        log_cb, done_cb, error_cb, cancel_cb = [MagicMock() for _ in range(4)]

        settings = {
            "VPN Update Path": "http://vpn.internal/health",
            "vpn_interface": "",
        }

        mock_glib = MagicMock()
        mock_glib.idle_add.side_effect = lambda cb, *a, **kw: cb(*a, **kw)

        call_count = [0]

        def set_cancel_then_fail(url, timeout=None):
            call_count[0] += 1
            if call_count[0] >= 1:
                mod._cancel_flag.set()
            raise Exception("not reachable")

        with patch("punch_gui.load_settings", return_value=settings), \
             patch("punch_gui.get_credentials", return_value=("", "")), \
             patch("punch_gui.GLib", mock_glib), \
             patch("urllib.request.urlopen", side_effect=set_cancel_then_fail), \
             patch("time.sleep"):
            mod.run_punch_in(log_cb, done_cb, error_cb, cancel_cb)

        cancel_cb.assert_called_once()

    def test_vpn_interface_check(self):
        mod = _ensure_mod()
        log_cb, done_cb, error_cb, cancel_cb = [MagicMock() for _ in range(4)]

        settings = {
            "VPN Update Path": "",
            "vpn_interface": "/sys/class/net/vpn0/operstate",
            "chromedriver_path": "/usr/bin/chromedriver",
            "work_sso_location": "https://sso.example.com",
        }

        mock_glib = MagicMock()
        mock_glib.idle_add.side_effect = lambda cb, *a, **kw: cb(*a, **kw)

        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.read.return_value = "up\n"

        sel_mocks, mock_wd, mock_opts, mock_svc, mock_ui, mock_ec, mock_exc = _build_selenium()
        mock_driver = MagicMock()

        with patch("punch_gui.load_settings", return_value=settings), \
             patch("punch_gui.get_credentials", return_value=("u", "p")), \
             patch("punch_gui.GLib", mock_glib), \
             patch("builtins.open", return_value=mock_file), \
             patch.dict("sys.modules", sel_mocks), \
             patch("time.sleep"):
            mock_wd.Chrome.return_value = mock_driver
            mock_ui.WebDriverWait.return_value.until.side_effect = [
                Exception("no login page"),
                MagicMock(),
            ]
            mod.run_punch_in(log_cb, done_cb, error_cb, cancel_cb)

        log_msgs = [c.args[0] for c in log_cb.call_args_list]
        assert any("VPN is up" in msg for msg in log_msgs)


# ===========================================================================
#  run_punch_in — Chrome / Selenium flow
# ===========================================================================

class TestRunPunchInChromeFailure:
    def test_chrome_start_error(self):
        mod = _ensure_mod()
        log_cb, done_cb, error_cb, cancel_cb = [MagicMock() for _ in range(4)]

        settings = {
            "VPN Update Path": "",
            "vpn_interface": "",
            "chromedriver_path": "/bad/path",
        }

        mock_glib = MagicMock()
        mock_glib.idle_add.side_effect = lambda cb, *a, **kw: cb(*a, **kw)

        sel_mocks, mock_wd, mock_opts, mock_svc, mock_ui, mock_ec, mock_exc = _build_selenium()

        with patch("punch_gui.load_settings", return_value=settings), \
             patch("punch_gui.get_credentials", return_value=("u", "p")), \
             patch("punch_gui.GLib", mock_glib), \
             patch.dict("sys.modules", sel_mocks):
            mock_wd.Chrome.side_effect = Exception("chrome not found")
            mod.run_punch_in(log_cb, done_cb, error_cb, cancel_cb)

        error_cb.assert_called_once()
        assert "chrome" in error_cb.call_args[0][0].lower()


class TestRunPunchInSuccess:
    def test_successful_punch(self):
        mod = _ensure_mod()
        log_cb, done_cb, error_cb, cancel_cb = [MagicMock() for _ in range(4)]

        settings = {
            "VPN Update Path": "",
            "vpn_interface": "",
            "chromedriver_path": "/usr/bin/chromedriver",
            "auto_login": True,
            "work_sso_location": "https://sso.example.com",
            "incognito": True,
            "headless": True,
            "mute_audio": True,
            "maximize_window": True,
        }

        mock_glib = MagicMock()
        mock_glib.idle_add.side_effect = lambda cb, *a, **kw: cb(*a, **kw)

        sel_mocks, mock_wd, mock_opts, mock_svc, mock_ui, mock_ec, mock_exc = _build_selenium()
        mock_driver = MagicMock()

        with patch("punch_gui.load_settings", return_value=settings), \
             patch("punch_gui.get_credentials", return_value=("alice", "pw123")), \
             patch("punch_gui.GLib", mock_glib), \
             patch.dict("sys.modules", sel_mocks), \
             patch("time.sleep"):
            mock_wd.Chrome.return_value = mock_driver

            mock_user_field = MagicMock()
            mock_ui.WebDriverWait.return_value.until.side_effect = [
                MagicMock(),       # login page detected
                mock_user_field,   # userNameInput found
                MagicMock(),       # punchSubmitBtnId found
            ]
            mock_driver.find_element.side_effect = [
                MagicMock(),       # passwordInput
                MagicMock(),       # submitButton
                MagicMock(),       # punchSubmitBtnId
            ]

            mod.run_punch_in(log_cb, done_cb, error_cb, cancel_cb)

        done_cb.assert_called_once()
        error_cb.assert_not_called()
        mock_driver.quit.assert_called_once()

    def test_no_login_page(self):
        mod = _ensure_mod()
        log_cb, done_cb, error_cb, cancel_cb = [MagicMock() for _ in range(4)]

        settings = {
            "VPN Update Path": "",
            "vpn_interface": "",
            "auto_login": True,
            "work_sso_location": "https://sso.example.com",
        }

        mock_glib = MagicMock()
        mock_glib.idle_add.side_effect = lambda cb, *a, **kw: cb(*a, **kw)

        sel_mocks, mock_wd, mock_opts, mock_svc, mock_ui, mock_ec, mock_exc = _build_selenium()
        mock_driver = MagicMock()

        with patch("punch_gui.load_settings", return_value=settings), \
             patch("punch_gui.get_credentials", return_value=("u", "p")), \
             patch("punch_gui.GLib", mock_glib), \
             patch.dict("sys.modules", sel_mocks):
            mock_wd.Chrome.return_value = mock_driver
            mock_ui.WebDriverWait.return_value.until.side_effect = [
                Exception("no login page"),
                MagicMock(),
            ]
            mod.run_punch_in(log_cb, done_cb, error_cb, cancel_cb)

        done_cb.assert_called_once()
        log_msgs = [c.args[0] for c in log_cb.call_args_list]
        assert any("already authenticated" in msg for msg in log_msgs)


# ===========================================================================
#  run_punch_in — cancellation
# ===========================================================================

class TestRunPunchInCancellation:
    def test_cancel_before_vpn(self):
        mod = _ensure_mod()
        log_cb, done_cb, error_cb, cancel_cb = [MagicMock() for _ in range(4)]

        mod._cancel_flag.set()

        settings = {"VPN Update Path": "http://vpn/health"}

        mock_glib = MagicMock()
        mock_glib.idle_add.side_effect = lambda cb, *a, **kw: cb(*a, **kw)

        with patch("punch_gui.load_settings", return_value=settings), \
             patch("punch_gui.get_credentials", return_value=("", "")), \
             patch("punch_gui.GLib", mock_glib):
            mod.run_punch_in(log_cb, done_cb, error_cb, cancel_cb)

        cancel_cb.assert_called_once()
        done_cb.assert_not_called()


# ===========================================================================
#  run_punch_in — driver cleanup
# ===========================================================================

class TestRunPunchInDriverCleanup:
    def test_driver_always_quit(self):
        mod = _ensure_mod()
        log_cb, done_cb, error_cb, cancel_cb = [MagicMock() for _ in range(4)]

        settings = {
            "VPN Update Path": "",
            "vpn_interface": "",
            "work_sso_location": "https://sso.example.com",
        }

        mock_glib = MagicMock()
        mock_glib.idle_add.side_effect = lambda cb, *a, **kw: cb(*a, **kw)

        sel_mocks, mock_wd, mock_opts, mock_svc, mock_ui, mock_ec, mock_exc = _build_selenium()
        mock_driver = MagicMock()

        with patch("punch_gui.load_settings", return_value=settings), \
             patch("punch_gui.get_credentials", return_value=("u", "p")), \
             patch("punch_gui.GLib", mock_glib), \
             patch.dict("sys.modules", sel_mocks):
            mock_wd.Chrome.return_value = mock_driver
            mock_ui.WebDriverWait.return_value.until.side_effect = Exception("browser crash")
            mod.run_punch_in(log_cb, done_cb, error_cb, cancel_cb)

        mock_driver.quit.assert_called_once()
