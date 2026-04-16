"""test_pip — pip Skill unit tests."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def pip_skill():
    from vessal.skills.pip.skill import Pip
    return Pip()


def test_install_calls_subprocess(pip_skill):
    """install() calls subprocess to run pip install."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")
        result = pip_skill.install("requests")
    assert "Installed" in result or "Success" in result
    args = mock_run.call_args[0][0]
    assert "install" in args
    assert "requests" in args


def test_install_failure_returns_error(pip_skill):
    """Returns an error message when installation fails."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="No matching distribution")
        result = pip_skill.install("nonexistent_package_xyz")
    assert "Failed" in result


def test_install_rejects_dangerous_input(pip_skill):
    """Rejects package names containing dangerous characters."""
    result = pip_skill.install("requests; rm -rf /")
    assert "Rejected" in result or "invalid" in result


def test_description_within_limit():
    from vessal.skills.pip.skill import Pip
    assert len(Pip.description) <= 15


def test_name_is_pip():
    from vessal.skills.pip.skill import Pip
    assert Pip.name == "pip"
