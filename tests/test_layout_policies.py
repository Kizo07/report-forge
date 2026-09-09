"""Milestone C task C-7 — RF-10 table/readability layout policies (subset)."""

from __future__ import annotations

from pathlib import Path

from reportforge import engine

FM = "title: Layout Probe\nreportforge-template: bespoke\ndate: 2026-09-08\n"


def _layout(monkeypatch, tmp_path: Path, body: str, slug: str = "lay-probe"):
    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    res = engine.scaffold_report(
        slug, template="bespoke", formats=["html"],
        frontmatter_yaml=FM, body=body)
    assert res["ok"] is True, res
    return Path(res["path"])


def _exhibit(slug: str, eid: str, alt: str = "", overwrite: bool = False):
    res = engine.register_exhibit(slug, exhibit_id=eid, title=eid,
                                  file=None, alt=alt, overwrite=overwrite)
    assert res["ok"] is True, res


def _pres(res):
    return [(i["code"], i["severity"])
            for i in res["categories"]["presentation"]["issues"]]


def test_compact_figure_has_no_layout_rules(tmp_path, monkeypatch):
    """C-7: default-width figures with captions and alts are clean."""
    _layout(monkeypatch, tmp_path,
            "# T\n\n![Rev trend](figures/rev.png){#fig-rev}\n")
    _exhibit("lay-probe", "fig-rev", alt="Revenue line, 2024-2026")
    codes = [c for c, _ in _pres(engine.check_readiness("lay-probe"))]
    assert "PRES-ALT-MISSING" not in codes
    assert "PRES-CAP-MISSING" not in codes


def test_complex_figure_requires_caption(tmp_path, monkeypatch):
    """C-7: full-width (complex) figures must carry an embed caption."""
    _layout(monkeypatch, tmp_path,
            "# T\n\n![](figures/cmp.png){#fig-cmp width=75%}\n")
    _exhibit("lay-probe", "fig-cmp", alt="Complex chart")
    codes = [c for c, _ in _pres(engine.check_readiness("lay-probe"))]
    assert "PRES-CAP-MISSING" in codes
    assert "PRES-ALT-MISSING" not in codes  # not wide: alt not demanded


def test_wide_figure_requires_alt(tmp_path, monkeypatch):
    """C-7: wide figures (width>=90%) must carry exhibit alt text."""
    _layout(monkeypatch, tmp_path,
            "# T\n\n![Wide view](figures/wide.png){#fig-wide width=95%}\n")
    _exhibit("lay-probe", "fig-wide")
    assert ("PRES-ALT-MISSING", "warning") in _pres(
        engine.check_readiness("lay-probe"))
    # Alt cures it (overwrite path).
    _exhibit("lay-probe", "fig-wide", alt="Wide bars", overwrite=True)
    codes = [c for c, _ in _pres(engine.check_readiness("lay-probe"))]
    assert "PRES-ALT-MISSING" not in codes


def test_ncol_comparison_counts_as_wide(tmp_path, monkeypatch):
    _layout(monkeypatch, tmp_path,
            "# T\n\n![Grid](figures/grid.png){#fig-grid layout-ncol=2}\n")
    _exhibit("lay-probe", "fig-grid")
    assert ("PRES-ALT-MISSING", "warning") in _pres(
        engine.check_readiness("lay-probe"))


def test_unregistered_figures_skip_policy_checks(tmp_path, monkeypatch):
    """C-7: an unregistered figure already errors (EXHIBIT-UNREGISTERED) —
    policy warnings must not pile on."""
    _layout(monkeypatch, tmp_path,
            "# T\n\n![Ghost](figures/g.png){#fig-ghost width=95%}\n")
    codes = [c for c, _ in _pres(engine.check_readiness("lay-probe"))]
    assert "PRES-ALT-MISSING" not in codes
    assert "PRES-CAP-MISSING" not in codes


def test_appendix_must_be_unnumbered(tmp_path, monkeypatch):
    _layout(monkeypatch, tmp_path, "# T\n\n# Appendix {.appendix}\n")
    assert ("PRES-APPENDIX-NUMBERED", "warning") in _pres(
        engine.check_readiness("lay-probe"))


def test_unnumbered_appendix_is_clean(tmp_path, monkeypatch):
    _layout(monkeypatch, tmp_path,
            "# T\n\n# Appendix {.appendix .unnumbered}\n")
    codes = [c for c, _ in _pres(engine.check_readiness("lay-probe"))]
    assert "PRES-APPENDIX-NUMBERED" not in codes
