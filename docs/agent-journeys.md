# Agent journeys (Milestone A)

Four CLI-only walkthroughs. Every step works without MCP; the MCP tool name
follows in parentheses. Reports live under `REPORTFORGE_REPORTS_DIR`
(default `reports/`); scratch work belongs in `/tmp`, never in `reports/`.

## 1. Create

```bash
reportforge capabilities                      # templates × profiles × outputs
reportforge new amzn-brief --template earnings-recap --formats html,pdf
reportforge status amzn-brief                 # manifest view: revision 1, draft
```

MCP: `reportforge_capabilities`, `reportforge_scaffold_report`,
`reportforge_project_status`. Scaffold writes `report.json` (revision 1,
draft) beside `index.qmd`.

## 2. Revise (one section, no full rewrite)

```bash
reportforge open amzn-brief                   # section ids + current revision
# read the section first (MCP reportforge_get_section), then:
# MCP reportforge_replace_section project section_id markdown expected_revision
```

Mutating section ops take `expected_revision`: a stale revision fails with
`changed_sections` context — re-read, re-apply, never clobber. Appends accept
`idempotency_key`; repeats are no-op replays. Whole-document rewrites stay
available via `write_report_body`.

## 3. Resume later

```bash
reportforge open amzn-brief                   # brief, profile, sections, revision, state
reportforge readiness amzn-brief              # what is missing / unsupported
reportforge preview amzn-brief                # contact sheet + pages (needs rendered PDF)
```

`open` answers "what is this report and where did I leave it" in one call.
`readiness` lists mandatory sections, missing assets, illustrative content,
unsupported evidence links, style issues, and review status. Drafts render
freely; only reviewed revisions release.

## 4. Deliver

```bash
reportforge readiness amzn-brief              # ready_for_review must be true
# record a review (MCP reportforge_record_review), approve, then:
reportforge export amzn-brief ./bundle --include-source
```

Export requires state `approved` and writes
`./bundle/<report_id>/r<rev>/` with deliverables, `manifest.json`,
`bundle.json` (relative-path descriptors with sha256), optional `source/` +
`data/`. The DeerFlow adapter resolves the same descriptors.

## Fresh-agent checklist

1. `capabilities` → pick template/profile/output.
2. `new` → write/append sections → `render`.
3. `readiness` → fix errors → review → `export`.
4. Never invent section ids; never hand-edit `report.json` (it is rebuilt
   from `index.qmd` on read).
