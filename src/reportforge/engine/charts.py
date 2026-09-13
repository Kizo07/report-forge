"""Engine charts cluster (Phase 3 split; see plan §4).

All engine-level references go through `_E` (deferred package
attribute access) so monkeypatching `reportforge.engine.<name>`
keeps working.
"""

from __future__ import annotations

from reportforge import engine as _E

import base64
import re
from pathlib import Path
from reportforge import manifest as manifest_mod



def tokens_for_keys() -> list[str]:
    """Palette names the token map covers (pinned; a new palette extends it)."""
    return sorted(_E.BRAND_TOKENS)


def tokens_for(palette: str) -> dict:
    """Resolve a palette name to its token record; unknown names fail
    loudly with the supported set (never a bare KeyError)."""
    try:
        return _E.BRAND_TOKENS[palette]
    except KeyError:
        raise ValueError(
            f"unknown palette {palette!r}; supported: {sorted(_E.BRAND_TOKENS)}")


def _apply_quantflow_plotly_template(fig, name: str) -> None:
    """Style a figure with the QuantFlow plotly identity (in place)."""
    import plotly.graph_objects as go
    import plotly.io as pio

    pal = tokens_for(name)
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


def _slugify_exhibit_id(stem: str) -> str:
    """F5 companion: slugify an auto-derived exhibit stem into the shared
    lowercase namespace (same rule as _SOURCE_KEY_RE/_FACT_ID_RE)."""
    slug = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    return f"fig-{slug or 'chart'}"


def _anchor_chart_output(out_basename: str, project: str | None,
                         root: Path | None) -> str:
    """Precedence rule for chart output paths (critic-1 compat finding).

    1. Sandbox paths (/mnt/user-data/...) → project's figures/ (existing
       translation — the host cannot write the agent's sandbox).
    2. An absolute path that already resolves inside the project → honored
       verbatim (existing callers pass <root>/figures/<name>).
    3. Anything else with a project (bare names, project-relative paths,
       absolute paths outside the project) → <root>/figures/<name...>,
       preserving any relative subdirectories.
    4. No project → unchanged (today's byte-for-byte behavior).
    """
    translated = _E._translate_sandbox_path(out_basename, project)
    if translated != out_basename:
        return translated
    if root is None:
        return out_basename
    p = Path(out_basename).expanduser()
    if p.is_absolute():
        try:
            p.resolve().relative_to(root.resolve())
            return out_basename
        except (ValueError, OSError):
            pass  # outside the project: redirect into figures/
        return str(root / "figures" / p.name)
    return str(root / "figures" / p)


def save_chart(fig_json: str, out_basename: str, width: int = 1400, height: int = 700, scale: int = 2, project: str | None = None, template: str | None = None, exhibit_id: str | None = None, exhibit_title: str | None = None, source_keys: list[str] | None = None, fact_ids: list[str] | None = None) -> dict:
    try:
        import plotly.io as pio

        fig = pio.from_json(fig_json)
    except Exception as exc:
        return {"ok": False, "error": f"invalid plotly figure JSON: {exc}"}
    template_applied: str | None = None
    try:
        if template:
            # C-3: explicit template= maps through the token keys first
            # (quantflow-dark/light, ledger-dark/light); anything else is
            # a stock/custom plotly template name handled by plotly itself.
            if template in _E.BRAND_TOKENS:
                _apply_quantflow_plotly_template(fig, template)
                template_applied = template
            else:
                if template not in pio.templates:
                    return {"ok": False, "error": f"unknown plotly template: {template}"}
                fig.update_layout(template=template)
                template_applied = template
        elif _E._figure_template_is_stock_default(fig):
            # No deliberate figure theme: match the page with the QuantFlow
            # identity so charts sit natively in portfolio reports.
            page = _E._project_template_name(project, Path(out_basename).expanduser())
            qname = _E._PORTFOLIO_TO_QUANTFLOW_TEMPLATE.get(page or "")
            if qname is not None:
                _apply_quantflow_plotly_template(fig, qname)
                template_applied = qname
    except Exception as exc:
        return {"ok": False, "error": f"chart theming failed: {exc}"}
    # Sandbox-path translation (lesson of AAPL run 1, 2026-09-01): the agent's
    # sandbox exposes /mnt/user-data/... while this MCP server runs on the
    # host filesystem. Sandbox paths written here would fail silently from the
    # agent's perspective. Milestone B precedence (_anchor_chart_output):
    # in-project absolutes honored, everything else lands in figures/.
    root: Path | None = None
    if project is not None:
        root, root_err = _E._project_root_or_error(project)
        if root_err:
            return root_err
        assert root is not None
        # Fail-before-write: dangling exhibit links must never leave a
        # half-registered chart on disk (B-3 test pins this ordering).
        manifest_pre, pre_err = _E._load_or_import(root)
        if pre_err:
            return pre_err
        assert manifest_pre is not None
        link_err = _E._check_registry_links(
            manifest_pre, source_keys or [], fact_ids or [])
        if link_err is not None:
            return {"ok": False, "error": link_err}
    out_basename = _anchor_chart_output(out_basename, project, root)
    out = Path(out_basename).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    png = out.with_suffix(".png")
    html_path = out.with_suffix(".html")
    try:
        fig.write_image(str(png), width=width, height=height, scale=scale)
        fig.write_html(str(html_path), include_plotlyjs="cdn", full_html=True)
    except Exception as exc:
        return {"ok": False, "error": f"chart export failed: {exc}", "partial": {"png": str(png)}}
    result: dict = {"ok": True, "png": str(png), "html": str(html_path), "embed_snippet": f"![caption.]({png.name}){{width=90%}}", "template_applied": template_applied}
    if root is not None:
        # Auto-register the exhibit (B-3): id defaults to the slugified file
        # stem in the fig- namespace; the just-written file grounds it.
        stem = png.stem
        if exhibit_id is not None:
            eid = exhibit_id
        elif stem.startswith("fig-"):
            eid = _slugify_exhibit_id(stem[4:])
        else:
            eid = _slugify_exhibit_id(stem)
        try:
            rel = str(png.resolve().relative_to(root.resolve()))
        except (ValueError, OSError):
            return {"ok": False, "error": f"chart landed outside the project root: {png}"}
        with _E._project_lock(root):
            manifest, err = _E._load_or_import(root)
            if err:
                return err
            assert manifest is not None
            # Re-saving a chart is an update, not a duplicate: None inherits
            # the existing record's links/title (F4: explicit [] clears).
            existing = manifest.exhibits.get(eid, {})
            sk = list(existing.get("source_keys", [])) if source_keys is None else list(source_keys)
            fi = list(existing.get("fact_ids", [])) if fact_ids is None else list(fact_ids)
            reg = _E._register_exhibit_locked(
                root, manifest, eid,
                exhibit_title or existing.get("title", eid), rel,
                sk, fi, existing.get("as_of"), existing.get("alt"), True)
            if not reg.get("ok"):
                return reg
            manifest_mod.save(manifest, str(root))
        result["exhibit_id"] = eid
        result["registry_version"] = manifest.registry_version
    return result


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
    root = _E.REPORTS_DIR / project.strip("/")
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


