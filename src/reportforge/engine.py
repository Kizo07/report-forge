"""Scaffold, render, and chart helpers for Quarto-based reports."""

from __future__ import annotations

import base64
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
from datetime import date
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


def _manifest_view(root: Path) -> dict | None:
    """Manifest projection for status responses; auto-imports legacy dirs."""
    try:
        if not (root / manifest_mod.MANIFEST_FILENAME).is_file():
            manifest_mod.import_dir(str(root))
        m = manifest_mod.load(str(root))
    except manifest_mod.ManifestError:
        return None
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
    }


def open_report(project: str) -> dict:
    """Open a report by slug: brief, profile, sections, revision, state."""
    root = REPORTS_DIR / project.strip("/")
    if not root.is_dir():
        return {"ok": False, "error": f"project not found: {project}"}
    view = _manifest_view(root)
    if view is None:
        return {"ok": False, "error": f"project has no readable manifest: {project}"}
    return {"ok": True, **view}


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
        state = {
            "last_render": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
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
    view = _manifest_view(root)
    artifacts: list[dict] = []
    if out_dir.is_dir():
        for name in ("index.pdf", "index.html", "index.docx"):
            p = out_dir / name
            if p.is_file():
                try:
                    artifacts.append(_file_descriptor(
                        out_dir, name, Path(name).stem,
                        "deliverable", _mime_for_name(name)))
                except OSError:
                    pass
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
        "artifacts": artifacts,
        "missing_work": missing_work,
    }


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


# --- WS-4: incremental composition -------------------------------------------

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
    """
    root = REPORTS_DIR / project.strip("/")
    if not root.is_dir():
        return {"ok": False, "error": f"project not found: {project}"}
    qmd_path = root / "index.qmd"
    if not qmd_path.is_file():
        return {"ok": False, "error": f"project has no index.qmd: {project}"}
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
    for line in markdown.splitlines():
        m = manifest_mod._HEADING_RE.match(line)
        if m and m.group(2).strip():
            return manifest_mod.slugify_section_id(m.group(2).strip())
    return None


# --- Milestone A Task 1.3: precise section operations (RF-02) ----------------

def _project_root_or_error(project: str) -> tuple[Path | None, dict | None]:
    root = REPORTS_DIR / project.strip("/")
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


def _stale_response(manifest) -> dict:
    changed = []
    for e in manifest_mod.events_since(manifest, 0)["events"]:
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
        "hint": f"re-read the section, re-apply your change on top of revision {manifest.revision}",
    }


def _check_expected(manifest, expected_revision) -> dict | None:
    if expected_revision is None:
        return {"ok": False, "error": "expected_revision is required (pass the manifest revision you read)"}
    if expected_revision != manifest.revision:
        return _stale_response(manifest)
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


def replace_section(project: str, section_id: str, markdown: str,
                    expected_revision: int | None = None,
                    actor: str = "tool:replace_section") -> dict:
    """Replace a section's heading + body wholesale; other bytes preserved."""
    root, err = _project_root_or_error(project)
    if err:
        return err
    assert root is not None
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
    new_block = markdown if markdown.endswith("\n") else markdown + "\n"
    new_text = (raw[:span["start_byte"]] + new_block.encode("utf-8")
                + raw[span["end_byte"]:]).decode("utf-8")
    return _commit_qmd_change(root, manifest, new_text,
                              f"replace section {section_id}",
                              actor, "replace", section_id)


def move_section(project: str, section_id: str, before_section_id: str | None = None,
                 to_end: bool = False, expected_revision: int | None = None,
                 actor: str = "tool:move_section") -> dict:
    """Move a section block before another section or to the document end."""
    root, err = _project_root_or_error(project)
    if err:
        return err
    assert root is not None
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
    return _commit_qmd_change(root, manifest, new_raw.decode("utf-8"),
                              f"move section {section_id}",
                              actor, "move", section_id)


def delete_section(project: str, section_id: str,
                   expected_revision: int | None = None,
                   actor: str = "tool:delete_section") -> dict:
    """Remove a section block."""
    root, err = _project_root_or_error(project)
    if err:
        return err
    assert root is not None
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


# --- Milestone A Task 1.5: preview artifacts (RF-05) --------------------------


def _load_manifest_if_present(root: Path) -> tuple[dict | None, str | None]:
    """Read report.json for a project; loud failure when absent/unreadable.

    Dict-level helper kept deliberately thin until Task 1.1's manifest module
    lands: engine preview/export code should not duplicate the manifest state
    machine, only consume it.
    """
    mpath = root / "report.json"
    if not mpath.is_file():
        return None, f"project has no report.json manifest (scaffold/import first): {mpath.name}"
    try:
        m = json.loads(mpath.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"manifest unreadable: {exc}"
    if not isinstance(m.get("revision"), int):
        return None, "manifest has no integer 'revision' field"
    return m, None


def render_preview(project: str, revision: int | None = None) -> dict:
    """Render preview artifacts (contact sheet, pages, exhibits) for a report.

    Contract §5: previews bind to (report_id, revision), are generated only
    from that revision's rendered PDF (no auto-render), live under
    <project>/output/previews/r<rev>/, and are returned as §3.2-shaped
    relative-path artifact descriptors — never host absolute paths.
    Read-only: the manifest revision is never bumped.
    """
    root = REPORTS_DIR / project.strip("/")
    if not root.is_dir():
        return {"ok": False, "error": f"project not found: {project}"}
    manifest, err = _load_manifest_if_present(root)
    if err:
        return {"ok": False, "error": err}
    assert manifest is not None
    current = manifest["revision"]
    if revision is not None and revision != current:
        return {
            "ok": False,
            "error": f"stale revision: requested {revision}, manifest is at revision {current}",
            "current_revision": current,
        }
    rev = current

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

    artifacts: list[dict] = [
        _file_descriptor(root, f"output/previews/r{rev}/contact-sheet.png", "contact-sheet", "preview", "image/png")
    ]
    for p in _numbered_pages(page_files):
        artifacts.append(
            _file_descriptor(root, f"output/previews/r{rev}/pages/page-{p}.png", f"page-{p}", "preview", "image/png")
        )

    charts_dir = root / "charts"
    if charts_dir.is_dir():
        for chart in sorted(charts_dir.glob("*.png")):
            artifacts.append(
                _file_descriptor(root, f"charts/{chart.name}", f"exhibit-{chart.stem}", "preview", "image/png")
            )

    return {
        "ok": True,
        "report_id": manifest.get("report_id", project.strip("/")),
        "revision": rev,
        "page_count": page_count,
        "artifacts": artifacts,
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


def _file_descriptor(root: Path, relpath: str, artifact_id: str, role: str, mime: str) -> dict:
    """§3.2 artifact descriptor for a file under a project/bundle root."""
    p = root / relpath
    data = p.read_bytes()
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
