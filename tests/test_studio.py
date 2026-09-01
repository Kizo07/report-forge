from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from reportforge import engine


@pytest.fixture
def isolated_studio(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    monkeypatch.setattr(engine, "REPORTS_DIR", reports)
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "reportforge")
    monkeypatch.setattr(engine, "_default_reference_docx", lambda: None)
    return reports


def test_template_catalog_exposes_content_neutral_studio() -> None:
    studio = next(item for item in engine.list_templates() if item["name"] == "studio")

    assert studio["formats"] == ["html", "pdf", "docx"]
    assert studio["content_neutral"] is True
    assert studio["title_layouts"] == ["hero", "compact"]
    assert studio["max_metrics"] == 6


def test_studio_minimal_scaffold_has_no_required_brand_or_metrics(
    isolated_studio: Path,
) -> None:
    result = engine.scaffold_report(
        "studio-minimal",
        title="A Flexible Brief",
        template="studio",
        formats=["html", "pdf", "docx"],
        metrics=[],
    )

    assert result["ok"] is True
    project = Path(result["path"])
    config = yaml.safe_load((project / "_quarto.yml").read_text())
    front_matter = yaml.safe_load((project / "index.qmd").read_text().split("---", 2)[1])
    body = (project / "index.qmd").read_text()

    assert set(config["format"]) == {"html", "typst", "docx"}
    assert "metrics" not in front_matter
    assert "organization" not in front_matter
    assert front_matter["title-layout"] == "hero"
    assert front_matter["accent"] == "#4f46e5"
    assert (project / "assets" / "typst-template.typ").is_file()
    assert (project / "assets" / "typst-show.typ").is_file()
    assert "Investment Research" not in body
    assert "Portfolio actions" not in body


def test_studio_supports_compact_layout_and_six_generic_metrics(
    isolated_studio: Path,
) -> None:
    metrics = [
        {"value": str(index), "label": f"Measure {index}"}
        for index in range(1, 7)
    ]
    result = engine.scaffold_report(
        "studio-rich",
        title='Signals: the “next” chapter',
        subtitle="A reusable editorial report",
        author="Research & Design",
        abstract="A flexible summary with no prescribed domain.",
        template="studio",
        formats=["pdf"],
        organization='North: "Studio"',
        eyebrow="Field Notes · 08",
        title_layout="compact",
        accent="#0f766e",
        metrics=metrics,
        confidential_mark="Internal working draft",
    )

    assert result["ok"] is True
    project = Path(result["path"])
    config = yaml.safe_load((project / "_quarto.yml").read_text())
    front_matter = yaml.safe_load((project / "index.qmd").read_text().split("---", 2)[1])

    assert set(config["format"]) == {"typst"}
    assert front_matter["organization"] == 'North: "Studio"'
    assert front_matter["eyebrow"] == "Field Notes · 08"
    assert front_matter["title-layout"] == "compact"
    assert front_matter["accent"] == "#0f766e"
    assert front_matter["metrics"] == metrics
    assert front_matter["confidential-mark"] == "Internal working draft"
    assert "--rf-accent: #0f766e" in (project / "styles.scss").read_text()


def test_studio_balances_four_metrics_as_two_by_two(
    isolated_studio: Path,
) -> None:
    result = engine.scaffold_report(
        "studio-four-metrics",
        template="studio",
        formats=["html"],
        metrics=[
            {"value": str(index), "label": f"Measure {index}"}
            for index in range(1, 5)
        ],
    )

    assert result["ok"] is True
    project = Path(result["path"])
    header = (project / "assets" / "studio-header.html").read_text()
    assert 'class="rf-metric-grid rf-metrics-4"' in header


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"title_layout": "poster"}, "title layout"),
        ({"accent": "linear-gradient(red, blue)"}, "accent"),
        ({"metrics": [{"value": str(i), "label": str(i)} for i in range(7)]}, "at most 6"),
    ],
)
def test_studio_rejects_invalid_visual_options_before_creating_project(
    isolated_studio: Path,
    kwargs: dict[str, object],
    message: str,
) -> None:
    result = engine.scaffold_report(
        "studio-invalid",
        template="studio",
        **kwargs,
    )

    assert result["ok"] is False
    assert message in result["error"].lower()
    assert not (isolated_studio / "studio-invalid").exists()
