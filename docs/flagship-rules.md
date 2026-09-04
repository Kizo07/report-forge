# Flagship report rules (QuantFlow visual flagships)

Snapshot of the voice, sizing, and verification rules that steered the
AMZN v2 run (2026-09-04). The live quant-desk skill carries the same rules;
this file is the committed mirror so a fresh checkout reproduces them.

## Prose voice — human desk analyst

- Short declarative sentences, one claim each (~20 words typical). One
  longer sentence per paragraph is allowed for flow — staccato everywhere
  reads as robotic as clause-stacks do.
- Plain exhibit names from the data ("AMZN 12-month returns vs peers").
  Never invented labels ("Price Hero", "Momentum Ladder").
- Banned: shouty headers ("THESIS IN ONE PARAGRAPH"),
  "delve/tapestry/landscape", "announces itself/adjudicates",
  "forensic attention", "honestly labeled", triple-parallel flourishes,
  non-English slips.
- Number ladders go in a table, not a sentence. Every number needs a unit
  and an as-of. Paragraphs close with the implication — vary the closer
  ("So what", "The read", "Bottom line", "Implication"), never the same
  one twice in a row.
- Alt text uses `&` ("S&P 500"), never "and" ("S and P").

## Figure sizing tiers

- Hero/technicals/fan: width=100%. Standard single chart: width=85%.
  Simple charts (<=12 bars, pies, single series): width=70% or paired
  two-up in `::: {layout-ncol=2}` at width=100% of the column.
- Every embed carries an explicit width. Never >2 width=100% figures
  without prose between. No lone chart as a section's only content —
  2-4 lines of read-through per exhibit.
- Exports (scale=2): hero 1600x800, standard 1400x700, compact 1200x550.
  Retina headroom is fine; past 2200x1000 is bloat.
- Every figure gets `{#fig-exN}` + fig-cap (native Exhibit numbering).
  Never hand-write `*Exhibit N*` paragraphs. Prose refers to `@fig-exN`.

## Chart identity

- Engine builders (`alpha_engine.viz`) with `theme="quantflow-light"` on
  light pages / `"quantflow-dark"` on dark — never hand-rolled plotly for
  standard exhibits, never silent matplotlib substitution (quote the full
  export error, stringify scalar Timestamps, retry once).
- Captions burned into pixels via
  `save_figure(..., caption_text=caption(asof, source))`.

## Pre-render checklist (in order — each prints pass/fail)

1. Word count meets the run's gate (mechanically counted, never estimated).
2. `python scripts/figure_lint.py <project-dir>` clean — size, crossrefs,
   voice tics, alt text, per-theme accent pixels, light brightness floor.
3. Render requested formats; artifact check (HTML img count, PDF pages,
   zero "Unable to display", zero dark charts on light).
4. `reportforge_publish_report` + `present_files`; final answer leads
   with the prediction, then absolute artifact paths.
