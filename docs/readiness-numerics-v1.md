# Numerical-consistency heuristics for `check_readiness` — v1 (quant)

Binds to `docs/milestone-a-contracts.md` §4.1 (numerical consistency, Milestone A automated column).
Owner: coder-2 (Task 1.4). Re-verify against contract V1 when `CONTRACT V1 READY` lands in #research.

Scope: heuristic, automatable consistency scans over `index.qmd` (frontmatter + body) only.
Non-goals (contract §4.1): no fact checking, no external data fetch, no PNG/OCR, no source
verification. Everything here flags internal disagreement between things the report itself says.
Posture: fuzzy matches are `warning` (for human confirmation); only exact-label conflicts and
arithmetic contradictions are `error`. Never silently pass (hard-fail principle).

## 1. Tokenizer / normalization (shared by all checks)

Pure stdlib `re`. Normalize before comparing:

- Strip `$`, `,` thousands separators; `USD`/`usd` suffix; unicode minus `−` → `-`.
- Percent forms unify: `percent|pct|%` → unit `pct`; `bps` → value/100 `pct`.
- Number patterns:
  - money: `[$]\s?-?[\d,]+(?:\.\d+)?(\s?USD)?` or `[\d,]+(?:\.\d+)?\s?USD`
  - percent: `-?[\d,]+(?:\.\d+)?\s?(?:percent|pct|%|bps?)`
  - bare number within 3 tokens of `close|price|spot|target|fair value` → treat as money.
- Dates: `\d{4}-\d{2}-\d{2}`; month-name forms (`Mar 2027`, `mid-2026`) parsed only in
  "as of / through / as of mid-" contexts; unparseable date mentions are ignored, not errors.
- Sign words: {minus, negative, fell, dropped, declined, lost, "-"} → neg;
  {plus, positive, gained, rose, up, rallied, "+"} → pos. Sign word adjacent to a number
  binds to it.

## 2. Quantity keys

Each extracted number gets a key `(kind, label_tokens, window_or_date)`:

- `kind` ∈ {spot, target, return_pct, vol_pct, weight_pct, other}.
- `label_tokens`: normalized content words near the number (ticker symbol(s), window words
  `21d|21-day|63d|126d|252d|12-month|monthly`, metric words `return|vol|close|target|capex|revenue`).
- Matching rule (conservative, false-error averse): two numbers are "the same quantity" only if
  their label token sets overlap on the discriminating token(s) (same ticker AND same window/metric
  word). If labels don't match, no comparison is made.

## 3. Checks

| Code | What fires | Severity |
| --- | --- | --- |
| `NUM-DERIVED-PCT` | Cover/frontmatter states `target $X (+Y%)` and a spot `$S` exists: `\|(Y − (X/S−1)·100)\| > 0.5` | error |
| `NUM-SPOT-DISAGREE` | All spot-price mentions (abstract, key-points, call blockquote, tables) keyed to same ticker+as-of: cluster values; clusters differing beyond tolerance (below) | error if Δ > 1.0, warning if 0.05 < Δ ≤ 1.0 (rounding gray zone) |
| `NUM-ASOF-FUTURE` | Any price-fact as-of date later than frontmatter `date:` | error |
| `NUM-ASOF-MIXED` | Price-fact as-of dates for same data family (tables + figure captions): mode vs outliers. Outlier → warning (one warning listing all, not per-row spam) | warning |
| `NUM-SIGN-CONFLICT` | Prose states a number with a sign word; the table row for the same keyed quantity has the opposite sign | error |
| `NUM-PROSE-TABLE` | Prose repeats a table quantity, same key, magnitude mismatch beyond tolerance (tolerance table below); hedged prose (`about|~|roughly|approximately`) gets the wide tolerance | warning |
| `NUM-SCENARIO-WEIGHTS` | Scenario/probability weights (frontmatter `scenarios` `value:` or body) sum ≠ 100 ± 0.5 | error |
| `NUM-SCENARIO-RECOMPUTE` | Weights × scenario return percents recompute a weighted return; a stated weighted figure disagrees by > 2.0pp (hedging-aware). If any scenario return is unparseable (e.g. tail "below $153"), cap severity at warning — the recompute is then bounded, not exact | warning; error when all scenario returns parse |
| `NUM-TARGET-AGREE` | Cover verdict/target vs scenario table base target: same key, Δ > 0 exact-value fields | error |
| `NUM-TABLE-TOTAL` | Explicit total/sum/net row: recompute from sibling rows, Δ beyond tolerance | error |

### Tolerances (explicit, in one place)

| Comparison | Pass (info at most) | Warning | Error |
| --- | --- | --- | --- |
| Precise quote ($254.98) vs rounded table cell (255) | Δ ≤ 0.5 | — | Δ > 0.5 with same key |
| Percent prose vs table, unhedged | Δ ≤ 0.05 | 0.05 < Δ ≤ 0.5 | Δ > 0.5 |
| Percent prose vs table, hedged ("about plus 7") | Δ ≤ 2.0 | 2.0 < Δ ≤ 4.0 | Δ > 4.0 |
| Derived cover % (target vs spot) | Δ ≤ 0.5 | — | Δ > 0.5 |
| Large aggregates (capex/revenue/cap, ≥ $1B) | rel Δ ≤ 1% | 1–3% | > 3% |

Exact equality fields: targets quoted to the dollar ($300), weights, counts — zero tolerance.

### Precedence / dedupe

One quantity with N disagreeing mentions → ONE issue, `detail` lists every location
(`index.qmd:LINE` or `frontmatter:key`). No per-mention spam. `section_id` set when the
primary location falls inside a known section.

### Issue shape (contract §4.1)

`{category: "numerical", severity, code, message, section_id?, detail?}`
Example:
```json
{"category": "numerical", "severity": "error", "code": "NUM-DERIVED-PCT",
 "message": "Cover says +18% to $310 but spot $254.98 implies +21.6%",
 "detail": "frontmatter:verdict vs index.qmd:17 (key-points) + index.qmd:36 (spot)"}
```

## 4. Grounding examples (from amzn-12m-muse-v2, real patterns)

- PASS/info: abstract "$254.98" vs table "AMZN close (USD, 2026-09-02) | 255" → Δ 0.02 ≤ 0.5.
- PASS/info: cover "+18%" vs derived 300/254.98 − 1 = +17.65% → Δ 0.35 ≤ 0.5.
- WOULD FIRE `NUM-SCENARIO-RECOMPUTE` (error: all parseable scenario returns; warning if tail
  unparseable): weights 20/50/25/5 × (−18/+18/+35/tail) recompute to 13.2–15.2% for any tail in
  [−20%, +20%]; prose says "about plus 7 percent" (index.qmd:72). Δ > 4pp hedged tolerance.
  Human confirms — exactly the contract's "flagged for human confirmation".
- WOULD FIRE `NUM-ASOF-MIXED` if one table caption read "As of 2026-09-01" vs mode 09-02.

## 5. Test fixture matrix for `tests/test_readiness.py` (numerics part)

Mutated copies of a small fixture QMD (never `reports/`):

1. derived-pct: cover "$310 (+18%)" with spot 254.98 → exactly 1 `NUM-DERIVED-PCT` error.
2. spot-drift: 254.98 in abstract, 256.00 in call blockquote → 1 `NUM-SPOT-DISAGREE` error.
3. as-of: `date: 2026-09-04`, one table "As of 2026-09-05" → 1 `NUM-ASOF-FUTURE` error;
   second fixture "As of 2026-09-01" vs mode → 1 `NUM-ASOF-MIXED` warning.
4. sign: prose "fell 1.64 percent" vs table row `+1.64` same key → 1 `NUM-SIGN-CONFLICT` error.
5. weights: scenarios 20/50/25 (no tail) → 1 `NUM-SCENARIO-WEIGHTS` error.
6. clean fixture (plan Task 1.4's 3-issue fixture: dangling ref + unreferenced chart +
   illustrative block) → ZERO numerical issues. Numerics must add no noise to it.
7. rounded-vs-precise (254.98 vs 255) → info only, `pass: true`.

## 6. Requires editorial review (listed, never computed)

Numbers inside chart PNGs (check captions instead), month-name/vague dates ("mid-2026"),
external claims (peer numbers, management statements), tail-scenario values below a floor.
