"""Milestone C task C-1 — explicit profile matrix, no template-name sniffing."""

from __future__ import annotations

import json
from pathlib import Path

from reportforge import engine


def _scaffold(monkeypatch, tmp_path: Path, slug: str = "prof-probe",
              template: str = "standard", **kw):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    return engine.scaffold_report(slug, template=template, **kw)


def _profile_of(tmp_path: Path, slug: str) -> dict:
    return json.loads(
        (tmp_path / "reports" / slug / "report.json").read_text())["profile"]


def test_all_templates_resolve_to_presets():
    """C-1: every list_templates() name maps to a preset whose report_type
    is the template's own name (no silent rename)."""
    names = [t["name"] for t in engine.list_templates()]
    assert len(names) == 19
    for name in names:
        prof, err = engine._profile_for_template(name)
        assert err is None, f"{name}: {err}"
        assert prof["report_type"] == name, f"{name} renamed to {prof['report_type']}"
        assert prof["brand"] == "quantflow"
        assert prof["theme"] in ("light", "dark")
        assert prof["layout"] == "magazine"
        assert prof["output_profile"] == "editorial"
        assert prof["policy"] == "draft"


def test_dark_variants_keep_theme():
    for name in ("portfolio-dark", "ledger-dark"):
        prof, err = engine._profile_for_template(name)
        assert err is None
        assert prof["theme"] == "dark"


def test_studio_report_type_not_renamed(tmp_path, monkeypatch):
    """C-1 R1-F2: studio must stay 'studio' — the 'studio-editorial'
    rename broke the REQUIRED_SECTIONS lookup."""
    res = _scaffold(monkeypatch, tmp_path, slug="studio-probe", template="studio")
    assert res["ok"] is True
    assert _profile_of(tmp_path, "studio-probe")["report_type"] == "studio"


def test_studio_readiness_hits_required_sections(tmp_path, monkeypatch):
    """C-1 R1-F2: with the rename fixed, studio reports get their
    required-sections check instead of STRUCT-NO-REQUIRED-LIST."""
    _scaffold(monkeypatch, tmp_path, slug="studio-ready", template="studio")
    res = engine.check_readiness("studio-ready")
    assert res["ok"] is True
    codes = [i["code"] for i in res.get("issues", [])]
    assert "STRUCT-NO-REQUIRED-LIST" not in codes


def test_bad_brand_rejected_loudly(tmp_path, monkeypatch):
    """C-1: unknown axis values fail with the supported set named."""
    res = _scaffold(monkeypatch, tmp_path, profile={"brand": "bogus"})
    assert res["ok"] is False
    assert "quantflow" in res["error"]


def test_legal_overrides_accepted(tmp_path, monkeypatch):
    res = _scaffold(monkeypatch, tmp_path, slug="prof-override",
                    profile={"output_profile": "web", "policy": "release"})
    assert res["ok"] is True
    prof = _profile_of(tmp_path, "prof-override")
    assert prof["output_profile"] == "web"
    assert prof["policy"] == "release"
    assert prof["report_type"] == "standard"


def test_theme_layout_overrides_rejected(tmp_path, monkeypatch):
    """C-1: theme/layout are fixed per preset (axes reserved, unpopulated)."""
    for bad in ({"theme": "dark"}, {"layout": "brief"},
                {"output_profile": "print"}, {"policy": "flagship"}):
        res = _scaffold(monkeypatch, tmp_path, slug="prof-bad", profile=bad)
        assert res["ok"] is False, bad
        assert "not supported" in res["error"]


def test_capabilities_map_agrees_with_stored_profile(tmp_path, monkeypatch):
    """C-1: discovery and stored profiles agree — the rename map is empty."""
    _scaffold(monkeypatch, tmp_path, slug="studio-agree", template="studio")
    caps = engine.reportforge_capabilities()
    assert caps["profiles"]["report_type_map"] == {}
    assert (_profile_of(tmp_path, "studio-agree")["report_type"] == "studio")
