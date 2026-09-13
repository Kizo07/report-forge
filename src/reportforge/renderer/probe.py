"""Toolchain compatibility probe (plan §4 Phase 1).

WARN-ONLY by design until one full snapshot cycle evidences per-family
version ranges (plan §5: a fail-closed probe would add a new render
failure mode before any evidence exists). Returns human-readable
warnings; the engine attaches them to the render result when non-empty.
"""

from __future__ import annotations


def render_probe(toolchain: dict) -> list[str]:
    """Best-effort warnings about the toolchain that is about to render."""
    warnings: list[str] = []
    quarto = toolchain.get("quarto")
    if not quarto:
        warnings.append("quarto version undetectable — render provenance is incomplete")
    for tool in ("poppler", "pandoc"):
        if toolchain.get(tool) is None:
            warnings.append(f"{tool} not found — previews/DOCX niceties may degrade")
    return warnings
