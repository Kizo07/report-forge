"""Interpreter execution: run_code / run_file / jupyter kernel registration
(plan §4 Phase 1). The engine owns permission gating and dict contracts;
this module owns the process spawn and its timeout.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from reportforge.renderer.errors import ToolTimeoutError

KERNEL_INSTALL_TIMEOUT_S = 120


def run(
    cmd: list[str],
    cwd: str | None = None,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    """Run an interpreter command line; ToolTimeoutError on timeout.

    OSError (interpreter missing/not executable) propagates — the engine
    formats it as a launch failure.
    """
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolTimeoutError(cmd[0], timeout) from exc


def ensure_kernel(venv_python: Path | None) -> str:
    """Install the reportforge jupyter kernel; degrade to 'python3' loudly
    (the engine surfaces the fallback via scaffold's jupyter_kernel field).
    """
    if venv_python is None:
        return "python3"
    try:
        result = subprocess.run(
            [str(venv_python), "-m", "ipykernel", "install", "--user",
             "--name", "reportforge", "--display-name", "reportforge"],
            capture_output=True,
            timeout=KERNEL_INSTALL_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "python3"
    return "reportforge" if result.returncode == 0 else "python3"
