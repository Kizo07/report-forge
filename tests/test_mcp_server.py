from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml

from reportforge import engine
from reportforge.mcp_server import _coerce_list, mcp


def test_mcp_scaffold_schema_exposes_studio_visual_options() -> None:
    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}

    scaffold = tools["reportforge_scaffold_report"]
    properties = scaffold.parameters["properties"]
    assert {
        "organization",
        "eyebrow",
        "title_layout",
        "accent",
        "metrics",
    } <= set(properties)
    assert properties["title_layout"]["default"] == "hero"
    assert properties["accent"]["default"] == "#4f46e5"


# --- WS-B: schema boundary must accept list | str | None -----------------

def _schema_types(prop: dict) -> set[str]:
    """Collect the JSON-schema types a property accepts (handles anyOf)."""
    types: set[str] = set()
    if "type" in prop:
        types.add(prop["type"])
    for variant in prop.get("anyOf", []):
        if "type" in variant:
            types.add(variant["type"])
    return types


@pytest.mark.parametrize("tool", ["reportforge_scaffold_report", "reportforge_render_report"])
def test_formats_param_accepts_string_at_schema_boundary(tool: str) -> None:
    """The 2026-09-01 studio run burned two scaffold attempts because formats
    was sent as a JSON string and the bare list[str] annotation rejected it at
    the pydantic boundary. The annotation must now admit str."""
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    properties = tools[tool].parameters["properties"]
    assert "string" in _schema_types(properties["formats"])


def test_scaffold_kpis_metrics_accept_string_at_schema_boundary() -> None:
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    properties = tools["reportforge_scaffold_report"].parameters["properties"]
    for name in ("kpis", "metrics"):
        assert "string" in _schema_types(properties[name])


# --- WS-B: _coerce_list normalization ------------------------------------

def test_coerce_list_parses_json_encoded_string() -> None:
    assert _coerce_list('["html", "pdf", "docx"]') == ["html", "pdf", "docx"]


def test_coerce_list_parses_csv_with_allowed_tokens() -> None:
    tokens = {"html", "pdf", "docx"}
    assert _coerce_list("html,pdf,docx", tokens) == ["html", "pdf", "docx"]
    assert _coerce_list(" html , pdf ", tokens) == ["html", "pdf"]


def test_coerce_list_csv_requires_all_tokens_known() -> None:
    tokens = {"html", "pdf", "docx"}
    # an unknown token means it's not a formats CSV — leave untouched
    assert _coerce_list("html,quarterly", tokens) == "html,quarterly"


def test_coerce_list_passthrough_list_and_none() -> None:
    assert _coerce_list(["pdf"]) == ["pdf"]
    assert _coerce_list(None) is None
    assert _coerce_list([{"value": "1", "label": "x"}]) == [{"value": "1", "label": "x"}]


def test_coerce_list_parses_json_object_string_for_kpis() -> None:
    assert _coerce_list('[{"value": "5%", "label": "yield"}]') == [{"value": "5%", "label": "yield"}]


# --- WS-B: end-to-end through the tool body ------------------------------

@pytest.fixture
def isolated_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    monkeypatch.setattr(engine, "REPORTS_DIR", reports)
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "reportforge")
    monkeypatch.setattr(engine, "_default_reference_docx", lambda: None)
    return reports


def test_scaffold_accepts_json_string_formats(isolated_reports: Path) -> None:
    """A JSON-encoded formats string (the exact shape that failed in run
    d1f6a9b5) must now scaffold successfully."""
    result = engine.scaffold_report(
        "wsb-json-formats",
        template="standard",
        formats=_coerce_list('["html", "pdf", "docx"]', {"html", "pdf", "docx"}),
    )
    assert result["ok"] is True
    config = yaml.safe_load((Path(result["path"]) / "_quarto.yml").read_text())
    assert set(config["format"]) == {"html", "pdf", "docx"}


def test_scaffold_accepts_csv_formats(isolated_reports: Path) -> None:
    result = engine.scaffold_report(
        "wsb-csv-formats",
        template="standard",
        formats=_coerce_list("html,docx", {"html", "pdf", "docx"}),
    )
    assert result["ok"] is True
    config = yaml.safe_load((Path(result["path"]) / "_quarto.yml").read_text())
    assert set(config["format"]) == {"html", "docx"}


# --- WS-C: publish_report delivery bridge --------------------------------

def test_publish_report_copies_outputs_into_dest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """publish_report bridges host renders into the thread outputs dir."""
    project_dir = engine.REPORTS_DIR / "wsc-publish-test"
    out = project_dir / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.pdf").write_bytes(b"%PDF-fake")
    (out / "index.html").write_text("<html>ok</html>")
    (out / "index_files" / "lib").mkdir(parents=True, exist_ok=True)
    (out / "index_files" / "lib" / "asset.js").write_text("//js")
    try:
        dest = tmp_path / "thread-outputs"
        result = engine.publish_report("wsc-publish-test", dest_dir=str(dest))
        assert result["ok"] is True
        assert set(result["published"]) == {"index.pdf", "index.html", "index_files/"}
        assert (dest / "wsc-publish-test" / "index.pdf").is_file()
        assert (dest / "wsc-publish-test" / "index_files" / "lib" / "asset.js").is_file()
        assert result["present_paths"] == [
            "/mnt/user-data/outputs/wsc-publish-test/index.html",
            "/mnt/user-data/outputs/wsc-publish-test/index.pdf",
            "/mnt/user-data/outputs/wsc-publish-test/index_files/",
        ]
        # env fallback: no dest_dir, DEERFLOW_THREAD_OUTPUTS_HOST set
        env_dest = tmp_path / "env-outputs"
        monkeypatch.setenv("DEERFLOW_THREAD_OUTPUTS_HOST", str(env_dest))
        result2 = engine.publish_report("wsc-publish-test")
        assert result2["ok"] is True
        assert result2["host_dir"] == str(env_dest / "wsc-publish-test")
        # no dest at all -> clean error, not a crash
        monkeypatch.delenv("DEERFLOW_THREAD_OUTPUTS_HOST", raising=False)
        result3 = engine.publish_report("wsc-publish-test")
        assert result3["ok"] is False
        assert "no thread outputs dir" in result3["error"]
        # unknown project -> clean error
        result4 = engine.publish_report("does-not-exist", dest_dir=str(dest))
        assert result4["ok"] is False and "project not found" in result4["error"]
    finally:
        import shutil as _shutil

        _shutil.rmtree(project_dir, ignore_errors=True)


def test_publish_report_mcp_tool_registered() -> None:
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    assert "reportforge_publish_report" in tools
    props = tools["reportforge_publish_report"].parameters["properties"]
    assert "project" in props and "dest_dir" in props
