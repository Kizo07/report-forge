"""Core engine: toolchain wrappers, scaffold, render, gates, release,
execution, status. Split out per Phase 3 of the robustness refactor
plan; the package __init__ re-exports the full surface.

Cross-module and test-stubbed references go through `_E` (the
package namespace) with deferred attribute access so monkeypatching
`reportforge.engine.<name>` keeps working.
"""

from __future__ import annotations

from reportforge import engine as _E

import fcntl
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
import yaml
from jinja2 import Template
from reportforge import manifest as manifest_mod
from reportforge import __version__ as _REPORTFORGE_VERSION
from reportforge.renderer import errors as _rerrors
from reportforge.renderer import interpreters as _rinterpreters
from reportforge.renderer import lint as _rlint
from reportforge.renderer import poppler as _rpoppler
from reportforge.renderer import probe as _rprobe
from reportforge.renderer import quarto as _rquarto
from reportforge.renderer import toolchain as _rtoolchain
from reportforge.renderer.quarto import CHROMIUM_PRINT_TIMEOUT_S
from reportforge.renderer.quarto import QUARTO_TIMEOUT_S



REPORTS_DIR = Path(
    os.environ.get(
        "REPORTFORGE_REPORTS_DIR",
        str(Path.home() / "Documents" / "report-forge" / "reports"),
    )
).expanduser()


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


_PORTFOLIO_TEMPLATES = {"portfolio-light", "portfolio-dark"}


_LEDGER_TEMPLATES = {"ledger-light", "ledger-dark"}


_EDITORIAL_TEMPLATES = {"studio"} | _PORTFOLIO_TEMPLATES | _LEDGER_TEMPLATES


_TEMPLATE_DEFAULT_ACCENTS = {"studio": "#4f46e5", "modern": "#2e5bff",
                             "portfolio-light": "#8f621f", "portfolio-dark": "#d9a54e",
                             "ledger-light": "#8f621f", "ledger-dark": "#e3ac55"}


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
    """Light-page project? Prefers the scaffolded `reportforge-template`
    frontmatter (exact match, immune to titles like "Spotlight on ..."),
    falling back to the legacy 'light' substring heuristic when the key is
    absent (bespoke / hand-written projects)."""
    qmd = workdir / "index.qmd"
    if not qmd.is_file():
        return False
    text = qmd.read_text()
    if not text.startswith("---"):
        return False
    fence = text.find("\n---", 3)
    head = text[:fence] if fence != -1 else text[:2000]
    m = re.search(r'^reportforge-template:\s*"?([a-z0-9-]+)"?\s*$', head, re.MULTILINE)
    if m:
        name = m.group(1)
        if name in ("portfolio-dark", "ledger-dark"):
            return False
        if name in ("portfolio-light", "ledger-light"):
            return True
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
    if not _E._frontmatter_flag(workdir, "engine_charts_only"):
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


_PROFILE_BRANDS = ("quantflow",)


_PROFILE_THEMES = ("light", "dark")


_PROFILE_LAYOUTS = ("magazine",)


_PROFILE_OUTPUTS = ("editorial", "web")


_PROFILE_POLICIES = ("draft", "release")


_PROFILE_OVERRIDABLE = ("output_profile", "policy")


_PROFILE_AXES = {
    "report_type": None,  # template name; never overridden, validated non-empty
    "brand": _PROFILE_BRANDS,
    "theme": _PROFILE_THEMES,
    "layout": _PROFILE_LAYOUTS,
    "output_profile": _PROFILE_OUTPUTS,
    "policy": _PROFILE_POLICIES,
}


def _quarto_version() -> str | None:
    """Best-effort `quarto --version`; None when quarto is absent/broken."""
    return _rtoolchain.quarto_version()


def _tool_version(cmd: list[str]) -> str | None:
    """First output line of a version probe; None when absent."""
    return _rtoolchain.tool_version(cmd)


def _toolchain_stamp() -> dict:
    """Toolchain binding for the release seal + state file (C-2, RF-09).

    Manifest-blind by design (§1.3): this lands in .reportforge-state.json
    and output/release.json only — never the manifest.
    """
    chromium = _E._chromium_binary()
    return {
        "quarto": _E._quarto_version(),
        "python": sys.version.split()[0],
        "reportforge": _REPORTFORGE_VERSION,
        "pandoc": _tool_version(["pandoc", "--version"]) if _rtoolchain.which("pandoc") else None,
        # typst: version string when standalone-installed, else the
        # "quarto-bundled" sentinel — quarto ships its own typst and
        # exposes no version probe for it (N3, milestone A review).
        "typst": _tool_version(["typst", "--version"]) if _rtoolchain.which("typst") else "quarto-bundled",
        "poppler": _tool_version(["pdfinfo", "-v"]) if _rtoolchain.which("pdfinfo") else None,
        "chromium": _tool_version([chromium, "--version"]) if chromium else None,
    }


def _venv_python() -> Path | None:
    """REPORTFORGE_PYTHON > active venv > repo .venv; None when absent."""
    return _rtoolchain.venv_python()


def _public_format_name(fmt: str) -> str:
    # R1-F12: the release map keys on the PUBLIC name — modern projects
    # render pdf via the internal `typst` quarto format, and that alias
    # must never leak into the release record.
    return "pdf" if fmt == "typst" else fmt


def _ensure_reportforge_kernel() -> str:
    """Install the reportforge jupyter kernel; 'python3' fallback (reported
    via scaffold's jupyter_kernel field)."""
    return _rinterpreters.ensure_kernel(_E._venv_python())


def _render_resolve_source(source: str) -> tuple[Path | None, dict | None]:
    """Stage 1 — resolve `source` to a qmd path (explicit, cwd-relative, or
    a project slug under REPORTS_DIR)."""
    src = Path(source).expanduser()
    if not src.is_absolute():
        src = Path.cwd() / src
    if not src.exists():
        candidate = _E.REPORTS_DIR / source.strip("/") / "index.qmd"
        if candidate.exists():
            src = candidate
        else:
            return None, {"ok": False, "error": f"source not found: {source}"}
    src = src.resolve()
    if src.is_dir():
        candidate = src / "index.qmd"
        if not candidate.is_file():
            return None, {"ok": False, "error": f"project has no index.qmd: {src}"}
        src = candidate
    if not src.is_file():
        return None, {"ok": False, "error": f"source is not a file: {src}"}
    return src, None


def _render_preflight(workdir: Path) -> dict | None:
    """Stage 2 — refuse to render in a broken environment."""
    # Binary presence, not a version probe: the stamp (post-render) is the
    # one that needs a working quarto; refusing early only needs the binary.
    if _rtoolchain.which("quarto") is None:
        return {
            "ok": False,
            "error": ("quarto not found on PATH — install Quarto (https://quarto.org) "
                      "and re-run; refusing to attempt a render without it"),
        }
    violation = _engine_charts_violation(workdir)
    if violation is not None:
        return {"ok": False, "error": violation}
    return None


def _render_build_env() -> dict:
    """Stage 3 — child-process environment (OTEL pinning, quarto tools,
    venv python so `execute.jupyter: reportforge` resolves)."""
    env = dict(__import__("os").environ)
    if env.get("OTEL_SDK_DISABLED") not in (None, "true", "false"):
        env["OTEL_SDK_DISABLED"] = "true" if env["OTEL_SDK_DISABLED"].lower() in ("1", "yes", "on") else "false"
    tools_dir = _quarto_tools_dir()
    if tools_dir:
        env["PATH"] = str(tools_dir) + ":" + env.get("PATH", "")
    venv_python = _E._venv_python()
    if venv_python:
        # Quarto discovers kernelspecs via the python it finds. Without an
        # activated venv it picks system python3, misses nbformat, and falls
        # back to a bare 'python3' kernel. Pin Quarto to the reportforge venv
        # so `execute.jupyter: reportforge` resolves against the right kernel.
        env["QUARTO_PYTHON"] = str(venv_python)
        env["PATH"] = str(venv_python.parent) + ":" + env.get("PATH", "")
    return env


def _render_resolve_formats(formats: list[str] | None, workdir: Path):
    """Stage 4 — decide the format list (explicit request, pdf-web
    expansion, typst-declaring projects) -> (wanted, pdf_web, error)."""
    # Render one format per quarto invocation: this Quarto version does not
    # accept comma-joined --to lists, and per-format runs keep failures
    # isolated to the failing format.
    if formats is not None and not formats:
        return None, False, {"ok": False, "error": "at least one format is required"}
    requested = list(formats) if formats is not None else None
    if requested is not None:
        unsupported = sorted(set(requested) - set(PUBLIC_FORMATS))
        if unsupported:
            return None, False, {
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
        return None, False, {"ok": False, "error": "project config contains no supported formats"}
    return wanted, pdf_web_requested, None


def _render_seal_snapshot(workdir: Path):
    """Stage 5 — seal the snapshot identity BEFORE invoking quarto (C-4).
    Renders of a bare qmd with no manifest skip the release record."""
    release_manifest, release_manifest_err = _load_or_import(workdir)
    if release_manifest_err is None and release_manifest is not None:
        try:
            return _E._release_inputs(workdir, release_manifest, _E._toolchain_stamp())
        except OSError:
            return None
    return None


def _render_format_loop(src: Path, wanted: list[str], env: dict, workdir: Path,
                        release_seal, out_dir: Path, tails: list[str],
                        rendered_outputs: list[str]):
    """Stage 6 — render each format, persist logs, seal artifacts.
    -> (sealed_artifacts, error|None)."""
    sealed_artifacts: dict = {}
    for fmt in wanted:
        if release_seal is not None:
            # The qmd must not move under a running render — a mid-loop
            # edit would seal formats from two different inputs.
            try:
                current_qmd = hashlib.sha256(src.read_bytes()).hexdigest()
            except OSError as exc:
                return None, {"ok": False, "error": f"index.qmd unreadable mid-render: {exc}"}
            if current_qmd != release_seal["qmd_sha256"]:
                return None, {
                    "ok": False,
                    "error": (f"index.qmd changed mid-render (snapshot {release_seal['release_id']} "
                              "no longer valid): re-render all formats together so the release stays one snapshot"),
                    "outputs": sorted(rendered_outputs),
                }
        cmd = ["quarto", "render", str(src), "--to", fmt]
        try:
            proc = _rquarto.run_quarto(
                cmd,
                cwd=workdir,
                timeout=QUARTO_TIMEOUT_S,
                env=env,
            )
        except _rerrors.ToolTimeoutError as exc:
            return None, {"ok": False, "error": f"quarto render ({fmt}) timed out after {exc.timeout_s}s"}
        except _rerrors.RendererError as exc:
            # Seam contract: every renderer failure mode crosses as a
            # RendererError subclass and is translated here — the one place
            # the public {"ok": False, ...} shape is produced for quarto.
            return None, {"ok": False, "error": str(exc)}
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
            return None, {
                "ok": False,
                "error": f"quarto render failed for format '{fmt}'",
                "log_tail": tail,
                "render_log": str(out_dir / f".render-log-{fmt}.txt"),
            }
        extension = "pdf" if fmt == "typst" else fmt
        expected = out_dir / f"{src.stem}.{extension}"
        if not expected.is_file():
            return None, {
                "ok": False,
                "error": f"quarto reported success but output is missing for format '{fmt}'",
                "log_tail": tail,
            }
        rendered_outputs.append(str(expected))
        if release_seal is not None:
            try:
                artifact_bytes = expected.read_bytes()
            except OSError:
                return None, {"ok": False,
                              "error": f"rendered output vanished before sealing: {expected}"}
            sealed_artifacts[_public_format_name(fmt)] = {
                "path": str(expected),
                "sha256": hashlib.sha256(artifact_bytes).hexdigest(),
                "bytes": len(artifact_bytes),
            }
    return sealed_artifacts, None


def _render_pdf_web_stage(workdir: Path, src: Path, out_dir: Path,
                          pdf_web_requested: bool, rendered_outputs: list[str]):
    """Stage 7 — optional headless-Chromium print of the html render.
    -> (pdf_web_note, error|None)."""
    if not pdf_web_requested:
        return None, None
    html_path = out_dir / f"{src.stem}.html"
    if not html_path.is_file():
        return None, {"ok": False, "error": "pdf-web requires an html render, but none was produced"}
    result_pw = _render_pdf_web(workdir, html_path, out_dir, src.stem)
    if not result_pw["ok"]:
        return None, {
            "ok": False,
            "error": result_pw["error"],
            "log_tail": result_pw.get("log_tail", ""),
            "outputs": sorted(rendered_outputs),
        }
    rendered_outputs.append(result_pw["pdf"])
    return result_pw["note"], None


def _render_release_stage(workdir: Path, release_seal, out_dir: Path,
                          sealed_artifacts: dict, rendered_outputs: list[str]) -> dict | None:
    """Stage 8 — merge this run's formats into output/release.json under
    the project lock (C-4, R1-F7). A sealed record from a DIFFERENT
    snapshot that still covers formats outside this run is a stale mix —
    refuse loudly, never merge across inputs. Re-rendering the same set
    re-seals."""
    if release_seal is None:
        return None
    with _project_lock(workdir):
        existing = _E._read_release_record(out_dir)
        if (existing is not None
                and existing.get("release_id") != release_seal["release_id"]):
            foreign = sorted(set(existing.get("artifacts", {}))
                             - set(sealed_artifacts))
            if foreign:
                return {
                    "ok": False,
                    "error": (f"stale snapshot mix: release {existing.get('release_id')} already covers "
                              f"{foreign}, but the inputs changed (now {release_seal['release_id']}): "
                              "re-render all formats together so the release stays one snapshot"),
                    "outputs": sorted(rendered_outputs),
                }
        merged = {}
        if (existing is not None
                and existing.get("release_id") == release_seal["release_id"]):
            merged = dict(existing.get("artifacts", {}))
        merged.update(sealed_artifacts)
        try:
            _E._write_release_record(out_dir, {**release_seal, "artifacts": merged})
        except OSError as exc:
            return {"ok": False,
                    "error": f"could not seal release record: {exc}",
                    "outputs": sorted(rendered_outputs)}
    return None


def _render_state_stage(workdir: Path, wanted: list[str], pdf_web_requested: bool,
                        src: Path, rendered_outputs: list[str]):
    """Stage 9 — machine-readable project state (WS-3) with the toolchain
    stamp. -> (state, error|None); state is the built dict even when
    persisting it failed — {} only when the stamp itself was unobtainable."""
    state: dict = {}
    try:
        try:
            rendered_manifest = manifest_mod.load(str(workdir))
            rendered_rev = rendered_manifest.revision
            rendered_reg = rendered_manifest.registry_version
        except manifest_mod.ManifestError:
            rendered_rev = None
            rendered_reg = None
        state = {
            "last_render": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            # Revision binding (RF-05): previews/export can verify the PDF
            # was rendered from the current manifest revision, not an older
            # one. A content edit bumps the revision and invalidates the PDF.
            "manifest_revision": rendered_rev,
            # Registry binding (R2, Milestone B): registry writes change
            # render inputs (sources.bib/_quarto.yml) without bumping the
            # revision — stamp it too so previews fail loudly on stale bytes.
            "registry_version": rendered_reg,
            "formats": wanted + (["pdf-web"] if pdf_web_requested else []),
            "outputs": sorted(rendered_outputs),
            "source": str(src),
            # Toolchain binding (C-2, RF-09): the exact renderer that
            # produced these bytes. Lives in state (artifacts), never the
            # manifest (§1.3). A stamp failure fails loudly — silently
            # omitting it would fake reproducibility.
            "toolchain": _E._toolchain_stamp(),
        }
        if state["toolchain"]["quarto"] is None:
            return {}, {
                "ok": False,
                "error": "quarto version undetectable after a successful render: "
                         "re-render once quarto is on PATH",
                "outputs": sorted(rendered_outputs),
            }
        (workdir / ".reportforge-state.json").write_text(json.dumps(state, indent=2))
    except OSError:
        pass
    return state, None


def render_report(source: str, formats: list[str] | None = None, project: str | None = None) -> dict:
    """Scaffold -> gate -> seal -> render -> seal-record -> state, composed
    from the named stages above. Lint lives in check_readiness; previews in
    render_preview."""
    src, err = _render_resolve_source(source)
    if err:
        return err
    workdir = _project_root_of(src) or src.parent
    err = _render_preflight(workdir)
    if err:
        return err
    env = _render_build_env()
    wanted, pdf_web_requested, err = _render_resolve_formats(formats, workdir)
    if err:
        return err
    release_seal = _render_seal_snapshot(workdir)
    out_dir = _output_dir_of(workdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tails: list[str] = []
    rendered_outputs: list[str] = []
    sealed_artifacts, err = _render_format_loop(src, wanted, env, workdir, release_seal,
                                                out_dir, tails, rendered_outputs)
    if err:
        return err
    pdf_web_note, err = _render_pdf_web_stage(workdir, src, out_dir, pdf_web_requested, rendered_outputs)
    if err:
        return err
    err = _render_release_stage(workdir, release_seal, out_dir, sealed_artifacts, rendered_outputs)
    if err:
        return err
    state, err = _render_state_stage(workdir, wanted, pdf_web_requested, src, rendered_outputs)
    if err:
        return err

    result = {
        "ok": True,
        "outputs": sorted(rendered_outputs),
        "log_tail": "\n".join(tails)[-RENDER_LOG_TAIL_CHARS:],
    }
    # Phase 1 probe: WARN-ONLY until per-family version ranges are evidenced
    # by a snapshot cycle (plan §5 — no new render failure mode on day one).
    warnings = _rprobe.render_probe(state["toolchain"]) if state else []
    if warnings:
        result["toolchain_warnings"] = warnings
    if pdf_web_note:
        result["pdf_web_note"] = pdf_web_note
    return result




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
        candidate = _E.REPORTS_DIR / project.strip("/")
        if candidate.is_dir():
            root = candidate
    if root is None:
        try:
            rel = out.resolve().relative_to(_E.REPORTS_DIR.resolve())
            if len(rel.parts) >= 1 and (_E.REPORTS_DIR / rel.parts[0]).is_dir():
                root = _E.REPORTS_DIR / rel.parts[0]
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
        "paper_bg": "#060a12", "plot_bg": "#0b1220", "font": "#e8eef4",
        "grid": "#16202e", "primary": "#e3ac55", "secondary": "#08bfff",
        "positive": "#34d399", "negative": "#f87171", "muted": "#93a3b8",
        "ramp": ["#6b5a26", "#a3853a", "#e3ac55", "#08bfff", "#7fd8ff"],
    },
    "ledger-light": {
        "paper_bg": "#eef3f6", "plot_bg": "#eef3f6", "font": "#22303c",
        "grid": "#d5dde4", "primary": "#8f621f", "secondary": "#009ed9",
        "positive": "#1f8a4c", "negative": "#cf4444", "muted": "#63798a",
        "ramp": ["#b09a5e", "#8f621f", "#6d4c17", "#009ed9", "#075e7d"],
    },
}


_PORTFOLIO_TO_QUANTFLOW_TEMPLATE = {
    "portfolio-dark": "quantflow-dark",
    "portfolio-light": "quantflow-light",
    "ledger-dark": "ledger-dark",
    "ledger-light": "ledger-light",
}


BRAND_TOKENS = {
    name: {"accent": pal["primary"], **pal}
    for name, pal in QUANTFLOW_PLOTLY_THEMES.items()
}


_STATUS_FORMAT_IDS = {"index.pdf": "pdf", "index.html": "html",
                       "index.docx": "docx"}


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


def _load_or_import(root: Path):
    try:
        if not (root / manifest_mod.MANIFEST_FILENAME).is_file():
            manifest_mod.import_dir(str(root))
        return manifest_mod.load(str(root)), None
    except manifest_mod.ManifestError as exc:
        return None, {"ok": False, "error": str(exc)}


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


REQUIRED_EVIDENCE = {
    "standard": [
        {"kind": ["article", "report", "filing", "dataset", "transcript",
                  "price-feed"],
         "label": "at least one cited source"},
    ],
    "memo": [
        {"kind": ["article", "report", "filing", "dataset", "transcript",
                  "price-feed"],
         "label": "at least one cited source"},
    ],
    "whitepaper": [
        {"kind": ["dataset", "report"], "label": "thesis evidence"},
        {"kind": ["article", "report", "filing"], "label": "background source"},
    ],
    "earnings-recap": [
        {"kind": ["filing", "transcript"],
         "label": "results source (filing or call transcript)"},
        {"kind": ["price-feed", "dataset"], "label": "market reaction data"},
    ],
    "sector-outlook": [
        {"kind": ["dataset", "price-feed"], "label": "sector price data"},
        {"kind": ["report", "filing"], "label": "sector fundamentals"},
    ],
    "thematic-deepdive": [
        {"kind": ["dataset"], "label": "theme data"},
        {"kind": ["report", "article"], "label": "theme research"},
    ],
    "macro-outlook": [
        {"kind": ["dataset"], "label": "macro data series"},
    ],
    "quant-factor-brief": [
        {"kind": ["dataset", "price-feed"], "label": "return/price data"},
        {"kind": ["report"], "label": "factor research"},
    ],
    "technical-brief": [
        {"kind": ["price-feed", "dataset"], "label": "market price data"},
    ],
    "esg-sustainability": [
        {"kind": ["report"], "label": "ESG data source"},
        {"kind": ["article", "report"], "label": "controversy coverage"},
    ],
    "crypto-digital": [
        {"kind": ["dataset", "price-feed"], "label": "market data"},
    ],
    "desk-synthesis": [
        {"kind": ["report"], "label": "desk input note"},
    ],
    "modern": [
        {"kind": ["dataset", "price-feed", "report"], "label": "signal evidence"},
    ],
}


ILLUSTRATIVE_MARKERS = ("ILLUSTRATIVE", "example-data", "Lorem", "Add a short abstract here")


_MONEY_RE = re.compile(r"\$\s?-?[\d,]+(?:\.\d+)?(?:\s?[Uu][Ss][Dd])?|[\d,]+(?:\.\d+)?\s?[Uu][Ss][Dd]")


_PCT_RE = re.compile(r"-?[\d,]+(?:\.\d+)?\s?(?:percent\b|pct\b|bps?\b|%)", re.IGNORECASE)


_ASOF_RE = re.compile(r"[Aa]s of (\d{4}-\d{2}-\d{2})")


_DATE_FM_RE = re.compile(r"^date\s*:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)


_FIGREF_RE = re.compile(r"@fig-([\w-]+)")


_FIGANCHOR_RE = re.compile(r"\{#fig-([\w-]+)[^}]*\}")


_SIGN_NEG_RE = re.compile(r"\b(minus|negative|fell|dropped|declined|lost)\b", re.IGNORECASE)


_SRC_CITE_RE = re.compile(r"@(src-[\w-]+)")


_CODE_SPAN_RE = re.compile(r"`[^`\n]+`")


_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


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


_FIGEMBED_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)\{#fig-([\w-]+)([^}]*)\}")


_WIDTH_PCT_RE = re.compile(r"width\s*=\s*\"?(\d+(?:\.\d+)?)\s*%\"?")


_COLUMN_PAGE_RE = re.compile(r"column\s*:\s*(page|screen)")


_NCOL_RE = re.compile(r"layout-ncol\s*=")


def _run_figure_lint(root: Path) -> str | None:
    """Run scripts/figure_lint.py; None when clean/missing, else output tail."""
    script = Path(__file__).resolve().parents[2] / "scripts" / "figure_lint.py"
    if not script.is_file():
        return None
    try:
        return _rlint.figure_lint(script, root)
    except _rerrors.ToolTimeoutError:
        return None


_BIB_YEAR_RE = re.compile(r"(\d{4})")


FACT_HISTORY_CAP = 20


_ROLLFORWARD_SKIP = ("output", ".reportforge-state.json", "report.json",
                     ".reportforge.lock")


_COVER_BLOCKS = ("target", "scenarios", "metrics")


_BUNDLE_FORMATS = ("html", "pdf", "docx")


MCP_TOOL_NAMES_FALLBACK = [
    "reportforge_list_templates", "reportforge_scaffold_report",
    "reportforge_scaffold_from_brief",
    "reportforge_render_report", "reportforge_save_chart",
    "reportforge_write_report_body", "reportforge_publish_report",
    "reportforge_run_code", "reportforge_run_file",
    "reportforge_save_asset", "reportforge_project_status",
    "reportforge_read_project_file", "reportforge_append_section",
    "reportforge_get_section", "reportforge_replace_section",
    "reportforge_move_section", "reportforge_delete_section",
    "reportforge_export_release", "reportforge_check_readiness",
    "reportforge_record_review", "reportforge_render_preview",
    "reportforge_register_source", "reportforge_register_exhibit",
    "reportforge_register_fact", "reportforge_update_fact",
    "reportforge_freeze_release", "reportforge_rollforward_report",
    "reportforge_derive_cover",
    "reportforge_capabilities",
]


def _pdf_page_count(pdf: Path) -> int:
    """Page count via pdfinfo (poppler); -1 when unavailable/unreadable."""
    return _rpoppler.page_count(pdf)


def _chromium_binary() -> str | None:
    return _rtoolchain.chromium_binary()


def _render_pdf_web(workdir: Path, html_path: Path, out_dir: Path, stem: str) -> dict:
    chromium = _E._chromium_binary()
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
    cmd = _rquarto.build_print_cmd(chromium, html_path, pdf_out)
    try:
        proc = _rquarto.print_pdf(cmd, timeout=CHROMIUM_PRINT_TIMEOUT_S)
    except _rerrors.ToolTimeoutError:
        return {"ok": False, "error": f"chromium print-to-pdf timed out after {CHROMIUM_PRINT_TIMEOUT_S}s"}
    if proc.returncode != 0 or not pdf_out.is_file():
        tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-15:])
        return {"ok": False, "error": "chromium print-to-pdf failed", "log_tail": tail}
    return {
        "ok": True,
        "pdf": str(pdf_out),
        "note": "pdf-web is a print snapshot of the html render; interactive JS/plotly content lives in the html artifact",
    }


def _project_root_of(src: Path) -> Path | None:
    start = src if src.is_dir() else src.parent
    for parent in [start, *start.parents]:
        if (parent / "_quarto.yml").exists():
            return parent
    return None


def _declares_typst_format(workdir: Path) -> bool:
    """True when a project drives its PDF through `format: typst` — either
    custom template partials (modern/studio/portfolio/ledger) or built-in
    typst-only options such as the whitepaper title page."""
    yml = workdir / "_quarto.yml"
    if not yml.exists():
        return False
    return "  typst:" in yml.read_text()


def _quarto_tools_dir() -> Path | None:
    quarto = _rtoolchain.which("quarto")
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


def _default_reference_docx() -> Path | None:
    """Bootstrap a pandoc reference.docx into the repo cache (best effort)."""
    return _rtoolchain.default_reference_docx()


