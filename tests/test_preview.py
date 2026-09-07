"""Task 1.5 contract tests — preview artifacts (RF-05).

Pinned to docs/milestone-a-contracts.md §5: contact-sheet + page-<n> +
exhibit-<fig-id> PNGs under output/previews/r<rev>/, returned as §3.2-shaped
relative-path descriptors (id/path/bytes/sha256/mime/role), revision-bound,
no host absolute paths, loud failure when pdftoppm or the rendered PDF is
missing. RED until engine.render_preview lands.
"""
from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from reportforge import engine


def _png_bytes(color: tuple[int, int, int] = (10, 20, 30)) -> bytes:
    img = Image.new("RGB", (4, 4), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def isolated_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    monkeypatch.setattr(engine, "REPORTS_DIR", reports)
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "reportforge")
    monkeypatch.setattr(engine, "_default_reference_docx", lambda: None)
    return reports


@pytest.fixture
def rendered_project(isolated_reports: Path) -> Path:
    """Scaffolded memo project with manifest, a chart, and a faked rendered PDF."""
    scaffold = engine.scaffold_report("preview-fixture", template="memo", formats=["pdf"])
    project = Path(scaffold["path"])
    (project / "report.json").write_text(
        '{"schema_version": 1, "report_id": "preview-fixture", "revision": 1, "state": "draft"}'
    )
    charts = project / "charts"
    charts.mkdir(exist_ok=True)
    (charts / "pnl.png").write_bytes(_png_bytes())
    out = project / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.pdf").write_bytes(b"%PDF-fake-not-a-real-pdf")
    return project


def _fake_pdftoppm(pages: int = 2) -> object:
    """Stand-in for subprocess.run: fakes pdfinfo + pdftoppm poppler calls.

    pdfinfo -> 'Pages: <pages>'; pdftoppm -> writes real tiny PNGs at
    <last-arg>-<n>.png (poppler's numbered multi-page naming).
    """

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        prog = Path(command[0]).name
        if prog == "pdfinfo":
            return subprocess.CompletedProcess(command, 0, f"Pages: {pages}\n", "")
        if prog == "pdftoppm":
            prefix = Path(command[-1])
            prefix.parent.mkdir(parents=True, exist_ok=True)
            for n in range(1, pages + 1):
                (prefix.parent / f"{prefix.name}-{n}.png").write_bytes(
                    _png_bytes((90, 90, 90))
                )
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    return fake_run


def test_render_preview_missing_project(isolated_reports: Path) -> None:
    result = engine.render_preview("no-such-project")
    assert result["ok"] is False
    assert "project not found" in result["error"]


def test_render_preview_requires_manifest(
    isolated_reports: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scaffold = engine.scaffold_report("preview-nomanifest", template="memo", formats=["pdf"])
    project = Path(scaffold["path"])
    # Simulate a legacy dir: scaffold writes a manifest since Task 1.2.
    (project / "report.json").unlink()
    out = project / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.pdf").write_bytes(b"%PDF-fake")
    monkeypatch.setattr(engine.subprocess, "run", _fake_pdftoppm())
    result = engine.render_preview("preview-nomanifest")
    assert result["ok"] is False
    assert "manifest" in result["error"].lower()


def test_render_preview_requires_rendered_pdf(
    rendered_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (rendered_project / "output" / "index.pdf").unlink()
    monkeypatch.setattr(engine.subprocess, "run", _fake_pdftoppm())
    result = engine.render_preview("preview-fixture")
    assert result["ok"] is False
    assert "pdf" in result["error"].lower()


def test_render_preview_missing_pdftoppm_is_loud(
    rendered_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(engine.shutil, "which", lambda name: None)
    result = engine.render_preview("preview-fixture")
    assert result["ok"] is False
    assert "pdftoppm" in result["error"].lower()


def test_render_preview_produces_contact_sheet_page_and_exhibit_pngs(
    rendered_project: Path, isolated_reports: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(engine.subprocess, "run", _fake_pdftoppm())
    result = engine.render_preview("preview-fixture")

    assert result["ok"] is True, result.get("error")
    ids = {a["id"] for a in result["artifacts"]}
    assert "contact-sheet" in ids
    assert "page-1" in ids
    assert "exhibit-pnl" in ids

    root = isolated_reports / "preview-fixture"
    for a in result["artifacts"]:
        p = root / a["path"]
        assert p.is_file(), a["path"]
        assert p.stat().st_size > 0
        assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", f"not a PNG: {a['path']}"
        assert a["bytes"] == p.stat().st_size
        assert a["mime"] == "image/png"
        assert a["role"] == "preview"
        assert a["sha256"] and len(a["sha256"]) == 64
    # stored under output/previews/r<rev>/ per §5
    previews_dir = root / "output" / "previews" / "r1"
    assert (previews_dir / "contact-sheet.png").is_file()


def test_render_preview_binds_revision_and_no_host_paths(
    rendered_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(engine.subprocess, "run", _fake_pdftoppm())
    result = engine.render_preview("preview-fixture")

    assert result["report_id"] == "preview-fixture"
    assert result["revision"] == 1
    for a in result["artifacts"]:
        assert not a["path"].startswith("/")
        assert "/home/" not in str(a)
    # read-only: manifest revision untouched
    import json

    m = json.loads((rendered_project / "report.json").read_text())
    assert m["revision"] == 1


def test_render_preview_rejects_stale_revision(
    rendered_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(engine.subprocess, "run", _fake_pdftoppm())
    result = engine.render_preview("preview-fixture", revision=99)
    assert result["ok"] is False
    assert "revision" in result["error"].lower()


def test_render_preview_mcp_tool_registered() -> None:
    import asyncio

    from reportforge import mcp_server

    tools = {t.name: t for t in asyncio.run(mcp_server.mcp.list_tools())}
    assert "reportforge_render_preview" in tools
    props = tools["reportforge_render_preview"].parameters["properties"]
    assert {"project", "revision"} <= set(props)
