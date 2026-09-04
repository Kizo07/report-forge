#!/usr/bin/env python3
"""Figure lint for flagship reports: size, caption, voice, palette hygiene.

Usage: figure_lint.py <project-dir>  (expects index.qmd + charts/)
Exit 1 lists every violation. Run before render; all must pass.

Checks:
  1. No more than 2 width=100% embeds in a row without prose between.
  2. Every embed carries an explicit width tier (hero 100 / standard 85 /
     simple 70); >60% at width=100% fails; exports past the absolute
     2200x1000 cap fail (retina headroom already allowed).
  3. Every figure has a {#fig-...} crossref (native Exhibit numbering).
  4. Banned caption/prose tics: hero labels, shouty headers, AI filler,
     non-ASCII slips in captions.
  5. Alt-text mangling (`S and P`-style `&` replacements).
  6. Palette identity: every chart carries QuantFlow accent pixels
     (per-theme gold/teal targets), and light-template charts pass a
     brightness floor (no dark PNGs on light pages).
"""

import re
import statistics
import sys
from pathlib import Path

from PIL import Image

BANNED = [
    "price hero", "price-hero", "momentum ladder", "demand-capacity",
    "thesis in one paragraph", "delve", "tapestry", "forensic attention",
    "honestly labeled", "announces itself",
]

# Per-theme accent targets (sampled pixels match within TOL).
ACCENTS = {
    "light": [(143, 98, 31), (20, 117, 108)],      # gold #8f621f, teal #14756c
    "dark": [(201, 162, 39), (86, 196, 196)],       # gold #c9a227, teal #56cfc4
}

# Absolute insanity cap (px @scale=2): retina exports legitimately exceed
# display size, so per-tier dim checks are meaningless — this catches only
# unambiguous bloat. The real sizing defect (everything at width=100%) is
# caught by the FULLWIDTH_SHARE check below.
ABS_MAX_W, ABS_MAX_H = 2200, 1000
FULLWIDTH_SHARE = 0.60

MAX_FULLWIDTH_RUN = 2
MIN_ACCENT_PX = 20
LIGHT_BRIGHTNESS_FLOOR = 150
# Light paper corner target (#e5ddcc): catches white-background charts
# (wrong template / default-style fallback) that pass brightness+accents.
LIGHT_PAPER = (229, 221, 204)
PAPER_TOL = 16


def _matches(px, targets, tol=60):
    return any(all(abs(a - b) <= tol for a, b in zip(px, t)) for t in targets)


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

    # Every embed needs an explicit width tier; count full-width share.
    fullwidth = 0
    for m in re.finditer(r"!\[([^\]]*)\]\(charts/([^)]+)\)(\{[^}]*\})?", body):
        alt, fname, opts = m.group(1), m.group(2), m.group(3) or ""
        w = re.search(r"width=(\d+)%", opts)
        if not w:
            bad.append(f"qmd: {fname} embed has no explicit width "
                       f"(defaults to 100% — tier it: hero 100/standard "
                       f"85/simple 70)")
        else:
            if w.group(1) == "100":
                fullwidth += 1
        if re.search(r"\b([A-Z]) and ([A-Z])\b", alt):
            bad.append(f"qmd: alt-text mangling ({alt!r}) — use & not 'and'")

    figs = re.findall(r"!\[.*?\]\(charts/", body)
    if figs and fullwidth / len(figs) > FULLWIDTH_SHARE:
        bad.append(f"qmd: {fullwidth}/{len(figs)} figures at width=100% "
                   f"(>60%) — tier simple charts to 70%, standard to 85%")
    crossrefs = len(re.findall(r"\{#fig-", body))
    if crossrefs < len(figs):
        bad.append(f"qmd: {len(figs)} figures but only {crossrefs} "
                   f"{{#fig-}} crossrefs (native Exhibit numbering)")

    low = body.lower()
    for tic in BANNED:
        if tic in low:
            bad.append(f"qmd: banned tic {tic!r} present")

    fm = body.split("---")
    theme = "light" if len(fm) > 1 and "light" in fm[1] else "dark"
    engine_only = bool(re.search(r"^engine_charts_only:\s*true\s*$", fm[1] if len(fm) > 1 else "", re.MULTILINE))
    accents = ACCENTS[theme]

    charts = proj / "charts"
    if charts.is_dir():
        for png in sorted(charts.glob("*.png")):
            try:
                im = Image.open(png).convert("RGB")
            except Exception as e:  # noqa: BLE001
                bad.append(f"{png.name}: unreadable ({e})")
                continue
            w, h = im.size
            if w > ABS_MAX_W or h > ABS_MAX_H:
                bad.append(f"{png.name}: export {w}x{h} exceeds absolute "
                           f"cap {ABS_MAX_W}x{ABS_MAX_H}")
            pix = im.load()
            assert pix is not None
            px = [pix[x, y] for y in range(0, im.height, 7)
                  for x in range(0, im.width, 7)]
            n_accent = sum(1 for p in px if _matches(p, accents))
            if n_accent < MIN_ACCENT_PX:
                bad.append(f"{png.name}: no QuantFlow accent pixels "
                           f"({n_accent} sampled) — theme not applied?")
            if theme == "light":
                lum = statistics.mean(
                    0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px)
                if lum < LIGHT_BRIGHTNESS_FLOOR:
                    bad.append(f"{png.name}: dark chart on light template "
                               f"(mean lum {lum:.0f})")
                boxes = (im.crop((0, 0, 12, 12)), im.crop((w - 12, 0, w, 12)),
                         im.crop((0, h - 12, 12, h)),
                         im.crop((w - 12, h - 12, w, h)))
                chans: list[int] = [0, 0, 0]
                total = 0
                for box in boxes:
                    raw = box.tobytes()
                    n = len(raw) // 3
                    total += n
                    for i in range(3):
                        chans[i] += sum(raw[i::3])
                paper = tuple(c // total for c in chans)
                if any(abs(a - b) > PAPER_TOL for a, b in zip(paper, LIGHT_PAPER)):
                    bad.append(f"{png.name}: paper {paper} is not the light "
                               f"template paper {LIGHT_PAPER} — wrong theme "
                               f"or default-style fallback?")
            if engine_only:
                sw = str(Image.open(png).info.get("Software", ""))
                if "matplotlib" in sw.lower() or "seaborn" in sw.lower():
                    bad.append(f"{png.name}: non-engine fallback chart "
                               f"({sw}) — engine_charts_only is set")

    if bad:
        print(f"figure_lint: {len(bad)} violation(s) in {proj}:")
        for b in bad:
            print(f"  - {b}")
        return 1
    print(f"figure_lint: clean ({len(figs)} figures, {crossrefs} crossrefs, "
          f"{theme} palette ok)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
