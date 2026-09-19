"""Engine exec_env cluster (Phase 3 split; see plan §4).

All engine-level references go through `_E` (deferred package
attribute access) so monkeypatching `reportforge.engine.<name>`
keeps working.
"""

from __future__ import annotations

from reportforge import engine as _E

import contextlib
import os
import tempfile
import threading
import time
from pathlib import Path
from reportforge.renderer import errors as _rerrors
from reportforge.renderer import interpreters as _rinterpreters
from reportforge.renderer import toolchain as _rtoolchain

_SHORT_TMP_LOCK = threading.Lock()



def _exec_enabled() -> bool:
    flag = os.environ.get("REPORTFORGE_EXEC", "").strip().lower()
    return flag not in {"off", "0", "false", "no"}


def _project_optional() -> bool:
    return os.environ.get("REPORTFORGE_PROJECT_OPTIONAL", "").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_project_root(project: str | None, require: bool) -> tuple[Path | None, dict | None]:
    if project and project.strip():
        root = _E.REPORTS_DIR / project.strip("/")
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


def _tail(text: str, limit: int = _E.EXEC_OUTPUT_TAIL) -> str:
    if len(text) <= limit:
        return text
    return "…[truncated]…\n" + text[-limit:]


def _short_tmp_dir() -> str:
    """Short Chrome-safe temp dir for spawned code and in-process exports.

    Unix sockets cap at 108 chars (sun_path); deer-flow pins ~150-char
    thread tmp into MCP envs, under which Chrome cannot create its profile
    SingletonSocket (kaleido BrowserFailedError, NVDA flagship 2026-09-19).
    A fixed short dir under /tmp keeps exports working regardless of
    spawner env. Per-uid so multi-user hosts don't collide on the 0700 dir.
    """
    path = Path(f"/tmp/rf-exec-{os.geteuid()}")
    path.mkdir(parents=True, exist_ok=True)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return str(path)


def _short_tmp_env_overlay() -> dict[str, str]:
    tmp = _short_tmp_dir()
    return {"TMPDIR": tmp, "TEMP": tmp, "TMP": tmp}


def _child_env() -> dict[str, str]:
    """Environment for run_code/run_file children: inherited env with the
    short-tmp overlay. Deliverables still land in the project via cwd; only
    genuine temp moves out of the (possibly socket-unsafe) spawner tmp."""
    return {**os.environ, **_short_tmp_env_overlay()}


@contextlib.contextmanager
def _chrome_safe_tmp():
    """Run an in-process Chrome export (save_chart) under the short tmp.

    Swaps the TMPDIR trio plus tempfile's cached tempdir; restores both
    after. Serialized with a lock so concurrent exports can't interleave
    the swap (the race would only misplace temp files, but exports are
    seconds-long so serializing is free).
    """
    overlay = _short_tmp_env_overlay()
    with _SHORT_TMP_LOCK:
        saved_env = {key: os.environ.get(key) for key in overlay}
        saved_tempdir = tempfile.tempdir
        try:
            os.environ.update(overlay)
            tempfile.tempdir = overlay["TMPDIR"]
            yield overlay["TMPDIR"]
        finally:
            for key, value in saved_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            tempfile.tempdir = saved_tempdir


def _png_theme_line(png_path: Path) -> dict | None:
    """Best-effort theme observation for one created PNG: corner hex plus
    the QuantFlow-Paper stamp save_figure burns in (None when unreadable).
    Lets agents spot a dark batch after the first export call instead of
    after all eighteen (NVDA flagship 2026-09-19)."""
    try:
        from PIL import Image

        with Image.open(png_path) as img:
            pixel = img.convert("RGB").getpixel((0, 0))
            corner = "#{:02x}{:02x}{:02x}".format(*pixel[:3])
            stamp = (img.info or {}).get("QuantFlow-Paper")
        return {"corner": corner, "paper_stamp": str(stamp) if stamp else None}
    except Exception:
        return None


def _theme_lines_for_created(root: Path, created: list[str]) -> list[dict]:
    lines = []
    for rel in created:
        if not rel.lower().endswith(".png"):
            continue
        line = _png_theme_line(root / rel)
        if line is not None:
            lines.append({"path": rel, **line})
    return lines


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
    interpreter = _E._venv_python()
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
        proc = _rinterpreters.run(
            [str(interpreter), "-c", code],
            cwd=cwd,
            timeout=timeout,
            env=_child_env(),
        )
    except _rerrors.ToolTimeoutError:
        return {"ok": False, "error": f"run_code timed out after {timeout}s"}
    except OSError as exc:
        return {"ok": False, "error": f"interpreter launch failed: {exc}"}
    duration = round(time.monotonic() - started, 3)
    if root is not None:
        created, modified = _diff_snapshot(root, before)
    else:
        created, modified = [], []
    result = {
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
    if root is not None:
        theme_lines = _theme_lines_for_created(root, created)
        if theme_lines:
            result["png_theme"] = theme_lines
    return result


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
    interpreter = _E._venv_python()
    if ext == ".py":
        if interpreter is None:
            return {"ok": False, "error": "no reportforge python interpreter found"}
        cmd = [str(interpreter), str(script)]
    elif ext == ".sh":
        cmd = ["bash", str(script)]
    elif ext == ".r":
        rscript = _rtoolchain.which("Rscript")
        if not rscript:
            return {"ok": False, "error": "Rscript not found on PATH"}
        cmd = [rscript, str(script)]
    else:
        return {"ok": False, "error": f"unsupported script type: {ext} (use .py, .sh, or .R)"}
    cmd += list(args or [])
    before = _snapshot_project(root)
    started = time.monotonic()
    try:
        proc = _rinterpreters.run(cmd, cwd=str(root), timeout=timeout, env=_child_env())
    except _rerrors.ToolTimeoutError:
        return {"ok": False, "error": f"run_file timed out after {timeout}s"}
    except OSError as exc:
        return {"ok": False, "error": f"script launch failed: {exc}"}
    created, modified = _diff_snapshot(root, before)
    result = {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout_tail": _tail(proc.stdout),
        "stderr_tail": _tail(proc.stderr),
        "created": created,
        "modified": modified,
        "duration_s": round(time.monotonic() - started, 3),
        "cwd": str(root),
    }
    theme_lines = _theme_lines_for_created(root, created)
    if theme_lines:
        result["png_theme"] = theme_lines
    return result


