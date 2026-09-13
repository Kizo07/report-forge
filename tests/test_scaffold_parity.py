"""Scaffold-parity gate (robustness refactor plan, Phase 2.5).

Scaffolds each template family and compares every produced file's hash
against the committed baseline in tests/scaffold_hashes/. This catches
scaffold-output drift that the PDF-ink parity gate cannot see (HTML
header, styles.scss, brand.yml, domain bodies…).

report.json is hashed via a normalized projection (timestamps stripped)
so the gate catches content drift, not wall-clock noise.

Scaffolding is fast (no Quarto render), so this runs in the default
suite. Regenerate baselines only after a DELIBERATE template change:
    .venv/bin/python scripts/make_scaffold_hashes.py
"""

import importlib.util
import json
from pathlib import Path

import pytest

from reportforge import engine

FAMILIES = [
    "standard", "memo", "whitepaper", "modern", "studio",
    "portfolio-light", "portfolio-dark", "ledger-light", "ledger-dark",
    "bespoke",
]
BASELINE_DIR = Path(__file__).resolve().parent / "scaffold_hashes"


@pytest.fixture
def isolated_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    monkeypatch.setattr(engine, "REPORTS_DIR", reports)
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "reportforge")
    monkeypatch.setattr(engine, "_default_reference_docx", lambda: None)
    return reports


def _tree_hash(root: Path) -> dict[str, str]:
    spec = importlib.util.spec_from_file_location(
        "make_scaffold_hashes",
        Path(__file__).resolve().parent.parent / "scripts" / "make_scaffold_hashes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.tree_hash(root)


def _baseline(family: str) -> dict[str, str]:
    path = BASELINE_DIR / f"{family}.json"
    if not path.is_file():
        pytest.fail(f"missing baseline {path} — run scripts/make_scaffold_hashes.py")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("family", FAMILIES)
def test_scaffold_matches_baseline(isolated_reports, family: str):
    baseline = _baseline(family)

    slug = f"baseline-{family}"  # same slug as the generator: slug → title
    result = engine.scaffold_report(slug, template=family, formats=["html"])
    assert result["ok"], result

    now = _tree_hash(isolated_reports / slug)
    missing = sorted(set(baseline) - set(now))
    added = sorted(set(now) - set(baseline))
    changed = sorted(k for k in set(baseline) & set(now)
                     if baseline[k] != now[k])
    problems = ( [f"missing file: {p}" for p in missing]
               + [f"unexpected file: {p}" for p in added]
               + [f"changed content: {p}" for p in changed] )
    assert not problems, f"{family}: scaffold drifted from baseline\n" + "\n".join(problems)
