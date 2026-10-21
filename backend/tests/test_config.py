import sys
from pathlib import Path

from app import config
from app.services import precache


def test_legacy_data_dir_kept(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "pinakes.db").write_bytes(b"")
    monkeypatch.chdir(tmp_path)
    assert config.default_data_dir() == Path("data")


def test_linux_default_uses_xdg(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert config.default_data_dir() == tmp_path / "xdg" / "pinakes"


def test_windows_default_uses_appdata(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "roam"))
    assert config.default_data_dir() == tmp_path / "roam" / "pinakes"


def test_priority_args_per_platform(monkeypatch):
    assert "preexec_fn" in precache._priority_args()
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        precache.subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x4000, raising=False
    )
    assert precache._priority_args() == {"creationflags": 0x4000}
