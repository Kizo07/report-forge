"""Scaffold-parity gate (robustness refactor plan, Phase 2.5).

Scaffolds every registered template (10 scaffold families + 9 domain
bodies) and compares each produced file's canonical hash against the
committed baseline in tests/scaffold_hashes/. This catches scaffold-
output drift the PDF-ink parity gate cannot see (HTML header,
styles.scss, brand.yml, domain bodies…).

Hashing is `templates.scaffold_tree_hash`: report.json loses its
wall-clock timestamps, scaffold dates in text files are normalized, so
baselines gate content only.

Scaffolding is fast (no Quarto render), so this runs in the default
suite. Regenerate baselines only after a DELIBERATE template change:
    .venv/bin/python scripts/make_scaffold_hashes.py
"""

import json
from pathlib import Path

import pytest

from reportforge import engine, templates

FAMILIES = [
    "standard", "memo", "whitepaper", "modern", "studio",
    "portfolio-light", "portfolio-dark", "ledger-light", "ledger-dark",
    "bespoke",
]
DOMAIN_SLUGS = sorted(templates.DOMAIN_SLUGS.values())
BASELINE_DIR = Path(__file__).resolve().parent / "scaffold_hashes"


@pytest.fixture
def isolated_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    monkeypatch.setattr(engine, "REPORTS_DIR", reports)
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "reportforge")
    monkeypatch.setattr(engine, "_default_reference_docx", lambda: None)
    return reports


def _baseline(template: str) -> dict[str, str]:
    path = BASELINE_DIR / f"{template}.json"
    if not path.is_file():
        pytest.fail(f"missing baseline {path} — run scripts/make_scaffold_hashes.py")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("template", FAMILIES + DOMAIN_SLUGS)
def test_scaffold_matches_baseline(isolated_reports, template: str):
    baseline = _baseline(template)

    slug = f"baseline-{template}"  # same slug as the generator: slug → title
    result = engine.scaffold_report(slug, template=template, formats=["html"])
    assert result["ok"], result

    now = templates.scaffold_tree_hash(isolated_reports / slug)
    missing = sorted(set(baseline) - set(now))
    added = sorted(set(now) - set(baseline))
    changed = sorted(k for k in set(baseline) & set(now)
                     if baseline[k] != now[k])
    problems = ( [f"missing file: {p}" for p in missing]
               + [f"unexpected file: {p}" for p in added]
               + [f"changed content: {p}" for p in changed] )
    assert not problems, f"{template}: scaffold drifted from baseline\n" + "\n".join(problems)
