// report-forge "memo" — single-column business memo, house neutrals.
// Compact memo head (title, rule, author/date meta), running header/footer,
// house table grammar. No cover infographics, no two-column body.
// House table grammar (shared partial, scaffolded to assets/table-style.typ;
// resolved from the project root — quarto inlines partials into index.typ).
#import "assets/table-style.typ": table-grammar
#let memo(
  title: none, subtitle: none, authors: (),
  date: none, organization: none,
  accent: "#1a2e4a", confidential-mark: none,
  margin: (x: 1in, top: 0.9in, bottom: 1in),
  paper: "us-letter", lang: "en", region: "US",
  font: none, fontsize: 10.5pt, mathfont: none, codefont: none,
  sectionnumbering: none, pagenumbering: "1",
  toc: false, toc-title: [Contents], toc-depth: 3, toc-indent: 1em, doc,
) = {
  let paper-tone = rgb("#ffffff")
  let ink = rgb("#22303f")
  let muted = rgb("#5b6b7f")
  let hairline = rgb("#d5dbe3")
  let accent-color = rgb(accent)

  set document(title: title)
  set page(
    paper: paper,
    margin: margin,
    fill: paper-tone,
    numbering: if toc { "(i)" } else { pagenumbering },
    header: context {
      let num = counter(page).at(here()).first()
      if num >= 2 {
        block(width: 100%)[
          #set text(size: 7.8pt, fill: muted, font: "IBM Plex Mono")
          #grid(columns: (1fr, auto), align: horizon)[
            #if organization != none [#upper[#organization]] else [MEMORANDUM]
          ][#date]
          #line(length: 100%, stroke: 0.55pt + hairline)
        ]
      }
    },
    footer: context {
      let num = counter(page).at(here()).first()
      block(width: 100%)[
        #line(length: 100%, stroke: 0.55pt + hairline)
        #set text(size: 7.8pt, fill: muted, font: "IBM Plex Mono")
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
  show math.equation: set text(font: mathfont) if mathfont != none
  show raw: set text(font: codefont) if codefont != none

  show heading.where(level: 1): it => block(above: 1.5em, below: 0.55em)[
    #grid(columns: (14pt, 1fr), column-gutter: 8pt, align: horizon)[
      #line(length: 14pt, stroke: 2.2pt + accent-color)
    ][
      #set text(font: "Space Grotesk", size: 13pt, weight: "bold", fill: ink)
      #it.body
    ]
  ]
  show heading.where(level: 2): it => block(above: 1.0em, below: 0.4em)[
    #set text(font: "Space Grotesk", size: 11pt, weight: "bold", fill: ink)
    #it.body
  ]
  show heading.where(level: 3): set text(font: "Space Grotesk", size: 10pt, weight: "bold", fill: muted)

  // Tables/figures: house grammar from the shared partial (applied where
  // the body is placed below) — 8.7pt, hairline rules, zebra rows.

  if title != none {
    block(width: 100%)[
      #set par(justify: false)
      #set text(font: "IBM Plex Mono", size: 8pt, weight: "medium", fill: accent-color)
      MEMORANDUM
      #v(0.4em)
      #set text(font: "Space Grotesk", size: 20pt, weight: "bold", fill: ink, hyphenate: false)
      #title
      #if subtitle != none {
        v(0.3em)
        set text(size: 11pt, fill: muted)
        subtitle
      }
      #v(0.55em)
      #line(length: 100%, stroke: 0.7pt + hairline)
      #v(0.45em)
      #set text(size: 8.5pt, fill: muted)
      #grid(columns: (1fr, auto), align: horizon)[
        #if authors != () [#authors.map(a => a.name).join(", ")] else if organization != none [#organization] else []
      ][#date]
    ]
    v(0.8em)
  }

  // Optional contents page: roman-numbered front matter, then restart
  // arabic body numbering.
  if toc {
    pagebreak()
    outline(title: toc-title, depth: toc-depth, indent: toc-indent)
    pagebreak()
    counter(page).update(1)
  }
  // Front matter was roman — restart explicit arabic body numbering at
  // function scope (a set inside the if block would revert after it).
  set page(numbering: "1") if toc

  table-grammar(
    doc,
    rule: hairline,
    header: rgb("#dde4ec"),
    alt: rgb("#f2f5f8"),
    body: paper-tone,
    ink: ink,
  )
}
