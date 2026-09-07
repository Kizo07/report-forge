"""Milestone B Task B-1: manifest evidence registry fields (RF-03) — schema 2."""

import json
import os
from pathlib import Path

import pytest

from reportforge import engine
from reportforge import manifest as M

QMD = """---
title: Test Report
reportforge-template: earnings-recap
---

# Test Report

Body.
"""


@pytest.fixture
def proj(tmp_path):
    root = tmp_path / "demo-1m"
    root.mkdir()
    (root / "index.qmd").write_text(QMD, encoding="utf-8")
    return str(root)


def _manifest_json(proj):
    with open(os.path.join(proj, "report.json"), encoding="utf-8") as f:
        return json.load(f)


def test_registries_default_empty(proj):
    m = M.create(proj, title="T")
    assert m.sources == {} and m.exhibits == {} and m.facts == {}
    assert m.registry_version == 0
    raw = _manifest_json(proj)
    assert raw["schema_version"] == 2


def test_old_v1_manifest_loads_with_empty_registries(proj):
    M.create(proj, title="T")
    raw = _manifest_json(proj)
    raw["schema_version"] = 1
    del raw["sources"], raw["exhibits"], raw["facts"], raw["registry_version"]
    with open(os.path.join(proj, "report.json"), "w", encoding="utf-8") as f:
        json.dump(raw, f)
    m = M.load(proj)
    assert m.sources == {} and m.exhibits == {} and m.facts == {}
    assert m.registry_version == 0


def test_newer_schema_fails_loudly(proj):
    M.create(proj, title="T")
    raw = _manifest_json(proj)
    raw["schema_version"] = 3
    with open(os.path.join(proj, "report.json"), "w", encoding="utf-8") as f:
        json.dump(raw, f)
    with pytest.raises(M.ManifestError):
        M.load(proj)


def test_malformed_source_fails_on_load(proj):
    M.create(proj, title="T")
    raw = _manifest_json(proj)
    raw["sources"] = {"src-bad": {"key": "src-bad", "kind": "filing"}}  # no title/date
    with open(os.path.join(proj, "report.json"), "w", encoding="utf-8") as f:
        json.dump(raw, f)
    with pytest.raises(M.ManifestError):
        M.load(proj)


def test_malformed_exhibit_fails_on_load(proj):
    M.create(proj, title="T")
    raw = _manifest_json(proj)
    raw["exhibits"] = {"fig-x": {"id": "fig-x"}}  # no title, no grounding
    with open(os.path.join(proj, "report.json"), "w", encoding="utf-8") as f:
        json.dump(raw, f)
    with pytest.raises(M.ManifestError):
        M.load(proj)


def test_registry_version_must_be_int(proj):
    M.create(proj, title="T")
    raw = _manifest_json(proj)
    raw["registry_version"] = "seven"
    with open(os.path.join(proj, "report.json"), "w", encoding="utf-8") as f:
        json.dump(raw, f)
    with pytest.raises(M.ManifestError):
        M.load(proj)


GOOD_SOURCE = {
    "key": "src-fed-sep-2026-dots",
    "kind": "dataset",
    "title": "FOMC dot plot September 2026",
    "date": "2026-09-17",
    "url": "https://example.invalid/dots",
}


def test_validate_source_ok():
    ok, err = M.validate_source(dict(GOOD_SOURCE))
    assert ok, err


def test_validate_source_rejects():
    bad_kind = dict(GOOD_SOURCE, kind="tweet")
    assert M.validate_source(bad_kind)[0] is False
    no_title = dict(GOOD_SOURCE)
    del no_title["title"]
    assert M.validate_source(no_title)[0] is False
    no_date = dict(GOOD_SOURCE)
    del no_date["date"]
    assert M.validate_source(no_date)[0] is False  # neither date nor as_of
    asof_ok = dict(GOOD_SOURCE)
    del asof_ok["date"]
    asof_ok["as_of"] = "2026-09-17"
    assert M.validate_source(asof_ok)[0] is True
    # src- namespace is reserved: crossref prefixes are not citekeys.
    for bad_key in ("fig-revenue", "tbl-results", "sec-method", "plain-key"):
        assert M.validate_source(dict(GOOD_SOURCE, key=bad_key))[0] is False, bad_key


def test_validate_exhibit_ok_and_rejects():
    good = {"id": "fig-revenue", "title": "Revenue trend",
            "file": "figures/revenue.png",
            "source_keys": ["src-fed-sep-2026-dots"], "fact_ids": []}
    assert M.validate_exhibit(good)[0] is True
    anchor_grounded = {"id": "fig-revenue", "title": "Revenue trend",
                       "file": None, "source_keys": [], "fact_ids": []}
    assert M.validate_exhibit(anchor_grounded)[0] is True
    no_title = dict(good)
    del no_title["title"]
    assert M.validate_exhibit(no_title)[0] is False
    bad_id = dict(good, id="chart-1")
    assert M.validate_exhibit(bad_id)[0] is False
    bad_links = dict(good, source_keys="src-fed-sep-2026-dots")
    assert M.validate_exhibit(bad_links)[0] is False


def test_validate_fact_ok_and_rejects():
    good = {"id": "fact-target-300", "value": 300, "unit": "USD",
            "kind": "calculated", "source_keys": [], "as_of": "2026-09-01"}
    assert M.validate_fact(good)[0] is True
    bad_kind = dict(good, kind="guessed")
    assert M.validate_fact(bad_kind)[0] is False
    for kind in ("observed", "calculated", "estimated", "illustrative"):
        assert M.validate_fact(dict(good, kind=kind))[0] is True, kind
    bad_id = dict(good, id="target-300")
    assert M.validate_fact(bad_id)[0] is False
    no_value = dict(good)
    del no_value["value"]
    assert M.validate_fact(no_value)[0] is False


# --- B-2: register_source -----------------------------------------------------
# (tests below, after the shared helpers)


# --- B-3: register_exhibit ------------------------------------------------------

WHITE_FIG_JSON = None  # built lazily: needs plotly import


def _white_fig_json():
    import plotly.express as px

    return px.line(x=[1, 2], y=[3, 4]).to_json()


def test_register_exhibit_file_grounded(tmp_path, monkeypatch):
    root = _scaffold(monkeypatch, tmp_path)
    engine.register_source("ev-probe", **SRC)
    (root / "figures").mkdir()
    (root / "figures" / "revenue.png").write_bytes(b"fake-png")
    res = engine.register_exhibit(
        "ev-probe", exhibit_id="fig-revenue", title="Revenue trend",
        file="figures/revenue.png", source_keys=["src-fed-sep-2026-dots"])
    assert res["ok"] is True
    m = M.load(str(root))
    assert m.exhibits["fig-revenue"]["file"] == "figures/revenue.png"
    assert m.registry_version == 2  # source + exhibit


def test_register_exhibit_anchor_grounded_no_file(tmp_path, monkeypatch):
    root = _scaffold(monkeypatch, tmp_path)
    qmd = (root / "index.qmd").read_text(encoding="utf-8")
    (root / "index.qmd").write_text(
        qmd + "\n![Rev.](figures/revenue.png){#fig-revenue}\n", encoding="utf-8")
    res = engine.register_exhibit("ev-probe", exhibit_id="fig-revenue",
                                  title="Revenue trend", file=None)
    assert res["ok"] is True  # grounded by anchor, file null never fires


def test_register_exhibit_ungrounded_fails(tmp_path, monkeypatch):
    _scaffold(monkeypatch, tmp_path)
    res = engine.register_exhibit("ev-probe", exhibit_id="fig-ghost",
                                  title="Ghost chart")
    assert res["ok"] is False  # no anchor, no file


def test_register_exhibit_dangling_source_fails(tmp_path, monkeypatch):
    root = _scaffold(monkeypatch, tmp_path)
    (root / "figures").mkdir()
    (root / "figures" / "x.png").write_bytes(b"x")
    res = engine.register_exhibit("ev-probe", exhibit_id="fig-x", title="X",
                                  file="figures/x.png",
                                  source_keys=["src-never-registered"])
    assert res["ok"] is False
    assert "src-never-registered" in res["error"]


def test_register_exhibit_reregister_needs_overwrite(tmp_path, monkeypatch):
    root = _scaffold(monkeypatch, tmp_path)
    (root / "figures").mkdir()
    (root / "figures" / "x.png").write_bytes(b"x")
    assert engine.register_exhibit(
        "ev-probe", exhibit_id="fig-x", title="X",
        file="figures/x.png")["ok"] is True
    dup = engine.register_exhibit("ev-probe", exhibit_id="fig-x", title="X2",
                                  file="figures/x.png")
    assert dup["ok"] is False
    assert "already registered" in dup["error"]
    assert engine.register_exhibit(
        "ev-probe", exhibit_id="fig-x", title="X2",
        file="figures/x.png", overwrite=True)["ok"] is True


def test_save_chart_with_project_registers_exhibit(tmp_path, monkeypatch):
    root = _scaffold(monkeypatch, tmp_path)
    out = engine.save_chart(_white_fig_json(), "trend", project="ev-probe")
    assert out["ok"] is True, out
    assert (root / "figures" / "trend.png").is_file()  # figures/, not cwd
    m = M.load(str(root))
    assert "fig-trend" in m.exhibits
    assert m.exhibits["fig-trend"]["file"] == "figures/trend.png"


def test_save_chart_explicit_in_project_path_honored(tmp_path, monkeypatch):
    root = _scaffold(monkeypatch, tmp_path)
    target = str(root / "figures" / "custom-name")
    out = engine.save_chart(_white_fig_json(), target, project="ev-probe")
    assert out["ok"] is True, out
    assert Path(out["png"]).is_file()
    assert Path(out["png"]).parent == root / "figures"


def test_save_chart_without_project_registers_nothing(tmp_path, monkeypatch):
    _scaffold(monkeypatch, tmp_path)
    out = engine.save_chart(_white_fig_json(),
                            str(tmp_path / "loose" / "trend"))
    assert out["ok"] is True, out
    m = M.load(str(tmp_path / "reports" / "ev-probe"))
    assert m.exhibits == {}
    assert m.registry_version == 0


def test_save_chart_bad_exhibit_link_fails_before_write(tmp_path, monkeypatch):
    root = _scaffold(monkeypatch, tmp_path)
    out = engine.save_chart(_white_fig_json(), "trend", project="ev-probe",
                            source_keys=["src-never-registered"])
    assert out["ok"] is False
    assert not (root / "figures" / "trend.png").exists()  # nothing half-written


# --- B-4: register_fact / update_fact ------------------------------------------

FACT = dict(fact_id="fact-target-300", value=300, unit="USD",
            kind="calculated", source_keys=["src-fed-sep-2026-dots"])


def test_register_fact_round_trip(tmp_path, monkeypatch):
    root = _scaffold(monkeypatch, tmp_path)
    engine.register_source("ev-probe", **SRC)
    res = engine.register_fact("ev-probe", **FACT)
    assert res["ok"] is True
    m = M.load(str(root))
    rec = m.facts["fact-target-300"]
    assert rec["value"] == 300 and rec["kind"] == "calculated"
    assert m.registry_version == 2


def test_register_fact_bad_kind_fails(tmp_path, monkeypatch):
    _scaffold(monkeypatch, tmp_path)
    res = engine.register_fact("ev-probe", **dict(FACT, kind="guessed"))
    assert res["ok"] is False


def test_register_fact_dangling_source_fails(tmp_path, monkeypatch):
    _scaffold(monkeypatch, tmp_path)
    res = engine.register_fact("ev-probe", **FACT)  # source not registered
    assert res["ok"] is False
    assert "src-fed-sep-2026-dots" in res["error"]


def test_register_fact_illustrative_flags(tmp_path, monkeypatch):
    _scaffold(monkeypatch, tmp_path)
    res = engine.register_fact("ev-probe", fact_id="fact-demo-1", value=999,
                               unit="USD", kind="illustrative")
    assert res["ok"] is True
    assert res["illustrative"] is True  # readiness half: EVID-COVER-ILLUSTRATIVE


def test_register_fact_duplicate_needs_overwrite(tmp_path, monkeypatch):
    _scaffold(monkeypatch, tmp_path)
    engine.register_source("ev-probe", **SRC)
    assert engine.register_fact("ev-probe", **FACT)["ok"] is True
    assert engine.register_fact("ev-probe", **FACT)["ok"] is False
    assert engine.register_fact("ev-probe", **FACT, overwrite=True)["ok"] is True


def test_update_fact_keeps_history_capped(tmp_path, monkeypatch):
    root = _scaffold(monkeypatch, tmp_path)
    engine.register_source("ev-probe", **SRC)
    engine.register_fact("ev-probe", **FACT)
    for v in (310, 320):
        up = engine.update_fact("ev-probe", "fact-target-300", value=v)
        assert up["ok"] is True
    m = M.load(str(root))
    rec = m.facts["fact-target-300"]
    assert rec["value"] == 320
    assert [h["value"] for h in rec["history"]] == [300, 310]
    assert rec["history"][-1]["superseded_by"] == 320
    for v in range(400, 430):
        engine.update_fact("ev-probe", "fact-target-300", value=v)
    rec = M.load(str(root)).facts["fact-target-300"]
    assert len(rec["history"]) == 20  # capped, oldest dropped


def test_update_fact_missing_id_fails(tmp_path, monkeypatch):
    _scaffold(monkeypatch, tmp_path)
    res = engine.update_fact("ev-probe", "fact-nope", value=1)
    assert res["ok"] is False


# --- B-5: evidence in views + capabilities -------------------------------------

def test_status_and_open_expose_evidence(tmp_path, monkeypatch):
    root = _scaffold(monkeypatch, tmp_path)
    engine.register_source("ev-probe", **SRC)
    st = engine.project_status("ev-probe")
    assert st["ok"] is True
    ev = st["manifest"]["evidence"]
    assert ev["counts"] == {"sources": 1, "exhibits": 0, "facts": 0}
    assert ev["sources"]["src-fed-sep-2026-dots"]["title"] == SRC["title"]
    assert ev["exhibits"] == {} and ev["facts"] == {}
    assert ev["registry_version"] == 1
    op = engine.open_report("ev-probe")
    assert op["ok"] is True
    assert op["evidence"]["counts"]["sources"] == 1


def test_capabilities_evidence_block():
    caps = engine.reportforge_capabilities()
    ev = caps["evidence"]
    assert ev["registry"] is True
    assert ev["bib_file"] == "sources.bib"
    assert set(("observed", "calculated", "estimated", "illustrative")) <= set(ev["fact_kinds"])
    assert "reportforge_register_source" in ev["register_tools"]
    assert "reportforge_update_fact" in ev["register_tools"]

def _scaffold(monkeypatch, tmp_path, slug="ev-probe", template="standard"):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    res = engine.scaffold_report(slug, template=template, formats=["html", "pdf"])
    assert res["ok"] is True
    return tmp_path / "reports" / slug


SRC = dict(key="src-fed-sep-2026-dots", kind="dataset",
           title="FOMC dot plot, September 2026", date="2026-09-17")


def test_register_source_persists_and_writes_bib(tmp_path, monkeypatch):
    root = _scaffold(monkeypatch, tmp_path)
    res = engine.register_source("ev-probe", **SRC)
    assert res["ok"] is True
    assert res["key"] == "src-fed-sep-2026-dots"
    m = M.load(str(root))
    assert m.sources["src-fed-sep-2026-dots"]["title"] == SRC["title"]
    assert m.registry_version == 1
    bib = (root / "sources.bib").read_text(encoding="utf-8")
    assert "@misc{src-fed-sep-2026-dots," in bib
    assert "FOMC dot plot" in bib


def test_register_source_duplicate_fails_loudly(tmp_path, monkeypatch):
    _scaffold(monkeypatch, tmp_path)
    assert engine.register_source("ev-probe", **SRC)["ok"] is True
    dup = engine.register_source("ev-probe", **SRC)
    assert dup["ok"] is False  # names existing title, no silent overwrite
    assert "already registered" in dup["error"]
    ok2 = engine.register_source("ev-probe", key=SRC["key"], kind=SRC["kind"],
                                 title="FOMC dots (revised)", date=SRC["date"],
                                 overwrite=True)
    assert ok2["ok"] is True


def test_register_source_bad_kind_fails(tmp_path, monkeypatch):
    _scaffold(monkeypatch, tmp_path)
    res = engine.register_source("ev-probe", **dict(SRC, kind="tweet"))
    assert res["ok"] is False


def test_register_source_rewrites_whole_bib(tmp_path, monkeypatch):
    root = _scaffold(monkeypatch, tmp_path)
    engine.register_source("ev-probe", **SRC)
    engine.register_source("ev-probe", key="src-bea-gdp-q2", kind="dataset",
                           title="BEA GDP Q2 2026", date="2026-07-30")
    bib = (root / "sources.bib").read_text(encoding="utf-8")
    assert "@misc{src-fed-sep-2026-dots," in bib  # first entry survives
    assert "@misc{src-bea-gdp-q2," in bib


def test_register_source_yml_top_level_bibliography(tmp_path, monkeypatch):
    root = _scaffold(monkeypatch, tmp_path)
    engine.register_source("ev-probe", **SRC)
    engine.register_source("ev-probe", key="src-x", kind="article",
                           title="X", date="2026-01-01")
    lines = (root / "_quarto.yml").read_text(encoding="utf-8").splitlines()
    bib_lines = [ln for ln in lines if ln.strip().startswith("bibliography:")]
    assert len(bib_lines) == 1  # exactly one, never duplicated
    assert bib_lines[0].startswith("bibliography:")  # top-level, not nested
    assert bib_lines[0].strip() == "bibliography: sources.bib"


def test_source_to_bibtex_escapes_and_year(tmp_path, monkeypatch):
    bib = engine._source_to_bibtex({
        "key": "src-tricky", "kind": "article",
        "title": "Growth {Q3} & 100% {real} results",
        "publisher": "Desk", "date": "2026-09-17",
        "url": "https://example.invalid/x", "as_of": "2026-09-18",
        "accessed": "2026-09-19"})
    assert "@misc{src-tricky," in bib
    assert "year = {2026}" in bib
    # Raw braces must not leak into the bib entry unescaped.
    assert "{Q3}" not in bib and "{real}" not in bib
    assert "as-of 2026-09-18" in bib and "accessed 2026-09-19" in bib
