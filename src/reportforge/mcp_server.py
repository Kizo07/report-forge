"""ReportForge MCP server: Quarto-backed multi-format report generation."""

from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP

from reportforge.engine import list_templates, publish_report, render_report, save_chart, scaffold_report, write_report_body


def _coerce_list(value: Any, allowed_tokens: set[str] | None = None) -> Any:
    """Accept JSON-encoded strings (and CSV for known-token lists) where a
    list is expected.

    Some models emit tool arguments like formats='["html", "pdf"]' (a JSON
    string) instead of a real array; fastmcp's strict pydantic validation
    rejects those, trapping the agent in a retry loop.  Parse such strings
    back into lists so the call succeeds.

    NOTE: list-typed tool parameters must be annotated ``list[...] | str |
    None`` at the MCP boundary — fastmcp validates args BEFORE the tool body
    runs, so a bare ``list[...]`` annotation rejects the string and this
    coercion never executes (verified: run d1f6a9b5 burned two scaffold
    attempts this way).

    When ``allowed_tokens`` is given, a bracket-less CSV string like
    "html,pdf,docx" whose parts all match is also split into a list.
    """
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("[") or s.startswith("{"):
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                pass
        elif allowed_tokens is not None and s:
            parts = [p.strip().lower() for p in s.split(",") if p.strip()]
            if parts and all(p in allowed_tokens for p in parts):
                return parts
    return value

mcp = FastMCP(
    "reportforge",
    instructions=(
        "Generate beautiful multi-format reports (HTML, PDF via Typst, DOCX) from "
        "Quarto .qmd sources with unified branding. Workflow: scaffold_report to create "
        "a report project, edit the index.qmd (or have the calling agent write content "
        "into it), optionally save_chart for plotly figures, then render_report to "
        "produce final documents, then publish_report to deliver the rendered files "
        "into the run's thread outputs (follow its next_step and call present_files "
        "with the returned present_paths — never substitute a manifest for the real files)."
    ),
)


_FORMAT_TOKENS = {"html", "pdf", "docx"}


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
    formats: list[str] | str | None = None,
    firm: str = "",
    kpis: list[dict[str, str]] | str | None = None,
    confidential_mark: str = "",
    organization: str = "",
    eyebrow: str = "",
    title_layout: str = "hero",
    accent: str = "#4f46e5",
    metrics: list[dict[str, str]] | str | None = None,
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
            PDF template; html/pdf/docx), or 'studio' (premium,
            content-neutral editorial layout with hero/compact title,
            optional organization, eyebrow, metrics, accent, and footer;
            flexible Markdown sections; html/pdf/docx).
        formats: Subset of ['html', 'pdf', 'docx'] to configure; defaults per
            template. Pass a real JSON list when possible; a JSON-encoded
            string or a CSV like "html,pdf,docx" is also accepted.
        firm: Firm or institution name (whitepaper title page / modern masthead + header).
        kpis: Optional KPI stat strip for the modern template, a list of
            {"value": ..., "label": ...} dicts (2-4 items ideal). Defaults to
            placeholders when omitted for 'modern'. A JSON-encoded string of
            the list is also accepted.
        confidential_mark: Optional confidentiality text for the modern template
            footer, e.g. "Confidential — For Discussion Purposes Only".
        organization: Generic organization or brand name for studio.
        eyebrow: Short studio kicker above the title.
        title_layout: Studio title composition, either "hero" or "compact".
        accent: Studio accent as a six-digit hex color.
        metrics: Optional studio metric strip, a list of 0-6 value/label
            objects. A JSON-encoded string of the list is also accepted.

    Returns paths and the source file to fill with content before rendering.
    """
    return scaffold_report(
        slug, title or None, subtitle, author, abstract, template,
        _coerce_list(formats, _FORMAT_TOKENS), firm,
        kpis=_coerce_list(kpis), confidential_mark=confidential_mark,
        organization=organization, eyebrow=eyebrow, title_layout=title_layout,
        accent=accent, metrics=_coerce_list(metrics),
    )


@mcp.tool
def reportforge_render_report(
    source: str,
    formats: list[str] | str | None = None,
) -> dict[str, Any]:
    """Render a .qmd report to one or more output formats.

    Args:
        source: Path to a .qmd file, a project _quarto.yml directory, or a report
            slug previously created by reportforge_scaffold_report.
        formats: Formats to render this run, e.g. ['html', 'pdf'] or ['docx'].
            A JSON-encoded string or a CSV like "html,pdf" is also accepted.
            Omit to render every format configured in _quarto.yml.

    Returns ok flag, absolute output file paths, and a log tail on failure.
    """
    return render_report(source, _coerce_list(formats, _FORMAT_TOKENS))


@mcp.tool
def reportforge_save_chart(
    fig_json: str,
    out_basename: str,
    width: int = 1400,
    height: int = 700,
    scale: int = 2,
    project: str = "",
) -> dict[str, Any]:
    """Export a Plotly figure to static PNG (+ standalone interactive HTML).

    Args:
        fig_json: Full plotly figure as JSON string (fig.to_json()).
        out_basename: Output path without extension; writes <base>.png and <base>.html.
            IMPORTANT: this server runs on the HOST filesystem. Sandbox paths
            like /mnt/user-data/... do not exist here — they are automatically
            redirected into the report project's figures/ directory, but you
            should prefer host paths such as <report dir>/figures/<name>.
        width/height: Pixel dimensions of the static export (pre-scale).
        scale: Resolution multiplier; 2 gives print-quality ~300dpi at width 1400.
        project: Optional report slug (from reportforge_scaffold_report). When a
            sandbox path is translated, the chart is anchored to this project's
            figures/ dir. If omitted, the most recently modified project is used.

    Returns png/html paths plus a ready-to-paste Markdown embed snippet.
    """
    return save_chart(fig_json, out_basename, width, height, scale, project=project or None)


@mcp.tool
def reportforge_write_report_body(
    source: str,
    content: str,
) -> dict[str, Any]:
    """Write the complete .qmd body of a scaffolded report project.

    This is how report content gets populated: after scaffold_report, call
    this with the full .qmd text (YAML front matter + markdown sections),
    then render_report.

    Args:
        source: Report slug (e.g. 'aapl-12m-outlook'), project directory, or
            path to the index.qmd.
        content: Complete .qmd text including YAML front matter.

    Returns ok flag, written path, and byte count.
    """
    return write_report_body(source, content)


@mcp.tool
def reportforge_publish_report(
    project: str,
    dest_dir: str | None = None,
) -> dict[str, Any]:
    """Publish a rendered report project's artifacts into the run's thread outputs.

    Report-forge renders on the host filesystem, which the agent sandbox cannot
    read — so the sandbox's present_files gate cannot serve those bytes and the
    run's delivery gate has nothing real to match. This tool bridges that gap:
    it copies the rendered deliverables (index.pdf/docx/html + companion asset
    dirs) into the thread's outputs directory, which IS mounted in the sandbox,
    and returns sandbox-virtual paths ready for present_files.

    Call this after a successful render_report. Then call present_files with the
    returned ``present_paths`` so the real artifacts — not a manifest — satisfy
    the delivery gate.

    Args:
        project: Report slug (e.g. 'aapl-12m-studio') whose output/ to publish.
        dest_dir: Optional explicit host destination dir. When omitted, uses the
            DEERFLOW_THREAD_OUTPUTS_HOST env var that deer-flow injects into
            stdio MCP sessions (the thread's host outputs dir).

    Returns ok flag, host_dir, published file names, present_paths (sandbox
    virtual paths), and next_step.
    """
    return publish_report(project, dest_dir)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
