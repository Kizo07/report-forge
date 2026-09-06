// report-forge "portfolio-light" — studio structure, portfolio light palette
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
  set page(columns: 2)
  show table: it => block(breakable: false, it)
  doc
}
