"""Quarto render + the pdf-web Chromium print (plan §4 Phase 1).

Per-tool timeouts live here: `quarto render` keeps its generous 900 s
(heavy Jupyter execution), while the Chromium print gets its own 120 s —
sharing the 900 s budget meant a hung browser tab blocked a render slot
for 15 minutes.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from reportforge.renderer.errors import QuartoNotFoundError, ToolTimeoutError

QUARTO_TIMEOUT_S = 900
CHROMIUM_PRINT_TIMEOUT_S = 120
VIRTUAL_TIME_BUDGET_MS = 15000


def run_quarto(
    cmd: list[str],
    cwd: str | Path,
    timeout: int = QUARTO_TIMEOUT_S,
    env: dict | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a fully-formed quarto command line.

    Raises QuartoNotFoundError if the binary vanishes between discovery and
    exec, ToolTimeoutError on timeout — the engine translates both into its
    public dict contract.
    """
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError as exc:
        raise QuartoNotFoundError(f"{cmd[0]} not found on PATH while rendering") from exc
    except subprocess.TimeoutExpired as exc:
        raise ToolTimeoutError("quarto render", timeout) from exc


def print_pdf(cmd: list[str], timeout: int = CHROMIUM_PRINT_TIMEOUT_S) -> subprocess.CompletedProcess[str]:
    """Run the headless-Chromium `--print-to-pdf` command line."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ToolTimeoutError("chromium print-to-pdf", timeout) from exc


def build_print_cmd(
    chromium: str, html_path: Path, pdf_out: Path
) -> list[str]:
    """Headless print command. The virtual-time budget lets JS/plotly
    visuals settle before the snapshot: without it, heavy pages print
    before charts finish drawing and the PDF ships blank figure areas."""
    return [
        chromium,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--virtual-time-budget={VIRTUAL_TIME_BUDGET_MS}",
        f"--print-to-pdf={pdf_out}",
        html_path.as_uri(),
    ]
