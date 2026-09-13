#!/usr/bin/env python3
"""Render baselines for template-parity gating (robustness refactor plan,
Phase 0). Scaffolds + PDF-renders one minimal project per template family
in an isolated temp REPORTS_DIR, then records per-family baselines:

    tests/render_baselines/<family>.json   page count + per-page ink
    tests/render_baselines/<family>.qmd    the exact source rendered

Regenerate after a DELIBERATE toolchain/template change:
    .venv/bin/python scripts/make_render_baselines.py [--only fam1,fam2]

Parity gate (tests/test_render_parity.py, run with RF_PARITY=1) compares
future renders against these JSONs. Ink = fraction of non-near-white
pixels per page rasterized by pdftoppm at 50 dpi — pin the poppler version
when regenerating (recorded in each JSON's "toolchain" block).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

# Isolate scaffolds from the repo tree — must be set BEFORE engine import.
_BASELINE_TMP = tempfile.mkdtemp(prefix="rf-baselines-")
os.environ["REPORTFORGE_REPORTS_DIR"] = _BASELINE_TMP

from reportforge import engine  # noqa: E402
from reportforge import templates  # noqa: E402

FAMILIES = [
    "standard", "memo", "whitepaper", "modern", "studio",
    "portfolio-light", "portfolio-dark", "ledger-light", "ledger-dark",
    "bespoke",
]
OUT_DIR = REPO / "tests" / "render_baselines"
DPI = 50
WHITE_THRESHOLD = 245  # pixels >= this on every channel count as paper


def page_ink_fractions(pdf: Path) -> list[float]:
    """Rasterize each page and return the non-paper ink fraction per page."""
    with tempfile.TemporaryDirectory(prefix="rf-ink-") as td:
        subprocess.run(
            ["pdftoppm", "-png", "-r", str(DPI), str(pdf), f"{td}/page"],
            check=True, capture_output=True, timeout=300)
        try:
            import numpy as np
            from PIL import Image
        except ImportError:
            sys.exit("make_render_baselines: needs numpy + pillow in the repo venv")
        fractions = []
        for png in sorted(Path(td).glob("page-*.png")):
            arr = np.asarray(Image.open(png).convert("L"))
            fractions.append(round(float((arr < WHITE_THRESHOLD).mean()), 4))
        return fractions


def baseline_for(family: str) -> dict:
    slug = f"baseline-{family}"
    result = engine.scaffold_report(slug, template=family, formats=["pdf"])
    if not result.get("ok"):
        raise SystemExit(f"{family}: scaffold failed: {result.get('error')}")
    root = Path(_BASELINE_TMP) / slug
    rendered = engine.render_report(slug, formats=["pdf"])
    if not rendered.get("ok"):
        raise SystemExit(f"{family}: render failed: {rendered.get('error')}\n"
                         f"{rendered.get('log_tail', '')}")
    pdf = root / "output" / "index.pdf"
    ink = page_ink_fractions(pdf)
    qmd = (root / "index.qmd").read_text(encoding="utf-8")
    # The scaffold embeds today's date; hash the NORMALIZED text so the
    # input gate does not expire at midnight (Milestone C review, finding 1).
    import hashlib
    normalized = templates._normalize_scaffold_text(qmd)
    return {
        "family": family,
        "pages": len(ink),
        "ink_per_page": ink,
        "toolchain": {
            "quarto": engine._quarto_version(),
            "poppler": engine._tool_version(["pdfinfo", "-v"]),
            "reportforge": engine._REPORTFORGE_VERSION,
            "dpi": DPI,
            "white_threshold": WHITE_THRESHOLD,
        },
        "index_qmd_sha256": hashlib.sha256(
            normalized.encode("utf-8")).hexdigest(),
    }, qmd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="comma-separated subset of families")
    args = parser.parse_args()
    families = args.only.split(",") if args.only else FAMILIES

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reports_dir = Path(_BASELINE_TMP)
    try:
        for family in families:
            print(f"[{family}] scaffolding + rendering…", flush=True)
            data, qmd = baseline_for(family)
            (OUT_DIR / f"{family}.json").write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8")
            (OUT_DIR / f"{family}.qmd").write_text(qmd, encoding="utf-8")
            print(f"[{family}] ok — {data['pages']}pp, "
                  f"mean ink {sum(data['ink_per_page']) / len(data['ink_per_page']):.3f}")
    finally:
        shutil.rmtree(reports_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
