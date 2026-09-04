from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from reportforge import engine


@pytest.fixture
def isolated_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    monkeypatch.setattr(engine, "REPORTS_DIR", reports)
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "reportforge")
    monkeypatch.setattr(engine, "_default_reference_docx", lambda: None)
    return reports


@pytest.mark.parametrize(
    ("template", "requested", "configured"),
    [
        ("standard", ["html"], {"html"}),
        ("standard", ["pdf"], {"pdf"}),
        ("standard", ["docx"], {"docx"}),
        ("standard", ["html", "docx"], {"html", "docx"}),
        ("standard", ["pdf", "docx"], {"pdf", "docx"}),
        ("standard", ["html", "pdf", "docx"], {"html", "pdf", "docx"}),
        ("modern", ["html", "docx"], {"html", "docx"}),
        ("modern", ["pdf"], {"typst"}),
        ("modern", ["html", "pdf", "docx"], {"html", "typst", "docx"}),
        ("memo", ["html"], {"html"}),
    ],
)
def test_scaffold_preserves_exact_supported_format_subset(
    isolated_reports: Path,
    template: str,
    requested: list[str],
    configured: set[str],
) -> None:
    result = engine.scaffold_report(
        f"{template}-subset",
        template=template,
        formats=requested,
    )

    assert result["ok"] is True
    project = Path(result["path"])
    config = yaml.safe_load((project / "_quarto.yml").read_text())
    assert set(config["format"]) == configured


def test_scaffold_serializes_user_metadata_as_valid_yaml(
    isolated_reports: Path,
) -> None:
    title = 'The "Quoted": Thesis — Δ'
    subtitle = 'What changed: "now"'
    author = 'Analyst "A":\nResearch Team'
    firm = 'Studio: "North"'
    mark = 'Internal: "Do not forward"'

    result = engine.scaffold_report(
        "quoted-metadata",
        title=title,
        subtitle=subtitle,
        author=author,
        abstract="Line one:\nLine two with “Unicode”.",
        template="modern",
        formats=["html"],
        firm=firm,
        confidential_mark=mark,
        kpis=[{"value": '42: "high"', "label": "Signal: Δ"}],
    )

    assert result["ok"] is True
    source = Path(result["source"]).read_text()
    front_matter = yaml.safe_load(source.split("---", 2)[1])
    assert front_matter["title"] == title
    assert front_matter["subtitle"] == subtitle
    assert front_matter["author"] == author
    assert front_matter["firm"] == firm
    assert front_matter["confidential-mark"] == mark
    assert front_matter["kpis"] == [{"value": '42: "high"', "label": "Signal: Δ"}]


def test_scaffold_rejects_unsupported_format_without_creating_project(
    isolated_reports: Path,
) -> None:
    result = engine.scaffold_report(
        "bad-format",
        template="standard",
        formats=["pptx"],
    )

    assert result["ok"] is False
    assert "unsupported format" in result["error"]
    assert not (isolated_reports / "bad-format").exists()


def test_scaffold_rejects_format_not_supported_by_selected_template(
    isolated_reports: Path,
) -> None:
    result = engine.scaffold_report(
        "memo-docx",
        template="memo",
        formats=["docx"],
    )

    assert result["ok"] is False
    assert "memo" in result["error"]
    assert "docx" in result["error"]
    assert not (isolated_reports / "memo-docx").exists()


def test_scaffold_rejects_empty_slug_without_writing_into_reports_root(
    isolated_reports: Path,
) -> None:
    result = engine.scaffold_report(
        "   ",
        template="standard",
        formats=["html"],
    )

    assert result["ok"] is False
    assert "slug" in result["error"]
    assert not isolated_reports.exists()


def test_render_directory_resolves_project_and_returns_created_output(
    isolated_reports: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scaffold = engine.scaffold_report(
        "directory-source",
        template="memo",
        formats=["html"],
    )
    project = Path(scaffold["path"])
    calls: list[tuple[list[str], Path]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        cwd = Path(str(kwargs["cwd"]))
        calls.append((command, cwd))
        output = project / "output" / "index.html"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("<html><body>created</body></html>")
        return subprocess.CompletedProcess(command, 0, "rendered", "")

    monkeypatch.setattr(engine.subprocess, "run", fake_run)

    result = engine.render_report(str(project), formats=["html"])

    assert result["ok"] is True
    assert result["outputs"] == [str(project / "output" / "index.html")]
    assert calls == [
        (
            ["quarto", "render", str(project / "index.qmd"), "--to", "html"],
            project,
        )
    ]


def test_render_returns_only_outputs_requested_in_current_run(
    isolated_reports: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scaffold = engine.scaffold_report(
        "fresh-outputs",
        template="memo",
        formats=["html", "pdf"],
    )
    project = Path(scaffold["path"])
    output_dir = project / "output"
    output_dir.mkdir()
    (output_dir / "index.pdf").write_bytes(b"stale")

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        (output_dir / "index.html").write_text("<html><body>fresh</body></html>")
        return subprocess.CompletedProcess(command, 0, "rendered", "")

    monkeypatch.setattr(engine.subprocess, "run", fake_run)

    result = engine.render_report(scaffold["source"], formats=["html"])

    assert result["ok"] is True
    assert result["outputs"] == [str(output_dir / "index.html")]


def test_render_rejects_explicit_empty_format_list(
    isolated_reports: Path,
) -> None:
    scaffold = engine.scaffold_report(
        "empty-render",
        template="memo",
        formats=["html"],
    )

    result = engine.render_report(scaffold["source"], formats=[])

    assert result["ok"] is False
    assert "at least one format" in result["error"]


def test_explicit_empty_metrics_disable_modern_placeholder_strip(
    isolated_reports: Path,
) -> None:
    result = engine.scaffold_report(
        "modern-without-metrics",
        template="modern",
        formats=["html"],
        kpis=[],
    )

    assert result["ok"] is True
    source = Path(result["source"]).read_text()
    front_matter = yaml.safe_load(source.split("---", 2)[1])
    assert "kpis" not in front_matter


def test_venv_python_uses_active_virtual_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    active_python = tmp_path / "active-venv" / "bin" / "python"
    active_python.parent.mkdir(parents=True)
    active_python.write_text("")
    monkeypatch.delenv("REPORTFORGE_PYTHON", raising=False)
    monkeypatch.setattr(engine.sys, "executable", str(active_python))
    monkeypatch.setattr(engine.sys, "prefix", str(active_python.parents[1]))
    monkeypatch.setattr(engine.sys, "base_prefix", "/usr")

    assert engine._venv_python() == active_python


def test_scaffold_uses_kernel_selected_by_environment_probe(
    isolated_reports: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "python3")

    result = engine.scaffold_report(
        "kernel-fallback",
        template="memo",
        formats=["html"],
    )

    assert result["ok"] is True
    config = yaml.safe_load((Path(result["path"]) / "_quarto.yml").read_text())
    assert config["execute"]["jupyter"] == "python3"
    assert result["jupyter_kernel"] == "python3"


def _mpl_png(path: Path) -> None:
    from PIL import Image, PngImagePlugin

    info = PngImagePlugin.PngInfo()
    info.add_text("Software", "Matplotlib version3.11.1, https://matplotlib.org/")
    Image.new("RGB", (120, 60), "white").save(path, pnginfo=info)


def test_scaffold_engine_charts_only_records_flag(isolated_reports: Path) -> None:
    result = engine.scaffold_report(
        "flag-test", template="memo", formats=["html"], engine_charts_only=True
    )
    assert result["ok"] is True
    head = (Path(result["path"]) / "index.qmd").read_text().split("---")[1]
    assert "engine_charts_only: true" in head


def test_render_hard_fails_on_fallback_charts(isolated_reports: Path) -> None:
    result = engine.scaffold_report(
        "flag-fail", template="memo", formats=["html"], engine_charts_only=True
    )
    assert result["ok"] is True
    proj = Path(result["path"])
    (proj / "charts").mkdir()
    _mpl_png(proj / "charts" / "fallback.png")
    out = engine.render_report("flag-fail")
    assert out["ok"] is False
    assert "fallback.png" in out["error"]
    assert "engine_charts_only" in out["error"]


def test_render_gate_passes_without_flag(isolated_reports: Path) -> None:
    result = engine.scaffold_report("no-flag", template="memo", formats=["html"])
    assert result["ok"] is True
    proj = Path(result["path"])
    (proj / "charts").mkdir()
    _mpl_png(proj / "charts" / "fallback.png")
    assert engine._engine_charts_violation(proj) is None


def _white_png(path: Path) -> None:
    from PIL import Image

    Image.new("RGB", (120, 60), "white").save(path)


def _flag_project(tmp_root: Path, template: str) -> Path:
    result = engine.scaffold_report(
        f"flag-{template}", template=template, formats=["html"],
        engine_charts_only=True,
    )
    assert result["ok"] is True
    proj = Path(result["path"])
    (proj / "charts").mkdir()
    return proj


def test_render_hard_fails_on_white_paper_charts(isolated_reports: Path) -> None:
    proj = _flag_project(isolated_reports, "portfolio-light")
    _white_png(proj / "charts" / "white.png")
    out = engine.render_report(f"flag-portfolio-light")
    assert out["ok"] is False
    assert "white.png" in out["error"]


def test_white_paper_gate_skipped_on_dark_template(isolated_reports: Path) -> None:
    proj = _flag_project(isolated_reports, "portfolio-dark")
    _white_png(proj / "charts" / "white.png")
    assert engine._engine_charts_violation(proj) is None


def test_white_paper_gate_off_without_flag(isolated_reports: Path) -> None:
    result = engine.scaffold_report(
        "light-noflag", template="portfolio-light", formats=["html"]
    )
    assert result["ok"] is True
    proj = Path(result["path"])
    (proj / "charts").mkdir()
    _white_png(proj / "charts" / "white.png")
    assert engine._engine_charts_violation(proj) is None
