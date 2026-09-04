"""Embedded Quarto templates used by reportforge.scaffold."""

QUARTO_YML = """\
project:
  type: default
  output-dir: output

execute:
  jupyter: <% jupyter_kernel %>
  echo: false
  warning: false
  message: false
  fig-dpi: 300
  freeze: auto

number-sections: <% number_sections %>
<%% if exhibit_labels %%>

crossref:
  fig-title: Exhibit
  tbl-title: Exhibit
  fig-prefix: Exhibit
  tbl-prefix: Exhibit
  sec-prefix: Section
<%% endif %%>

format:
  html:
    toc: <% toc %>
    toc-depth: 3
    theme:
      - brand
      - styles.scss
    code-fold: true
    code-tools: false
    link-external-newwindow: true
  pdf:
    pdf-engine: typst
    papersize: <% papersize %>
<%% if titlepage %%>
    titlepage: true
<%% endif %%>
    margin-x: 2cm
    margin-y: 2.2cm
    toc: <% toc %>
    number-sections: <% number_sections %>
    fig-pos: t
    colorlinks: true
    linkcolor: "#1a2e4a"
    urlcolor: "#3d6b9e"
    citecolor: "#5b6b7f"
  docx:
    reference-doc: assets/reference-doc.docx
    toc: <% toc %>
"""

BRAND_YML = """\
color:
  palette:
    ink: "#22303f"
    navy: "#1a2e4a"
    steel: "#3d6b9e"
    slate: "#5b6b7f"
    gold: "#c9a227"
    mist: "#f2f5f8"
  foreground: "#22303f"
  background: "#ffffff"
  primary: "#1a2e4a"
  secondary: "#3d6b9e"
  tertiary: "#5b6b7f"
  success: "#2e7d32"
  info: "#3d6b9e"
  warning: "#c9a227"
  danger: "#b3402a"
  light: "#f2f5f8"

typography:
  fonts:
    - family: Inter
      source: google
      weight: [400, 500, 600]
    - family: Space Grotesk
      source: google
      weight: [500, 700]
    - family: JetBrains Mono
      source: google
  base:
    family: Inter
    size: 1rem
  headings:
    family: Space Grotesk
    weight: 700
    color: "#1a2e4a"
  monospace: JetBrains Mono
  monospace-inline:
    color: "#1a2e4a"
    background-color: "#f2f5f8"
  monospace-block:
    background-color: mist

meta:
  name: ReportForge
"""

STYLES_SCSS = """\
/*-- scss:rules --*/

h1.title {
  letter-spacing: -0.02em;
}

.subtitle {
  color: $brand-slate;
  font-weight: 400;
}

.figure-caption,
caption {
  color: $brand-slate;
  font-size: 0.85rem;
}

blockquote {
  border-left: 4px solid $brand-gold;
  background: $brand-mist;
  padding: 0.6rem 1rem;
  border-radius: 0 8px 8px 0;
}

table {
  font-size: 0.92em;
}

div.callout-title-container {
  font-weight: 600;
}
"""

INDEX_QMD = """\
---
title: <% title_yaml %>
<%% if subtitle%%>
subtitle: <% subtitle_yaml %>
<%% endif%%>
<%% if author%%>
author: <% author_yaml %>
<%% endif%%>
date: <% date_yaml %>
date-format: long
abstract: <% abstract_yaml %>
---

# Executive summary

Summarize the question, method, headline findings, and the recommendation.
Aim for five sentences a busy reader can act on.

::: {.callout-note}
## Scope

State what this report covers and explicitly does not cover.
:::

# Background

Context the reader needs before the analysis. Cite sources with footnotes[^1].

[^1]: Source description.

# Analysis

## Data and method

Describe inputs, assumptions, and limitations.

## Findings

Embed charts produced by the reportforge chart helper:

![Example figure caption.](assets/example-chart.png){#fig-example width=90%}

See @fig-example for the trend. Reference tables with @tbl-example.

| Metric | Value | As-of |
|--------|------:|------|
| Example | 42 | 2026-08-26 |

: Example table caption. {#tbl-example}

# Recommendations

1. Recommendation one, tied to a finding.
2. Recommendation two.

# Appendix {.appendix}

Methodology notes, extended tables, reproducibility information.

```{python}
# id: example-chart
import plotly.express as px
import pandas as pd

df = pd.DataFrame({"x": range(12), "y": [3, 4, 3.5, 5, 6, 5.8, 7, 8, 7.6, 9, 9.4, 10.2]})
fig = px.line(df, x="x", y="y", markers=True)
fig.update_layout(template="plotly_white", title="Example chart")
fig.write_image("assets/example-chart.png", width=1400, height=700, scale=2)
fig
```
"""

MEMO_QMD = """\
---
title: <% title_yaml %>
<%% if author%%>
author: <% author_yaml %>
<%% endif%%>
date: <% date_yaml %>
date-format: long
---

# Purpose

One paragraph: what this memo decides or communicates.

# Key points

- Point one.
- Point two.

# Details

Short sections. No table of contents, no numbered sections.
"""

WHITEPAPER_QMD = """\
---
title: <% title_yaml %>
<%% if subtitle%%>
subtitle: <% subtitle_yaml %>
<%% endif%%>
<%% if author%%>
author: <% author_yaml %>
<%% endif%%>
date: <% date_yaml %>
date-format: long
abstract: <% abstract_yaml %>
---

<%% if firm%%>
::: {style="text-align: center;"}
**<% firm %>** · Investment Research
:::
<%% endif%%>

# Key takeaways {-}

- **Takeaway one** — the single most important conclusion, stated as a claim.
- **Takeaway two** — the second conclusion, tied to an exhibit if possible.
- **Takeaway three** — what the reader should do about it.

# Investment thesis

Two to four paragraphs: the opportunity, why it is mispriced or overlooked,
and what would make the thesis right or wrong. Lead with the conclusion.

> **Bottom line.** One-sentence version of the thesis for readers in a hurry.

## Why now

The catalysts or structural shifts that make this timely.

# Framework

The analytical framework or taxonomy the paper applies. Hedge-fund white
papers earn trust here: define terms precisely before using them.

## Definitions and scope

What is in scope, what is not, and the conventions used throughout.

# Analysis

The core of the paper. Build the argument exhibit by exhibit — every claim
should point at a chart or table.

## Exhibit-driven findings

![Example exhibit caption.](assets/example-chart.png){#fig-example width=90%}

As @fig-example shows, the trend supports the thesis. State the observation
first, then the interpretation, then the implication.

::: {#fig-metric}
| Metric | Value | As-of |
|--------|------:|------|
| Example | 42 | 2026-08-26 |

Example exhibit caption.
:::

## Robustness and counterarguments

Address the strongest case against the thesis and how the analysis handles
it. Papers that steelman survive scrutiny.

# Portfolio implications

Position sizing context, correlation with existing exposures, liquidity and
exit considerations.

## Risk factors

1. Risk one, with observable early-warning indicators.
2. Risk two, with the condition under which the thesis is abandoned.

# Conclusion

Restate the thesis in light of the evidence. End with the decision this
paper supports.

# Appendix {.appendix}

Methodology notes, data sources, extended exhibits, reproducibility.

```{python}
# Writes the print-quality exhibit PNG referenced by @fig-example above.
# NOTE: do NOT use `#| label:` / `#| fig-cap:` on executable chunks here —
# Quarto 1.10's typst-PDF path emits an undefined `quarto_super` helper for
# them ("unknown variable: quarto_super"). Use markdown embeds with
# {#fig-x} + caption text for exhibits instead.
import plotly.express as px
import pandas as pd

df = pd.DataFrame({"x": range(24), "y": [i + (i % 5) * 0.6 for i in range(24)]})
fig = px.line(df, x="x", y="y", markers=True)
fig.update_layout(template="plotly_white", title="Example exhibit")
# width 9in = target print width; font 16 = readable after ~45% shrink;
# scale=3 = 3x pixel density for print sharpness (~450 DPI effective).
fig.update_layout(font=dict(size=16))
fig.write_image("assets/example-chart.png", width=9 * 100, height=4.5 * 100, scale=3)
```
"""

WHITEPAPER_STYLES_EXTRA = """
.callout {
  border-radius: 8px;
}
h1 {
  border-bottom: 1px solid $brand-mist;
  padding-bottom: 0.3rem;
}
"""

# ---------------------------------------------------------------------------
# "modern" template — branded research brief.
#
# The PDF path is a CUSTOM TYPST TEMPLATE via Quarto's `format: typst` +
# template-partials (the R-for-the-Rest-of-Us / Clarity Data Studio approach
# to heavily branded PDFs). Full-bleed navy masthead, KPI stat strip,
# accent-tick headings, running header/footer with firm + confidentiality
# mark. Validated against Quarto 1.10.18 / Typst 0.15.1.
#
# Hard-won typst gotchas encoded in these partials:
#   - `format: pdf` REJECTS template-partials; must use `format: typst`.
#   - Partial filenames must be typst-template.typ / typst-show.typ.
#   - Typst 0.15: `page(loc).numbering` is gone — use
#     counter(page).at(here()).first() in header/footer context blocks.
#   - `str()` cannot stringify content (dates) — render date content directly.
#   - Inside `{ }` code mode, `#` is invalid — drop it.
#   - `show figure.caption: set text(...)` (show-set), NOT a function rule.
#   - Full-bleed: negative outset() shrinks; use move(dx/dy) + oversized block.
# ---------------------------------------------------------------------------

MODERN_YML = """\
project:
  type: default
  output-dir: output

execute:
  jupyter: <% jupyter_kernel %>
  echo: false
  warning: false
  message: false
  fig-dpi: 300
  freeze: auto

number-sections: false

crossref:
  fig-title: Exhibit
  tbl-title: Exhibit
  fig-prefix: Exhibit
  tbl-prefix: Exhibit
  sec-prefix: Section

format:
  html:
    toc: <% toc %>
    toc-depth: 3
    theme:
      - brand
      - styles.scss
    code-fold: true
    code-tools: false
    link-external-newwindow: true
  typst:
    papersize: <% papersize %>
    mainfont: Inter
    fontsize: 10.5pt
    template-partials:
      - assets/typst-template.typ
      - assets/typst-show.typ
  docx:
    reference-doc: assets/reference-doc.docx
    toc: <% toc %>
"""

MODERN_TYPT_TEMPLATE = r"""// report-forge "modern" conf() — custom typst template partial
#let conf(
  title: none, subtitle: none, authors: (), keywords: (),
  date: none, abstract: none, abstract-title: none, thanks: none,
  kpis: (), firm: none, confidential-mark: none,
  cols: 1, margin: (x: 0.9in, top: 0.8in, bottom: 1.0in),
  paper: "us-letter", lang: "en", region: "US",
  font: none, fontsize: 10.5pt, mathfont: none, codefont: none,
  linestretch: 1.15, sectionnumbering: none, linkcolor: none,
  citecolor: none, filecolor: none, pagenumbering: "1", doc,
) = {
  // brand colors
  let navy = rgb("#0f1b2d")
  let ink = rgb("#22303f")
  let accent = rgb("#2e5bff")
  let gold = rgb("#c9a227")
  let mist = rgb("#f2f5f8")

  set document(title: title, keywords: keywords)
  set page(
    paper: paper, margin: margin, numbering: pagenumbering,
    header: context {
      let num = counter(page).at(here()).first()
      if num >= 2 {
        block(width: 100%)[
          #set text(size: 8pt, fill: rgb("#5b6b7f"), font: "Space Grotesk")
          #grid(columns: (1fr, auto), align: horizon)[#if firm != none [#upper[#firm] — INVESTMENT RESEARCH] else [INVESTMENT RESEARCH]][#date]
          #line(length: 100%, stroke: 0.5pt + mist)
        ]
      }
    },
    footer: context {
      let num = counter(page).at(here()).first()
      if num >= 1 {
        block(width: 100%)[
          #line(length: 100%, stroke: 0.5pt + mist)
          #set text(size: 8pt, fill: rgb("#5b6b7f"), font: "Space Grotesk")
          #grid(columns: (auto, 1fr, auto), align: horizon)[#if confidential-mark != none [#upper[#confidential-mark]] else []][][#num]
        ]
      }
    },
  )
  set par(justify: true, leading: 0.72em, first-line-indent: 0em)
  set text(lang: lang, region: region, size: fontsize, fill: ink)
  set text(font: font) if font != none
  set heading(numbering: sectionnumbering)
  show link: set text(fill: accent)

  // heading style: accent tick + tight tracking
  show heading.where(level: 1): it => block(above: 1.6em, below: 0.6em)[
    #line(length: 24pt, stroke: 2.5pt + accent)
    #v(0.35em)
    #set text(font: "Space Grotesk", size: 15pt, weight: "bold", fill: navy)
    #it.body
  ]
  show heading.where(level: 2): it => block(above: 1.1em, below: 0.4em)[
    #set text(font: "Space Grotesk", size: 12pt, weight: "bold", fill: navy)
    #it.body
  ]

  // exhibit captions: small grey, left-aligned to match the document grid
  show figure.caption: set text(size: 9pt, fill: rgb("#5b6b7f"))
  show figure.caption: set align(left)

  // callouts: left accent bar
  show quote: it => block(inset: (left: 0.9em, y: 0.35em), stroke: (left: 2.5pt + accent))[
    #set text(style: "italic")
    #it
  ]

  // tables: light hairline rules + bold dark header row (house style)
  show table: set table(stroke: 0.5pt + rgb("#d5dbe3"))
  show table.cell.where(y: 0): set text(weight: "bold", fill: navy)

  // title block: full-bleed dark band (move bleeds past margins to page edge)
  if title != none {
    move(dx: -0.9in, dy: -0.8in, block(
      width: 100% + 1.8in,
      fill: navy, inset: (x: 0.9in, top: 1.0in, bottom: 0.85in),
    )[
      #set text(fill: white)
      #block(width: 100%)[
        #set text(font: "Space Grotesk", size: 9pt, weight: "medium", fill: gold)
        #upper[Investment Research]
      ]
      #v(0.45em)
      #block(width: 100%)[
        #set text(font: "Space Grotesk", size: 24pt, weight: "bold", fill: white)
        #title
      ]
      #if subtitle != none {
        v(0.35em)
        block(width: 100%)[
          #set text(size: 12pt, fill: rgb("#9fb3cc"))
          #subtitle
        ]
      }
      #v(0.9em)
      #line(length: 48pt, stroke: 2pt + gold)
      #v(0.55em)
      #grid(columns: (auto, 1fr, auto), align: horizon)[
        #set text(size: 9pt, fill: rgb("#9fb3cc"))
        #if authors != () { [#authors.map(a => a.name).join(", ")] }
      ][][
        #set text(size: 9pt, fill: rgb("#9fb3cc"))
        #date
      ]
    ])
    v(1.1em)
  }

  // KPI stat strip
  if kpis != () and kpis.len() > 0 {
    let n = kpis.len()
    block(width: 100%, inset: (y: 0.7em))[
      #grid(
        columns: (1fr,) * n, column-gutter: 0pt,
        ..kpis.map(k => block(inset: (right: 1em))[
          #block(width: 100%, inset: (left: 0.75em), stroke: (left: 2pt + accent))[
            #set text(font: "Space Grotesk", size: 16pt, weight: "bold", fill: navy)
            #k.value
            #linebreak()
            #set text(size: 8pt, fill: rgb("#5b6b7f"))
            #upper[#k.label]
          ]
        ])
      )
    ]
    v(0.6em)
  }

  if abstract != none {
    block(width: 100%, inset: (y: 0.6em))[
      #line(length: 100%, stroke: 0.5pt + mist)
      #v(0.5em)
      #set text(size: 10pt, fill: rgb("#5b6b7f"))
      #grid(columns: (auto, 1fr), column-gutter: 1.2em)[
        #set text(font: "Space Grotesk", size: 9pt, weight: "bold", fill: navy)
        #upper[Abstract]
      ][#abstract]
      #v(0.3em)
      #line(length: 100%, stroke: 0.5pt + mist)
    ]
    v(0.8em)
  }

  doc
}
"""

MODERN_TYPT_SHOW = """\
#show: doc => conf(
$if(title)$
  title: [$title$],
$endif$
$if(subtitle)$
  subtitle: [$subtitle$],
$endif$
$if(by-author)$
  authors: (
$for(by-author)$
$if(it.name.literal)$
    ( name: [$it.name.literal$] ),
$endif$
$endfor$
  ),
$endif$
$if(date)$
  date: [$date$],
$endif$
$if(abstract)$
  abstract: [$abstract$],
$endif$
$if(firm)$
  firm: [$firm$],
$endif$
$if(confidential-mark)$
  confidential-mark: [$confidential-mark$],
$endif$
$if(kpis)$
  kpis: (
$for(kpis)$
    ( value: [$it.value$], label: [$it.label$] ),
$endfor$
  ),
$endif$
$if(papersize)$
  paper: "$papersize$",
$endif$
$if(mainfont)$
  font: ("$mainfont$",),
$endif$
$if(fontsize)$
  fontsize: $fontsize$,
$endif$
$if(section-numbering)$
  sectionnumbering: "$section-numbering$",
$endif$
  pagenumbering: $if(page-numbering)$"$page-numbering$"$else$none$endif$,
  doc,
)
"""

MODERN_QMD = """\
---
title: <% title_yaml %>
<%% if subtitle%%>
subtitle: <% subtitle_yaml %>
<%% endif%%>
<%% if author%%>
author: <% author_yaml %>
<%% endif%%>
<%% if firm%%>
firm: <% firm_yaml %>
<%% endif%%>
<%% if confidential_mark%%>
confidential-mark: <% confidential_mark_yaml %>
<%% endif%%>
date: <% date_yaml %>
date-format: long
abstract: <% abstract_yaml %>
<%% if kpis_yaml%%>
<% kpis_yaml %>
<%% endif%%>
---

# Executive summary

Three to five sentences: what changed, why it matters, and what to do.
Modern research briefs lead with the number, not the narrative.

> **Bottom line.** One sentence a portfolio manager can repeat in a meeting.

# The signal

Build the case exhibit by exhibit. State the observation, then the
interpretation, then the implication.

![Example exhibit caption.](assets/example-chart.png){#fig-example width=90%}

As @fig-example shows, the trend supports the thesis.

::: {#fig-metric}
| Metric | Value | As-of |
|--------|------:|------|
| Example | 42 | 2026-08-26 |

Example exhibit caption.
:::

# What has changed

Regime context: the structural shift or catalyst that makes this actionable
now rather than six months ago.

# Portfolio actions

Concrete, sized, and bounded: what to add, cut, or hedge, and the expected
interaction with existing exposures.

# Risks and invalidation

1. Risk one, with its observable early-warning indicator.
2. The exact condition under which this thesis is abandoned.

# Method and data {.appendix}

Data sources, lookback windows, conventions, and reproducibility notes.

```{python}
# Writes the print-quality exhibit PNG referenced by @fig-example above.
# NOTE: do NOT use `#| label:` / `#| fig-cap:` on executable chunks —
# the typst-PDF path breaks on them. Markdown embeds + {#fig-x} instead.
import plotly.express as px
import pandas as pd

df = pd.DataFrame({"x": range(24), "y": [i + (i % 5) * 0.6 for i in range(24)]})
fig = px.line(df, x="x", y="y", markers=True)
fig.update_layout(template="plotly_white", title="Example exhibit")
fig.update_traces(line_color="#2e5bff", marker_color="#2e5bff", marker_size=5)
# width 9in = target print width; font 16 stays readable after shrink;
# scale=3 = ~450 DPI effective for print sharpness.
fig.update_layout(font=dict(size=16))
fig.write_image("assets/example-chart.png", width=9 * 100, height=4.5 * 100, scale=3)
```
"""

MODERN_STYLES_EXTRA = """
/* modern template: accent-tick headings + branded callouts (HTML) */
h1 {
  margin-top: 2.2rem;
  padding-top: 0.55rem;
  border-top: 3px solid #2e5bff;
  letter-spacing: -0.015em;
}
.quarto-title h1.title {
  border-top: none;
  margin-top: 0;
}
h2 {
  letter-spacing: -0.01em;
}
blockquote {
  border-left: 4px solid #2e5bff;
  background: transparent;
  padding: 0.4rem 1rem;
  color: $brand-slate;
  font-style: italic;
}
.figure-caption,
caption {
  text-align: left;
}
"""

# ---------------------------------------------------------------------------
# "studio" template — premium, content-neutral editorial system.
#
# Studio deliberately separates visual identity from document purpose. Its
# optional metadata controls composition, while the Markdown body remains free
# to use any section sequence. PDF uses a custom Typst partial; HTML gets a
# generated semantic header plus responsive CSS; DOCX keeps clean native
# structure through the reference document.
# ---------------------------------------------------------------------------

STUDIO_YML = """\
project:
  type: default
  output-dir: output

execute:
  jupyter: <% jupyter_kernel %>
  echo: false
  warning: false
  message: false
  fig-dpi: 300
  freeze: auto

number-sections: false

crossref:
  fig-title: Exhibit
  tbl-title: Table
  fig-prefix: Exhibit
  tbl-prefix: Table
  sec-prefix: Section

format:
  html:
    toc: <% toc %>
    toc-depth: 3
    theme:
      - brand
      - styles.scss
    include-before-body: assets/studio-header.html
    title-block-style: none
    code-fold: true
    code-tools: false
    link-external-newwindow: true
  typst:
    papersize: <% papersize %>
    mainfont: Inter
    fontsize: 10.5pt
    template-partials:
      - assets/typst-template.typ
      - assets/typst-show.typ
  docx:
    reference-doc: assets/reference-doc.docx
    toc: <% toc %>
"""

STUDIO_HTML_HEADER = """\
<header class="rf-studio-header rf-layout-<% title_layout %>" style="--rf-accent: <% accent %>" role="banner">
  <div class="rf-title-frame">
<%% if eyebrow %%>
    <p class="rf-eyebrow"><% eyebrow_html %></p>
<%% endif %%>
    <h1 class="rf-display-title"><% title_html %></h1>
<%% if subtitle %%>
    <p class="rf-display-subtitle"><% subtitle_html %></p>
<%% endif %%>
    <div class="rf-title-meta">
<%% if organization %%>
      <span class="rf-organization"><% organization_html %></span>
<%% endif %%>
<%% if author %%>
      <span><% author_html %></span>
<%% endif %%>
      <time><% date_html %></time>
    </div>
<%% if abstract %%>
    <p class="rf-deck"><% abstract_html %></p>
<%% endif %%>
  </div>
<%% if metrics_html %%>
  <div class="rf-metric-grid rf-metrics-<% metrics_count %>" aria-label="Key metrics">
<% metrics_html %>
  </div>
<%% endif %%>
<%% if verdict %%>
  <div class="rf-verdict" role="note">
    <span class="rf-verdict-tag">Conviction call</span>
    <span class="rf-verdict-text"><% verdict_html %></span>
  </div>
<%% endif %%>
<%% if key_points_html %%>
  <div class="rf-key-points" aria-label="Executive summary">
<% key_points_html %>
  </div>
<%% endif %%>
<%% if scenarios_html %%>
  <div class="rf-scenarios" aria-label="Scenarios">
<% scenarios_html %>
  </div>
<%% endif %%>
</header>
"""

STUDIO_TYPT_TEMPLATE = r"""// report-forge "studio" — flexible editorial Typst template
#let studio(
  title: none, subtitle: none, authors: (), keywords: (),
  date: none, abstract: none, abstract-title: none, thanks: none,
  metrics: (), verdict: none, key-points: (), scenarios: (),
  organization: none, eyebrow: none,
  title-layout: "hero", accent: "#4f46e5", confidential-mark: none,
  cols: 1, margin: (x: 0.82in, top: 0.72in, bottom: 0.9in),
  paper: "us-letter", lang: "en", region: "US",
  font: none, fontsize: 10.5pt, mathfont: none, codefont: none,
  linestretch: 1.15, sectionnumbering: none, linkcolor: none,
  citecolor: none, filecolor: none, pagenumbering: "1", doc,
) = {
  let paper-tone = rgb("#f8f7f3")
  let ink = rgb("#171923")
  let muted = rgb("#62697a")
  let hairline = rgb("#dfe1e7")
  let panel = rgb("#ffffff")
  let accent-color = rgb(accent)

  set document(title: title, keywords: keywords)
  set page(
    paper: paper,
    margin: margin,
    fill: paper-tone,
    numbering: pagenumbering,
    header: context {
      let num = counter(page).at(here()).first()
      if num >= 2 {
        block(width: 100%)[
          #set text(size: 7.8pt, fill: muted, font: "Space Grotesk")
          #grid(columns: (1fr, auto), align: horizon)[
            #if organization != none [#upper[#organization]] else if eyebrow != none [#upper[#eyebrow]] else [STUDIO REPORT]
          ][#date]
          #line(length: 100%, stroke: 0.55pt + hairline)
        ]
      }
    },
    footer: context {
      let num = counter(page).at(here()).first()
      block(width: 100%)[
        #line(length: 100%, stroke: 0.55pt + hairline)
        #set text(size: 7.8pt, fill: muted, font: "Space Grotesk")
        #grid(columns: (1fr, auto), align: horizon)[
          #if confidential-mark != none [#upper[#confidential-mark]] else []
        ][#num]
      ]
    },
  )
  set par(justify: true, leading: 0.74em, first-line-indent: 0em)
  set text(lang: lang, region: region, size: fontsize, fill: ink)
  set text(font: font) if font != none
  set heading(numbering: sectionnumbering)
  show link: set text(fill: accent-color)

  show heading.where(level: 1): it => block(above: 1.7em, below: 0.62em)[
    #grid(columns: (18pt, 1fr), column-gutter: 9pt, align: horizon)[
      #line(length: 18pt, stroke: 2.5pt + accent-color)
    ][
      #set text(font: "Space Grotesk", size: 15pt, weight: "bold", fill: ink)
      #it.body
    ]
  ]
  show heading.where(level: 2): it => block(above: 1.1em, below: 0.42em)[
    #set text(font: "Space Grotesk", size: 11.5pt, weight: "bold", fill: ink)
    #it.body
  ]
  show heading.where(level: 3): set text(font: "Space Grotesk", size: 10pt, weight: "bold", fill: muted)

  show figure.caption: set text(size: 9pt, fill: ink)
  show figure.caption: set align(left)
  show quote: it => block(
    width: 100%,
    fill: panel,
    radius: 6pt,
    inset: (left: 16pt, right: 14pt, y: 10pt),
    stroke: (left: 3pt + accent-color),
  )[
    #set text(size: 10.5pt, style: "italic", fill: ink)
    #it
  ]
  show table: set table(
    stroke: 0.5pt + hairline,
    inset: (x: 6pt, y: 5pt),
    fill: (x, y) => if y == 0 { rgb("#e7e9f5") } else if calc.rem(y, 2) == 0 { rgb("#f1f2f8") } else { panel },
  )
  show table: set text(size: 8.7pt)
  show table.cell.where(y: 0): set text(weight: "bold", fill: ink)
  show table.cell.where(x: 0): set text(weight: "bold")

  set page(margin: (x: margin.x, top: 0.5in, bottom: 0.6in))
  if title != none {
    if title-layout == "minimal" {
      // Plain title block: no card, no panel — kicker, title, rule, meta.
      block(width: 100%)[
        #set par(justify: false)
        #if eyebrow != none {
          line(length: 26pt, stroke: 1.4pt + accent-color)
          v(0.35em)
          set text(font: "Space Grotesk", size: 8pt, weight: "medium", fill: accent-color)
          upper[#eyebrow]
          v(0.5em)
        }
        #set text(font: "Space Grotesk", size: 24pt, weight: "bold", fill: ink, hyphenate: false)
        #title
        #if subtitle != none {
          v(0.3em)
          set text(size: 11pt, fill: muted)
          subtitle
        }
        #v(0.6em)
        #line(length: 40pt, stroke: 2pt + accent-color)
        #v(0.5em)
        #set text(size: 8.5pt, fill: muted)
        #grid(columns: (1fr, auto), align: horizon)[
          #if organization != none [#organization] else if authors != () [#authors.map(a => a.name).join(", ")] else []
        ][#date]
      ]
      v(0.9em)
    } else if title-layout == "compact" {
      block(
        width: 100%,
        inset: (left: 18pt, y: 15pt),
        stroke: (left: 4pt + accent-color),
      )[
        #set par(justify: false)
        #if eyebrow != none {
          set text(font: "Space Grotesk", size: 8pt, weight: "medium", fill: accent-color)
          upper[#eyebrow]
          v(0.45em)
        }
        #set text(font: "Space Grotesk", size: 23pt, weight: "bold", fill: ink, hyphenate: false)
        #title
        #if subtitle != none {
          v(0.35em)
          set text(size: 11pt, fill: muted)
          subtitle
        }
        #v(0.75em)
        #set text(size: 8.5pt, fill: muted)
        #grid(columns: (1fr, auto), align: horizon)[
          #if organization != none [#organization] else if authors != () [#authors.map(a => a.name).join(", ")] else []
        ][#date]
      ]
      v(1.0em)
    } else {
      block(
        width: 100%,
        fill: panel,
        radius: 10pt,
        inset: (left: 26pt, right: 24pt, top: 18pt, bottom: 15pt),
        stroke: (left: 7pt + accent-color, rest: 0.6pt + hairline),
      )[
        #set par(justify: false)
        #if eyebrow != none {
          set text(font: "Space Grotesk", size: 8.5pt, weight: "medium", fill: accent-color)
          upper[#eyebrow]
          v(0.7em)
        }
        #set text(font: "Space Grotesk", size: 22pt, weight: "bold", fill: ink, hyphenate: false)
        #title
        #if subtitle != none {
          v(0.5em)
          set text(size: 11pt, fill: muted)
          subtitle
        }
        #v(0.6em)
        #line(length: 46pt, stroke: 2.2pt + accent-color)
        #v(0.7em)
        #set text(size: 8.8pt, fill: muted)
        #grid(columns: (1fr, auto), align: horizon)[
          #if organization != none [#organization] else if authors != () [#authors.map(a => a.name).join(", ")] else []
        ][#date]
      ]
      v(0.7em)
    }
  }

  if metrics != () and metrics.len() > 0 {
    let n = metrics.len()
    let metric-cols = if n == 1 {
      (1fr,)
    } else if n == 2 or n == 4 {
      (1fr, 1fr)
    } else {
      (1fr, 1fr, 1fr)
    }
    grid(
      columns: metric-cols,
      column-gutter: 9pt,
      row-gutter: 9pt,
      ..metrics.map(metric => block(
        fill: panel,
        radius: 6pt,
        inset: (x: 12pt, y: 6pt),
        stroke: 0.55pt + hairline,
      )[
        #set text(font: "Space Grotesk", size: 12pt, weight: "bold", fill: ink)
        #metric.value
        #linebreak()
        #set text(size: 7.7pt, fill: muted)
        #upper[#metric.label]
      ])
    )
    v(0.55em)
  }


  if verdict != none {
    block(
      width: 100%,
      fill: rgb("#e9e8fa"),
      radius: 6pt,
      inset: (x: 14pt, y: 7pt),
      stroke: (left: 3pt + accent-color),
    )[
      #set text(font: "JetBrains Mono", size: 7.7pt, weight: "medium", fill: accent-color)
      CONVICTION CALL
      #linebreak()
      #set text(size: 9.5pt, weight: "bold", fill: ink)
      #verdict
    ]
    v(0.55em)
  }

  if key-points != () and key-points.len() > 0 {
    grid(
      columns: (1fr, 1fr),
      column-gutter: 8pt,
      row-gutter: 8pt,
      ..key-points.map(p => block(
        fill: panel,
        radius: 6pt,
        inset: (x: 12pt, y: 6pt),
        stroke: 0.55pt + hairline,
      )[
        #set text(size: 8pt, fill: ink)
        #text(fill: accent-color)[◆ ]#p
      ])
    )
    v(0.55em)
  }

  if scenarios != () and scenarios.len() > 0 {
    grid(
      columns: (1fr, 1fr, 1fr),
      column-gutter: 8pt,
      ..scenarios.enumerate().map(((i, s)) => block(
        fill: panel,
        radius: 6pt,
        inset: (x: 12pt, y: 6pt),
        stroke: if i == 1 { 1pt + accent-color } else { 0.55pt + hairline },
      )[
        #set text(font: "JetBrains Mono", size: 7.7pt, fill: muted)
        #upper[#s.label]
        #linebreak()
        #set text(size: 12pt, weight: "bold", fill: ink)
        #s.value
        #linebreak()
        #set text(size: 7.5pt, fill: muted)
        #s.detail
      ])
    )
    v(0.55em)
  }

  if abstract != none {
    block(
      width: 100%,
      fill: rgb("#efefff"),
      radius: 7pt,
      inset: (x: 15pt, y: 8pt),
    )[
      #set text(size: 8.5pt, fill: muted)
      #abstract
    ]
    v(0.55em)
  }

  pagebreak(weak: true)
  set page(margin: margin)
  doc
}
"""

STUDIO_TYPT_SHOW = """\
#show: doc => studio(
$if(title)$
  title: [$title$],
$endif$
$if(subtitle)$
  subtitle: [$subtitle$],
$endif$
$if(by-author)$
  authors: (
$for(by-author)$
$if(it.name.literal)$
    ( name: [$it.name.literal$] ),
$endif$
$endfor$
  ),
$endif$
$if(date)$
  date: [$date$],
$endif$
$if(abstract)$
  abstract: [$abstract$],
$endif$
$if(organization)$
  organization: [$organization$],
$endif$
$if(eyebrow)$
  eyebrow: [$eyebrow$],
$endif$
$if(title-layout)$
  title-layout: "$title-layout$",
$endif$
$if(accent-typst)$
  accent: "#$accent-typst$",
$endif$
$if(confidential-mark)$
  confidential-mark: [$confidential-mark$],
$endif$
$if(metrics)$
  metrics: (
$for(metrics)$
    ( value: [$it.value$], label: [$it.label$] ),
$endfor$
  ),
$endif$
$if(verdict)$
  verdict: [$verdict$],
$endif$
$if(key-points)$
  key-points: (
$for(key-points)$
    [$it$],
$endfor$
  ),
$endif$
$if(scenarios)$
  scenarios: (
$for(scenarios)$
    ( label: [$it.label$], value: [$it.value$], detail: [$it.detail$] ),
$endfor$
  ),
$endif$
$if(papersize)$
  paper: "$papersize$",
$endif$
$if(mainfont)$
  font: ("$mainfont$",),
$endif$
$if(fontsize)$
  fontsize: $fontsize$,
$endif$
$if(section-numbering)$
  sectionnumbering: "$section-numbering$",
$endif$
  pagenumbering: $if(page-numbering)$"$page-numbering$"$else$none$endif$,
  doc,
)
"""

STUDIO_QMD = """\
---
title: <% title_yaml %>
reportforge-template: "<% template_name %>"
<%% if subtitle%%>
subtitle: <% subtitle_yaml %>
<%% endif%%>
<%% if author%%>
author: <% author_yaml %>
<%% endif%%>
<%% if organization%%>
organization: <% organization_yaml %>
<%% endif%%>
<%% if eyebrow%%>
eyebrow: <% eyebrow_yaml %>
<%% endif%%>
title-layout: <% title_layout_yaml %>
accent: <% accent_yaml %>
accent-typst: <% accent_typst_yaml %>
<%% if confidential_mark%%>
confidential-mark: <% confidential_mark_yaml %>
<%% endif%%>
date: <% date_yaml %>
date-format: long
abstract: <% abstract_yaml %>
<%% if metrics_yaml%%>
<% metrics_yaml %>
<%% endif%%>
<%% if verdict%%>
verdict: <% verdict_yaml %>
<%% endif%%>
<%% if key_points_yaml%%>
<% key_points_yaml %>
<%% endif%%>
<%% if scenarios_yaml%%>
<% scenarios_yaml %>
<%% endif%%>
title-block-style: none
---

# Overview

Open with the idea, decision, or story this document exists to communicate.
Nothing below this line is required structure—rename, reorder, add, or remove
any section to fit the work.

> **Lead with meaning.** Use a short pull quote for the sentence readers should
> remember after they close the report.

<!-- Sketch only: replace with the sections this brief needs (findings,
     methods, evidence, risks, recommendations, appendix, …) and delete
     whatever does not fit. HTML comments never render in any format. -->

# Figures and tables

Use figures and tables when they clarify the argument. Captions remain
consistent across HTML, PDF, and DOCX.

![Example figure caption.](assets/example-chart.png){#fig-example width=80%}

As @fig-example shows, the template supports ordinary Quarto cross-references.

| Measure | Current | Previous |
|:--------|--------:|---------:|
| Example A | 42 | 38 |
| Example B | 17 | 21 |

: Example table caption. {#tbl-example}

**Interpretation.** Explain what the evidence means, where uncertainty remains,
and which assumptions matter. Ordinary Markdown—not a fixed template
vocabulary—drives the document.

# Notes

Sources, methods, definitions, and reproducibility details can live
here or anywhere else the document requires.

```{python}
# Generate the neutral print-quality example used by @fig-example.
# Keep cross-reference metadata on the Markdown image, not this executable
# chunk, for compatibility with Quarto's Typst path.
import pandas as pd
import plotly.express as px

df = pd.DataFrame({
    "period": list(range(12)),
    "value": [18, 22, 21, 27, 31, 29, 36, 41, 39, 46, 52, 57],
})
fig = px.line(df, x="period", y="value", markers=True)
fig.update_layout(
    template="<% plotly_default %>",
    title="Example trend",
    font=dict(size=16),
    margin=dict(l=55, r=30, t=70, b=50),
)
fig.update_traces(line_color="<% accent %>", marker_color="<% accent %>", marker_size=6)
fig.write_image("assets/example-chart.png", width=900, height=360, scale=3)
```
"""

STUDIO_STYLES_EXTRA = """
/* Studio: responsive editorial system. */
:root {
  --rf-accent: <% accent %>;
  --rf-paper: #f8f7f3;
  --rf-panel: #ffffff;
  --rf-ink: #171923;
  --rf-muted: #62697a;
  --rf-line: #dfe1e7;
}

body {
  background: var(--rf-paper);
  color: var(--rf-ink);
}

#title-block-header {
  display: none;
}

.rf-studio-header {
  --rf-accent: #4f46e5;
  position: relative;
  width: min(1120px, calc(100% - 3rem));
  margin: 2rem auto 3.5rem;
  overflow: hidden;
  border: 1px solid var(--rf-line);
  border-radius: 22px;
  background:
    radial-gradient(circle at 88% 8%, rgba(79, 70, 229, 0.16), transparent 30%),
    linear-gradient(145deg, #ffffff 0%, #f4f3ee 100%);
  box-shadow: 0 24px 70px rgba(23, 25, 35, 0.09);
}

.rf-studio-header::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 8px;
  background: var(--rf-accent);
}

.rf-title-frame {
  padding: 4.6rem 5rem 2.6rem;
}

.rf-layout-compact .rf-title-frame {
  padding: 2.4rem 3rem 1.9rem;
}

.rf-eyebrow {
  margin: 0 0 1rem;
  color: var(--rf-accent);
  font-family: "Space Grotesk", sans-serif;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.13em;
  text-transform: uppercase;
}

.rf-display-title {
  max-width: 900px;
  margin: 0;
  color: var(--rf-ink);
  font-family: "Space Grotesk", sans-serif;
  font-size: clamp(2.5rem, 6vw, 5.1rem);
  font-weight: 700;
  letter-spacing: -0.055em;
  line-height: 0.98;
  overflow-wrap: anywhere;
}

.rf-layout-compact .rf-display-title {
  font-size: clamp(2rem, 4.5vw, 3.45rem);
  line-height: 1.02;
}

.rf-display-subtitle {
  max-width: 760px;
  margin: 1.25rem 0 0;
  color: var(--rf-muted);
  font-size: clamp(1.05rem, 2vw, 1.35rem);
  line-height: 1.45;
}

.rf-title-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem 1.25rem;
  align-items: center;
  margin-top: 2rem;
  color: var(--rf-muted);
  font-size: 0.82rem;
}

.rf-title-meta span + span::before,
.rf-title-meta span + time::before,
.rf-title-meta time::before {
  content: "·";
  margin-right: 1.25rem;
  color: var(--rf-line);
}

.rf-organization {
  color: var(--rf-ink);
  font-family: "Space Grotesk", sans-serif;
  font-weight: 700;
}

.rf-deck {
  max-width: 800px;
  margin: 2rem 0 0;
  padding-top: 1.35rem;
  border-top: 1px solid var(--rf-line);
  color: var(--rf-muted);
  font-size: 1rem;
  line-height: 1.65;
}

.rf-metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  border-top: 1px solid var(--rf-line);
  background: var(--rf-line);
}

.rf-metrics-1 {
  grid-template-columns: minmax(0, 1fr);
}

.rf-metrics-2,
.rf-metrics-4 {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.rf-metric {
  min-width: 0;
  padding: 1.35rem 1.65rem;
  background: rgba(255, 255, 255, 0.88);
}

.rf-metric-value {
  color: var(--rf-ink);
  font-family: "Space Grotesk", sans-serif;
  font-size: clamp(1.35rem, 3vw, 2rem);
  font-weight: 700;
  letter-spacing: -0.035em;
  overflow-wrap: anywhere;
}

.rf-metric-label {
  margin-top: 0.2rem;
  color: var(--rf-muted);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
/* Cover infographics: verdict band, exec-summary key points, scenarios. */
.rf-verdict {
  display: flex;
  align-items: baseline;
  gap: 0.9rem;
  margin: 0;
  padding: 1.15rem 1.65rem;
  border-top: 1px solid var(--rf-line);
  border-left: 4px solid var(--rf-accent);
  background: color-mix(in srgb, var(--rf-accent) 10%, transparent);
}
.rf-verdict-tag {
  flex: none;
  color: var(--rf-accent);
  font-family: "IBM Plex Mono", "JetBrains Mono", monospace;
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}
.rf-verdict-text {
  color: var(--rf-ink);
  font-family: Fraunces, Georgia, serif;
  font-size: 1.12rem;
  font-weight: 600;
}
.rf-key-points {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  border-top: 1px solid var(--rf-line);
  background: var(--rf-line);
}
.rf-key-point {
  display: flex;
  gap: 0.7rem;
  align-items: flex-start;
  background: var(--rf-panel);
  padding: 1.1rem 1.4rem;
}
.rf-key-point-mark::before {
  content: "◆";
  color: var(--rf-accent);
  font-size: 0.8rem;
  line-height: 1.7;
}
.rf-key-point p {
  margin: 0;
  color: var(--rf-ink);
  font-size: 0.92rem;
  line-height: 1.55;
}
.rf-scenarios {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  border-top: 1px solid var(--rf-line);
  background: var(--rf-line);
}
.rf-scenario {
  background: var(--rf-panel);
  padding: 1.1rem 1.4rem;
}
.rf-scenario-base {
  background: color-mix(in srgb, var(--rf-accent) 8%, var(--rf-panel));
  box-shadow: inset 0 3px 0 var(--rf-accent);
}
.rf-scenario-label {
  color: var(--rf-muted);
  font-family: "IBM Plex Mono", "JetBrains Mono", monospace;
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}
.rf-scenario-value {
  margin: 0.15rem 0 0.3rem;
  color: var(--rf-ink);
  font-family: Fraunces, Georgia, serif;
  font-size: 1.6rem;
  font-weight: 600;
}
.rf-scenario-detail {
  color: var(--rf-muted);
  font-size: 0.82rem;
  line-height: 1.5;
}
/* Showcase tables — spreadsheet look: banded header, zebra rows, label
   column, tabular numerals. Wrap any Markdown table in ::: {.rf-showtable}
   (add .rf-nums-right to right-align data columns). */
.rf-showtable {
  margin: 1.5rem 0;
  border: 1px solid var(--rf-line);
  border-radius: 12px;
  overflow: hidden;
  background: var(--rf-panel);
}
.rf-showtable table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  margin: 0;
  font-size: 0.86rem;
}
.rf-showtable thead th {
  border-bottom: 2px solid var(--rf-accent);
  background: color-mix(in srgb, var(--rf-accent) 13%, transparent);
  color: var(--rf-ink);
  font-weight: 700;
  text-align: left;
  padding: 0.65rem 0.8rem;
  overflow-wrap: anywhere;
}
.rf-showtable tbody td {
  border-bottom: 1px solid var(--rf-line);
  color: var(--rf-ink);
  padding: 0.55rem 0.8rem;
  overflow-wrap: anywhere;
  font-variant-numeric: tabular-nums;
}
.rf-showtable tbody tr:nth-child(even) td {
  background: color-mix(in srgb, currentColor 4%, transparent);
}
.rf-showtable tbody tr:last-child td {
  border-bottom: none;
}
.rf-showtable tbody tr td:first-child {
  font-weight: 600;
}
.rf-showtable.rf-nums-right th:nth-child(n+2),
.rf-showtable.rf-nums-right td:nth-child(n+2) {
  text-align: right;
}
@media (max-width: 640px) {
  .rf-key-points,
  .rf-scenarios {
    grid-template-columns: minmax(0, 1fr);
  }
}


main.content {
  max-width: 880px;
}

main.content section.level1 > h1 {
  display: grid;
  grid-template-columns: 30px 1fr;
  gap: 0.7rem;
  align-items: center;
  margin-top: 3.25rem;
  padding: 0;
  border: 0;
  color: var(--rf-ink);
  font-size: clamp(1.65rem, 3vw, 2.2rem);
  letter-spacing: -0.035em;
}

main.content section.level1 > h1::before {
  content: "";
  width: 30px;
  height: 4px;
  border-radius: 999px;
  background: var(--rf-accent, #4f46e5);
}

main.content h2 {
  color: var(--rf-ink);
  letter-spacing: -0.025em;
}

.studio-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin: 1.5rem 0;
}

.studio-card {
  padding: 1.35rem 1.45rem;
  border: 1px solid var(--rf-line);
  border-radius: 14px;
  background: var(--rf-panel);
}

.studio-card h2 {
  margin-top: 0;
  font-size: 1rem;
}

/* Minimal title layout: no card chrome — plain themed title block. */
.rf-layout-minimal {
  background: transparent;
  border: none;
  box-shadow: none;
}

.rf-layout-minimal .rf-title-frame {
  padding: 1.5rem 0 0;
}

.rf-layout-minimal .rf-display-title {
  font-size: clamp(2rem, 4.5vw, 3.1rem);
}

.rf-layout-minimal .rf-metric-grid {
  background: transparent;
}

.rf-layout-minimal .rf-metric {
  background: transparent;
}

blockquote {
  margin: 1.6rem 0;
  padding: 1rem 1.25rem;
  border: 1px solid var(--rf-line);
  border-left: 5px solid var(--rf-accent, #4f46e5);
  border-radius: 0 12px 12px 0;
  background: var(--rf-panel);
  color: var(--rf-ink);
  font-style: normal;
}

table {
  overflow: hidden;
  border: 1px solid var(--rf-line);
  border-radius: 10px;
  background: var(--rf-panel);
}

thead {
  background: #efefff;
}

.figure-caption,
caption {
  color: var(--rf-muted);
  text-align: left;
}

@media (max-width: 720px) {
  .rf-studio-header {
    width: min(100% - 1rem, 1120px);
    margin-top: 0.5rem;
    border-radius: 16px;
  }

  .rf-title-frame,
  .rf-layout-compact .rf-title-frame {
    padding: 2.3rem 1.5rem 1.7rem 1.8rem;
  }

  .rf-display-title {
    font-size: clamp(2.15rem, 12vw, 3.4rem);
  }

  .rf-title-meta {
    display: grid;
    gap: 0.35rem;
  }

  .rf-title-meta span + span::before,
  .rf-title-meta span + time::before,
  .rf-title-meta time::before {
    content: none;
  }

  .rf-metric-grid,
  .studio-grid {
    grid-template-columns: 1fr;
  }

  .rf-metric {
    padding: 1rem 1.5rem;
  }
}

@media print {
  .rf-studio-header {
    box-shadow: none;
    break-inside: avoid;
  }
}
"""

BESPOKE_YML = """\
project:
  type: default
  output-dir: output

execute:
  jupyter: <% jupyter_kernel %>
  echo: false
  warning: false
  message: false
  fig-dpi: 300
  freeze: auto

format:
  html:
<%% if pdf_web %%>
    embed-resources: true
<%% endif %%>
    code-fold: true
  pdf:
    pdf-engine: typst
    papersize: us-letter
    toc: false
    number-sections: false
    colorlinks: true
    linkcolor: "#1a2e4a"
    urlcolor: "#3d6b9e"
    citecolor: "#5b6b7f"
  docx:
    toc: false
"""

# ---------------------------------------------------------------------------
# "portfolio-light" / "portfolio-dark" templates — studio feature parity
# dressed in the Kizo07.github.io portfolio system.
#
# Architecture mirrors "studio" exactly (same scaffold params: hero/compact
# title layouts, eyebrow, organization, 0-6 metrics, accent override,
# exhibit labels, html/pdf/docx; same header markup + body markup + body
# CSS classes so agent-facing `.studio-grid` / `.studio-card` divs keep
# working). Only the dressing differs:
#   - light: warm paper #e5ddcc, ink #362e21, gold #8f621f, cyan #14756c
#   - dark:  near-black #0a0d12, ink #e7eaf0, gold #d9a54e, cyan #56cfc4
# Display type is Fraunces (portfolio serif) with Georgia fallback; Typst
# uses Georgia directly (installed locally — Typst cannot fetch webfonts).
# Mono is IBM Plex Mono in HTML (browser-fetched) and JetBrains Mono in
# Typst (installed locally).
# ---------------------------------------------------------------------------

PORTFOLIO_YML = """\
project:
  type: default
  output-dir: output

execute:
  jupyter: <% jupyter_kernel %>
  echo: false
  warning: false
  message: false
  fig-dpi: 300
  freeze: auto

number-sections: false

crossref:
  fig-title: Exhibit
  tbl-title: Table
  fig-prefix: Exhibit
  tbl-prefix: Table
  sec-prefix: Section

format:
  html:
    toc: <% toc %>
    toc-depth: 3
    theme:
      - brand
      - styles.scss
    include-before-body: assets/portfolio-header.html
    title-block-style: none
    code-fold: true
    code-tools: false
    link-external-newwindow: true
  typst:
    papersize: <% papersize %>
    mainfont: Inter
    fontsize: 10.5pt
    template-partials:
      - assets/typst-template.typ
      - assets/typst-show.typ
  docx:
    reference-doc: assets/reference-doc.docx
    toc: <% toc %>
"""

PORTFOLIO_LIGHT_BRAND_YML = """\
color:
  palette:
    paper: "#e5ddcc"
    panel: "#ebe3d2"
    ink: "#362e21"
    muted: "#6d6250"
    gold: "#8f621f"
    aqua: "#14756c"
    line: "#d3c8b0"
    slate: "#6d6250"
    mist: "#ebe3d2"
  foreground: "#362e21"
  background: "#e5ddcc"
  primary: "#8f621f"
  secondary: "#14756c"
  tertiary: "#6d6250"
  success: "#2c6e4a"
  info: "#14756c"
  warning: "#8f621f"
  danger: "#a44a44"
  light: "#ebe3d2"

typography:
  fonts:
    - family: Fraunces
      source: google
      weight: [400, 600]
    - family: Inter
      source: google
      weight: [400, 500, 600]
    - family: IBM Plex Mono
      source: google
  base:
    family: Inter
    size: 1rem
  headings:
    family: Fraunces
    weight: 600
    color: "#362e21"
  monospace: IBM Plex Mono
  monospace-inline:
    color: "#14756c"
    background-color: "#e0d7c4"
  monospace-block:
    background-color: panel

meta:
  name: ReportForge Portfolio Light
"""

PORTFOLIO_DARK_BRAND_YML = """\
color:
  palette:
    paper: "#0a0d12"
    panel: "#10151d"
    ink: "#e7eaf0"
    muted: "#9aa4b2"
    gold: "#d9a54e"
    aqua: "#56cfc4"
    line: "#1e2632"
    slate: "#9aa4b2"
    mist: "#10151d"
  foreground: "#e7eaf0"
  background: "#0a0d12"
  primary: "#d9a54e"
  secondary: "#56cfc4"
  tertiary: "#9aa4b2"
  success: "#3ecf8e"
  info: "#56cfc4"
  warning: "#d9a54e"
  danger: "#ef6a6a"
  light: "#10151d"

typography:
  fonts:
    - family: Fraunces
      source: google
      weight: [400, 600]
    - family: Inter
      source: google
      weight: [400, 500, 600]
    - family: IBM Plex Mono
      source: google
  base:
    family: Inter
    size: 1rem
  headings:
    family: Fraunces
    weight: 600
    color: "#e7eaf0"
  monospace: IBM Plex Mono
  monospace-inline:
    color: "#56cfc4"
    background-color: "#151b25"
  monospace-block:
    background-color: panel

meta:
  name: ReportForge Portfolio Dark
"""

PORTFOLIO_LIGHT_TYPT_TEMPLATE = r"""// report-forge "portfolio-light" — studio structure, portfolio light palette
#let portfolio_light(
  title: none, subtitle: none, authors: (), keywords: (),
  date: none, abstract: none, abstract-title: none, thanks: none,
  metrics: (), verdict: none, key-points: (), scenarios: (),
  organization: none, eyebrow: none,
  title-layout: "hero", accent: "#8f621f", confidential-mark: none,
  cols: 1, margin: (x: 0.82in, top: 0.72in, bottom: 0.9in),
  paper: "us-letter", lang: "en", region: "US",
  font: none, fontsize: 10.5pt, mathfont: none, codefont: none,
  linestretch: 1.15, sectionnumbering: none, linkcolor: none,
  citecolor: none, filecolor: none, pagenumbering: "1", doc,
) = {
  let paper-tone = rgb("#e5ddcc")
  let panel = rgb("#ebe3d2")
  let ink = rgb("#362e21")
  let muted = rgb("#6d6250")
  let hairline = rgb("#d3c8b0")
  let accent-color = rgb(accent)
  let link-ink = rgb("#14756c")

  set document(title: title, keywords: keywords)
  set page(
    paper: paper,
    margin: margin,
    fill: paper-tone,
    numbering: pagenumbering,
    header: context {
      let num = counter(page).at(here()).first()
      if num >= 2 {
        block(width: 100%)[
          #set text(size: 7.8pt, fill: muted, font: "JetBrains Mono")
          #grid(columns: (1fr, auto), align: horizon)[
            #if organization != none [#upper[#organization]] else if eyebrow != none [#upper[#eyebrow]] else [PORTFOLIO REPORT]
          ][#date]
          #line(length: 100%, stroke: 0.55pt + hairline)
        ]
      }
    },
    footer: context {
      let num = counter(page).at(here()).first()
      block(width: 100%)[
        #line(length: 100%, stroke: 0.55pt + hairline)
        #set text(size: 7.8pt, fill: muted, font: "JetBrains Mono")
        #grid(columns: (1fr, auto), align: horizon)[
          #if confidential-mark != none [#upper[#confidential-mark]] else []
        ][#num]
      ]
    },
  )
  set par(justify: true, leading: 0.74em, first-line-indent: 0em)
  set text(lang: lang, region: region, size: fontsize, fill: ink)
  set text(font: font) if font != none
  set heading(numbering: sectionnumbering)
  show link: set text(fill: link-ink)

  show heading.where(level: 1): it => block(above: 1.7em, below: 0.62em)[
    #grid(columns: (18pt, 1fr), column-gutter: 9pt, align: horizon)[
      #line(length: 18pt, stroke: 2.5pt + accent-color)
    ][
      #set text(font: "Georgia", size: 15pt, weight: "bold", fill: ink)
      #it.body
    ]
  ]
  show heading.where(level: 2): it => block(above: 1.1em, below: 0.42em)[
    #set text(font: "Georgia", size: 11.5pt, weight: "bold", fill: ink)
    #it.body
  ]
  show heading.where(level: 3): set text(font: "Georgia", size: 10pt, weight: "bold", fill: muted)

  show figure.caption: set text(size: 9pt, fill: ink)
  show figure.caption: set align(left)
  show quote: it => block(
    width: 100%,
    fill: panel,
    radius: 6pt,
    inset: (left: 16pt, right: 14pt, y: 10pt),
    stroke: (left: 3pt + accent-color),
  )[
    #set text(size: 10.5pt, style: "italic", fill: ink)
    #it
  ]
  show table: set table(
    stroke: 0.5pt + hairline,
    inset: (x: 6pt, y: 5pt),
    fill: (x, y) => if y == 0 { rgb("#d9cba6") } else if calc.rem(y, 2) == 0 { rgb("#e0d4ba") } else { panel },
  )
  show table: set text(size: 8.7pt)
  show table.cell.where(y: 0): set text(weight: "bold", fill: ink)
  show table.cell.where(x: 0): set text(weight: "bold")

  set page(margin: (x: margin.x, top: 0.5in, bottom: 0.6in))
  if title != none {
    if title-layout == "minimal" {
      // Plain title block: no card, no panel — kicker, title, rule, meta.
      block(width: 100%)[
        #set par(justify: false)
        #if eyebrow != none {
          line(length: 26pt, stroke: 1.4pt + accent-color)
          v(0.35em)
          set text(font: "JetBrains Mono", size: 8pt, weight: "medium", fill: accent-color)
          upper[#eyebrow]
          v(0.5em)
        }
        #set text(font: "Georgia", size: 24pt, weight: "bold", fill: ink, hyphenate: false)
        #title
        #if subtitle != none {
          v(0.3em)
          set text(size: 11pt, fill: muted)
          subtitle
        }
        #v(0.6em)
        #line(length: 40pt, stroke: 2pt + accent-color)
        #v(0.5em)
        #set text(size: 8.5pt, fill: muted)
        #grid(columns: (1fr, auto), align: horizon)[
          #if organization != none [#organization] else if authors != () [#authors.map(a => a.name).join(", ")] else []
        ][#date]
      ]
      v(0.9em)
    } else if title-layout == "compact" {
      block(
        width: 100%,
        inset: (left: 18pt, y: 15pt),
        stroke: (left: 4pt + accent-color),
      )[
        #set par(justify: false)
        #if eyebrow != none {
          line(length: 26pt, stroke: 1.4pt + accent-color)
          v(0.4em)
          set text(font: "JetBrains Mono", size: 8pt, weight: "medium", fill: accent-color)
          upper[#eyebrow]
          v(0.45em)
        }
        #set text(font: "Georgia", size: 23pt, weight: "bold", fill: ink, hyphenate: false)
        #title
        #if subtitle != none {
          v(0.35em)
          set text(size: 11pt, fill: muted)
          subtitle
        }
        #v(0.75em)
        #set text(size: 8.5pt, fill: muted)
        #grid(columns: (1fr, auto), align: horizon)[
          #if organization != none [#organization] else if authors != () [#authors.map(a => a.name).join(", ")] else []
        ][#date]
      ]
      v(1.0em)
    } else {
      block(
        width: 100%,
        fill: panel,
        radius: 10pt,
        inset: (left: 26pt, right: 24pt, top: 18pt, bottom: 15pt),
        stroke: (left: 7pt + accent-color, rest: 0.6pt + hairline),
      )[
        #set par(justify: false)
        #if eyebrow != none {
          line(length: 26pt, stroke: 1.4pt + accent-color)
          v(0.4em)
          set text(font: "JetBrains Mono", size: 8.5pt, weight: "medium", fill: accent-color)
          upper[#eyebrow]
          v(0.7em)
        }
        #set text(font: "Georgia", size: 22pt, weight: "bold", fill: ink, hyphenate: false)
        #title
        #if subtitle != none {
          v(0.5em)
          set text(size: 11pt, fill: muted)
          subtitle
        }
        #v(0.6em)
        #line(length: 46pt, stroke: 2.2pt + accent-color)
        #v(0.7em)
        #set text(size: 8.8pt, fill: muted)
        #grid(columns: (1fr, auto), align: horizon)[
          #if organization != none [#organization] else if authors != () [#authors.map(a => a.name).join(", ")] else []
        ][#date]
      ]
      v(0.7em)
    }
  }

  if metrics != () and metrics.len() > 0 {
    let n = metrics.len()
    let metric-cols = if n == 1 {
      (1fr,)
    } else if n == 2 or n == 4 {
      (1fr, 1fr)
    } else {
      (1fr, 1fr, 1fr)
    }
    grid(
      columns: metric-cols,
      column-gutter: 9pt,
      row-gutter: 9pt,
      ..metrics.map(metric => block(
        fill: panel,
        radius: 6pt,
        inset: (x: 12pt, y: 6pt),
        stroke: 0.55pt + hairline,
      )[
        #set text(font: "Georgia", size: 12pt, weight: "bold", fill: ink)
        #metric.value
        #linebreak()
        #set text(font: "JetBrains Mono", size: 7.7pt, fill: muted)
        #upper[#metric.label]
      ])
    )
    v(0.55em)
  }


  if verdict != none {
    block(
      width: 100%,
      fill: rgb("#e2d3ac"),
      radius: 6pt,
      inset: (x: 14pt, y: 7pt),
      stroke: (left: 3pt + accent-color),
    )[
      #set text(font: "JetBrains Mono", size: 7.7pt, weight: "medium", fill: accent-color)
      CONVICTION CALL
      #linebreak()
      #set text(size: 9.5pt, weight: "bold", fill: ink)
      #verdict
    ]
    v(0.55em)
  }

  if key-points != () and key-points.len() > 0 {
    grid(
      columns: (1fr, 1fr),
      column-gutter: 8pt,
      row-gutter: 8pt,
      ..key-points.map(p => block(
        fill: panel,
        radius: 6pt,
        inset: (x: 12pt, y: 6pt),
        stroke: 0.55pt + hairline,
      )[
        #set text(size: 8pt, fill: ink)
        #text(fill: accent-color)[◆ ]#p
      ])
    )
    v(0.55em)
  }

  if scenarios != () and scenarios.len() > 0 {
    grid(
      columns: (1fr, 1fr, 1fr),
      column-gutter: 8pt,
      ..scenarios.enumerate().map(((i, s)) => block(
        fill: panel,
        radius: 6pt,
        inset: (x: 12pt, y: 6pt),
        stroke: if i == 1 { 1pt + accent-color } else { 0.55pt + hairline },
      )[
        #set text(font: "JetBrains Mono", size: 7.7pt, fill: muted)
        #upper[#s.label]
        #linebreak()
        #set text(size: 12pt, weight: "bold", fill: ink)
        #s.value
        #linebreak()
        #set text(size: 7.5pt, fill: muted)
        #s.detail
      ])
    )
    v(0.55em)
  }

  if abstract != none {
    block(
      width: 100%,
      fill: rgb("#efe4cb"),
      radius: 7pt,
      inset: (x: 15pt, y: 8pt),
    )[
      #set text(size: 8.5pt, fill: muted)
      #abstract
    ]
    v(0.55em)
  }

  pagebreak(weak: true)
  set page(margin: margin)
  doc
}
"""

PORTFOLIO_DARK_TYPT_TEMPLATE = r"""// report-forge "portfolio-dark" — studio structure, portfolio dark palette
#let portfolio_dark(
  title: none, subtitle: none, authors: (), keywords: (),
  date: none, abstract: none, abstract-title: none, thanks: none,
  metrics: (), verdict: none, key-points: (), scenarios: (),
  organization: none, eyebrow: none,
  title-layout: "hero", accent: "#d9a54e", confidential-mark: none,
  cols: 1, margin: (x: 0.82in, top: 0.72in, bottom: 0.9in),
  paper: "us-letter", lang: "en", region: "US",
  font: none, fontsize: 10.5pt, mathfont: none, codefont: none,
  linestretch: 1.15, sectionnumbering: none, linkcolor: none,
  citecolor: none, filecolor: none, pagenumbering: "1", doc,
) = {
  let paper-tone = rgb("#0a0d12")
  let panel = rgb("#10151d")
  let ink = rgb("#e7eaf0")
  let muted = rgb("#9aa4b2")
  let hairline = rgb("#1e2632")
  let accent-color = rgb(accent)
  let link-ink = rgb("#56cfc4")

  set document(title: title, keywords: keywords)
  set page(
    paper: paper,
    margin: margin,
    fill: paper-tone,
    numbering: pagenumbering,
    header: context {
      let num = counter(page).at(here()).first()
      if num >= 2 {
        block(width: 100%)[
          #set text(size: 7.8pt, fill: muted, font: "JetBrains Mono")
          #grid(columns: (1fr, auto), align: horizon)[
            #if organization != none [#upper[#organization]] else if eyebrow != none [#upper[#eyebrow]] else [PORTFOLIO REPORT]
          ][#date]
          #line(length: 100%, stroke: 0.55pt + hairline)
        ]
      }
    },
    footer: context {
      let num = counter(page).at(here()).first()
      block(width: 100%)[
        #line(length: 100%, stroke: 0.55pt + hairline)
        #set text(size: 7.8pt, fill: muted, font: "JetBrains Mono")
        #grid(columns: (1fr, auto), align: horizon)[
          #if confidential-mark != none [#upper[#confidential-mark]] else []
        ][#num]
      ]
    },
  )
  set par(justify: true, leading: 0.74em, first-line-indent: 0em)
  set text(lang: lang, region: region, size: fontsize, fill: ink)
  set text(font: font) if font != none
  set heading(numbering: sectionnumbering)
  show link: set text(fill: link-ink)

  show heading.where(level: 1): it => block(above: 1.7em, below: 0.62em)[
    #grid(columns: (18pt, 1fr), column-gutter: 9pt, align: horizon)[
      #line(length: 18pt, stroke: 2.5pt + accent-color)
    ][
      #set text(font: "Georgia", size: 15pt, weight: "bold", fill: ink)
      #it.body
    ]
  ]
  show heading.where(level: 2): it => block(above: 1.1em, below: 0.42em)[
    #set text(font: "Georgia", size: 11.5pt, weight: "bold", fill: ink)
    #it.body
  ]
  show heading.where(level: 3): set text(font: "Georgia", size: 10pt, weight: "bold", fill: muted)

  show figure.caption: set text(size: 9pt, fill: ink)
  show figure.caption: set align(left)
  show quote: it => block(
    width: 100%,
    fill: panel,
    radius: 6pt,
    inset: (left: 16pt, right: 14pt, y: 10pt),
    stroke: (left: 3pt + accent-color),
  )[
    #set text(size: 10.5pt, style: "italic", fill: ink)
    #it
  ]
  show table: set table(
    stroke: 0.5pt + hairline,
    inset: (x: 6pt, y: 5pt),
    fill: (x, y) => if y == 0 { rgb("#1b2230") } else if calc.rem(y, 2) == 0 { rgb("#0d1219") } else { panel },
  )
  show table: set text(size: 8.7pt)
  show table.cell.where(y: 0): set text(weight: "bold", fill: ink)
  show table.cell.where(x: 0): set text(weight: "bold")

  set page(margin: (x: margin.x, top: 0.5in, bottom: 0.6in))
  if title != none {
    if title-layout == "minimal" {
      // Plain title block: no card, no panel — kicker, title, rule, meta.
      block(width: 100%)[
        #set par(justify: false)
        #if eyebrow != none {
          line(length: 26pt, stroke: 1.4pt + accent-color)
          v(0.35em)
          set text(font: "JetBrains Mono", size: 8pt, weight: "medium", fill: accent-color)
          upper[#eyebrow]
          v(0.5em)
        }
        #set text(font: "Georgia", size: 24pt, weight: "bold", fill: ink, hyphenate: false)
        #title
        #if subtitle != none {
          v(0.3em)
          set text(size: 11pt, fill: muted)
          subtitle
        }
        #v(0.6em)
        #line(length: 40pt, stroke: 2pt + accent-color)
        #v(0.5em)
        #set text(size: 8.5pt, fill: muted)
        #grid(columns: (1fr, auto), align: horizon)[
          #if organization != none [#organization] else if authors != () [#authors.map(a => a.name).join(", ")] else []
        ][#date]
      ]
      v(0.9em)
    } else if title-layout == "compact" {
      block(
        width: 100%,
        inset: (left: 18pt, y: 15pt),
        stroke: (left: 4pt + accent-color),
      )[
        #set par(justify: false)
        #if eyebrow != none {
          line(length: 26pt, stroke: 1.4pt + accent-color)
          v(0.4em)
          set text(font: "JetBrains Mono", size: 8pt, weight: "medium", fill: accent-color)
          upper[#eyebrow]
          v(0.45em)
        }
        #set text(font: "Georgia", size: 23pt, weight: "bold", fill: ink, hyphenate: false)
        #title
        #if subtitle != none {
          v(0.35em)
          set text(size: 11pt, fill: muted)
          subtitle
        }
        #v(0.75em)
        #set text(size: 8.5pt, fill: muted)
        #grid(columns: (1fr, auto), align: horizon)[
          #if organization != none [#organization] else if authors != () [#authors.map(a => a.name).join(", ")] else []
        ][#date]
      ]
      v(1.0em)
    } else {
      block(
        width: 100%,
        fill: panel,
        radius: 10pt,
        inset: (left: 26pt, right: 24pt, top: 18pt, bottom: 15pt),
        stroke: (left: 7pt + accent-color, rest: 0.6pt + hairline),
      )[
        #set par(justify: false)
        #if eyebrow != none {
          line(length: 26pt, stroke: 1.4pt + accent-color)
          v(0.4em)
          set text(font: "JetBrains Mono", size: 8.5pt, weight: "medium", fill: accent-color)
          upper[#eyebrow]
          v(0.7em)
        }
        #set text(font: "Georgia", size: 22pt, weight: "bold", fill: ink, hyphenate: false)
        #title
        #if subtitle != none {
          v(0.5em)
          set text(size: 11pt, fill: muted)
          subtitle
        }
        #v(0.6em)
        #line(length: 46pt, stroke: 2.2pt + accent-color)
        #v(0.7em)
        #set text(size: 8.8pt, fill: muted)
        #grid(columns: (1fr, auto), align: horizon)[
          #if organization != none [#organization] else if authors != () [#authors.map(a => a.name).join(", ")] else []
        ][#date]
      ]
      v(0.7em)
    }
  }

  if metrics != () and metrics.len() > 0 {
    let n = metrics.len()
    let metric-cols = if n == 1 {
      (1fr,)
    } else if n == 2 or n == 4 {
      (1fr, 1fr)
    } else {
      (1fr, 1fr, 1fr)
    }
    grid(
      columns: metric-cols,
      column-gutter: 9pt,
      row-gutter: 9pt,
      ..metrics.map(metric => block(
        fill: panel,
        radius: 6pt,
        inset: (x: 12pt, y: 6pt),
        stroke: 0.55pt + hairline,
      )[
        #set text(font: "Georgia", size: 12pt, weight: "bold", fill: ink)
        #metric.value
        #linebreak()
        #set text(font: "JetBrains Mono", size: 7.7pt, fill: muted)
        #upper[#metric.label]
      ])
    )
    v(0.55em)
  }


  if verdict != none {
    block(
      width: 100%,
      fill: rgb("#1d1a10"),
      radius: 6pt,
      inset: (x: 14pt, y: 7pt),
      stroke: (left: 3pt + accent-color),
    )[
      #set text(font: "JetBrains Mono", size: 7.7pt, weight: "medium", fill: accent-color)
      CONVICTION CALL
      #linebreak()
      #set text(size: 9.5pt, weight: "bold", fill: ink)
      #verdict
    ]
    v(0.55em)
  }

  if key-points != () and key-points.len() > 0 {
    grid(
      columns: (1fr, 1fr),
      column-gutter: 8pt,
      row-gutter: 8pt,
      ..key-points.map(p => block(
        fill: panel,
        radius: 6pt,
        inset: (x: 12pt, y: 6pt),
        stroke: 0.55pt + hairline,
      )[
        #set text(size: 8pt, fill: ink)
        #text(fill: accent-color)[◆ ]#p
      ])
    )
    v(0.55em)
  }

  if scenarios != () and scenarios.len() > 0 {
    grid(
      columns: (1fr, 1fr, 1fr),
      column-gutter: 8pt,
      ..scenarios.enumerate().map(((i, s)) => block(
        fill: panel,
        radius: 6pt,
        inset: (x: 12pt, y: 6pt),
        stroke: if i == 1 { 1pt + accent-color } else { 0.55pt + hairline },
      )[
        #set text(font: "JetBrains Mono", size: 7.7pt, fill: muted)
        #upper[#s.label]
        #linebreak()
        #set text(size: 12pt, weight: "bold", fill: ink)
        #s.value
        #linebreak()
        #set text(size: 7.5pt, fill: muted)
        #s.detail
      ])
    )
    v(0.55em)
  }

  if abstract != none {
    block(
      width: 100%,
      fill: rgb("#151b25"),
      radius: 7pt,
      inset: (x: 15pt, y: 8pt),
    )[
      #set text(size: 8.5pt, fill: muted)
      #abstract
    ]
    v(0.55em)
  }

  pagebreak(weak: true)
  set page(margin: margin)
  doc
}
"""

PORTFOLIO_DARK_TYPT_SHOW = """\
#show: doc => portfolio_dark(
$if(title)$
  title: [$title$],
$endif$
$if(subtitle)$
  subtitle: [$subtitle$],
$endif$
$if(by-author)$
  authors: (
$for(by-author)$
$if(it.name.literal)$
    ( name: [$it.name.literal$] ),
$endif$
$endfor$
  ),
$endif$
$if(date)$
  date: [$date$],
$endif$
$if(abstract)$
  abstract: [$abstract$],
$endif$
$if(organization)$
  organization: [$organization$],
$endif$
$if(eyebrow)$
  eyebrow: [$eyebrow$],
$endif$
$if(title-layout)$
  title-layout: "$title-layout$",
$endif$
$if(accent-typst)$
  accent: "#$accent-typst$",
$endif$
$if(confidential-mark)$
  confidential-mark: [$confidential-mark$],
$endif$
$if(metrics)$
  metrics: (
$for(metrics)$
    ( value: [$it.value$], label: [$it.label$] ),
$endfor$
  ),
$endif$
$if(verdict)$
  verdict: [$verdict$],
$endif$
$if(key-points)$
  key-points: (
$for(key-points)$
    [$it$],
$endfor$
  ),
$endif$
$if(scenarios)$
  scenarios: (
$for(scenarios)$
    ( label: [$it.label$], value: [$it.value$], detail: [$it.detail$] ),
$endfor$
  ),
$endif$
$if(papersize)$
  paper: "$papersize$",
$endif$
$if(mainfont)$
  font: ("$mainfont$",),
$endif$
$if(fontsize)$
  fontsize: $fontsize$,
$endif$
$if(section-numbering)$
  sectionnumbering: "$section-numbering$",
$endif$
  pagenumbering: $if(page-numbering)$"$page-numbering$"$else$none$endif$,
  doc,
)
"""

PORTFOLIO_LIGHT_STYLES_EXTRA = """
/* Portfolio light: warm paper, serif display, gold kicker. */
:root {
  --rf-accent: <% accent %>;
  --rf-paper: #e5ddcc;
  --rf-panel: #ebe3d2;
  --rf-panel-2: #e0d7c4;
  --rf-ink: #362e21;
  --rf-muted: #6d6250;
  --rf-faint: #7b7060;
  --rf-gold: #8f621f;
  --rf-aqua: #14756c;
  --rf-line: #d3c8b0;
}

body {
  background: var(--rf-paper);
  color: var(--rf-ink);
}

#title-block-header {
  display: none;
}

.rf-studio-header {
  --rf-accent: #8f621f;
  width: min(1120px, calc(100% - 3rem));
  margin: 2rem auto 3.5rem;
  border: 1px solid var(--rf-line);
  border-radius: 14px;
  background: var(--rf-panel);
  box-shadow: 0 18px 44px rgba(64, 52, 28, 0.16);
}

.rf-title-frame {
  padding: 4.2rem 4.5rem 2.4rem;
}

.rf-layout-compact .rf-title-frame {
  padding: 2.4rem 3rem 1.9rem;
}

.rf-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 1rem;
  color: var(--rf-accent);
  font-family: "IBM Plex Mono", "JetBrains Mono", monospace;
  font-size: 0.72rem;
  font-weight: 500;
  letter-spacing: 0.22em;
  text-transform: uppercase;
}

.rf-eyebrow::before {
  content: "";
  width: 26px;
  border-top: 2px solid var(--rf-accent);
}

.rf-display-title {
  max-width: 900px;
  margin: 0;
  color: var(--rf-ink);
  font-family: "Fraunces", Georgia, serif;
  font-size: clamp(2.5rem, 6vw, 4.6rem);
  font-weight: 600;
  letter-spacing: -0.01em;
  line-height: 1.04;
  overflow-wrap: anywhere;
}

.rf-layout-compact .rf-display-title {
  font-size: clamp(2rem, 4.5vw, 3.2rem);
}

.rf-display-subtitle {
  max-width: 760px;
  margin: 1.25rem 0 0;
  color: var(--rf-muted);
  font-size: clamp(1.05rem, 2vw, 1.3rem);
  line-height: 1.5;
}

.rf-title-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem 1.25rem;
  align-items: center;
  margin-top: 2rem;
  color: var(--rf-muted);
  font-family: "IBM Plex Mono", "JetBrains Mono", monospace;
  font-size: 0.78rem;
}

.rf-title-meta span + span::before,
.rf-title-meta span + time::before,
.rf-title-meta time::before {
  content: "·";
  margin-right: 1.25rem;
  color: var(--rf-line);
}

.rf-organization {
  color: var(--rf-ink);
  font-family: "Fraunces", Georgia, serif;
  font-weight: 600;
}

.rf-deck {
  max-width: 800px;
  margin: 2rem 0 0;
  padding-top: 1.35rem;
  border-top: 1px solid var(--rf-line);
  color: var(--rf-muted);
  font-size: 1rem;
  line-height: 1.65;
}

.rf-metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  border-top: 1px solid var(--rf-line);
  background: var(--rf-line);
}

.rf-metrics-1 {
  grid-template-columns: minmax(0, 1fr);
}

.rf-metrics-2,
.rf-metrics-4 {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.rf-metric {
  min-width: 0;
  padding: 1.35rem 1.65rem;
  background: var(--rf-panel);
}

.rf-metric-value {
  color: var(--rf-ink);
  font-family: "Fraunces", Georgia, serif;
  font-size: clamp(1.35rem, 3vw, 2rem);
  font-weight: 600;
  letter-spacing: -0.01em;
  overflow-wrap: anywhere;
}

.rf-metric-label {
  margin-top: 0.2rem;
  color: var(--rf-muted);
  font-family: "IBM Plex Mono", "JetBrains Mono", monospace;
  font-size: 0.7rem;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}
/* Cover infographics: verdict band, exec-summary key points, scenarios. */
.rf-verdict {
  display: flex;
  align-items: baseline;
  gap: 0.9rem;
  margin: 0;
  padding: 1.15rem 1.65rem;
  border-top: 1px solid var(--rf-line);
  border-left: 4px solid var(--rf-accent);
  background: color-mix(in srgb, var(--rf-accent) 10%, transparent);
}
.rf-verdict-tag {
  flex: none;
  color: var(--rf-accent);
  font-family: "IBM Plex Mono", "JetBrains Mono", monospace;
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}
.rf-verdict-text {
  color: var(--rf-ink);
  font-family: Fraunces, Georgia, serif;
  font-size: 1.12rem;
  font-weight: 600;
}
.rf-key-points {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  border-top: 1px solid var(--rf-line);
  background: var(--rf-line);
}
.rf-key-point {
  display: flex;
  gap: 0.7rem;
  align-items: flex-start;
  background: var(--rf-panel);
  padding: 1.1rem 1.4rem;
}
.rf-key-point-mark::before {
  content: "◆";
  color: var(--rf-accent);
  font-size: 0.8rem;
  line-height: 1.7;
}
.rf-key-point p {
  margin: 0;
  color: var(--rf-ink);
  font-size: 0.92rem;
  line-height: 1.55;
}
.rf-scenarios {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  border-top: 1px solid var(--rf-line);
  background: var(--rf-line);
}
.rf-scenario {
  background: var(--rf-panel);
  padding: 1.1rem 1.4rem;
}
.rf-scenario-base {
  background: color-mix(in srgb, var(--rf-accent) 8%, var(--rf-panel));
  box-shadow: inset 0 3px 0 var(--rf-accent);
}
.rf-scenario-label {
  color: var(--rf-muted);
  font-family: "IBM Plex Mono", "JetBrains Mono", monospace;
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}
.rf-scenario-value {
  margin: 0.15rem 0 0.3rem;
  color: var(--rf-ink);
  font-family: Fraunces, Georgia, serif;
  font-size: 1.6rem;
  font-weight: 600;
}
.rf-scenario-detail {
  color: var(--rf-muted);
  font-size: 0.82rem;
  line-height: 1.5;
}
/* Showcase tables — spreadsheet look: banded header, zebra rows, label
   column, tabular numerals. Wrap any Markdown table in ::: {.rf-showtable}
   (add .rf-nums-right to right-align data columns). */
.rf-showtable {
  margin: 1.5rem 0;
  border: 1px solid var(--rf-line);
  border-radius: 12px;
  overflow: hidden;
  background: var(--rf-panel);
}
.rf-showtable table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  margin: 0;
  font-size: 0.86rem;
}
.rf-showtable thead th {
  border-bottom: 2px solid var(--rf-accent);
  background: color-mix(in srgb, var(--rf-accent) 13%, transparent);
  color: var(--rf-ink);
  font-weight: 700;
  text-align: left;
  padding: 0.65rem 0.8rem;
  overflow-wrap: anywhere;
}
.rf-showtable tbody td {
  border-bottom: 1px solid var(--rf-line);
  color: var(--rf-ink);
  padding: 0.55rem 0.8rem;
  overflow-wrap: anywhere;
  font-variant-numeric: tabular-nums;
}
.rf-showtable tbody tr:nth-child(even) td {
  background: color-mix(in srgb, currentColor 4%, transparent);
}
.rf-showtable tbody tr:last-child td {
  border-bottom: none;
}
.rf-showtable tbody tr td:first-child {
  font-weight: 600;
}
.rf-showtable.rf-nums-right th:nth-child(n+2),
.rf-showtable.rf-nums-right td:nth-child(n+2) {
  text-align: right;
}
@media (max-width: 640px) {
  .rf-key-points,
  .rf-scenarios {
    grid-template-columns: minmax(0, 1fr);
  }
}


main.content {
  max-width: 880px;
}

main.content section.level1 > h1 {
  margin-top: 3.25rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--rf-line);
  color: var(--rf-ink);
  font-family: "Fraunces", Georgia, serif;
  font-size: clamp(1.75rem, 3vw, 2.4rem);
  font-weight: 600;
  letter-spacing: -0.01em;
}

main.content h2 {
  color: var(--rf-ink);
  font-family: "Fraunces", Georgia, serif;
  letter-spacing: -0.01em;
}

.studio-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin: 1.5rem 0;
}

.studio-card {
  padding: 1.35rem 1.45rem;
  border: 1px solid var(--rf-line);
  border-radius: 14px;
  background: var(--rf-panel);
  box-shadow: 0 18px 44px rgba(64, 52, 28, 0.1);
}

.studio-card h2 {
  margin-top: 0;
  font-size: 1.1rem;
}

/* Minimal title layout: no card chrome — plain themed title block. */
.rf-layout-minimal {
  background: transparent;
  border: none;
  box-shadow: none;
}

.rf-layout-minimal .rf-title-frame {
  padding: 1.5rem 0 0;
}

.rf-layout-minimal .rf-display-title {
  font-size: clamp(2rem, 4.5vw, 3.1rem);
}

.rf-layout-minimal .rf-metric-grid {
  background: transparent;
}

.rf-layout-minimal .rf-metric {
  background: transparent;
}

blockquote {
  margin: 1.6rem 0;
  padding: 1rem 1.25rem;
  border: 1px solid var(--rf-line);
  border-left: 5px solid var(--rf-accent, #8f621f);
  border-radius: 0 12px 12px 0;
  background: var(--rf-panel);
  color: var(--rf-ink);
  font-style: normal;
}

/* Tables — fixed layout keeps every table inside the content column
   (columns share the width per pandoc's colgroup, long cells wrap);
   roomy cells, aligned numerals, striped rows, tinted header. */
table {
  width: 100%;
  table-layout: fixed;
  border: 1px solid var(--rf-line);
  border-radius: 10px;
  background: var(--rf-panel);
  font-size: 0.88em;
  font-variant-numeric: tabular-nums;
  margin: 1.1rem 0;
  overflow-wrap: break-word;
}

thead {
  background: var(--rf-panel-2);
}

th,
td {
  padding: 0.55rem 0.8rem;
  text-align: left;
  vertical-align: top;
  overflow-wrap: break-word;
  border-bottom: 1px solid var(--rf-line);
}

th {
  font-weight: 700;
}

tbody tr:nth-child(even) {
  background: rgba(127, 140, 160, 0.09);
}

tbody tr:last-child td {
  border-bottom: none;
}

.figure-caption,
caption {
  color: var(--rf-muted);
  font-size: 0.85rem;
  text-align: left;
}

a {
  color: var(--rf-aqua);
}

code {
  color: var(--rf-aqua);
}

@media (max-width: 720px) {
  .rf-studio-header {
    width: min(100% - 1rem, 1120px);
    margin-top: 0.5rem;
  }

  .rf-title-frame,
  .rf-layout-compact .rf-title-frame {
    padding: 2.3rem 1.5rem 1.7rem 1.8rem;
  }

  .rf-display-title {
    font-size: clamp(2.15rem, 12vw, 3.2rem);
  }

  .rf-title-meta {
    display: grid;
    gap: 0.35rem;
  }

  .rf-title-meta span + span::before,
  .rf-title-meta span + time::before,
  .rf-title-meta time::before {
    content: none;
  }

  .rf-metric-grid,
  .studio-grid {
    grid-template-columns: 1fr;
  }

  .rf-metric {
    padding: 1rem 1.5rem;
  }
}

@media print {
  .rf-studio-header {
    box-shadow: none;
    break-inside: avoid;
  }
}
"""

PORTFOLIO_DARK_STYLES_EXTRA = """
/* Portfolio dark: near-black, serif display, gold kicker. */
:root {
  --rf-accent: <% accent %>;
  --rf-paper: #0a0d12;
  --rf-panel: #10151d;
  --rf-panel-2: #151b25;
  --rf-ink: #e7eaf0;
  --rf-muted: #9aa4b2;
  --rf-faint: #7d8795;
  --rf-gold: #d9a54e;
  --rf-aqua: #56cfc4;
  --rf-line: #1e2632;
  color-scheme: dark;
}

body {
  background: var(--rf-paper);
  color: var(--rf-ink);
}

#title-block-header {
  display: none;
}

.rf-studio-header {
  --rf-accent: #d9a54e;
  width: min(1120px, calc(100% - 3rem));
  margin: 2rem auto 3.5rem;
  border: 1px solid var(--rf-line);
  border-radius: 14px;
  background: var(--rf-panel);
  box-shadow: 0 18px 50px rgba(2, 6, 12, 0.45);
}

.rf-title-frame {
  padding: 4.2rem 4.5rem 2.4rem;
}

.rf-layout-compact .rf-title-frame {
  padding: 2.4rem 3rem 1.9rem;
}

.rf-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 1rem;
  color: var(--rf-accent);
  font-family: "IBM Plex Mono", "JetBrains Mono", monospace;
  font-size: 0.72rem;
  font-weight: 500;
  letter-spacing: 0.22em;
  text-transform: uppercase;
}

.rf-eyebrow::before {
  content: "";
  width: 26px;
  border-top: 2px solid var(--rf-accent);
}

.rf-display-title {
  max-width: 900px;
  margin: 0;
  color: var(--rf-ink);
  font-family: "Fraunces", Georgia, serif;
  font-size: clamp(2.5rem, 6vw, 4.6rem);
  font-weight: 600;
  letter-spacing: -0.01em;
  line-height: 1.04;
  overflow-wrap: anywhere;
}

.rf-layout-compact .rf-display-title {
  font-size: clamp(2rem, 4.5vw, 3.2rem);
}

.rf-display-subtitle {
  max-width: 760px;
  margin: 1.25rem 0 0;
  color: var(--rf-muted);
  font-size: clamp(1.05rem, 2vw, 1.3rem);
  line-height: 1.5;
}

.rf-title-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem 1.25rem;
  align-items: center;
  margin-top: 2rem;
  color: var(--rf-muted);
  font-family: "IBM Plex Mono", "JetBrains Mono", monospace;
  font-size: 0.78rem;
}

.rf-title-meta span + span::before,
.rf-title-meta span + time::before,
.rf-title-meta time::before {
  content: "·";
  margin-right: 1.25rem;
  color: var(--rf-line);
}

.rf-organization {
  color: var(--rf-ink);
  font-family: "Fraunces", Georgia, serif;
  font-weight: 600;
}

.rf-deck {
  max-width: 800px;
  margin: 2rem 0 0;
  padding-top: 1.35rem;
  border-top: 1px solid var(--rf-line);
  color: var(--rf-muted);
  font-size: 1rem;
  line-height: 1.65;
}

.rf-metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  border-top: 1px solid var(--rf-line);
  background: var(--rf-line);
}

.rf-metrics-1 {
  grid-template-columns: minmax(0, 1fr);
}

.rf-metrics-2,
.rf-metrics-4 {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.rf-metric {
  min-width: 0;
  padding: 1.35rem 1.65rem;
  background: var(--rf-panel);
}

.rf-metric-value {
  color: var(--rf-ink);
  font-family: "Fraunces", Georgia, serif;
  font-size: clamp(1.35rem, 3vw, 2rem);
  font-weight: 600;
  letter-spacing: -0.01em;
  overflow-wrap: anywhere;
}

.rf-metric-label {
  margin-top: 0.2rem;
  color: var(--rf-muted);
  font-family: "IBM Plex Mono", "JetBrains Mono", monospace;
  font-size: 0.7rem;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}
/* Cover infographics: verdict band, exec-summary key points, scenarios. */
.rf-verdict {
  display: flex;
  align-items: baseline;
  gap: 0.9rem;
  margin: 0;
  padding: 1.15rem 1.65rem;
  border-top: 1px solid var(--rf-line);
  border-left: 4px solid var(--rf-accent);
  background: color-mix(in srgb, var(--rf-accent) 10%, transparent);
}
.rf-verdict-tag {
  flex: none;
  color: var(--rf-accent);
  font-family: "IBM Plex Mono", "JetBrains Mono", monospace;
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}
.rf-verdict-text {
  color: var(--rf-ink);
  font-family: Fraunces, Georgia, serif;
  font-size: 1.12rem;
  font-weight: 600;
}
.rf-key-points {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  border-top: 1px solid var(--rf-line);
  background: var(--rf-line);
}
.rf-key-point {
  display: flex;
  gap: 0.7rem;
  align-items: flex-start;
  background: var(--rf-panel);
  padding: 1.1rem 1.4rem;
}
.rf-key-point-mark::before {
  content: "◆";
  color: var(--rf-accent);
  font-size: 0.8rem;
  line-height: 1.7;
}
.rf-key-point p {
  margin: 0;
  color: var(--rf-ink);
  font-size: 0.92rem;
  line-height: 1.55;
}
.rf-scenarios {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  border-top: 1px solid var(--rf-line);
  background: var(--rf-line);
}
.rf-scenario {
  background: var(--rf-panel);
  padding: 1.1rem 1.4rem;
}
.rf-scenario-base {
  background: color-mix(in srgb, var(--rf-accent) 8%, var(--rf-panel));
  box-shadow: inset 0 3px 0 var(--rf-accent);
}
.rf-scenario-label {
  color: var(--rf-muted);
  font-family: "IBM Plex Mono", "JetBrains Mono", monospace;
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}
.rf-scenario-value {
  margin: 0.15rem 0 0.3rem;
  color: var(--rf-ink);
  font-family: Fraunces, Georgia, serif;
  font-size: 1.6rem;
  font-weight: 600;
}
.rf-scenario-detail {
  color: var(--rf-muted);
  font-size: 0.82rem;
  line-height: 1.5;
}
/* Showcase tables — spreadsheet look: banded header, zebra rows, label
   column, tabular numerals. Wrap any Markdown table in ::: {.rf-showtable}
   (add .rf-nums-right to right-align data columns). */
.rf-showtable {
  margin: 1.5rem 0;
  border: 1px solid var(--rf-line);
  border-radius: 12px;
  overflow: hidden;
  background: var(--rf-panel);
}
.rf-showtable table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  margin: 0;
  font-size: 0.86rem;
}
.rf-showtable thead th {
  border-bottom: 2px solid var(--rf-accent);
  background: color-mix(in srgb, var(--rf-accent) 13%, transparent);
  color: var(--rf-ink);
  font-weight: 700;
  text-align: left;
  padding: 0.65rem 0.8rem;
  overflow-wrap: anywhere;
}
.rf-showtable tbody td {
  border-bottom: 1px solid var(--rf-line);
  color: var(--rf-ink);
  padding: 0.55rem 0.8rem;
  overflow-wrap: anywhere;
  font-variant-numeric: tabular-nums;
}
.rf-showtable tbody tr:nth-child(even) td {
  background: color-mix(in srgb, currentColor 4%, transparent);
}
.rf-showtable tbody tr:last-child td {
  border-bottom: none;
}
.rf-showtable tbody tr td:first-child {
  font-weight: 600;
}
.rf-showtable.rf-nums-right th:nth-child(n+2),
.rf-showtable.rf-nums-right td:nth-child(n+2) {
  text-align: right;
}
@media (max-width: 640px) {
  .rf-key-points,
  .rf-scenarios {
    grid-template-columns: minmax(0, 1fr);
  }
}


main.content {
  max-width: 880px;
}

main.content section.level1 > h1 {
  margin-top: 3.25rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--rf-line);
  color: var(--rf-ink);
  font-family: "Fraunces", Georgia, serif;
  font-size: clamp(1.75rem, 3vw, 2.4rem);
  font-weight: 600;
  letter-spacing: -0.01em;
}

main.content h2 {
  color: var(--rf-ink);
  font-family: "Fraunces", Georgia, serif;
  letter-spacing: -0.01em;
}

.studio-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin: 1.5rem 0;
}

.studio-card {
  padding: 1.35rem 1.45rem;
  border: 1px solid var(--rf-line);
  border-radius: 14px;
  background: var(--rf-panel);
  box-shadow: 0 18px 50px rgba(2, 6, 12, 0.35);
}

.studio-card h2 {
  margin-top: 0;
  font-size: 1.1rem;
}

/* Minimal title layout: no card chrome — plain themed title block. */
.rf-layout-minimal {
  background: transparent;
  border: none;
  box-shadow: none;
}

.rf-layout-minimal .rf-title-frame {
  padding: 1.5rem 0 0;
}

.rf-layout-minimal .rf-display-title {
  font-size: clamp(2rem, 4.5vw, 3.1rem);
}

.rf-layout-minimal .rf-metric-grid {
  background: transparent;
}

.rf-layout-minimal .rf-metric {
  background: transparent;
}

blockquote {
  margin: 1.6rem 0;
  padding: 1rem 1.25rem;
  border: 1px solid var(--rf-line);
  border-left: 5px solid var(--rf-accent, #d9a54e);
  border-radius: 0 12px 12px 0;
  background: var(--rf-panel);
  color: var(--rf-ink);
  font-style: normal;
}

/* Tables — fixed layout keeps every table inside the content column
   (columns share the width per pandoc's colgroup, long cells wrap);
   roomy cells, aligned numerals, striped rows, tinted header. */
table {
  width: 100%;
  table-layout: fixed;
  border: 1px solid var(--rf-line);
  border-radius: 10px;
  background: var(--rf-panel);
  font-size: 0.88em;
  font-variant-numeric: tabular-nums;
  margin: 1.1rem 0;
  overflow-wrap: break-word;
}

thead {
  background: var(--rf-panel-2);
}

th,
td {
  padding: 0.55rem 0.8rem;
  text-align: left;
  vertical-align: top;
  overflow-wrap: break-word;
  border-bottom: 1px solid var(--rf-line);
}

th {
  font-weight: 700;
}

tbody tr:nth-child(even) {
  background: rgba(127, 140, 160, 0.09);
}

tbody tr:last-child td {
  border-bottom: none;
}

.figure-caption,
caption {
  color: var(--rf-muted);
  font-size: 0.85rem;
  text-align: left;
}

a {
  color: var(--rf-aqua);
}

code {
  color: var(--rf-aqua);
}

@media (max-width: 720px) {
  .rf-studio-header {
    width: min(100% - 1rem, 1120px);
    margin-top: 0.5rem;
  }

  .rf-title-frame,
  .rf-layout-compact .rf-title-frame {
    padding: 2.3rem 1.5rem 1.7rem 1.8rem;
  }

  .rf-display-title {
    font-size: clamp(2.15rem, 12vw, 3.2rem);
  }

  .rf-title-meta {
    display: grid;
    gap: 0.35rem;
  }

  .rf-title-meta span + span::before,
  .rf-title-meta span + time::before,
  .rf-title-meta time::before {
    content: none;
  }

  .rf-metric-grid,
  .studio-grid {
    grid-template-columns: 1fr;
  }

  .rf-metric {
    padding: 1rem 1.5rem;
  }
}

@media print {
  .rf-studio-header {
    box-shadow: none;
    break-inside: avoid;
  }
}
"""

PORTFOLIO_LIGHT_TYPT_SHOW = """\
#show: doc => portfolio_light(
$if(title)$
  title: [$title$],
$endif$
$if(subtitle)$
  subtitle: [$subtitle$],
$endif$
$if(by-author)$
  authors: (
$for(by-author)$
$if(it.name.literal)$
    ( name: [$it.name.literal$] ),
$endif$
$endfor$
  ),
$endif$
$if(date)$
  date: [$date$],
$endif$
$if(abstract)$
  abstract: [$abstract$],
$endif$
$if(organization)$
  organization: [$organization$],
$endif$
$if(eyebrow)$
  eyebrow: [$eyebrow$],
$endif$
$if(title-layout)$
  title-layout: "$title-layout$",
$endif$
$if(accent-typst)$
  accent: "#$accent-typst$",
$endif$
$if(confidential-mark)$
  confidential-mark: [$confidential-mark$],
$endif$
$if(metrics)$
  metrics: (
$for(metrics)$
    ( value: [$it.value$], label: [$it.label$] ),
$endfor$
  ),
$endif$
$if(verdict)$
  verdict: [$verdict$],
$endif$
$if(key-points)$
  key-points: (
$for(key-points)$
    [$it$],
$endfor$
  ),
$endif$
$if(scenarios)$
  scenarios: (
$for(scenarios)$
    ( label: [$it.label$], value: [$it.value$], detail: [$it.detail$] ),
$endfor$
  ),
$endif$
$if(papersize)$
  paper: "$papersize$",
$endif$
$if(mainfont)$
  font: ("$mainfont$",),
$endif$
$if(fontsize)$
  fontsize: $fontsize$,
$endif$
$if(section-numbering)$
  sectionnumbering: "$section-numbering$",
$endif$
  pagenumbering: $if(page-numbering)$"$page-numbering$"$else$none$endif$,
  doc,
)
"""
