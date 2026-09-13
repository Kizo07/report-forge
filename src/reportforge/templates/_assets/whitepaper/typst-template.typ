// report-forge "whitepaper" article — Quarto stock typst article + title page

#let article(
  title: none,
  subtitle: none,
  authors: none,
  keywords: (),
  date: none,
  abstract-title: none,
  abstract: none,
  thanks: none,
  titlepage: false,
  firm: none,
  cols: 1,
  lang: "en",
  region: "US",
  font: none,
  fontsize: 11pt,
  title-size: 1.5em,
  subtitle-size: 1.25em,
  heading-family: none,
  heading-weight: "bold",
  heading-style: "normal",
  heading-color: black,
  heading-line-height: 0.65em,
  mathfont: none,
  codefont: none,
  linestretch: 1,
  sectionnumbering: none,
  linkcolor: none,
  citecolor: none,
  filecolor: none,
  toc: false,
  toc_title: none,
  toc_depth: none,
  toc_indent: 1.5em,
  doc,
) = {
  // Set document metadata for PDF accessibility
  set document(title: title, keywords: keywords)
  set document(
    author: authors.map(author => content-to-string(author.name)).join(", ", last: " & "),
  ) if authors != none and authors != ()
  set par(
    justify: true,
    leading: linestretch * 0.65em
  )
  set text(lang: lang,
           region: region,
           size: fontsize)
  set text(font: font) if font != none
  show math.equation: set text(font: mathfont) if mathfont != none
  show raw: set text(font: codefont) if codefont != none

  set heading(numbering: sectionnumbering)

  show link: set text(fill: rgb(content-to-string(linkcolor))) if linkcolor != none
  show ref: set text(fill: rgb(content-to-string(citecolor))) if citecolor != none
  show link: this => {
    if filecolor != none and type(this.dest) == label {
      text(this, fill: rgb(content-to-string(filecolor)))
    } else {
      text(this)
    }
   }

  if titlepage and title != none {
    // Dedicated cover: everything alone on page 1, body breaks to page 2.
    page(margin: (x: 2.5cm, y: 4cm))[
      #v(1fr)
      #align(center)[
        #if firm != none [
          #text(size: 0.85em, weight: "semibold", tracking: 0.14em)[#upper[#firm — INVESTMENT RESEARCH]]
          #v(1.6em)
        ]
        #set par(leading: heading-line-height) if heading-line-height != none
        #set text(font: heading-family) if heading-family != none
        #set text(weight: heading-weight)
        #set text(style: heading-style) if heading-style != "normal"
        #set text(fill: heading-color) if heading-color != black
        #text(size: 2.2em)[#title]
        #(if subtitle != none {
          v(0.5em)
          text(size: 1.2em, weight: "regular", fill: black)[#subtitle]
        })
        #v(1.5em)
        #line(length: 32%, stroke: 0.8pt + rgb("#c9a227"))
      ]
      #v(1.5em)
      #if authors != none and authors != () {
        grid(
          columns: (1fr,) * calc.min(authors.len(), 3),
          row-gutter: 1.5em,
          ..authors.map(author =>
              align(center)[
                #author.name \
                #author.affiliation \
                #author.email
              ]
          )
        )
      }
      #if date != none [
        #align(center)[#block(inset: 1em)[
          #date
        ]]
      ]
      #v(1fr)
    ]
    // Abstract opens page 2; no repeated title block.
    if abstract != none {
      block(above: 0em, below: 1.5em, inset: 1.5em)[
        #text(weight: "semibold")[#abstract-title] #h(1em) #abstract
      ]
    }
  } else {
    let has-title-block = title != none or (authors != none and authors != ()) or date != none or abstract != none
    if has-title-block {
      place(
        top,
        float: true,
        scope: "parent",
        clearance: 4mm,
        block(below: 1em, width: 100%)[

          #if title != none {
            align(center, block(inset: 2em)[
              #set par(leading: heading-line-height) if heading-line-height != none
              #set text(font: heading-family) if heading-family != none
              #set text(weight: heading-weight)
              #set text(style: heading-style) if heading-style != "normal"
              #set text(fill: heading-color) if heading-color != black

              #text(size: title-size)[#title #if thanks != none {
                footnote(thanks, numbering: "*")
                counter(footnote).update(n => n - 1)
              }]
              #(if subtitle != none {
                parbreak()
                text(size: subtitle-size)[#subtitle]
              })
            ])
          }

          #if authors != none and authors != () {
            let count = authors.len()
            let ncols = calc.min(count, 3)
            grid(
              columns: (1fr,) * ncols,
              row-gutter: 1.5em,
              ..authors.map(author =>
                  align(center)[
                    #author.name \
                    #author.affiliation \
                    #author.email
                  ]
              )
            )
          }

          #if date != none {
            align(center)[#block(inset: 1em)[
              #date
            ]]
          }

          #if abstract != none {
            block(inset: 2em)[
            #text(weight: "semibold")[#abstract-title] #h(1em) #abstract
            ]
          }
        ]
      )
    }
  }

  if toc {
    let title = if toc_title == none {
      auto
    } else {
      toc_title
    }
    block(above: 0em, below: 2em)[
    #outline(
      title: toc_title,
      depth: toc_depth,
      indent: toc_indent
    );
    ]
  }

  doc
}

#set table(
  inset: 6pt,
  stroke: none
)
