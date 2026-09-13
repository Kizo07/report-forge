#!/usr/bin/env python3
"""Identity-token drift guard (Phase 4b).

report-forge's QUANTFLOW_PLOTLY_THEMES (engine/_impl.py) are a deliberate
mirror of alpha_engine.viz QUANTFLOW_THEMES — alpha_engine is CANONICAL
for chart-facing colors; page tokens follow so engine-built exhibits sit
on report pages with no restyling. This script detects drift between the
two copies BEFORE a render ships mismatched charts.

Usage:
    .venv/bin/python scripts/check_token_drift.py [path-to-alpha_engine]

Exit 0 = in sync (or alpha_engine not found, nothing to compare);
exit 1 = drift detected (listed). Override the alpha_engine location with
the first argument or ALPHA_ENGINE_PATH (default: sibling checkout).
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from reportforge.engine._impl import QUANTFLOW_PLOTLY_THEMES  # noqa: E402

# alpha_engine name → report-forge name; quantile_seq is alpha's name for
# report-forge's ramp.
SHARED = {
    "quantflow-dark": "quantflow-dark",
    "quantflow-light": "quantflow-light",
    "ledger-dark": "ledger-dark",
    "ledger-light": "ledger-light",
}
RAMP_ALIAS = {"ramp": "quantile_seq"}
ALPHA_PALETTE_NAMES = {
    "QUANTFLOW_DARK", "QUANTFLOW_LIGHT", "LEDGER_DARK", "LEDGER_LIGHT",
}


def load_alpha_themes(alpha_root: Path) -> dict:
    """Extract the palette dict literals from alpha_engine.viz WITHOUT
    executing it (viz.py has relative imports and its own dependency
    graph; the palettes are pure literals, so ast.literal_eval is exact
    and dependency-free)."""
    import ast

    viz = alpha_root / "src" / "alpha_engine" / "viz.py"
    if not viz.is_file():
        viz = alpha_root / "alpha_engine" / "viz.py"
    if not viz.is_file():
        raise FileNotFoundError(f"alpha_engine viz.py not found under {alpha_root}")
    tree = ast.parse(viz.read_text(encoding="utf-8"))
    literals: dict[str, dict] = {}
    themes_map: dict = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name == "QUANTFLOW_THEMES":
                if isinstance(node.value, ast.Dict):
                    themes_map = {
                        k.value: v.id
                        for k, v in zip(node.value.keys, node.value.values)
                        if isinstance(k, ast.Constant) and isinstance(v, ast.Name)
                    }
                continue
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError, SyntaxError):
                continue
            if name in ALPHA_PALETTE_NAMES:
                literals[name] = value
                # {"quantflow-dark": QUANTFLOW_DARK, ...} — values are name
                # references, not literals; extract them positionally.
                if isinstance(node.value, ast.Dict):
                    themes_map = {
                        k.value: v.id
                        for k, v in zip(node.value.keys, node.value.values)
                        if isinstance(k, ast.Constant) and isinstance(v, ast.Name)
                    }
    return {theme: literals[pal_name]
            for theme, pal_name in themes_map.items()
            if pal_name in literals}


def normalize_hex(value: str) -> str:
    return value.strip().lower()


# alpha-only keys report-forge intentionally does not mirror (its plotly
# template never reads them; alpha's "border" always equals "grid").
ALLOWED_ALPHA_ONLY_KEYS = {"border"}


def check(alpha_root: Path) -> tuple[list[str], dict]:
    """Compare EVERY shared palette key (ramp via its alias) between the
    two mirrors. -> (drift list, coverage report)."""
    alpha_themes = load_alpha_themes(alpha_root)
    drift: list[str] = []
    compared: dict[str, list[str]] = {}
    for alpha_name, rf_name in SHARED.items():
        alpha_pal = alpha_themes.get(alpha_name)
        rf_pal = QUANTFLOW_PLOTLY_THEMES.get(rf_name)
        if alpha_pal is None or rf_pal is None:
            drift.append(f"{rf_name}: palette missing on one side "
                         f"(alpha={alpha_pal is not None}, reportforge={rf_pal is not None})")
            continue
        compared[rf_name] = []
        for alpha_key, alpha_value in alpha_pal.items():
            if alpha_key in ALLOWED_ALPHA_ONLY_KEYS:
                continue
            rf_key = next((r for r, a in RAMP_ALIAS.items() if a == alpha_key),
                          alpha_key)
            if rf_key not in rf_pal:
                drift.append(f"{rf_name}.{rf_key}: missing (alpha has {alpha_key}={alpha_value!r})")
                continue
            compared[rf_name].append(rf_key)
            if isinstance(alpha_value, list):
                a_cmp = [normalize_hex(v) for v in alpha_value]
                r_cmp = [normalize_hex(v) for v in rf_pal[rf_key]]
                if a_cmp != r_cmp:
                    drift.append(f"{rf_name}.{rf_key}: {r_cmp} != alpha {a_cmp}")
            elif normalize_hex(str(alpha_value)) != normalize_hex(str(rf_pal[rf_key])):
                drift.append(
                    f"{rf_name}.{rf_key}: {rf_pal[rf_key]} != alpha {alpha_value} ({alpha_key})")
    return drift, compared


def main() -> int:
    alpha_root = Path(sys.argv[1] if len(sys.argv) > 1
                      else os.environ.get("ALPHA_ENGINE_PATH",
                                          REPO.parent / "alpha_engine"))
    if not Path(alpha_root).exists():
        print(f"check_token_drift: alpha_engine not found at {alpha_root} — nothing to compare")
        return 0
    drift, compared = check(Path(alpha_root))
    if drift:
        print("check_token_drift: DRIFT detected (report-forge vs alpha_engine.viz):")
        for d in drift:
            print(f"  {d}")
        return 1
    coverage = ", ".join(
        f"{name}[{len(keys)} keys]" for name, keys in compared.items())
    print(f"check_token_drift: in sync with alpha_engine.viz (compared: {coverage}; "
          f"alpha-only keys allowed: {sorted(ALLOWED_ALPHA_ONLY_KEYS)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
