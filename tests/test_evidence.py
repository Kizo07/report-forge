"""Milestone B Task B-1: manifest evidence registry fields (RF-03) — schema 2."""

import json
import os

import pytest

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
