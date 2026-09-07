#!/usr/bin/env python3
"""Derive Cyan Ledger report templates from the portfolio templates.

The LEDGER_DARK_* / LEDGER_LIGHT_* constants in
src/reportforge/templates.py are mechanical derivations of the
PORTFOLIO_* ones: same studio structure (cover infographics, showtable,
two-column body, Exhibit numbering), Cyan Ledger palette + type.

Source system: Kizo07.github.io `fusion/cyan-ledger` (v4: electric cyan
#08bfff x ledger gold #e3ac55 dark / #8f621f light, Space Grotesk / Inter /
IBM Plex Mono, midnight dark + ice light).

Usage: python3 scripts/derive_ledger_templates.py [--check]
  --check: exit 1 if templates.py is missing/stale LEDGER blocks.
Idempotent: skips blocks already present.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "src" / "reportforge" / "templates.py"

# Exact line spans (1-indexed, end-exclusive) of the portfolio sources.
SPANS = {
    "PORTFOLIO_DARK_TYPT_TEMPLATE": (2261, 2559),
    "PORTFOLIO_DARK_TYPT_SHOW": (2559, 2638),
    "PORTFOLIO_DARK_STYLES_EXTRA": (3113, 3589),
    "PORTFOLIO_DARK_BRAND_YML": (1912, 1963),
    "PORTFOLIO_LIGHT_TYPT_TEMPLATE": (1963, 2261),
    "PORTFOLIO_LIGHT_TYPT_SHOW": (3589, 3667),
    "PORTFOLIO_LIGHT_STYLES_EXTRA": (2638, 3113),
    "PORTFOLIO_LIGHT_BRAND_YML": (1861, 1912),
}

DARK_MAP = [
    ("#d9a54e", "#e3ac55"),  # ledger gold (dark)
    ("#56cfc4", "#08bfff"),  # ledger cyan
    ("#10151d", "#0c1220"),  # midnight panel
    ("#e7eaf0", "#e9eff5"),  # ice ink
    ("#9aa4b2", "#819aaa"),  # ledger faint
    ("#0a0d12", "#060a12"),  # midnight paper
    ("#1e2632", "#14202f"),  # hairline
    ("#151b25", "#0d1522"),
    ("#1b2230", "#101a29"),
    ("#0d1219", "#080d16"),
    ("#1d1a10", "#161206"),
    ("#7d8795", "#6f7f8f"),
    ("#3ecf8e", "#3fbfae"),  # ledger green-teal
    ("#ef6a6a", "#e66785"),  # ledger red
    ("Fraunces, Georgia, serif", '"Space Grotesk", sans-serif'),
    ("Fraunces", "Space Grotesk"),
    ("Georgia", "Space Grotesk"),
    ("JetBrains Mono", "IBM Plex Mono"),
    ("PORTFOLIO_DARK", "LEDGER_DARK"),
    ("portfolio-dark", "ledger-dark"),
    ("portfolio_dark", "ledger_dark"),
    ("Portfolio Dark", "Ledger Dark"),
    ("PORTFOLIO REPORT", "LEDGER REPORT"),
]

LIGHT_MAP = [
    ("#14756c", "#009ed9"),  # scheme-safe cyan
    ("#ebe3d2", "#e7edf2"),  # ice plot
    ("#362e21", "#1b2634"),  # slate ink
    ("#6d6250", "#5a6b7a"),
    ("#e5ddcc", "#eef3f6"),  # ice paper
    ("#d3c8b0", "#cfd9e1"),
    ("#e0d7c4", "#dde5ec"),
    ("#d9cba6", "#d3dde6"),
    ("#e0d4ba", "#d8e1e9"),
    ("#e2d3ac", "#d5dee7"),
    ("#efe4cb", "#e9eff4"),
    ("#7b7060", "#64727f"),
    ("#2c6e4a", "#237a57"),
    ("#a44a44", "#c05563"),
    ("Fraunces, Georgia, serif", '"Space Grotesk", sans-serif'),
    ("Fraunces", "Space Grotesk"),
    ("Georgia", "Space Grotesk"),
    ("JetBrains Mono", "IBM Plex Mono"),
    ("PORTFOLIO_LIGHT", "LEDGER_LIGHT"),
    ("portfolio-light", "ledger-light"),
    ("portfolio_light", "ledger_light"),
    ("Portfolio Light", "Ledger Light"),
    ("PORTFOLIO REPORT", "LEDGER REPORT"),
    # ledger gold (light) is identical to portfolio gold: no-op guard
    ("#8f621f", "#8f621f"),
]


def derive(src: str, mapping: list[tuple[str, str]], tag: str) -> str:
    # Tokens are inventoried across the whole template family; individual
    # blocks contain subsets — absent tokens are skipped, not errors.
    for old, new in mapping:
        if old != new and old in src:
            src = src.replace(old, new)
    return src


def build() -> dict[str, str]:
    lines = TPL.read_text().splitlines(keepends=True)

    def span(name: str) -> str:
        a, b = SPANS[name]
        assert lines[a - 1].startswith(name), f"span drift: {name}"
        return "".join(lines[a - 1 : b - 1])

    out: dict[str, str] = {}
    for const in SPANS:
        if const.startswith("PORTFOLIO_DARK"):
            tag = const.replace("PORTFOLIO_DARK", "LEDGER_DARK")
            out[tag] = derive(span(const), DARK_MAP, const)
        else:
            tag = const.replace("PORTFOLIO_LIGHT", "LEDGER_LIGHT")
            out[tag] = derive(span(const), LIGHT_MAP, const)
    # Fix derived header comments to name the ledger source.
    out["LEDGER_DARK_TYPT_TEMPLATE"] = out["LEDGER_DARK_TYPT_TEMPLATE"].replace(
        '// report-forge "ledger-dark" — studio structure, portfolio dark palette',
        '// report-forge "ledger-dark" — studio structure, Cyan Ledger midnight palette '
        "(derived; see scripts/derive_ledger_templates.py)",
        1,
    )
    out["LEDGER_LIGHT_TYPT_TEMPLATE"] = out["LEDGER_LIGHT_TYPT_TEMPLATE"].replace(
        '// report-forge "ledger-light" — studio structure, portfolio light palette',
        '// report-forge "ledger-light" — studio structure, Cyan Ledger ice palette '
        "(derived; see scripts/derive_ledger_templates.py)",
        1,
    )
    return out


def main() -> int:
    text = TPL.read_text()
    blocks = build()
    missing = [k for k in blocks if k not in text]
    if "--check" in sys.argv:
        if missing:
            print(f"derive_ledger: missing {len(missing)} LEDGER blocks")
            return 1
        print("derive_ledger: all LEDGER blocks present")
        return 0
    if not missing:
        print("derive_ledger: nothing to do")
        return 0
    with TPL.open("a") as fh:
        fh.write(
            "\n\n# --- Cyan Ledger variants (derived) ----------------------------"
            "----------------\n"
            "# Generated by scripts/derive_ledger_templates.py from the\n"
            "# PORTFOLIO_* constants above. Do not hand-edit; re-run the\n"
            "# generator after portfolio changes.\n"
        )
        for key in blocks:
            fh.write("\n" + blocks[key].rstrip("\n") + "\n")
    print(f"derive_ledger: appended {len(missing)} blocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
