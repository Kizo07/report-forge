"""Regression tests for the 2026-09-10 template bug-fix sweep.

Covers: modern accent wiring + provenance, accent sentinel resolution,
whitepaper title page, studio brand fonts + accent-tinted chrome,
bespoke docx reference, light-project detection, CLI surface, and the
ledger derive generator (font stacks + freshness).
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest
import yaml

from reportforge import engine
from reportforge import templates as templates_mod

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def isolated_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    monkeypatch.setattr(engine, "REPORTS_DIR", reports)
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "reportforge")
    monkeypatch.setattr(engine, "_default_reference_docx", lambda: None)
    return reports


# --- modern: accent wiring + provenance --------------------------------------


def test_modern_default_accent_reaches_typst_and_styles(isolated_reports: Path) -> None:
    result = engine.scaffold_report("mod-default", template="modern", formats=["html"])
    assert result["ok"] is True, result
    project = Path(result["path"])
    typt = (project / "assets" / "typst-template.typ").read_text()
    show = (project / "assets" / "typst-show.typ").read_text()
    styles = (project / "styles.scss").read_text()
    front_matter = yaml.safe_load(
        (project / "index.qmd").read_text().split("---", 2)[1]
    )
    # Default flows: qmd frontmatter -> pandoc $if(accent-typst)$ ->
    # conf(accent: "#...") — the hashless variant dodges pandoc's # escape.
    assert front_matter["accent"] == "#2e5bff"
    assert front_matter["accent-typst"] == "2e5bff"
    assert '$if(accent-typst)$' in show and 'accent: "#$accent-typst$",' in show
    assert 'accent: "#2e5bff"' in typt  # parameter default
    assert "#2e5bff" in styles
    assert "<% accent %>" not in styles  # placeholder fully rendered


def test_modern_explicit_accent_is_honored(isolated_reports: Path) -> None:
    result = engine.scaffold_report(
        "mod-accent", template="modern", formats=["html"], accent="#b3402a"
    )
    assert result["ok"] is True, result
    project = Path(result["path"])
    styles = (project / "styles.scss").read_text()
    front_matter = yaml.safe_load(
        (project / "index.qmd").read_text().split("---", 2)[1]
    )
    assert front_matter["accent"] == "#b3402a"
    assert "#b3402a" in styles
    assert "#2e5bff" not in styles


def test_modern_rejects_malformed_accent(isolated_reports: Path) -> None:
    result = engine.scaffold_report("mod-bad", template="modern", accent="blue")
    assert result["ok"] is False
    assert "six-digit hex" in result["error"]


def test_modern_records_template_provenance(isolated_reports: Path) -> None:
    result = engine.scaffold_report("mod-prov", template="modern", formats=["html"])
    assert result["ok"] is True, result
    qmd = (Path(result["path"]) / "index.qmd").read_text()
    front_matter = yaml.safe_load(qmd.split("---", 2)[1])
    assert front_matter["reportforge-template"] == "modern"


# --- accent sentinel: explicit accents are never silently re-skinned ----------


@pytest.mark.parametrize(
    ("template", "default_accent"),
    (
        ("studio", "#4f46e5"),
        ("modern", "#2e5bff"),
        ("portfolio-light", "#8f621f"),
        ("portfolio-dark", "#d9a54e"),
        ("ledger-light", "#8f621f"),
        ("ledger-dark", "#e3ac55"),
    ),
)
def test_omitted_accent_uses_template_default(
    isolated_reports: Path, template: str, default_accent: str
) -> None:
    result = engine.scaffold_report(
        f"acc-def-{template}", template=template, formats=["html"]
    )
    assert result["ok"] is True, result
    front_matter = yaml.safe_load(
        (Path(result["path"]) / "index.qmd").read_text().split("---", 2)[1]
    )
    assert front_matter["accent"].lower() == default_accent


def test_explicit_indigo_on_portfolio_is_not_swapped_to_gold(
    isolated_reports: Path,
) -> None:
    """Regression: #4f46e5 used to be treated as 'unset' and silently
    replaced with the portfolio gold even when passed explicitly."""
    result = engine.scaffold_report(
        "acc-explicit", template="portfolio-light", formats=["html"], accent="#4f46e5"
    )
    assert result["ok"] is True, result
    project = Path(result["path"])
    front_matter = yaml.safe_load(
        (project / "index.qmd").read_text().split("---", 2)[1]
    )
    styles = (project / "styles.scss").read_text()
    assert front_matter["accent"] == "#4f46e5"
    assert "--rf-accent: #4f46e5" in styles


# --- whitepaper: promised title page now activates ---------------------------


def test_whitepaper_scaffold_emits_titlepage(isolated_reports: Path) -> None:
    result = engine.scaffold_report("wp-title", template="whitepaper", formats=["pdf"])
    assert result["ok"] is True, result
    project = Path(result["path"])
    yml = (project / "_quarto.yml").read_text()
    # titlepage is a format:typst option — the yml swaps the print block to
    # typst and ships the title-page article partials.
    assert "titlepage: true" in yml
    assert "  typst:" in yml
    assert "template-partials" in yml
    assert (project / "assets" / "typst-template.typ").is_file()
    assert (project / "assets" / "typst-show.typ").is_file()
    show = (project / "assets" / "typst-show.typ").read_text()
    assert "$if(titlepage)$" in show
    typt = (project / "assets" / "typst-template.typ").read_text()
    assert "titlepage: false" in typt  # conf parameter exists


# --- studio: brand loads the fonts its CSS reaches for ------------------------


def test_studio_brand_loads_fraunces_and_plex_mono(isolated_reports: Path) -> None:
    result = engine.scaffold_report("studio-brand", template="studio", formats=["html"])
    assert result["ok"] is True, result
    brand = (Path(result["path"]) / "_brand.yml").read_text()
    assert "Fraunces" in brand
    assert "IBM Plex Mono" in brand
    assert "monospace: IBM Plex Mono" in brand


def test_studio_chrome_tints_follow_accent_not_hardcoded_indigo() -> None:
    """Regression: header radial + thead stayed indigo (#4f46e5/#efefff)
    even when the caller overrode the accent."""
    extra = templates_mod.STUDIO_STYLES_EXTRA
    assert "rgba(79, 70, 229" not in extra
    assert "#efefff" not in extra
    assert (
        "radial-gradient("
        "circle at 88% 8%, color-mix(in srgb, var(--rf-accent) 16%, transparent)"
        in extra
    )
    assert "background: color-mix(in srgb, var(--rf-accent) 8%, var(--rf-panel))" in extra


# --- bespoke: copied reference doc is actually referenced ---------------------


def test_bespoke_docx_block_references_copied_reference_doc() -> None:
    assert "reference-doc: assets/reference-doc.docx" in templates_mod.BESPOKE_YML


# --- light detection: frontmatter beats the title substring -------------------


def test_project_is_light_uses_template_frontmatter(isolated_reports: Path) -> None:
    result = engine.scaffold_report(
        "spotlight-probe",
        title="Spotlight on the midnight book",
        template="portfolio-dark",
        formats=["html"],
    )
    assert result["ok"] is True, result
    # "Spotlight" contains 'light' — the old substring heuristic flipped
    # this project to light for the white-chart gate.
    assert engine._project_is_light(Path(result["path"])) is False


def test_project_is_light_still_detects_light_templates(isolated_reports: Path) -> None:
    result = engine.scaffold_report("light-probe", template="ledger-light", formats=["html"])
    assert result["ok"] is True, result
    assert engine._project_is_light(Path(result["path"])) is True


# --- CLI surface ---------------------------------------------------------------


def test_scaffold_api_defaults_accent_to_none() -> None:
    """None (omit) resolves per template; the CLI maps 1:1 to this surface."""
    sig = inspect.signature(engine.scaffold_report)
    assert sig.parameters["accent"].default is None


def test_cli_title_layout_accepts_minimal(isolated_reports: Path, monkeypatch) -> None:
    from reportforge.cli import main

    rc = main([
        "new", "cli-minimal", "--title", "CLI Minimal", "--template", "studio",
        "--title-layout", "minimal", "--formats", "html",
    ])
    assert rc == 0
    qmd = (isolated_reports / "cli-minimal" / "index.qmd").read_text()
    assert 'title-layout: "minimal"' in qmd


# --- ledger derive generator: clean stacks + freshness ------------------------

_LEDGER_CONSTS = (
    "LEDGER_DARK_TYPT_TEMPLATE",
    "LEDGER_DARK_STYLES_EXTRA",
    "LEDGER_DARK_BRAND_YML",
    "LEDGER_LIGHT_TYPT_TEMPLATE",
    "LEDGER_LIGHT_STYLES_EXTRA",
    "LEDGER_LIGHT_BRAND_YML",
)


@pytest.mark.parametrize("const", _LEDGER_CONSTS)
def test_ledger_constants_have_clean_font_stacks(const: str) -> None:
    """Regression: the derive map produced 'Space Grotesk", Space Grotesk'
    serif stacks and doubled IBM Plex Mono entries."""
    val = getattr(templates_mod, const)
    assert '"Space Grotesk", Space Grotesk' not in val
    assert '"IBM Plex Mono", "IBM Plex Mono"' not in val
    assert "Georgia" not in val
    assert "Fraunces" not in val


def test_ledger_page_tokens_match_canonical_chart_palette() -> None:
    """Page panel/ink/hairline hexes equal alpha_engine's chart palette so
    exhibits sit pixel-matched on the page."""
    dark_styles = templates_mod.LEDGER_DARK_STYLES_EXTRA
    assert "#0b1220" in dark_styles  # panel == plot_bg
    assert "#060a12" in dark_styles  # paper == paper_bg
    light_styles = templates_mod.LEDGER_LIGHT_STYLES_EXTRA
    assert "#d5dde4" in light_styles  # line == grid
    assert "#eef3f6" in light_styles  # paper == paper_bg


def test_portfolio_and_ledger_styles_drop_dead_custom_properties() -> None:
    for const in (
        "PORTFOLIO_LIGHT_STYLES_EXTRA",
        "PORTFOLIO_DARK_STYLES_EXTRA",
        "LEDGER_LIGHT_STYLES_EXTRA",
        "LEDGER_DARK_STYLES_EXTRA",
    ):
        assert "--rf-gold:" not in getattr(templates_mod, const), const
        assert "--rf-faint:" not in getattr(templates_mod, const), const


def _load_derive_module():
    spec = importlib.util.spec_from_file_location(
        "derive_ledger_templates", _SCRIPTS / "derive_ledger_templates.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_derive_check_detects_stale_ledger_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    module = _load_derive_module()
    src = module.TPL
    stale = tmp_path / "templates.py"
    stale.write_text(src.read_text().replace("#0b1220", "#0c1220", 1))
    monkeypatch.setattr(module, "TPL", stale)
    assert module.main.__module__ == "derive_ledger_templates"
    import sys

    monkeypatch.setattr(sys, "argv", ["derive_ledger_templates.py", "--check"])
    assert module.main() == 1
    assert "stale" in capsys.readouterr().out


def test_derive_check_passes_on_fresh_tree() -> None:
    module = _load_derive_module()
    import sys

    old_argv = sys.argv
    sys.argv = ["derive_ledger_templates.py", "--check"]
    try:
        assert module.main() == 0
    finally:
        sys.argv = old_argv
