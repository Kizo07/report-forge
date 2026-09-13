"""Report-brief contract, schema `report_brief` v1.

A report brief is the STRUCTURED commissioning document an orchestrator
(e.g. QuantFlow) hands to report-forge: one validated dict that fully
determines a scaffold, replacing ~20 loose tool arguments. This module is
pure — no engine imports — so both sides of the contract can validate
against the same rules.

Versioning (contract §4 of docs/report-brief-v1.md):
- `schema` must be exactly "report_brief" (catches wrong-file accidents).
- `version` must equal SCHEMA_VERSION; older producers are rejected with
  the supported range in the message, newer producers are rejected rather
  than silently reinterpreted.
- Unknown keys are rejected: adding a key is a version bump, not a silent
  extension.
"""

from __future__ import annotations

import re

SCHEMA_NAME = "report_brief"
SCHEMA_VERSION = 1

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# str-valued optional fields, mapped 1:1 onto scaffold_report kwargs.
_STR_FIELDS = (
    "project", "template", "title", "subtitle", "author", "abstract",
    "firm", "confidential_mark", "organization", "eyebrow", "title_layout",
    "verdict", "accent", "frontmatter_yaml", "body", "brief",
)
_LIST_STR_FIELDS = ("formats", "key_points")
_LIST_DICT_FIELDS = ("metrics", "scenarios")
_OTHER_FIELDS = ("engine_charts_only", "profile")

KNOWN_KEYS = (
    {"schema", "version"}
    | set(_STR_FIELDS)
    | set(_LIST_STR_FIELDS)
    | set(_LIST_DICT_FIELDS)
    | set(_OTHER_FIELDS)
)

REQUIRED_KEYS = ("project", "template")


class BriefError(ValueError):
    """A report brief failed contract validation."""


def validate_brief(data) -> tuple[dict | None, list[str]]:
    """Validate a brief payload.

    Returns (normalized_brief, errors) — normalized is None when errors is
    non-empty. All problems are collected, not just the first, so an agent
    can fix the whole brief in one round trip.
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return None, [f"brief must be an object, got {type(data).__name__}"]

    schema = data.get("schema")
    if schema != SCHEMA_NAME:
        errors.append(
            f"schema must be exactly {SCHEMA_NAME!r} (got {schema!r}); "
            "this validator only reads report briefs, not arbitrary dicts")
    version = data.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        errors.append(f"version must be the integer {SCHEMA_VERSION} (got {version!r})")
    elif version != SCHEMA_VERSION:
        errors.append(
            f"unsupported report_brief version {version}; this reportforge "
            f"understands version {SCHEMA_VERSION} only")

    unknown = sorted(set(data) - KNOWN_KEYS)
    if unknown:
        errors.append(
            "unknown key(s): " + ", ".join(unknown)
            + f" — report_brief v{SCHEMA_VERSION} allows: " + ", ".join(sorted(KNOWN_KEYS)))

    for key in REQUIRED_KEYS:
        value = data.get(key)
        if not isinstance(value, str) or not value:
            errors.append(f"missing required key {key!r} (non-empty string)")
    if isinstance(data.get("project"), str) and data["project"] \
            and not SLUG_RE.match(data["project"]):
        errors.append(
            f"project {data['project']!r} is not a valid slug "
            "(lowercase letters/digits/hyphens, starting with a letter or digit)")

    for key in _STR_FIELDS:
        if key in data and not isinstance(data[key], str):
            errors.append(f"{key!r} must be a string (got {type(data[key]).__name__})")
    for key in _LIST_STR_FIELDS:
        value = data.get(key)
        if key in data:
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                errors.append(f"{key!r} must be a list of strings")
    for key in _LIST_DICT_FIELDS:
        value = data.get(key)
        if key in data:
            if (not isinstance(value, list)
                    or not all(isinstance(v, dict) for v in value)):
                errors.append(f"{key!r} must be a list of objects")
    if "engine_charts_only" in data and not isinstance(data["engine_charts_only"], bool):
        errors.append("'engine_charts_only' must be a boolean")
    if "profile" in data and not isinstance(data["profile"], dict):
        errors.append("'profile' must be an object")

    if errors:
        return None, errors

    normalized = {k: v for k, v in data.items() if k not in ("schema", "version")}
    return normalized, []


def parse_brief(data) -> dict:
    """Validate and return the normalized brief; raises BriefError with all
    problems joined when invalid."""
    parsed, errors = validate_brief(data)
    if errors:
        raise BriefError("; ".join(errors))
    return parsed


def brief_to_scaffold_kwargs(parsed: dict) -> dict:
    """Map a normalized brief onto reportforge.engine.scaffold_report kwargs.

    `project` becomes `slug`; `brief` (free text) becomes the manifest
    description via the `brief_description` key handled by the engine —
    everything else is a 1:1 kwarg.
    """
    kwargs: dict = {"slug": parsed["project"], "template": parsed["template"]}
    for key in _STR_FIELDS:
        if key in parsed and key not in ("project", "template", "brief"):
            # `brief` (free text) is commissioning metadata — it is stored
            # whole in the manifest's report_brief record, not a scaffold kwarg.
            kwargs[key] = parsed[key]
    for key in _LIST_STR_FIELDS + _LIST_DICT_FIELDS:
        if key in parsed:
            kwargs[key] = parsed[key]
    if "engine_charts_only" in parsed:
        kwargs["engine_charts_only"] = parsed["engine_charts_only"]
    if "profile" in parsed:
        kwargs["profile"] = parsed["profile"]
    return kwargs
