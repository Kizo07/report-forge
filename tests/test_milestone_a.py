"""Tasks 1.2 + 1.7 — scaffold manifest, status/open views, capabilities, CLI."""

from __future__ import annotations

import json
from pathlib import Path

from reportforge import engine
from reportforge.cli import main as cli_main


def _scaffold(monkeypatch, tmp_path: Path, slug: str = "journey-probe",
              template: str = "standard", formats=None):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    return engine.scaffold_report(slug, template=template,
                                  formats=formats or ["html", "pdf"])


def test_scaffold_writes_manifest(tmp_path, monkeypatch):
    res = _scaffold(monkeypatch, tmp_path)
    assert res["ok"] is True
    m = json.loads((tmp_path / "reports" / "journey-probe" / "report.json").read_text())
    assert m["report_id"] == "journey-probe"
    assert m["revision"] == 1 and m["state"] == "draft"
    assert m["profile"]["report_type"] == "standard"
    assert m["profile"]["theme"] == "light"
    assert m["formats"] == ["html", "pdf"]
    assert len(m["sections"]) > 0
    assert m["schema_version"] == 2  # Milestone B: registries ride schema 2


def test_status_and_open_expose_manifest_view(tmp_path, monkeypatch):
    _scaffold(monkeypatch, tmp_path)
    st = engine.project_status("journey-probe")
    assert st["ok"] is True
    assert st["manifest"]["revision"] == 1
    assert st["manifest"]["state"] == "draft"
    assert st["manifest"]["sections"]
    assert st["missing_work"]["manifest"] is True
    assert "pdf" in st["missing_work"]["unrendered_formats"]  # configured, not rendered
    assert st["missing_work"]["error_counts"] == {}
    op = engine.open_report("journey-probe")
    assert op["ok"] is True
    assert op["report_id"] == "journey-probe"
    assert op["revision"] == 1
    assert engine.open_report("nope")["ok"] is False


def test_capabilities_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    caps = engine.reportforge_capabilities()
    assert caps["schema_version"] == 1 and caps["server"] == "reportforge"
    assert len(caps["templates"]) >= 17
    assert caps["profiles"]["themes"] == ["light", "dark"]
    assert any(r["template"] == "standard" for r in caps["support_matrix"])
    assert caps["execution"]["run_code"] == (caps["execution"]["disabled_reason"] is None)
    assert caps["preview"]["backend"] == "pdftoppm"
    assert "reportforge_replace_section" in caps["tools"]
    assert "reportforge_export_release" in caps["tools"]
    assert "reportforge_capabilities" in caps["tools"]
    assert caps["manifest"]["states"] == ["draft", "review", "approved", "exported"]
    assert caps["docs"]["journeys"] == "docs/agent-journeys.md"


def test_capabilities_mcp_tool_registered():
    import asyncio

    from reportforge.mcp_server import mcp

    tools = {t.name for t in asyncio.run(mcp.list_tools())}
    assert "reportforge_capabilities" in tools
    assert "reportforge_check_readiness" in tools
    assert "reportforge_record_review" in tools


def test_mcp_tool_fallback_mirrors_live_registry():
    """F7: the static RF-07 tool list must equal the live MCP registry —
    a new tool missing from the fallback is a discovery failure."""
    import asyncio

    from reportforge.mcp_server import mcp

    live = {t.name for t in asyncio.run(mcp.list_tools())}
    assert set(engine.MCP_TOOL_NAMES_FALLBACK) == live
    assert set(engine._mcp_tool_names()) == live


def test_capabilities_env_dependence(tmp_path, monkeypatch):
    """F6: execution/preview flags must reflect the live environment."""
    import os

    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setenv("REPORTFORGE_EXEC", "off")
    caps = engine.reportforge_capabilities()
    assert caps["execution"]["run_code"] is False
    assert caps["execution"]["disabled_reason"] == "REPORTFORGE_EXEC=off"
    monkeypatch.delenv("REPORTFORGE_EXEC")
    caps = engine.reportforge_capabilities()
    assert caps["execution"]["run_code"] is True
    assert caps["execution"]["disabled_reason"] is None
    assert caps["preview"]["available"] == (engine.shutil.which("pdftoppm") is not None)
    # Stored-profile taxonomy agrees with discovery (F5); C-1: no renames.
    assert caps["profiles"]["report_type_map"] == {}


def test_status_unrendered_clears_after_render(tmp_path, monkeypatch):
    """F1: rendered formats leave unrendered_formats; ids are contract handles."""
    _scaffold(monkeypatch, tmp_path)
    root = tmp_path / "reports" / "journey-probe"
    out = root / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text("<html></html>")
    (out / "index.pdf").write_bytes(b"%PDF-fake")
    st = engine.project_status("journey-probe")
    assert st["ok"] is True
    assert st["missing_work"]["unrendered_formats"] == []
    by_id = {a["id"]: a for a in st["artifacts"]}
    assert set(by_id) == {"html", "pdf"}
    for a in st["artifacts"]:
        assert not Path(a["path"]).is_absolute()
        assert (root / a["path"]).is_file()  # root-relative, resolvable


def test_open_report_has_missing_work_and_artifacts(tmp_path, monkeypatch):
    """F2: open_report carries the §4.2 projection and artifacts per §1.6."""
    _scaffold(monkeypatch, tmp_path)
    op = engine.open_report("journey-probe")
    assert op["ok"] is True
    assert op["missing_work"]["manifest"] is True
    assert isinstance(op["artifacts"], list)


def test_bespoke_scaffold_writes_manifest(tmp_path, monkeypatch):
    """F3: bespoke scaffolds persist report.json incl. pdf-web, no lazy loss."""
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    res = engine.scaffold_report("bespoke-probe", template="bespoke",
                                 formats=["html", "pdf-web"])
    assert res["ok"] is True
    m = json.loads((tmp_path / "reports" / "bespoke-probe" / "report.json").read_text())
    assert m["revision"] == 1 and m["state"] == "draft"
    assert m["profile"]["report_type"] == "bespoke"
    assert "pdf-web" in m["formats"]
    assert m["profile"]["output_profile"] == "web"


def test_corrupt_manifest_error_surfaces(tmp_path, monkeypatch):
    """F8: a corrupt report.json yields a loud reason, not a silent null."""
    _scaffold(monkeypatch, tmp_path)
    (tmp_path / "reports" / "journey-probe" / "report.json").write_text("{broken")
    st = engine.project_status("journey-probe")
    assert st["ok"] is True
    assert st["manifest"] is None
    assert st["manifest_error"]
    op = engine.open_report("journey-probe")
    assert op["ok"] is False
    assert op["manifest_error"]


def test_cli_new_status_open_capabilities(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    assert cli_main(["new", "cli-probe", "--template", "memo"]) == 0
    capsys.readouterr()
    assert cli_main(["status", "cli-probe"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["manifest"]["profile"]["report_type"] == "memo"
    assert cli_main(["open", "cli-probe"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["report_id"] == "cli-probe"
    assert cli_main(["capabilities"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["server"] == "reportforge"
    assert cli_main(["status", "nope"]) == 1
