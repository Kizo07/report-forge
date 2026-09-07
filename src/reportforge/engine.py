"""Scaffold, render, and chart helpers for Quarto-based reports."""

from __future__ import annotations

import base64
import fcntl
import functools
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from html import escape as html_escape
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml
from jinja2 import Template

from reportforge import manifest as manifest_mod
from reportforge import templates

REPORTS_DIR = Path(
    os.environ.get(
        "REPORTFORGE_REPORTS_DIR",
        str(Path.home() / "Documents" / "report-forge" / "reports"),
    )
).expanduser()
QUARTO_TIMEOUT_S = 900
# pdf-web is not a Quarto format: it post-processes the rendered html with
# headless Chromium (print-to-pdf) so JS-rendered/plotly visuals survive.
PUBLIC_FORMATS = ("html", "pdf", "docx", "pdf-web")
RENDER_LOG_TAIL_CHARS = 8000
EXEC_OUTPUT_TAIL = 8192


def _tpl(source: str) -> Template:
    """Jinja template with report-forge's custom delimiters (so YAML/Quarto
    syntax like {# } or $ doesn't collide with Jinja defaults)."""
    return Template(
        source,
        variable_start_string="<%",
        variable_end_string="%>",
        block_start_string="<%%",
        block_end_string="%%>",
        comment_start_string="<##",
        comment_end_string="##>",
    )


@dataclass
class RenderResult:
    ok: bool
    outputs: list[str]
    log_tail: str


# Templates sharing the studio editorial pipeline (hero/compact title,
# eyebrow, organization, 0-6 metrics, accent override, exhibit labels).
_PORTFOLIO_TEMPLATES = {"portfolio-light", "portfolio-dark"}
# Cyan Ledger variants (derived; see scripts/derive_ledger_templates.py).
_LEDGER_TEMPLATES = {"ledger-light", "ledger-dark"}
_EDITORIAL_TEMPLATES = {"studio"} | _PORTFOLIO_TEMPLATES | _LEDGER_TEMPLATES
# Site-gold defaults (Kizo07.github.io); used only when the caller leaves
# the generic scaffold accent untouched.
_PORTFOLIO_DEFAULT_ACCENTS = {"portfolio-light": "#8f621f", "portfolio-dark": "#d9a54e",
                              "ledger-light": "#8f621f", "ledger-dark": "#e3ac55"}


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
        {"name": "whitepaper", "description": "Hedge-fund-style institutional white paper: key takeaways, investment thesis, framework, exhibit-driven analysis, portfolio implications, risk factors. Figures/tables labeled 'Exhibit N' with unified numbering; title page, TOC + numbered sections; html/pdf/docx.", "toc": True, "number_sections": True, "exhibit_labels": True, "papersize": "us-letter", "formats": ["html", "pdf", "docx"]},
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


def _non_engine_charts(workdir: Path) -> list[str]:
    """PNGs whose Software tag names matplotlib (or siblings).

    Engine exports (plotly/kaleido via save_figure, save_chart) carry no
    Software tag; matplotlib always stamps one. A flagship with
    `engine_charts_only: true` must contain zero of these.
    """
    bad = []
    charts = workdir / "charts"
    if not charts.is_dir():
        return bad
    try:
        from PIL import Image as _Image
    except ImportError:
        return bad
    for png in sorted(charts.glob("*.png")):
        try:
            with _Image.open(png) as im:
                sw = str(im.info.get("Software", ""))
        except Exception:
            continue
        if "matplotlib" in sw.lower() or "seaborn" in sw.lower():
            bad.append(png.name)
    return bad


def _project_is_light(workdir: Path) -> bool:
    qmd = workdir / "index.qmd"
    if not qmd.is_file():
        return False
    text = qmd.read_text()
    if not text.startswith("---"):
        return False
    fence = text.find("\n---", 3)
    head = text[:fence] if fence != -1 else text[:2000]
    return "light" in head


def _white_paper_charts(workdir: Path) -> list[str]:
    """Charts with near-white corners on a light-template project.

    Hand-rolled plotly (default/white template) or default-style matplotlib
    exports pass the Software-tag check but print as white cards on paper
    pages. Corner sampling avoids chart content; tolerance admits antialiased
    edges but not a #ffffff background.
    """
    bad = []
    charts = workdir / "charts"
    if not charts.is_dir():
        return bad
    try:
        from PIL import Image as _Image
    except ImportError:
        return bad
    for png in sorted(charts.glob("*.png")):
        try:
            with _Image.open(png) as im:
                rgb = im.convert("RGB")
                w, h = rgb.size
                boxes = (rgb.crop((0, 0, 12, 12)), rgb.crop((w - 12, 0, w, 12)),
                         rgb.crop((0, h - 12, 12, h)),
                         rgb.crop((w - 12, h - 12, w, h)))
                chans = [0, 0, 0]
                total = 0
                for box in boxes:
                    raw = box.tobytes()
                    n = len(raw) // 3
                    total += n
                    for i in range(3):
                        chans[i] += sum(raw[i::3])
                paper = tuple(c // total for c in chans)
        except Exception:
            continue
        if all(v > 244 for v in paper):
            bad.append(png.name)
    return bad


def _engine_charts_violation(workdir: Path) -> str | None:
    if not _frontmatter_flag(workdir, "engine_charts_only"):
        return None
    bad = _non_engine_charts(workdir)
    if not bad and _project_is_light(workdir):
        bad = _white_paper_charts(workdir)
    if not bad:
        return None
    return (
        "engine_charts_only is set but these charts are non-engine "
        f"fallbacks: {', '.join(bad)}. Rebuild them with the engine "
        "exhibit builders (theme matching the page) or drop the flag — "
        "render refuses to ship fallback charts on a flagship."
    )


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
    accent: str = "#4f46e5",
    metrics: list[dict] | None = None,
    verdict: str = "",
    key_points: list[str] | None = None,
    scenarios: list[dict] | None = None,
    frontmatter_yaml: str | None = None,
    body: str | None = None,
    engine_charts_only: bool = False,
) -> dict:
    specs = {t["name"]: t for t in list_templates()}
    if template not in specs:
        return {"ok": False, "error": f"unknown template {template!r}; available: {sorted(specs)}"}
    spec = specs[template]
    requested_formats = list(spec["formats"]) if formats is None else list(formats)
    unsupported = sorted(set(requested_formats) - set(PUBLIC_FORMATS))
    if unsupported:
        return {
            "ok": False,
            "error": f"unsupported format(s): {', '.join(unsupported)}; available: {list(PUBLIC_FORMATS)}",
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
    if template in _EDITORIAL_TEMPLATES:
        if title_layout not in {"hero", "compact", "minimal"}:
            return {"ok": False, "error": "title layout must be 'hero', 'compact' or 'minimal'"}
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
            return {"ok": False, "error": "accent must be a six-digit hex color such as #4f46e5"}
    if template in (_PORTFOLIO_TEMPLATES | _LEDGER_TEMPLATES) and accent.lower() == "#4f46e5":
        # Portfolio/Ledger templates default to their gold unless the caller
        # passes an explicit accent.
        accent = _PORTFOLIO_DEFAULT_ACCENTS[template]

    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in slug.strip().lower())
    if not slug:
        return {"ok": False, "error": "slug must contain at least one letter, number, '-' or '_'"}
    root = REPORTS_DIR / slug
    if root.exists():
        return {"ok": False, "error": f"report {slug!r} already exists at {root}"}
    assets = root / "assets"
    assets.mkdir(parents=True)
    kernel = _ensure_reportforge_kernel()

    if template == "bespoke":
        # No template opinions: project plumbing only. The caller owns the
        # frontmatter and body (write_report_body / append_section). Formats
        # in _quarto.yml follow the `formats` parameter; a document-level
        # `format:` block in the caller's frontmatter overrides them.
        yml_text = _tpl(templates.BESPOKE_YML).render(
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
        ref = _default_reference_docx()
        if ref is not None and "docx" in kept_formats:
            shutil.copy(ref, root / "assets" / "reference-doc.docx")
        # §1.6: every scaffold writes a fresh report.json — bespoke included,
        # so status/readiness/export key off the requested formats (pdf-web
        # included) instead of a lossy lazy auto-import.
        _write_scaffold_manifest(
            root,
            title=title or slug.replace("-", " ").replace("_", " ").title(),
            brief=subtitle or "",
            template="bespoke",
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
        "organization": organization or (firm if template in _EDITORIAL_TEMPLATES else ""),
        "eyebrow": eyebrow,
        "title_layout": title_layout,
        "accent": accent.lower(),
        "metrics": kpis if template in _EDITORIAL_TEMPLATES else [],
        "metrics_count": len(kpis) if template in _EDITORIAL_TEMPLATES else 0,
        # Cover infographics (editorial templates only): verdict band,
        # exec-summary key-point cards, and the 3-scenario strip.
        "verdict": verdict or "",
        "key_points": normalized_points if template in _EDITORIAL_TEMPLATES else [],
        "scenarios": normalized_scenarios if template in _EDITORIAL_TEMPLATES else [],
        "scenarios_count": len(normalized_scenarios) if template in _EDITORIAL_TEMPLATES else 0,
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
        (root / "_quarto.yml").write_text(_tpl(templates.MODERN_YML).render(ctx))
        (assets / "typst-template.typ").write_text(templates.MODERN_TYPT_TEMPLATE)
        (assets / "typst-show.typ").write_text(templates.MODERN_TYPT_SHOW)
        brand_tpl = templates.BRAND_YML
        styles_extra = templates.MODERN_STYLES_EXTRA
        body_tpl = templates.MODERN_QMD
    elif template in _EDITORIAL_TEMPLATES:
        if template == "studio":
            yml_tpl = templates.STUDIO_YML
            typt_tpl = templates.STUDIO_TYPT_TEMPLATE
            show_tpl = templates.STUDIO_TYPT_SHOW
            header_name = "studio-header.html"
            brand_tpl = templates.BRAND_YML
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
        (root / "_quarto.yml").write_text(_tpl(yml_tpl).render(ctx))
        (assets / "typst-template.typ").write_text(typt_tpl)
        (assets / "typst-show.typ").write_text(show_tpl)
        # Portfolio variants reuse the studio header markup (same eyebrow /
        # title / meta / metrics contract); the variant stylesheet dresses it.
        (assets / header_name).write_text(
            _tpl(templates.STUDIO_HTML_HEADER).render(ctx)
        )
        body_tpl = templates.STUDIO_QMD
    else:
        (root / "_quarto.yml").write_text(_tpl(templates.QUARTO_YML).render(ctx))
        brand_tpl = templates.BRAND_YML
        styles_extra = (
            templates.WHITEPAPER_STYLES_EXTRA if template == "whitepaper" else ""
        )
        body_tpl = {
            "standard": templates.INDEX_QMD,
            "memo": templates.MEMO_QMD,
            "whitepaper": templates.WHITEPAPER_QMD,
        }
        # Typed research bodies (earnings recap, outlooks, briefs, ...)
        # share the same pipeline; only the starter .qmd differs.
        body_tpl.update(getattr(templates, "DOMAIN_BODY_TEMPLATES", {}))
        body_tpl = body_tpl[template]
    (root / "_brand.yml").write_text(brand_tpl)
    styles = templates.STYLES_SCSS + styles_extra
    (root / "styles.scss").write_text(_tpl(styles).render(ctx))
    body = _tpl(body_tpl).render(ctx)
    kept_formats = [f for f in ("html", "pdf", "docx") if f in formats]
    yml = (root / "_quarto.yml").read_text()
    # The modern template declares `format: typst` in place of `format: pdf`
    # (format: pdf rejects template-partials). Treat pdf↔typst as one slot
    # for keep/drop decisions.
    yml_fmt_key = "typst" if template in ({"modern"} | _EDITORIAL_TEMPLATES) else "pdf"
    for fmt in ("html", "pdf", "docx"):
        if fmt not in kept_formats:
            yml = _drop_yaml_block(yml, yml_fmt_key if fmt == "pdf" else fmt)
    (root / "_quarto.yml").write_text(yml)
    (root / "index.qmd").write_text(body)
    if engine_charts_only:
        _set_frontmatter_flag(root / "index.qmd", "engine_charts_only", True)
    ref = _default_reference_docx()
    if ref is not None and "docx" in kept_formats:
        shutil.copy(ref, root / "assets" / "reference-doc.docx")
    _write_scaffold_manifest(
        root,
        title=title or slug.replace("-", " ").replace("_", " ").title(),
        brief=subtitle or "",
        template=template,
        formats=kept_formats + (["pdf-web"] if pdf_web_requested else []),
    )
    return {"ok": True, "path": str(root), "source": str(root / "index.qmd"), "formats": kept_formats, "jupyter_kernel": kernel}


# --- Milestone A Task 1.2: manifest on scaffold + manifest views ------------

_GENRE_TYPES = {
    "standard", "memo", "whitepaper", "bespoke",
    "earnings-recap", "sector-outlook", "thematic-deepdive", "macro-outlook",
    "quant-factor-brief", "technical-brief", "esg-sustainability",
    "crypto-digital", "desk-synthesis",
}


def _profile_for_template(template: str, pdf_web_requested: bool = False) -> dict:
    """Derive the §1.2 profile from the one template selector (constants only)."""
    if template in _GENRE_TYPES:
        report_type = template
    elif template == "studio":
        report_type = "studio-editorial"
    else:
        report_type = template  # portfolio/ledger/modern keep their own name
    return {
        "report_type": report_type,
        "brand": "quantflow",
        "theme": "dark" if "dark" in template else "light",
        "layout": "magazine",
        "output_profile": "web" if pdf_web_requested else "editorial",
        "policy": "draft",
    }


def _write_scaffold_manifest(root: Path, title: str, brief: str,
                             template: str, formats: list[str]) -> None:
    pdf_web = "pdf-web" in formats
    manifest_mod.create(
        str(root),
        title=title,
        brief=brief,
        profile=_profile_for_template(template, pdf_web),
        formats=list(formats),
        actor="tool:scaffold",
    )


def _manifest_view(root: Path) -> tuple[dict | None, str | None]:
    """Manifest projection for status responses; auto-imports legacy dirs.

    Returns (view, error): error carries the loud reason when the manifest
    is corrupt (§2.5), instead of degrading to a silent null.
    """
    try:
        if not (root / manifest_mod.MANIFEST_FILENAME).is_file():
            manifest_mod.import_dir(str(root))
        m = manifest_mod.load(str(root))
    except manifest_mod.ManifestError as exc:
        return None, str(exc)
    d = m.to_dict()
    return {
        "report_id": d["report_id"],
        "title": d["title"],
        "brief": d["brief"],
        "profile": d["profile"],
        "revision": d["revision"],
        "state": d["state"],
        "sections": d["sections"],
        "formats": d["formats"],
    }, None


def open_report(project: str) -> dict:
    """Open a report by slug: brief, profile, sections, revision, state,
    plus missing_work (§4.2 readiness summary) and artifacts (§1.6)."""
    root = REPORTS_DIR / project.strip("/")
    if not root.is_dir():
        return {"ok": False, "error": f"project not found: {project}"}
    view, manifest_error = _manifest_view(root)
    if view is None:
        return {"ok": False, "error": f"project has no readable manifest: {project}",
                "manifest_error": manifest_error}
    out_dir = _output_dir_of(root)
    artifacts = _status_artifacts(root, out_dir)
    return {"ok": True, **view,
            "missing_work": _missing_work_summary(root, view, artifacts),
            "artifacts": artifacts}


def _venv_python() -> Path | None:
    candidates: list[Path] = []
    if configured := os.environ.get("REPORTFORGE_PYTHON"):
        candidates.append(Path(configured).expanduser())
    if sys.prefix != sys.base_prefix:
        candidates.append(Path(sys.executable))
    candidates.append(Path(__file__).resolve().parents[2] / ".venv" / "bin" / "python")
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _ensure_reportforge_kernel() -> str:
    venv_python = _venv_python()
    if not venv_python:
        return "python3"
    try:
        result = subprocess.run(
            [str(venv_python), "-m", "ipykernel", "install", "--user", "--name", "reportforge", "--display-name", "reportforge"],
            capture_output=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "python3"
    return "reportforge" if result.returncode == 0 else "python3"


def render_report(source: str, formats: list[str] | None = None, project: str | None = None) -> dict:
    src = Path(source).expanduser()
    if not src.is_absolute():
        src = Path.cwd() / src
    if not src.exists():
        candidate = REPORTS_DIR / source.strip("/") / "index.qmd"
        if candidate.exists():
            src = candidate
        else:
            return {"ok": False, "error": f"source not found: {source}"}
    src = src.resolve()
    if src.is_dir():
        candidate = src / "index.qmd"
        if not candidate.is_file():
            return {"ok": False, "error": f"project has no index.qmd: {src}"}
        src = candidate
    if not src.is_file():
        return {"ok": False, "error": f"source is not a file: {src}"}
    workdir = _project_root_of(src) or src.parent
    violation = _engine_charts_violation(workdir)
    if violation is not None:
        return {"ok": False, "error": violation}
    env = dict(__import__("os").environ)
    if env.get("OTEL_SDK_DISABLED") not in (None, "true", "false"):
        env["OTEL_SDK_DISABLED"] = "true" if env["OTEL_SDK_DISABLED"].lower() in ("1", "yes", "on") else "false"
    tools_dir = _quarto_tools_dir()
    if tools_dir:
        env["PATH"] = str(tools_dir) + ":" + env.get("PATH", "")
    venv_python = _venv_python()
    if venv_python:
        # Quarto discovers kernelspecs via the python it finds. Without an
        # activated venv it picks system python3, misses nbformat, and falls
        # back to a bare 'python3' kernel. Pin Quarto to the reportforge venv
        # so `execute.jupyter: reportforge` resolves against the right kernel.
        env["QUARTO_PYTHON"] = str(venv_python)
        env["PATH"] = str(venv_python.parent) + ":" + env.get("PATH", "")

    # Render one format per quarto invocation: this Quarto version does not
    # accept comma-joined --to lists, and per-format runs keep failures
    # isolated to the failing format.
    if formats is not None and not formats:
        return {"ok": False, "error": "at least one format is required"}
    requested = list(formats) if formats is not None else None
    if requested is not None:
        unsupported = sorted(set(requested) - set(PUBLIC_FORMATS))
        if unsupported:
            return {
                "ok": False,
                "error": f"unsupported format(s): {', '.join(unsupported)}; available: {list(PUBLIC_FORMATS)}",
            }
    wanted = requested
    pdf_web_requested = False
    if wanted is not None and "pdf-web" in wanted:
        # pdf-web = headless-Chromium print of the html render. Requires html
        # as input (rendered first if not also requested).
        pdf_web_requested = True
        wanted = [f for f in wanted if f != "pdf-web"]
        if "html" not in wanted:
            wanted.insert(0, "html")
    if wanted is None:
        wanted = ["html", "pdf", "docx"] if not _declares_typst_format(workdir) else ["html", "typst", "docx"]
        # restrict to formats configured in _quarto.yml
        yml_txt = (workdir / "_quarto.yml").read_text() if (workdir / "_quarto.yml").exists() else ""
        wanted = [f for f in wanted if f"  {f}:" in yml_txt]
    elif "pdf" in wanted and _declares_typst_format(workdir):
        # Custom-typst projects (modern template) declare `format: typst`;
        # Quarto's `--to pdf` would run its default path and ignore the
        # partials. Map requested pdf → typst for such projects.
        wanted = ["typst" if f == "pdf" else f for f in wanted]

    if not wanted:
        return {"ok": False, "error": "project config contains no supported formats"}

    tails: list[str] = []
    rendered_outputs: list[str] = []
    out_dir = _output_dir_of(workdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for fmt in wanted:
        cmd = ["quarto", "render", str(src), "--to", fmt]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=QUARTO_TIMEOUT_S,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"quarto render ({fmt}) timed out after {QUARTO_TIMEOUT_S}s"}
        full_log = proc.stdout + proc.stderr
        # WS-3: persist the full render log — Typst/PDF failures are the #1
        # iteration blocker; the agent must be able to read the actual error
        # (reportforge_read_project_file output/.render-log-<fmt>.txt).
        try:
            (out_dir / f".render-log-{fmt}.txt").write_text(full_log)
        except OSError:
            pass
        tail = "\n".join(full_log.splitlines()[-15:])
        tails.append(f"--- {fmt} ---\n{tail}")
        if proc.returncode != 0:
            return {
                "ok": False,
                "error": f"quarto render failed for format '{fmt}'",
                "log_tail": tail,
                "render_log": str(out_dir / f".render-log-{fmt}.txt"),
            }
        extension = "pdf" if fmt == "typst" else fmt
        expected = out_dir / f"{src.stem}.{extension}"
        if not expected.is_file():
            return {
                "ok": False,
                "error": f"quarto reported success but output is missing for format '{fmt}'",
                "log_tail": tail,
            }
        rendered_outputs.append(str(expected))

    pdf_web_note = None
    if pdf_web_requested:
        html_path = out_dir / f"{src.stem}.html"
        if not html_path.is_file():
            return {"ok": False, "error": "pdf-web requires an html render, but none was produced"}
        result_pw = _render_pdf_web(workdir, html_path, out_dir, src.stem)
        if not result_pw["ok"]:
            return {
                "ok": False,
                "error": result_pw["error"],
                "log_tail": result_pw.get("log_tail", ""),
                "outputs": sorted(rendered_outputs),
            }
        rendered_outputs.append(result_pw["pdf"])
        pdf_web_note = result_pw["note"]

    # WS-3: machine-readable project state for reportforge_project_status.
    try:
        try:
            rendered_rev = manifest_mod.load(str(workdir)).revision
        except manifest_mod.ManifestError:
            rendered_rev = None
        state = {
            "last_render": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            # Revision binding (RF-05): previews/export can verify the PDF
            # was rendered from the current manifest revision, not an older
            # one. A content edit bumps the revision and invalidates the PDF.
            "manifest_revision": rendered_rev,
            "formats": wanted + (["pdf-web"] if pdf_web_requested else []),
            "outputs": sorted(rendered_outputs),
            "source": str(src),
        }
        (workdir / ".reportforge-state.json").write_text(json.dumps(state, indent=2))
    except OSError:
        pass

    result = {
        "ok": True,
        "outputs": sorted(rendered_outputs),
        "log_tail": "\n".join(tails)[-RENDER_LOG_TAIL_CHARS:],
    }
    if pdf_web_note:
        result["pdf_web_note"] = pdf_web_note
    return result


def write_report_body(source: str, content: str) -> dict:
    """Write/overwrite the .qmd body of a previously scaffolded report project.

    Scoped to projects under REPORTS_DIR. Resolves slugs like render_report
    does. The caller supplies the complete .qmd text including YAML front
    matter.
    """
    src = Path(source).expanduser()
    if not src.is_absolute():
        candidate = REPORTS_DIR / source.strip("/") / "index.qmd"
        if candidate.exists():
            src = candidate
        else:
            src = REPORTS_DIR / source.strip("/")
    try:
        src_resolved = src.resolve()
        root = _project_root_of(src_resolved) or src_resolved.parent
        if REPORTS_DIR.resolve() not in root.parents and root != REPORTS_DIR.resolve():
            return {"ok": False, "error": f"target is not inside the report-forge projects directory ({REPORTS_DIR})"}
    except Exception as exc:
        return {"ok": False, "error": f"cannot resolve target: {exc}"}
    target = src_resolved if src_resolved.suffix == ".qmd" else src_resolved / "index.qmd"
    try:
        target.write_text(content)
    except Exception as exc:
        return {"ok": False, "error": f"write failed: {exc}"}
    return {"ok": True, "source": str(target), "bytes": len(content.encode("utf-8"))}


def _figure_template_is_stock_default(fig) -> bool:
    """True when the figure carries no deliberate theme.

    Covers both a missing template and plotly's stock "plotly" default
    (which plotly-express bakes in at creation): only a theme that differs
    from stock counts as an explicit agent choice worth preserving.
    """
    current = fig.layout.template
    if current is None:
        return True
    try:
        import plotly.io as pio

        return current.to_plotly_json() == pio.templates["plotly"].to_plotly_json()
    except Exception:
        return False


def _project_template_name(project: str | None, out: Path) -> str | None:
    """Best-effort read of a report project's scaffold `template:` value.

    Used for theme-sensitive defaults (dark figures on dark pages). Returns
    None when the project or its frontmatter can't be read — callers then
    keep the figure as supplied.
    """
    root: Path | None = None
    if project and project.strip():
        candidate = REPORTS_DIR / project.strip("/")
        if candidate.is_dir():
            root = candidate
    if root is None:
        try:
            rel = out.resolve().relative_to(REPORTS_DIR.resolve())
            if len(rel.parts) >= 1 and (REPORTS_DIR / rel.parts[0]).is_dir():
                root = REPORTS_DIR / rel.parts[0]
        except (ValueError, OSError):
            root = None
    if root is None:
        return None
    try:
        text = (root / "index.qmd").read_text()
        head = text.split("---", 2)
        if len(head) < 3:
            return None
        front_matter = yaml.safe_load(head[1]) or {}
        # Namespaced key: a bare `template:` is a real Quarto option (custom
        # template path) and must not be hijacked.
        name = front_matter.get("reportforge-template")
        return str(name) if name else None
    except Exception:
        return None


# QuantFlow plotly identity — mirror of alpha_engine.viz.QUANTFLOW_DARK/LIGHT
# (alpha_engine is canonical; this copy lets save_chart style figures
# without a cross-repo import). Gold + teal, matched to the portfolio pages.
# Colorways derive from each palette (primary/secondary + ramp), mirroring
# quantflow_template() — never stock plotly blues, which wash out on paper.
QUANTFLOW_PLOTLY_THEMES = {
    "quantflow-dark": {
        "paper_bg": "#0a0d12", "plot_bg": "#10151d", "font": "#e7eaf0",
        "grid": "#1e2632", "primary": "#c9a227", "secondary": "#56cfc4",
        "positive": "#3fb950", "negative": "#f85149", "muted": "#9aa4b2",
        "ramp": ["#5c5320", "#8a7a2a", "#c9a227", "#56cfc4", "#79c0ff"],
    },
    "quantflow-light": {
        "paper_bg": "#e5ddcc", "plot_bg": "#ebe3d2", "font": "#362e21",
        "grid": "#d3c8b0", "primary": "#8f621f", "secondary": "#14756c",
        "positive": "#2e7d32", "negative": "#c62828", "muted": "#6d6250",
        "ramp": ["#b09a5e", "#8f621f", "#6d4c17", "#14756c", "#0f4c44"],
    },
    "ledger-dark": {
        "paper_bg": "#060a12", "plot_bg": "#0c1220", "font": "#e9eff5",
        "grid": "#14202f", "primary": "#e3ac55", "secondary": "#08bfff",
        "positive": "#3fbfae", "negative": "#e66785", "muted": "#819aaa",
        "ramp": ["#6b5a26", "#a3853c", "#e3ac55", "#08bfff", "#3fbfae"],
    },
    "ledger-light": {
        "paper_bg": "#eef3f6", "plot_bg": "#eef3f6", "font": "#22303c",
        "grid": "#cfd9e1", "primary": "#8f621f", "secondary": "#009ed9",
        "positive": "#237a57", "negative": "#c05563", "muted": "#5a6b7a",
        "ramp": ["#b09a5e", "#8f621f", "#6d4c17", "#009ed9", "#3fbfae"],
    },
}

_PORTFOLIO_TO_QUANTFLOW_TEMPLATE = {
    "portfolio-dark": "quantflow-dark",
    "portfolio-light": "quantflow-light",
    "ledger-dark": "ledger-dark",
    "ledger-light": "ledger-light",
}


def _apply_quantflow_plotly_template(fig, name: str) -> None:
    """Style a figure with the QuantFlow plotly identity (in place)."""
    import plotly.graph_objects as go
    import plotly.io as pio

    pal = QUANTFLOW_PLOTLY_THEMES[name]
    colorway = ([pal["primary"], pal["secondary"], pal["positive"],
                 pal["negative"]] + pal["ramp"] + [pal["muted"]])
    tmpl = go.layout.Template(layout=dict(
        paper_bgcolor=pal["paper_bg"], plot_bgcolor=pal["plot_bg"],
        font=dict(family="Inter, system-ui", color=pal["font"], size=13),
        colorway=colorway,
        xaxis=dict(gridcolor=pal["grid"], zerolinecolor=pal["grid"]),
        yaxis=dict(gridcolor=pal["grid"], zerolinecolor=pal["grid"]),
        hovermode="x unified",
    ))
    pio.templates[name] = tmpl
    fig.update_layout(template=tmpl)


def save_chart(fig_json: str, out_basename: str, width: int = 1400, height: int = 700, scale: int = 2, project: str | None = None, template: str | None = None) -> dict:
    try:
        import plotly.io as pio

        fig = pio.from_json(fig_json)
    except Exception as exc:
        return {"ok": False, "error": f"invalid plotly figure JSON: {exc}"}
    template_applied: str | None = None
    try:
        if template:
            if template in QUANTFLOW_PLOTLY_THEMES:
                _apply_quantflow_plotly_template(fig, template)
                template_applied = template
            else:
                if template not in pio.templates:
                    return {"ok": False, "error": f"unknown plotly template: {template}"}
                fig.update_layout(template=template)
                template_applied = template
        elif _figure_template_is_stock_default(fig):
            # No deliberate figure theme: match the page with the QuantFlow
            # identity so charts sit natively in portfolio reports.
            page = _project_template_name(project, Path(out_basename).expanduser())
            qname = _PORTFOLIO_TO_QUANTFLOW_TEMPLATE.get(page or "")
            if qname is not None:
                _apply_quantflow_plotly_template(fig, qname)
                template_applied = qname
    except Exception as exc:
        return {"ok": False, "error": f"chart theming failed: {exc}"}
    # Sandbox-path translation (lesson of AAPL run 1, 2026-09-01): the agent's
    # sandbox exposes /mnt/user-data/... while this MCP server runs on the
    # host filesystem. Sandbox paths written here would fail silently from the
    # agent's perspective. Translate them into the project's figures/ dir so
    # the rendered qmd can actually find them.
    out_basename = _translate_sandbox_path(out_basename, project)
    out = Path(out_basename).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    png = out.with_suffix(".png")
    html_path = out.with_suffix(".html")
    try:
        fig.write_image(str(png), width=width, height=height, scale=scale)
        fig.write_html(str(html_path), include_plotlyjs="cdn", full_html=True)
    except Exception as exc:
        return {"ok": False, "error": f"chart export failed: {exc}", "partial": {"png": str(png)}}
    return {"ok": True, "png": str(png), "html": str(html_path), "embed_snippet": f"![caption.]({png.name}){{width=90%}}", "template_applied": template_applied}


# --- WS-2: arbitrary asset ingestion --------------------------------------

def save_asset(
    project: str,
    dest_relpath: str,
    content_text: str | None = None,
    content_b64: str | None = None,
) -> dict:
    """Write arbitrary text or base64 binary into a report project.

    Generalizes save_chart beyond plotly: matplotlib PNGs, CSVs, raw HTML
    partials, anything. Confined to the project root (dest may not escape it).
    Exactly one of content_text / content_b64 must be given.
    """
    if not project or not project.strip():
        return {"ok": False, "error": "project is required"}
    root = REPORTS_DIR / project.strip("/")
    if not root.is_dir():
        return {"ok": False, "error": f"project not found: {project}"}
    if (content_text is None) == (content_b64 is None):
        return {"ok": False, "error": "provide exactly one of content_text or content_b64"}
    rel = dest_relpath.strip().lstrip("/")
    if not rel or rel.startswith(".."):
        return {"ok": False, "error": "dest_relpath must be a non-empty relative path"}
    target = (root / rel).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return {"ok": False, "error": f"dest_relpath escapes the project root: {dest_relpath}"}
    if content_text is not None:
        data: bytes = content_text.encode("utf-8")
    elif content_b64 is not None:
        try:
            data = base64.b64decode(content_b64, validate=True)
        except (ValueError, TypeError) as exc:
            return {"ok": False, "error": f"content_b64 is not valid base64: {exc}"}
    else:  # unreachable: XOR checked above
        return {"ok": False, "error": "provide exactly one of content_text or content_b64"}
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    except OSError as exc:
        return {"ok": False, "error": f"write failed: {exc}"}
    rel_out = str(target.relative_to(root.resolve()))
    return {
        "ok": True,
        "project": project.strip("/"),
        "path": str(target),
        "relpath": rel_out,
        "bytes": len(data),
        "embed_snippet": f"![{target.stem}.]({rel_out})",
    }


# --- WS-1: host-side code execution ----------------------------------------

def _exec_enabled() -> bool:
    flag = os.environ.get("REPORTFORGE_EXEC", "").strip().lower()
    return flag not in {"off", "0", "false", "no"}


def _project_optional() -> bool:
    return os.environ.get("REPORTFORGE_PROJECT_OPTIONAL", "").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_project_root(project: str | None, require: bool) -> tuple[Path | None, dict | None]:
    if project and project.strip():
        root = REPORTS_DIR / project.strip("/")
        if not root.is_dir():
            return None, {"ok": False, "error": f"project not found: {project}"}
        return root, None
    if not require:
        return None, None
    return None, {"ok": False, "error": "project is required for execution (set REPORTFORGE_PROJECT_OPTIONAL=1 to allow project-less runs)"}


def _snapshot_project(root: Path) -> dict[Path, float]:
    snap: dict[Path, float] = {}
    for p in root.rglob("*"):
        if p.is_file():
            snap[p] = p.stat().st_mtime
    return snap


def _diff_snapshot(root: Path, before: dict[Path, float]) -> tuple[list[str], list[str]]:
    created: list[str] = []
    modified: list[str] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root))
        mt = p.stat().st_mtime
        if p not in before:
            created.append(rel)
        elif mt != before[p]:
            modified.append(rel)
    return created, modified


def _tail(text: str, limit: int = EXEC_OUTPUT_TAIL) -> str:
    if len(text) <= limit:
        return text
    return "…[truncated]…\n" + text[-limit:]


def run_code(code: str, project: str | None = None, timeout: int = 300) -> dict:
    """Execute Python code on the HOST with the reportforge interpreter.

    Permission model (explicit, accepted by operator): this runs with the host
    user's permissions. cwd is pinned to the project root so relative paths
    land inside the project, but the code CAN reach the full host filesystem —
    this scoping is ergonomic, not a security boundary. Disable with
    REPORTFORGE_EXEC=off.

    Uses the same interpreter as Quarto's jupyter kernel (_venv_python:
    REPORTFORGE_PYTHON > active venv > repo .venv), so run_code and code
    chunks share one environment (pandas/pyarrow/statsmodels available).
    """
    if not _exec_enabled():
        return {"ok": False, "error": "code execution is disabled (REPORTFORGE_EXEC=off)"}
    root, err = _resolve_project_root(project, require=not _project_optional())
    if err:
        return err
    interpreter = _venv_python()
    if interpreter is None:
        return {"ok": False, "error": "no reportforge python interpreter found (REPORTFORGE_PYTHON / venv)"}
    if root is not None:
        cwd: str | None = str(root)
        before = _snapshot_project(root)
    else:
        cwd = None
        before = {}
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [str(interpreter), "-c", code],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"run_code timed out after {timeout}s"}
    except OSError as exc:
        return {"ok": False, "error": f"interpreter launch failed: {exc}"}
    duration = round(time.monotonic() - started, 3)
    if root is not None:
        created, modified = _diff_snapshot(root, before)
    else:
        created, modified = [], []
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout_tail": _tail(proc.stdout),
        "stderr_tail": _tail(proc.stderr),
        "created": created,
        "modified": modified,
        "duration_s": duration,
        "cwd": cwd,
        "note": "host execution with user permissions; stdout/stderr are ground truth — never report results you did not capture" if proc.returncode == 0 else None,
    }


def run_file(path: str, project: str, args: list[str] | None = None, timeout: int = 300) -> dict:
    """Run a script that already lives inside a report project.

    Extension dispatch: .py → reportforge interpreter, .sh/.R via bash/Rscript.
    The file must exist inside the project root. Same permission model and
    capture semantics as run_code.
    """
    if not _exec_enabled():
        return {"ok": False, "error": "code execution is disabled (REPORTFORGE_EXEC=off)"}
    root, err = _resolve_project_root(project, require=True)
    if err:
        return err
    if root is None:  # unreachable with require=True, but satisfies the type checker
        return {"ok": False, "error": "project is required for execution"}
    script = (root / path.lstrip("/")).resolve()
    try:
        script.relative_to(root.resolve())
    except ValueError:
        return {"ok": False, "error": f"script path escapes the project root: {path}"}
    if not script.is_file():
        return {"ok": False, "error": f"script not found in project: {path}"}
    ext = script.suffix.lower()
    interpreter = _venv_python()
    if ext == ".py":
        if interpreter is None:
            return {"ok": False, "error": "no reportforge python interpreter found"}
        cmd = [str(interpreter), str(script)]
    elif ext == ".sh":
        cmd = ["bash", str(script)]
    elif ext == ".r":
        rscript = shutil.which("Rscript")
        if not rscript:
            return {"ok": False, "error": "Rscript not found on PATH"}
        cmd = [rscript, str(script)]
    else:
        return {"ok": False, "error": f"unsupported script type: {ext} (use .py, .sh, or .R)"}
    cmd += list(args or [])
    before = _snapshot_project(root)
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"run_file timed out after {timeout}s"}
    except OSError as exc:
        return {"ok": False, "error": f"script launch failed: {exc}"}
    created, modified = _diff_snapshot(root, before)
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout_tail": _tail(proc.stdout),
        "stderr_tail": _tail(proc.stderr),
        "created": created,
        "modified": modified,
        "duration_s": round(time.monotonic() - started, 3),
        "cwd": str(root),
    }


# --- WS-3: inspection & iteration -------------------------------------------

def project_status(project: str) -> dict:
    """Summarize a report project: files, configured formats, render state."""
    root = REPORTS_DIR / project.strip("/")
    if not root.is_dir():
        return {"ok": False, "error": f"project not found: {project}"}
    files: list[dict] = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(root))
            files.append({"relpath": rel, "bytes": p.stat().st_size})
    formats: list[str] = []
    yml_path = root / "_quarto.yml"
    if yml_path.exists():
        try:
            cfg = yaml.safe_load(yml_path.read_text()) or {}
            fmt_block = cfg.get("format")
            if isinstance(fmt_block, dict):
                formats = list(fmt_block.keys())
        except yaml.YAMLError:
            pass
    state_path = root / ".reportforge-state.json"
    last_render = None
    if state_path.exists():
        try:
            last_render = json.loads(state_path.read_text())
        except json.JSONDecodeError:
            last_render = None
    out_dir = _output_dir_of(root)
    render_logs = sorted(p.name for p in out_dir.glob(".render-log-*.txt")) if out_dir.is_dir() else []
    view, manifest_error = _manifest_view(root)
    artifacts = _status_artifacts(root, out_dir)
    missing_work = _missing_work_summary(root, view, artifacts)
    return {
        "ok": True,
        "project": project.strip("/"),
        "path": str(root),
        "files": files,
        "configured_formats": formats,
        "output_dir": str(out_dir),
        "render_logs": render_logs,
        "last_render": last_render,
        "manifest": view,
        "manifest_error": manifest_error,
        "artifacts": artifacts,
        "missing_work": missing_work,
    }


_STATUS_FORMAT_IDS = {"index.pdf": "pdf", "index.html": "html",
                       "index.docx": "docx"}


def _status_artifacts(root: Path, out_dir: Path) -> list[dict]:
    """Rendered deliverable descriptors with §3.2 contract ids.

    Ids are the format handles (pdf/html/docx), not file stems — the
    missing-work projection keys off these. Paths are project-root-relative
    so they resolve with read_project_file like every other surface.
    """
    artifacts: list[dict] = []
    if out_dir.is_dir():
        for name in ("index.pdf", "index.html", "index.docx"):
            p = out_dir / name
            if p.is_file():
                try:
                    rel = str(p.resolve().relative_to(root.resolve()))
                except ValueError:
                    continue  # output dir outside the project: not addressable
                desc = _file_descriptor(root, rel, _STATUS_FORMAT_IDS[name],
                                        "deliverable", _mime_for_name(name))
                if desc is not None:
                    artifacts.append(desc)
    return artifacts


def _mime_for_name(name: str) -> str:
    return {
        ".pdf": "application/pdf",
        ".html": "text/html",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".png": "image/png",
    }.get(Path(name).suffix.lower(), "application/octet-stream")


def _missing_work_summary(root: Path, view: dict | None, artifacts: list[dict]) -> dict:
    """Compact readiness projection (§4.2): unrendered formats + error counts."""
    if view is None:
        return {"manifest": False, "unrendered_formats": [], "error_counts": {}}
    rendered = {a["id"] for a in artifacts}
    unrendered = [f for f in view.get("formats", [])
                  if f in ("html", "pdf", "docx") and f not in rendered]
    return {"manifest": True, "unrendered_formats": unrendered, "error_counts": {}}


def read_project_file(project: str, relpath: str, max_bytes: int = 32768) -> dict:
    """Read a text file from a report project (qmd, render logs, generated data).

    Binary files return size + a mime guess instead of content. Scoped to the
    project root.
    """
    root = REPORTS_DIR / project.strip("/")
    if not root.is_dir():
        return {"ok": False, "error": f"project not found: {project}"}
    target = (root / relpath.lstrip("/")).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return {"ok": False, "error": f"path escapes the project root: {relpath}"}
    if not target.is_file():
        return {"ok": False, "error": f"file not found: {relpath}"}
    size = target.stat().st_size
    head = target.open("rb").read(8192)
    if b"\x00" in head:
        return {
            "ok": True,
            "relpath": str(target.relative_to(root.resolve())),
            "bytes": size,
            "binary": True,
            "note": "binary file — content not returned",
        }
    data = target.open("r", encoding="utf-8", errors="replace").read(max_bytes + 1)
    truncated = len(data) > max_bytes
    return {
        "ok": True,
        "relpath": str(target.relative_to(root.resolve())),
        "bytes": size,
        "binary": False,
        "truncated": truncated,
        "content": data[:max_bytes],
    }


class _project_lock:
    """Inter-process mutex for one project's check-then-write window.

    §2.2's own rationale says concurrent agents are normal; without this,
    two sessions holding rev N can both pass the stale check and the
    second clobbers the first. stdlib fcntl, project-local lock file.
    """

    def __init__(self, root: Path):
        self._path = root / ".reportforge.lock"
        self._fh = None

    def __enter__(self):
        self._fh = open(self._path, "w", encoding="utf-8")
        assert self._fh is not None
        fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        assert self._fh is not None
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
        return False


def _section_op_errors(fn):
    """Contract §2.5: no exceptions cross the tool boundary.

    Engine entry points return `{ok: False, ...}` dicts; an unexpected
    error (e.g. non-UTF-8 index.qmd raising UnicodeDecodeError) becomes
    a dict too instead of surfacing through fastmcp as an exception.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — boundary contract
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return wrapper


# --- WS-4: incremental composition -------------------------------------------

@_section_op_errors
def append_section(project: str, markdown: str, before: str | None = None,
                   before_section_id: str | None = None,
                   idempotency_key: str | None = None,
                   actor: str = "tool:append_section") -> dict:
    """Append a markdown section to index.qmd, or insert before a heading.

    Additive edits without rewriting the whole body: the YAML frontmatter is
    preserved untouched. With `before` given, the section is inserted above
    the first heading whose text matches (case-insensitive substring);
    `before_section_id` instead addresses an exact section id. With
    `idempotency_key`, a repeat call with the same key is a no-op replay.
    When both anchors are given, `before_section_id` wins.
    """
    root = REPORTS_DIR / project.strip("/")
    if not root.is_dir():
        return {"ok": False, "error": f"project not found: {project}"}
    qmd_path = root / "index.qmd"
    if not qmd_path.is_file():
        return {"ok": False, "error": f"project has no index.qmd: {project}"}
    with _project_lock(root):
        manifest, err = _load_or_import(root)
        if err:
            return err
        assert manifest is not None
        if idempotency_key and idempotency_key in manifest.idempotency_ledger:
            prior = manifest.idempotency_ledger[idempotency_key]
            return {
                "ok": True,
                "idempotent_replay": True,
                "revision": prior.get("revision", manifest.revision),
                "section_id": prior.get("section_id"),
            }
        return _append_locked(root, qmd_path, manifest, markdown, before,
                              before_section_id, idempotency_key, actor)


def _append_locked(root: Path, qmd_path: Path, manifest, markdown: str,
                   before: str | None, before_section_id: str | None,
                   idempotency_key: str | None, actor: str) -> dict:
    text = qmd_path.read_text()
    # Split frontmatter: only when the file opens with a '---' line.
    fm_end = 0
    if text.startswith("---"):
        nl = text.find("\n")
        if nl != -1:
            close = text.find("\n---", nl)
            if close != -1:
                fence_end = text.find("\n", close + 1)
                fm_end = fence_end + 1 if fence_end != -1 else len(text)
    head, body = text[:fm_end], text[fm_end:]
    section = "\n" + markdown.strip() + "\n"
    if before_section_id:
        target = _find_span(_section_spans(text), before_section_id)
        if target is None:
            return {"ok": False, "error": f"unknown section {before_section_id!r}"}
        raw = text.encode("utf-8")
        new_text = (raw[:target["start_byte"]] + section.lstrip("\n").encode("utf-8")
                    + b"\n" + raw[target["start_byte"]:]).decode("utf-8")
        head, body = new_text[:fm_end], new_text[fm_end:]
        action = f"inserted before section {before_section_id!r}"
    elif before:
        pattern = re.compile(r"^#{1,6}[^\n]*" + re.escape(before) + r"[^\n]*$", re.IGNORECASE | re.MULTILINE)
        m = pattern.search(body)
        if not m:
            return {"ok": False, "error": f"no heading matching {before!r} found in index.qmd"}
        insert_at = m.start()
        body = body[:insert_at] + section.lstrip("\n") + "\n" + body[insert_at:]
        action = f"inserted before heading {before!r}"
    else:
        body = body.rstrip("\n") + section
        action = "appended to end of body"
    _write_qmd_atomic(qmd_path, head + body)
    new_id = _first_heading_id(markdown)
    manifest.sections = manifest_mod.scan_sections(head + body)
    manifest_mod.bump(manifest, f"append section {new_id or 'unnamed'}",
                      actor=actor, op="append", section_id=new_id)
    if idempotency_key:
        manifest.idempotency_ledger[idempotency_key] = {
            "revision": manifest.revision, "section_id": new_id}
        while len(manifest.idempotency_ledger) > manifest_mod.IDEMPOTENCY_CAP:
            manifest.idempotency_ledger.pop(next(iter(manifest.idempotency_ledger)))
    manifest_mod.save(manifest, str(root))
    return {
        "ok": True,
        "source": str(qmd_path),
        "action": action,
        "bytes": qmd_path.stat().st_size,
        "idempotent_replay": False,
        "revision": manifest.revision,
        "section_id": new_id,
        "next_step": "render_report to verify the composition",
    }


def _first_heading_id(markdown: str) -> str | None:
    """First heading id of an appended block, fence- and attr-aware.

    Shares the manifest scanner's prose-line logic: `#` lines inside
    fenced code and quarto `{...}` attribute suffixes must not leak into
    the revision log or the idempotency ledger (§2.4).
    """
    for _, line in manifest_mod._iter_prose_lines(markdown.splitlines()):
        m = manifest_mod._HEADING_RE.match(line)
        if not m:
            continue
        title = manifest_mod._ATTR_SUFFIX_RE.sub("", m.group(2)).strip()
        if title:
            return manifest_mod.slugify_section_id(title)
    return None


# --- Milestone A Task 1.3: precise section operations (RF-02) ----------------

def _project_root_or_error(project: str) -> tuple[Path | None, dict | None]:
    root = (REPORTS_DIR / project.strip("/")).resolve()
    if REPORTS_DIR.resolve() not in root.parents and root != REPORTS_DIR.resolve():
        return None, {"ok": False, "error": f"project escapes the reports dir: {project}"}
    if not root.is_dir():
        return None, {"ok": False, "error": f"project not found: {project}"}
    if not (root / "index.qmd").is_file():
        return None, {"ok": False, "error": f"project has no index.qmd: {project}"}
    return root, None


def _section_spans(text: str) -> list[dict]:
    """Sections with byte ranges: heading + lines until next heading of level <=."""
    lines = text.splitlines(keepends=True)
    byte_at = [0]
    for ln in lines:
        byte_at.append(byte_at[-1] + len(ln.encode("utf-8")))
    scanned = manifest_mod.scan_sections(text)
    spans = []
    for i, s in enumerate(scanned):
        start_line = s["line_start"]  # 1-based
        end_line = len(lines) + 1
        for later in scanned[i + 1:]:
            if later["level"] <= s["level"]:
                end_line = later["line_start"]
                break
        spans.append({
            "id": s["id"], "title": s["title"], "level": s["level"],
            "start_byte": byte_at[start_line - 1],
            "end_byte": byte_at[end_line - 1],
        })
    return spans


def _find_span(spans: list[dict], section_id: str) -> dict | None:
    for s in spans:
        if s["id"] == section_id:
            return s
    return None


def _load_or_import(root: Path):
    try:
        if not (root / manifest_mod.MANIFEST_FILENAME).is_file():
            manifest_mod.import_dir(str(root))
        return manifest_mod.load(str(root)), None
    except manifest_mod.ManifestError as exc:
        return None, {"ok": False, "error": str(exc)}


def _stale_response(manifest, since_revision: int) -> dict:
    """Stale-revision context scoped to what changed *since the caller*.

    Contract §2.2: `changed_sections` covers the caller's blind window
    (caller revision → current), not the whole log; the overflow flag
    passes through so a re-applying client knows the scope is partial.
    """
    ev = manifest_mod.events_since(manifest, since_revision)
    changed = []
    for e in ev["events"]:
        op = e.get("op") or ""
        event = {"replace": "replaced", "move": "moved", "delete": "deleted",
                 "append": "added", "create": "added", "import": "added"}.get(op)
        if event and e.get("section_id"):
            changed.append({"id": e["section_id"], "event": event,
                            "revision": e.get("revision")})
    return {
        "ok": False,
        "error": "stale revision",
        "stale_revision": True,
        "current_revision": manifest.revision,
        "changed_sections": changed[-50:],
        "events_truncated": ev["events_truncated"],
        "hint": f"re-read the section, re-apply your change on top of revision {manifest.revision}",
    }


def _check_expected(manifest, expected_revision) -> dict | None:
    if expected_revision is None:
        return {"ok": False, "error": "expected_revision is required (pass the manifest revision you read)"}
    if expected_revision != manifest.revision:
        return _stale_response(manifest, expected_revision)
    return None


def _write_qmd_atomic(qmd_path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(qmd_path.parent), prefix=".index.qmd.",
                               suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, qmd_path)


def _commit_qmd_change(root: Path, manifest, new_text: str, reason: str,
                       actor: str, op: str, section_id: str | None) -> dict:
    """Single transaction: in-memory transform already done; write QMD + bump."""
    _write_qmd_atomic(root / "index.qmd", new_text)
    manifest.sections = manifest_mod.scan_sections(new_text)
    manifest_mod.bump(manifest, reason, actor=actor, op=op, section_id=section_id)
    manifest_mod.save(manifest, str(root))
    return {"ok": True, "revision": manifest.revision, "section_id": section_id}


@_section_op_errors
def get_section(project: str, section_id: str) -> dict:
    """Read one section's markdown, level, and byte range. Read-only."""
    root, err = _project_root_or_error(project)
    if err:
        return err
    assert root is not None
    manifest, err = _load_or_import(root)
    if err:
        return err
    assert manifest is not None
    text = (root / "index.qmd").read_text(encoding="utf-8")
    span = _find_span(_section_spans(text), section_id)
    if span is None:
        return {"ok": False, "error": f"unknown section {section_id!r}"}
    raw = text.encode("utf-8")
    return {
        "ok": True,
        "section_id": section_id,
        "title": span["title"],
        "level": span["level"],
        "markdown": raw[span["start_byte"]:span["end_byte"]].decode("utf-8"),
        "byte_range": [span["start_byte"], span["end_byte"]],
        "revision": manifest.revision,
    }


@_section_op_errors
def replace_section(project: str, section_id: str, markdown: str,
                    expected_revision: int | None = None,
                    actor: str = "tool:replace_section") -> dict:
    """Replace a section's heading + body wholesale; other bytes preserved.

    The replacement should open with a heading: without one the section
    id vanishes from the index and the response carries a `warning`.
    """
    root, err = _project_root_or_error(project)
    if err:
        return err
    assert root is not None
    with _project_lock(root):
        manifest, err = _load_or_import(root)
        if err:
            return err
        assert manifest is not None
        gate = _check_expected(manifest, expected_revision)
        if gate:
            return gate
        text = (root / "index.qmd").read_text(encoding="utf-8")
        raw = text.encode("utf-8")
        span = _find_span(_section_spans(text), section_id)
        if span is None:
            return {"ok": False, "error": f"unknown section {section_id!r}"}
        new_id = _first_heading_id(markdown)
        new_block = markdown if markdown.endswith("\n") else markdown + "\n"
        new_text = (raw[:span["start_byte"]] + new_block.encode("utf-8")
                    + raw[span["end_byte"]:]).decode("utf-8")
        result = _commit_qmd_change(root, manifest, new_text,
                                    f"replace section {section_id}",
                                    actor, "replace", new_id or section_id)
        if new_id is None:
            result["warning"] = (
                f"replacement has no heading: section {section_id!r} is no "
                "longer addressable; re-add a heading to restore it"
            )
            result["section_id"] = section_id
        return result


@_section_op_errors
def move_section(project: str, section_id: str, before_section_id: str | None = None,
                 to_end: bool = False, expected_revision: int | None = None,
                 actor: str = "tool:move_section") -> dict:
    """Move a section block before another section or to the document end.

    A move that changes no bytes (e.g. move-before-self, move-to-end of
    the last section) is a no-op: it returns ok with `moved: False` and
    does not bump the revision (§1.3 — only content-changing ops bump).
    """
    root, err = _project_root_or_error(project)
    if err:
        return err
    assert root is not None
    with _project_lock(root):
        manifest, err = _load_or_import(root)
        if err:
            return err
        assert manifest is not None
        gate = _check_expected(manifest, expected_revision)
        if gate:
            return gate
        if before_section_id is None and not to_end:
            return {"ok": False,
                    "error": "pass before_section_id or to_end=True"}
        if before_section_id == section_id:
            return {"ok": True, "revision": manifest.revision,
                    "section_id": section_id, "moved": False,
                    "notice": "move-before-self is a no-op; revision unchanged"}
        text = (root / "index.qmd").read_text(encoding="utf-8")
        raw = text.encode("utf-8")
        spans = _section_spans(text)
        span = _find_span(spans, section_id)
        if span is None:
            return {"ok": False, "error": f"unknown section {section_id!r}"}
        block = raw[span["start_byte"]:span["end_byte"]]
        rest = raw[:span["start_byte"]] + raw[span["end_byte"]:]
        if to_end:
            if not rest.endswith(b"\n"):
                rest += b"\n"
            new_raw = rest + block
        else:
            assert before_section_id is not None
            # Locate the target in the shortened text (offsets shift after removal).
            target = _find_span(_section_spans(rest.decode("utf-8")), before_section_id)
            if target is None:
                return {"ok": False, "error": f"unknown section {before_section_id!r}"}
            new_raw = rest[:target["start_byte"]] + block + rest[target["start_byte"]:]
        if new_raw == raw:
            return {"ok": True, "revision": manifest.revision,
                    "section_id": section_id, "moved": False,
                    "notice": "move is a no-op (section already in place); revision unchanged"}
        return _commit_qmd_change(root, manifest, new_raw.decode("utf-8"),
                                  f"move section {section_id}",
                                  actor, "move", section_id)


@_section_op_errors
def delete_section(project: str, section_id: str,
                   expected_revision: int | None = None,
                   actor: str = "tool:delete_section") -> dict:
    """Remove a section block."""
    root, err = _project_root_or_error(project)
    if err:
        return err
    assert root is not None
    with _project_lock(root):
        manifest, err = _load_or_import(root)
        if err:
            return err
        assert manifest is not None
        gate = _check_expected(manifest, expected_revision)
        if gate:
            return gate
        text = (root / "index.qmd").read_text(encoding="utf-8")
        raw = text.encode("utf-8")
        span = _find_span(_section_spans(text), section_id)
        if span is None:
            return {"ok": False, "error": f"unknown section {section_id!r}"}
        new_raw = raw[:span["start_byte"]] + raw[span["end_byte"]:]
        return _commit_qmd_change(root, manifest, new_raw.decode("utf-8"),
                                  f"delete section {section_id}",
                                  actor, "delete", section_id)


# --- Milestone A Task 1.4: readiness + review records (RF-04) ------------------

REQUIRED_SECTIONS = {
    # Per-template mandatory-heading keywords (substring-matched, lowercase).
    # Derived from each template's scaffold body; content-neutral / caller-owned
    # bodies (portfolio-*, ledger-*, bespoke) intentionally have no list — the
    # structure check emits STRUCT-NO-REQUIRED-LIST (info) for those.
    "standard": ["executive summary", "analysis", "recommendations"],
    "memo": ["purpose"],
    "whitepaper": ["investment thesis", "analysis"],
    "earnings-recap": ["results at a glance", "guidance", "risks"],
    "sector-outlook": ["executive summary", "valuation", "risks"],
    "thematic-deepdive": ["key takeaways", "risks to the theme", "method and data"],
    "macro-outlook": ["executive summary", "scenarios", "asset implications"],
    "quant-factor-brief": ["signal summary", "performance", "risks"],
    "technical-brief": ["setup", "invalidation", "scenario levels"],
    "esg-sustainability": ["executive summary", "controversies", "financial materiality"],
    "crypto-digital": ["executive summary", "risks", "scenarios"],
    "desk-synthesis": ["executive summary", "recommendation", "scenarios"],
    "modern": ["the signal", "portfolio actions", "risks and invalidation"],
    "studio": ["overview", "figures and tables"],
}

ILLUSTRATIVE_MARKERS = ("ILLUSTRATIVE", "example-data", "Lorem", "Add a short abstract here")

_MONEY_RE = re.compile(r"\$\s?-?[\d,]+(?:\.\d+)?(?:\s?[Uu][Ss][Dd])?|[\d,]+(?:\.\d+)?\s?[Uu][Ss][Dd]")
_PCT_RE = re.compile(r"-?[\d,]+(?:\.\d+)?\s?(?:percent\b|pct\b|bps?\b|%)", re.IGNORECASE)
_ASOF_RE = re.compile(r"[Aa]s of (\d{4}-\d{2}-\d{2})")
_DATE_FM_RE = re.compile(r"^date\s*:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
_FIGREF_RE = re.compile(r"@fig-([\w-]+)")
_FIGANCHOR_RE = re.compile(r"\{#fig-([\w-]+)\}")
_SIGN_NEG_RE = re.compile(r"\b(minus|negative|fell|dropped|declined|lost)\b", re.IGNORECASE)


def _num_value(token: str) -> float | None:
    t = token.replace("$", "").replace(",", "").strip()
    t = re.sub(r"\s*(USD|usd|percent|pct|%|bps?)$", "", t, flags=re.IGNORECASE).strip()
    t = t.replace("−", "-")
    try:
        v = float(t)
    except ValueError:
        return None
    if re.search(r"bps?$", token.strip(), re.IGNORECASE):
        v = v / 100.0
    return v


def _frontmatter_dict(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    close = text.find("\n---", 3)
    if close == -1:
        return {}
    try:
        return yaml.safe_load(text[3:close]) or {}
    except yaml.YAMLError:
        return {}


def _issue(category: str, severity: str, code: str, message: str,
           section_id: str | None = None, detail: str = "") -> dict:
    return {"category": category, "severity": severity, "code": code,
            "message": message, "section_id": section_id, "detail": detail}


def _body_text(text: str) -> str:
    """QMD without the leading YAML frontmatter block (body facts only)."""
    if text.startswith("---"):
        close = text.find("\n---", 3)
        if close != -1:
            fence_end = text.find("\n", close + 1)
            if fence_end != -1:
                return text[fence_end + 1:]
    return text


def _readiness_structure(text: str, spans: list[dict], template: str) -> list[dict]:
    issues = []
    required = REQUIRED_SECTIONS.get(template or "")
    if required is None:
        # Contract §4.1 honest branch: content-neutral / caller-owned bodies
        # have no required-heading list — say so instead of silently passing.
        issues.append(_issue("structure", "info", "STRUCT-NO-REQUIRED-LIST",
                             f"no required-section list defined for template {template!r}"))
    else:
        titles = " ".join(s["title"].lower() for s in spans)
        for keyword in required:
            if keyword.lower() not in titles:
                issues.append(_issue("structure", "error", "STRUCT-MISSING-SECTION",
                                     f"mandatory section missing for template {template!r}: {keyword}"))
    if not spans:
        issues.append(_issue("structure", "error", "STRUCT-NO-SECTIONS",
                             "no sections found in index.qmd"))
    return issues


def _readiness_evidence(text: str, spans: list[dict]) -> list[dict]:
    issues = []
    total = 0
    for i, line in enumerate(text.splitlines(), start=1):
        for marker in ILLUSTRATIVE_MARKERS:
            if marker in line:
                total += 1
                if len([x for x in issues if x["code"] == "EVID-ILLUSTRATIVE"]) < 10:
                    issues.append(_issue("evidence", "warning", "EVID-ILLUSTRATIVE",
                                         f"illustrative content marker {marker!r} (line {i}) — never silently passed"))
                break
    if total > 10:
        # The 10-issue cap is display-only; the count itself stays visible so
        # a marker-heavy draft can never look cleaner than it is.
        issues.append(_issue("evidence", "info", "EVID-ILLUSTRATIVE-OVERFLOW",
                             f"{total} illustrative markers found; showing first 10"))
    return issues


# --- quantity keying (readiness-numerics-v1 §2, stdlib only) --------------------

_TICKER_RE = re.compile(r"\b[A-Z]{2,5}\b")
_TICKER_STOP = frozenset({
    # English words, units, months, and verbs that match [A-Z]{2,5} but are
    # never tickers. Conservative by design: missing a ticker means fewer
    # comparisons, never a false error.
    "USD", "EUR", "GBP", "AND", "THE", "FOR", "WITH", "FROM", "TOTAL",
    "SUM", "NET", "ALL", "PER", "ARE", "WAS", "HAS", "HAVE", "THIS",
    "THAT", "WITH", "WILL", "BE", "BY", "ON", "IN", "TO", "OF", "AS",
    "OR", "AT", "AN", "UP", "ROSE", "FELL", "LOST", "GAINED", "HOLD",
    "BUY", "SELL", "OVER", "UNDER", "OUT", "FIG", "TABLE", "NOTE",
    "YTD", "QOQ", "YOY", "TTM", "EPS", "IPO", "CEO", "CFO",
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP",
    "OCT", "NOV", "DEC", "MON", "TUE", "WED", "THU", "FRI",
})
_WINDOW_WORDS = ("21d", "21-day", "63d", "126d", "252d", "12-month", "monthly",
                 "weekly", "daily", "ytd", "qoq", "yoy", "ttm")
_METRIC_WORDS = ("return", "returns", "vol", "volatility", "close", "closing",
                 "target", "capex", "revenue", "revenues", "margin", "margins",
                 "upside", "downside", "drawdown", "sharpe", "beta", "alpha",
                 "price", "prices", "spot", "dividend", "yield", "sales",
                 "ebitda", "rsi", "macd", "growth", "momentum")
_SPOT_WORDS_RE = re.compile(r"clos(?:e|ing)|prices?|spot\b", re.IGNORECASE)
_TARGET_PHRASE_RE = re.compile(r"target price|price target|fair value|price objective",
                               re.IGNORECASE)
_TARGET_WORD_RE = re.compile(r"\btarget\b", re.IGNORECASE)
_PRICEISH_RE = re.compile(r"clos(?:e|ing)|prices?|spot|target|fair value", re.IGNORECASE)
_HEDGE_RE = re.compile(r"\babout\b|~|roughly|approximately|around|nearly|almost|c\. ?",
                       re.IGNORECASE)
_SIGN_POS_RE = re.compile(r"\b(plus|positive|gained|rose|up|rallied|higher)\b", re.IGNORECASE)
_BARE_NUM_RE = re.compile(r"(?<![\w$.,/-])([\d,]+\.\d+|[\d,]+)(?![\w%-/])")


def _label_tokens(window: str, line: str = "") -> dict:
    """Discriminating tokens near a number: tickers + window/metric words.

    Tickers come from the number's own line only — a ±120-char window
    spans adjacent table rows and would glue peer tickers onto every
    quantity in the block. Metric/window words use the wider window.
    """
    tickers = {t for t in _TICKER_RE.findall(line or window)
               if t not in _TICKER_STOP}
    low = window.lower()
    words = {w for w in _WINDOW_WORDS + _METRIC_WORDS if w in low}
    return {"tickers": tickers, "words": words}


def _same_key(a: dict, b: dict) -> bool:
    """Conservative overlap (§2): same quantity only on shared discriminators.

    Same ticker on both sides, or — when neither side names a ticker —
    shared window/metric words. Anything else: no comparison is made.
    """
    if a["tickers"] and b["tickers"]:
        return bool(a["tickers"] & b["tickers"])
    if a["tickers"] or b["tickers"]:
        return False
    return bool(a["words"] & b["words"])


def _is_table_row(line: str) -> bool:
    return line.lstrip().startswith("|")


def _governor_kind(before: str, after: str, header_word: str = "") -> str | None:
    """The word governing a number: nearest price/metric language before it.

    Whole-window presence tests misfire on mixed sentences ("closed at $S.
    Price target $T" — both words sit in both windows). The rightmost match
    in the ~40 chars before the number is what the number belongs to; a
    trailing target phrase ("$X price target") and the table column header
    are the only fallbacks. Returns spot/target/other/None.
    """
    cands: list[tuple[int, str]] = []
    for m in _TARGET_PHRASE_RE.finditer(before):
        cands.append((m.end(), "target"))
    for m in _SPOT_WORDS_RE.finditer(before):
        cands.append((m.end(), "spot"))
    for m in _TARGET_WORD_RE.finditer(before):
        cands.append((m.end(), "target"))
    if cands:
        return sorted(cands)[-1][1]
    if _TARGET_PHRASE_RE.search(after) or _TARGET_WORD_RE.search(after):
        return "target"
    low = before.lower()
    if any(w in low for w in _METRIC_WORDS):
        return "other"
    hw = header_word.lower()
    if _TARGET_PHRASE_RE.search(hw) or _TARGET_WORD_RE.search(hw):
        return "target"
    if _SPOT_WORDS_RE.search(hw):
        return "spot"
    if any(w in hw for w in _METRIC_WORDS):
        return "other"
    return None


def _header_cell_for(lines: list[str], line_no: int, pos: int, line_start: int) -> str:
    """Column-header cell above a table-row number (empty when not a table)."""
    idx = line_no - 1
    if idx < 0 or idx >= len(lines) or not _is_table_row(lines[idx]):
        return ""
    start = 0
    while idx > 0 and _is_table_row(lines[idx - 1]):
        idx -= 1
    header = [c.strip() for c in lines[idx].strip().strip("|").split("|")]
    col = lines[line_no - 1][:pos - line_start].count("|")
    return header[col] if col < len(header) else ""


def _pipe_tables(body: str) -> list[list[list[str]]]:
    """Consecutive pipe-row blocks parsed into rows of cells."""
    tables = []
    current: list[list[str]] = []
    for line in body.splitlines():
        if _is_table_row(line):
            current.append([c.strip() for c in line.strip().strip("|").split("|")])
        elif current:
            if len(current) >= 2:
                tables.append(current)
            current = []
    if len(current) >= 2:
        tables.append(current)
    return tables


def _extract_quantities(body: str) -> list[dict]:
    """Every comparable number with its §2 key.

    Money is a price mention only beside spot/target language — a target is
    never a spot (§3 NUM-DERIVED-PCT / NUM-SPOT-DISAGREE scoping). Money
    beside other metric words (revenue, margin, …) gets kind "other" so
    NUM-PROSE-TABLE can still key it. Bare numbers count only within 3
    tokens of a price word (spec §1).
    """
    quantities = []
    claimed = []  # (start, end) spans already claimed by money/pct matches
    lines = body.splitlines()
    line_starts = [0]
    for ln in lines:
        line_starts.append(line_starts[-1] + len(ln.encode("utf-8")) + 1)

    def line_of(pos: int) -> int:
        import bisect
        return min(bisect.bisect_right(line_starts, pos), len(lines))

    for m in _MONEY_RE.finditer(body):
        window = body[max(0, m.start() - 120):m.end() + 60]
        line_no = line_of(m.start())
        before = body[max(0, m.start() - 40):m.start()]
        after = body[m.end():m.end() + 30]
        header = _header_cell_for(lines, line_no, m.start(),
                                  line_starts[line_no - 1])
        kind = _governor_kind(before, after, header)
        if kind is None:
            continue  # money without quantity language is not comparable
        v = _num_value(m.group(0))
        if v is None:
            continue
        near = body[max(0, m.start() - 300):m.start()]
        dates = _ASOF_RE.findall(near)
        quantities.append({"value": v, "kind": kind,
                           "labels": _label_tokens(window, lines[line_no - 1]),
                           "asof": dates[-1] if dates else None,
                           "line": line_no, "pos": m.start(),
                           "table": _is_table_row(lines[line_no - 1])})
        claimed.append((m.start(), m.end()))
    for m in _PCT_RE.finditer(body):
        if any(s <= m.start() < e for s, e in claimed):
            continue
        window = body[max(0, m.start() - 120):m.end() + 60]
        low = window.lower()
        if "vol" in low or "volatility" in low or "std" in low.split():
            kind = "vol_pct"
        elif re.search(r"weight|probability|allocation|scenario", low):
            kind = "weight_pct"
        else:
            kind = "return_pct"
        v = _num_value(m.group(0))
        if v is None or v == 0:
            continue
        before = body[max(0, m.start() - 40):m.start()]
        sign = ("neg" if _SIGN_NEG_RE.search(before)
                else "pos" if _SIGN_POS_RE.search(before) else None)
        line_no = line_of(m.start())
        quantities.append({"value": v, "kind": kind,
                           "labels": _label_tokens(window, lines[line_no - 1]),
                           "asof": None, "line": line_no,
                           "pos": m.start(), "sign": sign,
                           "table": _is_table_row(lines[line_no - 1]),
                           "hedged": _HEDGE_RE.search(window) is not None})
        claimed.append((m.start(), m.end()))
    for m in _BARE_NUM_RE.finditer(body):
        if any(s <= m.start() < e for s, e in claimed):
            continue
        ctx = body[max(0, m.start() - 40):m.end() + 40]
        if _PRICEISH_RE.search(ctx) is None:
            continue
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        window = body[max(0, m.start() - 120):m.end() + 60]
        line_no = line_of(m.start())
        before = body[max(0, m.start() - 40):m.start()]
        after = body[m.end():m.end() + 30]
        header = _header_cell_for(lines, line_no, m.start(),
                                  line_starts[line_no - 1])
        kind = _governor_kind(before, after, header)
        # Bare numbers count only as price mentions (spec §1); a bare
        # metric-word number ("revenue 152") is too ambiguous to key.
        if kind not in ("spot", "target"):
            continue
        near = body[max(0, m.start() - 300):m.start()]
        dates = _ASOF_RE.findall(near)
        quantities.append({"value": v, "kind": kind,
                           "labels": _label_tokens(window, lines[line_no - 1]),
                           "asof": dates[-1] if dates else None,
                           "line": line_no, "pos": m.start(),
                           "table": _is_table_row(lines[line_no - 1])})
    return quantities


def _section_for_line(spans: list[dict], full_line: int) -> str | None:
    current = None
    for s in spans:
        if s.get("line_start", 0) <= full_line:
            current = s.get("id")
        else:
            break
    return current


def _readiness_numerical(body: str, front: dict, spans: list[dict] | None = None,
                         body_offset: int = 0) -> list[dict]:
    """All ten numerics-v1 checks over body quantities + frontmatter.

    Posture per spec: exact-label conflicts and arithmetic contradictions
    are error; fuzzy matches are warning; passes stay silent (the category
    `pass: true` verdict is the signal, so quiet fixtures stay quiet).
    One quantity with N disagreeing mentions yields ONE issue.
    """
    issues = []
    quants = _extract_quantities(body)
    spans = spans or []

    def sec(line: int) -> str | None:
        return _section_for_line(spans, body_offset + line) if spans else None

    def detail_line(line: int) -> str:
        return f"index.qmd:{body_offset + line}"

    # -- NUM-DERIVED-PCT: cover target +Y% vs a body spot $S ------------------
    verdict = str(front.get("verdict", ""))
    target_raw = front.get("target", "")
    pct_m = _PCT_RE.search(verdict)
    tgt_m = _MONEY_RE.search(str(target_raw) + " " + verdict)
    if tgt_m is None and isinstance(target_raw, (int, float)):
        target = float(target_raw)
    elif tgt_m is None and re.fullmatch(r"[\d,]+(?:\.\d+)?", str(target_raw).strip()):
        # Frontmatter `target: 300` is an exact-value field even without a
        # dollar sign — zero tolerance still applies (spec §3 TARGET-AGREE).
        target = float(str(target_raw).strip().replace(",", ""))
    else:
        target = _num_value(tgt_m.group(0)) if tgt_m else None
    spots = [q for q in quants if q["kind"] == "spot"]
    if pct_m and target and spots:
        claimed = _num_value(pct_m.group(0))
        spot = spots[0]  # document-order first true spot — never a target
        if claimed is not None and spot["value"]:
            derived = (target / spot["value"] - 1) * 100
            if abs(claimed - derived) > 0.5:
                issues.append(_issue(
                    "numerical", "error", "NUM-DERIVED-PCT",
                    f"cover claims {claimed:g}% to ${target:g} but spot "
                    f"${spot['value']:g} implies {derived:+.1f}%",
                    section_id=sec(spot["line"]),
                    detail=f"frontmatter:verdict/target vs {detail_line(spot['line'])}"))
    # -- NUM-SPOT-DISAGREE: clusters keyed by ticker+as-of --------------------
    groups: dict = {}
    order: list = []
    for s in spots:
        key = (s["asof"], frozenset(s["labels"]["tickers"]))
        placed = False
        for i, (ka, _) in enumerate(order):
            same_asof = ka[0] == key[0]
            tick_ok = (ka[1] == key[1] or (not ka[1] and not key[1]))
            if same_asof and tick_ok:
                groups[i].append(s)
                placed = True
                break
        if not placed:
            order.append((key, None))
            groups[len(order) - 1] = [s]
    for members in groups.values():
        if len(members) < 2:
            continue
        vals = [m["value"] for m in members]
        spread = max(vals) - min(vals)
        locs = ", ".join(detail_line(m["line"]) for m in members[:6])
        if spread > 1.0:
            issues.append(_issue(
                "numerical", "error", "NUM-SPOT-DISAGREE",
                f"spot mentions disagree by ${spread:.2f} "
                f"(as-of {members[0]['asof'] or 'unstated'})",
                section_id=sec(members[0]["line"]), detail=locs))
        elif spread > 0.05:
            issues.append(_issue(
                "numerical", "warning", "NUM-SPOT-DISAGREE",
                f"spot mentions differ by ${spread:.2f} — rounding gray zone",
                section_id=sec(members[0]["line"]), detail=locs))
    # -- price-fact as-of dates (tables, captions, price windows) -------------
    price_dates: list[tuple[str, int]] = []  # (date, body line)
    for m in _ASOF_RE.finditer(body):
        line_no = body.count("\n", 0, m.start()) + 1
        line = body.splitlines()[line_no - 1]
        is_price_fact = (
            _is_table_row(line)
            or "fig" in line.lower() or "caption" in line.lower()
            or any(q["kind"] in ("spot", "target")
                   and m.start() <= q["pos"] < m.start() + 400
                   for q in quants)
        )
        if is_price_fact:
            price_dates.append((m.group(1), line_no))
    fm_date = front.get("date")
    fm_date = str(fm_date) if fm_date is not None else None
    for d, line_no in sorted(set(price_dates)):
        if fm_date and d > fm_date:
            issues.append(_issue(
                "numerical", "error", "NUM-ASOF-FUTURE",
                f"as-of {d} is later than frontmatter date {fm_date}",
                section_id=sec(line_no), detail=detail_line(line_no)))
    if price_dates:
        from collections import Counter
        mode = Counter(d for d, _ in price_dates).most_common(1)[0][0]
        outliers = sorted({d for d, _ in price_dates if d != mode})
        if outliers:
            issues.append(_issue(
                "numerical", "warning", "NUM-ASOF-MIXED",
                f"as-of mode {mode}; outliers: {', '.join(outliers)}"))
    # -- NUM-SIGN-CONFLICT: prose sign vs same-key table row ------------------
    prose_pcts = [q for q in quants
                  if q["kind"] == "return_pct" and not q["table"] and q.get("sign")]
    if prose_pcts:
        for line in body.splitlines():
            if not _is_table_row(line):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 2:
                continue
            row_labels = _label_tokens(" ".join(cells))
            for cell in cells[1:]:
                cm = _PCT_RE.search(cell) or _MONEY_RE.search(cell)
                if not cm:
                    continue
                v = _num_value(cm.group(0))
                if v is None:
                    continue
                cell_neg = cell.strip().startswith(("-", "−")) or \
                    _SIGN_NEG_RE.search(cell) is not None
                cell_pos = cell.strip().startswith("+") or \
                    _SIGN_POS_RE.search(cell) is not None
                for p in prose_pcts:
                    if round(abs(p["value"]), 4) != round(abs(v), 4):
                        continue
                    if not _same_key(p["labels"], row_labels):
                        continue
                    conflict = ((p["sign"] == "neg" and cell_pos and not cell_neg)
                                or (p["sign"] == "pos" and cell_neg and not cell_pos))
                    if conflict:
                        issues.append(_issue(
                            "numerical", "error", "NUM-SIGN-CONFLICT",
                            f"prose states {'-' if p['sign'] == 'neg' else '+'}{abs(v):g} "
                            f"but table shows {cell.strip()[:24]}",
                            detail=f"{detail_line(p['line'])} vs table row: {line.strip()[:120]}"))
                        break
    # -- NUM-PROSE-TABLE: prose repeats a table quantity, mismatch ------------
    # Best-match pairing per table quantity: the closest same-key prose
    # mention decides. An exact repeat elsewhere must not let a distant
    # prose number fire against this cell (or vice versa).
    _COMPARABLE = ("spot", "target", "other", "return_pct")
    table_quants = [q for q in quants if q["table"] and q["kind"] in _COMPARABLE]
    prose_quants = [q for q in quants if not q["table"] and q["kind"] in _COMPARABLE]
    for t in table_quants:
        best = None  # (delta, prose_quant, threshold)
        for p in prose_quants:
            if t["kind"] != p["kind"] or not _same_key(t["labels"], p["labels"]):
                continue
            delta = abs(t["value"] - p["value"])
            if t["kind"] == "return_pct":
                threshold = 2.0 if p.get("hedged", False) else 0.05
            else:
                threshold = 0.5  # precise quote vs rounded cell: pass
            if best is None or delta < best[0]:
                best = (delta, p, threshold)
        if best is None:
            continue
        delta, p, threshold = best
        if delta <= threshold:
            continue
        if t["kind"] == "return_pct":
            issues.append(_issue(
                "numerical", "warning", "NUM-PROSE-TABLE",
                f"prose {p['value']:g} vs table {t['value']:g} "
                f"(Δ {delta:g}pp{', hedged' if p.get('hedged', False) else ''})",
                section_id=sec(p["line"]),
                detail=f"{detail_line(p['line'])} vs {detail_line(t['line'])}"))
        else:
            issues.append(_issue(
                "numerical", "warning", "NUM-PROSE-TABLE",
                f"prose ${p['value']:g} vs table ${t['value']:g}",
                section_id=sec(p["line"]),
                detail=f"{detail_line(p['line'])} vs {detail_line(t['line'])}"))
    # -- NUM-SCENARIO-WEIGHTS: weights sum to 100 ± 0.5 ------------------------
    weights = []
    scenarios = front.get("scenarios")
    if isinstance(scenarios, list):
        for s in scenarios:
            if isinstance(s, dict) and isinstance(s.get("value"), (int, float)):
                weights.append(float(s["value"]))
    if len(weights) >= 2 and abs(sum(weights) - 100) > 0.5:
        issues.append(_issue("numerical", "error", "NUM-SCENARIO-WEIGHTS",
                             f"scenario weights sum to {sum(weights):g}, not 100"))
    # -- NUM-SCENARIO-RECOMPUTE: weights × returns vs stated figure -----------
    pairs, tail_open = _scenario_pairs(front, body)
    stated, stated_hedged = _stated_weighted_return(front, body)
    if pairs and stated is not None:
        lo = sum(w * (r if r is not None else -20.0) for w, r, _ in pairs) / 100.0
        hi = sum(w * (r if r is not None else 20.0) for w, r, _ in pairs) / 100.0
        tol = 4.0 if stated_hedged else 2.0
        if tail_open:
            # Bounded, not exact: warn only when the stated figure sits
            # outside the whole feasible band by more than tolerance.
            if stated < lo - tol or stated > hi + tol:
                issues.append(_issue(
                    "numerical", "warning", "NUM-SCENARIO-RECOMPUTE",
                    f"weights × returns recompute to {lo:.1f}–{hi:.1f}% "
                    f"but stated {stated:g}% (tail scenario unparseable — bounded)",
                    detail="frontmatter:scenarios vs body/scenario prose"))
        elif abs(sum(w * r for w, r, _ in pairs) / 100.0 - stated) > tol:
            recomputed = sum(w * r for w, r, _ in pairs) / 100.0
            issues.append(_issue(
                "numerical", "error", "NUM-SCENARIO-RECOMPUTE",
                f"weights × returns recompute to {recomputed:.1f}% "
                f"but stated {stated:g}% (Δ > {tol:g}pp)",
                detail="frontmatter:scenarios vs stated weighted figure"))
    # -- NUM-TARGET-AGREE: cover target vs scenario-table base target ---------
    if target is not None:
        cover_target = target
        for table in _pipe_tables(body):
            for row in table[1:]:
                if not row or not re.search(r"\bbase\b", row[0], re.IGNORECASE):
                    continue
                for cell in row[1:]:
                    cm = _MONEY_RE.search(cell)
                    if not cm:
                        continue
                    base_target = _num_value(cm.group(0))
                    if (cover_target is not None and base_target is not None
                            and abs(cover_target - base_target) > 0):
                        issues.append(_issue(
                            "numerical", "error", "NUM-TARGET-AGREE",
                            f"cover target ${cover_target:g} vs scenario-table "
                            f"base ${base_target:g}",
                            detail=f"frontmatter:target vs {cell.strip()[:60]}"))
                        break
                else:
                    continue
                break
    # -- NUM-TABLE-TOTAL: total/sum/net rows recompute -------------------------
    for table in _pipe_tables(body):
        if len(table) < 3:
            continue
        header, rows = table[0], table[1:]
        total_idx = next((i for i, r in enumerate(rows)
                          if r and re.match(r"(?i)^(total|sum|net|combined)\b",
                                            r[0])), None)
        if total_idx is None:
            continue
        data_rows = [r for i, r in enumerate(rows) if i != total_idx]
        for col in range(1, max(len(r) for r in rows)):
            tcell = rows[total_idx][col] if col < len(rows[total_idx]) else ""
            tm = _MONEY_RE.search(tcell) or _PCT_RE.search(tcell)
            if not tm:
                continue
            tval = _num_value(tm.group(0))
            parts = []
            for r in data_rows:
                if col >= len(r):
                    break
                cm = _MONEY_RE.search(r[col]) or _PCT_RE.search(r[col])
                if not cm:
                    break
                v = _num_value(cm.group(0))
                if v is None:
                    break
                parts.append(v)
            else:
                if tval is None or not parts:
                    continue
                is_pct = "%" in tm.group(0) or "percent" in tm.group(0).lower()
                if is_pct:
                    bad = abs(sum(parts) - tval) > 0.5
                else:
                    bad = abs(sum(parts) - tval) > max(0.5, abs(tval) * 0.01)
                if bad:
                    issues.append(_issue(
                        "numerical", "error", "NUM-TABLE-TOTAL",
                        f"{header[col] if col < len(header) else 'column'} total "
                        f"{tval:g} vs recomputed {sum(parts):g}",
                        detail=f"row: {rows[total_idx][0][:60]}"))
    return issues


def _scenario_pairs(front: dict, body: str) -> tuple[list, bool]:
    """(weight, return-or-None, label) per scenario + tail-open flag."""
    pairs: list = []
    scenarios = front.get("scenarios")
    if isinstance(scenarios, list):
        for s in scenarios:
            if not isinstance(s, dict):
                continue
            w = s.get("value")
            if isinstance(w, bool) or not isinstance(w, (int, float)):
                for k in ("weight", "probability"):
                    if isinstance(s.get(k), (int, float)):
                        w = s[k]
                        break
            if isinstance(w, bool) or not isinstance(w, (int, float)):
                continue
            r = None
            for k in ("return", "pct", "percent", "upside", "expected"):
                v = s.get(k)
                if isinstance(v, bool):
                    continue
                if isinstance(v, (int, float)):
                    r = float(v)
                    break
                if isinstance(v, str):
                    m = _PCT_RE.search(v)
                    if m:
                        r = _num_value(m.group(0))
                        break
            pairs.append((float(w), r, str(s.get("label", "?"))))
    for table in _pipe_tables(body):
        header = [c.lower() for c in table[0]]
        has_label = any("scenario" in h or "case" in h for h in header)
        wi = next((i for i, h in enumerate(header)
                   if "weight" in h or "prob" in h), None)
        ri = next((i for i, h in enumerate(header)
                   if "return" in h or "upside" in h or "pct" in h or "%" in h),
                  None)
        if not (has_label and wi is not None and ri is not None):
            continue
        for row in table[1:]:
            if max(wi, ri) >= len(row):
                continue
            wm = _PCT_RE.search(row[wi]) or _BARE_NUM_RE.search(row[wi])
            rm = _PCT_RE.search(row[ri])
            if not wm:
                continue
            w = _num_value(wm.group(0)) if "%" in wm.group(0) else None
            try:
                w = float(wm.group(1).replace(",", "")) if w is None else w
            except (ValueError, AttributeError):
                continue
            r = _num_value(rm.group(0)) if rm else None
            pairs.append((w, r, row[0][:40]))
    tail_open = any(r is None for _, r, _ in pairs)
    return pairs, tail_open


def _stated_weighted_return(front: dict, body: str) -> tuple[float | None, bool]:
    """The report's own stated blended/expected return, if any."""
    for k in ("expected_return", "weighted_return", "blended_return", "expected"):
        v = front.get(k)
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            return float(v), False
        if isinstance(v, str):
            m = _PCT_RE.search(v)
            if m:
                return _num_value(m.group(0)), _HEDGE_RE.search(v) is not None
    m = re.search(
        r"(?:weighted|expected|blended)[^.\n]{0,60}?([+-]?[\d,]+(?:\.\d+)?\s?(?:percent|pct|%))",
        body, re.IGNORECASE)
    if m:
        return _num_value(m.group(1)), _HEDGE_RE.search(m.group(0)) is not None
    return None, False


def _readiness_presentation(root: Path, text: str) -> list[dict]:
    issues = []
    charts_dir = root / "charts"
    if charts_dir.is_dir():
        charts = sorted(p.name for p in charts_dir.glob("*.png"))
        for name in charts:
            stem = Path(name).stem
            if stem not in text and name not in text:
                issues.append(_issue("presentation", "warning", "PRES-UNREFERENCED-CHART",
                                     f"charts/{name} is never referenced in index.qmd"))
    anchors = set(_FIGANCHOR_RE.findall(text))
    for ref in sorted(set(_FIGREF_RE.findall(text))):
        if ref not in anchors:
            issues.append(_issue("presentation", "error", "PRES-DANGLING-REF",
                                 f"@fig-{ref} has no matching figure anchor"))
    try:
        violation = _engine_charts_violation(root)
    except Exception:
        violation = None
    if violation:
        issues.append(_issue("presentation", "error", "PRES-ENGINE-CHARTS",
                             violation))
    lint_out = _run_figure_lint(root)
    if lint_out is not None:
        issues.append(_issue("presentation", "warning", "PRES-FIGURE-LINT",
                             f"figure_lint reports: {lint_out[:300]}"))
    return issues


def _run_figure_lint(root: Path) -> str | None:
    """Run scripts/figure_lint.py; None when clean/missing, else output tail."""
    script = Path(__file__).resolve().parents[2] / "scripts" / "figure_lint.py"
    if not script.is_file():
        return None
    try:
        run = subprocess.run(
            [sys.executable, str(script), str(root)],
            capture_output=True, text=True, timeout=120)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if run.returncode == 0:
        return None
    out = (run.stdout + "\n" + run.stderr).strip()
    return out[-800:] if out else "figure_lint failed with no output"


def _readiness_editorial(manifest) -> list[dict]:
    if any(r.get("revision") == manifest.revision and r.get("decision") == "approved"
           for r in manifest.reviews):
        return [_issue("editorial", "info", "EDIT-REVIEWED",
                       f"revision {manifest.revision} has an approved review record")]
    return [_issue("editorial", "warning", "EDIT-NEEDS-REVIEW",
                   f"revision {manifest.revision} has no approved review record — judgment is human-only")]


def check_readiness(project: str) -> dict:
    """Unified readiness: structure, evidence, numerical, presentation, editorial.

    Automated checks only; factual accuracy and source quality are explicitly
    out of scope (review §3.6) — see the scope_note in every response.
    """
    root, err = _project_root_or_error(project)
    if err:
        return err
    assert root is not None
    manifest, err = _load_or_import(root)
    if err:
        return err
    assert manifest is not None
    text = (root / "index.qmd").read_text(encoding="utf-8")
    spans = _section_spans(text)
    front = _frontmatter_dict(text)
    body = _body_text(text)
    body_offset = len(text.splitlines()) - len(body.splitlines())
    template = manifest.to_dict().get("profile", {}).get("report_type", "")
    categories = {
        "structure": _readiness_structure(text, spans, template),
        "evidence": _readiness_evidence(text, spans),
        "numerical": _readiness_numerical(body, front, spans, body_offset),
        "presentation": _readiness_presentation(root, text),
        "editorial": _readiness_editorial(manifest),
    }
    cats = {name: {"pass": not any(i["severity"] == "error" for i in iss),
                   "issues": iss} for name, iss in categories.items()}
    ready = all(c["pass"] for c in cats.values())
    return {
        "ok": True,
        "report_id": manifest.report_id,
        "revision": manifest.revision,
        "state": manifest.state,
        "categories": cats,
        "ready_for_review": ready,
        "scope_note": ("automated structure/evidence/presentation checks only — "
                       "not factual accuracy, source quality, or financial claims (review §3.6)"),
    }


def record_review(project: str, revision: int, reviewer: str, decision: str,
                  comments: str = "", section_id: str | None = None,
                  actor: str = "tool:record_review") -> dict:
    """Append a review record to the manifest (§4.3)."""
    root, err = _project_root_or_error(project)
    if err:
        return err
    assert root is not None
    manifest, err = _load_or_import(root)
    if err:
        return err
    assert manifest is not None
    res = manifest_mod.add_review(manifest, revision, reviewer, decision,
                                  comments, section_id)
    if not res.get("ok"):
        return res
    manifest_mod.save(manifest, str(root))
    return {"ok": True, "report_id": manifest.report_id,
            "revision": revision, "decision": decision}


# --- Milestone A Task 1.6: portable export bundle (RF-06) ----------------------

_BUNDLE_FORMATS = ("html", "pdf", "docx")


def _bundle_artifact_id(rel: str) -> tuple[str, str]:
    """(id, role) for a bundle-relative path. Ids are unique by construction.

    Deliverables/previews/charts keep short semantic handles (their source
    dirs are flat with unique stems); everything else derives from the full
    relative path so source/, data/ and *_files/ companions can never
    collide. bundle.json itself is the index — it needs no descriptor.
    """
    p = Path(rel)
    name = p.name
    if name == "manifest.json":
        return "manifest-copy", "metadata"
    if name == "contact-sheet.png":
        return "contact-sheet", "preview"
    m = re.fullmatch(r"page-(\d+)\.png", name)
    if m and "previews" in p.parts:
        return f"page-{m.group(1)}", "preview"
    if p.suffix == ".png" and "previews" in p.parts:
        return f"exhibit-{p.stem}", "preview"
    if name in ("index.pdf", "index.html", "index.docx"):
        return {"index.pdf": "pdf", "index.html": "html",
                "index.docx": "docx"}[name], "deliverable"
    if "charts" in p.parts and p.suffix == ".png":
        return f"exhibit-{p.stem}", "preview"
    if p.parts and p.parts[0] in ("source", "data"):
        return rel.replace("/", "-"), p.parts[0]
    return rel.replace("/", "-"), "companion"


@_section_op_errors
def export_release(project: str, revision: int | None = None, dest: str = ".",
                   include_source: bool = False, include_data: bool = False,
                   actor: str = "tool:export_release") -> dict:
    """Export an approved revision as a self-contained bundle (§3).

    Layout: <dest>/<report_id>/r<rev>/ with deliverables, manifest.json copy,
    bundle.json descriptor index, optional source/ + data/. Overwrites are
    atomic per revision dir (rename-aside, never delete-then-rename); a
    successful export transitions the manifest to exported.
    """
    slug = project.strip("/")
    root = REPORTS_DIR / slug
    if not root.is_dir():
        return {"ok": False, "error": f"project not found: {project}"}
    with _project_lock(root):
        return _export_release_locked(slug, root, revision, dest,
                                      include_source, include_data, actor)


def _export_release_locked(slug: str, root: Path, revision: int | None,
                           dest: str, include_source: bool,
                           include_data: bool, actor: str) -> dict:
    manifest, err = _load_or_import(root)
    if err:
        return err
    assert manifest is not None
    current = manifest.revision
    if revision is not None and revision != current:
        return {"ok": False,
                "error": f"stale revision: requested {revision}, manifest is at revision {current}",
                "current_revision": current}
    if manifest.state not in ("approved", "exported"):
        return {"ok": False,
                "error": f"export requires state approved (current: {manifest.state}) — render drafts freely, release only reviewed revisions"}
    out_dir = _output_dir_of(root)
    if out_dir == root and (root / "output").is_dir():
        out_dir = root / "output"
    required = [f for f in manifest.to_dict().get("formats", []) if f in _BUNDLE_FORMATS]
    missing = [f for f in required if not (out_dir / f"index.{f}").is_file()]
    if missing:
        return {"ok": False,
                "error": f"no rendered output for {', '.join(missing)}: render first (export never auto-renders)"}
    exported_at = datetime.now().astimezone().isoformat()
    dest_root = Path(dest)
    rdir = dest_root / manifest.report_id / f"r{current}"
    tmp = dest_root / manifest.report_id / f".r{current}.tmp-{os.getpid()}"
    aside = dest_root / manifest.report_id / f".r{current}.prev-{os.getpid()}"
    warnings: list[str] = []
    artifacts: list = []
    swapped = False
    try:
        for stale in (tmp, aside):
            if stale.exists():
                shutil.rmtree(stale)
        tmp.mkdir(parents=True)
        for fmt in required:
            shutil.copy2(out_dir / f"index.{fmt}", tmp / f"index.{fmt}")
        for companion in sorted(out_dir.glob("*_files")):
            if companion.is_dir():
                shutil.copytree(companion, tmp / companion.name)
        (tmp / "manifest.json").write_text(
            json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False))
        prev_src = out_dir / "previews" / f"r{current}"
        if prev_src.is_dir():
            shutil.copytree(prev_src, tmp / "previews")
        includes = {"source": False, "data": False}
        if include_source:
            copied = []
            srcd = tmp / "source"
            srcd.mkdir()
            for name in ("index.qmd", "_quarto.yml", "styles.scss", "_brand.yml"):
                p = root / name
                if p.is_file():
                    shutil.copy2(p, srcd / name)
                    copied.append(name)
            includes["source"] = bool(copied)
            if not copied:
                warnings.append("include_source requested but no source files found")
        if include_data:
            data_src = root / "data"
            data_files = ([p for p in data_src.rglob("*") if p.is_file()]
                          if data_src.is_dir() else [])
            if data_files:
                shutil.copytree(data_src, tmp / "data")
                includes["data"] = True
            else:
                warnings.append("include_data requested but data/ is missing or empty")
        artifacts = []
        skipped: list[str] = []
        for p in sorted(tmp.rglob("*")):
            if not p.is_file():
                continue
            rel = str(p.relative_to(tmp))
            aid, role = _bundle_artifact_id(rel)
            desc = _describe_or_skip(tmp, rel, aid, role, _mime_for_name(p.name), skipped)
            if desc is not None:
                artifacts.append(desc)
        if skipped:
            warnings.append(f"artifacts vanished mid-build and were skipped: {', '.join(sorted(skipped))}")
        (tmp / "bundle.json").write_text(json.dumps({
            "schema_version": 1,
            "report_id": manifest.report_id,
            "revision": current,
            "exported_at": exported_at,
            "artifacts": artifacts,
            "includes": includes,
            "delivery": {"adapters": ["local-bundle", "deerflow"], "present_paths": []},
        }, indent=2, ensure_ascii=False))
        # Re-read bundle.json into the descriptor list so disk == response.
        artifacts = json.loads((tmp / "bundle.json").read_text())["artifacts"]
        rdir.parent.mkdir(parents=True, exist_ok=True)
        if rdir.exists():
            os.rename(rdir, aside)  # aside first: no crash window without a bundle
        os.rename(tmp, rdir)
        swapped = True
    except Exception as exc:  # noqa: BLE001 — cleanup + loud dict, never partial
        for stale in (tmp, aside):
            try:
                if stale.exists() and stale != rdir:
                    shutil.rmtree(stale)
            except OSError:
                pass
        # The only survivable failure is after a completed swap (e.g. aside
        # cleanup); anything earlier means no new bundle — fail loudly even
        # though a previous bundle may still sit at rdir.
        if not (swapped and rdir.is_dir()):
            return {"ok": False, "error": f"bundle write failed: {exc}"}
    finally:
        # Best-effort aside removal; a leftover .prev dir never shadows rdir.
        try:
            if aside.exists():
                shutil.rmtree(aside)
        except OSError:
            pass
    tr = manifest_mod.transition(manifest, "exported", actor, f"export r{current}")
    if tr.get("ok"):
        manifest_mod.save(manifest, str(root))
    return {
        "ok": True,
        "report_id": manifest.report_id,
        "revision": current,
        "state": manifest.state,
        "bundle_root": str(Path(manifest.report_id) / f"r{current}"),
        "artifacts": artifacts,
        "warnings": warnings,
        "next_step": "retrieve the bundle at <report_id>/r<rev> under the dest root",
    }


# --- Milestone A Task 1.7: capability discovery (RF-07 slice) -------------------

MCP_TOOL_NAMES_FALLBACK = [
    "reportforge_list_templates", "reportforge_scaffold_report",
    "reportforge_render_report", "reportforge_save_chart",
    "reportforge_write_report_body", "reportforge_publish_report",
    "reportforge_run_code", "reportforge_run_file",
    "reportforge_save_asset", "reportforge_project_status",
    "reportforge_read_project_file", "reportforge_append_section",
    "reportforge_get_section", "reportforge_replace_section",
    "reportforge_move_section", "reportforge_delete_section",
    "reportforge_export_release", "reportforge_check_readiness",
    "reportforge_record_review", "reportforge_render_preview",
    "reportforge_capabilities",
]


def _mcp_tool_names() -> list[str]:
    # mcp.list_tools() is async (and unusable inside a running loop), so the
    # engine keeps this static registry — update it when adding MCP tools.
    return list(MCP_TOOL_NAMES_FALLBACK)


def reportforge_capabilities() -> dict:
    """Capability discovery (§6): templates, profiles, support matrix, env."""
    templates = list_templates()
    matrix = [{
        "report_type": t.get("name"),
        "template": t.get("name"),
        "formats": t.get("formats", []),
        "exhibit_labels": bool(t.get("exhibit_labels", False)),
        "toc": bool(t.get("toc", False)),
        "content_neutral": bool(t.get("content_neutral", False)),
    } for t in templates]
    exec_on = _exec_enabled()
    pdftoppm = shutil.which("pdftoppm")
    return {
        "schema_version": 1,
        "server": "reportforge",
        "templates": templates,
        "profiles": {
            "report_types": [t.get("name") for t in templates],
            "brands": ["quantflow", "neutral"],
            "themes": ["light", "dark"],
            "layouts": ["magazine", "single-column", "chartbook", "compact"],
            "output_profiles": ["editorial", "web", "editable-docx"],
            # Template name → stored manifest profile.report_type for the
            # cases where they differ (only studio today). Discovery and
            # stored profile must agree on the same report (RF-08 inherits).
            "report_type_map": {"studio": "studio-editorial"},
        },
        "support_matrix": matrix,
        "execution": {
            "run_code": exec_on, "run_file": exec_on,
            "interpreter": "reportforge venv",
            "disabled_reason": None if exec_on else "REPORTFORGE_EXEC=off",
        },
        "preview": {
            "supported": True, "backend": "pdftoppm",
            "available": bool(pdftoppm),
            "artifact_ids": ["contact-sheet", "page-<n>", "exhibit-<fig-id>"],
        },
        "delivery": {
            "methods": ["local-bundle", "deerflow-thread-outputs"],
            "requires_env": ["DEERFLOW_THREAD_OUTPUTS_HOST (deerflow only)"],
        },
        "sections": {
            "ops": ["get", "replace", "move", "delete", "append"],
            "optimistic_concurrency": True,
            "idempotent_append": True,
        },
        "manifest": {"schema_version": manifest_mod.SCHEMA_VERSION,
                     "states": list(manifest_mod.STATES)},
        "tools": _mcp_tool_names(),
        "docs": {"flagship_rules": "docs/flagship-rules.md",
                 "contracts": "docs/milestone-a-contracts.md",
                 "journeys": "docs/agent-journeys.md"},
    }


# --- Milestone A Task 1.5: preview artifacts (RF-05) --------------------------

def _render_state_revision(root: Path) -> int | None:
    """Manifest revision stamped at render time (None when unstamped/legacy)."""
    try:
        state = json.loads((root / ".reportforge-state.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
    rev = state.get("manifest_revision") if isinstance(state, dict) else None
    return rev if isinstance(rev, int) else None


def render_preview(project: str, revision: int | None = None) -> dict:
    """Render preview artifacts (contact sheet, pages, exhibits) for a report.

    Contract §5: previews bind to (report_id, revision), are generated only
    from that revision's rendered PDF (no auto-render), live under
    <project>/output/previews/r<rev>/, and are returned as §3.2-shaped
    relative-path artifact descriptors — never host absolute paths.
    Read-only: the manifest revision is never bumped.

    PDF-staleness rule: the PDF must have been rendered from the current
    manifest revision (stamped in .reportforge-state.json at render time).
    A stamped-but-older PDF fails loudly; an unstamped legacy PDF proceeds
    with a warning and pdf_rendered_at_revision null.
    """
    root, err = _project_root_or_error(project)
    if err:
        return err
    assert root is not None
    manifest, err = _load_or_import(root)
    if err:
        return err
    assert manifest is not None
    current = manifest.revision
    if revision is not None and revision != current:
        return {
            "ok": False,
            "error": f"stale revision: requested {revision}, manifest is at revision {current}",
            "current_revision": current,
        }
    rev = current
    warnings: list[str] = []

    pdf_rev = _render_state_revision(root)
    if pdf_rev is not None and pdf_rev != rev:
        return {
            "ok": False,
            "error": (f"PDF was rendered from revision {pdf_rev} but the manifest "
                      f"is at revision {rev}: render_report first (a content edit "
                      f"invalidates previews)"),
            "current_revision": rev,
            "pdf_rendered_at_revision": pdf_rev,
        }
    if pdf_rev is None:
        warnings.append("PDF predates revision stamping; re-render to bind "
                        "previews to an exact revision")

    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        return {"ok": False, "error": "pdftoppm not found on PATH (previews unavailable)"}

    out_dir = _output_dir_of(root)
    if out_dir == root and (root / "output").is_dir():
        out_dir = root / "output"
    pdf = out_dir / "index.pdf"
    if not pdf.is_file():
        return {
            "ok": False,
            "error": f"no rendered PDF for revision {rev}: render first (previews never auto-render), missing {pdf.name}",
        }

    previews_dir = out_dir / "previews" / f"r{rev}"
    try:
        previews_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {"ok": False, "error": f"cannot create previews dir: {exc}"}

    page_count = _pdf_page_count(pdf)
    if page_count < 1:
        return {"ok": False, "error": f"cannot count pages in {pdf.name}: not a readable PDF"}

    pages_dir = previews_dir / "pages"
    try:
        pages_dir.mkdir(parents=True, exist_ok=True)
        run = subprocess.run(  # noqa: S603 fixed binary, fixed args
            [pdftoppm, "-png", "-r", "110", "-scale-to", "1400", pdf, str(pages_dir / "page")],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if run.returncode != 0:
            return {"ok": False, "error": f"pdftoppm page raster failed: {run.stderr.strip()}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "pdftoppm page raster timed out (120s)"}
    except OSError as exc:
        return {"ok": False, "error": f"pdftoppm page raster failed: {exc}"}

    page_files = sorted(pages_dir.glob("page-*.png"), key=_page_sort_key)
    unnumbered = pages_dir / "page.png"
    if not page_files and unnumbered.is_file():
        # poppler names single-page output <prefix>.png (no page number)
        numbered = pages_dir / "page-1.png"
        numbered.write_bytes(unnumbered.read_bytes())
        unnumbered.unlink()
        page_files = [numbered]
    if not page_files:
        return {"ok": False, "error": "pdftoppm produced no page PNGs"}

    contact = _build_contact_sheet(page_files, previews_dir / "contact-sheet.png")
    if contact is None:
        return {"ok": False, "error": "contact sheet composition failed (no page PNGs readable)"}

    artifacts: list[dict] = []
    skipped_previews: list[str] = []
    desc = _describe_or_skip(root, f"output/previews/r{rev}/contact-sheet.png",
                             "contact-sheet", "preview", "image/png", skipped_previews)
    if desc is not None:
        artifacts.append(desc)
    for p in _numbered_pages(page_files):
        desc = _describe_or_skip(root, f"output/previews/r{rev}/pages/page-{p}.png",
                                 f"page-{p}", "preview", "image/png", skipped_previews)
        if desc is not None:
            artifacts.append(desc)

    charts_dir = root / "charts"
    if charts_dir.is_dir():
        for chart in sorted(charts_dir.glob("*.png")):
            desc = _describe_or_skip(root, f"charts/{chart.name}",
                                     f"exhibit-{chart.stem}", "preview", "image/png",
                                     skipped_previews)
            if desc is not None:
                artifacts.append(desc)
    if skipped_previews:
        warnings.append("artifacts vanished mid-build and were skipped: "
                        + ", ".join(sorted(skipped_previews)))

    return {
        "ok": True,
        "report_id": manifest.report_id,
        "revision": rev,
        "page_count": page_count,
        "pdf_rendered_at_revision": pdf_rev,
        "artifacts": artifacts,
        "warnings": warnings,
        "next_step": "retrieve artifacts via read_project_file (binary) or export bundle §3",
    }


def _pdf_page_count(pdf: Path) -> int:
    """Page count via pdfinfo (poppler); -1 when unavailable/unreadable."""
    pdfinfo = shutil.which("pdfinfo")
    if not pdfinfo:
        return -1
    try:
        run = subprocess.run(  # noqa: S603 fixed binary, fixed args
            [pdfinfo, str(pdf)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError):
        return -1
    if run.returncode != 0:
        return -1
    for line in run.stdout.splitlines():
        if line.startswith("Pages:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return -1
    return -1


def _page_sort_key(p: Path) -> tuple[int, ...]:
    m = re.search(r"(\d+)\.png$", p.name)
    return (int(m.group(1)),) if m else (10**9,)


def _numbered_pages(page_files: list[Path]) -> list[int]:
    nums: list[int] = []
    for p in page_files:
        m = re.search(r"(\d+)\.png$", p.name)
        if m:
            nums.append(int(m.group(1)))
    return sorted(nums)


def _build_contact_sheet(page_files: list[Path], dest: Path) -> Path | None:
    """Tile page PNGs into one contact sheet PNG (Pillow)."""
    try:
        from PIL import Image
    except ImportError:
        return None
    tile_w = 360
    cols = 4
    thumbs: list[Image.Image] = []
    for pf in page_files:
        try:
            img = Image.open(pf)
            img.load()
        except Exception:
            continue
        ratio = tile_w / img.width
        thumbs.append(img.resize((tile_w, max(1, round(img.height * ratio)))))
    if not thumbs:
        return None
    rows = (len(thumbs) + cols - 1) // cols
    tile_h = max(t.height for t in thumbs)
    pad = 12
    sheet = Image.new("RGB", (cols * tile_w + (cols + 1) * pad, rows * tile_h + (rows + 1) * pad), (24, 24, 28))
    for i, t in enumerate(thumbs):
        r, c = divmod(i, cols)
        sheet.paste(t, (pad + c * (tile_w + pad), pad + r * (tile_h + pad)))
    sheet.save(dest, format="PNG")
    return dest


def _describe_or_skip(root: Path, relpath: str, artifact_id: str, role: str,
                      mime: str, skipped: list[str]) -> dict | None:
    """Describe one artifact; on a glob→read race record it and skip."""
    desc = _file_descriptor(root, relpath, artifact_id, role, mime)
    if desc is None:
        skipped.append(artifact_id)
    return desc


def _file_descriptor(root: Path, relpath: str, artifact_id: str, role: str, mime: str) -> dict | None:
    """§3.2 artifact descriptor for a file under a project/bundle root.

    Returns None when the file vanishes mid-build (glob→read race) instead
    of raising across the tool boundary (§2.5 no-exceptions convention);
    callers skip None and record which handle went missing.
    """
    p = root / relpath
    try:
        data = p.read_bytes()
    except OSError:
        return None
    return {
        "id": artifact_id,
        "path": relpath,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "mime": mime,
        "role": role,
    }


# --- WS-5: pdf-web (headless Chromium print of the html render) --------------

def _chromium_binary() -> str | None:
    if configured := os.environ.get("REPORTFORGE_CHROMIUM"):
        candidate = Path(configured).expanduser()
        return str(candidate) if candidate.is_file() else None
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        if found := shutil.which(name):
            return found
    return None


def _render_pdf_web(workdir: Path, html_path: Path, out_dir: Path, stem: str) -> dict:
    chromium = _chromium_binary()
    if not chromium:
        return {
            "ok": False,
            "error": "pdf-web needs headless Chromium: install it or set REPORTFORGE_CHROMIUM to the binary path",
        }
    pdf_out = out_dir / f"{stem}.pdf"
    # If a typst/latex pdf already claimed the conventional name, suffix the
    # web-print variant so both can coexist.
    if pdf_out.exists():
        pdf_out = out_dir / f"{stem}-web.pdf"
    cmd = [
        chromium,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--no-pdf-header-footer",
        # Let JS/plotly visuals settle before the print snapshot: without a
        # virtual-time budget, heavy pages print before charts finish drawing
        # and the PDF ships blank figure areas.
        "--virtual-time-budget=15000",
        f"--print-to-pdf={pdf_out}",
        html_path.as_uri(),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=QUARTO_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"chromium print-to-pdf timed out after {QUARTO_TIMEOUT_S}s"}
    if proc.returncode != 0 or not pdf_out.is_file():
        tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-15:])
        return {"ok": False, "error": "chromium print-to-pdf failed", "log_tail": tail}
    return {
        "ok": True,
        "pdf": str(pdf_out),
        "note": "pdf-web is a print snapshot of the html render; interactive JS/plotly content lives in the html artifact",
    }


def publish_report(project: str, dest_dir: str | None = None) -> dict:
    """Copy a rendered report project's deliverables into the run's thread outputs.

    Report-forge renders on the host (REPORTS_DIR/<project>/output/), which is
    outside the agent sandbox namespace: the sandbox cannot read those bytes,
    so `present_files` cannot serve them and the delivery gate has nothing to
    match. This bridge copies the rendered artifacts into the thread's outputs
    directory — inside the sandbox's /mnt/user-data mount — where the agent can
    then present the actual files.

    The destination is resolved from:
    1. explicit `dest_dir` (host path), else
    2. the DEERFLOW_THREAD_OUTPUTS_HOST env var injected by deer-flow into
       stdio MCP sessions (host-side thread outputs dir).

    Returns sandbox-virtual paths (/mnt/user-data/outputs/...) ready for
    present_files, plus host paths for operator inspection.
    """
    root = REPORTS_DIR / project.strip("/")
    if not root.is_dir():
        return {"ok": False, "error": f"project not found: {project}"}
    out_dir = _output_dir_of(root)
    if out_dir == root and (root / "output").is_dir():
        # No output-dir configured (or it resolves to the project root):
        # prefer the conventional output/ subdir when present.
        out_dir = root / "output"
    if not out_dir.is_dir():
        return {"ok": False, "error": f"project has no rendered output dir: {out_dir}"}

    dest = Path(dest_dir).expanduser() if dest_dir else None
    if dest is None:
        env_dest = os.environ.get("DEERFLOW_THREAD_OUTPUTS_HOST", "").strip()
        dest = Path(env_dest).expanduser() if env_dest else None
    if dest is None:
        return {
            "ok": False,
            "error": "no thread outputs dir available: pass dest_dir or run inside a deer-flow stdio session (DEERFLOW_THREAD_OUTPUTS_HOST)",
        }

    # Deliverables: rendered top-level files + any companion asset dirs
    # (Quarto's <stem>_files for self-contained html when embed-resources
    # is off, figures referenced relatively). Dotfiles are never
    # deliverables: WS-3 render logs (output/.render-log-<fmt>.txt) stay
    # readable via read_project_file but must not leak into thread outputs
    # and present_files.
    deliverables: list[Path] = [
        p for p in sorted(out_dir.iterdir()) if p.is_file() and not p.name.startswith(".")
    ]
    asset_dirs = [p for p in sorted(out_dir.iterdir()) if p.is_dir() and p.name.endswith("_files")]
    if not deliverables:
        return {"ok": False, "error": f"no rendered artifacts found in {out_dir}"}

    target_root = dest / project.strip("/")
    try:
        target_root.mkdir(parents=True, exist_ok=True)
        copied: list[str] = []
        for item in deliverables:
            shutil.copy2(item, target_root / item.name)
            copied.append(item.name)
        for adir in asset_dirs:
            shutil.copytree(adir, target_root / adir.name, dirs_exist_ok=True)
            copied.append(adir.name + "/")
    except OSError as exc:
        return {"ok": False, "error": f"publish copy failed: {exc}"}

    virtual = sorted(f"/mnt/user-data/outputs/{project.strip('/')}/{name}" for name in copied)
    return {
        "ok": True,
        "project": project.strip("/"),
        "host_dir": str(target_root),
        "published": copied,
        "present_paths": virtual,
        "next_step": "call present_files with present_paths",
    }


def _project_root_of(src: Path) -> Path | None:
    start = src if src.is_dir() else src.parent
    for parent in [start, *start.parents]:
        if (parent / "_quarto.yml").exists():
            return parent
    return None


def _translate_sandbox_path(path_str: str, project: str | None) -> str:
    """Translate agent-sandbox paths to host paths.

    The deer-flow agent sandbox exposes /mnt/user-data/{workspace,outputs,uploads},
    but reportforge runs on the host filesystem — those paths don't exist here.
    Redirect them into a report project's figures/ directory (resolved from the
    `project` slug when given, else the most recently modified project) so
    charts land where the qmd render will actually find them.
    """
    p = Path(path_str)
    sandbox_prefixes = ("/mnt/user-data",)
    if not any(str(p) == s or str(p).startswith(s + "/") for s in sandbox_prefixes):
        return path_str
    root: Path | None = None
    if project:
        candidate = REPORTS_DIR / project.strip("/")
        if candidate.is_dir():
            root = candidate
    if root is None:
        # Fall back to the most recently modified project directory.
        projects = [d for d in REPORTS_DIR.iterdir() if d.is_dir()] if REPORTS_DIR.is_dir() else []
        if projects:
            root = max(projects, key=lambda d: d.stat().st_mtime)
    if root is None:
        # No project to anchor to — leave the path alone and let the write fail
        # loudly with a clear error rather than guessing.
        return path_str
    figures = root / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    return str(figures / p.name)


def _declares_typst_format(workdir: Path) -> bool:
    """True when a project declares custom Typst template partials."""
    yml = workdir / "_quarto.yml"
    if not yml.exists():
        return False
    return "  typst:" in yml.read_text() and "template-partials" in yml.read_text()


def _quarto_tools_dir() -> Path | None:
    quarto = shutil.which("quarto")
    if not quarto:
        return None
    real = Path(quarto).resolve()
    candidate = real.parent / "tools" / "x86_64"
    if candidate.is_dir():
        return candidate
    for parent in real.parents:
        candidate = parent / "bin" / "tools" / "x86_64"
        if candidate.is_dir():
            return candidate
    return None


def _output_dir_of(workdir: Path) -> Path:
    yml = workdir / "_quarto.yml"
    if yml.exists():
        for line in yml.read_text().splitlines():
            stripped = line.split("#")[0].strip()
            if stripped.startswith("output-dir:"):
                value = stripped.split(":", 1)[1].strip().strip('"\'')
                if value:
                    return workdir / value
    return workdir


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


def _default_reference_docx() -> Path | None:
    pandoc = shutil.which("pandoc")
    cache = Path(__file__).resolve().parents[2] / "assets_cache"
    cache.mkdir(exist_ok=True)
    target = cache / "reference-doc.docx"
    if not target.exists() and pandoc:
        subprocess.run(
            [pandoc, "-o", str(target), "--print-default-data-file", "reference.docx"],
            capture_output=True,
            timeout=60,
        )
    return target if target.exists() else None
