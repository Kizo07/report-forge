# Milestone A — Phase 0 contracts

Status: v1 for review in #research (Tasks 0.1 + 0.2). Line-check pass 2026-09-06 fixed §1.4 state-reset wording, §2.1 append param semantics, §2.5 tool list. King commits; coders implement only what is written here. Anything marked OPEN is a coder/`#quant` decision to batch, not a contract change.

Sources of truth for these contracts:

- Plan: `~/.hermes/plans/2026-09-06-reportforge-milestone-a.md` (Tasks 0.1/0.2)
- Product review: `docs/product-architecture-review-2026-09-06.md` §6.1, §7 (RF-01/02/04/05/06/07), §8 Milestone A, §9
- Repo: `src/reportforge/engine.py`, `src/reportforge/mcp_server.py` (12 tools), `docs/flagship-rules.md`
- Baseline: 118 tests green; no commit/push by researchers.

Milestone A goal (review §8): an agent can resume a report, change one section, know the new revision, inspect its output, and deliver those exact artifacts — without a second authoritative copy of any prose in JSON.

---

## 1. Manifest schema (`report.json`) — Task 0.1 / RF-01

### 1.1 File and identity

- Every scaffolded report directory gets `report.json` at its root, beside `index.qmd`.
- `report.json` is metadata and index only. **Prose never lives in the manifest** — `index.qmd` is the sole source of truth for document content. The manifest's section index is a rebuildable projection of the QMD (see §1.5).
- File scope: Milestone A keeps the file-first architecture — no database, no new service.

### 1.2 Fields

```jsonc
{
  "schema_version": 1,
  "report_id": "amzn-12m-flagship",       // == project dir name == slug; immutable after scaffold
  "title": "AMZN 12-Month Outlook",
  "brief": "One-paragraph statement of the report's question and audience",
  "profile": {
    "report_type": "earnings-recap",       // genre: standard|memo|earnings-recap|sector-outlook|thematic-deepdive|macro-outlook|quant-factor-brief|technical-brief|esg-sustainability|crypto-digital|desk-synthesis|whitepaper|studio-editorial|bespoke
    "brand": "quantflow",                  // brand identity: "quantflow" (default) | "neutral"
    "theme": "light",                      // light | dark
    "layout": "magazine",                  // magazine | single-column | chartbook | compact
    "output_profile": "editorial",         // editorial (typst pdf + responsive html + docx) | web (html + pdf-web) | editable-docx
    "policy": "flagship"                   // general | flagship | draft
  },
  "revision": 7,
  "state": "draft",                        // draft | review | approved | exported
  "sections": [
    {"id": "s-exec-summary", "title": "Executive summary", "level": 2, "line_start": 42}
  ],
  "formats": ["html", "pdf", "docx"],
  "created": "2026-09-06T18:04:11-05:00",
  "updated": "2026-09-06T21:33:02-05:00"
}
```

Field rules:

- `schema_version` (int, currently `1`): bump only when a field is added/removed/renamed. Loaders accept the current version; on higher versions return a loud `ok:false` ("manifest written by newer schema") — never guess.
- `report_id` (string): directory name at creation time. Immutable: renaming a directory is out of scope for Milestone A.
- `profile.*` derives from the scaffolded `reportforge-template` frontmatter value + `_quarto.yml` (formats) at scaffold/import time. The dimensions follow the review's §3.2 decomposition (type/brand/theme/layout/output-profile/policy); Milestone A populates them as constants derived from the one template selector — it does NOT add a second template system. The full profile matrix is RF-08 (Milestone C).
- `sections[].line_start` is the 1-based line number in `index.qmd` where the section's first heading line starts. It is advisory for humans/debugging; ops address sections by `id`, never by line number.
- `formats`: subset of `["html", "pdf", "docx", "pdf-web"]` — the manifest echoes the configured render formats; changing it is a scaffold/config edit, not a manifest edit.
- `created`/`updated`: ISO-8601 with local offset, rewritten on every manifest save.

### 1.3 Revision semantics

- `revision` starts at 1.
- Any successful content-changing operation bumps +1: section replace/move/delete, section append (unless idempotent no-op), `write_report_body`, manual-edit reconciliation that changes the QMD, or asset/figure writes that the manifest tracks.
- Read-only operations NEVER bump: `get_section`, `project_status`, readiness, preview, import, render (renders produce artifacts, not prose).
- Render does not bump `revision` — it writes `.reportforge-state.json` (unchanged behavior) plus the artifact/revision binding in §5.
- `expected_revision` mismatch NEVER bumps (a rejected op changes nothing).

### 1.4 State machine and transitions

States: `draft`, `review`, `approved`, `exported`.

Allowed transitions (from → to; anything not listed is illegal and returns `ok:false` naming the current state):

| From | To | Trigger | Who may trigger |
| --- | --- | --- | --- |
| draft | review | author marks the revision ready for review (readiness run, human or agent request) | agent or human |
| review | draft | reviewer requests changes | reviewer (human) or agent acting on recorded review feedback |
| review | approved | reviewer accepts the revision (replaces today's ad-hoc "looks good" in chat) | human reviewer only |
| approved | exported | `export_release` succeeds | agent or human (system records it) |
| approved | review | changes requested after approval — revision bumped | human reviewer |
| exported | review | new prose change on an exported report | any agent/human edit; export of the new revision requires re-approval |

Rules:

- Only `export_release` may set `exported`, and only from `approved`. `draft → exported` is illegal (plan Task 1.1 Step 1 asserts exactly this).
- A revision bump on a report whose `state != draft` resets `state` to `draft` — an edit reopens the workflow (this subsumes the `exported → review` row: new prose on an exported report reopens review, and exporting that new revision requires re-approval). No transition removes the `revision_log`; a report re-entering `draft` still answers "what changed since revision N" from §2.2.
- Reviewer authority (human-only `review → approved`) is contract, not enforcement: the engine accepts the call from any caller; who is entitled to call it is the workflow's rule. Coder note: acceptance evidence (a review record) is required to approve — see §4.3.

### 1.5 Manual-edit reconciliation (the anti-duplication rule)

The manifest is a projection; it must never become a competing copy of the document. Review §8: "Do not introduce a second authoritative copy of every paragraph in JSON."

- On every manifest read (`load`), rebuild the section index from `index.qmd` headings; if the rebuilt index differs from the stored one (heading added/removed/moved/renamed by hand, or section byte-ranges shifted), the engine repairs the stored index and bumps `revision` +1 (an edit is an edit, whoever made it). `line_start` values are refreshed; `id`s are preserved and re-matched by heading text.
- Content-addressed headings: a section `id` is derived from the heading text, slugified (`s-` + lowercase, hyphens, alphanumerics, e.g. `s-exec-summary`), and **stable across moves**; renames of a heading change the id — that is the collision-free rule, accepted because `id`s are for agents, humans edit by prose.
- Manifest writes are atomic: write temp file + `os.replace` (crash-safe; no torn manifest).
- Import path for pre-manifest report dirs (e.g. `aapl-12m-flagship`): `import_dir(project)` scans `index.qmd` headings into the section index, derives `profile`/`formats` from frontmatter/`_quarto.yml`, sets `revision = 1`, `state = draft`, `created` = directory mtime, `updated` = now. Import NEVER rewrites `index.qmd`; existing `reports/` workbench dirs are untouched (review §9).

### 1.6 API surface (Task 1.1/1.2)

- `reportforge.manifest`: `load(root) -> Manifest`, `save(manifest)`, `bump(manifest, reason)`, `transition(manifest, to_state, actor, note)`; dataclass `Manifest` with the §1.2 fields.
- `scaffold_report` writes a fresh `report.json` (revision 1, state draft, sections from the starter body).
- `project_status` / `open_report(project)` return, in addition to today's keys, the manifest view: `report_id`, `title`, `brief`, `profile`, `revision`, `state`, `sections`, plus `missing_work` (readiness summary per §4.2) and `artifacts` (relative-path artifact descriptors, §3.2 shape, for the current revision's rendered outputs).

---

## 2. Section operations — Task 0.2 / RF-02

### 2.1 Operations

Four operations on `index.qmd`, addressed by stable section `id` (§1.5):

| Op | Request | Effect on QMD |
| --- | --- | --- |
| get_section | `project`, `section_id` | returns the section's markdown, its heading level, and byte range |
| replace_section | `project`, `section_id`, `markdown`, `expected_revision` | heading + body of that section replaced wholesale; every other byte of the file is preserved |
| move_section | `project`, `section_id`, `before_section_id` \| `to_end`, `expected_revision` | section block moves; headings and bodies move as one unit |
| delete_section | `project`, `section_id`, `expected_revision` | section block removed |
| append_section (existing tool, extended) | `project`, `markdown`, `before` (unchanged substring match; keeps current behavior), plus new `before_section_id` (exact §1.5 id), `idempotency_key` | unchanged insertion behavior + idempotency (§2.4) |

- A "section" = its heading line + all lines up to (not including) the next heading of level <= its own. Same-level and deeper headings belong to the section; shallower ones do not. The document title block (frontmatter) is not a section.
- `get_section` is read-only, no `expected_revision`, no bump.
- All mutating ops are single-transaction: read QMD → transform in memory → atomic write + manifest save (revision bump + section index rebuild) in one call. A failed op leaves both files untouched.
- Preserve unrelated bytes: a targeted edit must leave unrelated sections byte-identical (plan Task 1.3 verify bullet). The manifest's `updated` changes; the QMD outside the edited range does not.

### 2.2 `expected_revision` — optimistic concurrency

- Every mutating op takes `expected_revision: int`.
- Pass `expected_revision == manifest.revision` to succeed.
- On mismatch, the op does nothing and returns:

```jsonc
{
  "ok": false,
  "error": "stale revision",
  "stale_revision": true,
  "current_revision": 7,
  "changed_sections": [
    {"id": "s-risks", "title": "Risks", "event": "replaced", "revision": 7}
  ],
  "hint": "re-read the section, re-apply your change on top of revision 7"
}
```

- `changed_sections` lists the section-level events since the caller's revision: `added` / `replaced` / `moved` / `deleted` with the revision of each event, sourced from the manifest's revision log (§2.3). Bounded to the last 50 events; overflow adds `events_truncated: true`.
- Rationale (review §5.3): client retries and concurrent agents are normal workflow conditions; a stale write must fail loudly with enough context to re-apply, never clobber.

### 2.3 Revision log

The manifest carries a `revision_log` array (append-only, capped: keep last 50 entries) of `{revision, timestamp, actor, op, section_id, summary}`. `actor` is free text ("agent:deerflow", "human:fire", "tool:replace_section"). This is structure metadata, not prose — allowed in JSON.

### 2.4 Idempotency (append)

- `append_section` accepts an optional `idempotency_key` (string, caller-chosen).
- First append with key K: inserts and records `(K -> {revision, section_id})` in the manifest's idempotency ledger.
- Repeat append with the same K within the report's lifetime: **no-op**, returns `ok:true, idempotent_replay: true`, plus the original call's `revision` and `section_id`. Nothing is inserted; the revision is NOT bumped again.
- Key scope is the report (ledger persisted in the manifest, capped at 500 entries; oldest evicted). A key never expires while the report exists.
- Without `idempotency_key`, append behaves exactly as today (never a no-op).

### 2.5 MCP tools and error shape

- New tools: `reportforge_get_section`, `reportforge_replace_section`, `reportforge_move_section`, `reportforge_delete_section` (plan Task 1.3), and `reportforge_append_section` gains `idempotency_key`.
- Tool params are explicit (`project: str`, `section_id: str`, ...). No inference of project from "most recently modified" for these tools — explicit handles only (review §5.3).
- Errors: all section ops return `{ok:false, error, ...context}`; no exceptions cross the MCP boundary.
- CLI parity is Task 1.7 (later); contracts here are the MCP/engine layer.

---

## 3. Export bundle — Task 0.2 / RF-06

### 3.1 Layout

```
bundle/
  <report_id>/
    r<rev>/                       # e.g. r7 — revision-scoped, self-contained
      manifest.json               # copy of report.json at export time
      bundle.json                 # descriptor index (§3.2)
      index.pdf
      index.html
      index.docx
      assets/                     # optional: reference doc, images, etc. (opt-in)
      source/                     # optional: index.qmd + config (opt-in)
      data/                       # optional: registered datasets (opt-in)
      previews/                   # contact sheet + page PNGs (§5), when produced
```

- Destination root (`bundle/`) is caller-supplied (`export_release(project, revision, dest)`); the layout under it is this contract.
- `bundle/<report_id>/r<rev>/` is immutable once written: re-export of the same revision overwrites atomically (temp dir + rename), never appends. New revision ⇒ new `r<N>` dir.
- Export requires `state == approved` (§1.4). Exporting a draft is illegal — re-render is not gated, publication is.

### 3.2 Artifact descriptors

`bundle.json` (and the API response) lists artifacts as **relative paths only**:

```jsonc
{
  "schema_version": 1,
  "report_id": "amzn-12m-flagship",
  "revision": 7,
  "exported_at": "2026-09-06T21:40:00-05:00",
  "artifacts": [
    {"id": "pdf", "path": "index.pdf", "bytes": 482133, "sha256": "…", "mime": "application/pdf", "role": "deliverable"},
    {"id": "html", "path": "index.html", "bytes": 921102, "sha256": "…", "mime": "text/html", "role": "deliverable"},
    {"id": "docx", "path": "index.docx", "bytes": 38112, "sha256": "…", "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "role": "deliverable"},
    {"id": "manifest-copy", "path": "manifest.json", "bytes": 1201, "sha256": "…", "role": "metadata"},
    {"id": "contact-sheet", "path": "previews/contact-sheet.png", "bytes": 881233, "sha256": "…", "mime": "image/png", "role": "preview"}
  ],
  "includes": {"source": false, "data": false},
  "delivery": {"adapters": ["local-bundle", "deerflow"], "present_paths": []}
}
```

Rules:

- `artifacts[].id` is the stable handle (`pdf`, `html`, `docx`, `manifest-copy`, `contact-sheet`, `page-<n>`, `exhibit-<fig-id>`, `source`, `data-<name>`); `artifacts[].path` is relative to the `r<rev>` bundle root and must resolve identically for the generic client and the DeerFlow adapter — both retrieve the same bytes. Host absolute paths NEVER appear in descriptors or API responses (review RF-05/RF-06).
- `sha256` + `bytes` are recorded for every artifact; a client can verify what it received.
- Source (`index.qmd`, config, styles) and `data/` inclusion is **opt-in** (`include_source`, `include_data` flags on `export_release`); deliverables + manifest are always included. HTML bundles note whether they are self-contained (`embed-resources`) or expect adjacent `*_files/` dirs — the descriptor lists those dirs as artifacts too (review §6.6).
- Back-compat: `publish_report` (DeerFlow bridge) keeps its current behavior and response shape; `export_release` is the new client-neutral path on top of the same rendered artifacts. The DeerFlow adapter resolves bundle descriptors into `present_paths`.

### 3.3 Response

`export_release` returns: `{ok, report_id, revision, state, bundle_root (relative under dest), artifacts (the §3.2 list), next_step}`. Failure returns `{ok:false, error}` — including "not approved" with the current state named.

---

## 4. Readiness — Task 0.2 / RF-04

### 4.1 Categories and checks

`check_readiness(project)` returns one issue list per category. Milestone A implements the **automated** checks below; anything not implementable by script is listed as "requires editorial review" without a pass/fail.

| Category | Automated checks (Milestone A) | Deferred (listed, not computed) |
| --- | --- | --- |
| structure | mandatory sections present for the template (per-template required-heading list; missing = issue); heading levels well-ordered | section-depth sanity |
| evidence coverage | illustrative-content markers (never silently passed) + Milestone B registry linkage: 8 EVID-* codes over sources/exhibits/facts registries (see §8) | source quality, claim support, caption-number↔fact linkage |
| numerical consistency | heuristic pattern scans: metric strings on the cover (verdict/metrics) vs numbers appearing in tables — mismatch patterns flagged for human confirmation; #quant refines the heuristics (plan Task 1.4) | full fact checking |
| presentation | `charts/*.png` all referenced in the QMD (unreferenced chart = issue); zero dangling `@fig-` crossrefs (pdftotext grep on rendered PDF where applicable); `scripts/figure_lint.py` result surfaced as-is; `engine_charts_only` violations (reuses `_engine_charts_violation`) | label legibility, accessibility conformance |
| editorial review | whether a review record exists for the current revision (§4.3) and whether any recorded issue is unresolved | the actual judgment — human only |

Issue shape: `{category, severity: error|warning|info, code, message, section_id?, detail?}`. Category summary: `{pass: bool, issues: [...]}`. Top level: `{ok, report_id, revision, categories: {...}, ready_for_review: bool}` where `ready_for_review` = zero `error`-severity issues.

Non-goals (explicit): readiness does NOT verify factual accuracy, source quality, or financial claims (review §3.6). A style gate is not evidence verification, and the response says so.

### 4.2 `missing_work`

`project_status`/`open_report` surface `missing_work`: a compact projection of readiness — mandatory sections missing, artifacts not yet rendered for configured formats, and error-severity issue count per category.

### 4.3 `record_review`

`record_review(project, revision, reviewer, decision, comments?, section_id?)` appends to `reviews` in the manifest (capped at 100): `{revision, timestamp, reviewer, decision: changes_requested|approved, comments, section_id?}`. `review → approved` (§1.4) requires an `approved` review record for the current revision.

---

## 5. Preview artifacts — Task 0.2 / RF-05

### 5.1 Artifacts

`render_preview(project, revision)` →

| id | content | produced by |
| --- | --- | --- |
| `contact-sheet` | grid of all pages, one PNG | `pdftoppm` tile of rendered PDF |
| `page-<n>` | single page at readable resolution, PNG | `pdftoppm -f n -l n` |
| `exhibit-<fig-id>` | one exhibit's PNG from `charts/` (the chart file itself) | direct file descriptor |

- Previews bind to `(report_id, revision)`: generated only from that revision's rendered PDF; a re-render at the same revision replaces them, a new revision invalidates them.
- Stored under `<project>/output/previews/r<rev>/` and returned as relative-path artifact descriptors (same shape as §3.2) — never host absolute paths in responses.
- `pdftoppm` availability is a preflight dependency (`scripts/preflight_env.sh`); its absence is a loud `ok:false`, not a silent skip.
- Requires a rendered PDF for that revision; no auto-render inside `render_preview`.

---

## 6. Capability discovery — Task 0.2 / RF-07 slice

`reportforge_capabilities()` (MCP tool + `reportforge capabilities` CLI) returns:

```jsonc
{
  "schema_version": 1,
  "server": "reportforge",
  "templates": [/* list_templates() entries, unchanged */],
  "profiles": {
    "report_types": ["standard", "memo", "earnings-recap", "..."],   // == template genres
    "brands": ["quantflow", "neutral"],
    "themes": ["light", "dark"],
    "layouts": ["magazine", "single-column", "chartbook", "compact"],
    "output_profiles": ["editorial", "web", "editable-docx"]
  },
  "support_matrix": [
    {"report_type": "earnings-recap", "template": "earnings-recap", "formats": ["html", "pdf", "docx"],
     "exhibit_labels": true, "toc": false, "content_neutral": false}
  ],
  "execution": {"run_code": true, "run_file": true, "interpreter": "reportforge venv", "disabled_reason": null},
  "preview": {"supported": true, "backend": "pdftoppm", "available": true, "artifact_ids": ["contact-sheet", "page-<n>", "exhibit-<fig-id>"]},
  "delivery": {"methods": ["local-bundle", "deerflow-thread-outputs"], "requires_env": ["DEERFLOW_THREAD_OUTPUTS_HOST (deerflow only)"]},
  "sections": {"ops": ["get", "replace", "move", "delete", "append"], "optimistic_concurrency": true, "idempotent_append": true},
  "manifest": {"schema_version": 1, "states": ["draft", "review", "approved", "exported"]},
  "tools": [/* the 12 existing + new tool names */],
  "docs": {"flagship_rules": "docs/flagship-rules.md", "contracts": "docs/milestone-a-contracts.md", "journeys": "docs/agent-journeys.md"}
}
```

- `support_matrix` is derived from `list_templates()` — one row per template; Milestone A does not add a second template system (the type×brand×theme decomposition is RF-08).
- `execution.available == false` when `REPORTFORGE_EXEC=off` (with `disabled_reason`); `preview.available == false` when `pdftoppm` is missing. Both must reflect the live environment, not hardcoded true.

## 8. Milestone B — evidence registry (RF-03) + coverage deepening (RF-04)

### 8.1 Registry maps (`report.json`, schema 2)

`sources` (keyed by citekey), `exhibits` (keyed by `fig-<id>`), `facts`
(keyed by `fact-<slug>`), plus `registry_version: int` (0 for pre-B files).
Schema bumped 1 → 2: pre-B loaders fail loudly on B manifests instead of
silently wiping the registries on load-reconcile. Record shapes are
validated on load (`ManifestError` on hand-edited garbage — never silent).

- source: `key` (`src-<slug>`, reserved namespace), `kind` ∈ filing /
  article / dataset / price-feed / transcript / report / other, `title`,
  `date` or `as_of`, optional `url` (stored verbatim, never fetched),
  `publisher`, `accessed`.
- exhibit: `id` (`fig-<id>`, reuses a figure anchor), `title`,
  `file` (project-relative path or null when anchor-grounded),
  `source_keys[]`, `fact_ids[]`, optional `as_of`, `alt`.
- fact: `id` (`fact-<slug>`), `value` (numeric or string), `unit`,
  `kind` ∈ observed / calculated / estimated / illustrative (required),
  `source_keys[]`, optional `as_of`, `note`, `history[]` (capped at 20).

Registry writes bump `registry_version` (they change render inputs:
`sources.bib`, `_quarto.yml`) but never content `revision`. Preview/review
bindings record the version they were made at and warn on mismatch.

### 8.2 Registration tools

`reportforge_register_source` (persists + rewrites `sources.bib` + ensures
one TOP-LEVEL `bibliography: sources.bib` line in `_quarto.yml` — never
nested under `project:`, where Quarto silently ignores it),
`reportforge_register_exhibit` (id must match a live `{#fig-}` anchor or
`file` must exist under the project root; re-register needs
`overwrite=True`), `reportforge_register_fact` / `reportforge_update_fact`
(overwrite preserves history). All three check-then-write under the project
lock; dangling source/fact links fail loudly naming the missing key.
`save_chart` with a project anchors output into `figures/` (explicit
in-project absolute paths honored; sandbox paths translated as before),
pre-validates links before writing, and auto-registers the exhibit
(`fig-<stem>`, re-saves inherit existing links).

### 8.3 Coverage codes (`evidence` category)

Scanner rules: fenced code blocks stripped before scanning (error-severity
FPs would block release); cite scan = every `@src-<key>` occurrence in any
bracket style (bracketed, compound `[@a; @b]`, suppress-author `[-@k]`,
bare in-text); exhibit scan = `@fig-` refs AND `{#fig-}` embed definitions;
`fig-/tbl-/sec-/eq-` crossref prefixes are never citekeys. Cover matching:
`target`, `scenarios[].value`, `metrics[].value` normalized to floats
(tolerance 1e-6 relative); ranges and non-numerics unchecked; unit-blind by
design with the matched fact id named in the issue.

| Code | Severity | Fires when | Rationale |
| --- | --- | --- | --- |
| EVID-UNREGISTERED-CITE | error | cited `@src-` key with no record | mechanically unambiguous; renders broken |
| EVID-EXHIBIT-UNREGISTERED | error | `@fig-` ref or `{#fig-}` embed with no record | same unambiguity as cites |
| EVID-EXHIBIT-FILE-MISSING | error | record with `file` set but absent from disk (`file: null` never fires) | deliverable points at nothing |
| EVID-EXHIBIT-ANCHOR-MISSING | warning | anchor-grounded record whose anchor left the QMD | drift signal, not breakage |
| EVID-COVER-UNLINKED | warning | cover numeric with no equal-value fact | pragmatic for B (no legacy report passes an error gate); Milestone C auto-derivation promotes it to error |
| EVID-COVER-ILLUSTRATIVE | warning | matched cover fact has kind=illustrative | thesis on illustrative data must not be silent |
| EVID-MISSING-REQUIRED | error | genre's required kind neither registered nor cited (presence alone never satisfies) | the §7 headline outcome |
| EVID-NO-REQUIRED-LIST | info | genre has no REQUIRED_EVIDENCE entry (bespoke, studio, portfolio-*, ledger-*) | honest branch, mirrors STRUCT-NO-REQUIRED-LIST |

Per-genre `REQUIRED_EVIDENCE` (≤3 requirements each; content-neutral genres
omitted by design): standard/memo (any cited source), whitepaper (thesis
evidence + background), earnings-recap (filing/transcript + market reaction),
sector-outlook (prices + fundamentals), thematic-deepdive (theme data +
research), macro-outlook (macro series), quant-factor-brief (price data +
factor research), technical-brief (market data), esg-sustainability (ESG
data + controversy coverage), crypto-digital (market data),
desk-synthesis (desk inputs), modern (signal evidence).

### 8.4 Honest deferrals (Milestone B explicitly does NOT)

- Caption attribution (source/as-of rendered under a figure) is an
  editorial convention: records store the data, nothing renders it.
- Caption-number↔fact value linkage: record granularity satisfies §8's
  "captions to their records" for B.
- Verdict prose numerics: policed by UNREGISTERED-CITE + the numerics pass,
  not by cover linkage (structured target/scenarios/metrics only).
- Source-quality judgment stays editorial/human (review §7 note); no URL
  metadata fetching (local-first, no network in the registry path).

---

## 7. Coder acknowledgment

Coders implement Tasks 1.1–1.7 against this doc. Ack in #research with questions batched in one post; disputes go to @hermes. Changes to this doc after ack require a new post in #research (contract v1.1+), not silent drift.

