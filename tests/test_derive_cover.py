"""Milestone C task C-6 — cover auto-derivation + UNLINKED promotion."""

from __future__ import annotations

import json
from pathlib import Path

from reportforge import engine
from reportforge import manifest as M

QMD = """---
title: Cover Probe
reportforge-template: bespoke
target: 999
scenarios:
  - label: bear
    value: "10"
    detail: down
  - label: base
    value: "30"
    detail: flat
  - label: bull
    value: "60"
    detail: up
---

# Cover Probe

Body with a cite [@src-fed-sep-2026-dots].
"""


def _bespoke(monkeypatch, tmp_path: Path, slug: str = "cov-probe"):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    res = engine.scaffold_report(
        slug, template="bespoke", formats=["html"],
        frontmatter_yaml="title: Cover Probe\nreportforge-template: bespoke\n",
        body="# Cover Probe\n\nBody.\n")
    assert res["ok"] is True, res
    root = Path(res["path"])
    (root / "index.qmd").write_text(QMD)
    assert engine.register_source(
        slug, key="src-fed-sep-2026-dots", kind="report",
        title="Fed dots", date="2026-09-17")["ok"] is True
    return root


def _codes(res, category="evidence"):
    return [(i["code"], i["severity"])
            for i in res["categories"][category]["issues"]]


def _messages(res, code, category="evidence"):
    return [i["message"] for i in res["categories"][category]["issues"]
            if i["code"] == code]


def test_derive_cover_binds_target_by_convention(tmp_path, monkeypatch):
    """C-6: default fact-<field> convention binds without explicit mapping."""
    _bespoke(monkeypatch, tmp_path)
    engine.register_fact("cov-probe", "fact-target", 720.0)
    engine.register_fact("cov-probe", "fact-scenarios-0-value", 10.0)
    engine.register_fact("cov-probe", "fact-scenarios-1-value", 30.0)
    engine.register_fact("cov-probe", "fact-scenarios-2-value", 60.0)
    res = engine.derive_cover("cov-probe")
    assert res["ok"] is True, res
    assert sorted(res["updated"]) == ["scenarios[0].value",
                                      "scenarios[1].value",
                                      "scenarios[2].value", "target"]
    text = (tmp_path / "reports" / "cov-probe" / "index.qmd").read_text()
    assert "target: 720" in text
    assert "cover_derived: true" in text
    got = engine.check_readiness("cov-probe")
    assert ("EVID-COVER-UNLINKED", "error") not in _codes(got)
    assert [c for c, _ in _codes(got) if c == "EVID-COVER-UNLINKED"] == []


def test_derive_cover_explicit_mapping(tmp_path, monkeypatch):
    _bespoke(monkeypatch, tmp_path)
    engine.register_fact("cov-probe", "fact-pt", 720.0)
    engine.register_fact("cov-probe", "fact-bear", 10.0)
    engine.register_fact("cov-probe", "fact-base", 30.0)
    engine.register_fact("cov-probe", "fact-bull", 60.0)
    res = engine.derive_cover("cov-probe", mapping={
        "target": "fact-pt", "scenarios[0].value": "fact-bear",
        "scenarios[1].value": "fact-base", "scenarios[2].value": "fact-bull"})
    assert res["ok"] is True, res
    assert res["derived_from"]["target"] == "fact-pt"


def test_derive_cover_unmapped_field_fails_loudly(tmp_path, monkeypatch):
    """C-6: a numeric cover field with no fact fails naming the field —
    never silently keeps a hand value."""
    _bespoke(monkeypatch, tmp_path)
    res = engine.derive_cover("cov-probe")
    assert res["ok"] is False
    assert "target" in res["error"]


def test_unlinked_is_error_pointing_at_derive_cover(tmp_path, monkeypatch):
    """C-6: the contract promise — UNLINKED is an error with a fix pointer."""
    _bespoke(monkeypatch, tmp_path)
    res = engine.check_readiness("cov-probe")
    hits = [(c, s) for c, s in _codes(res) if c == "EVID-COVER-UNLINKED"]
    assert hits and all(s == "error" for _, s in hits)
    msgs = _messages(res, "EVID-COVER-UNLINKED")
    assert any("derive_cover" in m for m in msgs)


def test_derived_weights_split_stays_checked(tmp_path, monkeypatch):
    """C-6 R2-F9: a derived 30/40/30 split is registry-grounded, not
    noise — the weights skip must not hide later drift."""
    root = _bespoke(monkeypatch, tmp_path)
    text = (root / "index.qmd").read_text()
    text = text.replace('value: "10"', "value: 30").replace(
        'value: "30"', "value: 40", 1).replace('value: "60"', "value: 30")
    (root / "index.qmd").write_text(text)
    for fid, val in (("fact-target", 720.0),
                     ("fact-scenarios-0-value", 30.0),
                     ("fact-scenarios-1-value", 40.0),
                     ("fact-scenarios-2-value", 30.0)):
        engine.register_fact("cov-probe", fid, val)
    assert engine.derive_cover("cov-probe")["ok"] is True
    clean = engine.check_readiness("cov-probe")
    assert "EVID-COVER-UNLINKED" not in [c for c, _ in _codes(clean)]
    # Drift one fact: the (weights-summing) field must now fire.
    engine.update_fact("cov-probe", "fact-scenarios-1-value", value=41.0)
    drifted = engine.check_readiness("cov-probe")
    assert "EVID-COVER-UNLINKED" in [c for c, _ in _codes(drifted)]


def test_derive_cover_flow_style_fails_loudly(tmp_path, monkeypatch):
    """Review F1: flow-style '- {label:.., value:..}' items cannot be
    rewritten line-surgically — derive must fail loudly, never silently
    keep the hand value while stamping cover_derived."""
    root = _bespoke(monkeypatch, tmp_path)
    text = (root / "index.qmd").read_text()
    start = text.index("scenarios:")
    end = text.index("---", start)
    text = (text[:start]
            + "scenarios:\n  - {label: bear, value: 30}\n"
            + "  - {label: base, value: 40}\n"
            + "  - {label: bull, value: 30}\n"
            + text[end:])
    (root / "index.qmd").write_text(text)
    for fid, val in (("fact-target", 720.0),
                     ("fact-scenarios-0-value", 30.0),
                     ("fact-scenarios-1-value", 40.0),
                     ("fact-scenarios-2-value", 30.0)):
        engine.register_fact("cov-probe", fid, val)
    res = engine.derive_cover("cov-probe")
    assert res["ok"] is False
    assert "flow-style" in res["error"]
    assert "cover_derived" not in (root / "index.qmd").read_text()
