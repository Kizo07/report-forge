"""Engine registry cluster (Phase 3 split; see plan §4).

All engine-level references go through `_E` (deferred package
attribute access) so monkeypatching `reportforge.engine.<name>`
keeps working.
"""

from __future__ import annotations

from reportforge import engine as _E

from datetime import date, datetime
from pathlib import Path
from reportforge import manifest as manifest_mod



def _bibtex_escape(text: str) -> str:
    """Escape a free-text value for a braced BibTeX field."""
    return (text.replace("\\", "\\textbackslash{}")
                .replace("{", "\\{").replace("}", "\\}"))


def _bibtex_escape_url(url: str) -> str:
    # F6: URLs are code, not prose — escape the BibTeX specials that break
    # builds (% starts a comment, _ needs math mode, # & ~ ^ are active).
    out = url.replace("\\", "\\textbackslash{}")
    for ch, esc in (("%", "\\%"), ("_", "\\_"), ("#", "\\#"),
                    ("&", "\\&"), ("~", "\\~{}"), ("^", "\\^{}"),
                    ("{", "\\{"), ("}", "\\}")):
        out = out.replace(ch, esc)
    return out


def _source_to_bibtex(record: dict) -> str:
    """Render one source record as a minimal @misc BibTeX entry (stdlib)."""
    key = record.get("key", "unknown")
    out = [f"@misc{{{key},"]
    out.append(f"  title = {{{{{_bibtex_escape(str(record.get('title', '')))}}}}},")
    if record.get("publisher"):
        out.append(f"  author = {{{{{_bibtex_escape(str(record['publisher']))}}}}},")
    year_m = _E._BIB_YEAR_RE.search(
        str(record.get("date") or "") or str(record.get("as_of") or ""))
    if year_m:
        out.append(f"  year = {{{year_m.group(1)}}},")
    if record.get("url"):
        out.append(f"  url = {{{_bibtex_escape_url(str(record['url']))}}},")
    notes = []
    if record.get("as_of"):
        notes.append(f"as-of {record['as_of']}")
    if record.get("accessed"):
        notes.append(f"accessed {record['accessed']}")
    if notes:
        out.append(f"  note = {{{'; '.join(notes)}}},")
    out.append("}")
    return "\n".join(out) + "\n"


def _ensure_bibliography(root: Path) -> str | None:
    """Ensure a TOP-LEVEL `bibliography: sources.bib` line in _quarto.yml.

    Critic-1 finding 1: Quarto reads bibliography as a top-level document
    option — nested under `project:` it is silently ignored and every
    [@key] renders as literal text. Single idempotent line-append only;
    the file is never rewritten. Returns an error string or None.
    """
    yml = root / "_quarto.yml"
    if not yml.is_file():
        return "project has no _quarto.yml — cannot wire bibliography"
    text = yml.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line[:1].isspace():
            continue  # nested key: not ours, never touch it
        if line.strip().startswith("bibliography:"):
            return None  # top-level entry already present
    if text and not text.endswith("\n"):
        text += "\n"
    yml.write_text(text + "bibliography: sources.bib\n", encoding="utf-8")
    return None


@_E._section_op_errors
def register_source(project: str, key: str, kind: str, title: str,
                    date: str | None = None, url: str | None = None,
                    publisher: str | None = None, accessed: str | None = None,
                    as_of: str | None = None,
                    overwrite: bool = False) -> dict:
    """Register a citable source: persist record, rewrite sources.bib, wire yml.

    Check-then-write runs under the project lock. Registry writes bump
    registry_version (render inputs change) but never content revision.
    """
    root, err = _E._project_root_or_error(project)
    if err:
        return err
    assert root is not None
    with _E._project_lock(root):
        manifest, err = _E._load_or_import(root)
        if err:
            return err
        assert manifest is not None
        record: dict = {"key": key, "kind": kind, "title": title}
        for opt_key, opt_val in (("date", date), ("url", url),
                                 ("publisher", publisher),
                                 ("accessed", accessed), ("as_of", as_of)):
            if opt_val is not None:
                record[opt_key] = opt_val
        ok, verr = manifest_mod.validate_source(record)
        if not ok:
            return {"ok": False, "error": verr}
        if key in manifest.sources and not overwrite:
            existing = manifest.sources[key].get("title", "")
            return {"ok": False,
                    "error": f"source {key!r} already registered "
                             f"(title: {existing!r}); pass overwrite=True to replace"}
        manifest.sources[key] = record
        manifest.registry_version += 1
        # F1: wire the yml BEFORE touching sources.bib — a missing _quarto.yml
        # must fail with zero drift (no updated-but-unregistered bib on disk).
        yml_err = _ensure_bibliography(root)
        if yml_err is not None:
            return {"ok": False, "error": yml_err}
        bib = "".join(_source_to_bibtex(manifest.sources[k])
                      for k in sorted(manifest.sources))
        try:
            (root / "sources.bib").write_text(bib, encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "error": f"sources.bib write failed: {exc}"}
        manifest_mod.save(manifest, str(root))
        return {"ok": True, "report_id": manifest.report_id, "key": key,
                "bib_path": "sources.bib",
                "registry_version": manifest.registry_version}


def _check_registry_links(manifest, source_keys: list, fact_ids: list) -> str | None:
    """Dangling-link check shared by exhibit/fact registration (loud names)."""
    if not isinstance(source_keys, list) or not isinstance(fact_ids, list):
        return "source_keys and fact_ids must be lists of id strings"
    for sk in source_keys:
        if sk not in manifest.sources:
            return f"unknown source key: {sk!r} — register it first"
    for fid in fact_ids:
        if fid not in manifest.facts:
            return f"unknown fact id: {fid!r} — register it first"
    return None


def _exhibit_anchors(root: Path) -> set[str]:
    """Figure-anchor short ids ({#fig-<id>}) currently present in index.qmd."""
    try:
        text = (root / "index.qmd").read_text(encoding="utf-8")
    except OSError:
        return set()
    return set(_E._FIGANCHOR_RE.findall(text))


def _register_exhibit_locked(root: Path, manifest, exhibit_id: str,
                             title: str, file: str | None,
                             source_keys: list, fact_ids: list,
                             as_of: str | None, alt: str | None,
                             overwrite: bool) -> dict:
    """Record logic for register_exhibit; caller holds the project lock."""
    record: dict = {"id": exhibit_id, "title": title, "file": file,
                    "source_keys": list(source_keys),
                    "fact_ids": list(fact_ids)}
    if as_of is not None:
        record["as_of"] = as_of
    if alt is not None:
        record["alt"] = alt
    ok, verr = manifest_mod.validate_exhibit(record)
    if not ok:
        return {"ok": False, "error": verr}
    link_err = _check_registry_links(manifest, source_keys, fact_ids)
    if link_err is not None:
        return {"ok": False, "error": link_err}
    # Grounding (B-3): the id must match a live {#fig-} anchor, or the file
    # must exist under the project root. One of the two — never neither.
    short = exhibit_id[4:] if exhibit_id.startswith("fig-") else exhibit_id
    grounded = short in _exhibit_anchors(root)
    rel_file: str | None = None
    if file is not None:
        target = (root / file.strip().lstrip("/")).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError:
            return {"ok": False, "error": f"exhibit file escapes the project root: {file}"}
        if not target.is_file():
            return {"ok": False, "error": f"exhibit file not found in project: {file}"}
        grounded = True
        rel_file = str(target.relative_to(root.resolve()))
    if not grounded:
        return {"ok": False,
                "error": f"exhibit {exhibit_id!r} is ungrounded: no {{#fig-{short}}} "
                         "anchor in index.qmd and no existing file — pass file= or add the anchor"}
    record["file"] = rel_file  # normalized project-relative, or None
    if exhibit_id in manifest.exhibits and not overwrite:
        return {"ok": False,
                "error": f"exhibit {exhibit_id!r} already registered; "
                         "pass overwrite=True to replace"}
    manifest.exhibits[exhibit_id] = record
    manifest.registry_version += 1
    return {"ok": True, "exhibit_id": exhibit_id,
            "registry_version": manifest.registry_version}


@_E._section_op_errors
def register_exhibit(project: str, exhibit_id: str, title: str,
                     file: str | None = None,
                     source_keys: list[str] | None = None,
                     fact_ids: list[str] | None = None,
                     as_of: str | None = None, alt: str | None = None,
                     overwrite: bool = False) -> dict:
    """Register an exhibit record: figure file or anchor linked to evidence.

    Check-then-write runs under the project lock. Bumps registry_version,
    never content revision.
    """
    root, err = _E._project_root_or_error(project)
    if err:
        return err
    assert root is not None
    with _E._project_lock(root):
        manifest, err = _E._load_or_import(root)
        if err:
            return err
        assert manifest is not None
        res = _register_exhibit_locked(
            root, manifest, exhibit_id, title, file,
            source_keys or [], fact_ids or [], as_of, alt, overwrite)
        if not res.get("ok"):
            return res
        manifest_mod.save(manifest, str(root))
        return {"ok": True, "report_id": manifest.report_id, **res}


def _register_fact_locked(manifest, fact_id: str, value, unit: str,
                          kind: str, source_keys: list,
                          as_of: str | None, note: str,
                          overwrite: bool) -> dict:
    """Record logic shared by register_fact (create) and overwrite-replace."""
    record: dict = {"id": fact_id, "value": value, "unit": unit,
                    "kind": kind, "source_keys": list(source_keys),
                    "history": []}
    if as_of is not None:
        record["as_of"] = as_of
    if note:
        record["note"] = note
    ok, verr = manifest_mod.validate_fact(record)
    if not ok:
        return {"ok": False, "error": verr}
    link_err = _check_registry_links(manifest, source_keys, [])
    if link_err is not None:
        return {"ok": False, "error": link_err}
    if fact_id in manifest.facts and not overwrite:
        return {"ok": False,
                "error": f"fact {fact_id!r} already registered; "
                         "pass overwrite=True to replace or use update_fact"}
    if fact_id in manifest.facts:
        # Overwrite replaces the record but preserves its update history.
        record["history"] = manifest.facts[fact_id].get("history", [])
    manifest.facts[fact_id] = record
    manifest.registry_version += 1
    return {"ok": True, "fact_id": fact_id,
            "illustrative": kind == "illustrative",
            "registry_version": manifest.registry_version}


@_E._section_op_errors
def register_fact(project: str, fact_id: str, value, unit: str = "",
                  kind: str = "observed",
                  source_keys: list[str] | None = None,
                  as_of: str | None = None, note: str = "",
                  overwrite: bool = False) -> dict:
    """Register a shared typed quantity (observed/calculated/estimated/illustrative).

    Illustrative registrations are flagged in the response; the readiness
    half of the flag is EVID-COVER-ILLUSTRATIVE (B-6). Bumps
    registry_version, never content revision.
    """
    root, err = _E._project_root_or_error(project)
    if err:
        return err
    assert root is not None
    with _E._project_lock(root):
        manifest, err = _E._load_or_import(root)
        if err:
            return err
        assert manifest is not None
        res = _register_fact_locked(
            manifest, fact_id, value, unit, kind, source_keys or [],
            as_of, note, overwrite)
        if not res.get("ok"):
            return res
        manifest_mod.save(manifest, str(root))
        return {"ok": True, "report_id": manifest.report_id, **res}


@_E._section_op_errors
def update_fact(project: str, fact_id: str, value=None, unit=None,
                kind: str | None = None, source_keys=None,
                as_of: str | None = None, note: str | None = None) -> dict:
    """Update a fact record, keeping superseded values in capped history."""
    root, err = _E._project_root_or_error(project)
    if err:
        return err
    assert root is not None
    with _E._project_lock(root):
        manifest, err = _E._load_or_import(root)
        if err:
            return err
        assert manifest is not None
        if fact_id not in manifest.facts:
            return {"ok": False, "error": f"unknown fact id: {fact_id!r}"}
        old = manifest.facts[fact_id]
        # F2: detect the no-op BEFORE touching history — an update that
        # changes no field must not pollute history or invalidate approvals.
        new_value = old["value"] if value is None else value
        new_unit = old.get("unit", "") if unit is None else unit
        new_kind = old.get("kind", "") if kind is None else kind
        new_links = old.get("source_keys", []) if source_keys is None else list(source_keys)
        new_asof = old.get("as_of") if as_of is None else as_of
        new_note = old.get("note", "") if note is None else note
        if (new_value == old.get("value") and new_unit == old.get("unit", "")
                and new_kind == old.get("kind", "")
                and new_links == old.get("source_keys", [])
                and new_asof == old.get("as_of") and new_note == old.get("note", "")):
            return {"ok": True, "report_id": manifest.report_id,
                    "fact_id": fact_id, "value": old.get("value"),
                    "illustrative": old.get("kind") == "illustrative",
                    "changed": False,
                    "registry_version": manifest.registry_version}
        record = dict(old)
        history = list(record.get("history", []))
        # R2-F2: stamp WHEN — without it the rollforward account can say
        # what changed but never when.
        history.append({"value": old["value"], "unit": old.get("unit", ""),
                        "kind": old.get("kind", ""),
                        "superseded_by": new_value,
                        "at": datetime.now().astimezone().isoformat()})
        del history[:-_E.FACT_HISTORY_CAP]
        record["history"] = history
        record["value"] = new_value
        record["unit"] = new_unit
        record["kind"] = new_kind
        record["source_keys"] = new_links
        if as_of is not None:
            record["as_of"] = as_of
        if note is not None:
            record["note"] = note
        ok, verr = manifest_mod.validate_fact(record)
        if not ok:
            return {"ok": False, "error": verr}
        link_err = _check_registry_links(
            manifest, record.get("source_keys", []), [])
        if link_err is not None:
            return {"ok": False, "error": link_err}
        manifest.facts[fact_id] = record
        manifest.registry_version += 1
        manifest_mod.save(manifest, str(root))
        return {"ok": True, "report_id": manifest.report_id,
                "fact_id": fact_id, "value": new_value,
                "illustrative": record.get("kind") == "illustrative",
                "changed": True,
                "registry_version": manifest.registry_version}


def _parse_asof(value) -> date | None:
    """ISO-8601 date prefix or None.

    R2-F1: as_of is free-form and optional, so lexicographic compare is
    wrong ('2026-7-1' < '2026-10-30' is False). Unparseable/missing
    vintage is NEVER silently fresh — callers bucket it as unknown.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


