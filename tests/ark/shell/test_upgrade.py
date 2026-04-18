"""test_upgrade — unit tests for installer detection + PyPI latest lookup."""
from __future__ import annotations

import sys
from unittest.mock import patch

from vessal.ark.shell import upgrade


def test_check_pypi_latest_parses_info_version():
    fake_json = b'{"info": {"version": "1.2.3"}}'

    class _Resp:
        def read(self):
            return fake_json

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with patch("urllib.request.urlopen", return_value=_Resp()):
        latest = upgrade.check_pypi_latest("vessal")
    assert latest == "1.2.3"


def test_compare_versions_newer_available():
    assert upgrade.is_newer("1.2.3", current="1.2.0") is True
    assert upgrade.is_newer("1.2.0", current="1.2.3") is False
    assert upgrade.is_newer("1.2.3", current="1.2.3") is False


def test_build_upgrade_cmd_uv():
    cmd = upgrade.build_upgrade_cmd("uv")
    assert cmd == ["uv", "tool", "upgrade", "vessal"]


def test_build_upgrade_cmd_pipx():
    cmd = upgrade.build_upgrade_cmd("pipx")
    assert cmd == ["pipx", "upgrade", "vessal"]


def test_build_upgrade_cmd_pip_uses_current_interpreter():
    cmd = upgrade.build_upgrade_cmd("pip")
    assert cmd[0] == sys.executable
    assert cmd[1:] == ["-m", "pip", "install", "--upgrade", "vessal"]


def test_detect_installer_returns_string():
    """detect_installer is environment-dependent; just assert contract."""
    assert upgrade.detect_installer() in ("uv", "pipx", "pip")
