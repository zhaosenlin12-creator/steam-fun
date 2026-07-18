from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def test_cli_module_help_executes(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "steamfun_mirror.cli",
            "--help",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0
    assert "steam.fun local mirror" in result.stdout
    assert "serve" in result.stdout
    assert "capture" in result.stdout
