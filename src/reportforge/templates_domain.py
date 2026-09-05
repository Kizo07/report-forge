"""Domain-specific report bodies (finance research template family).

Each constant is a Quarto .qmd body for a typed research document:
earnings recaps, sector and macro outlooks, thematic deep dives, quant
factor briefs, technical briefs, ESG reviews, and crypto/digital-asset
notes. They ride the standard pipeline (QUARTO_YML in templates.py):
typst-engine PDF, exhibit cross-references, optional TOC + numbered
sections per spec in engine.list_templates().

Conventions (docs/flagship-rules.md):
- Number ladders go in tables, never sentences; every number keeps its
  unit and an as-of.
- Plain exhibit names from the data; no invented labels or shouty headers.
- Exhibits embed via Markdown images with {#fig-exN}; prose cites
  @fig-exN. Chunk-level `#| label:`/`#| fig-cap:` break Quarto's
  typst-PDF path ("unknown variable: quarto_super") — never use them.
- Exports: width 9in, font 16, scale=3 (~450 DPI effective at print).
"""

# Shared exhibit chunk skeleton — only data + title + accent vary per body.
_CHUNK_HEADER = """\
```{python}
# Writes the print-quality exhibit PNG referenced by @fig-example above.
# NOTE: do NOT use `#| label:` / `#| fig-cap:` on executable chunks here —
# Quarto's typst-PDF path emits an undefined `quarto_super` helper for
# them. Markdown embeds with {#fig-x} + caption text carry the metadata.
import pandas as pd
import plotly.express as px
"""

_FRONTMATTER = """\
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
reportforge-template: "<% template_name %>"
---
"""

EARNINGS_RECAP_QMD = _FRONTMATTER + """
# Results at a glance {-}

Lead with the print: revenue, margins, and EPS against consensus, each
with its unit and as-of. One sentence on what drove the surprise, one on
why it matters for the position.

| Metric | Reported | Consensus | Surprise |
|--------|---------:|----------:|---------:|
| Revenue ($mm) | 5,240 | 5,110 | +2.5% |
| Gross margin (%) | 61.8 | 60.9 | +90 bps |
| EPS ($) | 2.43 | 2.31 | +5.2% |

: Headline results vs consensus, quarter reported as of the report date. {#tbl-results}

> **What changed.** The one line that separates this print from the prior
> quarter's trend.

# Segment detail

Walk each reporting segment: growth rate, margin, and the driver behind
both. Keep segments in a table; read through the two that moved the
consolidated number.

![Segment revenue growth, trailing eight quarters.](assets/example-chart.png){#fig-example width=85%}

As @fig-example shows, the mix shift concentrates in one segment. State
the observation, then the interpretation, then the implication.

# Margins and cost drivers

Bridge gross margin and operating margin in basis points. Name the cost
lines that moved — price, mix, input costs, one-offs — and say which are
durable.

# Guidance and outlook

Compare management's guide to the print and to the street. Flag any
change in capital-return language (buyback, dividend) with its size.

# Market reaction

Price and volume reaction by the close after the print, plus the move in
the closest read-through names. Reaction that contradicts the surprise
usually means positioning, not fundamentals — say which.

# Risks to the read

1. The first risk to this interpretation, with its observable
   early-warning indicator.
2. The data revision or disclosure gap that could flip the segment read.

# Method and data {.appendix}

Source filings, consensus provider, as-of timestamps, and conventions
(reported vs organic, GAAP vs adjusted).

""" + _CHUNK_HEADER + """\
df = pd.DataFrame({
    "quarter": [f"Q{i % 4 + 1}'{22 + i // 4}" for i in range(8)],
    "cloud": [18, 21, 24, 28, 31, 35, 39, 44],
    "retail": [40, 41, 39, 42, 43, 41, 44, 43],
    "ads": [12, 13, 15, 14, 16, 18, 17, 19],
})
fig = px.line(df, x="quarter", y=["cloud", "retail", "ads"], markers=True)
fig.update_layout(template="plotly_white", title="Segment revenue ($mm)", font=dict(size=16))
fig.write_image("assets/example-chart.png", width=9 * 100, height=4.5 * 100, scale=3)
```
"""

SECTOR_OUTLOOK_QMD = _FRONTMATTER + """
# Executive summary

Three to five sentences: where the sector sits in the cycle, the one
call that matters for the next four quarters, and the positioning it
implies.

# Where we stand

Top-down setup: demand, pricing power, inventory, and capacity
utilization across the sector. Each claim gets a unit and an as-of.

# Relative performance

![Sector total return vs S&P 500, trailing 24 months.](assets/example-chart.png){#fig-example width=85%}

As @fig-example shows, relative strength concentrated after the inflection
in orders. Name the months that mattered and what triggered them.

| Subsector | Return 12m (%) | Weight (%) | EPS revision (%) |
|-----------|---------------:|-----------:|-----------------:|
| Semis | +34.2 | 28 | +8.1 |
| Hardware | +12.6 | 22 | +2.4 |
| Software | +6.1 | 35 | -1.2 |
| IT services | +3.8 | 15 | +0.6 |

: Subsector scorecard, as of the report date. {#tbl-subsectors}

# Subsector readings

Two to four sentences per subsector that moved: the driver, the
valuation read, and the preferred exposure. Subsectors that did nothing
get one line or nothing.

# Valuation

Where the sector trades versus its own history and the market: forward
P/E, EV/EBITDA, and the earnings-revision breadth behind them. A
multiple without the earnings path is a number, not a view.

# Positioning implications

Concrete: overweight/underweight versus benchmark, the names or baskets
that express it, and the crowding check before sizing.

# Risks

1. The macro risk that cuts across every subsector, with its indicator.
2. The sector-specific risk, and the level at which the call is wrong.

# Method and data {.appendix}

Index definitions, return conventions (total return, USD), revision
data source, and as-of dates.

""" + _CHUNK_HEADER + """\
df = pd.DataFrame({
    "month": pd.period_range("2024-09", periods=24, freq="M").astype(str),
    "sector": 100 * (1 + 0.01 * pd.Series(range(24)).cumsum()
                     + 0.02 * pd.Series([(i % 6 - 2.5) / 4 for i in range(24)]).cumsum()),
    "market": 100 * (1 + 0.006 * pd.Series(range(24)).cumsum()),
})
fig = px.line(df, x="month", y=["sector", "market"], markers=False)
fig.update_layout(template="plotly_white", title="Sector vs market, indexed to 100", font=dict(size=16))
fig.write_image("assets/example-chart.png", width=9 * 100, height=4.5 * 100, scale=3)
```
"""

THEMATIC_DEEPDIVE_QMD = _FRONTMATTER + """
# Key takeaways {-}

- **Takeaway one** — the theme's size and growth in one claim, with units.
- **Takeaway two** — the catalyst that makes it investable now.
- **Takeaway three** — the preferred exposure and the main way it fails.

# The theme, defined

What is in scope, what is not, and the conventions used to size it.
Define terms precisely before using them; a theme nobody can bound is a
slogan.

## Why now

The regulatory, cost, or technology inflection that moved this from
slide-deck to income statement, dated.

# Sizing the opportunity

![Theme revenue pool, actual and projected ($bn).](assets/example-chart.png){#fig-example width=85%}

As @fig-example shows, the revenue pool compounds through the decade.
Give the base-year size, the terminal size, and the CAGR — in a table,
with the source for each.

| Layer | 2025 ($bn) | 2030E ($bn) | CAGR (%) |
|-------|-----------:|------------:|---------:|
| Hardware | 84 | 211 | 20.2 |
| Software & services | 31 | 118 | 30.7 |
| Total | 115 | 329 | 23.4 |

: Revenue pool by layer, base year 2025. {#tbl-sizing}

# Demand drivers

The two or three forces that pull spend: who pays, for what, and the
unit economics of adoption. Each driver gets a measurable proxy.

# Value chain and beneficiaries

Where the margin pools sit by layer, and which companies capture them.
Distinguish capacity owners, integrators, and IP holders — they carry
different risk.

# Public-market exposure

The listed proxies: pure-plays, diversifieds with exposure, and picks-
and-shovels. Revenue exposure as a percent of sales, in a table.

# Roadmap and signposts

Dated milestones that confirm or kill the thesis — product launches,
capacity additions, procurement deadlines. Each signpost names the
observable that will mark it.

# Risks to the theme

1. The adoption risk, with the signpost that would reveal it first.
2. The policy/subsidy risk, and the exposure that depends on it.

# Method and data {.appendix}

Sizing method, source hierarchy, projection assumptions, and as-of dates.

""" + _CHUNK_HEADER + """\
df = pd.DataFrame({
    "year": list(range(2023, 2031)),
    "actual": [72, 88, 115, None, None, None, None, None],
    "projected": [None, None, 115, 146, 186, 236, 289, 329],
})
fig = px.line(df, x="year", y=["actual", "projected"], markers=True)
fig.update_layout(template="plotly_white", title="Theme revenue pool ($bn)", font=dict(size=16))
fig.write_image("assets/example-chart.png", width=9 * 100, height=4.5 * 100, scale=3)
```
"""

MACRO_OUTLOOK_QMD = _FRONTMATTER + """
# Executive summary

The one-paragraph view: growth path, inflation path, policy response,
and the asset call each implies. Every quantitative claim carries a
unit and an as-of.

# Nowcast

Where the economy sits today: nowcast GDP for the current quarter,
run-rate inflation, and the labor gauges. Keep the indicator table
tight and dated.

| Indicator | Latest | Prior | As-of |
|-----------|-------:|-----:|------|
| GDP nowcast, QoQ SAAR (%) | 1.9 | 2.2 | report date |
| Core PCE, YoY (%) | 2.6 | 2.7 | report date |
| Payrolls 3m avg (k) | 142 | 168 | report date |

: Key indicators at a glance. {#tbl-nowcast}

# Growth

The consumption-investment-external decomposition and the fiscal
impulse. State what would raise the nowcast and what would cut it.

# Inflation

Core versus headline, goods versus services, and the wage-cost pass-
through. Base effects get their own paragraph with the months they roll
off.

![Core inflation decomposition, contributions in pp.](assets/example-chart.png){#fig-example width=85%}

As @fig-example shows, the disinflation ran through goods first. Say
whether the remaining stick is shelter, wages, or margins — they imply
different policy paths.

# Policy and rates

The expected policy path versus the market curve, and the reaction
function behind the view. FX follows from rate differentials — state
the direction and the pair.

# Scenarios

Bear, base, and bull with probabilities, the variable that separates
them, and the asset expression of each. Probabilities sum to 100.

| Scenario | Probability (%) | GDP path | Policy | Asset read |
|----------|----------------:|----------|--------|------------|
| Bear | 25 | Stall | Cuts 150 bps | Duration wins |
| Base | 55 | Trend | Cuts 75 bps | Carry with quality tilt |
| Bull | 20 | Re-acceleration | Holds | Cyclicals and credit |

: Scenario grid for the outlook horizon. {#tbl-scenarios}

# Asset implications

Rates, credit, FX, and equities under the base case, with the hedge
that pays best if the bear case arrives.

# Method and data {.appendix}

Data sources, vintage dates, nowcast method, and forecast conventions.

""" + _CHUNK_HEADER + """\
df = pd.DataFrame({
    "month": pd.period_range("2024-01", periods=32, freq="M").astype(str),
    "goods": [0.4, 0.3, 0.2, 0.1, 0.0, -0.1, -0.1, 0.0, 0.1, 0.1, 0.2, 0.2] + [0.1] * 20,
    "services": [2.2, 2.2, 2.1, 2.1, 2.0, 2.0, 1.9, 1.9, 1.9, 1.8, 1.8, 1.8] + [1.7] * 20,
})
fig = px.line(df, x="month", y=["goods", "services"], markers=False)
fig.update_layout(template="plotly_white", title="Core CPI contributions (pp, YoY)", font=dict(size=16))
fig.write_image("assets/example-chart.png", width=9 * 100, height=4.5 * 100, scale=3)
```
"""

QUANT_FACTOR_BRIEF_QMD = _FRONTMATTER + """
# Signal summary {-}

One short paragraph: what the signal measures, the asset universe, the
rebalance cadence, and the headline performance stat with its window.

| Stat | Value | Window |
|------|------:|--------|
| Long-short Sharpe | 0.84 | 2016–2026 |
| Information coefficient | 0.047 | monthly |
| Annual turnover (x) | 3.8 | trailing 12m |
| Drawdown (%) | -11.2 | 2020 peak-to-trough |

: Signal headline statistics. {#tbl-stats}

# Definition

The signal in one sentence, then the precise formula in words: inputs,
transformation, neutralizations, and the window. A signal that cannot
be restated exactly is not a signal.

# Construction

Universe filters, weighting, rebalance timing, and execution
assumptions. State the neutralization set (sector, beta, size) and the
treatment of missing data.

# Performance

![Cumulative long-short return, net of costs.](assets/example-chart.png){#fig-example width=85%}

As @fig-example shows, the signal earned its keep in the high-
dispersion regime. Read through the decay: where the edge concentrated
by year and by regime, in a table.

# Costs and turnover

Turnover by decile, the cost model, and the breakeven spread in bps
per unit of turnover. The gross-to-net bridge belongs here.

# Combinations

Correlation with the existing book's signals, and the marginal
contribution after combination. A signal that duplicates what the book
already owns earns nothing — show the residual.

# Robustness

Specification checks: alternative windows, neutralization sets, and
universe filters. The honest section — report the specifications where
the signal weakens, not only where it holds.

# Risks

1. The regime that kills the edge, with the monitoring metric.
2. The capacity limit, and the AUM at which the net curve flattens.

# Method and data {.appendix}

Data vintages, point-in-time conventions, and the backtest engine.

""" + _CHUNK_HEADER + """\
import numpy as np

rng = np.random.default_rng(7)
months = pd.period_range("2016-01", periods=120, freq="M").astype(str)
ret = np.cumsum(rng.normal(0.0055, 0.018, 120))
df = pd.DataFrame({"month": months, "long_short": 100 * (1 + ret)})
fig = px.line(df, x="month", y="long_short")
fig.update_layout(template="plotly_white", title="Long-short cumulative return (net, 100 = start)", font=dict(size=16))
fig.write_image("assets/example-chart.png", width=9 * 100, height=4.5 * 100, scale=3)
```
"""

TECHNICAL_BRIEF_QMD = _FRONTMATTER + """
# Setup {-}

The instrument, the timeframe, and the setup in one sentence: trend
state, the key level in price with its unit, and the trigger being
watched. As-of date on every level.

# Trend and levels

![Price with 50- and 200-day averages, 18 months.](assets/example-chart.png){#fig-example width=85%}

As @fig-example shows, price reclaimed the 200-day average and held it
on the retest. Mark support and resistance in a table, not prose.

| Level | Price ($) | Type | Provenance |
|-------|----------:|------|-----------|
| 232 | Resistance | Prior high | 2026-07 |
| 214 | Support | 200-day average | report date |
| 198 | Support | Gap fill | 2026-05 |

: Key levels, as of the report date. {#tbl-levels}

# Momentum

Rate-of-change and momentum oscillators on the traded timeframe, plus
the divergence check. Momentum that confirms price gets one paragraph;
divergence gets two.

# Volatility and volume

Realized volatility by window, the implied-realized spread, and volume
on the last swing versus its average. Volatility states the risk on
the stop distance — carry the number into the position sizing.

# Scenario levels

Bear, base, and bull price paths with the invalidation level that ends
each. Probabilities sum to 100.

| Scenario | Probability (%) | Path | Trigger |
|----------|----------------:|------|---------|
| Bear | 30 | 198 then 185 | Close below 198 |
| Base | 50 | 214 → 232 | Holds 214 on volume |
| Bull | 20 | 232 → 250 | Breakout above 232 |

: Scenario grid with triggers. {#tbl-scenarios}

# Invalidation

The exact condition that voids the read, the level it sits at, and
what the chart says if it breaks. A technical brief without an
invalidation level is a hope, not a read.

# Method and data {.appendix}

Data source, session conventions, and the definition of every
indicator used.

""" + _CHUNK_HEADER + """\
import numpy as np

days = pd.bdate_range("2025-03-01", periods=380)
close = 180 + np.cumsum(np.random.default_rng(3).normal(0.09, 1.1, 380))
df = pd.DataFrame({"close": close}, index=days)
df["ma50"] = df["close"].rolling(50).mean()
df["ma200"] = df["close"].rolling(200).mean()
fig = px.line(df, x=df.index, y=["close", "ma50", "ma200"])
fig.update_layout(template="plotly_white", title="Price with 50/200-day averages ($)", font=dict(size=16))
fig.write_image("assets/example-chart.png", width=9 * 100, height=4.5 * 100, scale=3)
```
"""

ESG_SUSTAINABILITY_QMD = _FRONTMATTER + """
# Executive summary

The company's ESG profile in three sentences: where it leads its
sector, where it lags, and the financially material issue that could
move the equity or the cost of capital.

# Rating profile

| Pillar | Company | Sector median | Trend |
|--------|--------:|--------------:|-------|
| Environmental | 62 | 48 | Improving |
| Social | 55 | 54 | Flat |
| Governance | 71 | 59 | Improving |
| Composite | 62 | 53 | Improving |

: Rating profile vs sector, as of the report date. {#tbl-ratings}

Read through the gap: one pillar drives the composite. Ratings
diverge across providers — name the provider and date.

# Environmental

Emissions intensity, energy mix, water, and waste with units and
as-of dates. Scope coverage matters: state whether Scope 3 is
estimated, modeled, or absent.

![Emissions intensity vs sector, indexed.](assets/example-chart.png){#fig-example width=85%}

As @fig-example shows, the intensity gap widened after the sector's
2023 cleanup lagged. Tie the trajectory to the capital plan that pays
for it.

# Social

Workforce safety and turnover, product liability, and community
exposure. Report the incident rates, not the policy documents.

# Governance

Board independence and refresh rate, dual-class or related-party
flags, and compensation alignment. Governance red flags discount every
other disclosure — lead with them if present.

# Controversies

Open controversies with severity, date, and status. Distinguish
alleged from adjudicated; both matter, at different weights.

# Disclosure quality

Reporting framework, assurance level, and the gaps between what the
sector peers disclose and what this company does. Missing data is a
finding — name the missing lines.

# Financial materiality

The bridge to numbers: carbon price exposure, capex share aligned or
misaligned, and the revenue at regulatory risk. End with the
valuation question the ESG profile raises.

# Method and data {.appendix}

Rating provider and vintage, controversy sources, and estimation
conventions.

""" + _CHUNK_HEADER + """\
df = pd.DataFrame({
    "year": list(range(2019, 2026)),
    "company": [128, 121, 112, 104, 96, 88, 81],
    "sector": [130, 127, 123, 118, 113, 108, 104],
})
fig = px.line(df, x="year", y=["company", "sector"], markers=True)
fig.update_layout(template="plotly_white", title="Emissions intensity, indexed to 2019 = 100", font=dict(size=16))
fig.write_image("assets/example-chart.png", width=9 * 100, height=4.5 * 100, scale=3)
```
"""

CRYPTO_DIGITAL_QMD = _FRONTMATTER + """
# Executive summary

Where the asset class sits: total market cap with its as-of, the
regime that governs flows, and the one call for the horizon. Every
price and flow figure carries its unit and timestamp.

# Market structure

Structure first, price second: realized and implied volatility,
funding, basis, and open interest. State the venue-set the numbers
come from — CEX prints differ from aggregated tape.

| Metric | Latest | 30d avg | As-of |
|--------|-------:|--------:|------|
| Total market cap ($tn) | 3.4 | 3.3 | report date |
| Perp funding, majors (bps/8h) | 3.1 | 1.8 | report date |
| BTC futures basis, 3m (%) | 8.4 | 7.1 | report date |

: Market structure gauges. {#tbl-structure}

# Flows

Spot ETF creations and redemptions by day and issuer, exchange net
flows, and stablecoin issuance as the marginal dollar. Direction and
magnitude — in a table.

![Spot ETF net flows, trailing 60 sessions ($mm).](assets/example-chart.png){#fig-example width=85%}

As @fig-example shows, the flow regime flipped in the middle of the
window. Read through the issuer concentration: one issuer's print is
not the market's vote.

# On-chain readings

Active addresses, exchange balances, and the holder-cohort moves that
matter for the asset covered. Define every metric before using it —
on-chain conventions vary by data vendor.

# Protocol fundamentals

For the asset covered: fee revenue, staking yield, token emission,
and the supply schedule. Real yield net of emission is the number;
gross yield is marketing.

# Regulatory watch

The dated events that reprice the class: filings, enforcement,
legislation, and election calendars. Each event gets its date and the
direction of its expected impact.

# Scenarios

Bear, base, and bull with probabilities, the variable that separates
them, and the level that marks each.

| Scenario | Probability (%) | BTC range ($k) | Driver |
|----------|----------------:|---------------:|--------|
| Bear | 30 | 48–62 | Risk-off, ETF outflows |
| Base | 50 | 62–84 | Range, stable flows |
| Bull | 20 | 84–105 | Policy break, supply squeeze |

: Scenario grid for the outlook horizon. {#tbl-scenarios}

# Risks

1. The liquidity risk unique to the venue set, with the depth numbers.
2. The regulatory tail, and the position size it justifies.

# Method and data {.appendix}

Venues, data vendors, UTC conventions, and the treatment of weekend
prints.

""" + _CHUNK_HEADER + """\
import numpy as np

days = pd.bdate_range("2026-06-01", periods=60)
flows = np.random.default_rng(11).normal(180, 320, 60)
df = pd.DataFrame({"flow_mm": flows}, index=days)
fig = px.bar(df, x=df.index, y="flow_mm")
fig.update_layout(template="plotly_white", title="Spot ETF net flows ($mm/day)", font=dict(size=16))
fig.write_image("assets/example-chart.png", width=9 * 100, height=4.5 * 100, scale=3)
```
"""

# engine.scaffold_report dispatch: standard/memo/whitepaper stay in
# templates.py; these typed bodies join the same lookup.
DOMAIN_BODY_TEMPLATES = {
    "earnings-recap": EARNINGS_RECAP_QMD,
    "sector-outlook": SECTOR_OUTLOOK_QMD,
    "thematic-deepdive": THEMATIC_DEEPDIVE_QMD,
    "macro-outlook": MACRO_OUTLOOK_QMD,
    "quant-factor-brief": QUANT_FACTOR_BRIEF_QMD,
    "technical-brief": TECHNICAL_BRIEF_QMD,
    "esg-sustainability": ESG_SUSTAINABILITY_QMD,
    "crypto-digital": CRYPTO_DIGITAL_QMD,
}
