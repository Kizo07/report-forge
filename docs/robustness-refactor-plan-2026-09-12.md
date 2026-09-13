# Report Forge: robustness refactor plan — templates, engine, renderer boundary

Date: 2026-09-12 (rev 2 — post muse review, same day)
Repository: report-forge
Baseline: `08be8c4` (flagship-rules: .column-page class on figures)
Scope: structural refactor only. No stack migration, no behavior change, no new templates, no agent/LLM features.

Revision history:
- rev 1 (2026-09-12): initial draft.
- rev 2 (2026-09-12): muse review verdict `REQUEST-CHANGES`; all 5 blocking findings, 5 major findings, and nits incorporated. Corrections: toolchain stays out of the manifest (state file + release record instead, per `test_versions.py:58`); subprocess inventory corrected to 10 sites (Chromium and pandoc sites added); Phase 2 rescored to 10 template families + 9 domain bodies (ledger families included); explicit test-coupling strategy (monkeypatch retargeting, private re-export list, `test_versions.py` hash migration); `render_report` stage list corrected to the real 260-line pipeline; probe starts warn-only; Phase 2 now depends on Phase 1; numeric tolerances and named seeded breakages added; effort re-estimated ~2×.

Related reading:
- `docs/product-architecture-review-2026-09-06.md` (product-level review; its "retain Quarto" conclusion is assumed, not re-litigated here)
- QuantFlow fork boundary decisions (2026-09-12 session): report-forge stays a deterministic, LLM-free publishing engine; QuantFlow owns all agent/research functionality.

## 1. Goal

Reduce robustness risk and make extension cheap by fixing the three structural liabilities identified in the 2026-09-12 architecture review:

1. `src/reportforge/templates.py` — 5,902 lines of inline Python string constants.
2. `src/reportforge/engine.py` — 4,978 lines, 150 top-level functions, mixing ~6 unrelated concerns.
3. The **renderer boundary** — ten scattered `subprocess.run` sites calling quarto/chromium/pandoc/ipykernel/poppler/interpreters with ad-hoc error handling and no version discipline.

Non-goals (explicitly deferred, with their own trigger conditions):
- Versioned report-brief/manifest contract between QuantFlow and report-forge (next milestone after this one; depends on Phases 1–3 being in place).
- Single-sourcing chart-identity tokens shared with `alpha_engine` (drift risk is real but orthogonal; can proceed in parallel).
- Direct Typst (`typst-py`) PDF adapter. The Phase 1 seam exists precisely so this becomes a bounded addition *if* Quarto's documented Typst gaps (image sizing, full-width floats) ever block a concrete layout.

## 2. Current state and risks

### 2.1 templates.py — all template assets as Python strings

Every template asset lives in one module as a string constant:

- Shared scaffolding: `QUARTO_YML`, `BRAND_YML`, `STYLES_SCSS`.
- Bodies: `INDEX_QMD`, `MEMO_QMD`, `WHITEPAPER_QMD`, `MODERN_QMD`, `STUDIO_QMD`.
- Typst partials: `WHITEPAPER_TYPT_TEMPLATE`, `MODERN_TYPT_TEMPLATE`, `STUDIO_TYPT_TEMPLATE`, `PORTFOLIO_LIGHT_TYPT_TEMPLATE`, `PORTFOLIO_DARK_TYPT_TEMPLATE`, `LEDGER_DARK_TYPT_TEMPLATE` (`templates.py:4087`), `LEDGER_LIGHT_TYPT_TEMPLATE` (`templates.py:4996`).
- Per-template config/show-table/SCSS fragments: `*_TYPT_SHOW`, `*_STYLES_EXTRA`, `*_BRAND_YML`, `MODERN_YML`, `STUDIO_YML`, `STUDIO_HTML_HEADER`, `BESPOKE_YML`, etc.

The module serves **19 registered templates** (`list_templates`, `engine.py:77-98`): 8 base families + 9 domain briefs (`templates_domain.py`) + 2 derived ledger families (ledger-dark/light). The ledger constants are themselves generated: their headers read "derived; see `scripts/derive_ledger_templates.py`", which derives them from the portfolio constants by palette+font token swap.

Consequences (risks R1–R5):

- **R1 — No tooling on the most-changed artifacts.** The Typst partials are the files most likely to need iteration and debugging, but as Python strings they get no syntax checking, no `typst` preview, no editor support, no formatter. Every mistake surfaces only at render time, inside a Quarto error message.
- **R2 — Opaque diffs and review.** A one-character Typst change appears in git as a Python string edit with escaped quoting; blame and review of template logic is noisy. The commit history shows this friction (multiple `fix(template): …` and `fix(palettes): …` commits).
- **R3 — Measured duplication: 5 near-copy Typst bodies.** Studio, portfolio-light, portfolio-dark, ledger-dark, ledger-light share one structural body; studio vs portfolio-light alone differ by 113 diff lines — including the Typst entry-point name (`#let studio(` vs `#let portfolio_light(`), font stacks, and link-ink handling — not just a palette. Three of the five are hand-edited copies; two are script-derived. A structural fix must be applied five times or regenerated and re-checked.
- **R4 — Code that writes code.** `scripts/derive_ledger_templates.py` (218 lines) generates Python string constants into `templates.py`. Generating constants is a workaround for the constants not being first-class files; it adds a second authoring format and a second failure surface, and its `--check` mode has no CI consumer, so derived-vs-source staleness is currently unenforced.
- **R5 — Fragile authoring mechanics.** The constants are plain and raw triple-quoted strings (zero f-strings, zero `.format(`) rendered at scaffold time through Jinja with report-forge's custom delimiters — `<%`/`%>`, `<%%`, `<##` (`_tpl`, `engine.py:43-53`). The risk is not the templating mechanism but the host medium: brace-heavy Typst/CSS embedded in Python strings is easy to corrupt when editing, and no editor tooling understands the embedded Jinja-in-Python combination.

### 2.2 engine.py — monolith of mixed concerns

4,978 lines, 150 top-level functions, at least six distinct responsibilities:

| Concern | Examples in engine.py |
| --- | --- |
| Scaffolding | `scaffold_report`, profile/template matrix validation |
| Render + release | `render_report` (260 lines, `engine.py:851-1105`), `freeze_release`, `rollforward` |
| Chart pipeline | `save_chart`, `save_asset`, `_apply_quantflow_plotly_template`, exhibit slugging/anchoring |
| Quality gates | `_run_figure_lint` (`engine.py:3298`), `_engine_charts_violation`, `_white_paper_charts` |
| Identity tokens | `tokens_for`, `tokens_for_keys` (duplicated from alpha_engine — drift risk, see non-goals) |
| Previews + inspection | `render_preview` (~`engine.py:4400-4540`), `_render_pdf_web` (`engine.py:4655`), `_pdf_page_count`, `open_report`, manifest views |
| Code execution | `run_code`, `run_file` (py/sh/R), `_ensure_reportforge_kernel` |
| Machine wiring | `_venv_python`, kernel `--user` install |

Consequences (risks E1–E5):

- **E1 — Blast radius.** Two-thirds of all commits (52 of 79: 45 touching engine.py, 19 templates.py) land in the same files; merge conflicts and regressions compound.
- **E2 — `render_report` is a pipeline in one function, and its real stages are not what a naive reading suggests.** Actual behavior (`engine.py:851-1105`, 260 lines): resolve project/template → pre-render `engine_charts_only` gate → release-seal snapshot → env pinning (`QUARTO_PYTHON`, OTEL vars, `engine.py:873-886`) → per-format `quarto render` with missing-output checks (`engine.py:987-994`) → optional pdf-web branch via headless Chromium (`engine.py:1013`) → release record + state-file toolchain stamp (`engine.py:1055-1096`). It never runs the figure lint (that is `check_readiness`, `engine.py:3285-3306`) and never generates previews (that is `render_preview`, ~`engine.py:4400-4540`) — those are separate entry points the Phase 3 split must also give owners (`_render_pdf_web`, `_quarto_tools_dir`, `_declares_typst_format` included).
- **E3 — Ten scattered, ad-hoc external process calls.** Each with individually invented timeouts and error contracts:

  | Site | Tool | Purpose |
  | --- | --- | --- |
  | `engine.py:678` | `quarto --version` | version probe |
  | `engine.py:841` | venv python + `ipykernel install --user` | kernel registration |
  | `engine.py:960` | `quarto render <src> --to <fmt>` | main render |
  | `engine.py:1602` | venv python `-c <code>` | `run_code` |
  | `engine.py:1671` | py/sh/R interpreter | `run_file` |
  | `engine.py:3298` | `sys.executable scripts/figure_lint.py` | lint gate |
  | `engine.py:4479` | `pdftoppm` | preview pages |
  | `engine.py:4549` | `pdfinfo` | page counts |
  | `engine.py:4681` | headless Chromium `--print-to-pdf` | pdf-web format (`_render_pdf_web`) |
  | `engine.py:4973` | `pandoc --print-default-data-file reference.docx` | DOCX reference doc (`_default_reference_docx`) |

- **E4 — Silent degradation on machine wiring.** `_quarto_version()` returns `None` when Quarto is missing; `_ensure_reportforge_kernel()` falls back to `"python3"` (surfaced only later via the scaffold's `jupyter_kernel` field). Both convert environment problems into downstream misbehavior rather than loud, early failures.
- **E5 — Test coupling.** 24 test files (~5,446 lines) exercise engine internals directly, in three specific ways that any refactor must handle deliberately: (a) tests monkeypatch `engine.subprocess.run` itself (`tests/test_engine.py:152`, `tests/test_flexibility.py:315,339,402,425,453`, `tests/test_preview.py:96` ff.) — moving subprocess into `renderer/` breaks every such test; (b) tests import private names the facade must therefore re-export: `engine._engine_charts_violation`, `engine._profile_for_template`, `engine._venv_python`, `engine._PORTFOLIO_TO_QUANTFLOW_TEMPLATE`, `engine._apply_quantflow_plotly_template`, `engine._tpl`, `engine._project_is_light`, `engine._source_to_bibtex`; (c) `tests/test_versions.py:16-20` hashes the literal filenames `templates.py`/`templates_domain.py` — Phase 2 breaks this by design and must migrate it, not preserve it.
- **E6 — Environment baseline is not pinned.** The repo `.venv` currently lacks `pytest`; a green-suite claim requires a pinned dev environment first (muse observed 298 tests passing under a patched invocation with unrelated missing-dependency collection errors excluded).

### 2.3 Renderer boundary — no seam, no version discipline

- **B1 — Upgrades are silent breaks.** Templates depend on Quarto stock-Typst behavior (the "vendored typst partials" workaround exists precisely because the stock path did not deliver the promised title page). Quarto and Typst both move fast; Quarto's own docs acknowledge Typst-support limitations (image sizing; missing appendices/full-width floats without custom template functions). Nothing records which toolchain versions a template family is *known to work with*, and there is no per-render probe.
- **B2 — No swap point.** Adding a direct-Typst PDF path, or changing how `pdf-web` is produced, means editing `render_report` internals. There is no interface to implement.
- **B3 — Inconsistent error contracts and timeouts.** Some sites raise, some return `{"ok": False, "error": …}` dicts, some return sentinels (`-1` page count). `QUARTO_TIMEOUT_S = 900` (`engine.py:35`) is shared by the Quarto render *and* the Chromium print (`engine.py:4681`) — a hung browser tab blocks a render slot for 15 minutes.
- **B4 — Optional-tool ambiguity.** Poppler (`pdftoppm`, `pdfinfo`) and Chromium are probed with `shutil.which`/env-var at call time; missing tools degrade previews/page counts/pdf-web in ways discovered far from the cause. `scripts/preflight_env.sh` exists but is not enforced by the engine.

## 3. Target shape (this refactor)

Three internal layers, no public API change:

```
CLI / MCP server (unchanged imports)
  -> engine facade (thin, re-exports public API + the 8 test-imported privates)
       -> scaffold / render / release / charts / gates / tokens / preview / exec modules
       -> renderer seam (the ONLY package doing subprocess calls)
            -> quarto | chromium (pdf-web) | pandoc (reference.docx)
               | kernel/exec interpreters | poppler | lint
  -> templates/<family>/ asset directories (real .typ/.qmd/.scss/.yml files,
     copied into projects; ledger families derived file-to-file from portfolio)
```

## 4. Phased plan

### Phase 0 — Baseline and safety net (1–2 days)

> **Pinned environment (recorded 2026-09-12):** CPython 3.14.7, uv-managed repo `.venv` (rebuilt in place after the original symlinked-interpreter venv stopped resolving its own site-packages). Dev/runtime deps: project `-e .` plus `pytest`, `pillow`, `statsmodels`, `pyarrow`. Baseline: **`pytest -q` → 373 passed, 0 failed** (~70 s). Tools on PATH: quarto, pandoc, pdftoppm/pdfinfo (poppler), chromium. All parity/ink baselines and stamps recorded with this toolchain.

1. **Pin the test environment.** Add `pytest` (and any test-only deps) as dev requirements installed into the repo `.venv`; record the baseline suite result in this doc (target: full suite green in the pinned env — muse observed 298 passing once unrelated missing-dependency collection errors are excluded; the refactor must not start from an unpinned "mostly green"). **Done 2026-09-12: 373 passed / 0 failed.**
2. **Extend the existing toolchain stamp — do NOT touch the manifest.** The manifest is deliberately render-blind: toolchain lives in `.reportforge-state.json` and the release record (`engine.py:1081-1085`, stamped at `engine.py:930-934`; `tests/test_versions.py:58` asserts `"toolchain" not in manifest` — this invariant is §1.3 of the state design and must survive). Extend that existing state/release toolchain block with `pandoc`, `typst` (via quarto), and poppler versions/presence.
3. **Preflight enforcement.** Extend `scripts/preflight_env.sh` to report every external tool the engine can invoke: `quarto`, `pandoc`, `ipykernel`, `pdftoppm`, `pdfinfo`, Chromium (`REPORTFORGE_CHROMIUM` or discovered). Convert absent-required-tools into hard scaffold/render errors instead of silent fallbacks (the kernel fallback stays but is reported via the scaffold's `jupyter_kernel` field — fixes E4).
4. **Render snapshots.** One committed reference project per **scaffold family (10: standard, memo, whitepaper, modern, studio, portfolio-light, portfolio-dark, ledger-light, ledger-dark, bespoke)** — record page counts + `scripts/page_ink.py` ink signatures as the parity baseline. **Pin the poppler raster version** used for baselines (`page_ink` thresholds were calibrated on a single 14-page document, `scripts/page_ink.py:15-17`, and depend on the poppler raster output).
5. **Wire `derive_ledger_templates.py --check` into the Phase 0 gate** (and later CI) so derived-staleness is enforced from here on.
6. **Seeded-failure drill:** verify the gate catches three named breakages — quarto absent from PATH, poppler absent, kernel registration failing.

**Acceptance:** every render's state file names its full toolchain; snapshots exist for 10 families on a pinned poppler; preflight catches all three seeded breakages; `--check` runs in the gate; pinned env documented.

### Phase 1 — Renderer seam (1–2 days + a mechanical test patch)

1. New package `src/reportforge/renderer/`:
   - `toolchain.py` — discovery + version queries (moves `_quarto_version`, `_venv_python`, `_ensure_reportforge_kernel`, `_chromium_binary`, poppler/pandoc probes). Also the home for the moved `_default_reference_docx` pandoc call (`engine.py:4973`).
   - `quarto.py` — `render(source, fmt, workdir, timeout)`, `version()`, and the pdf-web Chromium print (moved `_render_pdf_web`, `engine.py:4655-4681`).
   - `errors.py` — one `RendererError` hierarchy; every site converts failures into it; callers keep their existing dict contracts at the API edge (translation in the facade, not the seam).
   - `probe.py` — per-family compatibility probe of required toolchain ranges. **Starts warn-only** (logs into the render result), flips to enforcing after one full snapshot cycle proves the ranges (B1; avoids introducing a new render failure mode before any evidence exists).
   - Timeouts become per-tool: split `QUARTO_TIMEOUT_S` so the Chromium print no longer inherits 900 s (suggest: quarto render 900 s unchanged, chromium print 120 s, pandoc 60 s as today, poppler 120 s) — fixes the B3 timeout-sharing bug as a side effect of the move.
2. Move all **ten** `subprocess.run` sites (inventory in §2.2/E3) into the package. No logic changes, no output changes.
3. **Test migration is explicit and mechanical, not "tests unchanged":** in the same PR, retarget the `monkeypatch.setattr(engine.subprocess, "run", …)` sites in `tests/test_engine.py`, `tests/test_flexibility.py`, and `tests/test_preview.py` to the renderer module they exercise (each is a one-line path change; ~10 sites total). `engine.py` ends the phase with no `subprocess` import of its own.

**Acceptance:** `grep -rn "subprocess" src/reportforge --include="*.py"` matches only `src/reportforge/renderer/`; full pinned suite green including the retargeted tests; a deliberate Quarto-down run surfaces a `RendererError`-derived message in `render_report`'s output dict; probe results appear (warn-only) in the render result.

### Phase 2 — templates.py → asset directories (4–7 days, incl. spike)

0. **Pre-Phase-2 overlay spike (blocking).** Studio vs portfolio-light differ by 113 lines *including the Typst entry-point name, font stacks, and link-ink handling* — the palette is not the whole delta (R3). Spike: parameterize one body over {entry-point name, fonts, palette, link-ink} and prove a portfolio-light render **byte-comparable** (same toolchain) to the family's Phase 0 snapshot. **Fallback if the spike fails:** keep five per-family body files and dedupe only the palette/font tokens; do not force the overlay.
1. Create `src/reportforge/templates/<family>/` per family — real files: `_quarto.yml`, `brand.yml`, `index.qmd`, `styles.scss`, `typst/*.typ` partials (show-table fragments as their own files), `HEADER.html` where applicable. **Ten scaffold families**, extracted one family per PR, simplest first: memo → standard → whitepaper → modern → studio → portfolio-light → portfolio-dark → ledger-light → ledger-dark → bespoke.
2. Domain briefs (`templates_domain.py`, 9 bodies) get the same treatment under `templates/domains/<name>/`.
3. **Before the first portfolio/ledger PR:** rewrite `scripts/derive_ledger_templates.py` as a file-to-file generator over the new asset layout (its palette+font swap logic survives; the Python-constant emission does not). Its `--check` mode, already wired into the Phase 0 gate, now enforces asset staleness.
4. Loader module (`templates/load.py`) reads assets, computes an integrity hash, and exposes the same data `scaffold_report` consumes today. `template_version()` (`engine.py:658-670`) switches to a **directory hash**, and `tests/test_versions.py:16-20` is migrated from filename hashes to the directory hash in the same PR (a deliberate, designed break — not an accident).
5. Add a per-family scaffold snapshot test (scaffold → hash the produced tree) to catch accidental asset edits.
6. Packaging check before merging: confirm the hatchling wheel config ships the non-Python asset files (`packages = ["src/reportforge"]` + include rules for `*.typ/*.qmd/*.scss/*.yml`), verified by installing the built wheel into a scratch venv and scaffolding from it.
7. Extract, delete the corresponding constants each time; at the end **delete `templates.py`** (now achievable: all 19 templates' assets are accounted for).

**Parity gate per family PR (mechanical):** rendered page counts equal to the Phase 0 baseline; per-page ink signatures within **±2 % relative** of baseline, on the **pinned poppler version**; scaffold tree hash test green. A human visual pass of the family's flagship render is recorded in the PR description as a secondary check (explicitly not the gate).

**Acceptance:** `templates.py` gone; 10 families + 9 domain bodies as assets; generator file-to-file with `--check` enforced; all parity gates green against Phase 0.

### Phase 3 — split engine.py (2–4 days)

1. Mechanical extraction into a package, moving whole functions with `git mv`-style commits to preserve blame: `scaffold.py`, `render.py`, `release.py`, `charts.py`, `gates.py`, `tokens.py`, `preview.py`, `exec_env.py`. The split assigns explicit owners to everything §2.2/E2 names: the render pipeline stages, `_render_pdf_web`/`_quarto_tools_dir`/`_declares_typst_format`, `check_readiness`'s lint stage, and `render_preview`.
2. `render.py` restructures `render_report` into the **real** stage sequence: resolve → charts-gate → seal → env-pin → per-format render (+missing-output checks) → pdf-web branch → release record + state stamp. Each stage becomes a named, separately callable function; `render_report` remains the same public composition (lint and previews stay in their own entry points, `check_readiness` and `render_preview`).
3. `engine.py` remains a facade re-exporting the current public names **plus the eight test-imported privates** listed in E5(b), so `mcp_server.py`, `cli.py`, and the 24 test files keep importing exactly as before. Any test that is *retargeted* anyway (Phase 1's monkeypatch sites) may import from the new home directly.
4. `render_report`'s body after the split is a linear composition of named stages — the checkable form of this criterion is: **≤ 60 lines**, every statement a stage call or trivial glue.

**Acceptance:** `mcp_server.py` and `cli.py` untouched and green; full pinned suite green; `wc -l` on every module ≤ 1,500; `render_report` body ≤ 60 lines composed of named stages.

### Phase 4 — deferred, explicit triggers (out of scope here)

- **Direct Typst PDF adapter:** implement behind the Phase 1 seam only when a concrete layout is blocked by Quarto's Typst support.
- **Versioned report-brief contract for QuantFlow:** next milestone; requires Phases 1–3 landed so the contract sits on clean layers.
- **Shared identity tokens with alpha_engine:** parallel track; not blocked by anything here.

## 5. Risks of the refactor itself

| Risk | Mitigation |
| --- | --- |
| Template extraction changes rendered output | Parity gate is mechanical: equal page counts + ink signatures within ±2 % relative on pinned poppler + scaffold tree hashes; one family per PR keeps diffs reviewable |
| Regression in a family nobody rendered recently | Phase 0 snapshot set covers all 10 families before any extraction |
| Test-suite breakage during engine split | Facade re-exports public API + the eight named privates; monkeypatch sites retargeted mechanically in Phase 1's PR; `test_versions.py` hash migration is planned, not incidental |
| Renderer error-contract change breaks MCP consumers | Seam returns rich errors internally; the public dict contract is translated at the facade and covered by `test_mcp_server.py` |
| Overlay mechanism can't reproduce portfolio output byte-comparably | Pre-Phase-2 spike with explicit fallback (five per-family bodies, palette-only dedupe) |
| Derived assets drift | Generator rewritten file-to-file before portfolio/ledger PRs; `--check` enforced in the gate from Phase 0 |
| Probe fails closed on unevidenced ranges | Probe ships warn-only; enforcing only after one snapshot cycle |
| Loader hash feeds the release seal — silent re-sealing | Phase 2 depends on Phase 1's seal semantics; note it in the loader PR; expect one intentional re-seal, documented |
| Wheel ships without asset files | Packaging verification step (scratch venv install) is part of Phase 2's merge checklist |
| POSIX-only assumptions surface during moves | Pre-existing: `import fcntl` (`engine.py:6`, lock at `engine.py:1823-1845`) and `":"`-joined PATH entries (`engine.py:878,886`). Declare POSIX-only support in the README during Phase 1 rather than silently assuming; do not fix Windows here |
| Encoding bugs during extraction | Pre-existing `read_text()/write_text()` calls without `encoding=` (`engine.py:103,115,334,362,913`, among others). All newly moved/loader code passes `encoding="utf-8"`; opportunistic fix allowed in moved functions only |
| Jinja `<%`-delimited asset files get mangled by formatters | Add formatter/linter exclusions (`.prettierignore`/editor config) for `templates/**` asset files in Phase 2's first PR |
| Timeout regressions | Per-tool timeouts land with the Phase 1 move (chromium 120 s, quarto 900 s, pandoc 60 s, poppler 120 s) |

## 6. Whole-effort acceptance criteria

1. `templates.py` no longer exists; assets for all 19 registered templates (10 scaffold families + 9 domain briefs) are real files under `src/reportforge/templates/`, with per-family scaffold snapshot tests and a file-to-file derive generator whose `--check` is gate-enforced.
2. `grep -rn "subprocess" src/reportforge --include="*.py"` matches only `src/reportforge/renderer/`; a warn-capable compatibility probe runs on every render and its result (plus the extended toolchain block) lands in the state file and release record — **never in the manifest** (`test_versions.py:58` stays green, unmodified).
3. `engine.py` is a thin facade re-exporting public API + the eight named privates; every module ≤ 1,500 lines; `render_report` body ≤ 60 lines of named stages.
4. All 10 reference projects render with page counts equal to and ink signatures within ±2 % relative of the Phase 0 baseline on the pinned poppler; the full pinned suite is green, including the retargeted monkeypatch tests.
5. No public API (CLI flags, MCP tool names/signatures) changed — verified by `test_cli.py` + `test_mcp_server.py` untouched and green.

## 7. Milestone log

| Milestone | Verdict | Notes |
| --- | --- | --- |
| Phase 0 (commit `cb6126c`) | — | Pinned env: CPython 3.14.7 venv rebuilt (original symlinked-interpreter venv broke); baseline 373 passed. Plan wording note (A-review N7): the parity metric actually recorded is a grayscale per-page ink fraction at 50 dpi (near-white threshold 245), not page_ink.py's gap/balance stats. |
| Phases 0+1 (muse review A) | APPROVE-WITH-NITS | M1 error contract completed (QuartoNotFoundError from run_quarto; RendererError→dict translation at the facade), M2 probe tests, M3 freeze_release stamp, M4 which() routed through seam, M5 in-suite subprocess-confinement test, M6/N1/N2/N3/N5/N8 adopted. M6 noted: PDF-ink parity does not cover HTML-only assets — Phase 2's scaffold-tree hash tests are the backstop. Overlay spike result: studio vs portfolio-light differ by 68/303 changed lines (comments, entry-point name, palette block) — an overlay spec would need 68 pinned replacements; **fallback selected per plan §4 Phase 2.0**: per-family bodies stay standalone, palette/token dedupe via shared files only. |
| Phase 2 (single extraction commit) | pending review | Plan deviation, recorded: families were extracted in ONE commit rather than one-family-per-PR — solo execution, and the byte-exactness contract was enforced mechanically instead (loader values verified byte-identical to the old constants before the swap; scaffold-tree hash gate + full 10-family RF_PARITY render gate green). Overlay spike: 68/303 changed lines → fallback selected (per-family bodies). Derive generator rewritten file-to-file; stale-detection test migrated to the asset model. Wheel packaging verified via scratch-venv install + scaffold. |
| Phase 3 (muse review C: APPROVE-WITH-NITS) | done | Review verdict on the split: mechanically sound — 146/147 blocks byte-identical, facade surface 200/200 names, stub propagation proven live, stage fidelity line-checked. Fixes applied: parity input gate date-normalized on both sides (the gate would have expired nightly), import-order dependency documented + decorator-chain guard test, stage-call path documented, state-stage docstring corrected. Final: 402 passed, 10 skipped; RF_PARITY 10/10. | engine.py (4,978 lines) → package `reportforge/engine/`: `_impl` (core, 1,054) + 11 clusters (scaffold 608, readiness 1,002, sections 458, registry 377, release 420, status 314, preview 241, charts 235, exec_env 176, cover 149, publish 121) + generated facade `__init__`. Split done by an AST-verified tool (`scripts/split_engine.py`): bodies move verbatim; only exact Name-node positions get the `_E.` deferred-package prefix, so the 7 test-stubbed globals + REPORTS_DIR keep monkeypatch semantics (69 patch sites green). render_report recomposed into 9 named stages, body 46 lines. Full suite 401 passed + full RF_PARITY 10/10. Stage functions (`_render_resolve_source`…`_render_state_stage`) are callable via `reportforge.engine._impl` — the supported path; the facade deliberately re-exports the pre-split surface only. Facade import order (generated): `sections` precedes `registry`/`release`/`cover` — cross-module decorators (`@_E._section_op_errors`) bind at import time; do not reorder. |

## 8. Sequencing summary

| Phase | Depends on | Effort | Risk |
| --- | --- | --- | --- |
| 0 — Baseline & safety net | — | 1–2 days | Low |
| 1 — Renderer seam | 0 | 1–2 days (+1 PR-scope test patch) | Low |
| 2 — Templates → assets | **1** (seal semantics; loader hash re-seals) + overlay spike | 4–7 days | Medium (visual parity, overlay spike) |
| 3 — Engine split | 1 | 2–4 days | Low–Medium (mechanical) |
| 4 — Deferred items | 1–3 | trigger-based | — |

Phases 2 and 3 both require Phase 1 and are independent of each other, but Phase 2 is deliberately sequenced after Phase 1: the asset-loader's directory hash feeds `template_version()`, which feeds the Phase 1 release seal — landing the loader first means exactly one intentional, documented re-seal instead of two.
