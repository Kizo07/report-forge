#!/usr/bin/env python3
"""Page-density gate for flagship PDFs: no half-empty pages.

Usage: page_ink.py <report.pdf> [--dpi 50] [--gap-pct 10] [--min-bal 0.5]
Exit 1 lists every violation. Run AFTER render (it reads the PDF).

Two mechanical proxies for "a lot of empty space":
  1. Vertical gaps: a consecutive band of near-blank rows taller than
     --gap-pct of the page (section breaks that stranded whitespace,
     charts that pushed text away).
  2. Column imbalance: in two-column bodies, one text column holding
     less than --min-bal of the other's ink (a stranded half-column).

First page (cover) and last page (closer) are exempt — covers are
deliberately airy and closers taper. Thresholds calibrated 2026-09-11
on msft-12m-ledger-light (14pp): flags pp 3,4,5,7,8 (the gappy ones),
passes the dense pages (gaps <=6%, balance >=0.52).

Needs pdftoppm (poppler) + PIL.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except ImportError:
    print("page_ink: needs numpy+PIL — run with the repo venv "
          "(.venv/bin/python scripts/page_ink.py ...)")
    raise SystemExit(2)


def page_stats(png: Path):
    a = np.asarray(Image.open(png).convert("RGB")).astype(int)
    h, w, _ = a.shape
    corners = np.concatenate([
        a[:8, :8].reshape(-1, 3), a[:8, -8:].reshape(-1, 3),
        a[-8:, :8].reshape(-1, 3), a[-8:, -8:].reshape(-1, 3),
    ])
    paper = corners.mean(0)
    ink = abs(a - paper).sum(-1) > 45
    rowfrac = ink.mean(1)
    maxgap = cur = 0
    for v in rowfrac:
        if v < 0.005:
            cur += 1
            maxgap = max(maxgap, cur)
        else:
            cur = 0
    mid = w // 2
    left = float(ink[:, :mid].mean())
    right = float(ink[:, mid:].mean())
    bal = min(left, right) / max(left, right) if max(left, right) > 0 else 1.0
    return 100 * maxgap / h, bal


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0].startswith("--"):
        print(__doc__)
        return 2
    pdf = Path(args[0])
    dpi = 50
    gap_pct = 10.0
    min_bal = 0.5
    it = iter(args[1:])
    for a in it:
        if a == "--dpi":
            dpi = int(next(it))
        elif a == "--gap-pct":
            gap_pct = float(next(it))
        elif a == "--min-bal":
            min_bal = float(next(it))
    if not pdf.is_file():
        print(f"page_ink: not found: {pdf}")
        return 2
    if shutil.which("pdftoppm") is None:
        print("page_ink: pdftoppm (poppler) not on PATH")
        return 2
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), str(pdf),
             str(Path(td) / "p")],
            capture_output=True, text=True)
        if r.returncode != 0:
            print(f"page_ink: pdftoppm failed: {r.stderr.strip()[-300:]}")
            return 2
        pages = sorted(Path(td).glob("p-*.png"))
        bad = []
        for idx, pg in enumerate(pages, 1):
            if idx == 1 or idx == len(pages):
                continue  # cover + closer exempt
            gap, bal = page_stats(pg)
            if gap > gap_pct:
                bad.append(f"p{idx}: {gap:.1f}% consecutive vertical gap "
                           f"(>{gap_pct:.0f}%) — stranded whitespace")
            if bal < min_bal:
                bad.append(f"p{idx}: column balance {bal:.2f} "
                           f"(<{min_bal:.2f}) — half-empty column")
    if bad:
        print(f"page_ink: {len(bad)} violation(s) in {pdf}:")
        for b in bad:
            print(f"  - {b}")
        return 1
    print(f"page_ink: clean ({len(pages)} pages, "
          f"gap<={gap_pct:.0f}% bal>={min_bal:.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
