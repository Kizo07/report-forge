"""Milestone C task C-4 — release snapshot: one frozen input set."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from reportforge import engine


def _scaffold(monkeypatch, tmp_path: Path, slug: str = "rel-probe"):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    res = engine.scaffold_report(slug, template="standard", formats=["html", "pdf"])
    assert res["ok"] is True, res
    return Path(res["path"])


def _fake_run_factory(project: Path):
    def fake_run(command, **kwargs):
        if not command or command[0] != "quarto":
            # e.g. the ipykernel install probe at scaffold: fail fast so
            # the caller falls back (never hang the suite on real installs).
            return subprocess.CompletedProcess(command, 1, "", "")
        if command[:2] == ["quarto", "--version"]:
            return subprocess.CompletedProcess(command, 0, "1.7.0\n", "")
        fmt = command[command.index("--to") + 1]
        ext = "pdf" if fmt == "typst" else fmt
        out = project / "output" / f"index.{ext}"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"%s-bytes" % ext.encode())
        return subprocess.CompletedProcess(command, 0, "rendered", "")
    return fake_run


def _release(project: Path) -> dict:
    return json.loads((project / "output" / "release.json").read_text())


def test_separate_renders_share_one_release_id(tmp_path, monkeypatch):
    """C-4: html then pdf in separate calls seal the SAME snapshot."""
    project = _scaffold(monkeypatch, tmp_path)
    monkeypatch.setattr(engine.subprocess, "run", _fake_run_factory(project))
    assert engine.render_report(str(project), formats=["html"])["ok"] is True
    first = _release(project)
    assert engine.render_report(str(project), formats=["pdf"])["ok"] is True
    second = _release(project)
    assert second["release_id"] == first["release_id"]
    assert len(second["release_id"]) == 12
    assert set(second["artifacts"]) == {"html", "pdf"}
    assert second["artifacts"]["pdf"]["bytes"] == len(b"pdf-bytes")


def test_qmd_change_between_renders_fails_loudly(tmp_path, monkeypatch):
    """C-4: a changed index.qmd between format renders refuses to mix."""
    project = _scaffold(monkeypatch, tmp_path)
    monkeypatch.setattr(engine.subprocess, "run", _fake_run_factory(project))
    assert engine.render_report(str(project), formats=["html"])["ok"] is True
    qmd = project / "index.qmd"
    qmd.write_text(qmd.read_text() + "\n<!-- late edit -->\n")
    res = engine.render_report(str(project), formats=["pdf"])
    assert res["ok"] is False
    assert "snapshot" in res["error"] or "re-render" in res["error"]


def test_rerender_same_format_reseals(tmp_path, monkeypatch):
    project = _scaffold(monkeypatch, tmp_path)
    monkeypatch.setattr(engine.subprocess, "run", _fake_run_factory(project))
    assert engine.render_report(str(project), formats=["html"])["ok"] is True
    first = _release(project)
    assert engine.render_report(str(project), formats=["html"])["ok"] is True
    second = _release(project)
    assert second["release_id"] == first["release_id"]
    assert set(second["artifacts"]) == {"html"}


def test_freeze_release_verifies_and_detects_drift(tmp_path, monkeypatch):
    project = _scaffold(monkeypatch, tmp_path)
    monkeypatch.setattr(engine.subprocess, "run", _fake_run_factory(project))
    engine.render_report(str(project), formats=["html", "pdf"])
    frozen = engine.freeze_release("rel-probe")
    assert frozen["ok"] is True and frozen["verified"] is True
    (project / "index.qmd").write_text(
        (project / "index.qmd").read_text() + "\n<!-- drift -->\n")
    stale = engine.freeze_release("rel-probe")
    assert stale["ok"] is False
    assert "drift" in stale["error"] or "changed" in stale["error"]


def _approve(project: Path) -> None:
    """Force approved state (test setup, bypasses transitions)."""
    mpath = project / "report.json"
    m = json.loads(mpath.read_text())
    m["state"] = "approved"
    mpath.write_text(json.dumps(m))


def test_export_embeds_release_and_warns_when_absent(tmp_path, monkeypatch):
    """C-4: bundles carry release.json; pre-C reports warn, not fail."""
    project = _scaffold(monkeypatch, tmp_path, slug="rel-export")
    monkeypatch.setattr(engine.subprocess, "run", _fake_run_factory(project))
    engine.render_report(str(project), formats=["html", "pdf"])
    _approve(project)
    dest = tmp_path / "bundles"
    res = engine.export_release("rel-export", dest=str(dest))
    assert res["ok"] is True, res
    bundle = dest / "rel-export" / f"r{res['revision']}" / "release.json"
    assert bundle.is_file()

    # Pre-C: hand-rolled outputs, no release.json → warning, still exports.
    project2 = _scaffold(monkeypatch, tmp_path, slug="rel-legacy")
    out = project2 / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_bytes(b"legacy")
    (out / "index.pdf").write_bytes(b"legacy")
    _approve(project2)
    res2 = engine.export_release("rel-legacy", dest=str(dest))
    assert res2["ok"] is True, res2
    assert any("release snapshot" in w for w in res2.get("warnings", []))
