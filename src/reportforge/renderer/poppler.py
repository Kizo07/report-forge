"""Poppler (pdftoppm/pdfinfo) primitives for previews and page counts."""

from __future__ import annotations

import subprocess
from pathlib import Path

from reportforge.renderer.errors import ToolTimeoutError

POPPLER_TIMEOUT_S = 120


def page_count(pdf: Path) -> int:
    """Page count via pdfinfo; -1 when unavailable/unreadable (legacy
    sentinel kept — callers decide whether that is fatal)."""
    pdfinfo = __import__("shutil").which("pdfinfo")
    if not pdfinfo:
        return -1
    try:
        run = subprocess.run(  # noqa: S603 fixed binary, fixed args
            [pdfinfo, str(pdf)],
            capture_output=True,
            text=True,
            timeout=POPPLER_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError):
        return -1
    if run.returncode != 0:
        return -1
    for line in run.stdout.splitlines():
        if line.startswith("Pages:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return -1
    return -1


def raster_pages(pdftoppm: str, pdf: Path, pages_dir: Path) -> subprocess.CompletedProcess[str]:
    """Rasterize pages to `pages_dir/page-*.png` (110 dpi, 1400px scale)."""
    try:
        return subprocess.run(  # noqa: S603 fixed binary, fixed args
            [pdftoppm, "-png", "-r", "110", "-scale-to", "1400", pdf,
             str(pages_dir / "page")],
            capture_output=True,
            text=True,
            timeout=POPPLER_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolTimeoutError("pdftoppm page raster", POPPLER_TIMEOUT_S) from exc
