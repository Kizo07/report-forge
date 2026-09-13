"""Engine cover cluster (Phase 3 split; see plan §4).

All engine-level references go through `_E` (deferred package
attribute access) so monkeypatching `reportforge.engine.<name>`
keeps working.
"""

from __future__ import annotations

from reportforge import engine as _E

import json
import re
from reportforge import manifest as manifest_mod



def _cover_field_fact_id(path: str) -> str:
    """Default fact id for a cover path (explicit mapping overrides)."""
    slug = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")
    return f"fact-{slug or 'cover'}"


def _yaml_cover_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    return json.dumps(str(value), ensure_ascii=False)


@_E._section_op_errors
def derive_cover(project: str, mapping: dict | None = None) -> dict:
    """Bind cover numerics to fact records, writing values into frontmatter.

    mapping: {cover path: fact id} for paths target, scenarios[i].value,
    metrics[i].value. Unmapped paths fall back to the fact-<field>
    convention (e.g. target → fact-target). A numeric cover field with no
    resolvable fact fails loudly naming the field. Sets cover_derived:
    true (lifts the scenario-weights skip) and bumps the revision — the
    QMD changed, so previews must re-render.
    """
    if mapping is None:
        mapping = {}
    if not isinstance(mapping, dict):
        return {"ok": False, "error": "mapping must be a map of cover path to fact id"}
    root, err = _E._project_root_or_error(project)
    if err:
        return err
    assert root is not None
    with _E._project_lock(root):
        manifest, err = _E._load_or_import(root)
        if err:
            return err
        assert manifest is not None
        try:
            text = (root / "index.qmd").read_text(encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "error": f"cannot read index.qmd: {exc}"}
        front = _E._frontmatter_dict(text)
        # Full field list: derivation binds weights too (R2-F9), so the
        # readiness skip must not hide fields here.
        candidates = _E._cover_numeric_candidates(front, skip_weights=False)
        resolved: dict[str, tuple[str, object]] = {}
        unmapped: list[str] = []
        for field, _number in candidates:
            fid = mapping.get(field) or _cover_field_fact_id(field)
            rec = manifest.facts.get(fid)
            if rec is None:
                unmapped.append(f"{field} (no fact {fid!r})")
            else:
                resolved[field] = (fid, rec.get("value"))
        if unmapped:
            return {
                "ok": False,
                "error": ("cover fields with no fact record: "
                          + "; ".join(unmapped)
                          + " — register the facts (default ids like "
                            "'fact-target') or pass an explicit mapping"),
            }
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            return {"ok": False, "error": "index.qmd has no YAML frontmatter block"}
        close = None
        for i in range(1, len(lines)):
            if lines[i].strip() in ("---", "..."):
                close = i
                break
        if close is None:
            return {"ok": False, "error": "index.qmd frontmatter never closes"}
        top: str | None = None
        idx = -1
        updated: list[str] = []
        derived_from: dict[str, str] = {}
        for i in range(1, close):
            line = lines[i]
            m0 = re.match(r"^([A-Za-z0-9_-]+)\s*:", line)
            if m0:
                key = m0.group(1)
                top = key if key in _E._COVER_BLOCKS else None
                idx = -1
                if key == "target" and "target" in resolved:
                    fid, val = resolved["target"]
                    lines[i] = f"target: {_yaml_cover_scalar(val)}"
                    updated.append("target")
                    derived_from["target"] = fid
                continue
            if top in ("scenarios", "metrics") and re.match(r"^\s+-\s", line):
                idx += 1
                # Review F1: a flow-style item (- {label:.., value:..})
                # cannot be rewritten line-surgically; failing loudly
                # beats silently keeping the hand value.
                if "{" in line.split("-", 1)[1]:
                    path = f"{top}[{idx}].value"
                    if path in resolved:
                        return {
                            "ok": False,
                            "error": (
                                f"cover {top}[{idx}] uses flow-style YAML "
                                "('- {label:.., value:..}'): derive_cover "
                                "only rewrites block-style 'value:' lines — "
                                "rewrite the item in block style, then "
                                "re-run derive_cover"),
                        }
                continue
            mv = re.match(r"^(\s+)value\s*:", line)
            if mv and top in ("scenarios", "metrics") and idx >= 0:
                path = f"{top}[{idx}].value"
                if path in resolved:
                    fid, val = resolved[path]
                    lines[i] = f"{mv.group(1)}value: {_yaml_cover_scalar(val)}"
                    updated.append(path)
                    derived_from[path] = fid
        if not any(re.match(r"^cover_derived\s*:",
                            lines[i]) for i in range(1, close)):
            lines.insert(close, "cover_derived: true")
            close += 1
        try:
            (root / "index.qmd").write_text(
                "\n".join(lines) + ("\n" if text.endswith("\n") else ""),
                encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "error": f"cannot write index.qmd: {exc}"}
        manifest_mod.bump(
            manifest,
            f"derive_cover: bound {len(updated)} cover fields to facts",
            actor="tool:derive_cover")
        manifest_mod.save(manifest, str(root))
        return {"ok": True, "report_id": manifest.report_id,
                "updated": sorted(updated), "derived_from": derived_from,
                "revision": manifest.revision}


