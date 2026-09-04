"""Contract: alpha_engine exhibit builders work under the reportforge env.

reportforge_run_code inherits the MCP server env, whose PYTHONPATH includes
alpha_engine/src (see deer-flow extensions_config.json). This pins the agent
pattern: import builders from alpha_engine.viz in-report, style with
theme="quantflow-dark"/"quantflow-light" to match the page, save_figure()
PNGs into charts/, and metrics_markdown() for showtable-ready tables.
"""
from pathlib import Path

import pytest

AE_SRC = Path(__file__).resolve().parents[2] / "alpha_engine" / "src"

pytestmark = pytest.mark.skipif(
    not AE_SRC.is_dir(), reason="sibling alpha_engine checkout not present")

import sys  # noqa: E402

sys.path.insert(0, str(AE_SRC))

from reportforge import engine as rf_engine  # noqa: E402

from alpha_engine.viz import (  # noqa: E402
    QUANTFLOW_DARK,
    attribution_bars,
    comps_bars,
    event_timeline,
    metrics_markdown,
    price_technicals,
    save_figure,
    scenario_fan,
    waterfall_bridge,
)


def _series(n=120, seed=0):
    import numpy as np
    import pandas as pd

    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    px = pd.Series(
        100 * np.cumprod(1 + np.random.default_rng(seed).normal(0.001, 0.02, n)),
        index=idx, name="PX",
    )
    return px


def test_quantflow_dark_palette_identity():
    assert QUANTFLOW_DARK["paper_bg"] == "#0a0d12"
    assert QUANTFLOW_DARK["primary"] == "#c9a227"
    assert QUANTFLOW_DARK["secondary"] == "#56cfc4"


def test_flagship_builders_dark_theme():
    import pandas as pd

    px = _series()
    assert price_technicals(px, theme="quantflow-dark").layout.paper_bgcolor == \
        QUANTFLOW_DARK["paper_bg"]
    assert waterfall_bridge(["A", "B"], [10, -3],
                            theme="quantflow-dark").data
    proj = pd.DataFrame({"bear": [100, 95], "base": [100, 110],
                         "bull": [100, 125]})
    assert scenario_fan(proj, theme="quantflow-dark").data
    assert attribution_bars({"a": 1.5, "b": -0.5},
                            theme="quantflow-dark").data
    assert comps_bars({"A": 20.0, "B": 25.0}, metric_name="P/E",
                      highlight=["A"], theme="quantflow-dark").data
    events = pd.DataFrame({"date": ["2025-02-01"], "label": ["earnings"]})
    assert event_timeline(events, price=px, theme="quantflow-dark").data


def test_save_figure_png_roundtrip(tmp_path):
    out = save_figure(price_technicals(_series(), theme="quantflow-dark"),
                      tmp_path / "charts-test.png")
    assert out.is_file() and out.stat().st_size > 0


def test_metrics_markdown_showtable_ready():
    md = metrics_markdown({"sharpe": 1.42, "max_dd": -0.18})
    assert "| Metric | Value |" in md
    assert "sharpe" in md and "1.42" in md


def test_save_chart_colorway_derived_no_stock_blues():
    import plotly.graph_objects as go

    for name in ("quantflow-dark", "quantflow-light"):
        fig = go.Figure(go.Bar(x=["a"], y=[1]))
        rf_engine._apply_quantflow_plotly_template(fig, name)
        cw = list(fig.layout.template.layout.colorway)
        assert cw[0] == rf_engine.QUANTFLOW_PLOTLY_THEMES[name]["primary"]
        # stock plotly blue must never leak in (dark ramp's own #79c0ff
        # tail is canonical and fine on near-black, but not on paper)
        assert "#58a6ff" not in cw
        if name == "quantflow-light":
            assert "#79c0ff" not in cw


def test_plotly_mirror_matches_engine_palettes():
    from alpha_engine.viz import QUANTFLOW_THEMES

    for name, pal in QUANTFLOW_THEMES.items():
        mirror = rf_engine.QUANTFLOW_PLOTLY_THEMES[name]
        for key in ("paper_bg", "plot_bg", "font", "grid", "primary",
                    "secondary", "positive", "negative", "muted"):
            assert mirror[key] == pal[key], (name, key)
        assert mirror["ramp"] == pal["quantile_seq"], name


def test_round2_builders_and_caption(tmp_path):
    from alpha_engine.viz import (caption, price_levels, returns_dist,
                                  waterfall_bridge)

    px = _series()
    assert returns_dist(px.pct_change().dropna(),
                        theme="quantflow-light").data
    assert price_levels(px, {"support": 90.0, "resist": 130.0},
                        theme="quantflow-light").data
    fig = waterfall_bridge(["S", "a", "Sub", "b", "T"],
                           [100, 10, 110, 5, 115], totals=[2, 4],
                           theme="quantflow-light")
    assert list(fig.data[0].measure)[2] == "total"
    cap = caption(asof="2026-09-02", source="store")
    probe = price_technicals(px, theme="quantflow-light")
    out = save_figure(probe, tmp_path / "cap.png", caption_text=cap)
    assert out.is_file()
    assert any(a.text == cap for a in probe.layout.annotations)
