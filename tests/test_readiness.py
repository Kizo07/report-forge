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
               ("As of 2026-09-02\n\n| Metric | Close |\n| AMZN | $254.98 |\n\n"
                "As of 2026-09-02\n\n| Metric | Close |\n| AMZN | $254.98 |\n\n"
                "As of 2026-09-01\n\n| Metric | Close |\n| AMZN | $254.90 |\n"
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


# --- critic-2 RF-04 review: spec grounding + missing codes -------------------

def test_grounding_pass_cover_spot_target(tmp_path, monkeypatch):
    """Numerics-v1 §4: '+18% to $300' with spot $254.98 → derived +17.65%,
    Δ0.35 ≤ 0.5 → no error. The target must never be mistaken for the spot."""
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path)
    fm = ("title: T\nreportforge-template: standard\ndate: 2026-09-04\n"
          "target: 300\nverdict: '+18% to $300'\n")
    body = ("AMZN closed at $254.98. Price target $300.\n" + BASE_SECTIONS)
    proj = _make(tmp_path, "p-ground", fm, body)
    res = engine.check_readiness(proj)
    assert res["categories"]["numerical"]["issues"] == []
    assert res["categories"]["numerical"]["pass"] is True


def test_peer_comp_table_does_not_cluster(tmp_path, monkeypatch):
    """§2 keying: different tickers never cluster, even at equal as-of."""
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path)
    fm = "title: T\nreportforge-template: standard\ndate: 2026-09-04\n"
    body = ("| Name | Close |\n| AMZN | $254.98 |\n| MSFT | $420.10 |\n"
            + BASE_SECTIONS)
    proj = _make(tmp_path, "p-peers", fm, body)
    res = engine.check_readiness(proj)
    assert res["categories"]["numerical"]["issues"] == []


def test_scenario_recompute_error_all_parse(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path)
    fm = ("title: T\nreportforge-template: standard\ndate: 2026-09-04\n"
          "scenarios:\n  - {label: bear, value: 20, return: -18}\n"
          "  - {label: base, value: 50, return: 18}\n"
          "  - {label: bull, value: 25, return: 35}\n"
          "  - {label: tail, value: 5, return: 10}\n"
          "expected_return: 7\n")
    proj = _make(tmp_path, "p-recomp", fm, BASE_SECTIONS)
    res = engine.check_readiness(proj)
    codes = _codes(res, "numerical")
    assert codes == ["NUM-SCENARIO-RECOMPUTE"]
    assert res["categories"]["numerical"]["issues"][0]["severity"] == "error"


def test_scenario_recompute_warning_tail_open(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path)
    fm = ("title: T\nreportforge-template: standard\ndate: 2026-09-04\n"
          "scenarios:\n  - {label: bear, value: 20, return: -18}\n"
          "  - {label: base, value: 50, return: 18}\n"
          "  - {label: bull, value: 25, return: 35}\n"
          "  - {label: tail, value: 5}\n"
          "expected_return: 99\n")
    proj = _make(tmp_path, "p-recomp-tail", fm, BASE_SECTIONS)
    res = engine.check_readiness(proj)
    issues = res["categories"]["numerical"]["issues"]
    assert [i["code"] for i in issues] == ["NUM-SCENARIO-RECOMPUTE"]
    assert issues[0]["severity"] == "warning"


def test_target_agree_fires(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path)
    fm = ("title: T\nreportforge-template: standard\ndate: 2026-09-04\n"
          "target: 300\n")
    body = ("| Scenario | Target |\n| Base | $310 |\n" + BASE_SECTIONS)
    proj = _make(tmp_path, "p-tagree", fm, body)
    res = engine.check_readiness(proj)
    assert _codes(res, "numerical") == ["NUM-TARGET-AGREE"]


def test_table_total_fires(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path)
    fm = "title: T\nreportforge-template: standard\ndate: 2026-09-04\n"
    body = ("| Segment | Revenue |\n| Cloud | $100 |\n| Ads | $50 |\n"
            "| Total | $999 |\n" + BASE_SECTIONS)
    proj = _make(tmp_path, "p-total", fm, body)
    res = engine.check_readiness(proj)
    assert _codes(res, "numerical") == ["NUM-TABLE-TOTAL"]


def test_prose_table_warning_and_hedged_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path)
    fm = "title: T\nreportforge-template: standard\ndate: 2026-09-04\n"
    body = ("Revenue was $152.4. The segment revenue stands at about $160.\n\n"
            "| Segment | Revenue |\n| Cloud | $152.4 |\n| Ads | $161.5 |\n"
            + BASE_SECTIONS)
    proj = _make(tmp_path, "p-pt", fm, body)
    res = engine.check_readiness(proj)
    issues = res["categories"]["numerical"]["issues"]
    assert [i["code"] for i in issues] == ["NUM-PROSE-TABLE"]
    assert issues[0]["severity"] == "warning"


def test_required_sections_per_genre_and_bespoke_info(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path)
    fm = "title: T\nreportforge-template: earnings-recap\ndate: 2026-09-04\n"
    root = _write(tmp_path, "p-genre", fm, "# Executive summary\n\nOnly this.\n")
    manifest_mod.import_dir(str(root))
    res = engine.check_readiness("p-genre")
    assert "STRUCT-MISSING-SECTION" in _codes(res, "structure")
    fm2 = "title: T\nreportforge-template: bespoke\ndate: 2026-09-04\n"
    root2 = _write(tmp_path, "p-bespoke", fm2, "# Anything\n\nFreeform.\n")
    manifest_mod.import_dir(str(root2))
    res2 = engine.check_readiness("p-bespoke")
    struct = res2["categories"]["structure"]
    assert struct["pass"] is True  # info only, never blocks
    assert "STRUCT-NO-REQUIRED-LIST" in _codes(res2, "structure")
