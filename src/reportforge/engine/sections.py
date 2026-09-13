"""Engine sections cluster (Phase 3 split; see plan §4).

All engine-level references go through `_E` (deferred package
attribute access) so monkeypatching `reportforge.engine.<name>`
keeps working.
"""

from __future__ import annotations

from reportforge import engine as _E

import functools
import json
import os
import re
import tempfile
from pathlib import Path
from reportforge import manifest as manifest_mod



def write_report_body(source: str, content: str) -> dict:
    """Write/overwrite the .qmd body of a previously scaffolded report project.

    Scoped to projects under REPORTS_DIR. Resolves slugs like render_report
    does. The caller supplies the complete .qmd text including YAML front
    matter.
    """
    src = Path(source).expanduser()
    if not src.is_absolute():
        candidate = _E.REPORTS_DIR / source.strip("/") / "index.qmd"
        if candidate.exists():
            src = candidate
        else:
            src = _E.REPORTS_DIR / source.strip("/")
    try:
        src_resolved = src.resolve()
        root = _E._project_root_of(src_resolved) or src_resolved.parent
        if _E.REPORTS_DIR.resolve() not in root.parents and root != _E.REPORTS_DIR.resolve():
            return {"ok": False, "error": f"target is not inside the report-forge projects directory ({_E.REPORTS_DIR})"}
    except Exception as exc:
        return {"ok": False, "error": f"cannot resolve target: {exc}"}
    target = src_resolved if src_resolved.suffix == ".qmd" else src_resolved / "index.qmd"
    try:
        target.write_text(content)
    except Exception as exc:
        return {"ok": False, "error": f"write failed: {exc}"}
    return {"ok": True, "source": str(target), "bytes": len(content.encode("utf-8"))}


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
    root = _E.REPORTS_DIR / project.strip("/")
    if not root.is_dir():
        return {"ok": False, "error": f"project not found: {project}"}
    qmd_path = root / "index.qmd"
    if not qmd_path.is_file():
        return {"ok": False, "error": f"project has no index.qmd: {project}"}
    with _E._project_lock(root):
        manifest, err = _E._load_or_import(root)
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


def _project_root_or_error(project: str) -> tuple[Path | None, dict | None]:
    root = (_E.REPORTS_DIR / project.strip("/")).resolve()
    if _E.REPORTS_DIR.resolve() not in root.parents and root != _E.REPORTS_DIR.resolve():
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
    manifest, err = _E._load_or_import(root)
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
    with _E._project_lock(root):
        manifest, err = _E._load_or_import(root)
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
    with _E._project_lock(root):
        manifest, err = _E._load_or_import(root)
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
    with _E._project_lock(root):
        manifest, err = _E._load_or_import(root)
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


def _set_frontmatter_description(qmd_path: Path, brief: str) -> None:
    """Point the copied QMD's description at the new brief (best-effort)."""
    try:
        lines = qmd_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if not lines or lines[0].strip() != "---":
        return
    end = None
    title_at = None
    for i in range(1, len(lines)):
        stripped = lines[i].strip()
        if stripped in ("---", "..."):
            end = i
            break
        if re.match(r"^description\s*:", lines[i]):
            lines[i] = f"description: {json.dumps(brief, ensure_ascii=False)}"
            qmd_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return
        if title_at is None and re.match(r"^title\s*:", lines[i]):
            title_at = i
    if end is None:
        return
    insert_at = (title_at + 1) if title_at is not None else 1
    lines.insert(insert_at,
                 f"description: {json.dumps(brief, ensure_ascii=False)}")
    try:
        qmd_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass


