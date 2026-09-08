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

SCHEMA_VERSION = 2
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
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_SLUG_BAD_RE = re.compile(r"[^a-z0-9]+")
_ATTR_SUFFIX_RE = re.compile(r"\s*\{[^}]*\}\s*$")


def _iter_prose_lines(body: list[str]):
    """Yield ``(index, line)`` pairs for body lines outside fenced code blocks.

    QMD reports embed executable python chunks; a `#` comment inside a
    fence is not a heading and must never become a section id. The index
    is the position in the original body list so `line_start` stays exact.
    """
    in_fence: str | None = None
    for i, line in enumerate(body):
        m = _FENCE_RE.match(line)
        if m:
            fence = m.group(1)[0]  # backtick vs tilde; length need not match to close
            if in_fence is None:
                in_fence = fence
            elif fence == in_fence:
                in_fence = None
            continue  # fence markers themselves are never headings
        if in_fence is not None:
            continue
        yield i, line


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
    seen_ids: dict[str, int] = {}
    for i, line in _iter_prose_lines(body):
        m = _HEADING_RE.match(line)
        if not m:
            continue
        level = len(m.group(1))
        # Strip quarto span attributes ({.appendix}, {-}) for a clean title/id.
        title = _ATTR_SUFFIX_RE.sub("", m.group(2)).strip()
        if not title:
            continue
        base_id = slugify_section_id(title)
        n = seen_ids.get(base_id, 0)
        seen_ids[base_id] = n + 1
        # Duplicate headings are common (e.g. repeated "Results"); the
        # contract's collision-free rule gets a -2/-3 suffix.
        sid = base_id if n == 0 else f"{base_id}-{n + 1}"
        sections.append(
            {
                "id": sid,
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
    # RF-03 evidence registries (Milestone B): sources cited from prose,
    # exhibits backing figures, shared fact records. Schema 2: pre-B
    # loaders must fail loudly on these files, never silently wipe them.
    sources: dict = field(default_factory=dict)
    exhibits: dict = field(default_factory=dict)
    facts: dict = field(default_factory=dict)
    # Render-input generation: registry writes touch sources.bib/_quarto.yml,
    # so each mutation bumps this; preview/review bindings record it and
    # warn on mismatch (content revision is for prose edits only).
    registry_version: int = 0
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
        init = {k: v for k, v in data.items() if k in known}
        for map_name, validator in (("sources", validate_source),
                                    ("exhibits", validate_exhibit),
                                    ("facts", validate_fact)):
            records = init.get(map_name, {})
            if not isinstance(records, dict):
                raise ManifestError(f"manifest {map_name!r} is not a map")
            for key, rec in records.items():
                ok, err = validator(rec)
                if not ok:
                    raise ManifestError(
                        f"manifest {map_name}[{key!r}] invalid: {err}")
        reg = init.get("registry_version", 0)
        if not isinstance(reg, int) or isinstance(reg, bool):
            raise ManifestError(
                f"manifest registry_version is not an int: {reg!r}")
        return cls(**init)


# --- RF-03 record validators (shape-only; link checks live in engine) --------

SOURCE_KINDS = ("filing", "article", "dataset", "price-feed",
                "transcript", "report", "other")
FACT_KINDS = ("observed", "calculated", "estimated", "illustrative")

_SOURCE_KEY_RE = re.compile(r"^src-[a-z0-9][a-z0-9-]*$")
# F5: one namespace rule everywhere — exhibit ids are lowercase slugs too,
# matching src- and fact- keys.
_EXHIBIT_ID_RE = re.compile(r"^fig-[a-z0-9][a-z0-9-]*$")
_FACT_ID_RE = re.compile(r"^fact-[a-z0-9][a-z0-9-]*$")


def _nonempty_str(rec: dict, key: str) -> bool:
    val = rec.get(key)
    return isinstance(val, str) and bool(val.strip())


def validate_source(rec: object) -> tuple[bool, str]:
    """Shape-check a source record. Returns (ok, error)."""
    if not isinstance(rec, dict):
        return False, "source record is not an object"
    key = rec.get("key", "")
    if not isinstance(key, str) or not _SOURCE_KEY_RE.match(key):
        # The src- namespace is reserved: fig-/tbl-/sec- crossrefs and
        # bare words are never citekeys (contract: pandoc-builtin exclusion).
        return False, f"key {key!r} must match src-<slug>"
    if rec.get("kind") not in SOURCE_KINDS:
        return False, f"kind {rec.get('kind')!r} not in {list(SOURCE_KINDS)}"
    if not _nonempty_str(rec, "title"):
        return False, "title is required"
    if not _nonempty_str(rec, "date") and not _nonempty_str(rec, "as_of"):
        return False, "one of date / as_of is required"
    return True, ""


def validate_exhibit(rec: object) -> tuple[bool, str]:
    """Shape-check an exhibit record. Returns (ok, error)."""
    if not isinstance(rec, dict):
        return False, "exhibit record is not an object"
    if not isinstance(rec.get("id"), str) or not _EXHIBIT_ID_RE.match(rec["id"]):
        return False, f"id {rec.get('id')!r} must reuse a figure anchor (fig-<id>)"
    if not _nonempty_str(rec, "title"):
        return False, "title is required"
    if rec.get("file") is not None and not isinstance(rec.get("file"), str):
        return False, "file must be a path string or null (anchor-grounded)"
    for link_key in ("source_keys", "fact_ids"):
        links = rec.get(link_key, [])
        if not isinstance(links, list) or not all(isinstance(x, str) for x in links):
            return False, f"{link_key} must be a list of id strings"
    return True, ""


def validate_fact(rec: object) -> tuple[bool, str]:
    """Shape-check a fact record. Returns (ok, error)."""
    if not isinstance(rec, dict):
        return False, "fact record is not an object"
    if not isinstance(rec.get("id"), str) or not _FACT_ID_RE.match(rec["id"]):
        return False, f"id {rec.get('id')!r} must match fact-<slug>"
    value = rec.get("value")
    if value is None:
        return False, "value is required (numeric or string)"
    # F3: an empty/blank string is a vacuous fact, not a value.
    if isinstance(value, str) and not value.strip():
        return False, "value must not be an empty string"
    if not isinstance(rec.get("unit", ""), str):
        return False, "unit must be a string"
    if rec.get("kind") not in FACT_KINDS:
        return False, f"kind {rec.get('kind')!r} not in {list(FACT_KINDS)}"
    links = rec.get("source_keys", [])
    if not isinstance(links, list) or not all(isinstance(x, str) for x in links):
        return False, "source_keys must be a list of id strings"
    return True, ""


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
    root = os.fspath(root)
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
    root = os.fspath(root)
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
        qualifying = [
            r for r in manifest.reviews
            if r.get("revision") == manifest.revision
            and r.get("decision") == "approved"
        ]
        if not qualifying:
            return {
                "ok": False,
                "error": "approval requires an approved review record for the current revision",
                "current_state": manifest.state,
                "current_revision": manifest.revision,
            }
        # R2: a registration after the review changes render bytes without
        # bumping revision — the approval bound the old registry. Any
        # review at the current registry_version cures a stale one.
        if not any(r.get("registry_version", 0) == manifest.registry_version
                   for r in qualifying):
            return {
                "ok": False,
                "error": ("registry changed since the approved review "
                          f"(registry v{qualifying[-1].get('registry_version', 0)} "
                          f"-> v{manifest.registry_version}); re-review before approval"),
                "current_state": manifest.state,
                "current_revision": manifest.revision,
                "current_registry_version": manifest.registry_version,
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
            "registry_version": manifest.registry_version,
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
    body = _strip_frontmatter(qmd_text.splitlines())
    for _, line in _iter_prose_lines(body):
        m = _HEADING_RE.match(line)
        if m and len(m.group(1)) == 1:
            return m.group(2).strip()
    return fallback


def create(root: str, title: str, brief: str = "", profile: dict | None = None,
           formats: list | None = None, sections: list | None = None,
           actor: str = "tool:scaffold", overwrite: bool = False) -> Manifest:
    """Build a fresh revision-1 draft manifest and save it.

    Refuses to clobber an existing manifest unless ``overwrite=True`` —
    revision history is immutable per contract §1.2, so a silent reset to
    revision 1 is never acceptable.
    """
    root = os.fspath(root)
    if not overwrite and os.path.isfile(_manifest_path(root)):
        raise ManifestError(
            f"manifest already exists at {_manifest_path(root)}; "
            "pass overwrite=True to reset it (revision history will be lost)"
        )
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
    # Contract §1.2: never guess. A present-but-unrecognized template value
    # is echoed verbatim so the anomaly stays visible; only an absent value
    # falls back to "standard".
    genre = template if template else "standard"
    theme = "dark" if (template or "").endswith("-dark") else "light"
    return {
        "report_type": genre,
        "brand": "quantflow",
        "theme": theme,
        "layout": "magazine",
        "output_profile": "editorial",
        # Contract §1.2 lists general|flagship|draft policies but gives no
        # Milestone-A derivation rule; fresh manifests start restrictive.
        # RF-08 (workflow gates) will own policy transitions.
        "policy": "draft",
    }


def _formats_from_quarto_yml(root: str) -> list[str] | None:
    """Parse `format:` keys from the report's _quarto.yml (stdlib-only).

    Returns None when the file is missing or has no recognizable format
    block, letting the caller fall back to its default.
    """
    try:
        text = open(os.path.join(root, "_quarto.yml"), encoding="utf-8").read()
    except OSError:
        return None
    formats: list[str] = []
    in_format_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^format\s*:", stripped):
            # Inline form: `format: html` — block form follows on next lines.
            inline = stripped.split(":", 1)[1].strip()
            if inline:
                return [inline] if inline in ("html", "pdf", "docx") else None
            in_format_block = True
            continue
        if in_format_block:
            if not line[:1].isspace() and stripped:
                break  # dedented: block over
            m = re.match(r"^\s{2,}(html|pdf|docx)\s*:", line)
            if m and m.group(1) not in formats:
                formats.append(m.group(1))
    return formats or None


def import_dir(root: str) -> Manifest:
    """Adopt a pre-manifest report dir. Never rewrites index.qmd."""
    root = os.fspath(root)
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
        # Contract §1.2: formats derive from _quarto.yml at import time.
        formats=_formats_from_quarto_yml(root) or ["html", "pdf", "docx"],
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
