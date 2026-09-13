"""Engine scaffold cluster (Phase 3 split; see plan §4).

All engine-level references go through `_E` (deferred package
attribute access) so monkeypatching `reportforge.engine.<name>`
keeps working.
"""

from __future__ import annotations

from reportforge import engine as _E

import json
import re
import shutil
from html import escape as html_escape
from datetime import date, datetime
from pathlib import Path
import yaml
from reportforge import manifest as manifest_mod
from reportforge import templates



def list_templates() -> list[dict]:
    return [
        {"name": "standard", "description": "Multi-section business report: executive summary, analysis, recommendations. TOC + numbered sections; html/pdf/docx.", "toc": True, "number_sections": True, "formats": ["html", "pdf", "docx"]},
        {"name": "memo", "description": "Single-purpose memo: purpose, key points, details. No TOC; html/pdf.", "toc": False, "number_sections": False, "formats": ["html", "pdf"]},
        {"name": "earnings-recap", "description": "Post-earnings recap: results-at-a-glance table vs consensus, segment detail, margin bridge, guidance read, market reaction, risks. Exhibits labeled 'Exhibit N'; no TOC; html/pdf/docx.", "toc": False, "number_sections": False, "exhibit_labels": True, "papersize": "us-letter", "formats": ["html", "pdf", "docx"]},
        {"name": "sector-outlook", "description": "Sector outlook: where-we-stand, relative performance, subsector scorecard table, valuation, positioning implications, risks. TOC + numbered sections; exhibits labeled 'Exhibit N'; html/pdf/docx.", "toc": True, "number_sections": True, "exhibit_labels": True, "papersize": "us-letter", "formats": ["html", "pdf", "docx"]},
        {"name": "thematic-deepdive", "description": "Thematic deep dive: key takeaways, theme definition and sizing, demand drivers, value chain, public-market exposure, roadmap signposts, risks. TOC + numbered sections; exhibits labeled 'Exhibit N'; html/pdf/docx.", "toc": True, "number_sections": True, "exhibit_labels": True, "papersize": "us-letter", "formats": ["html", "pdf", "docx"]},
        {"name": "macro-outlook", "description": "Macro outlook: nowcast indicator table, growth/inflation/policy sections, bear-base-bull scenario grid with probabilities, asset implications. TOC + numbered sections; exhibits labeled 'Exhibit N'; html/pdf/docx.", "toc": True, "number_sections": True, "exhibit_labels": True, "papersize": "a4", "formats": ["html", "pdf", "docx"]},
        {"name": "quant-factor-brief", "description": "Quant factor brief: signal summary stats table, precise definition and construction, net-of-cost performance, turnover/costs, combinations, robustness. No TOC; exhibits labeled 'Exhibit N'; html/pdf/docx.", "toc": False, "number_sections": False, "exhibit_labels": True, "papersize": "a4", "formats": ["html", "pdf", "docx"]},
        {"name": "technical-brief", "description": "Technical brief: setup, trend and key-level table, momentum, volatility and volume, scenario levels with triggers, explicit invalidation level. No TOC; exhibits labeled 'Exhibit N'; html/pdf/docx.", "toc": False, "number_sections": False, "exhibit_labels": True, "papersize": "us-letter", "formats": ["html", "pdf", "docx"]},
        {"name": "esg-sustainability", "description": "ESG / sustainability review: rating profile table vs sector, environmental/social/governance sections, controversies, disclosure quality, financial materiality. TOC + numbered sections; exhibits labeled 'Exhibit N'; html/pdf/docx.", "toc": True, "number_sections": True, "exhibit_labels": True, "papersize": "a4", "formats": ["html", "pdf", "docx"]},
        {"name": "crypto-digital", "description": "Crypto / digital-asset note: market-structure gauges, ETF and exchange flows, on-chain readings, protocol fundamentals, regulatory watch, scenario grid. No TOC; exhibits labeled 'Exhibit N'; html/pdf/docx.", "toc": False, "number_sections": False, "exhibit_labels": True, "papersize": "us-letter", "formats": ["html", "pdf", "docx"]},
        {"name": "desk-synthesis", "description": "Full-desk synthesis: one section per quant-desk agent (quant, technical, catalysts, earnings, sector, macro, thematic, demand) plus bull/bear adjudication, scenario grid, risk/sizing, recommendation. TOC + numbered sections; exhibits labeled 'Exhibit N'; html/pdf/docx.", "toc": True, "number_sections": True, "exhibit_labels": True, "papersize": "us-letter", "formats": ["html", "pdf", "docx"]},
        {"name": "whitepaper", "description": "Hedge-fund-style institutional white paper: key takeaways, investment thesis, framework, exhibit-driven analysis, portfolio implications, risk factors. Figures/tables labeled 'Exhibit N' with unified numbering; title page, TOC + numbered sections; html/pdf/docx.", "toc": True, "number_sections": True, "exhibit_labels": True, "papersize": "us-letter", "titlepage": True, "formats": ["html", "pdf", "docx"]},
        {"name": "modern", "description": "Modern branded research brief: full-bleed dark masthead with firm + subtitle, KPI stat strip, accent-tick headings, running header/footer with confidentiality mark, exhibit-driven short sections (executive summary → signal → actions → risks). Custom typst PDF template; figures/tables labeled 'Exhibit N'; html/pdf/docx.", "toc": False, "number_sections": False, "exhibit_labels": True, "papersize": "us-letter", "formats": ["html", "pdf", "docx"]},
        {"name": "studio", "description": "Premium content-neutral editorial report: hero, compact, or minimal title, optional organization/eyebrow/metrics/verdict/key-points/scenarios cover infographics, accent override, footer, configurable accent, flexible Markdown sections, refined figures and tables. Custom Typst PDF and responsive HTML; html/pdf/docx.", "toc": False, "number_sections": False, "exhibit_labels": True, "papersize": "us-letter", "formats": ["html", "pdf", "docx"], "content_neutral": True, "title_layouts": ["hero", "compact", "minimal"], "max_metrics": 6},
        {"name": "portfolio-light", "description": "Studio editorial pipeline in the portfolio light theme: warm paper, serif display type, gold kicker. Hero/compact/minimal title, eyebrow, organization, 0-6 metrics, verdict/key-points/scenarios cover infographics, accent override, exhibit labels; html/pdf/docx.", "toc": False, "number_sections": False, "exhibit_labels": True, "papersize": "us-letter", "formats": ["html", "pdf", "docx"], "content_neutral": True, "title_layouts": ["hero", "compact", "minimal"], "max_metrics": 6},
        {"name": "portfolio-dark", "description": "Studio editorial pipeline in the portfolio dark theme: near-black paper, serif display type, gold kicker. Hero/compact/minimal title, eyebrow, organization, 0-6 metrics, verdict/key-points/scenarios cover infographics, accent override, exhibit labels; html/pdf/docx.", "toc": False, "number_sections": False, "exhibit_labels": True, "papersize": "us-letter", "formats": ["html", "pdf", "docx"], "content_neutral": True, "title_layouts": ["hero", "compact", "minimal"], "max_metrics": 6},
        {"name": "ledger-dark", "description": "Studio editorial pipeline in the Cyan Ledger midnight theme: near-black blue paper, Space Grotesk display type, ledger-gold kicker, cyan links. Same cover infographics (metrics/verdict/key-points/scenarios), two-column body, exhibit labels; html/pdf/docx.", "toc": False, "number_sections": False, "exhibit_labels": True, "papersize": "us-letter", "formats": ["html", "pdf", "docx"], "content_neutral": True, "title_layouts": ["hero", "compact", "minimal"], "max_metrics": 6},
        {"name": "ledger-light", "description": "Studio editorial pipeline in the Cyan Ledger ice theme: ice-blue paper, Space Grotesk display type, ledger-gold kicker, scheme-safe cyan links. Same cover infographics, two-column body, exhibit labels; html/pdf/docx.", "toc": False, "number_sections": False, "exhibit_labels": True, "papersize": "us-letter", "formats": ["html", "pdf", "docx"], "content_neutral": True, "title_layouts": ["hero", "compact", "minimal"], "max_metrics": 6},
        {"name": "bespoke", "description": "Minimal project, no template opinions: you supply the full .qmd frontmatter and body (via write_report_body / append_section). Use for custom layouts, html-first designs, or the pdf-web (headless-Chromium print) path. html/pdf/docx/pdf-web.", "toc": False, "number_sections": False, "formats": ["html", "pdf", "docx", "pdf-web"], "content_neutral": True},
    ]


def _set_frontmatter_flag(qmd_path: Path, key: str, value: bool) -> None:
    """Insert `key: true/false` right after the opening --- fence."""
    text = qmd_path.read_text()
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return
    lines.insert(1, f"{key}: {'true' if value else 'false'}\n")
    qmd_path.write_text("".join(lines))


def _frontmatter_flag(workdir: Path, key: str) -> bool:
    qmd = workdir / "index.qmd"
    if not qmd.is_file():
        return False
    text = qmd.read_text()
    if not text.startswith("---"):
        return False
    fence = text.find("\n---", 3)
    head = text[:fence] if fence != -1 else text[:2000]
    return bool(re.search(rf"^{key}:\s*true\s*$", head, re.MULTILINE))


def scaffold_report(
    slug: str,
    title: str | None = None,
    subtitle: str = "",
    author: str = "",
    abstract: str = "Add a short abstract here.",
    template: str = "standard",
    formats: list[str] | None = None,
    firm: str = "",
    kpis: list[dict] | None = None,
    confidential_mark: str = "",
    organization: str = "",
    eyebrow: str = "",
    title_layout: str = "hero",
    accent: str | None = None,
    metrics: list[dict] | None = None,
    verdict: str = "",
    key_points: list[str] | None = None,
    scenarios: list[dict] | None = None,
    frontmatter_yaml: str | None = None,
    body: str | None = None,
    engine_charts_only: bool = False,
    profile: dict | None = None,
    report_brief: dict | None = None,
) -> dict:
    specs = {t["name"]: t for t in list_templates()}
    if template not in specs:
        return {"ok": False, "error": f"unknown template {template!r}; available: {sorted(specs)}"}
    spec = specs[template]
    requested_formats = list(spec["formats"]) if formats is None else list(formats)
    unsupported = sorted(set(requested_formats) - set(_E.PUBLIC_FORMATS))
    if unsupported:
        return {
            "ok": False,
            "error": f"unsupported format(s): {', '.join(unsupported)}; available: {list(_E.PUBLIC_FORMATS)}",
        }
    if not requested_formats:
        return {"ok": False, "error": "at least one format is required"}
    template_unsupported = sorted(set(requested_formats) - set(spec["formats"]))
    if template_unsupported:
        return {
            "ok": False,
            "error": (
                f"template {template!r} does not support format(s): "
                f"{', '.join(template_unsupported)}"
            ),
        }
    formats = requested_formats
    # pdf-web is not a Quarto format — it post-processes the html render with
    # headless Chromium. Extract it here; html is its prerequisite input.
    pdf_web_requested = "pdf-web" in formats
    if pdf_web_requested:
        formats = [f for f in formats if f != "pdf-web"]
        if "html" not in formats:
            formats.insert(0, "html")
    # C-1: resolve + validate the profile BEFORE touching the disk — a bad
    # override fails with zero side effects.
    if profile is not None and not isinstance(profile, dict):
        return {"ok": False, "error": "profile must be a map of axis overrides"}
    preset, profile_error = _profile_for_template(
        template, pdf_web_requested, profile)
    if profile_error:
        return {"ok": False, "error": profile_error}
    assert preset is not None  # error branch returned above

    if metrics is not None and kpis is not None:
        return {"ok": False, "error": "use either metrics or kpis, not both"}
    metric_input = metrics if metrics is not None else kpis
    normalized_kpis, kpi_error = _normalize_kpis(metric_input, template)
    if kpi_error:
        return {"ok": False, "error": kpi_error}
    normalized_points, points_error = _normalize_key_points(key_points)
    if points_error:
        return {"ok": False, "error": points_error}
    normalized_scenarios, scenarios_error = _normalize_scenarios(scenarios)
    if scenarios_error:
        return {"ok": False, "error": scenarios_error}
    if accent is None:
        accent = _E._TEMPLATE_DEFAULT_ACCENTS.get(template, "#4f46e5")
    if template in _E._EDITORIAL_TEMPLATES or template == "modern":
        if template in _E._EDITORIAL_TEMPLATES and title_layout not in {"hero", "compact", "minimal"}:
            return {"ok": False, "error": "title layout must be 'hero', 'compact' or 'minimal'"}
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
            return {"ok": False, "error": "accent must be a six-digit hex color such as #4f46e5"}

    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in slug.strip().lower())
    if not slug:
        return {"ok": False, "error": "slug must contain at least one letter, number, '-' or '_'"}
    root = _E.REPORTS_DIR / slug
    if root.exists():
        return {"ok": False, "error": f"report {slug!r} already exists at {root}"}
    assets = root / "assets"
    assets.mkdir(parents=True)
    kernel = _E._ensure_reportforge_kernel()

    if template == "bespoke":
        # No template opinions: project plumbing only. The caller owns the
        # frontmatter and body (write_report_body / append_section). Formats
        # in _quarto.yml follow the `formats` parameter; a document-level
        # `format:` block in the caller's frontmatter overrides them.
        yml_text = _E._tpl(templates.BESPOKE_YML).render(
            {"jupyter_kernel": kernel, "pdf_web": pdf_web_requested}
        )
        kept_formats = [f for f in ("html", "pdf", "docx") if f in formats]
        for fmt in ("html", "pdf", "docx"):
            if fmt not in kept_formats:
                yml_text = _drop_yaml_block(yml_text, fmt)
        (root / "_quarto.yml").write_text(yml_text)
        fm_text = ""
        if frontmatter_yaml is not None and frontmatter_yaml.strip():
            try:
                parsed = yaml.safe_load(frontmatter_yaml)
            except yaml.YAMLError as exc:
                shutil.rmtree(root, ignore_errors=True)
                return {"ok": False, "error": f"frontmatter_yaml is not valid YAML: {exc}"}
            if parsed is None:
                shutil.rmtree(root, ignore_errors=True)
                return {"ok": False, "error": "frontmatter_yaml is empty"}
            if not isinstance(parsed, dict):
                shutil.rmtree(root, ignore_errors=True)
                return {"ok": False, "error": "frontmatter_yaml must be a YAML mapping"}
            fm_text = frontmatter_yaml.strip()
            if engine_charts_only:
                fm_text += "\nengine_charts_only: true"
        body_text = (body or "").strip()
        if fm_text:
            qmd = f"---\n{fm_text}\n---\n\n{body_text}\n"
        elif body_text:
            qmd = body_text + "\n"
        else:
            qmd = (
                "---\ntitle: \"Untitled\"\n---\n\n"
                "<!-- Write content with reportforge_write_report_body or "
                "reportforge_append_section, then render_report. -->\n"
            )
        (root / "index.qmd").write_text(qmd)
        ref = _E._default_reference_docx()
        if ref is not None and "docx" in kept_formats:
            shutil.copy(ref, root / "assets" / "reference-doc.docx")
        # §1.6: every scaffold writes a fresh report.json — bespoke included,
        # so status/readiness/export key off the requested formats (pdf-web
        # included) instead of a lossy lazy auto-import.
        _write_scaffold_manifest(
            root,
            title=title or slug.replace("-", " ").replace("_", " ").title(),
            brief=subtitle or "",
            profile=preset,
            formats=kept_formats + (["pdf-web"] if pdf_web_requested else []),
        )
        return {
            "ok": True,
            "path": str(root),
            "source": str(root / "index.qmd"),
            "formats": kept_formats + (["pdf-web"] if pdf_web_requested else []),
            "jupyter_kernel": kernel,
            "template": "bespoke",
        }

    kpis = normalized_kpis
    kpis_yaml = ""
    if kpis:
        kpis_yaml = "kpis:\n" + "\n".join(
            f"  - value: {json.dumps(k['value'], ensure_ascii=False)}\n"
            f"    label: {json.dumps(k['label'], ensure_ascii=False)}"
            for k in kpis
        )

    ctx = {
        "title": title or slug.replace("-", " ").title(),
        "subtitle": subtitle,
        "author": author,
        "firm": firm,
        "date": date.today().isoformat(),
        "abstract": abstract,
        "toc": "true" if spec["toc"] else "false",
        "number_sections": "true" if spec["number_sections"] else "false",
        "exhibit_labels": spec.get("exhibit_labels", False),
        "titlepage": spec.get("titlepage", False),
        "papersize": spec.get("papersize", "a4"),
        "confidential_mark": confidential_mark,
        "kpis_yaml": kpis_yaml,
        "organization": organization or (firm if template in _E._EDITORIAL_TEMPLATES else ""),
        "eyebrow": eyebrow,
        "title_layout": title_layout,
        "accent": accent.lower(),
        "metrics": kpis if template in _E._EDITORIAL_TEMPLATES else [],
        "metrics_count": len(kpis) if template in _E._EDITORIAL_TEMPLATES else 0,
        # Cover infographics (editorial templates only): verdict band,
        # exec-summary key-point cards, and the 3-scenario strip.
        "verdict": verdict or "",
        "key_points": normalized_points if template in _E._EDITORIAL_TEMPLATES else [],
        "scenarios": normalized_scenarios if template in _E._EDITORIAL_TEMPLATES else [],
        "scenarios_count": len(normalized_scenarios) if template in _E._EDITORIAL_TEMPLATES else 0,
        # Starter-body figure default: dark figures for the dark theme so the
        # example chart (and any inline chunks) match the page.
        "plotly_default": "plotly_dark" if template in ("portfolio-dark", "ledger-dark") else "plotly_white",
        # Recorded into the scaffolded frontmatter so tools (chart theming)
        # and humans can tell which template a project was built from.
        "template_name": template,
        "jupyter_kernel": kernel,
    }
    for field in (
        "title",
        "subtitle",
        "author",
        "firm",
        "date",
        "abstract",
        "confidential_mark",
        "organization",
        "eyebrow",
        "title_layout",
        "accent",
        "verdict",
    ):
        ctx[f"{field}_yaml"] = _yaml_scalar(ctx[field])
    ctx["metrics_yaml"] = _metric_yaml("metrics", ctx["metrics"])
    ctx["key_points_yaml"] = _str_list_yaml("key-points", ctx["key_points"])
    ctx["scenarios_yaml"] = _scenario_yaml(ctx["scenarios"])
    ctx["accent_typst_yaml"] = _yaml_scalar(str(ctx["accent"]).removeprefix("#"))
    ctx["title_html"] = html_escape(str(ctx["title"]))
    ctx["subtitle_html"] = html_escape(str(ctx["subtitle"]))
    ctx["author_html"] = html_escape(str(ctx["author"]))
    ctx["organization_html"] = html_escape(str(ctx["organization"]))
    ctx["eyebrow_html"] = html_escape(str(ctx["eyebrow"]))
    ctx["date_html"] = html_escape(str(ctx["date"]))
    ctx["abstract_html"] = html_escape(str(ctx["abstract"]))
    ctx["metrics_html"] = "\n".join(
        (
            '<div class="rf-metric">'
            f'<div class="rf-metric-value">{html_escape(metric["value"])}</div>'
            f'<div class="rf-metric-label">{html_escape(metric["label"])}</div>'
            "</div>"
        )
        for metric in ctx["metrics"]
    )
    ctx["verdict_html"] = html_escape(str(ctx["verdict"]))
    ctx["key_points_html"] = "\n".join(
        (
            '<div class="rf-key-point">'
            '<span class="rf-key-point-mark" aria-hidden="true"></span>'
            f"<p>{html_escape(point)}</p>"
            "</div>"
        )
        for point in ctx["key_points"]
    )
    ctx["scenarios_html"] = "\n".join(
        (
            f'<div class="rf-scenario{" rf-scenario-base" if idx == 1 else ""}">'
            f'<div class="rf-scenario-label">{html_escape(scenario["label"])}</div>'
            f'<div class="rf-scenario-value">{html_escape(scenario["value"])}</div>'
            f'<div class="rf-scenario-detail">{html_escape(scenario["detail"])}</div>'
            "</div>"
        )
        for idx, scenario in enumerate(ctx["scenarios"])
    )
    if template == "modern":
        # Modern briefs use a custom typst template for the PDF path —
        # `format: pdf` rejects template-partials, so the yml declares
        # `format: typst` and render_report() maps requested 'pdf' to it.
        (root / "_quarto.yml").write_text(_E._tpl(templates.MODERN_YML).render(ctx))
        (assets / "typst-template.typ").write_text(templates.MODERN_TYPT_TEMPLATE)
        (assets / "typst-show.typ").write_text(templates.MODERN_TYPT_SHOW)
        brand_tpl = templates.BRAND_YML
        styles_extra = templates.MODERN_STYLES_EXTRA
        body_tpl = templates.MODERN_QMD
    elif template in _E._EDITORIAL_TEMPLATES:
        if template == "studio":
            yml_tpl = templates.STUDIO_YML
            typt_tpl = templates.STUDIO_TYPT_TEMPLATE
            show_tpl = templates.STUDIO_TYPT_SHOW
            header_name = "studio-header.html"
            brand_tpl = templates.STUDIO_BRAND_YML
            styles_extra = templates.STUDIO_STYLES_EXTRA
        elif template == "portfolio-light":
            yml_tpl = templates.PORTFOLIO_YML
            typt_tpl = templates.PORTFOLIO_LIGHT_TYPT_TEMPLATE
            show_tpl = templates.PORTFOLIO_LIGHT_TYPT_SHOW
            header_name = "portfolio-header.html"
            brand_tpl = templates.PORTFOLIO_LIGHT_BRAND_YML
            styles_extra = templates.PORTFOLIO_LIGHT_STYLES_EXTRA
        elif template == "ledger-light":
            yml_tpl = templates.PORTFOLIO_YML
            typt_tpl = templates.LEDGER_LIGHT_TYPT_TEMPLATE
            show_tpl = templates.LEDGER_LIGHT_TYPT_SHOW
            header_name = "portfolio-header.html"
            brand_tpl = templates.LEDGER_LIGHT_BRAND_YML
            styles_extra = templates.LEDGER_LIGHT_STYLES_EXTRA
        elif template == "ledger-dark":
            yml_tpl = templates.PORTFOLIO_YML
            typt_tpl = templates.LEDGER_DARK_TYPT_TEMPLATE
            show_tpl = templates.LEDGER_DARK_TYPT_SHOW
            header_name = "portfolio-header.html"
            brand_tpl = templates.LEDGER_DARK_BRAND_YML
            styles_extra = templates.LEDGER_DARK_STYLES_EXTRA
        else:
            yml_tpl = templates.PORTFOLIO_YML
            typt_tpl = templates.PORTFOLIO_DARK_TYPT_TEMPLATE
            show_tpl = templates.PORTFOLIO_DARK_TYPT_SHOW
            header_name = "portfolio-header.html"
            brand_tpl = templates.PORTFOLIO_DARK_BRAND_YML
            styles_extra = templates.PORTFOLIO_DARK_STYLES_EXTRA
        (root / "_quarto.yml").write_text(_E._tpl(yml_tpl).render(ctx))
        (assets / "typst-template.typ").write_text(typt_tpl)
        (assets / "typst-show.typ").write_text(show_tpl)
        # Portfolio variants reuse the studio header markup (same eyebrow /
        # title / meta / metrics contract); the variant stylesheet dresses it.
        (assets / header_name).write_text(
            _E._tpl(templates.STUDIO_HTML_HEADER).render(ctx)
        )
        body_tpl = templates.STUDIO_QMD
    else:
        (root / "_quarto.yml").write_text(_E._tpl(templates.QUARTO_YML).render(ctx))
        brand_tpl = templates.BRAND_YML
        styles_extra = (
            templates.WHITEPAPER_STYLES_EXTRA if template == "whitepaper" else ""
        )
        if spec.get("titlepage"):
            # Quarto 1.10/pandoc 3.8 have no native format:typst titlepage,
            # so titlepage templates ship their own article partials.
            (assets / "typst-template.typ").write_text(templates.WHITEPAPER_TYPT_TEMPLATE)
            (assets / "typst-show.typ").write_text(templates.WHITEPAPER_TYPT_SHOW)
        body_tpl = {
            "standard": templates.INDEX_QMD,
            "memo": templates.MEMO_QMD,
            "whitepaper": templates.WHITEPAPER_QMD,
        }
        # Typed research bodies (earnings recap, outlooks, briefs, ...)
        # share the same pipeline; only the starter .qmd differs.
        body_tpl.update(templates.DOMAIN_BODY_TEMPLATES)
        body_tpl = body_tpl[template]
    (root / "_brand.yml").write_text(brand_tpl)
    styles = templates.STYLES_SCSS + styles_extra
    (root / "styles.scss").write_text(_E._tpl(styles).render(ctx))
    body = _E._tpl(body_tpl).render(ctx)
    kept_formats = [f for f in ("html", "pdf", "docx") if f in formats]
    yml = (root / "_quarto.yml").read_text()
    # The modern/editorial/whitepaper-titlepage templates declare
    # `format: typst` in place of `format: pdf` (format: pdf rejects
    # template-partials and silently ignores typst-only keys like
    # titlepage). Treat pdf<->typst as one slot for keep/drop decisions.
    yml_fmt_key = "typst" if "  typst:" in yml else "pdf"
    for fmt in ("html", "pdf", "docx"):
        if fmt not in kept_formats:
            yml = _drop_yaml_block(yml, yml_fmt_key if fmt == "pdf" else fmt)
    (root / "_quarto.yml").write_text(yml)
    (root / "index.qmd").write_text(body)
    if engine_charts_only:
        _set_frontmatter_flag(root / "index.qmd", "engine_charts_only", True)
    ref = _E._default_reference_docx()
    if ref is not None and "docx" in kept_formats:
        shutil.copy(ref, root / "assets" / "reference-doc.docx")
    _write_scaffold_manifest(
        root,
        title=title or slug.replace("-", " ").replace("_", " ").title(),
        brief=subtitle or "",
        profile=preset,
        formats=kept_formats + (["pdf-web"] if pdf_web_requested else []),
        report_brief=report_brief,
    )
    return {"ok": True, "path": str(root), "source": str(root / "index.qmd"), "formats": kept_formats, "jupyter_kernel": kernel}


def _profile_matrix_error(key: str, value) -> str:
    supported = {axis: list(vals) if vals else "<template-name>"
                 for axis, vals in _E._PROFILE_AXES.items()}
    return (f"profile {key}={value!r} not supported; supported matrix: "
            f"{supported}; overridable axes: {list(_E._PROFILE_OVERRIDABLE)} "
            "(theme/layout/brand/report_type are fixed per preset)")


def _profile_for_template(template: str, pdf_web_requested: bool = False,
                          overrides: dict | None = None) -> tuple[dict | None, str | None]:
    """Resolve the §1.2 profile preset for a template + legal overrides.

    Returns (profile, error): error names the supported matrix, never a
    bare rejection. Unknown templates still resolve (report_type echoes the
    name, e.g. bespoke) — template existence is scaffold's job, not the
    matrix's.
    """
    base = {
        "report_type": template,
        "brand": "quantflow",
        "theme": "dark" if "dark" in template else "light",
        "layout": "magazine",
        "output_profile": "web" if pdf_web_requested else "editorial",
        "policy": "draft",
    }
    for key, value in (overrides or {}).items():
        allowed = _E._PROFILE_AXES.get(key, "unknown-axis")
        if key not in _E._PROFILE_OVERRIDABLE or value not in (allowed or ()):
            return None, _profile_matrix_error(key, value)
        base[key] = value
    return base, None


def _write_scaffold_manifest(root: Path, title: str, brief: str,
                             profile: dict, formats: list[str],
                             report_brief: dict | None = None) -> None:
    manifest_mod.create(
        str(root),
        title=title,
        brief=brief,
        profile=profile,
        formats=list(formats),
        actor="tool:scaffold",
        template_version=template_version(),
        report_brief=report_brief,
    )


def template_version() -> str:
    """C-2 R1-F4: content hash (12-hex) of the template assets.

    A version constant would never move on template edits (``__version__``
    is ``0.1.0`` regardless) — the hash makes every template change
    visible in every future manifest. Phase 2: hashes the asset tree
    (templates/_assets/**) instead of two module files. Computed live so
    working-tree edits stamp honestly; old manifests keep theirs forever.
    """
    return templates.content_hash()


def _drop_yaml_block(text: str, top_key: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    skipping = False
    target = f"  {top_key}:"
    target_indent = len(target) - len(target.lstrip())
    for line in lines:
        if line.startswith(target):
            skipping = True
            continue
        if skipping:
            stripped = line.lstrip(" \t")
            indentation = len(line) - len(stripped)
            if line.strip() and indentation <= target_indent:
                skipping = False
                out.append(line)
            continue
        out.append(line)
    return "".join(out)


def _yaml_scalar(value: object) -> str:
    """Serialize a scalar using JSON, a safe YAML 1.2 subset."""
    return json.dumps(str(value), ensure_ascii=False)


def _normalize_kpis(
    kpis: list[dict] | None,
    template: str,
) -> tuple[list[dict[str, str]], str | None]:
    if kpis is None:
        if template == "modern":
            return [
                {"value": "+62 bps", "label": "Realized alpha"},
                {"value": "0.94", "label": "Signal IC"},
                {"value": "18.3%", "label": "Dispersion"},
                {"value": "-0.21", "label": "Crowding z"},
            ], None
        return [], None
    if not isinstance(kpis, list) or not all(isinstance(item, dict) for item in kpis):
        return [], "kpis must be a list of objects with value and label fields"
    if any("value" not in item or "label" not in item for item in kpis):
        return [], "kpis must be a list of objects with value and label fields"
    if len(kpis) > 6:
        return [], "kpis supports at most 6 items"
    return [
        {"value": str(item["value"]), "label": str(item["label"])}
        for item in kpis
    ], None


def _metric_yaml(key: str, metrics: list[dict[str, str]]) -> str:
    if not metrics:
        return ""
    return f"{key}:\n" + "\n".join(
        f"  - value: {json.dumps(metric['value'], ensure_ascii=False)}\n"
        f"    label: {json.dumps(metric['label'], ensure_ascii=False)}"
        for metric in metrics
    )


def _normalize_key_points(
    key_points: list[str] | None,
) -> tuple[list[str], str | None]:
    if key_points is None:
        return [], None
    if not isinstance(key_points, list) or not all(
        isinstance(item, str) for item in key_points
    ):
        return [], "key_points must be a list of strings"
    if len(key_points) > 4:
        return [], "key_points supports at most 4 items"
    return [str(item) for item in key_points], None


def _normalize_scenarios(
    scenarios: list[dict] | None,
) -> tuple[list[dict[str, str]], str | None]:
    if scenarios is None:
        return [], None
    if not isinstance(scenarios, list) or not all(
        isinstance(item, dict) for item in scenarios
    ):
        return [], "scenarios must be a list of objects"
    if scenarios and len(scenarios) != 3:
        return [], "scenarios must be empty or exactly 3 items (bear/base/bull)"
    if any(
        "label" not in item or "value" not in item or "detail" not in item
        for item in scenarios
    ):
        return [], "scenarios items need label, value, and detail fields"
    return [
        {
            "label": str(item["label"]),
            "value": str(item["value"]),
            "detail": str(item["detail"]),
        }
        for item in scenarios
    ], None


def _str_list_yaml(key: str, items: list[str]) -> str:
    if not items:
        return ""
    return f"{key}:\n" + "\n".join(
        f"  - {json.dumps(item, ensure_ascii=False)}" for item in items
    )


def _scenario_yaml(scenarios: list[dict[str, str]]) -> str:
    if not scenarios:
        return ""
    return "scenarios:\n" + "\n".join(
        f"  - label: {json.dumps(s['label'], ensure_ascii=False)}\n"
        f"    value: {json.dumps(s['value'], ensure_ascii=False)}\n"
        f"    detail: {json.dumps(s['detail'], ensure_ascii=False)}"
        for s in scenarios
    )




def scaffold_from_brief(brief: dict) -> dict:
    """Create a report project from a structured report brief (schema
    `report_brief` v1, see src/reportforge/brief.py and
    docs/report-brief-v1.md).

    The brief is validated strictly (all problems reported at once), the
    normalized brief is recorded in the manifest's `report_brief` field,
    and the remaining keys map 1:1 onto scaffold_report kwargs. Validation
    failure returns the standard {"ok": False, ...} shape with an
    `errors` list; template/formats validation stays with scaffold_report.
    """
    from reportforge import brief as brief_mod

    parsed, errors = brief_mod.validate_brief(brief)
    if errors:
        return {
            "ok": False,
            "error": "invalid report_brief (schema "
                     f"{brief_mod.SCHEMA_NAME!r} v{brief_mod.SCHEMA_VERSION}): "
                     + " | ".join(errors),
            "errors": errors,
        }
    kwargs = brief_mod.brief_to_scaffold_kwargs(parsed)
    result = scaffold_report(report_brief=parsed, **kwargs)
    if result.get("ok"):
        result["report_brief"] = {
            "schema": brief_mod.SCHEMA_NAME,
            "version": brief_mod.SCHEMA_VERSION,
        }
    return result
