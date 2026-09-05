"""Scaffold tests for the domain template family (typed research bodies)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from reportforge import engine, templates


@pytest.fixture
def isolated_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    monkeypatch.setattr(engine, "REPORTS_DIR", reports)
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "reportforge")
    monkeypatch.setattr(engine, "_default_reference_docx", lambda: None)
    return reports


DOMAIN_TEMPLATES = sorted(templates.DOMAIN_BODY_TEMPLATES)


def test_catalog_exposes_all_domain_templates() -> None:
    specs = {item["name"]: item for item in engine.list_templates()}
    for name in DOMAIN_TEMPLATES:
        assert name in specs, f"{name} missing from list_templates()"
        spec = specs[name]
        assert spec["formats"] == ["html", "pdf", "docx"]
        assert spec["exhibit_labels"] is True
        assert spec["papersize"] in ("us-letter", "a4")
        assert isinstance(spec["toc"], bool)
        assert isinstance(spec["number_sections"], bool)


def test_every_domain_body_renders_through_jinja() -> None:
    ctx = {
        "title_yaml": '"T"',
        "subtitle_yaml": '"S"',
        "author_yaml": '"A"',
        "date_yaml": '"2026-09-04"',
        "abstract_yaml": '"Abs."',
        "template_name": "x",
    }
    for name, body in templates.DOMAIN_BODY_TEMPLATES.items():
        rendered = engine._tpl(body).render(ctx)
        assert "<%" not in rendered, f"{name}: unrendered placeholder"
        assert "{#fig-" in rendered, f"{name}: no figure crossref"
        assert "```{python}" in rendered, f"{name}: no exhibit chunk"


@pytest.mark.parametrize("name", DOMAIN_TEMPLATES)
def test_domain_scaffold_creates_valid_project(
    isolated_reports: Path, name: str
) -> None:
    spec = next(item for item in engine.list_templates() if item["name"] == name)
    result = engine.scaffold_report(
        f"{name}-proj",
        title="Domain Check",
        template=name,
    )

    assert result["ok"] is True, result
    project = Path(result["path"])
    config = yaml.safe_load((project / "_quarto.yml").read_text())
    qmd = (project / "index.qmd").read_text()

    assert set(config["format"]) == {"html", "pdf", "docx"}
    # exhibit_labels -> unified Exhibit crossref block
    assert config["crossref"]["fig-prefix"] == "Exhibit"
    assert config["format"]["pdf"]["papersize"] == spec["papersize"]
    assert config["format"]["pdf"]["toc"] == spec["toc"]
    # frontmatter round-trips and records the scaffold template
    front_matter = yaml.safe_load(qmd.split("---", 2)[1])
    assert front_matter["reportforge-template"] == name
    # flagship gates: explicit exhibit width + {#fig-} crossref + no tics
    assert "width=85%" in qmd
    assert "#fig-example" in qmd and "@fig-example" in qmd
    assert not re.search(r"^#\| (label|fig-cap):", qmd, re.MULTILINE)
    low = qmd.lower()
    for tic in ("delve", "tapestry", "forensic attention", "honestly labeled"):
        assert tic not in low


def test_domain_scaffold_honors_format_subset(isolated_reports: Path) -> None:
    result = engine.scaffold_report(
        "earnings-recap-subset",
        template="earnings-recap",
        formats=["html"],
    )
    assert result["ok"] is True
    config = yaml.safe_load((Path(result["path"]) / "_quarto.yml").read_text())
    assert set(config["format"]) == {"html"}


def test_unknown_template_still_rejected(isolated_reports: Path) -> None:
    result = engine.scaffold_report("nope", template="earnings-recapp")
    assert result["ok"] is False
    assert "unknown template" in result["error"]
