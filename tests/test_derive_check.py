"""Phase 0 gate: derived LEDGER template assets must never go stale.

The ledger families are generated from portfolio by
scripts/derive_ledger_templates.py; until Phase 2 moves derivation
file-to-file, --check (exit 0 = fresh) is the staleness gate and this
test is its enforcement point.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "derive_ledger_templates.py"


def test_derived_ledger_blocks_fresh():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, (
        f"derived LEDGER blocks stale — run scripts/derive_ledger_templates.py:\n"
        f"{result.stdout}\n{result.stderr}")
