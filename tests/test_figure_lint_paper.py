"""Per-template paper checks for scripts/figure_lint.py.

The NVDA flagship (studio, 2026-09-19) shipped beige (#e5ddcc) charts on
near-white (#f8f7f3) pages and figure_lint passed: studio fell through to
the dark heuristic (no paper check at all). The lint must be paper-aware
per template — studio→white, portfolio→beige, ledger→ice — so a
mismatched set fails instead of passing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "figure_lint.py"

# Accent patch readable under both dark and light accent sets (within the
# TOL=60 window of each), so fixtures isolate the paper check rather than
# the accent check.
PATCH_RGB = (55, 155, 65)


def _fixture_project(root: Path, template: str, paper_hex: str) -> Path:
    from PIL import Image

    proj = root / f"lint-{template}"
    (proj / "charts").mkdir(parents=True)
    (proj / "index.qmd").write_text(
        "---\n"
        'title: "Probe"\n'
        f'reportforge-template: "{template}"\n'
        "---\n"
        "\n"
        "# Body\n"
        "\n"
        "Some text.\n"
        "\n"
        "![Green patch sample](charts/ex01.png){#fig-ex01 width=85%}\n",
        encoding="utf-8",
    )
    img = Image.new("RGB", (200, 140), paper_hex)
    img.paste(PATCH_RGB, (80, 50, 120, 90))
    img.save(proj / "charts" / "ex01.png")
    return proj


def _run_lint(proj: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(proj)],
        capture_output=True, text=True, timeout=120,
    )


def test_studio_beige_chart_fails_paper_check(tmp_path: Path) -> None:
    """The NVDA failure: beige charts on a white studio page must fail."""
    proj = _fixture_project(tmp_path, "studio", "#e5ddcc")
    run = _run_lint(proj)
    assert run.returncode == 1, run.stdout
    assert "paper" in run.stdout.lower()


def test_studio_white_chart_passes(tmp_path: Path) -> None:
    proj = _fixture_project(tmp_path, "studio", "#f8f7f3")
    run = _run_lint(proj)
    assert run.returncode == 0, run.stdout


def test_portfolio_light_beige_still_passes(tmp_path: Path) -> None:
    proj = _fixture_project(tmp_path, "portfolio-light", "#e5ddcc")
    run = _run_lint(proj)
    assert run.returncode == 0, run.stdout


def test_portfolio_light_white_chart_fails(tmp_path: Path) -> None:
    proj = _fixture_project(tmp_path, "portfolio-light", "#f8f7f3")
    run = _run_lint(proj)
    assert run.returncode == 1, run.stdout
    assert "paper" in run.stdout.lower()


def test_ledger_light_ice_passes_and_beige_fails(tmp_path: Path) -> None:
    ice = _fixture_project(tmp_path, "ledger-light", "#eef3f6")
    run = _run_lint(ice)
    assert run.returncode == 0, run.stdout
    beige = _fixture_project(tmp_path / "other", "ledger-light", "#e5ddcc")
    run = _run_lint(beige)
    assert run.returncode == 1, run.stdout
    assert "paper" in run.stdout.lower()
