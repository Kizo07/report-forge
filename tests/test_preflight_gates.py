"""Phase 0 preflight gates: loud environment failures and the extended
toolchain stamp (robustness refactor plan 2026-09-12, Phase 0).

Covers:
- _toolchain_stamp() shape and manifest-blindness (state file + release
  record only — §1.3 invariant, also enforced by test_versions.py).
- Seeded-failure drill: quarto absent → loud render error (no traceback
  escape); poppler absent → loud preview error; kernel registration
  failing → scaffold degrades with a reported fallback kernel.
"""

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


TOOLCHAIN_KEYS = {"quarto", "python", "reportforge", "pandoc", "typst", "poppler", "chromium"}


def test_toolchain_stamp_keys_and_manifest_blindness(monkeypatch):
    monkeypatch.setattr(engine, "_quarto_version", lambda: "9.9.9-test")
    stamp = engine._toolchain_stamp()
    assert TOOLCHAIN_KEYS <= set(stamp)
    assert stamp["quarto"] == "9.9.9-test"
    assert stamp["python"].count(".") == 2
    assert stamp["reportforge"] == engine._REPORTFORGE_VERSION


def test_render_state_stamps_extended_toolchain(isolated_reports, monkeypatch):
    """The state file carries the extended toolchain block; the manifest
    never does (§1.3 — render writes artifacts, not the manifest)."""
    monkeypatch.setattr(engine, "_quarto_version", lambda: "9.9.9-test")
    engine.scaffold_report("stamp-memo", template="memo", formats=["html"])
    result = engine.render_report("stamp-memo", formats=["html"])
    assert result["ok"] is True, result
    state = json.loads(
        (isolated_reports / "stamp-memo" / ".reportforge-state.json").read_text(encoding="utf-8")
    )
    assert state["toolchain"]["quarto"] == "9.9.9-test"
    assert TOOLCHAIN_KEYS <= set(state["toolchain"])
    manifest_path = isolated_reports / "stamp-memo" / "report.json"
    assert "toolchain" not in json.loads(manifest_path.read_text(encoding="utf-8"))


def test_quarto_absent_fails_loudly(isolated_reports, monkeypatch):
    """Seeded drill: quarto off PATH → dict error, not a traceback escape."""
    engine.scaffold_report("no-quarto", template="memo", formats=["html"])
    real_which = engine.shutil.which
    monkeypatch.setattr(
        engine.shutil, "which",
        lambda name: None if name == "quarto" else real_which(name),
    )
    monkeypatch.setattr(engine, "_quarto_version", lambda: None)
    result = engine.render_report("no-quarto", formats=["html"])
    assert result["ok"] is False
    assert "quarto not found" in result["error"]


def test_poppler_absent_fails_loudly_in_previews(isolated_reports, monkeypatch):
    """Seeded drill: poppler off PATH → render_preview refuses with a clear
    error instead of degraded output."""
    engine.scaffold_report("no-poppler", template="memo", formats=["html"])
    real_which = engine.shutil.which
    monkeypatch.setattr(
        engine.shutil, "which",
        lambda name: None if name == "pdftoppm" else real_which(name),
    )
    result = engine.render_preview("no-poppler")
    assert result["ok"] is False
    assert "pdftoppm not found" in result["error"]


def test_kernel_fallback_reported_via_scaffold(tmp_path, monkeypatch):
    """Seeded drill: no usable venv interpreter → scaffold still succeeds
    but reports the degraded kernel instead of hiding the fallback.

    Uses the real _ensure_reportforge_kernel (no fixture stub): with no
    venv interpreter it must return 'python3' without invoking ipykernel.
    """
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(engine, "_venv_python", lambda: None)
    result = engine.scaffold_report("no-kernel", template="memo", formats=["html"])
    assert result["ok"] is True
    assert result["jupyter_kernel"] == "python3"


def test_subprocess_confined_to_renderer_package():
    """Phase 1 acceptance, enforced in-suite (milestone A review M5): the
    engine must not import subprocess — every external process call lives
    in reportforge.renderer."""
    import inspect

    assert not hasattr(engine, "subprocess")
    assert "import subprocess" not in inspect.getsource(engine)


def test_warn_only_probe_attached_when_tools_missing(isolated_reports, monkeypatch):
    """Milestone A review M2: the warn-only probe must surface missing
    tools as toolchain_warnings without failing the render."""
    stamp = engine._toolchain_stamp()
    stamp["poppler"] = None
    monkeypatch.setattr(engine, "_toolchain_stamp", lambda: stamp)
    engine.scaffold_report("probe-warn", template="memo", formats=["html"])
    result = engine.render_report("probe-warn", formats=["html"])
    assert result["ok"] is True
    assert result.get("toolchain_warnings")
    assert any("poppler" in w for w in result["toolchain_warnings"])


def test_no_probe_warnings_when_toolchain_complete(isolated_reports, monkeypatch):
    """Milestone A review M2: a healthy stamp must NOT add the key."""
    real_stamp = engine._toolchain_stamp
    def healthy_stamp() -> dict:
        stamp = real_stamp()
        stamp["poppler"] = "poppler 24.02 (test)"
        stamp["pandoc"] = "pandoc 3.1 (test)"
        return stamp
    monkeypatch.setattr(engine, "_toolchain_stamp", healthy_stamp)
    engine.scaffold_report("probe-clean", template="memo", formats=["html"])
    result = engine.render_report("probe-clean", formats=["html"])
    assert result["ok"] is True
    assert "toolchain_warnings" not in result


def test_cross_module_decorator_chain_intact():
    """Milestone C review finding 2: registry/release/cover functions are
    wrapped by sections._section_op_errors across the package split; the
    functools.wraps marker proves the decorator chain survived."""
    assert hasattr(engine.register_source, "__wrapped__")
    assert hasattr(engine.rollforward_report, "__wrapped__")
    assert hasattr(engine.derive_cover, "__wrapped__")
