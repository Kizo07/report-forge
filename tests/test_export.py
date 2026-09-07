"""Task 1.6 contract tests — export bundle + delivery descriptors (RF-06).

Pinned to docs/milestone-a-contracts.md §3 (r<rev> layout, manifest.json copy,
relative-path descriptors with sha256, approved-state gate, opt-in source/).
RED until engine.export_release + manifest-writing scaffold (Task 1.1/1.2) land.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from reportforge import engine


@pytest.fixture
def isolated_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    monkeypatch.setattr(engine, "REPORTS_DIR", reports)
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "reportforge")
    monkeypatch.setattr(engine, "_default_reference_docx", lambda: None)
    return reports


def _approve(project_root: Path) -> None:
    """Force the manifest to approved state (test setup, bypasses transitions)."""
    mpath = project_root / "report.json"
    m = json.loads(mpath.read_text())
    m["state"] = "approved"
    mpath.write_text(json.dumps(m))


@pytest.fixture
def rendered_project(isolated_reports: Path) -> dict:
    """Scaffolded standard project with faked rendered artifacts in output/."""
    scaffold = engine.scaffold_report(
        "export-fixture", template="standard", formats=["html", "pdf", "docx"]
    )
    project = Path(scaffold["path"])
    out = project / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text("<html><body>ok</body></html>")
    (out / "index.pdf").write_bytes(b"%PDF-fake")
    (out / "index.docx").write_bytes(b"PK-fake-docx")
    (out / "index_files" / "lib").mkdir(parents=True, exist_ok=True)
    (out / "index_files" / "lib" / "asset.js").write_text("//js")
    _approve(project)
    return {"scaffold": scaffold, "project": project}


def test_export_release_missing_project(isolated_reports: Path, tmp_path: Path) -> None:
    result = engine.export_release("no-such-project", dest=str(tmp_path / "bundle"))
    assert result["ok"] is False
    assert "project not found" in result["error"]


def test_export_release_requires_rendered_output(
    isolated_reports: Path, tmp_path: Path
) -> None:
    scaffold = engine.scaffold_report("export-empty", template="standard", formats=["pdf"])
    _approve(Path(scaffold["path"]))
    result = engine.export_release("export-empty", dest=str(tmp_path / "bundle"))
    assert result["ok"] is False
    assert "render" in result["error"].lower()


def test_export_release_draft_is_illegal(
    isolated_reports: Path, tmp_path: Path
) -> None:
    """§3.1: export requires state == approved; exporting a draft fails loudly."""
    scaffold = engine.scaffold_report("export-draft", template="standard", formats=["pdf"])
    project = Path(scaffold["path"])
    out = project / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.pdf").write_bytes(b"%PDF-fake")
    result = engine.export_release("export-draft", dest=str(tmp_path / "bundle"))
    assert result["ok"] is False
    assert "approved" in result["error"].lower()
    assert not (tmp_path / "bundle" / "export-draft").exists()


def test_export_release_writes_self_contained_bundle(
    rendered_project: dict, isolated_reports: Path, tmp_path: Path
) -> None:
    dest = tmp_path / "bundle"
    result = engine.export_release("export-fixture", revision=1, dest=str(dest))

    assert result["ok"] is True, result.get("error")
    bundle_root = dest / "export-fixture" / "r1"
    assert (bundle_root / "index.pdf").read_bytes() == b"%PDF-fake"
    assert (bundle_root / "index.html").read_text() == "<html><body>ok</body></html>"
    assert (bundle_root / "index.docx").read_bytes() == b"PK-fake-docx"
    # manifest copy travels with the bundle (named manifest.json per §3.1)
    manifest_path = bundle_root / "manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text())
    assert manifest["report_id"] == "export-fixture"
    # descriptor index travels with the bundle
    assert (bundle_root / "bundle.json").is_file()
    # companion asset dirs are included (self-contained html)
    assert (bundle_root / "index_files" / "lib" / "asset.js").is_file()


def test_export_release_descriptors_are_relative_sha256_and_resolve(
    rendered_project: dict, isolated_reports: Path, tmp_path: Path
) -> None:
    dest = tmp_path / "bundle"
    result = engine.export_release("export-fixture", revision=1, dest=str(dest))

    descriptors = result["artifacts"]
    assert descriptors, "bundle must expose artifact descriptors"
    deliverables = [d for d in descriptors if d.get("role") == "deliverable"]
    assert {d["id"] for d in deliverables} >= {"pdf", "html", "docx"}
    for d in descriptors:
        rel = d["path"]
        assert not rel.startswith("/"), f"descriptor must be relative: {rel}"
        assert "/home/" not in rel
        assert d.get("sha256"), f"descriptor missing sha256: {rel}"
        target = dest / "export-fixture" / "r1" / rel
        assert target.is_file(), f"descriptor does not resolve: {rel}"
    # bundle.json on disk agrees with the response
    on_disk = json.loads((dest / "export-fixture" / "r1" / "bundle.json").read_text())
    assert {d["path"] for d in on_disk["artifacts"]} == {d["path"] for d in descriptors}


def test_export_release_source_inclusion_is_opt_in(
    rendered_project: dict, isolated_reports: Path, tmp_path: Path
) -> None:
    dest_default = tmp_path / "b1"
    r1 = engine.export_release("export-fixture", revision=1, dest=str(dest_default))
    assert r1["ok"] is True
    bundle = dest_default / "export-fixture" / "r1"
    assert not (bundle / "source").exists()
    assert not (bundle / "data").exists()

    dest_src = tmp_path / "b2"
    r2 = engine.export_release(
        "export-fixture", revision=1, dest=str(dest_src), include_source=True
    )
    assert r2["ok"] is True
    bundle2 = dest_src / "export-fixture" / "r1"
    assert (bundle2 / "source" / "index.qmd").is_file()


def test_export_release_revision_dir_separates_revisions(
    rendered_project: dict, isolated_reports: Path, tmp_path: Path
) -> None:
    dest = tmp_path / "bundle"
    r1 = engine.export_release("export-fixture", revision=1, dest=str(dest))
    assert r1["ok"] is True
    # manifest revision advances; a second export lands in a new r<N> dir
    mpath = isolated_reports / "export-fixture" / "report.json"
    m = json.loads(mpath.read_text())
    m["revision"] = 2
    mpath.write_text(json.dumps(m))
    r2 = engine.export_release("export-fixture", revision=2, dest=str(dest))
    assert r2["ok"] is True
    assert (dest / "export-fixture" / "r2" / "index.pdf").is_file()
    assert (dest / "export-fixture" / "r1" / "index.pdf").is_file()


def test_export_release_marks_state_exported(
    rendered_project: dict, isolated_reports: Path, tmp_path: Path
) -> None:
    """§1.4: only export_release may set exported, only from approved."""
    dest = tmp_path / "bundle"
    result = engine.export_release("export-fixture", revision=1, dest=str(dest))
    assert result["ok"] is True
    m = json.loads((isolated_reports / "export-fixture" / "report.json").read_text())
    assert m["state"] == "exported"


def test_publish_report_back_compat(
    rendered_project: dict, isolated_reports: Path, tmp_path: Path
) -> None:
    """Task 1.6 must extend, not break, the existing publish_report bridge."""
    dest = tmp_path / "thread-outputs"
    result = engine.publish_report("export-fixture", dest_dir=str(dest))
    assert result["ok"] is True
    assert set(result["published"]) == {"index.pdf", "index.html", "index.docx", "index_files/"}
    assert (dest / "export-fixture" / "index.pdf").is_file()


def test_export_release_mcp_tool_registered() -> None:
    import asyncio

    from reportforge import mcp_server

    tools = {t.name: t for t in asyncio.run(mcp_server.mcp.list_tools())}
    assert "reportforge_export_release" in tools
    props = tools["reportforge_export_release"].parameters["properties"]
    assert {"project", "dest"} <= set(props)
