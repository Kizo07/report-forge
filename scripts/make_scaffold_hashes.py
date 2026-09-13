#!/usr/bin/env python3
"""Scaffold-tree baselines for template-parity gating (robustness refactor
plan, Phase 2.5). Scaffolds one minimal project per template family in an
isolated temp REPORTS_DIR and records a sha256 over every produced file:

    tests/scaffold_hashes/<family>.json   {relpath: sha256}

This is the HTML-side backstop the PDF-ink parity gate cannot see (html
header, styles.scss, brand.yml all land here). Regenerate after a
DELIBERATE template change:
    .venv/bin/python scripts/make_scaffold_hashes.py [--only fam1,fam2]
"""

import argparse
import hashlib
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

FAMILIES = [
    "standard", "memo", "whitepaper", "modern", "studio",
    "portfolio-light", "portfolio-dark", "ledger-light", "ledger-dark",
    "bespoke",
]
OUT_DIR = REPO / "tests" / "scaffold_hashes"

# report.json embeds wall-clock timestamps (created/updated/revision_log);
# hash a normalized projection so the gate catches CONTENT drift only.
VOLATILE_MANIFEST_KEYS = {"created", "updated", "revision_log"}


def canonical_hash(path: Path) -> str:
    if path.name == "report.json":
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in VOLATILE_MANIFEST_KEYS:
            data.pop(key, None)
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hash(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            hashes[rel] = canonical_hash(p)
    return hashes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="comma-separated subset of families")
    args = parser.parse_args()
    families = args.only.split(",") if args.only else FAMILIES

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reports_dir = Path(_BASELINE_TMP)
    try:
        for family in families:
            slug = f"baseline-{family}"
            result = engine.scaffold_report(slug, template=family, formats=["html"])
            if not result.get("ok"):
                raise SystemExit(f"{family}: scaffold failed: {result.get('error')}")
            hashes = tree_hash(reports_dir / slug)
            # toolchain-independent: scaffold output must not vary with the
            # environment, so no toolchain block here — if it does vary,
            # that is exactly what this gate exists to catch.
            (OUT_DIR / f"{family}.json").write_text(
                json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"[{family}] {len(hashes)} files hashed")
    finally:
        shutil.rmtree(reports_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
