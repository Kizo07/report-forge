"""Wide tables must fit their column: every Typst template that styles
tables carries the fit rules (reduced size, hyphenation, ragged cells).
Regression: the TSLA flagship scenario table (5 columns in a 2-column
layout) clipped its As-of dates at the page edge.

Root cause (2026-10-26): pandoc emits percentage columns summing to
100% of the available width, so in a ~240pt text column a 4+ column
table gets ~30pt tracks that unbreakable strings (as-of dates like
2027-09-04, ~51pt at 8.7pt) overflow past the page edge by +27pt. No
font size or hyphenation setting can wrap those strings (Typst never
breaks the numeric-hyphen run, even with hyphenate:true). The durable
fix: two-column families float wide tables across both columns
(wide-table-span). One-column families (modern, memo via the shared
grammar) keep inline tables: percentage tracks already resolve against
the full text width there, which fits by construction (proven by probe:
zero overflow at modern geometry).
"""

from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from reportforge import templates as templates_mod

ASSETS = Path(templates_mod.ASSETS_DIR)
TEMPLATES = [
    "portfolio-light/typst-template.typ",
    "portfolio-dark/typst-template.typ",
    "studio/typst-template.typ",
    "ledger-light/typst-template.typ",
    "ledger-dark/typst-template.typ",
    "modern/typst-template.typ",
    "_shared/table-style.typ",
]
# Two-column bodies: the only place a percentage table can be starved.
TWO_COLUMN_TEMPLATES = [
    "portfolio-light/typst-template.typ",
    "portfolio-dark/typst-template.typ",
    "studio/typst-template.typ",
    "ledger-light/typst-template.typ",
    "ledger-dark/typst-template.typ",
]


def test_all_table_templates_carry_fit_rules():
    for rel in TEMPLATES:
        text = (ASSETS / rel).read_text(encoding="utf-8")
        assert "hyphenate: true" in text, f"{rel}: table cells cannot hyphenate"
        assert "justify: false" in text, f"{rel}: table cells stay justified"


def test_all_table_templates_break_hyphens():
    """Hyphen-break invariant: table cells admit breaks after hyphens.

    Typst never breaks numeric-hyphen runs (as-of dates), so every
    template adds a zero-width space after each hyphen inside tables.
    This is the backstop for tables nested in quarto Div blocks, where
    parent-scope spanning cannot reach.
    """
    for rel in TEMPLATES:
        text = (ASSETS / rel).read_text(encoding="utf-8")
        assert "table-hyphen-break" in text, f"{rel}: missing hyphen-break rule"


def test_two_column_templates_span_wide_tables():
    """Span invariant: 4+ relative-column tables must float parent-wide.

    Set-rules alone cannot fix cell-content overflow (pandoc's explicit
    percentage columns ignore them), so each two-column template must
    carry the wide-table-span show rule. Would have failed on the
    8pt/hyphenate-only fix.
    """
    for rel in TWO_COLUMN_TEMPLATES:
        text = (ASSETS / rel).read_text(encoding="utf-8")
        assert "wide-table-span" in text, f"{rel}: missing wide-table-span rule"
        assert 'scope: "parent"' in text, f"{rel}: wide tables do not span"
        assert "cols.all" in text, f"{rel}: wide-table detection missing"
        assert "breakable: false" in text, f"{rel}: narrow-table path lost"


def _typst_binary() -> Path | None:
    if found := shutil.which("typst"):
        return Path(found)
    bundled = Path("/opt/quarto/bin/tools/x86_64/typst")
    return bundled if bundled.is_file() else None


def test_wide_table_span_probe_renders_without_overflow(tmp_path: Path):
    """Rendered probe: the real partial must keep a 5-col table in-bounds.

    Compiles a minimal doc through the actual portfolio-light partial
    with the TSLA scenario table forced into the right column (the
    reported overflow site), both bare and Div-wrapped (#block, as
    quarto emits for ::: divs), and asserts via pdftotext -bbox that
    no word crosses the text-area right edge (612pt - 0.82in margin)
    and that the bare table spanned (first column starts in the left
    half). Pre-fix this fails with +23pt overflow; skips when
    typst/pdftotext are absent.
    """
    typst = _typst_binary()
    pdftotext = shutil.which("pdftotext")
    if typst is None or pdftotext is None:
        pytest.skip("typst or pdftotext unavailable")
    shutil.copy(ASSETS / "portfolio-light/typst-template.typ", tmp_path / "typst-template.typ")
    probe = tmp_path / "probe.typ"
    probe.write_text(
        '#import "typst-template.typ": portfolio_light\n'
        "#show: doc => portfolio_light(title: [Span probe], doc)\n"
        "#lorem(30)\n"
        "#colbreak()\n"
        "#block[\n"
        "#table(\n"
        "  columns: (17.86%, 19.64%, 19.64%, 30.36%, 12.5%),\n"
        "  align: (left, right, right, left, left),\n"
        "  table.header([Scenario], [Target (USD)], [Return (pct)], [What carries it], [As-of]),\n"
        "  table.hline(),\n"
        "  [Bear], [220], [-38], [Price cuts, margin decay, robotaxi delay], [2027-09-04],\n"
        "  [Base], [420], [+19], [Floor holds, storage repair, 8+ metros], [2027-09-04],\n"
        "  [Bull], [505], [+43], [60 GWh energy, FSD attach, permits], [2027-09-04],\n"
        ")\n"
        "]\n"
        "#table(\n"
        "  columns: (17.86%, 19.64%, 19.64%, 30.36%, 12.5%),\n"
        "  align: (left, right, right, left, left),\n"
        "  table.header([Scenario], [Target (USD)], [Return (pct)], [What carries it], [As-of]),\n"
        "  table.hline(),\n"
        "  [Bear], [220], [-38], [Price cuts, margin decay, robotaxi delay], [2027-09-04],\n"
        "  [Base], [420], [+19], [Floor holds, storage repair, 8+ metros], [2027-09-04],\n"
        "  [Bull], [505], [+43], [60 GWh energy, FSD attach, permits], [2027-09-04],\n"
        ")\n",
        encoding="utf-8",
    )
    pdf = tmp_path / "probe.pdf"
    run = subprocess.run(
        [str(typst), "compile", str(probe), str(pdf)],
        capture_output=True, text=True, timeout=120,
    )
    assert run.returncode == 0, f"typst compile failed: {run.stderr[:500]}"
    bbox = tmp_path / "probe.xml"
    run = subprocess.run(
        [pdftotext, "-bbox", str(pdf), str(bbox)],
        capture_output=True, text=True, timeout=120,
    )
    assert run.returncode == 0, f"pdftotext failed: {run.stderr[:300]}"
    edge = 612 - 0.82 * 72
    ns = {"x": "http://www.w3.org/1999/xhtml"}
    words = ET.parse(bbox).getroot().findall(".//x:word", ns)
    # 2.8pt tolerance covers Typst hanging-hyphen microtype (+2.66pt
    # observed on body text); table overflow was +20..27pt.
    over = [
        (float(w.get("xMax")), "".join(w.itertext()))
        for w in words if float(w.get("xMax")) > edge + 2.8
    ]
    assert not over, f"words past text-area edge: {over[:5]}"
    first_col = [
        float(w.get("xMin")) for w in words
        if "".join(w.itertext()) == "Bear"
    ]
    assert first_col, "probe table missing from output"
    assert min(first_col) < 300, (
        f"wide table did not span: first-col xMin {min(first_col):.1f}"
    )
