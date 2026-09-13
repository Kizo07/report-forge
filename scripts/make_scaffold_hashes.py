#!/usr/bin/env python3
"""Scaffold-tree baselines for template-parity gating (robustness refactor
plan, Phase 2.5). Scaffolds one minimal project per registered template
(10 scaffold families + 9 domain bodies) in an isolated temp REPORTS_DIR
and records canonical hashes of every produced file:

    tests/scaffold_hashes/<template>.json   {relpath: sha256}

Hashing lives in the templates package (`templates.scaffold_tree_hash`):
report.json is projected without wall-clock timestamps, and scaffold
dates in .qmd/.html text are normalized so baselines do not expire at
midnight (Milestone B review, finding 1).

The generator pins the kernel/reference-doc environment exactly like the
parity-test fixture, so baselines are machine-independent (finding 3).

Regenerate after a DELIBERATE template change:
    .venv/bin/python scripts/make_scaffold_hashes.py [--only tpl1,tpl2]
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

# Isolate scaffolds from the repo tree — must be set BEFORE engine import.
_BASELINE_TMP = tempfile.mkdtemp(prefix="rf-scaffold-hashes-")
os.environ["REPORTFORGE_REPORTS_DIR"] = _BASELINE_TMP

from reportforge import engine  # noqa: E402
from reportforge import templates  # noqa: E402

FAMILIES = [
    "standard", "memo", "whitepaper", "modern", "studio",
    "portfolio-light", "portfolio-dark", "ledger-light", "ledger-dark",
    "bespoke",
]
DOMAIN_SLUGS = sorted(templates.DOMAIN_SLUGS.values())
OUT_DIR = REPO / "tests" / "scaffold_hashes"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="comma-separated subset of templates")
    args = parser.parse_args()
    templates_to_hash = args.only.split(",") if args.only else FAMILIES + DOMAIN_SLUGS

    # Pin the environment exactly like tests/test_scaffold_parity.py's
    # fixture, so baselines do not bake in machine-specific kernel or
    # reference-doc state (Milestone B review, finding 3).
    engine._ensure_reportforge_kernel = lambda: "reportforge"
    engine._default_reference_docx = lambda: None

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reports_dir = Path(_BASELINE_TMP)
    try:
        for template in templates_to_hash:
            slug = f"baseline-{template}"
            result = engine.scaffold_report(slug, template=template, formats=["html"])
            if not result.get("ok"):
                raise SystemExit(f"{template}: scaffold failed: {result.get('error')}")
            hashes = templates.scaffold_tree_hash(reports_dir / slug)
            (OUT_DIR / f"{template}.json").write_text(
                json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"[{template}] {len(hashes)} files hashed")
    finally:
        shutil.rmtree(reports_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
