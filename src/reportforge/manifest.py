"""Report manifest (RF-01): identity, revision, and lifecycle for file-first reports.

The manifest (``report.json`` at a report directory root) is metadata and
index only — prose always lives in ``index.qmd``. The section index is a
rebuildable projection of the QMD headings (contract
``docs/milestone-a-contracts.md`` §1): every :func:`load` re-scans the QMD,
repairs drift, and bumps the revision when a hand edit changed anything.

Stdlib only. Atomic writes (temp file + ``os.replace``).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime

SCHEMA_VERSION = 1
MANIFEST_FILENAME = "report.json"
QMD_FILENAME = "index.qmd"

STATES = ("draft", "review", "approved", "exported")

TRANSITIONS = {
    "draft": ("review",),
    "review": ("draft", "approved"),
    "approved": ("exported", "review"),
    "exported": ("review",),
}

REVISION_LOG_CAP = 50
IDEMPOTENCY_CAP = 500
REVIEWS_CAP = 100

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_SLUG_BAD_RE = re.compile(r"[^a-z0-9]+")


class ManifestError(Exception):
    """Loud failure for missing/corrupt/newer-schema manifests."""


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def slugify_section_id(heading_text: str) -> str:
    """Stable content-addressed section id: ``s-`` + slugified heading text."""
    slug = _SLUG_BAD_RE.sub("-", heading_text.strip().lower()).strip("-")
    return "s-" + (slug or "section")


def _strip_frontmatter(lines: list[str]) -> list[str]:
    """Remove a leading YAML frontmatter block (--- ... ---) if present."""
    if len(lines) >= 2 and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() in ("---", "..."):
                return lines[i + 1 :]
    return lines


def scan_sections(qmd_text: str) -> list[dict]:
    """Project the QMD headings into ``[{id, title, level, line_start}]``.

    ``line_start`` is the 1-based line number of the heading in the original
    text (frontmatter included) — advisory only; ops address sections by id.
    """
    lines = qmd_text.splitlines()
    body = _strip_frontmatter(lines)
    offset = len(lines) - len(body)  # 0-based count of stripped frontmatter lines
    sections = []
    for i, line in enumerate(body):
        m = _HEADING_RE.match(line)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        if not title:
            continue
        sections.append(
            {
                "id": slugify_section_id(title),
                "title": title,
                "level": level,
                "line_start": offset + i + 1,  # 1-based in original text
            }
        )
    return sections


@dataclass
class Manifest:
    report_id: str
    title: str
    brief: str = ""
    profile: dict = field(default_factory=dict)
    revision: int = 1
    state: str = "draft"
    sections: list = field(default_factory=list)
    formats: list = field(default_factory=list)
    created: str = ""
    updated: str = ""
    revision_log: list = field(default_factory=list)
    idempotency_ledger: dict = field(default_factory=dict)
    reviews: list = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Manifest":
        version = data.get("schema_version", 1)
        if version > SCHEMA_VERSION:
            raise ManifestError(
                f"manifest written by newer schema (version {version}); "
                f"this loader supports up to {SCHEMA_VERSION}"
            )
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


def _manifest_path(root: str) -> str:
    return os.path.join(root, MANIFEST_FILENAME)


def _qmd_path(root: str) -> str:
    return os.path.join(root, QMD_FILENAME)


def _read_qmd(root: str) -> str | None:
    try:
        with open(_qmd_path(root), encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def save(manifest: Manifest, root: str) -> dict:
    """Atomically persist the manifest (temp file + os.replace)."""
    manifest.updated = _now_iso()
    path = _manifest_path(root)
    fd, tmp = tempfile.mkstemp(dir=root, prefix=".report.json.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return {"ok": True, "report_id": manifest.report_id, "revision": manifest.revision}


def _index_signature(sections: list[dict]) -> list[tuple]:
    return [(s["id"], s["title"], s["level"]) for s in sections]


def load(root: str) -> Manifest:
    """Load the manifest, rebuilding the section index from the QMD.

    Manual heading edits are reconciled: a drifted index is repaired and the
    revision bumped (an edit is an edit, whoever made it).
    """
    path = _manifest_path(root)
    if not os.path.exists(path):
        raise ManifestError(f"no manifest at {path} — scaffold or import_dir first")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ManifestError(f"corrupt manifest at {path}: {e}")
    manifest = Manifest.from_dict(data)
    qmd = _read_qmd(root)
    if qmd is not None:
        fresh = scan_sections(qmd)
        if _index_signature(fresh) != _index_signature(manifest.sections):
            manifest.sections = fresh
            bump(manifest, "manual-edit reconciliation: section index drifted",
                 actor="system:reconcile")
            save(manifest, root)
    return manifest


def bump(manifest: Manifest, reason: str, actor: str = "tool",
         op: str | None = None, section_id: str | None = None) -> dict:
    """Bump revision +1, log the event, reopen non-draft states to draft."""
    manifest.revision += 1
    manifest.updated = _now_iso()
    if manifest.state != "draft":
        manifest.state = "draft"
    manifest.revision_log.append(
        {
            "revision": manifest.revision,
            "timestamp": manifest.updated,
            "actor": actor,
            "op": op,
            "section_id": section_id,
            "summary": reason,
        }
    )
    del manifest.revision_log[:-REVISION_LOG_CAP]
    return {"ok": True, "revision": manifest.revision, "state": manifest.state}


def transition(manifest: Manifest, to_state: str, actor: str, note: str = "") -> dict:
    """Move the lifecycle state machine; illegal transitions fail loudly."""
    if to_state not in STATES:
        return {"ok": False, "error": f"unknown state {to_state!r}"}
    allowed = TRANSITIONS.get(manifest.state, ())
    if to_state not in allowed:
        return {
            "ok": False,
            "error": f"illegal transition {manifest.state} -> {to_state}",
            "current_state": manifest.state,
        }
    if manifest.state == "review" and to_state == "approved":
        if not any(
            r.get("revision") == manifest.revision and r.get("decision") == "approved"
            for r in manifest.reviews
        ):
            return {
                "ok": False,
                "error": "approval requires an approved review record for the current revision",
                "current_state": manifest.state,
                "current_revision": manifest.revision,
            }
    manifest.state = to_state
    manifest.updated = _now_iso()
    manifest.revision_log.append(
        {
            "revision": manifest.revision,
            "timestamp": manifest.updated,
            "actor": actor,
            "op": "transition",
            "section_id": None,
            "summary": f"{to_state} ({note})" if note else to_state,
        }
    )
    del manifest.revision_log[:-REVISION_LOG_CAP]
    return {"ok": True, "state": manifest.state, "revision": manifest.revision}


def add_review(manifest: Manifest, revision: int, reviewer: str, decision: str,
               comments: str = "", section_id: str | None = None) -> dict:
    """Append a review record (storage primitive for §4.3 record_review)."""
    if decision not in ("changes_requested", "approved"):
        return {"ok": False, "error": f"unknown decision {decision!r}"}
    manifest.reviews.append(
        {
            "revision": revision,
            "timestamp": _now_iso(),
            "reviewer": reviewer,
            "decision": decision,
            "comments": comments,
            "section_id": section_id,
        }
    )
    del manifest.reviews[:-REVIEWS_CAP]
    return {"ok": True, "revision": revision, "decision": decision}


def events_since(manifest: Manifest, revision: int, limit: int = 50) -> dict:
    """Section-level events after `revision` (for stale-revision responses)."""
    events = [e for e in manifest.revision_log if e.get("revision", 0) > revision]
    truncated = len(events) > limit
    return {"events": events[-limit:], "events_truncated": truncated}


def _frontmatter_value(qmd_text: str, key: str) -> str | None:
    lines = qmd_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() in ("---", "..."):
            break
        m = re.match(rf"^{re.escape(key)}\s*:\s*(.+?)\s*$", line)
        if m:
            return m.group(1).strip().strip("\"'")
    return None


def _title_from_qmd(qmd_text: str, fallback: str) -> str:
    title = _frontmatter_value(qmd_text, "title")
    if title:
        return title
    for line in _strip_frontmatter(qmd_text.splitlines()):
        m = _HEADING_RE.match(line)
        if m and len(m.group(1)) == 1:
            return m.group(2).strip()
    return fallback


def create(root: str, title: str, brief: str = "", profile: dict | None = None,
           formats: list | None = None, sections: list | None = None,
           actor: str = "tool:scaffold") -> Manifest:
    """Build a fresh revision-1 draft manifest and save it."""
    now = _now_iso()
    if sections is None:
        qmd = _read_qmd(root)
        sections = scan_sections(qmd) if qmd is not None else []
    manifest = Manifest(
        report_id=os.path.basename(os.path.abspath(root)),
        title=title,
        brief=brief,
        profile=profile or {},
        revision=1,
        state="draft",
        sections=sections or [],
        formats=formats or ["html", "pdf", "docx"],
        created=now,
        updated=now,
        revision_log=[
            {
                "revision": 1,
                "timestamp": now,
                "actor": actor,
                "op": "create",
                "section_id": None,
                "summary": "scaffolded",
            }
        ],
    )
    save(manifest, root)
    return manifest


def _profile_from_template(template: str | None) -> dict:
    genre = template or "standard"
    theme = "dark" if (template or "").endswith("-dark") else "light"
    return {
        "report_type": genre,
        "brand": "quantflow",
        "theme": theme,
        "layout": "magazine",
        "output_profile": "editorial",
        "policy": "draft",
    }


def import_dir(root: str) -> Manifest:
    """Adopt a pre-manifest report dir. Never rewrites index.qmd."""
    qmd = _read_qmd(root)
    if qmd is None:
        raise ManifestError(f"import needs {_qmd_path(root)} and it is missing")
    template = _frontmatter_value(qmd, "reportforge-template")
    report_id = os.path.basename(os.path.abspath(root))
    manifest = Manifest(
        report_id=report_id,
        title=_title_from_qmd(qmd, report_id),
        brief=_frontmatter_value(qmd, "description") or "",
        profile=_profile_from_template(template),
        revision=1,
        state="draft",
        sections=scan_sections(qmd),
        formats=["html", "pdf", "docx"],
        created=datetime.fromtimestamp(
            os.path.getmtime(root)).astimezone().isoformat(),
        updated=_now_iso(),
    )
    manifest.revision_log.append(
        {
            "revision": 1,
            "timestamp": manifest.updated,
            "actor": "tool:import",
            "op": "import",
            "section_id": None,
            "summary": "imported pre-manifest directory",
        }
    )
    save(manifest, root)
    return manifest
