"""Milestone C task C-5 — rollforward: next-period reports with a
changed-facts account."""

from __future__ import annotations

import json
from pathlib import Path

from reportforge import engine
from reportforge import manifest as M

SRC = {"key": "src-fed-sep-2026-dots", "kind": "report",
       "title": "Fed dots", "date": "2026-09-17"}


def _source_with_evidence(monkeypatch, tmp_path: Path, slug: str = "rf-q2"):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    res = engine.scaffold_report(slug, template="earnings-recap",
                                 formats=["html"])
    assert res["ok"] is True, res
    root = Path(res["path"])
    assert engine.register_source(slug, **SRC)["ok"] is True
    assert engine.register_fact(
        slug, "fact-revenue", 100.0, unit="USDm", kind="observed",
        source_keys=[SRC["key"]], as_of="2026-07-30")["ok"] is True
    assert engine.register_fact(
        slug, "fact-guidance", "raise", kind="estimated",
        as_of="2026-07-30")["ok"] is True
    (root / "figures").mkdir(exist_ok=True)
    (root / "figures" / "rev.png").write_bytes(b"fake-png")
    assert engine.register_exhibit(
        slug, exhibit_id="fig-rev", title="Revenue",
        file="figures/rev.png",
        source_keys=[SRC["key"]], fact_ids=["fact-revenue"])["ok"] is True
    return root


def _roll(monkeypatch, tmp_path, slug="rf-q2", new_slug="rf-q3", **kw):
    _source_with_evidence(monkeypatch, tmp_path, slug)
    params = {"period": "Q3'26", "as_of": "2026-10-30"}
    params.update(kw.pop("params", {}))
    return engine.rollforward_report(slug, new_slug, brief="Q3 update",
                                     params=params, **kw)


def test_rollforward_carries_registries(tmp_path, monkeypatch):
    root = _source_with_evidence(monkeypatch, tmp_path)
    src_reg = M.load(str(root)).registry_version
    res = engine.rollforward_report(
        "rf-q2", "rf-q3", brief="Q3 update",
        params={"period": "Q3'26", "as_of": "2026-10-30"})
    assert res["ok"] is True, res
    assert res["supersedes"]["report"] == "rf-q2"
    assert res["carried"] == {"sources": 1, "exhibits": 1, "facts": 2}
    new = M.load(str(tmp_path / "reports" / "rf-q3"))
    assert new.revision == 1 and new.state == "draft"
    assert new.registry_version == src_reg  # independent counters: stated
    assert set(new.sources) == {"src-fed-sep-2026-dots"}
    assert set(new.facts) == {"fact-revenue", "fact-guidance"}
    assert new.exhibits["fig-rev"]["file"] == "figures/rev.png"
    assert new.supersedes["report"] == "rf-q2"


def test_rollforward_requires_brief_and_asof(tmp_path, monkeypatch):
    _source_with_evidence(monkeypatch, tmp_path)
    assert engine.rollforward_report(
        "rf-q2", "rf-q3x", brief="",
        params={"period": "Q3", "as_of": "2026-10-30"})["ok"] is False
    assert engine.rollforward_report(
        "rf-q2", "rf-q3y", brief="Q3",
        params={"period": "Q3"})["ok"] is False  # no as_of, no checklist


def test_rollforward_excludes_outputs_and_state(tmp_path, monkeypatch):
    root = _source_with_evidence(monkeypatch, tmp_path)
    (root / "output").mkdir(exist_ok=True)
    (root / "output" / "index.html").write_text("<html></html>")
    (root / ".reportforge-state.json").write_text('{"manifest_revision": 1}')
    res = engine.rollforward_report(
        "rf-q2", "rf-q3", brief="Q3 update",
        params={"period": "Q3'26", "as_of": "2026-10-30"})
    assert res["ok"] is True, res
    new_root = tmp_path / "reports" / "rf-q3"
    assert not (new_root / "output").exists()
    assert not (new_root / ".reportforge-state.json").exists()
    assert (new_root / "report.json").is_file()


def test_stale_and_unknown_vintage(tmp_path, monkeypatch):
    """C-5 R2-F1: ISO dates compare chronologically; free-form/missing
    as_of lands in unknown_vintage — never silently fresh."""
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    engine.scaffold_report("rf-v", template="standard", formats=["html"])
    engine.register_fact("rf-v", "fact-old", 1.0, as_of="2026-01-15")
    engine.register_fact("rf-v", "fact-new", 2.0, as_of="2026-10-30")
    engine.register_fact("rf-v", "fact-nodate", 3.0)
    engine.register_fact("rf-v", "fact-weird", 4.0, as_of="Q2-2026")
    # DD/MM is never ISO: a naive string compare would call this stale
    # ("15/.." < "20.."), the ISO parser buckets it unknown.
    engine.register_fact("rf-v", "fact-sloppy", 5.0, as_of="15/01/2026")
    res = engine.rollforward_report(
        "rf-v", "rf-v2", brief="refresh",
        params={"period": "Oct", "as_of": "2026-10-30"})
    assert res["ok"] is True, res
    assert res["stale"] == ["fact-old"]
    assert sorted(res["unknown_vintage"]) == ["fact-nodate", "fact-sloppy",
                                              "fact-weird"]


def test_update_fact_history_carries_timestamp(tmp_path, monkeypatch):
    """C-5 R2-F2: history says what changed AND when."""
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    engine.scaffold_report("rf-h", template="standard", formats=["html"])
    engine.register_fact("rf-h", "fact-x", 1.0)
    res = engine.update_fact("rf-h", "fact-x", value=2.0)
    assert res["ok"] is True and res["changed"] is True
    m = M.load(str(tmp_path / "reports" / "rf-h"))
    hist = m.facts["fact-x"]["history"]
    assert len(hist) == 1 and hist[0]["value"] == 1.0
    assert isinstance(hist[0].get("at"), str) and hist[0]["at"]


def test_rollforward_copies_bib_figures_quarto(tmp_path, monkeypatch):
    root = _source_with_evidence(monkeypatch, tmp_path)
    assert (root / "sources.bib").is_file()
    res = engine.rollforward_report(
        "rf-q2", "rf-q3", brief="Q3 update",
        params={"period": "Q3'26", "as_of": "2026-10-30"})
    assert res["ok"] is True, res
    new_root = tmp_path / "reports" / "rf-q3"
    assert (new_root / "sources.bib").is_file()
    assert (new_root / "figures" / "rev.png").is_file()
    assert (new_root / "_quarto.yml").is_file()
    assert (new_root / "index.qmd").is_file()
