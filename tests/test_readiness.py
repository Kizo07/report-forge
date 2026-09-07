"""Task 1.4 — readiness (contract §4) + quant fixture matrix (readiness-numerics-v1)."""

from __future__ import annotations

from pathlib import Path

from reportforge import engine
from reportforge import manifest as manifest_mod

BASE_SECTIONS = """
# Executive summary

Clean summary with no prices.

# Analysis

Clean analysis with no prices.

# Recommendations

Hold.
"""


def _write(tmp_path: Path, name: str, frontmatter: str, body: str) -> Path:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.qmd").write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")
    return root


def _make(tmp_path: Path, name: str, frontmatter: str, body: str) -> str:
    root = _write(tmp_path, name, frontmatter, body)
    manifest_mod.import_dir(str(root))
    return name


def _codes(res: dict, category: str) -> list[str]:
    return [i["code"] for i in res["categories"][category]["issues"]]


def test_derived_pct_fires_once(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path)
    fm = "title: T\nreportforge-template: standard\ndate: 2026-09-04\ntarget: 310\nverdict: '+18% to $310'\n"
    body = "Spot $254.98.\n" + BASE_SECTIONS
    proj = _make(tmp_path, "p-derived", fm, body)
    res = engine.check_readiness(proj)
    assert res["ok"] is True
    assert _codes(res, "numerical") == ["NUM-DERIVED-PCT"]
    assert res["categories"]["numerical"]["issues"][0]["severity"] == "error"


def test_spot_drift_fires_once(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path)
    fm = "title: T\nreportforge-template: standard\ndate: 2026-09-04\n"
    body = ("Close $254.98.\n\n> Quoted $256.00 at the close.\n" + BASE_SECTIONS)
    proj = _make(tmp_path, "p-spot", fm, body)
    res = engine.check_readiness(proj)
    assert _codes(res, "numerical") == ["NUM-SPOT-DISAGREE"]
    assert res["categories"]["numerical"]["issues"][0]["severity"] == "error"


def test_asof_future_and_mixed(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path)
    fm = "title: T\nreportforge-template: standard\ndate: 2026-09-04\n"
    p1 = _make(tmp_path, "p-future", fm,
               "As of 2026-09-05\n\n| Metric | Value |\n| Close | 100 |\n" + BASE_SECTIONS)
    assert _codes(engine.check_readiness(p1), "numerical") == ["NUM-ASOF-FUTURE"]
    p2 = _make(tmp_path, "p-mixed", fm,
               ("As of 2026-09-02\n\nAs of 2026-09-02\n\nAs of 2026-09-01\n"
                + BASE_SECTIONS))
    res2 = engine.check_readiness(p2)
    assert _codes(res2, "numerical") == ["NUM-ASOF-MIXED"]
    assert res2["categories"]["numerical"]["issues"][0]["severity"] == "warning"


def test_sign_conflict_fires_once(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path)
    fm = "title: T\nreportforge-template: standard\ndate: 2026-09-04\n"
    body = ("Momentum fell 1.64 percent week over week.\n\n"
            "| Metric | Change |\n| Momentum | +1.64% |\n" + BASE_SECTIONS)
    proj = _make(tmp_path, "p-sign", fm, body)
    assert _codes(engine.check_readiness(proj), "numerical") == ["NUM-SIGN-CONFLICT"]


def test_scenario_weights_sum(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path)
    fm = ("title: T\nreportforge-template: standard\ndate: 2026-09-04\n"
          "scenarios:\n  - {label: bear, value: 20}\n  - {label: base, value: 50}\n  - {label: bull, value: 25}\n")
    proj = _make(tmp_path, "p-weights", fm, BASE_SECTIONS)
    assert _codes(engine.check_readiness(proj), "numerical") == ["NUM-SCENARIO-WEIGHTS"]


def test_clean_trio_has_zero_numerical_issues(tmp_path, monkeypatch):
    """Plan Task 1.4's 3-issue fixture: dangling ref + orphan chart + illustrative."""
    from PIL import Image
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path)
    fm = "title: T\nreportforge-template: standard\ndate: 2026-09-04\n"
    body = ("See @fig-ex9 for detail.\n\nILLUSTRATIVE placeholder exhibit.\n"
            + BASE_SECTIONS)
    root = _write(tmp_path, "p-clean", fm, body)
    charts = root / "charts"
    charts.mkdir(exist_ok=True)
    Image.new("RGB", (4, 4), (10, 20, 30)).save(charts / "orphan.png")
    manifest_mod.import_dir(str(root))
    res = engine.check_readiness("p-clean")
    assert res["categories"]["numerical"]["issues"] == []
    assert any(i["code"] == "PRES-DANGLING-REF"
               for i in res["categories"]["presentation"]["issues"])


def test_rounded_vs_precise_is_quiet(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path)
    fm = "title: T\nreportforge-template: standard\ndate: 2026-09-04\n"
    body = "Close $254.98. Table shows $255 at the close.\n" + BASE_SECTIONS
    proj = _make(tmp_path, "p-round", fm, body)
    res = engine.check_readiness(proj)
    assert res["categories"]["numerical"]["issues"] == []
    assert res["categories"]["numerical"]["pass"] is True


def test_structure_and_review_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path)
    fm = "title: T\nreportforge-template: standard\ndate: 2026-09-04\n"
    root = _write(tmp_path, "p-struct", fm, "# Executive summary\n\nOnly this.\n")
    manifest_mod.import_dir(str(root))
    res = engine.check_readiness("p-struct")
    assert "STRUCT-MISSING-SECTION" in _codes(res, "structure")
    assert res["ready_for_review"] is False
    rec = engine.record_review("p-struct", 1, "human:fire", "approved", "lgtm")
    assert rec["ok"] is True
    res2 = engine.check_readiness("p-struct")
    assert any(i["code"] == "EDIT-REVIEWED"
               for i in res2["categories"]["editorial"]["issues"])
    bad = engine.record_review("p-struct", 1, "human:fire", "maybe")
    assert bad["ok"] is False
