"""Engine publish cluster (Phase 3 split; see plan §4).

All engine-level references go through `_E` (deferred package
attribute access) so monkeypatching `reportforge.engine.<name>`
keeps working.
"""

from __future__ import annotations

from reportforge import engine as _E

import os
import shutil
from pathlib import Path



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
    root = _E.REPORTS_DIR / project.strip("/")
    if not root.is_dir():
        return {"ok": False, "error": f"project not found: {project}"}
    out_dir = _E._output_dir_of(root)
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
        candidate = _E.REPORTS_DIR / project.strip("/")
        if candidate.is_dir():
            root = candidate
    if root is None:
        # Fall back to the most recently modified project directory.
        projects = [d for d in _E.REPORTS_DIR.iterdir() if d.is_dir()] if _E.REPORTS_DIR.is_dir() else []
        if projects:
            root = max(projects, key=lambda d: d.stat().st_mtime)
    if root is None:
        # No project to anchor to — leave the path alone and let the write fail
        # loudly with a clear error rather than guessing.
        return path_str
    figures = root / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    return str(figures / p.name)


