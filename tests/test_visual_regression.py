"""Visual-regression harness tests (Impl F).

scripts/visual_regression.py builds a page manifest (ordered contact-sheet
inputs + per-page sha256) from a report's page PNGs and --check compares
it against a recorded baseline. All fixtures are fake report dirs with
dummy PNGs — no Quarto render, no pdftoppm.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "visual_regression.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("visual_regression", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vr = _load_script()


def _png_bytes(color: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", (8, 8), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def fake_report(tmp_path: Path) -> Path:
    """Fake rendered report: previews tree with 3 dummy page PNGs."""
    pages = tmp_path / "fake" / "output" / "previews" / "r2" / "pages"
    pages.mkdir(parents=True)
    (tmp_path / "fake" / "index.qmd").write_text("---\ntitle: Fake\n---\n")
    (pages / "page-1.png").write_bytes(_png_bytes((200, 30, 30)))
    (pages / "page-2.png").write_bytes(_png_bytes((30, 200, 30)))
    (pages / "page-3.png").write_bytes(_png_bytes((30, 30, 200)))
    return tmp_path / "fake"


def test_build_manifest_lists_pages_in_order(fake_report: Path) -> None:
    manifest = vr.build_manifest(fake_report)
    assert manifest["report"] == "fake"
    assert manifest["revision"] == 2
    assert manifest["page_count"] == 3
    assert manifest["contact_sheet_inputs"] == [
        "output/previews/r2/pages/page-1.png",
        "output/previews/r2/pages/page-2.png",
        "output/previews/r2/pages/page-3.png",
    ]
    assert [p["page"] for p in manifest["pages"]] == [1, 2, 3]
    for entry in manifest["pages"]:
        data = (fake_report / entry["path"]).read_bytes()
        assert entry["bytes"] == len(data)
        import hashlib
        assert entry["sha256"] == hashlib.sha256(data).hexdigest()


def test_build_manifest_prefers_latest_revision(tmp_path: Path) -> None:
    root = tmp_path / "multi"
    for rev in ("r1", "r2"):
        pages = root / "output" / "previews" / rev / "pages"
        pages.mkdir(parents=True)
        (pages / "page-1.png").write_bytes(_png_bytes((10, 10, 10)))
    (root / "output" / "previews" / "r2" / "pages" / "page-2.png").write_bytes(
        _png_bytes((20, 20, 20)))
    manifest = vr.build_manifest(root)
    assert manifest["revision"] == 2
    assert manifest["page_count"] == 2


def test_build_manifest_single_page_fallback(tmp_path: Path) -> None:
    pages = tmp_path / "single" / "output" / "previews" / "r1" / "pages"
    pages.mkdir(parents=True)
    (pages / "page.png").write_bytes(_png_bytes((5, 5, 5)))
    manifest = vr.build_manifest(tmp_path / "single")
    assert manifest["page_count"] == 1
    assert manifest["pages"][0]["page"] == 1


def test_build_manifest_no_pages_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no page PNGs"):
        vr.build_manifest(tmp_path)


def test_check_passes_on_identical_baseline(fake_report: Path) -> None:
    manifest = vr.build_manifest(fake_report)
    baseline = json.loads(json.dumps(manifest))  # round-trip like a file
    verdict = vr.check_manifest(manifest, baseline)
    assert verdict["ok"] is True
    assert verdict["page_count_match"] is True
    assert verdict["mismatched_pages"] == []


def test_check_detects_hash_change(fake_report: Path) -> None:
    baseline = vr.build_manifest(fake_report)
    (fake_report / "output" / "previews" / "r2" / "pages"
     / "page-2.png").write_bytes(_png_bytes((99, 99, 99)))
    current = vr.build_manifest(fake_report)
    verdict = vr.check_manifest(current, baseline)
    assert verdict["ok"] is False
    assert verdict["page_count_match"] is True
    assert [m["page"] for m in verdict["mismatched_pages"]] == [2]


def test_check_detects_page_count_change(fake_report: Path) -> None:
    baseline = vr.build_manifest(fake_report)
    (fake_report / "output" / "previews" / "r2" / "pages"
     / "page-3.png").unlink()
    current = vr.build_manifest(fake_report)
    verdict = vr.check_manifest(current, baseline)
    assert verdict["ok"] is False
    assert verdict["page_count_match"] is False
    assert verdict["missing_pages"] == [3]


def test_check_cli_exit_codes(fake_report: Path, tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    manifest = vr.build_manifest(fake_report)
    vr.write_manifest(manifest, baseline_path)
    run = lambda *a: subprocess.run(
        [sys.executable, str(SCRIPT), str(fake_report), *a],
        capture_output=True, text=True)
    try:
        import reportforge  # noqa: F401
    except ImportError:
        pytest.skip("reportforge importable only under the repo venv")
    match = run("--check", str(baseline_path))
    assert match.returncode == 0, match.stderr
    (fake_report / "output" / "previews" / "r2" / "pages"
     / "page-1.png").write_bytes(_png_bytes((1, 2, 3)))
    drift = run("--check", str(baseline_path))
    assert drift.returncode == 1
    assert "page 1" in drift.stderr


def test_portfolio_header_source_generalised() -> None:
    """Portfolio-light owns a placeholder (not report-specific) header."""
    src = (REPO / "src" / "reportforge" / "templates" / "_assets"
           / "portfolio-light" / "portfolio-header.html").read_text(encoding="utf-8")
    for cls in ("rf-studio-header", "rf-title-frame", "rf-eyebrow",
                "rf-display-title", "rf-title-meta", "rf-deck", "rf-verdict"):
        assert cls in src
    for placeholder in ("<% title_html %>", "<% eyebrow_html %>",
                        "<% verdict_html %>", "<% date_html %>"):
        assert placeholder in src
    for report_specific in ("Tesla", "TSLA", "OVERWEIGHT", "420",
                            "QuantFlow", "2026-09-05"):
        assert report_specific not in src
    assert "tsla-12m-flagship-light" in src  # provenance pointer
