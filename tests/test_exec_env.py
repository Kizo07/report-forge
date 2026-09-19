"""Tests for the exec_env cluster: chrome-safe tmp defaults and PNG theme lines.

Covers the NVDA flagship (2026-09-19) findings:
- run_code/run_file children must not inherit a socket-unsafe TMPDIR
  (deer-flow pins ~150-char thread tmp into MCP envs; Chrome unix
  sockets cap at 108 chars -> kaleido BrowserFailedError).
- run_code results report created-PNG theme lines (corner + paper stamp)
  so a dark batch fails fast after the first export call instead of
  burning a full 18-chart batch.
"""

from __future__ import annotations

import os
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


LONG_TMP = "/tmp/" + "t" * 130 + "/.mcp/tmp"


class TestShortTmpExecEnv:
    def test_run_code_child_gets_short_tmpdir(
        self, isolated_reports: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Simulate the deer-flow MCP spawn env: very long TMPDIR must not
        reach run_code children (Chrome sockets cannot live under it)."""
        monkeypatch.setenv("TMPDIR", LONG_TMP)
        monkeypatch.setenv("TEMP", LONG_TMP)
        monkeypatch.setenv("TMP", LONG_TMP)
        engine.scaffold_report("exec-tmp", template="memo", formats=["html"])
        result = engine.run_code(
            "import os\nprint(os.environ['TMPDIR'])\nprint(os.environ['TEMP'])\nprint(os.environ['TMP'])",
            project="exec-tmp",
        )
        assert result["ok"] is True
        lines = result["stdout_tail"].strip().splitlines()
        assert len(lines) == 3
        for line in lines:
            assert len(line) < 60, f"child tmp still socket-unsafe: {line}"
            assert Path(line).is_dir()

    def test_run_code_preserves_rest_of_env(
        self, isolated_reports: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TMPDIR", LONG_TMP)
        monkeypatch.setenv("REPORTFORGE_PROBE_VAR", "probe-value")
        engine.scaffold_report("exec-env", template="memo", formats=["html"])
        result = engine.run_code(
            "import os\nprint(os.environ.get('REPORTFORGE_PROBE_VAR'))\nprint(os.environ.get('PATH') is not None)",
            project="exec-env",
        )
        assert result["ok"] is True
        assert "probe-value" in result["stdout_tail"]
        assert "True" in result["stdout_tail"]

    def test_save_chart_export_sees_short_tmp(
        self, isolated_reports: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In-process kaleido export (save_chart) must run under the short
        tmp even when the server process inherited a long TMPDIR. No real
        Chrome needed: stub write_image and observe tempfile.gettempdir()."""
        import tempfile

        import plotly.graph_objects as go

        monkeypatch.setenv("TMPDIR", LONG_TMP)
        monkeypatch.setattr(tempfile, "tempdir", LONG_TMP)
        seen: dict[str, str] = {}

        def fake_write_image(self, path, **kwargs):
            seen["tmpdir"] = tempfile.gettempdir()
            Path(path).write_bytes(b"fake-png")

        monkeypatch.setattr(go.Figure, "write_image", fake_write_image)
        monkeypatch.setattr(
            go.Figure,
            "write_html",
            lambda self, path, **kwargs: Path(path).write_text("<html></html>"),
        )

        engine.scaffold_report("exec-chart", template="memo", formats=["html"])
        fig = go.Figure(data=[go.Bar(y=[1, 2, 3])])
        result = engine.save_chart(
            fig.to_json(), "charts/probe.png", project="exec-chart"
        )
        assert result["ok"] is True, result.get("error")
        assert len(seen["tmpdir"]) < 60, f"export tmp still socket-unsafe: {seen['tmpdir']}"
        # Process env must be restored after the export.
        assert os.environ["TMPDIR"] == LONG_TMP
        assert tempfile.tempdir == LONG_TMP

    def test_save_chart_real_export_under_long_tmpdir(
        self, isolated_reports: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """True regression: real kaleido export with a socket-unsafe TMPDIR
        (NVDA flagship BrowserFailedError). Slow (~15s, needs Chrome) but it
        is the exact failure; the stub test above pins the contract fast."""
        import tempfile

        import plotly.graph_objects as go

        long_tmp = tmp_path / ("p" * 140)
        long_tmp.mkdir()
        monkeypatch.setenv("TMPDIR", str(long_tmp))
        monkeypatch.setenv("TEMP", str(long_tmp))
        monkeypatch.setenv("TMP", str(long_tmp))
        monkeypatch.setattr(tempfile, "tempdir", str(long_tmp))

        engine.scaffold_report("exec-chrome", template="memo", formats=["html"])
        fig = go.Figure(data=[go.Bar(y=[1, 2, 3])])
        result = engine.save_chart(fig.to_json(), "charts/chrome.png", project="exec-chrome")
        assert result["ok"] is True, result.get("error")
        assert Path(result["png"]).is_file()


class TestCreatedPngThemeLines:
    def test_run_code_reports_created_png_theme(self, isolated_reports: Path) -> None:
        from PIL import Image
        from PIL.PngImagePlugin import PngInfo

        engine.scaffold_report("exec-theme", template="memo", formats=["html"])
        result = engine.run_code(
            "from pathlib import Path\n"
            "from PIL import Image\n"
            "from PIL.PngImagePlugin import PngInfo\n"
            "Path('charts').mkdir(exist_ok=True)\n"
            "img = Image.new('RGB', (64, 64), '#e5ddcc')\n"
            "meta = PngInfo()\n"
            "meta.add_text('QuantFlow-Paper', '#e5ddcc')\n"
            "img.save('charts/ex01.png', pnginfo=meta)\n"
            "print('wrote png')",
            project="exec-theme",
        )
        assert result["ok"] is True, result.get("stderr_tail")
        assert "charts/ex01.png" in result["created"]
        assert "png_theme" in result
        assert result["png_theme"] == [
            {"path": "charts/ex01.png", "corner": "#e5ddcc", "paper_stamp": "#e5ddcc"}
        ]

    def test_run_code_png_theme_absent_without_pngs(self, isolated_reports: Path) -> None:
        engine.scaffold_report("exec-notheme", template="memo", formats=["html"])
        result = engine.run_code(
            "from pathlib import Path\nPath('notes.txt').write_text('no pngs here')\nprint('ok')",
            project="exec-notheme",
        )
        assert result["ok"] is True
        assert "png_theme" not in result

    def test_run_code_png_theme_best_effort_on_unreadable_png(
        self, isolated_reports: Path
    ) -> None:
        engine.scaffold_report("exec-badpng", template="memo", formats=["html"])
        result = engine.run_code(
            "from pathlib import Path\nPath('charts').mkdir(exist_ok=True)\nPath('charts/broken.png').write_bytes(b'not a png')\nprint('ok')",
            project="exec-badpng",
        )
        assert result["ok"] is True
        assert result.get("png_theme", []) == []
