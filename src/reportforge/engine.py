"""Scaffold, render, and chart helpers for Quarto-based reports."""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
from html import escape as html_escape
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from jinja2 import Template

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


def list_templates() -> list[dict]:
    return [
        {"name": "standard", "description": "Multi-section business report: executive summary, analysis, recommendations. TOC + numbered sections; html/pdf/docx.", "toc": True, "number_sections": True, "formats": ["html", "pdf", "docx"]},
        {"name": "memo", "description": "Single-purpose memo: purpose, key points, details. No TOC; html/pdf.", "toc": False, "number_sections": False, "formats": ["html", "pdf"]},
        {"name": "whitepaper", "description": "Hedge-fund-style institutional white paper: key takeaways, investment thesis, framework, exhibit-driven analysis, portfolio implications, risk factors. Figures/tables labeled 'Exhibit N' with unified numbering; title page, TOC + numbered sections; html/pdf/docx.", "toc": True, "number_sections": True, "exhibit_labels": True, "papersize": "us-letter", "formats": ["html", "pdf", "docx"]},
        {"name": "modern", "description": "Modern branded research brief: full-bleed dark masthead with firm + subtitle, KPI stat strip, accent-tick headings, running header/footer with confidentiality mark, exhibit-driven short sections (executive summary → signal → actions → risks). Custom typst PDF template; figures/tables labeled 'Exhibit N'; html/pdf/docx.", "toc": False, "number_sections": False, "exhibit_labels": True, "papersize": "us-letter", "formats": ["html", "pdf", "docx"]},
        {"name": "studio", "description": "Premium content-neutral editorial report: hero or compact title, optional organization/eyebrow/metrics/footer, configurable accent, flexible Markdown sections, refined figures and tables. Custom Typst PDF and responsive HTML; html/pdf/docx.", "toc": False, "number_sections": False, "exhibit_labels": True, "papersize": "us-letter", "formats": ["html", "pdf", "docx"], "content_neutral": True, "title_layouts": ["hero", "compact"], "max_metrics": 6},
        {"name": "bespoke", "description": "Minimal project, no template opinions: you supply the full .qmd frontmatter and body (via write_report_body / append_section). Use for custom layouts, html-first designs, or the pdf-web (headless-Chromium print) path. html/pdf/docx/pdf-web.", "toc": False, "number_sections": False, "formats": ["html", "pdf", "docx", "pdf-web"], "content_neutral": True},
    ]


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
    frontmatter_yaml: str | None = None,
    body: str | None = None,
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
    if template == "studio":
        if title_layout not in {"hero", "compact"}:
            return {"ok": False, "error": "title layout must be 'hero' or 'compact'"}
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
            return {"ok": False, "error": "accent must be a six-digit hex color such as #4f46e5"}

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
        "organization": organization or (firm if template == "studio" else ""),
        "eyebrow": eyebrow,
        "title_layout": title_layout,
        "accent": accent.lower(),
        "metrics": kpis if template == "studio" else [],
        "metrics_count": len(kpis) if template == "studio" else 0,
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
    ):
        ctx[f"{field}_yaml"] = _yaml_scalar(ctx[field])
    ctx["metrics_yaml"] = _metric_yaml("metrics", ctx["metrics"])
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
    if template == "modern":
        # Modern briefs use a custom typst template for the PDF path —
        # `format: pdf` rejects template-partials, so the yml declares
        # `format: typst` and render_report() maps requested 'pdf' to it.
        (root / "_quarto.yml").write_text(_tpl(templates.MODERN_YML).render(ctx))
        (assets / "typst-template.typ").write_text(templates.MODERN_TYPT_TEMPLATE)
        (assets / "typst-show.typ").write_text(templates.MODERN_TYPT_SHOW)
    elif template == "studio":
        (root / "_quarto.yml").write_text(_tpl(templates.STUDIO_YML).render(ctx))
        (assets / "typst-template.typ").write_text(templates.STUDIO_TYPT_TEMPLATE)
        (assets / "typst-show.typ").write_text(templates.STUDIO_TYPT_SHOW)
        (assets / "studio-header.html").write_text(
            _tpl(templates.STUDIO_HTML_HEADER).render(ctx)
        )
    else:
        (root / "_quarto.yml").write_text(_tpl(templates.QUARTO_YML).render(ctx))
    (root / "_brand.yml").write_text(templates.BRAND_YML)
    styles = templates.STYLES_SCSS
    body_tpl = {
        "standard": templates.INDEX_QMD,
        "memo": templates.MEMO_QMD,
        "whitepaper": templates.WHITEPAPER_QMD,
        "modern": templates.MODERN_QMD,
        "studio": templates.STUDIO_QMD,
    }[template]
    if template == "whitepaper":
        styles += templates.WHITEPAPER_STYLES_EXTRA
    elif template == "modern":
        styles += templates.MODERN_STYLES_EXTRA
    elif template == "studio":
        styles += templates.STUDIO_STYLES_EXTRA
    (root / "styles.scss").write_text(_tpl(styles).render(ctx))
    body = _tpl(body_tpl).render(ctx)
    kept_formats = [f for f in ("html", "pdf", "docx") if f in formats]
    yml = (root / "_quarto.yml").read_text()
    # The modern template declares `format: typst` in place of `format: pdf`
    # (format: pdf rejects template-partials). Treat pdf↔typst as one slot
    # for keep/drop decisions.
    yml_fmt_key = "typst" if template in {"modern", "studio"} else "pdf"
    for fmt in ("html", "pdf", "docx"):
        if fmt not in kept_formats:
            yml = _drop_yaml_block(yml, yml_fmt_key if fmt == "pdf" else fmt)
    (root / "_quarto.yml").write_text(yml)
    (root / "index.qmd").write_text(body)
    ref = _default_reference_docx()
    if ref is not None and "docx" in kept_formats:
        shutil.copy(ref, root / "assets" / "reference-doc.docx")
    return {"ok": True, "path": str(root), "source": str(root / "index.qmd"), "formats": kept_formats, "jupyter_kernel": kernel}


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


def save_chart(fig_json: str, out_basename: str, width: int = 1400, height: int = 700, scale: int = 2, project: str | None = None) -> dict:
    try:
        import plotly.io as pio

        fig = pio.from_json(fig_json)
    except Exception as exc:
        return {"ok": False, "error": f"invalid plotly figure JSON: {exc}"}
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
    return {"ok": True, "png": str(png), "html": str(html_path), "embed_snippet": f"![caption.]({png.name}){{width=90%}}"}


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
    return {
        "ok": True,
        "project": project.strip("/"),
        "path": str(root),
        "files": files,
        "configured_formats": formats,
        "output_dir": str(out_dir),
        "render_logs": render_logs,
        "last_render": last_render,
    }


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

def append_section(project: str, markdown: str, before: str | None = None) -> dict:
    """Append a markdown section to index.qmd, or insert before a heading.

    Additive edits without rewriting the whole body: the YAML frontmatter is
    preserved untouched. With `before` given, the section is inserted above
    the first heading whose text matches (case-insensitive substring).
    """
    root = REPORTS_DIR / project.strip("/")
    if not root.is_dir():
        return {"ok": False, "error": f"project not found: {project}"}
    qmd_path = root / "index.qmd"
    if not qmd_path.is_file():
        return {"ok": False, "error": f"project has no index.qmd: {project}"}
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
    if before:
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
    qmd_path.write_text(head + body)
    return {
        "ok": True,
        "source": str(qmd_path),
        "action": action,
        "bytes": qmd_path.stat().st_size,
        "next_step": "render_report to verify the composition",
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
    # is off, figures referenced relatively).
    deliverables: list[Path] = [p for p in sorted(out_dir.iterdir()) if p.is_file()]
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
