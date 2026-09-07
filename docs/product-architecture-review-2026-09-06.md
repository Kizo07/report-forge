# Report Forge: product and architecture review

Date: 2026-09-06  
Repository: `/home/fire/Documents/report-forge`  
Baseline: `992f1b667835f88fb232c39be260d4f87aae00ea`  
Purpose: an actionable product review for the next agent, covering current features, missing capabilities, architectural tradeoffs, and agent operation.

This is a static product assessment. I read the product documentation, public tool interfaces, rendering and template architecture, selected report sources, and three committed showcase images. I consulted current primary documentation for the publishing technologies. I did **not** run the application, render reports, run tests or linters, search for bugs, or verify the financial claims in example reports. References to future acceptance scenarios below describe proposed product behavior; they are not results of tests performed in this review.

“Missing” means no dedicated capability was found in the reviewed Report Forge interfaces and architecture. A capable agent may approximate it with arbitrary code or file editing, and an external orchestrator may already provide part of it. Neither possibility makes it a first-class Report Forge feature. Upstream QuantFlow, DeerFlow, and CAO implementations were outside this review.

## 1. Assessment and recommended direction

**Keep Quarto and the existing Typst PDF work. Prioritize the report workflow around them before adding more templates or replacing the rendering stack.**

Report Forge already has a credible purpose: turning agent-authored analysis into consistently branded research documents. Its strongest product assets are the editorial templates, chart identity, readable report sources, several output formats, and tools that bridge an agent's authoring environment to real deliverable files. The committed examples show a recognizable publishing style. [R1], [R2], [R3], [R9]

The main limitation is that the product understands **files and rendering operations** better than it understands **a report's evidence, sections, revisions, and publication state**. An agent can operate the tools, but must supply much of the production discipline itself. A more capable document renderer would not, by itself, close that gap. [R2], [R4]

Recommended positioning:

> A local-first publishing engine for agents and analysts that turns structured report briefs, evidence, and Markdown into reviewable, reproducible research publications.

Retain QuantFlow as the strongest domain profile. Make the underlying publishing concepts usable for other analytical reports. Avoid expanding immediately into a general office suite or a second agent orchestrator.

The next development cycle should address these priorities:

1. A report manifest and explicit report identity, with stable sections and revision history.
2. A complete agent workflow: discover, compose, inspect, revise, render, review, export.
3. Structured sources, exhibits, and facts, with visible freshness and uncertainty.
4. Separate choices for report type, visual theme, layout density, output format, and publication policy.
5. Portable artifacts and explicit support levels for PDF, HTML, and DOCX.

## 2. What the product currently offers

### 2.1 Existing capability inventory

| Capability | Present today | Product assessment |
| --- | --- | --- |
| Report scaffolding | Creates a report folder with QMD, configuration, branding, styles, and relevant template assets. | A useful unit of ownership and portability. Creation is better supported than the subsequent report lifecycle. |
| General and visual templates | `standard`, `memo`, `whitepaper`, `modern`, `studio`, `portfolio-light`, `portfolio-dark`, `bespoke`. | Enough breadth to establish the product. The choices mix content genre, visual identity, and customization level. |
| Domain starters | `earnings-recap`, `sector-outlook`, `thematic-deepdive`, `macro-outlook`, `quant-factor-brief`, `technical-brief`, `esg-sustainability`, `crypto-digital`, `desk-synthesis`. | Nine useful content outlines already exist. They are starter documents, rather than workflows that verify the required evidence has been supplied. |
| Editorial covers | Hero/compact/minimal title options for editorial templates, organization, eyebrow, accent, up to six metrics, verdict, up to four key points, three scenarios. | Distinctive and easy to scan. The cover schema is tightly shaped around research convictions and bear/base/bull stories. |
| PDF, HTML, DOCX | Quarto-based output; custom Typst partials for the editorial families; reference DOCX for Word output. | Valuable coverage, but each format has a separate presentation mechanism. Export availability should not imply identical design fidelity. |
| Browser-printed PDF | `pdf-web` prints rendered HTML with Chromium; advertised in the `bespoke` template's format list. | A useful alternative for HTML-led compositions. It produces a static snapshot, with interactivity retained in HTML. |
| Exhibits and tables | Native cross-reference conventions, explicit figure widths, showcase table treatment, print columns and spanning figures. | Strong editorial vocabulary, but agents must author much of the syntax and select the layout manually. |
| Charts and assets | Plotly JSON to PNG and interactive HTML; theme matching for portfolio reports; arbitrary text and base64 asset writing. | Flexible ingestion. Assets have filenames and bytes, but little first-class analytical meaning. |
| Computation | Host Python execution; existing Python, shell, and R scripts; captured output and changed-file lists. | Powerful for trusted local agents. This also makes Report Forge a compute environment with operating responsibilities beyond publishing. |
| Editing | Whole-document writing and additive section insertion. | Supports initial composition and expansion. Targeted revisions and coordination remain agent responsibilities. |
| Inspection | File inventory, configured formats, render logs, last-render metadata, bounded text-file reads. | Useful operational visibility. It does not provide a report outline with completeness, review state, or a built-in visual preview. |
| Delivery | Copies output files and companion directories into an explicit destination or DeerFlow thread outputs. | Solves a real host/sandbox handoff problem. The returned presentation workflow is specific to that integration. |
| Quality conventions | Optional chart-style checks within rendering; separate flagship figure/prose linter; written production checklist. | A helpful foundation. Its strongest checks concern publication style, not factual validity or complete report readiness. |

Evidence: template catalog and operations in [R2], MCP descriptions in [R4], styles and format configurations in [R3], domain bodies in [R5], quality conventions in [R6], [R7].

There are **17 registered templates** at this baseline. The README describes the eight general/visual templates, and the older proposal document predates several current domain additions. Future planning should use the current catalog before treating a proposed template as missing. This is a product-discovery concern, not a recommendation to spend the next cycle increasing the template count. [R1], [R2], [R10]

### 2.2 What deserves to be preserved

**Readable, file-based documents.** Markdown and local assets are easy for coding agents to create and for humans to inspect. Reports can be tracked in Git, edited with ordinary tools, and retained independently of a running application. Preserve this property when adding richer metadata. [R2], [R9]

**A recognizable visual system.** The warm-paper and dark examples have consistent headers, typography, table styling, and gold/teal exhibits. This is a meaningful product asset: users receive something that looks like a publication rather than an exported conversation. [R9]

**An actual delivery step.** Returning a render path is often insufficient for an agent operating through a sandbox or chat application. Report Forge explicitly addresses that final handoff. Generalize the mechanism while retaining its convenience. [R2] (`publish_report`), [R4]

**Practical agent ergonomics.** Accepting common list argument representations, returning structured status, preserving full render logs, exposing computation results, and appending sections are useful accommodations to real agent behavior. Build on these instead of forcing every client to become a Quarto expert. [R4]

## 3. Critique of the report experience

### 3.1 The product is strongest for a specific research desk

The evidence supports a finance-oriented publishing engine with a reusable general core. Portfolio themes, conviction covers, desk roles, chart rules, and prose guidance are unusually specific to equity research. Even general writing tools contain detailed desk-style instructions. This specificity helps the current use case, but creates friction when an agent needs a scientific analysis, an operational review, or a customer research report. [R4], [R5], [R6]

Make the domain a selectable profile. A QuantFlow profile should own its vocabulary, cover defaults, evidence expectations, and approved exhibit builders. A general analytical profile should be free to choose different sections, chart libraries, and voice rules. Domain expertise should remain an advantage users opt into.

### 3.2 Template choice conflates independent decisions

An earnings recap is a report type; dark is an appearance; studio is an editorial layout; bespoke is a level of author control. They currently share one template selector. The domain starters use the standard pipeline, while the portfolio choices use the editorial pipeline. An agent wanting a branded dark earnings recap must reconcile those choices itself. [R2] (`list_templates`, `scaffold_report`), [R3], [R5]

Expose independent dimensions:

| Choice | Example values |
| --- | --- |
| Report type | Memo, earnings recap, desk synthesis, thematic research |
| Brand | QuantFlow, neutral, organization-owned profile |
| Theme | Light, dark, economical print |
| Layout | Single-column, magazine, chartbook, compact brief |
| Output profile | Editorial PDF, responsive HTML, editable DOCX |
| Policy | General analytical, QuantFlow flagship, draft |

Do not implement every combination immediately. Publish a supported-combinations matrix and start with the combinations current users need. Preserve existing template names as presets during migration.

### 3.3 The visual identity is ahead of the reading controls

I visually inspected the committed TSLA light cover, light body, and dark body showcase images. The covers establish a clear hierarchy, and the body pages use space efficiently. At the displayed page size, several embedded chart labels and source lines are much smaller than surrounding prose. Dense two-column text also requires sustained reading effort. These are observations about the supplied images, not measurements of every output or accessibility findings. [R9]

The flagship rules optimize explicit width tiers, word counts, and page density. Those are useful production constraints, but they do not establish that an exhibit's important labels are legible at its final placement size. Higher raster resolution alone does not make physically small labels easier to read. [R6], [R7]

Recommended controls:

- Separate full research, executive brief, and chartbook reading modes; reuse the same underlying facts and exhibits.
- Define chart label size in relation to final print placement, alongside export resolution.
- Offer a white-paper print profile and single-column reading profile as explicit choices.
- Let HTML readers enlarge exhibits and obtain the underlying data where permitted.
- Make page targets advisory budgets with explicit overflow decisions. Let the brief specify mandatory material so an agent cannot satisfy a page target by silently omitting it.

### 3.4 Covers summarize the thesis, but need semantic flexibility

The cover provides considerable hierarchy: title, subtitle, abstract, metrics, verdict, key points, and scenarios. These fields can also repeat the same thesis several times. The three-card scenario strip is appropriate for a finance outlook but less natural for a memo with two alternatives or research with four plausible outcomes. Metric and scenario values are display strings, rather than typed quantities connected to a shared fact record. [R2] (`normalization helpers`), [R3] (`STUDIO_HTML_HEADER`), [R9]

Retain the current presets, but add cover compositions tied to reader intent. Derive repeated facts from shared records and let each cover choose which elements to show. Keep three scenarios as a finance preset rather than the universal data model.

### 3.5 Tables need a richer analytical contract

The spreadsheet treatment is useful, and narrow tables suit the existing magazine layout. The instruction to keep tables small, combined with unbreakable print tables, limits wide financial statements, long comparisons, and detailed appendices. These are common analytical needs. [R3], [R4], [R6]

Add semantic table definitions with units, precision, missing-value labels, source notes, and column groups. Support a small number of explicit layout policies: compact in-column, full-width, landscape appendix, and multi-page with repeated headers. Offer CSV/XLSX downloads as companion deliverables where a document table would be unwieldy. Avoid making the agent solve each table as a bespoke layout exercise.

### 3.6 Report completeness and factual confidence are outside the current gates

The flagship gate recognizes chart software tags and visual characteristics; the separate linter checks selected syntax, sizing, prose, and palette conventions. These checks can encourage consistency. They do not establish that a chart came from an approved dataset, that its calculation is correct, or that a claim is supported. A matching palette is evidence about appearance. [R2] (`_engine_charts_violation`), [R7]

Similarly, starter templates contain illustrative numbers, example charts, and prose instructions. These are useful teaching aids, but there is no first-class distinction in the public workflow between demonstration content and a completed research deliverable. [R3], [R5]

Introduce separate readiness categories: structure, evidence coverage, numerical consistency, presentation, and editorial review. Mark illustrative content explicitly. Permit rendering a draft while reserving a publication-ready status for the required checks and reviews. Do not market a style gate as protection against unsupported analysis.

## 4. Is Quarto the right choice?

### 4.1 Recommendation: retain it for the current product

The current need combines narrative, calculations, citations, exhibits, HTML, and printed research. Quarto is a reasonable foundation for that mix. Its Typst route renders QMD to PDF and supports custom formats; Word has its own style-template mechanism; bibliographies and computational parameters already exist upstream. Report Forge can expose those capabilities more effectively without replacing the compiler. [Q1], [Q2], [Q3], [Q4]

The highest-value product improvements identified here—report identity, source records, stable sections, review state, and portable delivery—belong above the renderer. A renderer migration would compete with that work while requiring the existing design system and examples to be re-established.

This is a fit assessment, not a measured performance comparison. No competing renderer was installed or benchmarked.

### 4.2 Distinguish the layers

The present pipeline is approximately:

```text
External agent / research workflow
  -> Report Forge MCP, Python API, or narrower CLI
  -> QMD + YAML + styles + template assets + chart files
  -> Quarto and Pandoc document processing
       -> Typst -> PDF
       -> HTML
       -> DOCX with Word styles
  -> optional Chromium print of HTML -> pdf-web
  -> local/DeerFlow artifact copy
```

Quarto and Typst are complementary here. Report Forge uses both the `pdf` format configured with a Typst engine and the `typst` format with custom partials, depending on template family. Describe that distinction as an internal rendering detail; the user should choose a clear output profile. [R2] (`render_report`), [R3]

### 4.3 Costs and limitations of the present choice

| Tradeoff | Consequence for the product | Recommended response |
| --- | --- | --- |
| Several authoring and presentation layers | Specialized layouts involve QMD/Pandoc conventions, Typst, HTML/CSS, and metadata. Agents currently see many of those details. | Put stable report components above the formats; retain raw QMD for advanced use. |
| Separate output mechanisms | A styled HTML card or custom Typst cover is not automatically a Word layout. | Document format fidelity and supported components, rather than promising identical output. |
| Version-sensitive custom formats | Templates depend on the behavior of the publishing toolchain. | Record compatible toolchain and template versions and make upgrades deliberate. |
| Source-based authoring | Excellent for agents; less convenient for a human who expects to click and revise a page. | Add a review and preview surface before considering a full editor. |
| Static print | Interactive exploration belongs in HTML; a PDF can only preserve a selected state. | Define an explicit static representation for every interactive exhibit. |
| File-oriented publication | Quarto output does not supply Report Forge's missing revision and editorial workflow. | Implement that workflow in Report Forge and integrate with the existing orchestrator. |

Current Quarto documentation supports columns and several layout controls and still documents image-sizing limitations for Typst. The repository's more restrictive authoring rules describe its chosen templates/toolchain; they should not be generalized into permanent limitations of Quarto itself. Likewise, PNG-only chart conventions are a Report Forge workflow choice: current Typst integration supports other static image formats, including SVG. Version compatibility with this checkout remains unassessed. [Q1], [R6]

### 4.4 Alternatives and when they would justify a change

The tradeoff judgments in this table are inferences for this product, not benchmark findings.

| Approach | When it becomes attractive | What Report Forge would take on | Decision now |
| --- | --- | --- | --- |
| Quarto + Typst, current direction | Analytical documents with Markdown authoring and several outputs. | Maintaining a bounded set of format adapters and templates. | **Keep as the default.** |
| Direct Typst document generation | Exact PDF composition becomes the dominant requirement and QMD translation materially obstructs necessary layouts. | A more specialized authoring representation and explicit handling of the other output experiences. | Consider a bounded PDF adapter only after a concrete requirement demonstrates the need. |
| HTML/CSS with browser printing, optionally paged-media tooling | Interactive web research and browser-designed layouts become the primary experience. | Print pagination, static chart states, and an independent DOCX strategy. | Develop the existing `pdf-web` option if demand warrants it; a wholesale rewrite is premature. |
| Direct Pandoc conversion | Most reports become non-executable, relatively simple document conversions. | Recreating whichever Quarto project, execution, and authoring conveniences remain necessary. | Little evident product benefit for the present analytical workflow. |
| DOCX-centered authoring | Human Word editing, tracked changes, and client templates become the core workflow. | Treating Word as a primary editorial representation and defining how changes reach other outputs. | Revisit only if Word collaboration becomes a primary requirement. |

Direct Typst exposes markup and programmable document construction; Pandoc already performs multi-format conversion; Paged.js applies paged-media styling to browser documents. Those facts motivate the alternatives, but do not establish superiority for Report Forge. [Q5], [Q6], [Q7]

Quarto also supports interactive documents, so future interactivity does not automatically require abandoning it. Start by specifying the reader interaction and its static fallback. [Q8]

## 5. Can agents operate it properly?

### 5.1 Yes for supervised report production; incomplete for autonomous publication

**A capable agent has the operations needed to create a report today.** The MCP surface offers template discovery, scaffolding, chart and asset creation, computation, document writing, incremental insertion, rendering, operational inspection, and artifact delivery. It is considerably more useful than a single “render this Markdown” tool. [R4]

**The interface does not yet make a report's complete production state explicit.** The agent still manages the outline, unresolved evidence, repeatable computations, targeted edits, layout assessment, and release decision. Existing reports demonstrate the intended output; static inspection cannot establish reliability across agents or hosts. [R2], [R4], [R9]

| Agent situation | Assessment from the available interface |
| --- | --- |
| Coding agent with host filesystem and suitable preview tools | Best fit. It can use the high-level tools and directly inspect or edit project files when necessary. |
| MCP-only agent with Report Forge's execution tools enabled | Broadly capable, but advanced inspection and policy checks require authoring code or invoking external utilities through that escape hatch. |
| MCP-only agent with execution disabled | Can still author QMD, write assets, export Plotly charts, render, and inspect textual results. No dedicated page-image preview or structured report-validation tool is exposed. This is an interface inventory, not an assurance that rendering itself is non-executing. |
| DeerFlow agent with its presentation tools | The delivery bridge is specifically designed for this case. Report Forge instructs the caller to use a separate `present_files` capability. |
| Another MCP client or remote host | Creation and rendering are conceptually portable, but file locations, previews, and delivery need an explicit integration contract. |
| Several contributors working on one report | Can contribute files or sections by convention. No first-class section ownership, revision-conflict handling, or review handoff contract was found. |
| Unattended recurring publication | Missing a complete job, freshness, revision, and release model. Scheduling should be owned by an external workflow system. |

### 5.2 What an agent must currently remember

The intended journey spans several responsibilities:

1. Choose a template and scaffold a project.
2. Acquire evidence outside Report Forge and perform calculations or asset generation.
3. Write the QMD, preserve the needed metadata, insert exhibits and cross-references, and obey the chosen layout conventions.
4. Run the separate flagship linter where applicable and inspect its textual result.
5. Render the requested formats, inspect state and logs, and review the actual artifacts with additional tools.
6. Copy deliverables to the destination and present them using the surrounding application's mechanism.

The core has no explicit answer to “which of those steps remains incomplete for this revision?” `project_status` provides files and last-render information, which is valuable but insufficient for that question. [R2] (`project_status`), [R4], [R6]

### 5.3 The main agent usability gaps

**Discoverability and onboarding.** The README, tool descriptions, flagship rules, and template catalog contain different slices of product knowledge. The CLI covers fewer operations than MCP. A fresh agent needs a compact capability response, examples for common journeys, and an explicit account of which tools and host resources are available. The long desk-writing rules should be discoverable profile documentation rather than repeated universal tool instructions. [R1], [R4], [R6], [R8]

**Precise revision.** Whole-QMD replacement is expensive in context and broad in effect. `append_section` is additive and uses heading text for positioning. Neither offers a stable section identifier with replace, move, delete, or compare operations. `read_project_file` bounds content from the beginning of a file; it is not a navigable section reader. A small requested change to a long report should require only a small read and write. [R2] (`write_report_body`, `append_section`, `read_project_file`)

**Explicit identity and replay behavior.** Calls should consistently name the report and revision. Some chart-path conveniences infer a project from recent filesystem activity. That convenience is poorly matched to concurrent or resumed work. Add explicit report handles, expected-revision checks, and repeatable request IDs where operations create or append content. Treat client retries as a normal workflow condition. [R2] (`_translate_sandbox_path`), [R4]

**Visual feedback.** Logs cannot tell an agent whether the cover hierarchy works or a chart label is readable. Expose page thumbnails/contact sheets and individual exhibit previews as retrievable artifacts. Agents with vision can inspect those; other clients can request human review. This should work through the documented product interface, without a hardcoded assumption that the client can open a host path. [R4]

**Long-running work.** Rendering waits for subprocesses and returns after completion; formats are processed sequentially. There is no Report Forge job handle with progress, cancellation, or resume semantics. Introduce those when unattended or longer workflows become a priority. FastMCP transport capabilities do not substitute for durable application job state. [R2] (`render_report`)

**Research meaning.** An agent can save a CSV, but cannot register it as the dataset behind an exhibit through a dedicated interface. It can write a source URL into prose, but cannot ask which claims lack sources. It can update a target price string, but cannot ask which cover cards, tables, and paragraphs depend on that fact. These are the high-value differences between a file toolkit and a report production product. [R2], [R4]

### 5.4 A better supported agent journey

Proposed operations below are product contracts, not current tool names or an instruction to implement each as a separate endpoint:

```text
Discover capabilities and selected profile
  -> Create or open report from a brief
  -> Read manifest and outline
  -> Register source/data/exhibit records
  -> Read or update a named section at an expected revision
  -> Check completeness and evidence coverage
  -> Render a specific revision
  -> Retrieve previews and record review decisions
  -> Export that revision's artifacts through a chosen delivery adapter
```

Return compact, structured results: report ID, revision, changed section IDs, available artifacts, readiness issues, and suggested next operations. Keep Markdown as the normal prose format and raw-file tools as escape hatches. Prefer a coherent small set of operations over adding a separate tool for every visual component.

## 6. Architectural choices and their product consequences

### 6.1 File-based projects: retain, with a manifest above them

**Current choice:** each report is a directory containing its QMD, configuration, assets, and outputs; a small state file records the last successful render. [R2]

**Benefit:** transparent, easy to archive, and compatible with local agents and ordinary editors.

**Downside:** a directory is not a complete report identity. It does not inherently distinguish a workbench from a draft, a review candidate from a release, or two revisions of the same research. There is no dedicated report listing/search/archive operation in the current MCP surface. [R4]

**Recommendation:** add a small versioned manifest containing the report ID, title, brief, profile selections, revision, section order, evidence/exhibit references, required formats, and workflow state. Markdown files remain authoritative for prose. Define how manual edits are detected and reconciled so a manifest does not create a competing copy of the document.

Start with files and an optional rebuildable local index. Introduce a database only when cross-report search, jobs, or concurrent access justify it. Do not make the original reports dependent on a central server to remain readable.

### 6.2 Copied template assets: reproducible snapshots need explicit versions

**Current choice:** styles, HTML cover fragments, branding, and Typst partials are materialized during scaffolding. Portfolio themes and chart themes use related but separately represented visual values. [R2] (`scaffold_report`, `QUANTFLOW_PLOTLY_THEMES`), [R3]

**Benefit:** the report carries its layout resources and can be customized locally.

**Downside:** a template improvement is not a managed upgrade for existing reports. Design intent exists across several representations, and an agent must understand which files drive which output. This complicates rebranding and recurring updates.

**Recommendation:** version theme/layout packages, record the version and local overrides in each report, and provide an explicit upgrade preview. Use shared design tokens for colors, typography roles, spacing, and chart identity; retain format-specific layout rules where necessary. Derive cover representations from a canonical metadata record through a documented build step.

Quarto already supports packaging custom Typst formats and shared branding. Use those mechanisms where they reduce Report Forge's own maintenance burden. They do not eliminate the need to document which brand properties and components each format supports. [Q9], [Q10]

### 6.3 Computation mixed with publishing: convenient, but broad

**Current choice:** code and script execution share the host user's permissions and the report interpreter. The source explicitly describes project working-directory scoping as an ergonomic choice rather than filesystem isolation. Executable QMD is another computation entry point. [R2] (`run_code`, `run_file`, `render_report`), [R3]

**Benefit:** trusted local agents can calculate, inspect, and publish without moving data through several services.

**Downside:** deploying a renderer now also involves maintaining an execution environment, dependency availability, and resource policy. The present permission model is a fit for a trusted personal workstation; it should not silently become the model for a shared hosted product. This is an architectural boundary assessment, not a vulnerability finding.

**Recommendation:** define a lightweight publish-from-prepared-assets profile and a separately enabled computation profile. If isolated execution is later required, make it a worker boundary covering scripts, executable documents, and renderer subprocesses. Keep analysis orchestration external. Report Forge should record the inputs and outputs it consumed, rather than owning agent selection, model calls, and research delegation.

### 6.4 Reproducibility requires a release snapshot

The templates declare `freeze: auto`, and reports retain source and chart files. Those are useful ingredients, but no complete release record links source, input data, calculations, toolchain, template revision, and final artifacts. Python dependencies have minimum bounds in `pyproject.toml`; the reviewed product contract does not establish a pinned publishing environment. [R2], [R3], [R11]

Quarto documents that freeze governs global project renders, while an individual document render executes code. Cache invalidation also needs attention when external inputs change. Report Forge invokes the source document separately for each output, so `freeze: auto` should not be presented as a guarantee that every format uses one computed snapshot. [Q11], [R2] (`render_report`)

Define a release as a set of inputs and artifacts with recorded hashes and versions. Calculate or collect the evidence once for that release, then let formats consume it. Record as-of, retrieval time, and publication time separately. If live data changes, create a new revision with an explicit freshness decision. Avoid retaining unrestricted host environment dumps or raw agent conversations as reproducibility records.

### 6.5 PNG exhibits: convenient interchange, incomplete analytical objects

**Current choice:** the usual report path embeds local PNGs; `save_chart` also creates interactive HTML. The external chart workflow can burn source information into image pixels. [R1], [R2] (`save_chart`), [R6]

**Benefits:** a stable visual representation across formats and freedom to compute charts outside the document.

**Downsides:** the image alone does not preserve accessible labels, queryable data, a reusable chart specification, or the relationship between an exhibit and a claim. Pixel captions are difficult to restyle or extract. Interactive HTML exports currently reference Plotly through a CDN, so offline portability needs an explicit packaging decision. [R2] (`save_chart`)

**Recommendation:** register an exhibit with an ID, title, description/alt text, data references, source records, as-of, units, chart specification or generating-script reference, and available output variants. Support vector or raster output according to format compatibility and chart content. Select the HTML interactive version or print fallback from the same exhibit record. Keep PNG import for externally supplied charts.

Do not equate an approved chart library with verified research. Builder identity and input provenance should be recorded separately from visual policy.

### 6.6 Publishing means delivery, not a hosted publication platform

The existing publish operation copies artifacts and returns host and sandbox presentation paths. It does not implement a report catalog, stable public URLs, hosting, access-controlled reader portals, or an editorial release history. That is a sensible initial scope. [R2] (`publish_report`), [R4]

Separate three concepts: **render** produces artifacts; **export/deliver** makes selected artifacts available to a client; **publish** releases a specific reviewed revision to a defined destination. Preserve the DeerFlow bridge as one adapter. Add a generic local bundle and client-neutral artifact descriptors before considering remote destinations.

A useful bundle should offer explicit choices for final documents, supporting assets, source, permitted data, and a manifest. It should distinguish a self-contained download from HTML that expects adjacent resources or network access. Artifact IDs and relative paths should be the product contract; host-specific locations belong to adapters.

### 6.7 Multi-format support needs an honest fidelity contract

| Output | Recommended promise | Current limitation to make explicit |
| --- | --- | --- |
| Typst PDF | Editorially composed static research document. | Custom layout rules, pagination constraints, and no interactive charts. |
| HTML | Responsive reading and optional exhibit exploration. | Richer interactions need deliberate integration; portable/offline packaging is a separate choice. |
| DOCX | Editable narrative, tables, references, and figures using a defined Word style profile. | The existing architecture uses a reference document, not the HTML/Typst layout system. Exact cover and magazine-layout parity is unestablished. |
| pdf-web | Browser-print representation of an HTML report. | Static capture of a chosen state; needs its own print composition policy. |

Word reference documents customize Word styles. A polished DOCX experience is feasible, but it needs its own product design and acceptance targets. Treating an exported DOCX as an editable review copy is different from promising bidirectional round-tripping of Word edits into QMD. No such round-trip workflow was found here. [Q2], [R3], [R4]

Accessibility should also be specified per output: meaningful alt text, readable label sizes, table semantics, keyboard-friendly HTML, and a chosen PDF accessibility target. Existing image descriptions and HTML semantics provide a start; this review did not assess conformance. Current Quarto Typst documentation includes PDF accessibility options, whose availability must be matched to the project's chosen toolchain. [Q1], [R3], [R6]

## 7. Missing and incomplete capabilities: prioritized backlog

Priorities reflect the assumed next milestone: dependable agent-assisted analytical reporting on a local installation. **P0** establishes a complete, reviewable report workflow; **P1** improves repeatability and everyday usability; **P2** depends on a demonstrated user need. Effort is relative scope, not a time estimate.

| ID | Priority / scope | Capability and present gap | Minimum useful outcome | Dependencies / starting points |
| --- | --- | --- | --- | --- |
| RF-01 | P0 / Medium | **Report manifest and lifecycle.** Directories and last-render state exist; explicit brief, revision, completeness, and release state do not. | Open a report by stable ID and obtain its brief, profile, sections, revision, missing work, and artifacts. Distinguish draft, review candidate, approved revision, and exported release. Support existing report folders without rewriting their prose. | Foundational. [R2] (`scaffold_report`, `project_status`) |
| RF-02 | P0 / Medium | **Precise agent editing.** Whole-document replacement and append exist; stable section operations and revision checks do not. | Read, replace, move, and remove a named section without resending the report. Preserve unrelated content. A stale revision request returns the current revision and changed-section information; repeating an accepted append does not duplicate it. | RF-01. [R2] (`write_report_body`, `append_section`, `read_project_file`), [R4] |
| RF-03 | P0 / Large | **Evidence and exhibit registry.** Sources and as-of notes exist in authored content; there is no queryable connection between claims, facts, datasets, and exhibits. | Register a source once; link an exhibit and a claim to it; expose source/as-of information in the report; identify missing evidence. Mark observed values, calculations, estimates, and illustrative data distinctly. Preserve open Markdown citation syntax. | RF-01. [R2] (`save_asset`, `save_chart`), [R5], [R9] |
| RF-04 | P0 / Medium | **Integrated readiness and review.** Style checks and a checklist exist separately; no unified report readiness operation or release decision exists. | One structured response lists mandatory sections, missing assets, illustrative content, unsupported evidence links, selected-profile style issues, and review status. Draft rendering remains available. Release eligibility refers to a specific revision and distinguishes automated checks from editorial judgment. | RF-01; deepen evidence checks with RF-03. [R2] (`render_report`), [R6], [R7] |
| RF-05 | P0 / Medium | **Agent-accessible visual preview.** Files and logs are exposed; there is no dedicated preview contract. | Retrieve a page contact sheet, an individual page, and an exhibit preview for a render revision. Record human or agent review feedback against that revision. Viewing must work through an artifact mechanism supported by the client. | RF-01 and initial artifact descriptors from RF-06. [R4] |
| RF-06 | P0 / Medium | **Portable export and release bundle.** DeerFlow/local copying exists; client-neutral retrieval and explicit release contents do not. | Export a chosen revision's PDF/HTML/DOCX with required companion files and a manifest. Offer source/data inclusion as explicit options. A generic client and the DeerFlow adapter can both identify and retrieve the same artifact bytes. | RF-01. [R2] (`publish_report`, `_translate_sandbox_path`), [R4] |
| RF-07 | P1 / Medium | **Capability discovery and onboarding.** Product knowledge is distributed, and CLI coverage is narrower than MCP. | A fresh agent can discover supported template/profile/output combinations, execution availability, dependency readiness, preview support, and delivery methods. Publish concise examples for creating, revising, resuming, and delivering reports; document or close the selected CLI gaps. | Can start immediately; update as other contracts land. [R1], [R4], [R8], [R11], [R12] |
| RF-08 | P1 / Large | **Composable and versioned design profiles.** Genre, theme, layout, and policy are mixed in template names; assets are copied into each report. | Produce an earnings recap and a desk synthesis with the same chosen brand and either supported appearance. Record template versions, preserve older reports, and preview upgrades. Cover metadata and chart colors derive from shared records/tokens. | RF-01 and RF-07. [R2] (`list_templates`, `scaffold_report`), [R3], [R5] |
| RF-09 | P1 / Large | **Repeatable builds and recurring updates.** Source files and freeze settings exist; a frozen evidence/release contract and refresh workflow do not. | Generate several formats from the same prepared input snapshot. Record toolchain, template, input, and artifact identifiers/hashes. Create next-period reports from a brief with explicit parameters and a visible account of changed facts. | RF-01, RF-03, RF-06. [R2] (`render_report`), [R3], [R11] |
| RF-10 | P1 / Medium–Large | **Readable exhibits, richer tables, and output profiles.** Width conventions and styled tables exist; semantic sizing and broad analytical-table policies do not. | Demonstrate a compact chart, a complex chart, a wide comparison, and a long appendix using documented layout policies. Provide data downloads, meaningful descriptions, and defined HTML/DOCX/static fallbacks. Keep format promises explicit. | RF-03 and RF-08. [R3], [R6], [R7] |
| RF-11 | P1 when unattended work is needed / Large | **Build job lifecycle and contributor handoff.** Synchronous operations and append-based contribution exist; durable render jobs and revision-aware handoffs do not. | Obtain a job ID, progress, per-format outcome, and cancellation state; resume inspection after reconnecting. Contributions identify their section and base revision. External orchestration remains responsible for assigning agents and deciding research roles. | RF-01, RF-02, RF-06. [R2] (`render_report`, `run_code`, `run_file`), [R4] |
| RF-12 | P2 / Medium–Large | **Human review surface and report library.** Report files are present; a dedicated catalog and annotation experience are not. | Search/filter reports by subject, date, type, and status; compare revisions; annotate a section or page and record acceptance. Begin with a read/review interface built on the same report and artifact contracts as MCP. | RF-01, RF-02, RF-05, RF-06. [R4] |

For RF-03, evidence coverage is a structural property: a record links to a source. That alone does not establish that the source supports the claim. Preserve an explicit editorial assessment for source quality, uncertainty, conflicting evidence, and interpretation.

Additional conditional features can follow this foundation: batch generation, external scheduling hooks, interactive scenario exploration, chartbooks and slide companions, organization-owned Word styles, localization, and hosted publication destinations. Their priority depends on the intended audience. A separate microservice fleet or a full collaborative editor would introduce substantial scope before the core report workflow is complete.

## 8. Suggested sequence for the next agent

### Milestone A: a revision can be edited, reviewed, and delivered

Start with RF-01, RF-02, and RF-06, plus a compact capability description from RF-07. Add basic preview support from RF-05 and a minimal readiness result from RF-04. The first milestone should let an agent resume a report, change one section, identify the new revision, inspect its output, and deliver those exact artifacts.

Keep compatibility with ordinary QMD editing. Report imports and manual changes must have a defined reconciliation path. Do not introduce a second authoritative copy of every paragraph in JSON.

### Milestone B: a report explains where its claims and exhibits came from

Add RF-03 and deepen RF-04. Start with sources, exhibits, and important shared facts; exhaustive sentence-level modeling is unnecessary for an initial useful release. Connect displayed metrics and captions to their records. Expose missing evidence and illustrative content before release.

Use existing research report genres as examples of the contract. A domain starter should define required evidence and sections, not just provide text to replace.

### Milestone C: the same report system works across designs and periods

Implement RF-08 and RF-09, then prioritize the table and readability policies in RF-10. Support a small, explicit matrix of report types and output profiles. Record the chosen environment and template versions. Use Quarto's computational parameters as an underlying mechanism where appropriate; Report Forge still needs to own brief validation and release identity. [Q4]

### Milestone D: scale according to actual demand

Add RF-11 when render duration, reconnecting clients, concurrent contributors, or scheduled workflows require it. Build RF-12 when human review has become a recurring bottleneck. Use the same operations for the UI, CLI, and MCP clients so product behavior stays coherent.

## 9. Architecture and scope guidance for the implementing agent

Use these provisional defaults unless the owner gives a different product direction:

| Decision | Recommended default | Reason to revisit |
| --- | --- | --- |
| Audience | Agent-assisted analytical reporting, with finance as the strongest profile. | A different report category becomes the primary user need. |
| Deployment | Local-first, trusted single-owner installation. | Multiple untrusted users or a hosted service is explicitly required. |
| Source of truth | Markdown prose plus a versioned manifest for structure and metadata. | A deliberately chosen visual editor requires another model. |
| Outputs | PDF and HTML as publication formats; DOCX with a documented editing-oriented profile. | Word fidelity or tracked-change round-tripping becomes mandatory. |
| Rendering | Quarto with Typst as the normal print route; browser printing as an optional profile. | A specific necessary report composition cannot be reasonably supported. |
| Computation | Prefer prepared, versioned evidence for publication; retain an explicit trusted compute option. | A shared execution service becomes an authorized deployment requirement. |
| Agent coordination | External orchestrator owns task assignment; Report Forge owns report revisions and artifacts. | Changes must remain consistent with the machine's orchestration authority. |

Before implementation, read the applicable workspace instructions and reconcile this baseline with the current catalog. On this machine, implementation/delegation must follow the maintained CAO and AgentSystem policies. This review is not a Codex-direct implementation exception or authority to start peer agents.

Turn each selected backlog item into a bounded contract containing the user-visible outcome, allowed paths, compatibility requirements, and acceptance evidence. The “minimum useful outcome” column is the starting point. Keep the existing reports and showcase assets as reference material, and preserve the user's pre-existing untracked report directories.

The key open product choice is the primary editing experience: agent/Markdown, human review over generated pages, or Word-first collaboration. This review assumes agent/Markdown authoring with lightweight human review because that best matches the current project.

## 10. Evidence and limits

### Repository sources

The paths below are relative to this document. Function and template names in the review identify the relevant architectural surface; they are navigation aids, not code-review findings.

- **R1:** [README](../README.md): positioning, showcase, advertised workflows and outputs.
- **R2:** [Engine](../src/reportforge/engine.py): `list_templates`, `scaffold_report`, `render_report`, `write_report_body`, `save_chart`, `save_asset`, `run_code`, `run_file`, `project_status`, `read_project_file`, `append_section`, `publish_report`, and related helpers.
- **R3:** [General and editorial templates](../src/reportforge/templates.py): format settings, copied layout assets, covers, themes, typography, print columns, tables, and example content.
- **R4:** [MCP interface](../src/reportforge/mcp_server.py): the 12 exposed tools and their workflow instructions.
- **R5:** [Domain templates](../src/reportforge/templates_domain.py): nine registered research starter bodies, including desk synthesis.
- **R6:** [Flagship rules](flagship-rules.md): desk roles, prose, exhibit sizing, chart identity, pre-render checklist, and density assumptions.
- **R7:** [Figure linter source](../scripts/figure_lint.py): the scope of the existing standalone publication-style checks. Read only; not run.
- **R8:** [CLI](../src/reportforge/cli.py): template discovery, creation, rendering, and chart export commands.
- **R9:** [AAPL source](../reports/aapl-12m-flagship/index.qmd), [TSLA light source](../reports/tsla-12m-flagship-light/index.qmd), [TSLA light cover image](images/showcase-tsla-light-cover.png), [TSLA light body image](images/showcase-tsla-light-body.png), and [TSLA dark body image](images/showcase-tsla-dark-body.png). The three images were visually inspected; report sources were sampled for structure and conventions. Their financial assertions were not checked.
- **R10:** [Earlier template proposals](new-templates-2026-proposals.md): historical product ideation, not an authoritative list of missing current features. Its market-trend claims were not adopted as evidence for this review.
- **R11:** [Package metadata](../pyproject.toml): Python requirements, dependency declarations, package and CLI entry point.
- **R12:** [Environment preflight source](../scripts/preflight_env.sh): existing environment preparation/checking mechanism. Read only; not run.

### External primary documentation

Consulted on 2026-09-06. These describe upstream capabilities; they do not certify compatibility with this installation. The comparative recommendations remain the reviewer's judgments.

- **Q1:** [Quarto: Typst basics](https://quarto.org/docs/output-formats/typst.html): PDF route, layout controls, known limitations, image formats, and accessibility options.
- **Q2:** [Quarto: Word templates](https://quarto.org/docs/output-formats/ms-word-templates.html): reference documents and Word styles.
- **Q3:** [Quarto: citations](https://quarto.org/docs/authoring/citations.html): bibliography files, citation syntax, and citation processing.
- **Q4:** [Quarto: parameters](https://quarto.org/docs/computations/parameters.html): parameterized computations and rendering.
- **Q5:** [Typst: syntax](https://typst.app/docs/reference/syntax/): document markup and embedded code modes.
- **Q6:** [Pandoc overview](https://pandoc.org/): multi-format document conversion.
- **Q7:** [Paged.js: web design for print](https://pagedjs.org/en/documentation/5-web-design-for-print/): print-media styling for browser documents.
- **Q8:** [Quarto: interactivity](https://quarto.org/docs/interactive/): interactive document approaches, including client-side computation.
- **Q9:** [Quarto: custom Typst formats](https://quarto.org/docs/output-formats/typst-custom.html): shareable formats, template partials, and customization boundaries.
- **Q10:** [Quarto: branding](https://quarto.org/docs/authoring/brand.html): shared branding across formats.
- **Q11:** [Quarto: managing execution](https://quarto.org/docs/projects/code-execution.html): freeze scope, caching, and external-input refresh considerations.

No statements here establish bug absence, production reliability, render speed, accessibility compliance, financial accuracy, or successful operation by a particular model. Those questions were outside the requested review. The deliverable is a product critique and prioritized architectural direction grounded in the inspected repository.

[R1]: ../README.md
[R2]: ../src/reportforge/engine.py
[R3]: ../src/reportforge/templates.py
[R4]: ../src/reportforge/mcp_server.py
[R5]: ../src/reportforge/templates_domain.py
[R6]: flagship-rules.md
[R7]: ../scripts/figure_lint.py
[R8]: ../src/reportforge/cli.py
[R9]: ../reports/tsla-12m-flagship-light/index.qmd
[R10]: new-templates-2026-proposals.md
[R11]: ../pyproject.toml
[R12]: ../scripts/preflight_env.sh
[Q1]: https://quarto.org/docs/output-formats/typst.html
[Q2]: https://quarto.org/docs/output-formats/ms-word-templates.html
[Q3]: https://quarto.org/docs/authoring/citations.html
[Q4]: https://quarto.org/docs/computations/parameters.html
[Q5]: https://typst.app/docs/reference/syntax/
[Q6]: https://pandoc.org/
[Q7]: https://pagedjs.org/en/documentation/5-web-design-for-print/
[Q8]: https://quarto.org/docs/interactive/
[Q9]: https://quarto.org/docs/output-formats/typst-custom.html
[Q10]: https://quarto.org/docs/authoring/brand.html
[Q11]: https://quarto.org/docs/projects/code-execution.html
