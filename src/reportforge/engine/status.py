"""Engine status cluster (Phase 3 split; see plan §4).

All engine-level references go through `_E` (deferred package
attribute access) so monkeypatching `reportforge.engine.<name>`
keeps working.
"""

from __future__ import annotations

from reportforge import engine as _E

import json
from pathlib import Path
import yaml
from reportforge import manifest as manifest_mod
from reportforge import templates
from reportforge.renderer import toolchain as _rtoolchain



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
        # RF-03 discovery (B-5): counts AND full maps — pinned shape, no
        # truncation at human scale (critic-2: pick one, pin it in tests).
        "evidence": {
            "counts": {"sources": len(d.get("sources", {})),
                       "exhibits": len(d.get("exhibits", {})),
                       "facts": len(d.get("facts", {}))},
            "sources": d.get("sources", {}),
            "exhibits": d.get("exhibits", {}),
            "facts": d.get("facts", {}),
            "registry_version": d.get("registry_version", 0),
        },
        # C-4: sealed release (None until render_report seals one).
        "release": _E._release_summary(root),
    }, None


def open_report(project: str) -> dict:
    """Open a report by slug: brief, profile, sections, revision, state,
    plus missing_work (§4.2 readiness summary) and artifacts (§1.6)."""
    root = _E.REPORTS_DIR / project.strip("/")
    if not root.is_dir():
        return {"ok": False, "error": f"project not found: {project}"}
    view, manifest_error = _manifest_view(root)
    if view is None:
        return {"ok": False, "error": f"project has no readable manifest: {project}",
                "manifest_error": manifest_error}
    out_dir = _E._output_dir_of(root)
    artifacts = _status_artifacts(root, out_dir)
    return {"ok": True, **view,
            "missing_work": _E._missing_work_summary(root, view, artifacts),
            "artifacts": artifacts}


def project_status(project: str) -> dict:
    """Summarize a report project: files, configured formats, render state."""
    root = _E.REPORTS_DIR / project.strip("/")
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
    out_dir = _E._output_dir_of(root)
    render_logs = sorted(p.name for p in out_dir.glob(".render-log-*.txt")) if out_dir.is_dir() else []
    view, manifest_error = _manifest_view(root)
    artifacts = _status_artifacts(root, out_dir)
    missing_work = _E._missing_work_summary(root, view, artifacts)
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
                desc = _E._file_descriptor(root, rel, _E._STATUS_FORMAT_IDS[name],
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


def read_project_file(project: str, relpath: str, max_bytes: int = 32768) -> dict:
    """Read a text file from a report project (qmd, render logs, generated data).

    Binary files return size + a mime guess instead of content. Scoped to the
    project root.
    """
    root = _E.REPORTS_DIR / project.strip("/")
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


def _mcp_tool_names() -> list[str]:
    # mcp.list_tools() is async (and unusable inside a running loop), so the
    # engine keeps this static registry — update it when adding MCP tools.
    return list(_E.MCP_TOOL_NAMES_FALLBACK)


def reportforge_capabilities() -> dict:
    """Capability discovery (§6): templates, profiles, support matrix, env."""
    templates = _E.list_templates()
    matrix = [{
        "report_type": t.get("name"),
        "template": t.get("name"),
        "formats": t.get("formats", []),
        "exhibit_labels": bool(t.get("exhibit_labels", False)),
        "toc": bool(t.get("toc", False)),
        "content_neutral": bool(t.get("content_neutral", False)),
    } for t in templates]
    exec_on = _E._exec_enabled()
    pdftoppm = _rtoolchain.which("pdftoppm")
    return {
        "schema_version": 1,
        "server": "reportforge",
        "templates": templates,
        "profiles": {
            "report_types": [t.get("name") for t in templates],
            # C-8 R1-F11: advertise matrix truth — the single-brand,
            # magazine-layout reality from §9.1, not aspirational lists.
            "brands": ["quantflow"],
            "themes": ["light", "dark"],
            "layouts": ["magazine"],
            "output_profiles": ["editorial", "web"],
            "overridable_axes": ["output_profile", "policy"],
            "fixed_axes": ["report_type", "brand", "theme", "layout"],
            # Template name → stored manifest profile.report_type for the
            # cases where they differ. C-1: no renames remain (studio stays
            # studio) — the map is empty and pinned so any future rename
            # must update discovery + stored profiles together.
            "report_type_map": {},
        },
        "release": {
            "record": "output/release.json",
            "identity": "12-hex sha256 of index.qmd + registry content "
                        "hash (sources.bib + figures/) + toolchain + "
                        "template_version",
            "merge": "per-format renders merge under the project lock; a "
                     "sealed record from a different snapshot covering "
                     "formats outside the run fails loudly (re-render "
                     "together)",
            "verify_tool": "reportforge_freeze_release",
        },
        "rollforward": {
            "tool": "reportforge_rollforward_report",
            "carries": ["sources", "exhibits", "facts", "figures/",
                        "sources.bib", "_quarto.yml", "index.qmd"],
            "excludes": ["output/", ".reportforge-state.json",
                         "report.json", ".reportforge.lock"],
            "returns": ["carried", "stale", "unknown_vintage",
                        "supersedes"],
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
        "evidence": {
            "registry": True,
            "citation_syntax": "[@key] (bracket) and @key (in-text); "
                               "keys live in the src- namespace",
            "bib_file": "sources.bib",
            "fact_kinds": list(manifest_mod.FACT_KINDS),
            "register_tools": ["reportforge_register_source",
                               "reportforge_register_exhibit",
                               "reportforge_register_fact",
                               "reportforge_update_fact"],
            "cover_tools": ["reportforge_derive_cover"],
            "caption_attribution": "editorial convention for Milestone B "
                                   "(records carry source_keys/as_of/alt; "
                                   "nothing renders them into captions yet)",
        },
        "tools": _mcp_tool_names(),
        "docs": {"flagship_rules": "docs/flagship-rules.md",
                 "contracts": "docs/milestone-a-contracts.md",
                 "journeys": "docs/agent-journeys.md"},
    }


def _render_state_revision(root: Path) -> int | None:
    """Manifest revision stamped at render time (None when unstamped/legacy)."""
    try:
        state = json.loads((root / ".reportforge-state.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
    rev = state.get("manifest_revision") if isinstance(state, dict) else None
    return rev if isinstance(rev, int) else None


def _render_state_registry_version(root: Path) -> int | None:
    """Registry version stamped at render time (None when unstamped/legacy).

    Legacy state files predate the field — absent means "made before the
    binding existed", not "version zero", so callers proceed (the revision
    check still gates truly ancient PDFs).
    """
    try:
        state = json.loads((root / ".reportforge-state.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
    reg = state.get("registry_version") if isinstance(state, dict) else None
    return reg if isinstance(reg, int) else None


