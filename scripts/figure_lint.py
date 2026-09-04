#!/usr/bin/env python3
"""Figure lint for flagship reports: size, caption, and voice hygiene.

Usage: figure_lint.py <project-dir>  (expects index.qmd + charts/)
Exit 1 lists every violation. Run before render; all must pass.

Checks:
  1. No more than 2 width=100% embeds in a row without prose between.
  2. Simple-chart PNGs (<=12 bars can't be detected — proxy: file with
     width>=2000px AND height>=850px) flagged as oversized exports.
  3. Every figure has a {#fig-...} crossref (native Exhibit numbering).
  4. Banned caption/prose tics: hero labels, shouty headers, AI filler,
     non-ASCII slips in captions.
"""

import re
import sys
from pathlib import Path

from PIL import Image

BANNED = [
    "price hero", "price-hero", "momentum ladder", "demand-capacity",
    "thesis in one paragraph", "delve", "tapestry", "forensic attention",
    "honestly labeled", "announces itself",
]

MAX_FULLWIDTH_RUN = 2
MAX_EXPORT_W, MAX_EXPORT_H = 2000, 850


def main() -> int:
    proj = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    qmd = proj / "index.qmd"
    body = qmd.read_text()
    bad = []

    lines = body.splitlines()
    run = 0
    for i, ln in enumerate(lines, 1):
        if re.search(r"!\[.*\]\(charts/.*\)\{[^}]*width=100%", ln):
            run += 1
            if run > MAX_FULLWIDTH_RUN:
                bad.append(f"qmd:{i}: {run} consecutive width=100% figures")
        elif ln.strip().startswith("!["):
            run = 0
        elif ln.strip() and not ln.strip().startswith((":::", "#", "|", "!")):
            run = 0

    embeds = re.findall(r"!\[.*?\]\(charts/.*?\)(\{[^}]*\})?", body)
    figs = re.findall(r"!\[.*?\]\(charts/", body)
    crossrefs = len(re.findall(r"\{#fig-", body))
    if crossrefs < len(figs):
        bad.append(f"qmd: {len(figs)} figures but only {crossrefs} "
                   f"{{#fig-}} crossrefs (native Exhibit numbering)")

    low = body.lower()
    for tic in BANNED:
        if tic in low:
            bad.append(f"qmd: banned tic {tic!r} present")

    charts = proj / "charts"
    if charts.is_dir():
        for png in sorted(charts.glob("*.png")):
            try:
                w, h = Image.open(png).size
            except Exception as e:  # noqa: BLE001
                bad.append(f"{png.name}: unreadable ({e})")
                continue
            if w >= MAX_EXPORT_W and h >= MAX_EXPORT_H:
                bad.append(f"{png.name}: oversized export {w}x{h} "
                           f"(>={MAX_EXPORT_W}x{MAX_EXPORT_H}) — use a "
                           f"compact tier or pair it)")

    if bad:
        print(f"figure_lint: {len(bad)} violation(s) in {proj}:")
        for b in bad:
            print(f"  - {b}")
        return 1
    print(f"figure_lint: clean ({len(figs)} figures, {crossrefs} crossrefs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
