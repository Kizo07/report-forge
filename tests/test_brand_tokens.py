"""Milestone C task C-3 — brand tokens keyed by palette name (all four)."""

from __future__ import annotations

from pathlib import Path

import pytest

from reportforge import engine
from reportforge import templates as templates_mod


def _white_fig_json():
    import plotly.express as px

    return px.line(x=[1, 2], y=[3, 4]).to_json()


def test_tokens_for_all_four_palettes():
    """C-3: every palette resolves; accent is the palette primary."""
    expected = {
        "quantflow-dark": "#c9a227",
        "quantflow-light": "#8f621f",
        "ledger-dark": "#e3ac55",
        "ledger-light": "#8f621f",
    }
    assert set(engine.tokens_for_keys()) == set(expected)
    for name, accent in expected.items():
        tok = engine.tokens_for(name)
        assert tok["accent"] == accent == tok["primary"], name


def test_tokens_for_unknown_names_supported():
    with pytest.raises(ValueError, match="ledger-dark"):
        engine.tokens_for("bogus-palette")


def test_save_chart_explicit_template_through_tokens(tmp_path, monkeypatch):
    """C-3: explicit template= maps through the same token keys."""
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    engine.scaffold_report("tok-probe", template="standard", formats=["html"])
    out = engine.save_chart(_white_fig_json(), "led", project="tok-probe",
                            template="ledger-dark")
    assert out["ok"] is True, out
    assert out["template_applied"] == "ledger-dark"


def test_save_chart_ledger_project_keeps_ledger_palette(tmp_path, monkeypatch):
    """C-3 R1-F1: auto-derive must not silently re-palette a ledger
    report to quantflow-dark (same brand+theme, different palette)."""
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    engine.scaffold_report("tok-ledger", template="ledger-dark",
                           formats=["html"])
    out = engine.save_chart(_white_fig_json(), "rev", project="tok-ledger")
    assert out["ok"] is True, out
    assert out["template_applied"] == "ledger-dark"


def test_scaffold_writes_matching_brand_yml(tmp_path, monkeypatch):
    """C-3: cover colors resolve from the per-template _brand.yml."""
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    pairs = {
        "portfolio-dark": templates_mod.PORTFOLIO_DARK_BRAND_YML,
        "portfolio-light": templates_mod.PORTFOLIO_LIGHT_BRAND_YML,
        "ledger-dark": templates_mod.LEDGER_DARK_BRAND_YML,
        "ledger-light": templates_mod.LEDGER_LIGHT_BRAND_YML,
    }
    for template, expected in pairs.items():
        slug = "tok-" + template
        res = engine.scaffold_report(slug, template=template, formats=["html"])
        assert res["ok"] is True, res
        written = (tmp_path / "reports" / slug / "_brand.yml").read_text()
        assert written == expected, template
