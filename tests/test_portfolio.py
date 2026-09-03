"""Portfolio light/dark templates: studio pipeline, portfolio dressing."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from reportforge import engine


@pytest.fixture
def isolated_portfolio(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    monkeypatch.setattr(engine, "REPORTS_DIR", reports)
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "reportforge")
    monkeypatch.setattr(engine, "_default_reference_docx", lambda: None)
    return reports


def test_template_catalog_exposes_portfolio_variants() -> None:
    specs = {t["name"]: t for t in engine.list_templates()}
    for name in ("portfolio-light", "portfolio-dark"):
        spec = specs[name]
        assert spec["formats"] == ["html", "pdf", "docx"]
        assert spec["content_neutral"] is True
        assert spec["title_layouts"] == ["hero", "compact"]
        assert spec["max_metrics"] == 6


def test_portfolio_scaffold_writes_variant_assets(
    isolated_portfolio: Path,
) -> None:
    for template, gold in (
        ("portfolio-light", "#8f621f"),
        ("portfolio-dark", "#d9a54e"),
    ):
        slug = template.replace("-", "")
        result = engine.scaffold_report(
            slug,
            title="A Portfolio Brief",
            template=template,
            formats=["html", "pdf", "docx"],
            eyebrow="Equity Research",
            organization="QuantFlow Desk",
            metrics=[{"value": "$100", "label": "Example"}],
        )
        assert result["ok"] is True, result
        project = Path(result["path"])
        config = yaml.safe_load((project / "_quarto.yml").read_text())
        front_matter = yaml.safe_load(
            (project / "index.qmd").read_text().split("---", 2)[1]
        )

        assert set(config["format"]) == {"html", "typst", "docx"}
        assert "assets/portfolio-header.html" in (project / "_quarto.yml").read_text()
        assert (project / "assets" / "portfolio-header.html").is_file()
        assert (project / "assets" / "typst-template.typ").is_file()
        assert (project / "assets" / "typst-show.typ").is_file()
        # Studio gold default is replaced by the site gold per variant.
        assert front_matter["accent"] == gold
        assert front_matter["eyebrow"] == "Equity Research"
        assert front_matter["organization"] == "QuantFlow Desk"
        assert "portfolio" in (project / "_brand.yml").read_text().lower()


def test_portfolio_explicit_accent_overrides_site_gold(
    isolated_portfolio: Path,
) -> None:
    result = engine.scaffold_report(
        "pf-accent",
        title="Custom Accent",
        template="portfolio-dark",
        formats=["html"],
        accent="#14756c",
    )
    assert result["ok"] is True, result
    front_matter = yaml.safe_load(
        (Path(result["path"]) / "index.qmd").read_text().split("---", 2)[1]
    )
    assert front_matter["accent"] == "#14756c"


def test_portfolio_rejects_invalid_visual_options_before_creating_project(
    isolated_portfolio: Path,
) -> None:
    bad_layout = engine.scaffold_report(
        "pf-bad-layout", title="T", template="portfolio-light", title_layout="sidebar"
    )
    assert bad_layout["ok"] is False
    assert "title layout" in bad_layout["error"]
    assert not (isolated_portfolio / "pf-bad-layout").exists()

    bad_accent = engine.scaffold_report(
        "pf-bad-accent", title="T", template="portfolio-dark", accent="gold"
    )
    assert bad_accent["ok"] is False
    assert "accent" in bad_accent["error"]
    assert not (isolated_portfolio / "pf-bad-accent").exists()
