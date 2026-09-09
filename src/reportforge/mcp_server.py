"""ReportForge MCP server: Quarto-backed multi-format report generation."""

from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP

from reportforge.engine import (
    append_section,
    check_readiness,
    delete_section,
    derive_cover,
    export_release,
    freeze_release,
    get_section,
    list_templates,
    move_section,
    project_status,
    publish_report,
    read_project_file,
    record_review,
    register_exhibit,
    register_fact,
    register_source,
    render_preview,
    render_report,
    replace_section,
    run_code,
    run_file,
    save_asset,
    save_chart,
    scaffold_report,
    rollforward_report,
    update_fact,
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


def _coerce_str_list(value: Any) -> Any:
    """Coerce a JSON-encoded string of strings to a list (see _coerce_list)."""
    coerced = _coerce_list(value)
    if isinstance(coerced, str):
        s = coerced.strip()
        if s.startswith("["):
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                pass
    return coerced


def _coerce_id_list(value: Any) -> list | None:
    """Registry link lists: None stays None, a bare id becomes [id]."""
    coerced = _coerce_str_list(value)
    if coerced is None:
        return None
    if isinstance(coerced, str):
        return [coerced] if coerced.strip() else []
    return coerced

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
    verdict: str = "",
    key_points: list[str] | str | None = None,
    scenarios: list[dict[str, str]] | str | None = None,
    frontmatter_yaml: str | None = None,
    body: str | None = None,
    engine_charts_only: bool = False,
    profile: dict[str, str] | str | None = None,
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
        title_layout: Studio title composition: "hero", "compact", or "minimal"
            (plain title block without the card).
        accent: Studio accent as a six-digit hex color.
        metrics: Optional studio metric strip, a list of 0-6 value/label
            objects. A JSON-encoded string of the list is also accepted.
        verdict: Optional conviction-call band on the cover of studio /
            portfolio reports, e.g. "OVERWEIGHT — $720 base target (+21%)".
        key_points: Optional exec-summary bullets (max 4 strings) rendered
            as cover cards. A JSON-encoded string of the list is accepted.
        scenarios: Optional cover scenario strip — exactly 3 objects with
            label/value/detail (bear/base/bull order; the middle card is
            highlighted as the base case). A JSON-encoded string is accepted.
        frontmatter_yaml: For the 'bespoke' template: full YAML front matter for
            index.qmd (everything between the --- fences), so the caller owns
            the layout (title, format options, custom css, etc.).
        body: For the 'bespoke' template: initial Markdown body for index.qmd.
            If omitted, a placeholder body is written.
        engine_charts_only: Flagship hard-fail switch. When true the project
            frontmatter records `engine_charts_only: true` and render_report
            REFUSES to render if any chart PNG carries a non-engine Software
            tag (matplotlib/seaborn fallback) — or, on light templates, a
            near-white background (hand-rolled plotly default) — returning
            ok:false naming the files instead of shipping them. Set it on
            every flagship; fallback is forbidden there (quote the export
            error, stringify scalar Timestamps, retry, escalate).

    Returns paths and the source file to fill with content before rendering.
    """
    if isinstance(profile, str) and profile.strip():
        try:
            profile = json.loads(profile)
        except json.JSONDecodeError:
            # Not a map and not JSON: route through the matrix error so the
            # caller sees the supported set instead of a bare rejection.
            profile = {"_unparsed": profile}
    return scaffold_report(
        slug, title or None, subtitle, author, abstract, template,
        _coerce_list(formats, _FORMAT_TOKENS), firm,
        kpis=_coerce_list(kpis), confidential_mark=confidential_mark,
        organization=organization, eyebrow=eyebrow, title_layout=title_layout,
        accent=accent, metrics=_coerce_list(metrics),
        verdict=verdict, key_points=_coerce_str_list(key_points),
        scenarios=_coerce_list(scenarios),
        frontmatter_yaml=frontmatter_yaml, body=body,
        engine_charts_only=engine_charts_only, profile=profile,
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
def reportforge_freeze_release(project: str) -> dict[str, Any]:
    """Re-seal + verify output/release.json against current inputs (RF-09).

    Args:
        project: Report slug (project directory name).

    Fails loudly when the inputs drifted since the seal (qmd, registry,
    toolchain, template) or an artifact is missing/changed on disk.
    Run after rendering all formats; re-run after any re-render.
    """
    return freeze_release(project)


@mcp.tool
def reportforge_rollforward_report(
    project: str,
    new_slug: str,
    brief: str = "",
    params: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    """Birth a next-period report from a finished one (RF-09).

    Args:
        project: Source report slug.
        new_slug: Slug for the new period report.
        brief: REQUIRED new mandate for the period (empty fails loudly).
        params: Map with period label, as_of ISO date (REQUIRED — drives
            the stale-facts checklist), optional title override. A
            JSON-encoded string is also accepted.

    Registries deep-copy with registry_version preserved; output/, state,
    and the old manifest never cross. Returns carried counts plus the
    stale / unknown_vintage refresh checklist.
    """
    if isinstance(params, str) and params.strip():
        try:
            params = json.loads(params)
        except json.JSONDecodeError:
            return {"ok": False,
                    "error": "params is not valid JSON: pass a map with period/as_of"}
    return rollforward_report(project, new_slug, brief,
                              params if isinstance(params, (dict, type(None)))
                              else {"_unparsed": params})


@mcp.tool
def reportforge_derive_cover(
    project: str,
    mapping: dict[str, str] | str | None = None,
) -> dict[str, Any]:
    """Bind cover numerics to fact records (RF-04 deepening).

    Args:
        project: Report slug.
        mapping: {cover path: fact id} for target, scenarios[i].value,
            metrics[i].value. Omitted paths fall back to the fact-<field>
            convention (target → fact-target). A JSON-encoded string is
            also accepted. A numeric cover field with no resolvable fact
            fails loudly — hand values are never kept silently.
    """
    if isinstance(mapping, str) and mapping.strip():
        try:
            mapping = json.loads(mapping)
        except json.JSONDecodeError:
            return {"ok": False,
                    "error": "mapping is not valid JSON: pass a map of cover path to fact id"}
    return derive_cover(
        project,
        mapping if isinstance(mapping, (dict, type(None))) else {"_unparsed": mapping})


@mcp.tool
def reportforge_register_exhibit(
    project: str,
    exhibit_id: str,
    title: str,
    file: str | None = None,
    source_keys: list[str] | str | None = None,
    fact_ids: list[str] | str | None = None,
    as_of: str | None = None,
    alt: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Register an exhibit record: figure file or anchor linked to evidence.

    The exhibit must be grounded: its id must match a {#fig-<id>} anchor in
    index.qmd, or file must point at an existing file in the project.

    Args:
        project: Report slug (project directory name).
        exhibit_id: Must reuse a figure anchor (fig-<id>).
        title: Human-readable exhibit title.
        file: Project-relative figure path (or null for anchor-grounded).
        source_keys: Registered source keys backing this exhibit.
        fact_ids: Registered fact ids shown in this exhibit.
        as_of: Data vintage.
        alt: Accessibility text for the figure.
        overwrite: Replace an existing record with the same id.
    """
    return register_exhibit(
        project, exhibit_id, title, file=file,
        source_keys=_coerce_id_list(source_keys),
        fact_ids=_coerce_id_list(fact_ids),
        as_of=as_of, alt=alt, overwrite=overwrite)


@mcp.tool
def reportforge_save_chart(
    fig_json: str,
    out_basename: str,
    width: int = 1400,
    height: int = 700,
    scale: int = 2,
    project: str = "",
    template: str = "",
    exhibit_id: str = "",
    exhibit_title: str = "",
    source_keys: list[str] | str | None = None,
    fact_ids: list[str] | str | None = None,
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
        template: Optional plotly template name ("quantflow-dark",
            "quantflow-light", or any registered plotly template). When set
            it wins. When omitted and the figure has no explicit template,
            the chart matches the project page: portfolio-dark/light projects
            get the QuantFlow identity automatically; everything else keeps
            the figure as supplied. An explicitly themed figure (including
            alpha_engine viz builders with theme=...) is never overridden.

    Returns png/html paths plus a ready-to-paste Markdown embed snippet.
        When project is given the exhibit auto-registers (id defaults to the
        file stem in the fig- namespace); pass exhibit_id/title/links to
        attribute it at save time. On re-save, omitted link lists inherit
        the existing record; pass an explicit empty list to clear them.
    """
    return save_chart(fig_json, out_basename, width, height, scale, project=project or None, template=template or None, exhibit_id=exhibit_id or None, exhibit_title=exhibit_title or None, source_keys=_coerce_id_list(source_keys), fact_ids=_coerce_id_list(fact_ids))


@mcp.tool
def reportforge_write_report_body(
    source: str,
    content: str,
) -> dict[str, Any]:
    """Write the complete .qmd body of a scaffolded report project.

    This is how report content gets populated: after scaffold_report, call
    this with the full .qmd text (YAML front matter + markdown sections),
    then render_report.

    Tables — keep them narrow or they will clutter/overflow in every format:
    max ~6 columns, short cell text (a few words; numbers over prose), one
    idea per table (split wide comparisons into two tables or move detail to
    the appendix), right-align numeric columns with markdown colons. Wide
    tables scroll in HTML but still paginate badly in PDF/DOCX. Showcase
    Showcase tables (scenarios, comps, calendars) get the spreadsheet treatment by
    wrapping them in ::: {.rf-showtable} ... ::: — banded accent header,
    zebra rows, semibold label column, tabular numerals. Add .rf-nums-right
    to the wrapper (::: {.rf-showtable .rf-nums-right}) to right-align all
    data columns. Same styling renders in PDF via the Typst template.

    Prose voice — write like a human desk analyst, not a language model:
    short declarative sentences (one claim each, ~20 words max); never stack
    three or more subordinate clauses in one sentence. Plain exhibit names
    from the data ("AMZN 12-month returns vs peers"), never invented labels
    ("Price Hero", "Momentum Ladder", "Demand-Capacity"). Banned tics:
    shouty headers ("THESIS IN ONE PARAGRAPH"), "delve/tapestry/landscape",
    "announces itself/adjudicates", "forensic attention", "honestly labeled",
    triple-parallel flourishes, non-English slips. Number ladders
    ("down 8% on 21d, up 2% on 63d...") go in a table, not a sentence —
    prose states the read, the table carries the digits. Every number needs
    a unit and an as-of; every paragraph answers "so what" in its last line.

    Figure sizing — widths are % of the TWO-COLUMN body (portfolio/studio
    PDFs flow body text in two columns from page 2; cover stays
    single-column page 1). Match embed width to information content:
    heroes (technicals/fan/timeline/major exhibits) width=100% AND wrapped
    in ::: {column-page} so they span both columns — an unwrapped 100%
    only fills its own column. Standard/bar/simple charts width=85% of
    the column (≈ old 40%-of-page print size) with running text flowing
    beside them; two-column flow replaces layout-ncol pairing. Never
    stack more than two spanned heroes without intervening prose; never
    leave a lone chart as the only content under a heading — each
    exhibit gets 2-4 lines saying what it shows and what the reader
    should conclude. Tables stay in-column (template keeps them
    unbreakable): max 5 data columns, as-of in the caption never per-row,
    symbol headers (P/E, EV/EBITDA, S&P). NEVER `$` in alt text or
    fig-cap (math-mode kill).

    Before render, run `python scripts/figure_lint.py <project-dir>` from
    the report-forge checkout — size/caption/voice/palette gate, must be
    clean. Full rules: docs/flagship-rules.md.

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
    before_section_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Append a markdown section to a project's index.qmd without rewriting it.

    Additive composition: the YAML front matter is preserved untouched. With
    `before` given, the section is inserted above the first heading whose text
    contains that string (case-insensitive). Use for incremental edits; use
    write_report_body for full rewrites.

    Tables — keep them narrow or they will clutter/overflow in every format:
    max ~6 columns, short cell text (a few words; numbers over prose), one
    idea per table (split wide comparisons into two tables or move detail to
    the appendix), right-align numeric columns with markdown colons.
    Showcase tables get the spreadsheet treatment: wrap in
    ::: {.rf-showtable} ... ::: (add .rf-nums-right to right-align data
    columns) for a banded accent header, zebra rows, and semibold label
    column in HTML and PDF.

    Prose voice — write like a human desk analyst: short declarative
    sentences (one claim each, ~20 words max), plain exhibit names from the
    data, never invented labels ("Price Hero", "Momentum Ladder"). Banned:
    shouty headers, "delve/tapestry/landscape", "announces itself",
    "forensic attention", triple-parallel flourishes, non-English slips.
    Number ladders go in a table, not a sentence. Every number needs a unit
    and an as-of.

    Figure sizing — widths are % of the TWO-COLUMN body (two columns from
    page 2, cover single-column page 1). Heroes width=100% wrapped in
    ::: {column-page} to span both columns; bar/standard/simple charts
    width=85% of the column with text flowing beside them. Never stack
    more than two spanned heroes without prose between; every exhibit
    gets 2-4 lines of read-through. Tables stay in-column: max 5 data
    columns, as-of in caption, symbol headers. NEVER `$` in alt/fig-cap.

    Before render, run `python scripts/figure_lint.py <project-dir>` —
    must be clean. Full rules: docs/flagship-rules.md.

    Args:
        project: Report slug (project directory name).
        markdown: Markdown section(s) to add (headings, prose, code chunks,
            image embeds).
        before: Optional heading text to insert above.
        before_section_id: Optional exact section id to insert above.
        idempotency_key: Optional caller-chosen key; repeats are no-op replays.

    Returns ok flag, action taken, new file size, and next_step (render).
    """
    return append_section(project, markdown, before=before,
                          before_section_id=before_section_id,
                          idempotency_key=idempotency_key)


@mcp.tool
def reportforge_get_section(
    project: str,
    section_id: str,
) -> dict[str, Any]:
    """Read one report section's markdown, heading level, and byte range.

    Read-only: never bumps the manifest revision. Address sections by stable
    id (s- + slugified heading); get ids from project_status (manifest view).

    Args:
        project: Report slug (project directory name).
        section_id: Stable section id, e.g. 's-executive-summary'.
    """
    return get_section(project, section_id)


@mcp.tool
def reportforge_replace_section(
    project: str,
    section_id: str,
    markdown: str,
    expected_revision: int,
) -> dict[str, Any]:
    """Replace a section's heading + body wholesale; other bytes preserved.

    Optimistic concurrency: pass the manifest revision you read. A stale
    revision fails loudly with changed_sections context — never clobbers.

    Args:
        project: Report slug (project directory name).
        section_id: Stable section id to replace.
        markdown: Replacement block (heading + body).
        expected_revision: Manifest revision the change applies on top of.
    """
    return replace_section(project, section_id, markdown,
                           expected_revision=expected_revision)


@mcp.tool
def reportforge_move_section(
    project: str,
    section_id: str,
    expected_revision: int,
    before_section_id: str | None = None,
    to_end: bool = False,
) -> dict[str, Any]:
    """Move a section block before another section or to the document end.

    Args:
        project: Report slug (project directory name).
        section_id: Stable section id to move.
        before_section_id: Move above this section id (omit with to_end).
        to_end: Move to the document end.
        expected_revision: Manifest revision the change applies on top of.
    """
    return move_section(project, section_id, before_section_id=before_section_id,
                        to_end=to_end, expected_revision=expected_revision)


@mcp.tool
def reportforge_delete_section(
    project: str,
    section_id: str,
    expected_revision: int,
) -> dict[str, Any]:
    """Remove a section block from a project's index.qmd.

    Args:
        project: Report slug (project directory name).
        section_id: Stable section id to remove.
        expected_revision: Manifest revision the change applies on top of.
    """
    return delete_section(project, section_id, expected_revision=expected_revision)


@mcp.tool
def reportforge_export_release(
    project: str,
    dest: str,
    revision: int | None = None,
    include_source: bool = False,
    include_data: bool = False,
) -> dict[str, Any]:
    """Export an approved revision as a self-contained bundle (§3).

    Layout <dest>/<report_id>/r<rev>/ with deliverables, manifest.json copy,
    bundle.json descriptor index, optional source/ + data/. Drafts are
    rejected — only approved revisions release. A successful export marks
    the manifest exported.

    Args:
        project: Report slug (project directory name).
        dest: Destination root directory for the bundle.
        revision: Revision to export (default: current).
        include_source: Also bundle index.qmd + config.
        include_data: Also bundle the data/ directory.
    """
    return export_release(project, revision=revision, dest=dest,
                          include_source=include_source,
                          include_data=include_data)


@mcp.tool
def reportforge_check_readiness(
    project: str,
) -> dict[str, Any]:
    """Unified readiness: structure, evidence, numerical, presentation, editorial.

    Returns per-category issues plus ready_for_review (zero errors).
    Automated checks only — never factual verification (review §3.6).

    Args:
        project: Report slug (project directory name).
    """
    return check_readiness(project)


@mcp.tool
def reportforge_register_source(
    project: str,
    key: str,
    kind: str,
    title: str,
    date: str | None = None,
    url: str | None = None,
    publisher: str | None = None,
    accessed: str | None = None,
    as_of: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Register a citable source in the report's evidence registry (RF-03).

    Persists the record, rewrites sources.bib, and wires a top-level
    bibliography entry in _quarto.yml. Cite the key from prose as [@key].

    Args:
        project: Report slug (project directory name).
        key: Citekey, must match src-<slug>.
        kind: filing, article, dataset, price-feed, transcript, report, other.
        title: Human-readable source title.
        date: Publication date (one of date/as_of required).
        url: Source URL (stored verbatim, never fetched).
        publisher: Publisher/author for the bib entry.
        accessed: Retrieval date for the bib note.
        as_of: Data vintage when it differs from publication date.
        overwrite: Replace an existing record with the same key.
    """
    return register_source(project, key, kind, title, date=date, url=url,
                           publisher=publisher, accessed=accessed,
                           as_of=as_of, overwrite=overwrite)


@mcp.tool
def reportforge_register_fact(
    project: str,
    fact_id: str,
    value: Any,
    unit: str = "",
    kind: str = "observed",
    source_keys: list[str] | str | None = None,
    as_of: str | None = None,
    note: str = "",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Register a shared typed fact record (RF-03).

    Kind is required: observed, calculated, estimated, or illustrative.
    Cover verdict/target/scenarios/metrics values should have matching
    fact ids (checked by readiness EVID-COVER-UNLINKED).

    Args:
        project: Report slug (project directory name).
        fact_id: Must match fact-<slug>.
        value: Numeric or string quantity.
        unit: Unit string (may be empty).
        kind: observed, calculated, estimated, or illustrative.
        source_keys: Registered source keys backing this fact.
        as_of: Data vintage.
        note: Free-text provenance note.
        overwrite: Replace an existing record (history is preserved).
    """
    return register_fact(project, fact_id, value, unit=unit, kind=kind,
                         source_keys=_coerce_id_list(source_keys),
                         as_of=as_of, note=note, overwrite=overwrite)


@mcp.tool
def reportforge_update_fact(
    project: str,
    fact_id: str,
    value: Any = None,
    unit: str | None = None,
    kind: str | None = None,
    source_keys: list[str] | str | None = None,
    as_of: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Update a fact record; superseded values stay in capped history (20).

    Args:
        project: Report slug (project directory name).
        fact_id: Existing fact id.
        value: New value (defaults to current — refreshes metadata only).
        unit/kind/source_keys/as_of/note: Optional replacements.
    """
    return update_fact(project, fact_id, value=value, unit=unit, kind=kind,
                       source_keys=_coerce_id_list(source_keys),
                       as_of=as_of, note=note)


@mcp.tool
def reportforge_record_review(
    project: str,
    revision: int,
    reviewer: str,
    decision: str,
    comments: str = "",
    section_id: str | None = None,
) -> dict[str, Any]:
    """Record a human/agent review decision against a revision (§4.3).

    Approval (review -> approved) requires an approved record for the
    current revision.

    Args:
        project: Report slug (project directory name).
        revision: Revision the decision applies to.
        reviewer: Who decided (e.g. 'human:fire').
        decision: 'changes_requested' or 'approved'.
        comments: Optional rationale.
        section_id: Optional section the decision targets.
    """
    return record_review(project, revision, reviewer, decision,
                         comments=comments, section_id=section_id)


@mcp.tool
def reportforge_capabilities() -> dict[str, Any]:
    """Capability discovery (§6): templates, profiles, support matrix, env.

    Fresh agents call this first: supported template/profile/output
    combinations, execution availability, preview support, delivery methods,
    section ops, manifest states, tool list, and doc pointers. No arguments.
    """
    from reportforge import engine as _engine
    return _engine.reportforge_capabilities()


@mcp.tool
def reportforge_render_preview(
    project: str,
    revision: int | None = None,
) -> dict[str, Any]:
    """Render preview artifacts for a report revision (RF-05).

    Produces a contact sheet (all pages tiled), per-page PNGs, and exhibit
    PNGs (charts/*), stored under <project>/output/previews/r<rev>/ and
    returned as relative-path artifact descriptors (id/path/bytes/sha256/
    mime/role). Previews bind to (report_id, revision): the rendered PDF
    must already exist — render first, this tool never auto-renders.

    Args:
        project: Report slug (project directory name).
        revision: Optional expected revision; mismatch is a loud failure
            with current_revision in the response.

    Returns ok, report_id, revision, page_count, artifacts, next_step.
    """
    return render_preview(project, revision=revision)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
