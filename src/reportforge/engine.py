"""Scaffold, render, and chart helpers for Quarto-based reports."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from jinja2 import Template

from reportforge import templates

REPORTS_DIR = Path.home() / "Documents" / "report-forge" / "reports"
QUARTO_TIMEOUT_S = 900


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
) -> dict:
    specs = {t["name"]: t for t in list_templates()}
    if template not in specs:
        return {"ok": False, "error": f"unknown template {template!r}; available: {sorted(specs)}"}
    spec = specs[template]
    formats = formats or spec["formats"]
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in slug.strip().lower())
    root = REPORTS_DIR / slug
    if root.exists():
        return {"ok": False, "error": f"report {slug!r} already exists at {root}"}
    assets = root / "assets"
    assets.mkdir(parents=True)

    # KPI stat strip (modern template). Sensible placeholders so the strip
    # renders in a fresh scaffold; replace with real figures.
    kpis = kpis or [
        {"value": "+62 bps", "label": "Realized alpha"},
        {"value": "0.94", "label": "Signal IC"},
        {"value": "18.3%", "label": "Dispersion"},
        {"value": "-0.21", "label": "Crowding z"},
    ]
    kpis_yaml = ""
    if kpis:
        import json as _json
        kpis_yaml = "kpis:\n" + "\n".join(
            f"  - value: {_json.dumps(str(k.get('value', '')))}\n    label: {_json.dumps(str(k.get('label', '')))}"
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
    }
    def _tpl(source: str) -> Template:
        return Template(
            source,
            variable_start_string="<%",
            variable_end_string="%>",
            block_start_string="<%%",
            block_end_string="%%>",
            comment_start_string="<##",
            comment_end_string="##>",
        )
    if template == "modern":
        # Modern briefs use a custom typst template for the PDF path —
        # `format: pdf` rejects template-partials, so the yml declares
        # `format: typst` and render_report() maps requested 'pdf' to it.
        (root / "_quarto.yml").write_text(_tpl(templates.MODERN_YML).render(ctx))
        (assets / "typst-template.typ").write_text(templates.MODERN_TYPT_TEMPLATE)
        (assets / "typst-show.typ").write_text(templates.MODERN_TYPT_SHOW)
    else:
        (root / "_quarto.yml").write_text(_tpl(templates.QUARTO_YML).render(ctx))
    (root / "_brand.yml").write_text(templates.BRAND_YML)
    styles = templates.STYLES_SCSS
    body_tpl = {
        "standard": templates.INDEX_QMD,
        "memo": templates.MEMO_QMD,
        "whitepaper": templates.WHITEPAPER_QMD,
        "modern": templates.MODERN_QMD,
    }[template]
    if template == "whitepaper":
        styles += templates.WHITEPAPER_STYLES_EXTRA
    elif template == "modern":
        styles += templates.MODERN_STYLES_EXTRA
    (root / "styles.scss").write_text(styles)
    body = _tpl(body_tpl).render(ctx)
    kept_formats = [f for f in ("html", "pdf", "docx") if f in formats]
    yml = (root / "_quarto.yml").read_text()
    # The modern template declares `format: typst` in place of `format: pdf`
    # (format: pdf rejects template-partials). Treat pdf↔typst as one slot
    # for keep/drop decisions.
    yml_fmt_key = "typst" if template == "modern" else "pdf"
    for fmt in ("html", "pdf", "docx"):
        if fmt not in kept_formats:
            yml = _drop_yaml_block(yml, yml_fmt_key if fmt == "pdf" else fmt)
    (root / "_quarto.yml").write_text(yml)
    (root / "index.qmd").write_text(body)
    ref = _default_reference_docx()
    if ref is not None and "docx" in kept_formats:
        shutil.copy(ref, root / "assets" / "reference-doc.docx")
    kernel = _ensure_reportforge_kernel()
    return {"ok": True, "path": str(root), "source": str(root / "index.qmd"), "formats": kept_formats, "jupyter_kernel": kernel}


def _venv_python() -> Path | None:
    candidate = Path(__file__).resolve().parents[2] / ".venv" / "bin" / "python"
    return candidate if candidate.exists() else None


def _ensure_reportforge_kernel() -> str:
    venv_python = _venv_python()
    if not venv_python:
        return "python3"
    subprocess.run(
        [str(venv_python), "-m", "ipykernel", "install", "--user", "--name", "reportforge", "--display-name", "reportforge"],
        capture_output=True,
        timeout=120,
    )
    return "reportforge"


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
    wanted = list(formats) if formats else None
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

    tails: list[str] = []
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
        tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-15:])
        tails.append(f"--- {fmt} ---\n{tail}")
        if proc.returncode != 0:
            return {"ok": False, "error": f"quarto render failed for format '{fmt}'", "log_tail": tail}
    out_dir = _output_dir_of(workdir)
    outputs = sorted(str(p) for p in out_dir.glob("*") if p.suffix in {".html", ".pdf", ".docx", ".pptx", ".revealjs"}) if out_dir.exists() else []
    return {"ok": True, "outputs": outputs, "log_tail": "\n".join(tails)[-600:]}


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


def _project_root_of(src: Path) -> Path | None:
    for parent in [src.parent, *src.parents]:
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
    """True when the project yml declares a custom `format: typst` block
    (modern template). Such projects must render pdf via `--to typst`."""
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
    for line in lines:
        if line.startswith(f"  {top_key}:"):
            skipping = True
            continue
        if skipping:
            if line[:1] not in (" ", "\t") and line.strip():
                skipping = False
                out.append(line)
            continue
        out.append(line)
    return "".join(out)


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
