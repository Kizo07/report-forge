// report-forge "modern" conf() — custom typst template partial
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
