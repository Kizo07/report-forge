// report-forge shared table grammar — house Typst table style.
//
// Import from a family template and wrap the body:
//   #import "assets/table-style.typ": table-grammar
//   table-grammar(doc, rule: hairline, header: ..., alt: ..., body: ..., ink: ...)
// (Table styling must wrap `doc`: bare show rules in an imported file do
// not leak into the importing scope, so a plain `#include` cannot work.)
//
// Grammar: 8.7pt body, hairline rules, zebra rows, left caption.
// quartable is LaTeX-only and intentionally not used here.
#let table-grammar(
  doc,
  rule: rgb("#d5dde4"),
  header: rgb("#d3dde6"),
  alt: rgb("#d8e1e9"),
  body: rgb("#e7edf2"),
  ink: rgb("#1b2634"),
) = {
  show figure.caption: set text(size: 9pt, fill: ink)
  show figure.caption: set align(left)
  show table: set table(
    stroke: 0.5pt + rule,
    inset: (x: 6pt, y: 5pt),
    fill: (x, y) => if y == 0 { header } else if calc.rem(y, 2) == 0 { alt } else { body },
  )
  show table: set text(size: 8pt, hyphenate: true)
  show table.cell: set par(justify: false, leading: 0.4em)
  show table.cell.where(y: 0): set text(weight: "bold", fill: ink)
  show table.cell.where(x: 0): set text(weight: "bold")
  // Breakable hyphens (table-hyphen-break): Typst never breaks the
  // numeric-hyphen run in date strings, so a zero-width space after
  // each hyphen adds a break opportunity. Only takes effect when a
  // cell would otherwise overflow its track.
  show table: it => {
    show "-": "-\u{200B}"
    it
  }
  doc
}
