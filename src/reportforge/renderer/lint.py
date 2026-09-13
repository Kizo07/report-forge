"""Figure-lint gate runner (pre-render exhibit checks)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from reportforge.renderer.errors import ToolTimeoutError

LINT_TIMEOUT_S = 120
LINT_TAIL_CHARS = 800


def figure_lint(script: Path, root: Path) -> str | None:
    """Run scripts/figure_lint.py against a project; None when clean."""
    try:
        run = subprocess.run(
            [sys.executable, str(script), str(root)],
            capture_output=True, text=True, timeout=LINT_TIMEOUT_S)
    except (subprocess.TimeoutExpired, OSError) as exc:
        if isinstance(exc, subprocess.TimeoutExpired):
            raise ToolTimeoutError("figure_lint", LINT_TIMEOUT_S) from exc
        return None
    if run.returncode == 0:
        return None
    out = (run.stdout + "\n" + run.stderr).strip()
    return out[-LINT_TAIL_CHARS:] if out else "figure_lint failed with no output"
