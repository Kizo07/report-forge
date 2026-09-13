"""Report-brief contract v1 (schema `report_brief`) — Phase 4a.

Covers validation (strict, all-errors-at-once), the engine wrapper
(`scaffold_from_brief`), manifest recording (schema 5 `report_brief`
field), parity with the kwargs scaffold path, and MCP registration.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from reportforge import engine, templates
from reportforge.brief import (
    SCHEMA_NAME,
    SCHEMA_VERSION,
    BriefError,
    brief_to_scaffold_kwargs,
    parse_brief,
    validate_brief,
)


@pytest.fixture
def isolated_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    monkeypatch.setattr(engine, "REPORTS_DIR", reports)
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "reportforge")
    monkeypatch.setattr(engine, "_default_reference_docx", lambda: None)
    return reports


def _valid_brief(**overrides) -> dict:
    brief = {
        "schema": SCHEMA_NAME,
        "version": SCHEMA_VERSION,
        "project": "brief-probe",
        "template": "memo",
        "formats": ["html"],
        "title": "Brief Probe",
    }
    brief.update(overrides)
    return brief


# --- validation ---------------------------------------------------------------


def test_valid_brief_parses_and_normalizes():
    parsed = parse_brief(_valid_brief())
    assert parsed["project"] == "brief-probe"
    assert "schema" not in parsed and "version" not in parsed  # envelope stripped
    kwargs = brief_to_scaffold_kwargs(parsed)
    assert kwargs["slug"] == "brief-probe"
    assert kwargs["template"] == "memo"
    assert "brief" not in kwargs  # commissioning metadata, not a kwarg


def test_wrong_envelope_rejected():
    parsed, errors = validate_brief(_valid_brief(schema="manifest"))
    assert parsed is None
    assert any("schema" in e for e in errors)


def test_unsupported_version_rejected():
    parsed, errors = validate_brief(_valid_brief(version=2))
    assert parsed is None
    assert any("version 2" in e and "understands version 1" in e for e in errors)


def test_non_integer_version_rejected():
    parsed, errors = validate_brief(_valid_brief(version="1"))
    assert parsed is None
    assert any("integer" in e for e in errors)


def test_missing_required_keys_reported_together():
    brief = _valid_brief()
    del brief["project"]
    del brief["template"]
    parsed, errors = validate_brief(brief)
    assert parsed is None
    assert sum("missing required key" in e for e in errors) == 2


def test_unknown_keys_rejected_with_hint():
    parsed, errors = validate_brief(_valid_brief(pages=3))
    assert parsed is None
    assert any("unknown key" in e and "pages" in e for e in errors)


def test_bad_slug_rejected():
    parsed, errors = validate_brief(_valid_brief(project="My Report!"))
    assert parsed is None
    assert any("slug" in e for e in errors)


def test_field_type_errors_collected():
    parsed, errors = validate_brief(
        _valid_brief(title=42, metrics="nope", engine_charts_only="yes", formats="html"))
    assert parsed is None
    joined = " | ".join(errors)
    for fragment in ("'title'", "'metrics'", "'engine_charts_only'", "'formats'"):
        assert fragment in joined


def test_parse_brief_raises_brief_error():
    with pytest.raises(BriefError):
        parse_brief({"schema": "report_brief", "version": 1})


# --- engine surface -------------------------------------------------------------


def test_scaffold_from_brief_records_brief_in_manifest(isolated_reports):
    result = engine.scaffold_from_brief(
        _valid_brief(brief="Commissioned by the Phase 4 contract probe"))
    assert result["ok"] is True, result
    assert result["report_brief"] == {"schema": SCHEMA_NAME, "version": SCHEMA_VERSION}

    manifest = json.loads(
        (isolated_reports / "brief-probe" / "report.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 5
    assert manifest["report_brief"]["project"] == "brief-probe"
    assert manifest["report_brief"]["brief"] == "Commissioned by the Phase 4 contract probe"


def test_scaffold_from_brief_validation_failure_shape(isolated_reports):
    result = engine.scaffold_from_brief({"schema": "report_brief", "version": 1})
    assert result["ok"] is False
    assert result["errors"]


def test_scaffold_from_brief_matches_kwargs_scaffold(isolated_reports):
    """A brief without commissioning metadata must scaffold the SAME
    project (minus the manifest's report_brief record) as the equivalent
    kwargs call."""
    engine.scaffold_from_brief(_valid_brief(project="parity-a"))
    engine.scaffold_report(
        slug="parity-b", template="memo", formats=["html"], title="Brief Probe")
    a = templates.scaffold_tree_hash(isolated_reports / "parity-a")
    b = templates.scaffold_tree_hash(isolated_reports / "parity-b")
    # manifests legitimately differ (report_brief + id/title text) —
    # everything else must be byte-identical
    diff = sorted(k for k in set(a) | set(b)
                  if k != "report.json" and a.get(k) != b.get(k))
    assert not diff, f"brief/kwargs scaffolds diverge: {diff}"


def test_old_schema_manifests_still_load(isolated_reports):
    """Schema 4 manifests (pre-brief) must keep loading after the bump:
    from_dict rejects only newer schemas; missing report_brief defaults."""
    engine.scaffold_report("legacy-s4", template="memo", formats=["html"])
    manifest_path = isolated_reports / "legacy-s4" / "report.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 5
    data["schema_version"] = 4  # simulate a pre-bump manifest
    data.pop("report_brief", None)
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    manifest = engine.manifest_mod.load(str(isolated_reports / "legacy-s4"))
    assert manifest.report_brief == {}


# --- MCP surface ----------------------------------------------------------------


def test_mcp_tool_registered():
    import asyncio
    from reportforge.mcp_server import mcp

    tools = {t.name for t in asyncio.run(mcp.list_tools())}
    assert "reportforge_scaffold_from_brief" in tools


def test_scaffold_from_brief_bespoke_records_brief(isolated_reports):
    """Milestone D blocking finding 1: the bespoke scaffold path must
    forward the commissioning record like every other path."""
    result = engine.scaffold_from_brief(_valid_brief(
        project="brief-bespoke",
        template="bespoke",
        frontmatter_yaml='title: "Bespoke From Brief"',
        body="# Bespoke body\n",
        brief="bespoke commissioning note"))
    assert result["ok"] is True, result
    manifest = json.loads(
        (isolated_reports / "brief-bespoke" / "report.json").read_text(encoding="utf-8"))
    assert manifest["report_brief"]["template"] == "bespoke"
    assert manifest["report_brief"]["brief"] == "bespoke commissioning note"


def test_brief_rejects_fields_the_template_ignores(isolated_reports):
    """Milestone D finding 3: a brief that sets cover fields on a
    non-editorial template is a loud error, never a silent drop."""
    result = engine.scaffold_from_brief(_valid_brief(
        project="brief-drop", template="memo",
        metrics=[{"label": "Target", "value": "$1"}]))
    assert result["ok"] is False
    assert any("metrics" in e for e in result["errors"])
