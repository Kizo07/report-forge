"""Milestone C task C-2 — template + toolchain version stamps, schema 3."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from reportforge import templates as reportforge_templates
from reportforge import engine
from reportforge import manifest as M


def _expected_template_version() -> str:
    """Independent recomputation: derive from SPEC + DOMAIN_SLUGS (the
    declared mapping) rather than re-walking the tree, so a systematic
    error in content_hash's traversal cannot hide (milestone B review 5)."""
    assets = Path(reportforge_templates.__file__).parent / "_assets"
    rels = list(reportforge_templates.SPEC.values())
    rels += [f"domains/{slug}.qmd" for slug in reportforge_templates.DOMAIN_SLUGS.values()]
    h = hashlib.sha256()
    for rel in sorted(rels):
        h.update(rel.encode())
        h.update(b"\x00")
        h.update((assets / rel).read_bytes())
        h.update(b"\x00")
    return h.hexdigest()[:12]


def test_scaffold_records_template_version(tmp_path, monkeypatch):
    """C-2: manifest carries the content hash of the template sources."""
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    res = engine.scaffold_report("ver-probe", template="standard",
                                 formats=["html"])
    assert res["ok"] is True
    m = json.loads((tmp_path / "reports" / "ver-probe" / "report.json").read_text())
    assert m["schema_version"] == 5
    assert m["template_version"] == _expected_template_version()


def test_render_stamps_toolchain_in_state(tmp_path, monkeypatch):
    """C-2: toolchain (quarto/python/reportforge) lands in the state file,
    never the manifest."""
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    res = engine.scaffold_report("ver-render", template="memo", formats=["html"])
    assert res["ok"] is True
    project = Path(res["path"])

    def fake_run(command, **kwargs):
        if command[0] != "quarto":  # toolchain-stamp probes: tag the program
            return subprocess.CompletedProcess(command, 0, f"{command[0]} probe\n", "")
        if command[:2] == ["quarto", "--version"]:
            return subprocess.CompletedProcess(command, 0, "1.7.0\n", "")
        out = project / "output" / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("<html></html>")
        return subprocess.CompletedProcess(command, 0, "rendered", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    out = engine.render_report(str(project), formats=["html"])
    assert out["ok"] is True
    state = json.loads((project / ".reportforge-state.json").read_text())
    assert state["toolchain"]["quarto"] == "1.7.0"
    assert state["toolchain"]["python"].split(".")[0] >= "3"
    from reportforge import __version__ as expected_version
    assert state["toolchain"]["reportforge"] == expected_version
    m = json.loads((project / "report.json").read_text())
    assert "toolchain" not in m  # §1.3: render writes artifacts, not the manifest


def test_schema2_migrates_and_stamps_4(tmp_path):
    """C-2 R1-F5 + C-5: a schema-2 manifest migrates with template_version
    pre-c AND supersedes {}, and the save persists schema 4."""
    root = tmp_path / "mig"
    root.mkdir()
    (root / "index.qmd").write_text("---\ntitle: T\n---\n\n# T\n")
    M.create(str(root), title="T")
    raw = json.loads((root / "report.json").read_text())
    raw["schema_version"] = 2
    del raw["template_version"]
    del raw["supersedes"]
    (root / "report.json").write_text(json.dumps(raw))
    m = M.load(str(root))
    assert m.schema_version == 5
    assert m.template_version == "pre-c"
    assert m.supersedes == {}
    M.save(m, str(root))
    raw2 = json.loads((root / "report.json").read_text())
    assert raw2["schema_version"] == 5  # migration sticks


def test_schema6_rejected_loudly(tmp_path):
    root = tmp_path / "v4"
    root.mkdir()
    (root / "index.qmd").write_text("---\ntitle: T\n---\n\n# T\n")
    M.create(str(root), title="T")
    raw = json.loads((root / "report.json").read_text())
    raw["schema_version"] = 6
    (root / "report.json").write_text(json.dumps(raw))
    with pytest.raises(M.ManifestError):
        M.load(str(root))
