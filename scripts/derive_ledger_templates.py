#!/usr/bin/env python3
"""Derive Cyan Ledger report templates from the portfolio templates.

Phase 2 (robustness refactor plan): the ledger asset files under
src/reportforge/templates/_assets/ledger-{dark,light}/ are mechanical
derivations of the portfolio-* ones — same studio structure (cover
infographics, showtable, two-column body, Exhibit numbering), Cyan
Ledger palette + type. This generator works FILE-TO-FILE: it reads each
portfolio asset, applies the token maps below, and rewrites (or checks)
the matching ledger asset.

Source system: Kizo07.github.io `fusion/cyan-ledger` (v4: electric cyan
#08bfff x ledger gold #e3ac55 dark / #8f621f light, Space Grotesk / Inter /
IBM Plex Mono, midnight dark + ice light).

Chart-facing hexes mirror alpha_engine.viz LEDGER_DARK/LEDGER_LIGHT
(canonical); page tokens follow so charts stay pixel-matched to pages.

Usage: python3 scripts/derive_ledger_templates.py [--check]
  --check: exit 1 if any ledger asset is missing or stale.
Idempotent: refreshes (rewrites) the derived files in place.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "src" / "reportforge" / "templates" / "_assets"

# Portfolio source → ledger target (same filename under the family dir).
SOURCES = [
    ("portfolio-dark", "ledger-dark"),
    ("portfolio-light", "ledger-light"),
]
FILES = ["typst-template.typ", "typst-show.typ", "styles-extra.scss", "brand.yml"]

DARK_MAP = [
    ("#d9a54e", "#e3ac55"),  # ledger gold (dark)
    ("#56cfc4", "#08bfff"),  # ledger cyan
    ("#10151d", "#0b1220"),  # midnight panel (== alpha plot_bg)
    ("#e7eaf0", "#e8eef4"),  # ice ink (== alpha font)
    ("#9aa4b2", "#93a3b8"),  # ledger muted (== alpha muted)
    ("#0a0d12", "#060a12"),  # midnight paper
    ("#1e2632", "#16202e"),  # hairline (== alpha grid)
    ("#151b25", "#1d2b3f"),  # panel-2 (== alpha border)
    ("#1b2230", "#101a29"),
    ("#0d1219", "#080d16"),
    ("#1d1a10", "#161206"),
    ("#7d8795", "#6f7f8f"),
    ("#3ecf8e", "#34d399"),  # ledger green (== alpha positive)
    ("#ef6a6a", "#f87171"),  # ledger red (== alpha negative)
    # Font stacks: composite rules first so bare-token renames below
    # can never double-apply inside an already-rewritten stack.
    ('"Fraunces", Georgia, serif', '"Space Grotesk", sans-serif'),
    ("Fraunces, Georgia, serif", '"Space Grotesk", sans-serif'),
    ('"IBM Plex Mono", "JetBrains Mono", monospace', '"IBM Plex Mono", monospace'),
    ("Georgia", "Space Grotesk"),  # Typst display font (local-only fallback)
    ("Fraunces", "Space Grotesk"),
    ("JetBrains Mono", "IBM Plex Mono"),
    ("PORTFOLIO DARK", "LEDGER DARK"),
    ("portfolio-dark", "ledger-dark"),
    ("portfolio_dark", "ledger_dark"),
    ("Portfolio Dark", "Ledger Dark"),
    ("PORTFOLIO REPORT", "LEDGER REPORT"),
]

LIGHT_MAP = [
    ("#14756c", "#009ed9"),  # scheme-safe cyan
    ("#ebe3d2", "#e7edf2"),  # ice panel
    ("#362e21", "#1b2634"),  # slate ink
    ("#6d6250", "#63798a"),  # muted (== alpha muted)
    ("#e5ddcc", "#eef3f6"),  # ice paper
    ("#d3c8b0", "#d5dde4"),  # hairline (== alpha grid)
    ("#e0d7c4", "#dde5ec"),
    ("#d9cba6", "#d3dde6"),
    ("#e0d4ba", "#d8e1e9"),
    ("#e2d3ac", "#d5dee7"),
    ("#efe4cb", "#e9eff4"),
    ("#2c6e4a", "#1f8a4c"),  # positive (== alpha)
    ("#a44a44", "#cf4444"),  # negative (== alpha)
    # Font stacks: composite rules first (see DARK_MAP).
    ('"Fraunces", Georgia, serif', '"Space Grotesk", sans-serif'),
    ("Fraunces, Georgia, serif", '"Space Grotesk", sans-serif'),
    ('"IBM Plex Mono", "JetBrains Mono", monospace', '"IBM Plex Mono", monospace'),
    ("Georgia", "Space Grotesk"),
    ("Fraunces", "Space Grotesk"),
    ("JetBrains Mono", "IBM Plex Mono"),
    ("portfolio-light", "ledger-light"),
    ("portfolio_light", "ledger_light"),
    ("Portfolio Light", "Ledger Light"),
    ("PORTFOLIO REPORT", "LEDGER REPORT"),
]

# Header fixups: the portfolio header comment names the palette origin;
# after token maps the derived file still says "portfolio {dark,light}
# palette" — replace the whole header line with the ledger one (the exact
# wording the pre-refactor generator produced, kept byte-stable).
# Keyed (dst_family, filename) and asserted loud: a portfolio header
# rewording must BREAK the generator, not silently keep a stale header
# (milestone B review, finding 6).
HEADER_FIXUPS = {
    ("ledger-dark", "typst-template.typ"): [
        ('// report-forge "ledger-dark" — studio structure, portfolio dark palette',
         '// report-forge "ledger-dark" — studio structure, Cyan Ledger midnight palette '
         "(derived; see scripts/derive_ledger_templates.py)"),
    ],
    ("ledger-light", "typst-template.typ"): [
        ('// report-forge "ledger-light" — studio structure, portfolio light palette',
         '// report-forge "ledger-light" — studio structure, Cyan Ledger ice palette '
         "(derived; see scripts/derive_ledger_templates.py)"),
    ],
}


def derive(src: str, mapping: list[tuple[str, str]]) -> str:
    # Tokens are inventoried across the whole template family; individual
    # files contain subsets — absent tokens are skipped, not errors.
    for old, new in mapping:
        if old != new and old in src:
            src = src.replace(old, new)
    return src


def derive_file(src_family: str, dst_family: str, name: str) -> str:
    mapping = DARK_MAP if src_family.endswith("dark") else LIGHT_MAP
    derived = derive((ASSETS / src_family / name).read_text(encoding="utf-8"), mapping)
    for old, new in HEADER_FIXUPS.get((dst_family, name), []):
        if old not in derived:
            raise AssertionError(
                f"header fixup pattern no longer matches {src_family}/{name}: "
                f"the portfolio header was reworded — update HEADER_FIXUPS"
            )
        derived = derived.replace(old, new, 1)
    return derived


def main() -> int:
    check = "--check" in sys.argv
    stale: list[str] = []
    for src_family, dst_family in SOURCES:
        for name in FILES:
            derived = derive_file(src_family, dst_family, name)
            dst_path = ASSETS / dst_family / name
            if check:
                if not dst_path.is_file() or dst_path.read_text(encoding="utf-8") != derived:
                    stale.append(f"{dst_family}/{name}")
            else:
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                dst_path.write_text(derived, encoding="utf-8", newline="")
                print(f"derive_ledger: wrote {dst_family}/{name}")

    if check:
        if stale:
            print("derive_ledger: ledger assets stale or missing — re-run the generator")
            for s in stale:
                print(f"  stale: {s}")
            return 1
        print("derive_ledger: ledger assets present and fresh")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
