"""Template-parity gate (robustness refactor plan, Phase 0 baseline /
Phase 2 extraction). Compares a fresh scaffold+render of each template
family against the committed baseline in tests/render_baselines/.

Opt-in because it runs real Quarto renders for all 10 families:

    RF_PARITY=1 .venv/bin/python -m pytest tests/test_render_parity.py

Parity = equal page count + per-page ink within ±2% relative of baseline,
on the same poppler raster (version recorded in each baseline JSON).
Regenerate baselines only after a DELIBERATE template/toolchain change:
    .venv/bin/python scripts/make_render_baselines.py
"""

import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

from reportforge import engine, templates


@pytest.fixture
def isolated_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    monkeypatch.setattr(engine, "REPORTS_DIR", reports)
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "reportforge")
    monkeypatch.setattr(engine, "_default_reference_docx", lambda: None)
    return reports

BASELINE_DIR = Path(__file__).resolve().parent / "render_baselines"
FAMILIES = [
    "standard", "memo", "whitepaper", "modern", "studio",
    "portfolio-light", "portfolio-dark", "ledger-light", "ledger-dark",
    "bespoke",
]
REL_INK_TOLERANCE = 0.02

pytestmark = pytest.mark.skipif(
    not os.environ.get("RF_PARITY"),
    reason="real-render parity gate; run with RF_PARITY=1",
)


def _ink(pdf: Path) -> list[float]:
    spec = importlib.util.spec_from_file_location(
        "make_render_baselines",
        Path(__file__).resolve().parent.parent / "scripts" / "make_render_baselines.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.page_ink_fractions(pdf)


def _baseline(family: str) -> dict:
    path = BASELINE_DIR / f"{family}.json"
    if not path.is_file():
        pytest.fail(f"missing baseline {path} — run scripts/make_render_baselines.py")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("family", FAMILIES)
def test_family_render_parity(isolated_reports, family: str):
    baseline = _baseline(family)
    # Same slug as scripts/make_render_baselines.py: the slug feeds the
    # default title, so a different name would legitimately change the ink.
    slug = f"baseline-{family}"
    result = engine.scaffold_report(slug, template=family, formats=["pdf"])
    assert result["ok"], result

    # Input parity: the scaffolded source must be byte-identical to the
    # baseline's before we even compare output ink.
    qmd = isolated_reports / slug / "index.qmd"
    # date-normalized on both sides: the scaffold embeds today's date
    qmd_sha = hashlib.sha256(
        templates._normalize_scaffold_text(
            qmd.read_text(encoding="utf-8")).encode("utf-8")).hexdigest()
    assert qmd_sha == baseline["index_qmd_sha256"], (
        f"{family}: scaffolded index.qmd drifted from the baseline source")

    rendered = engine.render_report(slug, formats=["pdf"])
    assert rendered["ok"], rendered

    pdf = isolated_reports / slug / "output" / "index.pdf"
    ink = _ink(pdf)

    assert len(ink) == baseline["pages"], (
        f"{family}: page count drifted — {len(ink)}pp vs baseline {baseline['pages']}pp")
    for i, (now, was) in enumerate(zip(ink, baseline["ink_per_page"])):
        if was == 0:
            assert now == 0, f"{family} p{i + 1}: ink {now} vs baseline 0"
            continue
        drift = abs(now - was) / was
        assert drift <= REL_INK_TOLERANCE, (
            f"{family} p{i + 1}: ink {now:.4f} vs baseline {was:.4f} "
            f"({drift:.1%} > {REL_INK_TOLERANCE:.0%})")
