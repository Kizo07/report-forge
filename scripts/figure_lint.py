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
  7. No unescaped `$` in figure alt text or fig-cap: a `$...$` pair
     (even across alt + caption of one line) parses as inline math and
     silently un-renders the figure in HTML *and* PDF while firing
     crossref warnings. Write `USD B` / `USD`, or escape as `\\$`.
  8. Every `#`/`##` heading needs a preceding blank line (outside code
     fences) — without it the marker renders as literal body text.
  9. Encoding variety (needs stamped charts, see save_figure): with 6+
     stamped figures, bar-only figures must be <=50% and at least 2
     figures must carry a non-default encoding (heatmap/box/violin/
     treemap/pie/scatterpolar/candlestick/area/coef) — bars are not the
     default.
 10. Wide markdown tables in a single text column: estimated width
     (per-column max cell length + 3 chars padding each) over
     MAX_TABLE_WIDTH must ride ::: {column-page}, split, or move to the
     appendix (MSFT p4 overflow).
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

# Per-theme palette targets (sampled pixels match within TOL).
# Full palette, not just the two brand accents: sign-colored dots
# (coef plots) and ramp-colored boxes legitimately carry no gold/cyan
# yet are fully themed (pilot-variety, 2026-09-11).
ACCENTS = {
    "light": [(143, 98, 31), (20, 117, 108), (46, 125, 50),
              (198, 40, 40), (109, 98, 80), (176, 154, 94),
              (109, 76, 23), (15, 76, 68)],
    "dark": [(201, 162, 39), (86, 196, 196), (63, 185, 80),
             (248, 81, 73), (154, 164, 178), (92, 83, 32),
             (138, 122, 42), (121, 192, 255)],
    "ledger-light": [(143, 98, 31), (0, 158, 217), (31, 138, 76),
                     (207, 68, 68), (99, 121, 138), (176, 154, 94),
                     (109, 76, 23), (7, 94, 125)],
    "ledger-dark": [(227, 172, 85), (8, 191, 255), (52, 211, 153),
                    (248, 113, 113), (147, 163, 184), (107, 90, 38),
                    (163, 133, 58), (127, 216, 255)],
}

# Absolute insanity cap (px @scale=2): must fit our own tier spec
# (hero 1600x800 @scale=2 = 3200x1600) — a cap below the spec fails
# compliant exports (TSLA-dark 2026-09-05: agent followed the spec,
# the gate was wrong). Catches only exports beyond hero tier.
ABS_MAX_W, ABS_MAX_H = 3400, 1700
FULLWIDTH_SHARE = 0.60

MAX_FULLWIDTH_RUN = 2
MIN_ACCENT_PX = 20
LIGHT_BRIGHTNESS_FLOOR = 150
# Variety gate (check 9): bar-only = every stamped trace kind is "bar".
# Plain "scatter" (line charts) earns no credit — it is the other half
# of the old default. Credited encodings are the ones bars can't do.
VARIETY_CREDIT = frozenset({
    "heatmap", "box", "violin", "treemap", "pie", "scatterpolar",
    "barpolar", "candlestick", "ohlc", "area", "coef",
})
MIN_VARIETY_N = 6
BAR_ONLY_MAX_SHARE = 0.50
MIN_VARIETY_CREDIT = 2
# Table-width rule (check 10): single-column tables wider than this
# overflow into the gutter. Width is estimated as the sum of per-column
# max cell lengths + 3 chars per column of padding — a 5-col table of
# short numbers fits, a 3-col table with a 75-char cell does not.
MAX_TABLE_WIDTH = 58
# Light paper corner targets (#e5ddcc portfolio, #eef3f6 ledger ice):
# catches white-background charts (wrong template / default-style
# fallback) that pass brightness+accents.
LIGHT_PAPERS = {
    "light": (229, 221, 204),
    "ledger-light": (238, 243, 246),
}
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
        for zone, label in ((alt, "alt text"), (opts, "fig-cap/attrs")):
            if re.search(r"(?<!\\)\$", zone):
                bad.append(f"qmd: {fname} unescaped $ in {label} — Quarto "
                           f"parses $...$ as math and silently un-renders "
                           f"the figure (write USD or \\$)")

    figs = re.findall(r"!\[.*?\]\(charts/", body)
    if figs and fullwidth / len(figs) > FULLWIDTH_SHARE:
        bad.append(f"qmd: {fullwidth}/{len(figs)} figures at width=100% "
                   f"(>60%) — tier simple charts to 70%, standard to 85%")
    crossrefs = len(re.findall(r"\{#fig-", body))
    if crossrefs < len(figs):
        bad.append(f"qmd: {len(figs)} figures but only {crossrefs} "
                   f"{{#fig-}} crossrefs (native Exhibit numbering)")

    # ATX headings need a preceding blank line — without it `# ...`
    # renders as literal paragraph text (TSLA 2026-09-06: 8 leaks).
    # (Outside ``` code fences — `#` comments inside chunks are fine.)
    in_fence = False
    for i, ln in enumerate(lines, 1):
        if ln.strip().startswith("```"):
            in_fence = not in_fence
        if (not in_fence and re.match(r"^#{1,3} ", ln)
                and i > 1 and lines[i - 2].strip()
                and not lines[i - 2].strip().startswith("```")):
            bad.append(f"qmd:{i}: heading without preceding blank line "
                       f"({ln.strip()[:40]!r} renders as literal text)")

    low = body.lower()
    for tic in BANNED:
        if tic in low:
            bad.append(f"qmd: banned tic {tic!r} present")

    # Wide markdown tables in a single text column overflow into the
    # gutter (MSFT ledger-light p4, 2026-09-11). Tables with >3 columns
    # or cells over 28 chars must ride column-page, split, or move to
    # the appendix — unless already inside a ::: {column-page} div.
    fenced = False
    divstack: list[bool] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s.startswith("```"):
            fenced = not fenced
            i += 1
            continue
        if not fenced and s.startswith(":::"):
            if "{" in s:
                divstack.append("column-page" in s)
            elif divstack:
                divstack.pop()
            i += 1
            continue
        if (not fenced and s.startswith("|") and i + 1 < len(lines)
                and re.match(r"^\|[\s:\-|]+\|\s*$",
                             lines[i + 1].strip())):
            j = i
            rows = []
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows.append(lines[j].strip())
                j += 1
            content = [r for k, r in enumerate(rows) if k != 1]
            split = [r.strip("|").split("|") for r in content]
            ncols = max(len(r) for r in split)
            colw = [0] * ncols
            for r in split:
                for c, cell in enumerate(r):
                    colw[c] = max(colw[c], len(cell.strip()))
            width_est = sum(colw) + 3 * ncols
            if not any(divstack) and width_est > MAX_TABLE_WIDTH:
                bad.append(
                    f"qmd:{i + 1}: table ~{width_est} chars wide in a "
                    f"single text column — wrap in "
                    f"::: {{column-page}}, split it, or move to the "
                    f"appendix (overflows like MSFT p4)")
            i = j
            continue
        i += 1

    fm = body.split("---")
    head = fm[1] if len(fm) > 1 else ""
    m = re.search(r"^reportforge-template:\s*[\"']?([\w-]+)", head, re.MULTILINE)
    tpl = m.group(1) if m else ""
    if tpl in ACCENTS:
        theme = tpl
    else:
        theme = "light" if "light" in head else "dark"
    engine_only = bool(re.search(r"^engine_charts_only:\s*true\s*$", head, re.MULTILINE))
    accents = ACCENTS[theme]

    charts = proj / "charts"
    stamped: list[set[str]] = []
    if charts.is_dir():
        for png in sorted(charts.glob("*.png")):
            try:
                fh = Image.open(png)
                stamp = dict(fh.info).get("QuantFlow-Traces")
                im = fh.convert("RGB")
            except Exception as e:  # noqa: BLE001
                bad.append(f"{png.name}: unreadable ({e})")
                continue
            if stamp:
                stamped.append(set(str(stamp).split(",")))
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
                bad.append(f"{png.name}: no QuantFlow palette pixels "
                           f"({n_accent} sampled) — theme not applied?")
            if theme in LIGHT_PAPERS:
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
                want = LIGHT_PAPERS[theme]
                if any(abs(a - b) > PAPER_TOL for a, b in zip(paper, want)):
                    bad.append(f"{png.name}: paper {paper} is not the light "
                               f"template paper {want} — wrong theme "
                               f"or default-style fallback?")
                # Plot interior must not be pure white on light templates —
                # a white plot box on ice paper is the visible mismatch
                # (AMD ledger-light, 2026-09-08). Sample the center.
                core = im.crop((w // 2 - 20, h // 2 - 20,
                                w // 2 + 20, h // 2 + 20))
                raw = core.tobytes()
                n = len(raw) // 3
                mean_core = tuple(sum(raw[i::3]) // n for i in range(3))
                if all(v > 247 for v in mean_core):
                    bad.append(f"{png.name}: plot interior {mean_core} is "
                               f"near-white on light template — plot_bg "
                               f"must match the page paper")
            if engine_only:
                sw = str(Image.open(png).info.get("Software", ""))
                if "matplotlib" in sw.lower() or "seaborn" in sw.lower():
                    bad.append(f"{png.name}: non-engine fallback chart "
                               f"({sw}) — engine_charts_only is set")

    if stamped:
        if len(stamped) >= MIN_VARIETY_N:
            bar_only = sum(1 for kinds in stamped if kinds <= {"bar"})
            if bar_only / len(stamped) > BAR_ONLY_MAX_SHARE:
                bad.append(
                    f"charts: {bar_only}/{len(stamped)} stamped figures "
                    f"are bar-only "
                    f"(>{BAR_ONLY_MAX_SHARE:.0%}) — match encodings to "
                    f"data (heatmap/box/treemap/area/radar/coef/scatter "
                    f"with trend); bars are not the default")
            credited = sum(1 for kinds in stamped
                           if kinds & VARIETY_CREDIT)
            if credited < MIN_VARIETY_CREDIT:
                bad.append(
                    f"charts: only {credited}/{len(stamped)} stamped "
                    f"figures carry a non-default encoding — need at "
                    f"least {MIN_VARIETY_CREDIT} "
                    f"(heatmap/box/violin/treemap/pie/scatterpolar/"
                    f"candlestick/area/coef)")
        # Fewer than MIN_VARIETY_N stamped figures (or none: pre-stamp
        # reports): gate skips — unstamped history is not evidence.

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
