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
