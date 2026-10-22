import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "version.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False
    )


def test_versions_in_sync():
    r = run("check")
    assert r.returncode == 0, r.stdout


def test_tag_mismatch_fails():
    assert run("check", "--tag", "v0.0.1").returncode == 1


def test_bad_format_rejected():
    assert run("set", "1.2").returncode != 0
