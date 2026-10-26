#!/usr/bin/env python3
"""Visual-regression harness: page-manifest build + baseline check.

Given a rendered report dir (or scaffold tmp report), this produces the
contact-sheet input list — the ordered page PNGs — and a manifest JSON of
pages (page count + per-page sha256). Page PNGs come from the existing
`engine.render_preview` machinery; this script never reimplements
rendering (no pdftoppm calls, no PDF raster code).

Two modes:

  Build:   visual_regression.py <report> [--render] [--out manifest.json]
           Collects page PNGs (rendering previews first with --render),
           writes the manifest, and prints the contact-sheet input list
           (paths relative to the report dir, one per line).

  Check:   visual_regression.py <report> --check baselines.json [--render]
           Rebuilds the manifest and compares page count + file hashes
           against the recorded baseline. Exit 0 on match, 1 on drift,
           2 on usage/resolution errors.

<report> is a project slug (resolved under REPORTFORGE_REPORTS_DIR or
--reports-dir) or a path to the report directory.

Manifest schema:
  {"report": str, "revision": int|null, "page_count": int,
   "contact_sheet_inputs": [relpath, ...],
   "pages": [{"page": int, "path": relpath, "bytes": int, "sha256": hex}]}
Paths are report-dir-relative (never host-absolute).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from reportforge import engine  # noqa: E402

PAGE_RE = re.compile(r"page-(\d+)\.png$")
REVISION_RE = re.compile(r"r(\d+)$")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _numbered(pngs: list[Path]) -> list[tuple[int, Path]]:
    numbered = []
    for p in pngs:
        m = PAGE_RE.search(p.name)
        if m:
            numbered.append((int(m.group(1)), p))
    return sorted(numbered)


def collect_page_pngs(report_dir: Path) -> tuple[list[Path], int | None]:
    """Ordered page PNGs under a report dir + their preview revision.

    Primary layout is the render_preview output tree
    ``output/previews/r<rev>/pages/page-<n>.png`` (latest revision wins).
    A bare ``pages/`` dir or a dir holding ``page-*.png`` directly is also
    accepted so scaffold-tmp and fixture reports work without a render.
    """
    report_dir = report_dir.resolve()
    previews = report_dir / "output" / "previews"
    candidates: list[tuple[int | None, Path]] = []
    if previews.is_dir():
        for rev_dir in sorted(previews.iterdir()):
            pages = rev_dir / "pages"
            if not pages.is_dir():
                continue
            m = REVISION_RE.search(rev_dir.name)
            candidates.append((int(m.group(1)) if m else None, pages))
    if not candidates:
        for fallback in (report_dir / "pages", report_dir):
            if any(fallback.glob("page-*.png")) or (fallback / "page.png").is_file():
                candidates.append((None, fallback))
                break
    if not candidates:
        raise ValueError(f"no page PNGs found under {report_dir}")
    # Latest stamped revision first; unstamped fallbacks sort last.
    candidates.sort(key=lambda c: (c[0] is None, c[0] or 0), reverse=True)
    revision, pages_dir = candidates[0]
    numbered = _numbered(list(pages_dir.glob("page-*.png")))
    if not numbered and (pages_dir / "page.png").is_file():
        # poppler names single-page output <prefix>.png (no page number).
        numbered = [(1, pages_dir / "page.png")]
    if not numbered:
        raise ValueError(f"no page PNGs found under {report_dir}")
    return [p for _, p in numbered], revision


def build_manifest(report_dir: Path, *, report: str | None = None) -> dict:
    """Manifest (page count + per-page hashes) for a report's page PNGs."""
    report_dir = report_dir.resolve()
    pages, revision = collect_page_pngs(report_dir)
    entries = []
    for path in pages:
        m = PAGE_RE.search(path.name)
        entries.append({
            "page": int(m.group(1)) if m else 1,
            "path": path.relative_to(report_dir).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    inputs = [e["path"] for e in entries]
    return {
        "report": report or report_dir.name,
        "revision": revision,
        "page_count": len(entries),
        "contact_sheet_inputs": inputs,
        "pages": entries,
    }


def write_manifest(manifest: dict, path: Path) -> Path:
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def check_manifest(manifest: dict, baseline: dict) -> dict:
    """Compare page count + per-page hashes against a recorded baseline."""
    base_pages = {p["page"]: p for p in baseline.get("pages", [])}
    cur_pages = {p["page"]: p for p in manifest.get("pages", [])}
    mismatches = [
        {"page": n, "expected": base_pages[n]["sha256"],
         "actual": cur_pages[n]["sha256"]}
        for n in sorted(set(base_pages) & set(cur_pages))
        if base_pages[n].get("sha256") != cur_pages[n].get("sha256")
    ]
    missing = sorted(set(base_pages) - set(cur_pages))
    extra = sorted(set(cur_pages) - set(base_pages))
    count_ok = manifest.get("page_count") == baseline.get("page_count")
    ok = count_ok and not mismatches and not missing and not extra
    return {
        "ok": ok,
        "page_count": manifest.get("page_count"),
        "baseline_page_count": baseline.get("page_count"),
        "page_count_match": count_ok,
        "mismatched_pages": mismatches,
        "missing_pages": missing,
        "extra_pages": extra,
    }


def resolve_report(report: str, reports_dir: Path | None = None) -> tuple[Path, str]:
    """Resolve <report> slug-or-path to (report_dir, slug)."""
    as_path = Path(report).expanduser()
    if as_path.is_dir() and (as_path / "index.qmd").is_file():
        return as_path.resolve(), as_path.resolve().name
    root = reports_dir or Path(
        os.environ.get("REPORTFORGE_REPORTS_DIR", str(engine.REPORTS_DIR)))
    candidate = (root / report.strip("/")).resolve()
    if not candidate.is_dir():
        raise ValueError(f"report not found: {report} (looked in {root})")
    return candidate, report.strip("/")


def ensure_previews(slug: str, reports_dir: Path | None = None,
                    revision: int | None = None) -> dict:
    """Render preview page PNGs via the existing engine machinery.

    Thin wrapper over engine.render_preview — the harness never shells
    out to pdftoppm itself.
    """
    if reports_dir is not None:
        engine.REPORTS_DIR = Path(reports_dir)
    return engine.render_preview(slug, revision=revision)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build or check a visual-regression page manifest.")
    parser.add_argument("report", help="project slug or report directory")
    parser.add_argument("--reports-dir", help="reports root (slug lookup)")
    parser.add_argument("--render", action="store_true",
                        help="run engine.render_preview first")
    parser.add_argument("--out", default=None,
                        help="manifest output path "
                             "(default: <report>/visual-manifest.json)")
    parser.add_argument("--check", default=None, metavar="BASELINE.json",
                        help="compare against a recorded baseline manifest")
    parser.add_argument("--quiet", action="store_true",
                        help="print only the check verdict / manifest path")
    args = parser.parse_args(argv)

    reports_dir = Path(args.reports_dir).expanduser() if args.reports_dir else None
    try:
        report_dir, slug = resolve_report(args.report, reports_dir)
    except ValueError as exc:
        print(f"visual_regression: {exc}", file=sys.stderr)
        return 2

    if args.render:
        render_root = reports_dir
        if render_root is None and Path(args.report).expanduser().is_dir():
            # Report given as a path: its parent is the reports root.
            render_root = report_dir.parent
        result = ensure_previews(slug, render_root)
        if not result.get("ok"):
            print(f"visual_regression: render_preview failed: "
                  f"{result.get('error')}", file=sys.stderr)
            return 2

    try:
        manifest = build_manifest(report_dir, report=slug)
    except ValueError as exc:
        print(f"visual_regression: {exc}", file=sys.stderr)
        return 2

    if args.check:
        try:
            baseline = json.loads(Path(args.check).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"visual_regression: cannot read baseline "
                  f"{args.check}: {exc}", file=sys.stderr)
            return 2
        verdict = check_manifest(manifest, baseline)
        if verdict["ok"]:
            print(f"visual_regression: MATCH "
                  f"({manifest['page_count']} pages, {manifest['report']})")
            return 0
        print(f"visual_regression: DRIFT in {manifest['report']}: "
              f"pages {verdict['page_count']} "
              f"(baseline {verdict['baseline_page_count']})", file=sys.stderr)
        for m in verdict["mismatched_pages"]:
            print(f"  page {m['page']}: hash changed "
                  f"{m['expected'][:12]} -> {m['actual'][:12]}", file=sys.stderr)
        for n in verdict["missing_pages"]:
            print(f"  page {n}: missing vs baseline", file=sys.stderr)
        for n in verdict["extra_pages"]:
            print(f"  page {n}: extra vs baseline", file=sys.stderr)
        return 1

    out = Path(args.out).expanduser() if args.out else report_dir / "visual-manifest.json"
    write_manifest(manifest, out)
    if not args.quiet:
        for rel in manifest["contact_sheet_inputs"]:
            print(rel)
    print(f"visual_regression: wrote {out} "
          f"({manifest['page_count']} pages)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
