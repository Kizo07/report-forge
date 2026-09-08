"""Milestone C task C-2 — template + toolchain version stamps, schema 3."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from reportforge import engine
from reportforge import manifest as M


def _expected_template_version() -> str:
    h = hashlib.sha256()
    for name in ("templates.py", "templates_domain.py"):
        h.update((Path(engine.__file__).parent / name).read_bytes())
    return h.hexdigest()[:12]


def test_scaffold_records_template_version(tmp_path, monkeypatch):
    """C-2: manifest carries the content hash of the template sources."""
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    res = engine.scaffold_report("ver-probe", template="standard",
                                 formats=["html"])
    assert res["ok"] is True
    m = json.loads((tmp_path / "reports" / "ver-probe" / "report.json").read_text())
    assert m["schema_version"] == 3
    assert m["template_version"] == _expected_template_version()


def test_render_stamps_toolchain_in_state(tmp_path, monkeypatch):
    """C-2: toolchain (quarto/python/reportforge) lands in the state file,
    never the manifest."""
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    res = engine.scaffold_report("ver-render", template="memo", formats=["html"])
    assert res["ok"] is True
    project = Path(res["path"])

    def fake_run(command, **kwargs):
        if command[:2] == ["quarto", "--version"]:
            return subprocess.CompletedProcess(command, 0, "1.7.0\n", "")
        out = project / "output" / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("<html></html>")
        return subprocess.CompletedProcess(command, 0, "rendered", "")

    monkeypatch.setattr(engine.subprocess, "run", fake_run)
    out = engine.render_report(str(project), formats=["html"])
    assert out["ok"] is True
    state = json.loads((project / ".reportforge-state.json").read_text())
    assert state["toolchain"]["quarto"] == "1.7.0"
    assert state["toolchain"]["python"].split(".")[0] >= "3"
    assert state["toolchain"]["reportforge"] == "0.1.0"
    m = json.loads((project / "report.json").read_text())
    assert "toolchain" not in m  # §1.3: render writes artifacts, not the manifest


def test_schema2_migrates_and_stamps_3(tmp_path):
    """C-2 R1-F5: a schema-2 manifest migrates with template_version
    pre-c AND the save persists schema 3 (no silent stick at 2)."""
    root = tmp_path / "mig"
    root.mkdir()
    (root / "index.qmd").write_text("---\ntitle: T\n---\n\n# T\n")
    M.create(str(root), title="T")
    raw = json.loads((root / "report.json").read_text())
    raw["schema_version"] = 2
    del raw["template_version"]
    (root / "report.json").write_text(json.dumps(raw))
    m = M.load(str(root))
    assert m.schema_version == 3
    assert m.template_version == "pre-c"
    M.save(m, str(root))
    raw2 = json.loads((root / "report.json").read_text())
    assert raw2["schema_version"] == 3  # migration sticks


def test_schema4_rejected_loudly(tmp_path):
    root = tmp_path / "v4"
    root.mkdir()
    (root / "index.qmd").write_text("---\ntitle: T\n---\n\n# T\n")
    M.create(str(root), title="T")
    raw = json.loads((root / "report.json").read_text())
    raw["schema_version"] = 4
    (root / "report.json").write_text(json.dumps(raw))
    with pytest.raises(M.ManifestError):
        M.load(str(root))
