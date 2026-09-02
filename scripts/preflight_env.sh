#!/usr/bin/env bash
# report-forge WS-6 pre-flight: validate the execution environment BEFORE the
# first render, so missing ipykernel/pandas etc. surface as an actionable
# error instead of a mysterious Quarto kernel failure mid-run.
#
# Usage: scripts/preflight_env.sh
# Exit code 0 = ready, non-zero = a requirement is missing (details printed).
set -u

fail=0

# Which python does report-forge use? Same resolution order as engine._venv_python:
# 1. REPORTFORGE_PYTHON  2. active venv  3. repo .venv
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -n "${REPORTFORGE_PYTHON:-}" ]]; then
  PY="$REPORTFORGE_PYTHON"
  echo "interpreter: REPORTFORGE_PYTHON=$PY"
elif [[ -n "${VIRTUAL_ENV:-}" ]]; then
  PY="$VIRTUAL_ENV/bin/python"
  echo "interpreter: active venv -> $PY"
else
  PY="$REPO_ROOT/.venv/bin/python"
  echo "interpreter: repo .venv -> $PY"
fi

if [[ ! -x "$PY" ]]; then
  echo "FAIL: interpreter not found or not executable: $PY"
  exit 1
fi

echo "python: $("$PY" -c 'import sys; print(sys.version.split()[0])')"

# Required: jupyter stack for Quarto execution, quant stack for run_code.
REQUIRED=(jupyter_client ipykernel nbformat plotly)
QUANT=(pandas pyarrow numpy statsmodels)
OPTIONAL=(matplotlib kaleido scipy)

check() {
  local mod="$1" label="$2" optional="${3:-no}"
  if "$PY" -c "import $mod" >/dev/null 2>&1; then
    local ver
    ver="$("$PY" -c "import $mod; print(getattr($mod, '__version__', '?'))" 2>/dev/null)"
    echo "  ok: $mod ($ver)"
  elif [[ "$optional" == "yes" ]]; then
    echo "  optional-missing: $mod ($label)"
  else
    echo "  MISSING: $mod ($label)"
    fail=1
  fi
}

echo "required:"
for m in "${REQUIRED[@]}"; do check "$m" "quarto kernel execution"; done
echo "quant stack (for run_code / code chunks):"
for m in "${QUANT[@]}"; do check "$m" "factor/backtest compute"; done
echo "optional:"
for m in "${OPTIONAL[@]}"; do check "$m" "charts/export" yes; done

# Quarto CLI must be on PATH.
if command -v quarto >/dev/null 2>&1; then
  echo "quarto: $(quarto --version)"
else
  echo "  MISSING: quarto CLI on PATH"
  fail=1
fi

# Reportforge kernel must be installable (the engine does this at scaffold
# time, but verify the mechanism works).
if "$PY" -c "import ipykernel" >/dev/null 2>&1; then
  if "$PY" -m ipykernel install --user --name reportforge --display-name reportforge >/dev/null 2>&1; then
    echo "jupyter kernel 'reportforge': installed"
  else
    echo "  FAIL: could not install jupyter kernel 'reportforge'"
    fail=1
  fi
fi

# Chromium for pdf-web (optional but reported).
CHROMIUM="${REPORTFORGE_CHROMIUM:-}"
if [[ -z "$CHROMIUM" ]]; then
  CHROMIUM="$(command -v chromium || command -v chromium-browser || command -v google-chrome || true)"
fi
if [[ -n "$CHROMIUM" && -x "$CHROMIUM" ]]; then
  echo "chromium (pdf-web): $CHROMIUM"
else
  echo "  note: no chromium found — pdf-web format will fail until installed or REPORTFORGE_CHROMIUM is set"
fi

if [[ "$fail" -ne 0 ]]; then
  echo ""
  echo "PRE-FLIGHT FAILED — install missing packages into $PY, e.g.:"
  echo "  uv pip install --python $PY <missing packages>"
  exit 1
fi

echo ""
echo "PRE-FLIGHT OK"
