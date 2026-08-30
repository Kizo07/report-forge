"""ReportForge MCP server: Quarto-backed multi-format report generation."""

from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP

from reportforge.engine import list_templates, render_report, save_chart, scaffold_report

mcp = FastMCP(
    "reportforge",
    instructions=(
        "Generate beautiful multi-format reports (HTML, PDF via Typst, DOCX) from "
        "Quarto .qmd sources with unified branding. Workflow: scaffold_report to create "
        "a report project, edit the index.qmd (or have the calling agent write content "
        "into it), optionally save_chart for plotly figures, then render_report to "
        "produce final documents."
    ),
)


@mcp.tool
def reportforge_list_templates() -> list[dict[str, Any]]:
    """List available report templates with their default formats and layout options."""
    return list_templates()


@mcp.tool
def reportforge_scaffold_report(
    slug: str,
    title: str = "",
    subtitle: str = "",
    author: str = "",
    abstract: str = "Add a short abstract here.",
    template: str = "standard",
    formats: list[str] | None = None,
    firm: str = "",
    kpis: list[dict[str, str]] | None = None,
    confidential_mark: str = "",
) -> dict[str, Any]:
    """Create a new branded report project under ~/Documents/report-forge/reports/<slug>/.

    Args:
        slug: Short identifier used as directory name (kebab-case recommended).
        title: Report title (defaults to prettified slug).
        subtitle: Optional subtitle.
        author: Author name or team.
        abstract: One-paragraph summary placed in the front matter.
        template: 'standard' (full report, toc+numbered sections, html/pdf/docx),
            'memo' (short memo, html/pdf), 'whitepaper' (hedge-fund-style
            institutional white paper: key takeaways, investment thesis,
            framework, exhibit-driven analysis, portfolio implications, risk
            factors; figures and tables labeled 'Exhibit N'; letter pagesize,
            title page, toc+numbered sections, html/pdf/docx), or 'modern'
            (modern branded research brief: full-bleed dark masthead, KPI stat
            strip, accent-tick headings, running header/footer with firm +
            confidentiality mark, exhibit-driven short sections; custom typst
            PDF template; html/pdf/docx).
        formats: Subset of ['html', 'pdf', 'docx'] to configure; defaults per template.
        firm: Firm or institution name (whitepaper title page / modern masthead + header).
        kpis: Optional KPI stat strip for the modern template, a list of
            {"value": ..., "label": ...} dicts (2-4 items ideal). Defaults to
            placeholders when omitted for 'modern'.
        confidential_mark: Optional confidentiality text for the modern template
            footer, e.g. "Confidential — For Discussion Purposes Only".

    Returns paths and the source file to fill with content before rendering.
    """
    return scaffold_report(
        slug, title or None, subtitle, author, abstract, template, formats, firm,
        kpis=kpis, confidential_mark=confidential_mark,
    )


@mcp.tool
def reportforge_render_report(
    source: str,
    formats: list[str] | None = None,
) -> dict[str, Any]:
    """Render a .qmd report to one or more output formats.

    Args:
        source: Path to a .qmd file, a project _quarto.yml directory, or a report
            slug previously created by reportforge_scaffold_report.
        formats: Formats to render this run, e.g. ['html', 'pdf'] or ['docx'].
            Omit to render every format configured in _quarto.yml.

    Returns ok flag, absolute output file paths, and a log tail on failure.
    """
    return render_report(source, formats)


@mcp.tool
def reportforge_save_chart(
    fig_json: str,
    out_basename: str,
    width: int = 1400,
    height: int = 700,
    scale: int = 2,
) -> dict[str, Any]:
    """Export a Plotly figure to static PNG (+ standalone interactive HTML).

    Args:
        fig_json: Full plotly figure as JSON string (fig.to_json()).
        out_basename: Output path without extension; writes <base>.png and <base>.html.
        width/height: Pixel dimensions of the static export (pre-scale).
        scale: Resolution multiplier; 2 gives print-quality ~300dpi at width 1400.

    Returns png/html paths plus a ready-to-paste Markdown embed snippet.
    """
    return save_chart(fig_json, out_basename, width, height, scale)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
