"""Renderer seam: the ONLY package in report-forge allowed to spawn
external processes (robustness refactor plan 2026-09-12, Phase 1).

Engine code composes these primitives; engine-level private wrappers
(`engine._quarto_version`, `engine._venv_python`, …) delegate here so
existing tests that monkeypatch those names keep working.

Error contract: primitives raise `RendererError` subclasses (notably
`ToolTimeoutError`); the engine translates them into its public
`{"ok": False, "error": …}` dicts at the API edge.
"""

from reportforge.renderer import errors, interpreters, lint, poppler, probe, quarto, toolchain
from reportforge.renderer.errors import (
    ChromiumPrintError,
    QuartoNotFoundError,
    QuartoRenderError,
    RendererError,
    ToolTimeoutError,
)

__all__ = [
    "errors",
    "toolchain",
    "quarto",
    "interpreters",
    "poppler",
    "lint",
    "probe",
    "RendererError",
    "QuartoNotFoundError",
    "QuartoRenderError",
    "ChromiumPrintError",
    "ToolTimeoutError",
]
