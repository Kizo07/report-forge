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
        assert spec["title_layouts"] == ["hero", "compact", "minimal"]
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


def _white_figure_json() -> str:
    import plotly.express as px

    return px.line(x=[1, 2], y=[3, 4]).to_json()


def test_save_chart_auto_dark_for_portfolio_dark(
    isolated_portfolio: Path,
) -> None:
    result = engine.scaffold_report(
        "pf-chartdark", title="Charts", template="portfolio-dark", formats=["html"]
    )
    assert result["ok"] is True, result
    out = engine.save_chart(
        _white_figure_json(),
        str(isolated_portfolio / "pf-chartdark" / "figures" / "trend"),
        project="pf-chartdark",
    )
    assert out["ok"] is True, out
    assert out["template_applied"] == "plotly_dark"
    assert Path(out["png"]).is_file()


def test_save_chart_keeps_light_page_light(
    isolated_portfolio: Path,
) -> None:
    result = engine.scaffold_report(
        "pf-chartlight", title="Charts", template="portfolio-light", formats=["html"]
    )
    assert result["ok"] is True, result
    out = engine.save_chart(
        _white_figure_json(),
        str(isolated_portfolio / "pf-chartlight" / "figures" / "trend"),
        project="pf-chartlight",
    )
    assert out["ok"] is True, out
    assert out["template_applied"] is None


def test_save_chart_explicit_figure_theme_is_never_overridden(
    isolated_portfolio: Path,
) -> None:
    import plotly.express as px

    result = engine.scaffold_report(
        "pf-chartfig", title="Charts", template="portfolio-dark", formats=["html"]
    )
    assert result["ok"] is True, result
    fig = px.line(x=[1, 2], y=[3, 4])
    fig.update_layout(template="plotly_white")
    out = engine.save_chart(
        fig.to_json(),
        str(isolated_portfolio / "pf-chartfig" / "figures" / "trend"),
        project="pf-chartfig",
    )
    assert out["ok"] is True, out
    assert out["template_applied"] is None


def test_save_chart_explicit_template_wins_over_project_theme(
    isolated_portfolio: Path,
) -> None:
    result = engine.scaffold_report(
        "pf-chartexp", title="Charts", template="portfolio-dark", formats=["html"]
    )
    assert result["ok"] is True, result
    out = engine.save_chart(
        _white_figure_json(),
        str(isolated_portfolio / "pf-chartexp" / "figures" / "trend"),
        project="pf-chartexp",
        template="plotly_white",
    )
    assert out["ok"] is True, out
    assert out["template_applied"] == "plotly_white"


def test_save_chart_rejects_unknown_template(
    isolated_portfolio: Path,
) -> None:
    out = engine.save_chart(_white_figure_json(), "whatever/trend", template="nope")
    assert out["ok"] is False
    assert "unknown plotly template" in out["error"]


def test_portfolio_minimal_layout_scaffolds_without_card(
    isolated_portfolio: Path,
) -> None:
    result = engine.scaffold_report(
        "pf-min",
        title="Minimal Brief",
        template="portfolio-dark",
        formats=["html", "pdf"],
        title_layout="minimal",
        eyebrow="Briefing",
    )
    assert result["ok"] is True, result
    project = Path(result["path"])
    front_matter = yaml.safe_load(
        (project / "index.qmd").read_text().split("---", 2)[1]
    )
    assert front_matter["title-layout"] == "minimal"
    header = (project / "assets" / "portfolio-header.html").read_text()
    assert "rf-layout-minimal" in header


def test_studio_minimal_layout_shares_editorial_pipeline(
    isolated_portfolio: Path,
) -> None:
    result = engine.scaffold_report(
        "st-min", title="Minimal Studio", template="studio", title_layout="minimal"
    )
    assert result["ok"] is True, result
    assert "rf-layout-minimal" in (
        Path(result["path"]) / "assets" / "studio-header.html"
    ).read_text()


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


def test_portfolio_cover_infographics_scaffold(
    isolated_portfolio: Path,
) -> None:
    scenarios = [
        {"label": "Bear", "value": "$480", "detail": "-19% · 25%"},
        {"label": "Base", "value": "$720", "detail": "+21% · 50%"},
        {"label": "Bull", "value": "$950", "detail": "+60% · 25%"},
    ]
    result = engine.scaffold_report(
        "pf-cover",
        title="Cover Test",
        template="portfolio-dark",
        verdict="OVERWEIGHT — $720 base target",
        key_points=["Ad engine compounding", "Capex fear overdone"],
        scenarios=scenarios,
    )
    assert result["ok"] is True, result
    project = Path(result["path"])
    header = (project / "assets" / "portfolio-header.html").read_text()
    assert "rf-verdict" in header
    assert "OVERWEIGHT" in header
    assert header.count("rf-key-point\"") == 2
    assert header.count("rf-scenario\"") + header.count("rf-scenario ") >= 3
    assert "rf-scenario-base" in header
    front_matter = yaml.safe_load(
        (project / "index.qmd").read_text().split("---", 2)[1]
    )
    assert front_matter["verdict"] == "OVERWEIGHT — $720 base target"
    assert front_matter["key-points"] == [
        "Ad engine compounding",
        "Capex fear overdone",
    ]
    assert front_matter["scenarios"][1]["value"] == "$720"
    show = (project / "assets" / "typst-show.typ").read_text()
    assert "verdict:" in show and "key-points:" in show and "scenarios:" in show
    template_typ = (project / "assets" / "typst-template.typ").read_text()
    assert "CONVICTION CALL" in template_typ
    assert "calc.rem(y, 2)" in template_typ


def test_portfolio_cover_validation_rejects_bad_shapes(
    isolated_portfolio: Path,
) -> None:
    too_many = engine.scaffold_report(
        "pf-bad-kp", title="T", template="portfolio-dark",
        key_points=["a", "b", "c", "d", "e"],
    )
    assert too_many["ok"] is False
    assert "key_points" in too_many["error"]
    assert not (isolated_portfolio / "pf-bad-kp").exists()

    two_scen = engine.scaffold_report(
        "pf-bad-sc", title="T", template="portfolio-dark",
        scenarios=[{"label": "A", "value": "1", "detail": "x"}],
    )
    assert two_scen["ok"] is False
    assert "scenarios" in two_scen["error"]
    assert not (isolated_portfolio / "pf-bad-sc").exists()


def test_portfolio_showtable_styles_present(isolated_portfolio: Path) -> None:
    for template in ("portfolio-light", "portfolio-dark"):
        slug = "pf-show-" + template.replace("portfolio-", "")
        result = engine.scaffold_report(
            slug, title="T", template=template, formats=["html"],
        )
        assert result["ok"] is True, result
        styles = (Path(result["path"]) / "styles.scss").read_text()
        assert ".rf-showtable" in styles
        assert ".rf-nums-right" in styles
