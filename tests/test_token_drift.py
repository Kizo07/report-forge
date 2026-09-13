"""Identity-token drift guard (Phase 4b).

alpha_engine.viz is CANONICAL for chart-facing palettes; report-forge's
QUANTFLOW_PLOTLY_THEMES mirror them so engine-built exhibits sit on report
pages without restyling. This test runs the drift check whenever the
alpha_engine checkout sits next to report-forge (or ALPHA_ENGINE_PATH is
set) and skips otherwise — a lone report-forge checkout has nothing to
compare against.
"""

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
ALPHA_ROOT = Path(os.environ.get(
    "ALPHA_ENGINE_PATH", REPO.parent / "alpha_engine"))

pytestmark = pytest.mark.skipif(
    not (ALPHA_ROOT.exists() and (
        (ALPHA_ROOT / "src" / "alpha_engine" / "viz.py").is_file()
        or (ALPHA_ROOT / "alpha_engine" / "viz.py").is_file())),
    reason=f"alpha_engine checkout not found at {ALPHA_ROOT}",
)


def _load_check():
    spec_path = REPO / "scripts" / "check_token_drift.py"
    spec = __import__("importlib").util.spec_from_file_location(
        "check_token_drift", spec_path)
    module = __import__("importlib").util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reportforge_tokens_match_alpha_engine():
    module = _load_check()
    drift, coverage = module.check(ALPHA_ROOT)
    assert len(coverage) == len(module.SHARED), (
        f"coverage narrowed: compared {sorted(coverage)}")
    assert not drift, (
        "identity tokens drifted from alpha_engine.viz (canonical):\n"
        + "\n".join(drift)
        + "\nFix reportforge/engine/_impl.py QUANTFLOW_PLOTLY_THEMES "
        "(or alpha_engine) — page tokens must follow the chart palette.")


def test_all_shared_palettes_present_on_both_sides():
    module = _load_check()
    alpha_themes = module.load_alpha_themes(ALPHA_ROOT)
    from reportforge.engine._impl import QUANTFLOW_PLOTLY_THEMES
    for alpha_name, rf_name in module.SHARED.items():
        assert alpha_name in alpha_themes, f"alpha_engine lost {alpha_name}"
        assert rf_name in QUANTFLOW_PLOTLY_THEMES, \
            f"report-forge lost {rf_name}; re-sync with alpha_engine.viz"
