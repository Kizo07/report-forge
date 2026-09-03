"""ReportForge MCP server: Quarto-backed multi-format report generation."""

from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP

from reportforge.engine import (
    append_section,
    list_templates,
    project_status,
    publish_report,
    read_project_file,
    render_report,
    run_code,
    run_file,
    save_asset,
    save_chart,
    scaffold_report,
    write_report_body,
)


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
        "Generate beautiful multi-format reports (HTML, PDF via Typst, DOCX, and pdf-web "
        "via headless-Chromium print of the HTML) from Quarto .qmd sources with unified "
        "branding. Workflow: scaffold_report to create a report project, edit the index.qmd "
        "(write_report_body for the full body, append_section for additive edits), optionally "
        "save_chart for plotly figures or save_asset for arbitrary files (matplotlib PNGs, "
        "CSVs, HTML partials), then render_report to produce final documents, then "
        "publish_report to deliver the rendered files into the run's thread outputs (follow "
        "its next_step and call present_files with the returned present_paths — never "
        "substitute a manifest for the real files). For compute-heavy reports use run_code / "
        "run_file to execute Python on the host (same interpreter as the report kernel: "
        "pandas/pyarrow/statsmodels available) and inspect results with project_status / "
        "read_project_file before iterating. The 'bespoke' template removes all layout "
        "opinions for custom designs."
    ),
)


_FORMAT_TOKENS = {"html", "pdf", "docx", "pdf-web"}


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
    frontmatter_yaml: str | None = None,
    body: str | None = None,
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
            flexible Markdown sections; html/pdf/docx), or 'portfolio-light'
            / 'portfolio-dark' (same editorial pipeline as 'studio' in the
            portfolio light/dark themes: warm paper or near-black, serif
            display type, gold kicker; html/pdf/docx).
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
        frontmatter_yaml: For the 'bespoke' template: full YAML front matter for
            index.qmd (everything between the --- fences), so the caller owns
            the layout (title, format options, custom css, etc.).
        body: For the 'bespoke' template: initial Markdown body for index.qmd.
            If omitted, a placeholder body is written.

    Returns paths and the source file to fill with content before rendering.
    """
    return scaffold_report(
        slug, title or None, subtitle, author, abstract, template,
        _coerce_list(formats, _FORMAT_TOKENS), firm,
        kpis=_coerce_list(kpis), confidential_mark=confidential_mark,
        organization=organization, eyebrow=eyebrow, title_layout=title_layout,
        accent=accent, metrics=_coerce_list(metrics),
        frontmatter_yaml=frontmatter_yaml, body=body,
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


@mcp.tool
def reportforge_run_code(
    code: str,
    project: str | None = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """Execute Python code on the host inside a report project.

    Runs with the reportforge interpreter (the SAME environment the Quarto
    jupyter kernel uses — pandas, pyarrow, numpy, statsmodels, plotly,
    matplotlib are available), with the working directory pinned to the
    project root, so relative paths land inside the project. This is HOST
    execution with the user's permissions: use it to compute numbers, fit
    models, and produce data files that the report then embeds — test-then-
    write instead of blind authoring.

    Args:
        code: Python source to execute.
        project: Report slug whose root becomes the cwd. Required unless the
            server is configured to allow project-less runs.
        timeout: Seconds before the run is killed (default 300).

    Returns ok flag, exit_code, stdout_tail, stderr_tail, created/modified
    file lists (relative to the project), and duration_s. The captured
    stdout/stderr are ground truth — never report results you did not see.
    """
    return run_code(code, project=project, timeout=timeout)


@mcp.tool
def reportforge_run_file(
    path: str,
    project: str,
    args: list[str] | str | None = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """Run a script that already lives inside a report project.

    Dispatch by extension: .py → reportforge interpreter, .sh → bash,
    .R → Rscript. Same host-permission model and capture semantics as
    run_code; cwd is the project root.

    Args:
        path: Path to the script relative to the project root.
        project: Report slug containing the script.
        args: Command-line arguments for the script; a JSON-encoded list or a
            CSV string is also accepted.
        timeout: Seconds before the run is killed (default 300).

    Returns ok flag, exit_code, stdout_tail, stderr_tail, created/modified
    file lists, and duration_s.
    """
    return run_file(path, project, args=_coerce_list(args), timeout=timeout)


@mcp.tool
def reportforge_save_asset(
    project: str,
    dest_relpath: str,
    content_text: str | None = None,
    content_b64: str | None = None,
) -> dict[str, Any]:
    """Write an arbitrary file (text or base64 binary) into a report project.

    Generalizes save_chart beyond plotly: matplotlib-exported PNGs, CSVs,
    style.css, HTML partials, anything the template should embed. Confined to
    the project root.

    Args:
        project: Report slug (project directory name).
        dest_relpath: Destination path relative to the project root, e.g.
            'assets/rebalance.csv' or 'figures/turnover.png'.
        content_text: UTF-8 text content (for text files).
        content_b64: Base64-encoded content (for binary files such as PNGs).
            Provide exactly one of content_text / content_b64.

    Returns ok flag, absolute path, relpath, byte count, and an embed_snippet
    suitable for .qmd markdown.
    """
    return save_asset(project, dest_relpath, content_text=content_text, content_b64=content_b64)


@mcp.tool
def reportforge_project_status(project: str) -> dict[str, Any]:
    """Summarize a report project for inspection and iteration.

    Returns the file tree (relpath + bytes), the formats configured in
    _quarto.yml, the output directory, available render logs, and the state
    of the last render (formats, outputs, timestamp). Use after a failed
    render to find the render log to read, or to confirm assets landed.

    Args:
        project: Report slug (project directory name).
    """
    return project_status(project)


@mcp.tool
def reportforge_read_project_file(
    project: str,
    relpath: str,
    max_bytes: int = 32768,
) -> dict[str, Any]:
    """Read a text file from a report project (source, logs, generated data).

    Use this to read render logs after a failed render (see project_status
    for log names) and to inspect what a run_code step actually wrote before
    embedding it. Binary files return size only.

    Args:
        project: Report slug (project directory name).
        relpath: Path relative to the project root, e.g.
            'output/.render-log-typst.txt'.
        max_bytes: Maximum characters to return (default 32768); longer
            content is truncated with truncated=True.
    """
    return read_project_file(project, relpath, max_bytes=max_bytes)


@mcp.tool
def reportforge_append_section(
    project: str,
    markdown: str,
    before: str | None = None,
) -> dict[str, Any]:
    """Append a markdown section to a project's index.qmd without rewriting it.

    Additive composition: the YAML front matter is preserved untouched. With
    `before` given, the section is inserted above the first heading whose text
    contains that string (case-insensitive). Use for incremental edits; use
    write_report_body for full rewrites.

    Args:
        project: Report slug (project directory name).
        markdown: Markdown section(s) to add (headings, prose, code chunks,
            image embeds).
        before: Optional heading text to insert above.

    Returns ok flag, action taken, new file size, and next_step (render).
    """
    return append_section(project, markdown, before=before)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
