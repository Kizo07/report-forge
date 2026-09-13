"""Renderer error hierarchy (plan §4 Phase 1).

The seam raises these; the engine translates them into its public
`{"ok": False, "error": …}` dicts at the API edge so MCP/CLI consumers
never see raw exceptions.
"""

from __future__ import annotations


class RendererError(RuntimeError):
    """Base: an external rendering tool failed or is unavailable."""


class QuartoNotFoundError(RendererError):
    """Quarto binary absent from PATH."""


class ToolTimeoutError(RendererError):
    """An external tool exceeded its per-tool timeout."""

    def __init__(self, tool: str, timeout_s: int) -> None:
        super().__init__(f"{tool} timed out after {timeout_s}s")
        self.tool = tool
        self.timeout_s = timeout_s


class QuartoRenderError(RendererError):
    """`quarto render` exited nonzero or produced no output."""

    def __init__(self, fmt: str, log_tail: str = "", log_path: str | None = None) -> None:
        super().__init__(f"quarto render failed for format '{fmt}'")
        self.fmt = fmt
        self.log_tail = log_tail
        self.log_path = log_path


class ChromiumPrintError(RendererError):
    """Headless Chromium `--print-to-pdf` failed."""

    def __init__(self, log_tail: str = "") -> None:
        super().__init__("chromium print-to-pdf failed")
        self.log_tail = log_tail
