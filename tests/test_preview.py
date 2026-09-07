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
    # Task 1.2's scaffold already wrote a proper revision-1 manifest; the
    # preview path consumes it through manifest_mod.load (drift repair).
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


def test_render_preview_missing_manifest_auto_imports(
    isolated_reports: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Legacy dirs without report.json are adopted via import_dir (§1.6)."""
    import json

    scaffold = engine.scaffold_report("preview-nomanifest", template="memo", formats=["pdf"])
    project = Path(scaffold["path"])
    (project / "report.json").unlink()
    out = project / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.pdf").write_bytes(b"%PDF-fake")
    monkeypatch.setattr(engine.subprocess, "run", _fake_pdftoppm())
    result = engine.render_preview("preview-nomanifest")
    assert result["ok"] is True, result.get("error")
    assert json.loads((project / "report.json").read_text())["revision"] == 1


def test_render_preview_missing_qmd_is_loud(
    isolated_reports: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scaffold = engine.scaffold_report("preview-noqmd", template="memo", formats=["pdf"])
    project = Path(scaffold["path"])
    (project / "report.json").unlink()
    (project / "index.qmd").unlink()
    result = engine.render_preview("preview-noqmd")
    assert result["ok"] is False
    assert "index.qmd" in result["error"]


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


# --- critic-2 RF-05 review regressions ---------------------------------------

def _write_render_state(project: Path, revision: int | None) -> None:
    import json

    (project / ".reportforge-state.json").write_text(
        json.dumps({"last_render": "2026-09-07T00:00:00+00:00",
                    "manifest_revision": revision, "formats": ["pdf"],
                    "outputs": ["index.pdf"], "source": "index.qmd"}))


def test_render_preview_refuses_stale_pdf(
    rendered_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PDF rendered at r1, manifest bumped to r2 → loud re-render demand."""
    from reportforge import manifest as manifest_mod

    m = manifest_mod.load(str(rendered_project))
    manifest_mod.bump(m, "content edit", actor="test")
    manifest_mod.save(m, str(rendered_project))
    _write_render_state(rendered_project, 1)
    monkeypatch.setattr(engine.subprocess, "run", _fake_pdftoppm())
    result = engine.render_preview("preview-fixture")
    assert result["ok"] is False
    assert "render" in result["error"].lower()
    assert result["pdf_rendered_at_revision"] == 1
    assert result["current_revision"] == 2
    assert not (rendered_project / "output" / "previews").exists()


def test_render_preview_stamped_pdf_binds_revision(
    rendered_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_render_state(rendered_project, 1)
    monkeypatch.setattr(engine.subprocess, "run", _fake_pdftoppm())
    result = engine.render_preview("preview-fixture")
    assert result["ok"] is True, result.get("error")
    assert result["pdf_rendered_at_revision"] == 1
    assert result["warnings"] == []


def test_render_preview_unstamped_pdf_warns(
    rendered_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert not (rendered_project / ".reportforge-state.json").exists()
    monkeypatch.setattr(engine.subprocess, "run", _fake_pdftoppm())
    result = engine.render_preview("preview-fixture")
    assert result["ok"] is True, result.get("error")
    assert result["pdf_rendered_at_revision"] is None
    assert any("re-render" in w for w in result["warnings"])


def _fake_pdftoppm_single_page() -> object:
    """Poppler names single-page output <prefix>.png (no page number)."""

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        prog = Path(command[0]).name
        if prog == "pdfinfo":
            return subprocess.CompletedProcess(command, 0, "Pages: 1\n", "")
        if prog == "pdftoppm":
            prefix = Path(command[-1])
            prefix.parent.mkdir(parents=True, exist_ok=True)
            (prefix.parent / f"{prefix.name}.png").write_bytes(_png_bytes())
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 0, "", "", )

    return fake_run


def test_render_preview_single_page_fallback(
    rendered_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(engine.subprocess, "run", _fake_pdftoppm_single_page())
    result = engine.render_preview("preview-fixture")
    assert result["ok"] is True, result.get("error")
    assert result["page_count"] == 1
    assert "page-1" in {a["id"] for a in result["artifacts"]}
    assert (rendered_project / "output" / "previews" / "r1" / "pages" / "page-1.png").is_file()
