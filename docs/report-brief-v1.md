# Report Brief Contract — schema `report_brief` v1

Status: **stable** (v1) · Validator: `src/reportforge/brief.py` · Engine entry: `engine.scaffold_from_brief(brief)` · MCP tool: `reportforge_scaffold_from_brief`

## Purpose

The report brief is the structured commissioning document an orchestrator
(QuantFlow) hands to report-forge. One validated dict replaces ~20 loose
tool arguments, and the normalized brief is recorded in the report's
manifest (`report_brief` field, manifest schema 5) so every report
carries its own commissioning record.

## Envelope

```json
{
  "schema": "report_brief",
  "version": 1,
  "project": "nvda-12m-outlook",
  "template": "sector-outlook",
  "title": "NVIDIA — 12-Month Outlook",
  "formats": ["html", "pdf"],
  "cover": { "see cover fields below" },
  "brief": "Commissioned by QuantFlow desk session <id>"
}
```

- `schema` must be exactly `"report_brief"` — catches wrong-payload accidents.
- `version` must be exactly `1`. Producers on other versions are rejected
  with the supported range in the message — never silently reinterpreted.
- Unknown keys are **rejected** (all problems listed at once in `errors`).
  Adding a key is a version bump.

## Fields

| Key | Type | Required | Notes |
| --- | --- | --- | --- |
| `project` | string | ✅ | kebab-case slug (`^[a-z0-9][a-z0-9-]*$`), becomes the directory name |
| `template` | string | ✅ | one of `reportforge_list_templates` names (10 families + 9 domain bodies + bespoke) |
| `title`, `subtitle`, `author`, `abstract`, `firm`, `confidential_mark`, `organization`, `eyebrow`, `title_layout`, `verdict`, `accent`, `frontmatter_yaml`, `body` | string | — | 1:1 with `scaffold_report` kwargs |
| `formats` | list[string] | — | subset of `["html", "pdf", "docx", "pdf-web"]` |
| `metrics` | list[object] | — | cover KPI strip (≤6), e.g. `{"label": "Target", "value": "$300"}` |
| `key_points` | list[string] | — | cover key-point cards (≤4) |
| `scenarios` | list[object] | — | cover scenario strip (exactly 3): `{"label", "value", "detail"}` |
| `engine_charts_only` | bool | — | hard chart gate: refuse fallback (matplotlib/seaborn) exhibits |
| `profile` | object | — | report-type profile axes (report_type/brand/theme/layout/output_profile/policy) |
| `brief` | string | — | free-text commissioning note; stored in the manifest, NOT a scaffold kwarg |

## Semantics

1. **Strict validation, all errors at once.** `scaffold_from_brief` never
   fails on the first problem — `errors` lists everything so an agent can
   fix the brief in one round trip.
2. **Template/format validation stays with the engine.** The brief
   validator checks structure; unknown templates/formats are rejected by
   `scaffold_report` with its normal message.
3. **Commissioning record.** On success the normalized brief (envelope
   stripped) is stored in the manifest's `report_brief` field, and the
   tool result echoes `{"schema": "report_brief", "version": 1}`.
4. **Compatibility.** Manifest schema bumped 4 → 5; schema-4 manifests
   keep loading (`report_brief` defaults to `{}`). Old report-forge
   loaders reading new manifests fail loudly per contract §1.4 — expected.

## Producer checklist (QuantFlow)

- Emit the envelope with `schema`/`version` set; treat `errors` lists as
  the repair loop.
- Template names: fetch `reportforge_list_templates` rather than hardcoding.
- After scaffold, the brief is on file — re-running the same brief is
  idempotent at the manifest level only if the project is new; scaffold
  refuses to clobber existing projects either way.
