"""External-tool discovery and version probes (plan §4 Phase 1).

Pure primitives: locate binaries, read versions, bootstrap the pandoc
DOCX reference. No engine policy lives here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# renderer/toolchain.py → parents: [0] renderer, [1] reportforge, [2] src, [3] repo
REPO_ROOT = Path(__file__).resolve().parents[3]


def which(name: str) -> str | None:
    return shutil.which(name)


def tool_version(cmd: list[str], timeout: int = 15) -> str | None:
    """First output line of a `cmd --version`-style probe; None when absent.

    Ignores the exit code: poppler tools print their version to stderr and
    exit nonzero on `-v`.
    """
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
    return lines[0].strip() if lines else None


def quarto_version() -> str | None:
    """Best-effort `quarto --version`; None when quarto is absent/broken."""
    if shutil.which("quarto") is None:
        return None
    try:
        proc = subprocess.run(
            ["quarto", "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    first = (proc.stdout or "").strip().splitlines()
    return first[0].strip() if first else None


def venv_python() -> Path | None:
    """The reportforge interpreter: REPORTFORGE_PYTHON > active venv > repo .venv."""
    candidates: list[Path] = []
    if configured := os.environ.get("REPORTFORGE_PYTHON"):
        candidates.append(Path(configured).expanduser())
    if sys.prefix != sys.base_prefix:
        candidates.append(Path(sys.executable))
    candidates.append(REPO_ROOT / ".venv" / "bin" / "python")
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def chromium_binary() -> str | None:
    if configured := os.environ.get("REPORTFORGE_CHROMIUM"):
        candidate = Path(configured).expanduser()
        return str(candidate) if candidate.is_file() else None
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        if found := shutil.which(name):
            return found
    return None


def default_reference_docx() -> Path | None:
    """Bootstrap a pandoc reference.docx into the repo cache (best effort)."""
    pandoc = shutil.which("pandoc")
    cache = REPO_ROOT / "assets_cache"
    cache.mkdir(exist_ok=True)
    target = cache / "reference-doc.docx"
    if not target.exists() and pandoc:
        subprocess.run(
            [pandoc, "-o", str(target), "--print-default-data-file", "reference.docx"],
            capture_output=True,
            timeout=60,
        )
    return target if target.exists() else None
