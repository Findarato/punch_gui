import json
import os
import sys
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def tmp_settings(tmp_path):
    """Write a settings.json to tmp_path and return its path."""
    path = tmp_path / "settings.json"
    return path


@pytest.fixture
def tmp_creds(tmp_path):
    """Write a credentials.json to tmp_path and return its path."""
    path = tmp_path / "credentials.json"
    return path


@pytest.fixture
def sample_settings():
    return {
        "chromedriver_path": "/usr/bin/chromedriver",
        "antifarm_sleep": 8,
        "deviation": 5,
        "maximize_window": True,
        "headless": False,
        "incognito": True,
        "auto_login": True,
        "mute_audio": True,
        "vpn_interface": "/sys/class/net/vpn0/operstate",
        "work_sso_location": "https://work.mykronos.com/wfd/home",
        "VPN Update Path": "http://work.domain.site",
    }


@pytest.fixture
def sample_creds():
    return {"login": "testuser", "password": "testpass123"}
