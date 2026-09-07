"""Ledger dark/light templates: Cyan Ledger dressing on the studio pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from reportforge import engine, templates


@pytest.fixture
def isolated_ledger(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    monkeypatch.setattr(engine, "REPORTS_DIR", reports)
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "reportforge")
    monkeypatch.setattr(engine, "_default_reference_docx", lambda: None)
    return reports


@pytest.mark.parametrize(
    ("template", "accent", "paper"),
    (
        ("ledger-dark", "#e3ac55", "#060a12"),
        ("ledger-light", "#8f621f", "#eef3f6"),
    ),
)
def test_ledger_scaffold_cover_pipeline(
    isolated_ledger: Path, template: str, accent: str, paper: str
) -> None:
    specs = {item["name"]: item for item in engine.list_templates()}
    assert template in specs
    assert specs[template]["exhibit_labels"] is True
    slug = template.replace("-", "")
    result = engine.scaffold_report(
        slug,
        title="A Ledger Brief",
        template=template,
        formats=["html", "pdf", "docx"],
        eyebrow="Equity Research",
        organization="QuantFlow Desk",
        metrics=[{"value": "USD 100", "label": "Example"}],
        verdict="OVERWEIGHT — USD 420 base target",
        key_points=["Demand compounds", "Capex fear overdone"],
        scenarios=[
            {"label": "Bear", "value": "USD 220", "detail": "Demand stalls"},
            {"label": "Base", "value": "USD 420", "detail": "Steady ramp"},
            {"label": "Bull", "value": "USD 520", "detail": "Autonomy pays"},
        ],
    )
    assert result["ok"] is True, result
    project = Path(result["path"])
    typt = (project / "assets" / "typst-template.typ").read_text()
    # Ledger palette + type, two-column body, unbreakable tables.
    assert paper in typt
    assert "Space Grotesk" in typt
    assert "set page(columns: 2)" in typt
    assert "breakable: false" in typt
    # No portfolio tokens leak into the derived template.
    assert "Georgia" not in typt
    assert "portfolio_dark" not in typt and "portfolio_light" not in typt
    front_matter = yaml.safe_load(
        (project / "index.qmd").read_text().split("---", 2)[1]
    )
    assert front_matter["reportforge-template"] == template
    assert front_matter["verdict"].startswith("OVERWEIGHT")
    assert len(front_matter["key-points"]) == 2
    assert len(front_matter["scenarios"]) == 3


def test_ledger_plotly_themes_registered() -> None:
    for name, primary, paper in (
        ("ledger-dark", "#e3ac55", "#060a12"),
        ("ledger-light", "#8f621f", "#eef3f6"),
    ):
        pal = engine.QUANTFLOW_PLOTLY_THEMES[name]
        assert pal["primary"] == primary
        assert pal["paper_bg"] == paper
        assert pal["secondary"] in ("#08bfff", "#009ed9")
    assert engine._PORTFOLIO_TO_QUANTFLOW_TEMPLATE["ledger-dark"] == "ledger-dark"
    assert engine._PORTFOLIO_TO_QUANTFLOW_TEMPLATE["ledger-light"] == "ledger-light"


def test_ledger_constants_derived_from_portfolio() -> None:
    for const in (
        "LEDGER_DARK_TYPT_TEMPLATE",
        "LEDGER_DARK_TYPT_SHOW",
        "LEDGER_DARK_STYLES_EXTRA",
        "LEDGER_DARK_BRAND_YML",
        "LEDGER_LIGHT_TYPT_TEMPLATE",
        "LEDGER_LIGHT_TYPT_SHOW",
        "LEDGER_LIGHT_STYLES_EXTRA",
        "LEDGER_LIGHT_BRAND_YML",
    ):
        assert hasattr(templates, const), const
