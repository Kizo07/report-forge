"""Tests for the native-flexibility surface (plan 2026-09-01-reportforge-native-flexibility).

Covers WS-1 (run_code/run_file), WS-2 (save_asset), WS-3 (project_status /
read_project_file / render-log persistence), WS-4 (append_section + bespoke
template), and WS-5 (pdf-web).
"""

from __future__ import annotations

import asyncio
import base64
import subprocess
from pathlib import Path

import pytest
import yaml

from reportforge import engine
from reportforge.mcp_server import mcp


@pytest.fixture
def isolated_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    monkeypatch.setattr(engine, "REPORTS_DIR", reports)
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "reportforge")
    monkeypatch.setattr(engine, "_default_reference_docx", lambda: None)
    return reports


# --- WS-4: bespoke template -------------------------------------------------


def test_bespoke_scaffold_uses_caller_frontmatter_and_body(isolated_reports: Path) -> None:
    result = engine.scaffold_report(
        "bespoke-basic",
        template="bespoke",
        formats=["html", "pdf-web"],
        frontmatter_yaml='title: "My Custom Report"\nformat:\n  html:\n    theme: darkly',
        body="# Opening\n\nSome prose.",
    )
    assert result["ok"] is True
    assert result["template"] == "bespoke"
    assert result["formats"] == ["html", "pdf-web"]
    qmd = (Path(result["path"]) / "index.qmd").read_text()
    assert qmd.startswith('---\ntitle: "My Custom Report"')
    assert "# Opening" in qmd

    # pdf-web requested => html block gets embed-resources for self-contained print input.
    yml_text = (Path(result["path"]) / "_quarto.yml").read_text()
    assert "embed-resources: true" in yml_text
    # docx/pdf were not requested -> dropped from the project config.
    assert "docx:" not in yml_text
    assert "typst:" not in yml_text


def test_bespoke_scaffold_placeholder_when_no_content(isolated_reports: Path) -> None:
    result = engine.scaffold_report("bespoke-empty", template="bespoke", formats=["html"])
    assert result["ok"] is True
    qmd = (Path(result["path"]) / "index.qmd").read_text()
    assert "Untitled" in qmd


def test_bespoke_scaffold_rejects_invalid_frontmatter_yaml(isolated_reports: Path) -> None:
    result = engine.scaffold_report(
        "bespoke-bad-yaml",
        template="bespoke",
        formats=["html"],
        frontmatter_yaml="title: [unclosed",
    )
    assert result["ok"] is False
    assert "YAML" in result["error"]
    # failed scaffold must not leave a partial project behind
    assert not (isolated_reports / "bespoke-bad-yaml").exists()


def test_bespoke_scaffold_rejects_non_mapping_frontmatter(isolated_reports: Path) -> None:
    result = engine.scaffold_report(
        "bespoke-list",
        template="bespoke",
        formats=["html"],
        frontmatter_yaml="- a\n- b",
    )
    assert result["ok"] is False
    assert "mapping" in result["error"]


# --- WS-4: append_section ----------------------------------------------------


def test_append_section_appends_and_preserves_frontmatter(isolated_reports: Path) -> None:
    scaffold = engine.scaffold_report("append-me", template="memo", formats=["html"])
    qmd_path = Path(scaffold["source"])
    original_fm = qmd_path.read_text().split("---")[1]

    result = engine.append_section("append-me", "## New Section\n\nBody text.")
    assert result["ok"] is True
    text = qmd_path.read_text()
    assert text.split("---")[1] == original_fm  # frontmatter untouched
    assert text.rstrip().endswith("Body text.")


def test_append_section_inserts_before_matching_heading(isolated_reports: Path) -> None:
    scaffold = engine.scaffold_report(
        "append-before",
        template="bespoke",
        formats=["html"],
        frontmatter_yaml='title: "T"',
        body="# First\n\none\n\n# Second\n\ntwo\n",
    )
    assert scaffold["ok"] is True

    result = engine.append_section("append-before", "## Inserted\n\nmid", before="Second")
    assert result["ok"] is True
    assert "inserted before heading" in result["action"]
    text = (Path(scaffold["path"]) / "index.qmd").read_text()
    assert text.index("## Inserted") < text.index("# Second")
    assert text.index("## Inserted") > text.index("# First")


def test_append_section_no_matching_heading(isolated_reports: Path) -> None:
    scaffold = engine.scaffold_report("append-nomatch", template="memo", formats=["html"])
    result = engine.append_section("append-nomatch", "x", before="Nonexistent Heading")
    assert result["ok"] is False
    assert "no heading matching" in result["error"]


def test_append_section_unknown_project(isolated_reports: Path) -> None:
    result = engine.append_section("ghost-project", "x")
    assert result["ok"] is False


# --- WS-2: save_asset ----------------------------------------------------------


def test_save_asset_text_and_binary(isolated_reports: Path) -> None:
    scaffold = engine.scaffold_report("asset-proj", template="memo", formats=["html"])
    root = Path(scaffold["path"])

    text_result = engine.save_asset("asset-proj", "assets/data.csv", content_text="a,b\n1,2\n")
    assert text_result["ok"] is True
    assert (root / "assets" / "data.csv").read_text() == "a,b\n1,2\n"
    assert text_result["bytes"] == len("a,b\n1,2\n")

    payload = b"\x89PNG\r\n\x1a\nfake"
    b64_result = engine.save_asset(
        "asset-proj", "figures/chart.png", content_b64=base64.b64encode(payload).decode()
    )
    assert b64_result["ok"] is True
    assert (root / "figures" / "chart.png").read_bytes() == payload


def test_save_asset_requires_exactly_one_content(isolated_reports: Path) -> None:
    engine.scaffold_report("asset-xor", template="memo", formats=["html"])
    both = engine.save_asset("asset-xor", "a.txt", content_text="x", content_b64="eA==")
    neither = engine.save_asset("asset-xor", "a.txt")
    assert both["ok"] is False
    assert neither["ok"] is False


def test_save_asset_rejects_path_escape(isolated_reports: Path) -> None:
    engine.scaffold_report("asset-escape", template="memo", formats=["html"])
    result = engine.save_asset("asset-escape", "../evil.txt", content_text="nope")
    assert result["ok"] is False
    assert "error" in result
    assert not (isolated_reports / "evil.txt").exists()


def test_save_asset_rejects_invalid_base64(isolated_reports: Path) -> None:
    engine.scaffold_report("asset-b64", template="memo", formats=["html"])
    result = engine.save_asset("asset-b64", "x.bin", content_b64="!!!not-base64!!!")
    assert result["ok"] is False
    assert "base64" in result["error"]


# --- WS-1: run_code / run_file --------------------------------------------------


def test_run_code_captures_stdout_and_file_diff(isolated_reports: Path) -> None:
    engine.scaffold_report("exec-proj", template="memo", formats=["html"])
    result = engine.run_code(
        "from pathlib import Path\n"
        "Path('generated.txt').write_text('hello from run_code')\n"
        "print('computed:', 6 * 7)",
        project="exec-proj",
    )
    assert result["ok"] is True
    assert result["exit_code"] == 0
    assert "computed: 42" in result["stdout_tail"]
    assert "generated.txt" in result["created"]
    # cwd was pinned to the project root
    root = isolated_reports / "exec-proj"
    assert (root / "generated.txt").read_text() == "hello from run_code"


def test_run_code_reports_failure_exit_code(isolated_reports: Path) -> None:
    engine.scaffold_report("exec-fail", template="memo", formats=["html"])
    result = engine.run_code("import sys\nprint('boom', file=sys.stderr)\nsys.exit(3)", project="exec-fail")
    assert result["ok"] is False
    assert result["exit_code"] == 3
    assert "boom" in result["stderr_tail"]


def test_run_code_disabled_via_env(isolated_reports: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine.scaffold_report("exec-off", template="memo", formats=["html"])
    monkeypatch.setenv("REPORTFORGE_EXEC", "off")
    result = engine.run_code("print(1)", project="exec-off")
    assert result["ok"] is False
    assert "disabled" in result["error"]


def test_run_code_requires_project_unless_optional(isolated_reports: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = engine.run_code("print(1)")
    assert result["ok"] is False
    assert "project is required" in result["error"]

    monkeypatch.setenv("REPORTFORGE_PROJECT_OPTIONAL", "1")
    result = engine.run_code("print(2)")
    assert result["ok"] is True
    assert "2" in result["stdout_tail"]


def test_run_code_timeout(isolated_reports: Path) -> None:
    engine.scaffold_report("exec-slow", template="memo", formats=["html"])
    result = engine.run_code("import time\ntime.sleep(10)", project="exec-slow", timeout=1)
    assert result["ok"] is False
    assert "timed out" in result["error"]


def test_run_code_quant_stack_available(isolated_reports: Path) -> None:
    """WS-6: the execution interpreter must carry the quant stack."""
    engine.scaffold_report("exec-quant", template="memo", formats=["html"])
    result = engine.run_code(
        "import pandas, numpy, statsmodels\n"
        "import pyarrow\n"
        "print('quant-ok', pandas.__version__, numpy.__version__, statsmodels.__version__)",
        project="exec-quant",
    )
    assert result["ok"] is True, result.get("stderr_tail")
    assert "quant-ok" in result["stdout_tail"]


def test_run_file_dispatches_python_and_shell(isolated_reports: Path) -> None:
    scaffold = engine.scaffold_report("runfile-proj", template="memo", formats=["html"])
    root = Path(scaffold["path"])
    (root / "script.py").write_text("print('py-script-ok')\n")
    (root / "script.sh").write_text("echo shell-script-ok\n")

    py_result = engine.run_file("script.py", "runfile-proj")
    assert py_result["ok"] is True
    assert "py-script-ok" in py_result["stdout_tail"]

    sh_result = engine.run_file("script.sh", "runfile-proj")
    assert sh_result["ok"] is True
    assert "shell-script-ok" in sh_result["stdout_tail"]


def test_run_file_rejects_escape_and_unknown(isolated_reports: Path) -> None:
    engine.scaffold_report("runfile-guard", template="memo", formats=["html"])
    escape = engine.run_file("../../etc/passwd", "runfile-guard")
    assert escape["ok"] is False
    assert "escapes" in escape["error"]

    missing = engine.run_file("nope.py", "runfile-guard")
    assert missing["ok"] is False

    bad_ext = engine.run_file("script.py", "runfile-guard")
    assert bad_ext["ok"] is False  # script.py does not exist -> not found error


def test_run_file_args_passed_through(isolated_reports: Path) -> None:
    scaffold = engine.scaffold_report("runfile-args", template="memo", formats=["html"])
    root = Path(scaffold["path"])
    (root / "show.py").write_text("import sys\nprint('args:', sys.argv[1:])\n")
    result = engine.run_file("show.py", "runfile-args", args=["one", "two"])
    assert result["ok"] is True
    assert "['one', 'two']" in result["stdout_tail"]


# --- WS-3: project_status / read_project_file / render logs --------------------


def test_project_status_reports_files_formats_and_state(
    isolated_reports: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scaffold = engine.scaffold_report("status-proj", template="memo", formats=["html"])
    project = Path(scaffold["path"])

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        out = project / "output" / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("<html>ok</html>")
        return subprocess.CompletedProcess(command, 0, "rendered", "")

    monkeypatch.setattr(engine.subprocess, "run", fake_run)
    rendered = engine.render_report(scaffold["source"], formats=["html"])
    assert rendered["ok"] is True

    status = engine.project_status("status-proj")
    assert status["ok"] is True
    relpaths = {f["relpath"] for f in status["files"]}
    assert "index.qmd" in relpaths
    assert "output/index.html" in relpaths
    assert status["configured_formats"] == ["html"]
    assert status["last_render"] is not None
    assert status["last_render"]["formats"] == ["html"]
    assert status["render_logs"] == [".render-log-html.txt"]


def test_render_persists_full_log_on_failure(
    isolated_reports: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scaffold = engine.scaffold_report("faillog-proj", template="memo", formats=["html"])
    project = Path(scaffold["path"])

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, "", "FATAL: kernel exploded")

    monkeypatch.setattr(engine.subprocess, "run", fake_run)
    result = engine.render_report(scaffold["source"], formats=["html"])
    assert result["ok"] is False
    assert "render_log" in result

    log_path = project / "output" / ".render-log-html.txt"
    assert log_path.is_file()
    assert "kernel exploded" in log_path.read_text()

    # read_project_file can fetch the failure log for diagnosis
    read = engine.read_project_file("faillog-proj", "output/.render-log-html.txt")
    assert read["ok"] is True
    assert "kernel exploded" in read["content"]


def test_read_project_file_binary_and_escape(isolated_reports: Path) -> None:
    scaffold = engine.scaffold_report("read-proj", template="memo", formats=["html"])
    root = Path(scaffold["path"])
    (root / "blob.bin").write_bytes(b"\x00\x01\x02binary")

    binary = engine.read_project_file("read-proj", "blob.bin")
    assert binary["ok"] is True
    assert binary["binary"] is True
    assert "content" not in binary

    escape = engine.read_project_file("read-proj", "../secret.txt")
    assert escape["ok"] is False

    missing = engine.read_project_file("read-proj", "does-not-exist.md")
    assert missing["ok"] is False


def test_read_project_file_truncates_long_content(isolated_reports: Path) -> None:
    scaffold = engine.scaffold_report("read-long", template="memo", formats=["html"])
    root = Path(scaffold["path"])
    (root / "big.txt").write_text("x" * 1000)

    result = engine.read_project_file("read-long", "big.txt", max_bytes=100)
    assert result["ok"] is True
    assert result["truncated"] is True
    assert len(result["content"]) == 100


# --- WS-5: pdf-web ---------------------------------------------------------------


def test_render_pdf_web_prints_html_via_chromium(
    isolated_reports: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scaffold = engine.scaffold_report("pdfweb-proj", template="memo", formats=["html"])
    project = Path(scaffold["path"])

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if command and command[0] == "quarto":
            out = project / "output" / "index.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("<html>page</html>")
            return subprocess.CompletedProcess(command, 0, "rendered", "")
        # chromium invocation: find --print-to-pdf=<path> and create the file
        pdf_target = next(a.split("=", 1)[1] for a in command if a.startswith("--print-to-pdf="))
        Path(pdf_target).write_bytes(b"%PDF-1.4 fake")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(engine.subprocess, "run", fake_run)
    monkeypatch.setattr(engine, "_chromium_binary", lambda: "/fake/chromium")

    result = engine.render_report(scaffold["source"], formats=["pdf-web"])
    assert result["ok"] is True
    # pdf-web alone still produces the html render plus the printed pdf
    names = sorted(Path(p).name for p in result["outputs"])
    assert names == ["index.html", "index.pdf"]
    assert "pdf_web_note" in result


def test_render_pdf_web_without_chromium_fails_cleanly(
    isolated_reports: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scaffold = engine.scaffold_report("pdfweb-nochrome", template="memo", formats=["html"])
    project = Path(scaffold["path"])

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        out = project / "output" / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("<html>page</html>")
        return subprocess.CompletedProcess(command, 0, "rendered", "")

    monkeypatch.setattr(engine.subprocess, "run", fake_run)
    monkeypatch.setattr(engine, "_chromium_binary", lambda: None)

    result = engine.render_report(scaffold["source"], formats=["pdf-web"])
    assert result["ok"] is False
    assert "Chromium" in result["error"]
    # the html render already produced is still reported
    assert result["outputs"] == [str(project / "output" / "index.html")]


def test_pdf_web_suffix_when_typst_pdf_exists(
    isolated_reports: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scaffold = engine.scaffold_report("pdfweb-coexist", template="memo", formats=["html", "pdf"])
    project = Path(scaffold["path"])

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if command and command[0] == "quarto":
            fmt = command[-1]
            ext = "pdf" if fmt in ("pdf", "typst") else fmt
            out = project / "output" / f"index.{ext}"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"%PDF quarto")
            return subprocess.CompletedProcess(command, 0, "rendered", "")
        pdf_target = next(a.split("=", 1)[1] for a in command if a.startswith("--print-to-pdf="))
        Path(pdf_target).write_bytes(b"%PDF chromium")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(engine.subprocess, "run", fake_run)
    monkeypatch.setattr(engine, "_chromium_binary", lambda: "/fake/chromium")

    result = engine.render_report(scaffold["source"], formats=["html", "pdf", "pdf-web"])
    assert result["ok"] is True
    names = sorted(Path(p).name for p in result["outputs"])
    # typst pdf keeps index.pdf; the web print gets -web suffix
    assert names == ["index-web.pdf", "index.html", "index.pdf"]


# --- MCP schema boundary -----------------------------------------------------------


def _tool(name: str):
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    return tools[name]


def test_new_tools_registered() -> None:
    tools = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {
        "reportforge_run_code",
        "reportforge_run_file",
        "reportforge_save_asset",
        "reportforge_project_status",
        "reportforge_read_project_file",
        "reportforge_append_section",
    } <= tools


def test_scaffold_schema_exposes_bespoke_params() -> None:
    properties = _tool("reportforge_scaffold_report").parameters["properties"]
    assert {"frontmatter_yaml", "body"} <= set(properties)


def test_run_file_args_accepts_string_at_schema_boundary() -> None:
    properties = _tool("reportforge_run_file").parameters["properties"]
    prop = properties["args"]
    types = {prop.get("type")}
    for variant in prop.get("anyOf", []):
        types.add(variant.get("type"))
    assert "string" in types


def test_list_templates_includes_bespoke_and_pdf_web() -> None:
    specs = {t["name"]: t for t in engine.list_templates()}
    assert "bespoke" in specs
    assert "pdf-web" in specs["bespoke"]["formats"]
    assert specs["bespoke"]["content_neutral"] is True
