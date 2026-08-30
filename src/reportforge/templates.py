"""Embedded Quarto templates used by reportforge.scaffold."""

QUARTO_YML = """\
project:
  type: default
  output-dir: output

execute:
  jupyter: reportforge
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
title: "<% title %>"
<%% if subtitle%%>
subtitle: "<% subtitle %>"
<%% endif%%>
<%% if author%%>
author: "<% author %>"
<%% endif%%>
date: <% date %>
date-format: long
abstract: |
  <% abstract %>
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
title: "<% title %>"
<%% if author%%>
author: "<% author %>"
<%% endif%%>
date: <% date %>
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
title: "<% title %>"
<%% if subtitle%%>
subtitle: "<% subtitle %>"
<%% endif%%>
<%% if author%%>
author: "<% author %>"
<%% endif%%>
date: <% date %>
date-format: long
abstract: |
  <% abstract %>
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
  jupyter: reportforge
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
  confidential-mark: "$confidential-mark$",
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
title: "<% title %>"
<%% if subtitle%%>
subtitle: "<% subtitle %>"
<%% endif%%>
<%% if author%%>
author: "<% author %>"
<%% endif%%>
<%% if firm%%>
firm: "<% firm %>"
<%% endif%%>
<%% if confidential_mark%%>
confidential-mark: "<% confidential_mark %>"
<%% endif%%>
date: <% date %>
date-format: long
abstract: |
  <% abstract %>
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
