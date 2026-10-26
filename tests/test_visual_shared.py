"""Shared HTML layer gate (Impl D): lightbox + TOC defaults, brand theming.

Scaffolds into tmp via the parity-test isolation pattern and asserts the
generated `_quarto.yml` carries the shared HTML defaults:

- lightbox: built-in Quarto >= 1.4 `lightbox: true` on every flagship
  (non-bespoke) html block — NOT the quarto-lightbox extension.
- toc: follows the template spec's toc flag — flagship-length templates
  scaffold toc:true, short-form templates (memo, briefs, modern,
  studio/editorial family, bespoke) stay false.
- bespoke stays opinion-free: no lightbox/toc injected into its html block.
- shared styles.scss keeps brand tokens (`$brand-*`) as the source.
"""

from pathlib import Path

import pytest
import yaml

from reportforge import engine

SPECS = {t["name"]: t for t in engine.list_templates()}
FLAGSHIP = sorted(n for n in SPECS if n != "bespoke")


@pytest.fixture
def isolated_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    monkeypatch.setattr(engine, "REPORTS_DIR", reports)
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "reportforge")
    monkeypatch.setattr(engine, "_default_reference_docx", lambda: None)
    return reports


def _scaffold_html(isolated_reports: Path, template: str) -> dict:
    slug = f"visual-{template}"
    result = engine.scaffold_report(slug, template=template, formats=["html"])
    assert result["ok"], result
    yml = yaml.safe_load((isolated_reports / slug / "_quarto.yml").read_text())
    return yml["format"]["html"]


@pytest.mark.parametrize("template", FLAGSHIP)
def test_flagship_html_has_lightbox_and_spec_toc(isolated_reports, template: str):
    html = _scaffold_html(isolated_reports, template)
    assert html.get("lightbox") is True, f"{template}: missing lightbox: true"
    assert html.get("toc") is SPECS[template]["toc"], (
        f"{template}: toc {html.get('toc')} != spec {SPECS[template]['toc']}"
    )


def test_memo_scaffold_carries_custom_typst_shell(isolated_reports):
    """Memo scaffolds its staged Typst shell + brand: Inter-based PDF
    instead of Quarto's default Typst template/serif."""
    result = engine.scaffold_report("visual-memo-shell", template="memo", formats=["html", "pdf"])
    assert result["ok"], result
    root = isolated_reports / "visual-memo-shell"
    assert (root / "assets" / "typst-template.typ").is_file()
    assert (root / "assets" / "typst-show.typ").is_file()
    assert (root / "assets" / "table-style.typ").is_file()
    brand = yaml.safe_load((root / "_brand.yml").read_text())
    assert brand["typography"]["base"]["family"] == "Inter"
    yml = (root / "_quarto.yml").read_text()
    assert "typst:" in yml and "assets/typst-template.typ" in yml


def test_memo_short_form_toc_stays_false(isolated_reports):
    assert _scaffold_html(isolated_reports, "memo")["toc"] is False


def test_bespoke_stays_opinion_free(isolated_reports):
    html = _scaffold_html(isolated_reports, "bespoke")
    assert "lightbox" not in html
    assert "toc" not in html


def test_no_html_format_is_noop(isolated_reports):
    slug = "visual-nohtml"
    result = engine.scaffold_report(slug, template="standard", formats=["pdf"])
    assert result["ok"], result
    text = (isolated_reports / slug / "_quarto.yml").read_text()
    assert "lightbox" not in text


def test_shared_styles_use_brand_tokens(isolated_reports):
    slug = "visual-styles"
    result = engine.scaffold_report(slug, template="standard", formats=["html"])
    assert result["ok"], result
    styles = (isolated_reports / slug / "styles.scss").read_text()
    assert "$brand-" in styles
    assert "brand tokens are the source of truth" in styles
