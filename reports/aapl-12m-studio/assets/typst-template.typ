// report-forge "studio" — flexible editorial Typst template
#let studio(
  title: none, subtitle: none, authors: (), keywords: (),
  date: none, abstract: none, abstract-title: none, thanks: none,
  metrics: (), organization: none, eyebrow: none,
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

  show figure.caption: set text(size: 8.7pt, fill: muted)
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
  show table: set table(stroke: 0.5pt + hairline, inset: 6pt)
  show table.cell.where(y: 0): set text(weight: "bold", fill: ink)

  if title != none {
    if title-layout == "compact" {
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
        inset: (left: 26pt, right: 24pt, top: 32pt, bottom: 28pt),
        stroke: (left: 7pt + accent-color, rest: 0.6pt + hairline),
      )[
        #set par(justify: false)
        #if eyebrow != none {
          set text(font: "Space Grotesk", size: 8.5pt, weight: "medium", fill: accent-color)
          upper[#eyebrow]
          v(0.7em)
        }
        #set text(font: "Space Grotesk", size: 29pt, weight: "bold", fill: ink, hyphenate: false)
        #title
        #if subtitle != none {
          v(0.5em)
          set text(size: 12pt, fill: muted)
          subtitle
        }
        #v(1.25em)
        #line(length: 46pt, stroke: 2.2pt + accent-color)
        #v(0.7em)
        #set text(size: 8.8pt, fill: muted)
        #grid(columns: (1fr, auto), align: horizon)[
          #if organization != none [#organization] else if authors != () [#authors.map(a => a.name).join(", ")] else []
        ][#date]
      ]
      v(1.15em)
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
        inset: (x: 12pt, y: 10pt),
        stroke: 0.55pt + hairline,
      )[
        #set text(font: "Space Grotesk", size: 15pt, weight: "bold", fill: ink)
        #metric.value
        #linebreak()
        #set text(size: 7.7pt, fill: muted)
        #upper[#metric.label]
      ])
    )
    v(0.85em)
  }

  if abstract != none {
    block(
      width: 100%,
      fill: rgb("#efefff"),
      radius: 7pt,
      inset: (x: 15pt, y: 12pt),
    )[
      #set text(size: 9.6pt, fill: muted)
      #abstract
    ]
    v(0.9em)
  }

  doc
}
