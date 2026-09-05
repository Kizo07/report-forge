# Proposed 2026 template additions — research note

Research date: 2026-09-04. Ranked candidates for new report-forge templates,
grounded in 2026 web sources (cited inline; ledger:
`/tmp/rf_trends_ledger.json`). Specs follow the conventions of
`engine.py::list_templates()` — name, one-line description, toc/numbering,
exhibit labels, formats. No code; proposals only.

Existing 8 templates (standard, memo, whitepaper, modern, studio,
portfolio-light, portfolio-dark, bespoke) are layout-first. All 12 proposals
below are *content-genre* templates — the fastest-growing category of 2026
research output, and the gap in the current roster.

---

## 1. `equity-note` — sell-side style equity research note

**Description:** Institutional equity research note: rating box (Buy/Hold/Sell,
price target, upside), investment thesis, business overview, industry position,
earnings forecasts, valuation triangulation (DCF + comps + precedents), risk
factors, financial summary tables. Exhibit labels, TOC off, numbered off; short
front page with rating summary; html/pdf/docx.

**Sections**
1. Rating summary — rating, price target, upside/downside, market cap, as-of
2. Investment thesis — 3-5 claims, each tied to an exhibit
3. Company overview — products, markets, leadership, recent news
4. Industry & competitive position — market share, peer benchmarking
5. Financial analysis — revenue/margin/EPS history and forecast table
6. Valuation — DCF, comps, precedent transactions; triangulated target
7. Catalysts — next 12 months, dated
8. Key risks — risk + mitigant pairs
9. Appendix — model assumptions, financial statements

**Why trending:** The equity research note remains the canonical format; 2026
guides enumerate it as the gold-standard structure (thesis → overview →
industry → financials → valuation → risks) [3][2][1]. AI-assisted production
(source-grounded, audit-ready notes) is now the standard workflow at research
teams, increasing note volume and demand for structured templates [1]. MiFID II
unbundling keeps pressure on smaller, higher-quality formatted notes [41].

## 2. `earnings-recap` — post-earnings flash note

**Description:** Same-day or next-morning earnings reaction note: beat/miss
scorecard vs consensus, revenue/EBITDA/EPS vs street, segment detail, guidance
revision table, estimate changes, rating/PT action. No TOC, no numbered
sections, exhibit labels; html/pdf.

**Sections**
1. Headline — beat/miss verdict in one line, stock reaction, as-of
2. Scorecard — revenue, EPS, margins vs consensus and prior year (table)
3. Segment detail — per-segment results and drivers
4. Guidance — new vs prior guidance, implied revisions (table)
5. Management commentary — earnings-call tone, key quotes
6. Estimate & rating action — what changed and why
7. What to watch — next quarter's swing factors

**Why trending:** Guidance revisions dominate 2026 earnings coverage — same-store
sales and full-year guide changes are the lead of most recaps (e.g. Wingstop
2026 SSS guide [50], Sweetgreen 2026 guidance [51], Starbucks Q3 2026 [52][54]).
The recap/flash format is one of the seven standard 2026 equity report types
(sell-side update) [3].

## 3. `thematic` — megatrend / AI / energy-transition theme report

**Description:** Thematic research report: theme definition, TAM sizing, value
chain map (enablers / beneficiaries / disruptors), exposure basket with risk
tiers, momentum indicators, policy tailwinds. TOC + numbered sections, exhibit
labels, title page; html/pdf/docx.

**Sections**
1. Executive summary — the theme in five sentences
2. Theme definition & why now — structural shift, catalysts
3. Market sizing — TAM/SAM trajectory exhibits
4. Value chain map — enablers, beneficiaries, disruptors (diagram + table)
5. Exposure basket — tickers mapped to theme leverage, risk tiers
6. Momentum & monitoring — mentions growth, capex flows, policy
7. Risks to the theme — hype cycles, regulation, substitution
8. Appendix — methodology, basket construction rules

**Why trending:** Thematic/trend reports are "increasingly popular" 2026
growth-investor format — TAM → value chain → basket structure [3]. Megatrend
framing (AI, energy transition, infrastructure divergence) anchors 2026
sell-side and consultant research [8][6].

## 4. `macro-outlook` — year-ahead / Fed & global macro outlook

**Description:** Annual or quarterly macro strategy outlook: growth/inflation/
rates base case, Fed and central-bank path, cross-asset allocation, regional
views, scenario fan (base/bull/bear with probabilities). TOC + numbered
sections, exhibit labels, title page; html/pdf/docx.

**Sections**
1. Executive summary — base case in one page
2. Growth & inflation outlook — exhibits with fan charts
3. Policy path — Fed/ECB/BOJ rates trajectory
4. Cross-asset views — equities, rates, credit, FX, commodities (table)
5. Regional views — US, Europe, EM
6. Scenarios — base/bull/bear with probabilities and market implications
7. Risks & watchlist — indicators that would change the call
8. Appendix — forecast table, methodology

**Why trending:** The year-ahead macro outlook is the highest-production 2026
research genre — Goldman 2026 Outlooks [31], J.P. Morgan 2026 Year-Ahead [32],
Deloitte's global economic outlook [34], and TD's Global Strategy Outlook [35].

## 5. `sector-outlook` — GICS sector deep dive

**Description:** Top-down sector report: sector size and growth drivers,
sub-segment analysis, competitive landscape and value chain, relative valuation
comps across the peer group, company case studies, top picks. TOC + numbered
sections, exhibit labels; html/pdf/docx.

**Sections**
1. Executive summary — sector stance (overweight/underweight) and picks
2. Sector overview — size, growth trajectory, key drivers
3. Sub-segment analysis — e.g. cloud/semis/security for tech
4. Competitive landscape & value chain — choke points, dependencies
5. Relative valuation — peer comps table, leaders vs laggards
6. Company case studies — 2-3 short profiles
7. Regulatory & policy risks
8. Top picks & allocation implications

**Why trending:** Sector/industry-focused reports are a distinct 2026 type —
macro overview → landscape map → relative valuation → case studies [3].

## 6. `quant-factor-brief` — factor / smart-beta performance brief

**Description:** Quant factor brief: factor return quilt, factor performance
tables vs benchmark, leadership rotation analysis, decile/tercile spread
exhibits, regime commentary, discipline/behavior framing. No TOC; exhibit
labels; html/pdf.

**Sections**
1. Headline — quarter's factor leadership in one line, as-of
2. Factor quilt — annual returns by factor, color-scaled (hero exhibit)
3. Factor detail — momentum, low-vol, quality, dividend, buyback, value
4. Leadership rotation — who went last-to-first, regime read
5. Spreads & deciles — long/short spread exhibits
6. Discipline framing — time-in-factor vs timing-the-factor
7. Appendix — factor definitions, ETF proxies, methodology

**Why trending:** Factor review quilts are an active 2026 publication format —
Nasdaq Dorsey Wright Q1 2026 Factor Review documents 2025→2026 factor rotation
(last-to-first leadership) [21]; smart-beta education/factor content remains a
staple ETF-research genre [22][24].

## 7. `digital-assets` — crypto / digital asset institutional note

**Description:** Digital-asset research note: market structure, spot-ETF and
institutional flows, on-chain metrics, regulatory timeline, adoption curve,
risk section sized for institutional allocators. TOC + numbered sections,
exhibit labels; html/pdf/docx.

**Sections**
1. Executive summary — market stance, as-of
2. Market structure — volumes, dominance, correlation to risk assets
3. Institutional flows — ETF flows, custody, allocator survey data
4. On-chain fundamentals — active addresses, staking, supply metrics
5. Regulatory timeline — enacted and pending, by jurisdiction
6. Adoption & use-case outlook — payments, tokenization, stablecoins
7. Risks — custody, protocol, regulatory, drawdown history
8. Appendix — data sources, definitions

**Why trending:** 2026 is framed as the "dawn of the institutional era" for
digital assets — Grayscale 2026 Digital Asset Outlook [17][19]; Coinbase/EY
2026 institutional investor digital-assets survey documents allocator adoption
[16]; institutional flow analysis is a standing 2026 beat [18][20].

## 8. `esg-sustainability` — ESG / sustainability research & disclosure report

**Description:** ESG research report: E/S/G pillar sections with metrics
tables, regulatory compliance matrix (CSRD/ISSB/SEC), emissions and transition
data, ESG-adjusted valuation, peer governance benchmarking. TOC + numbered
sections, exhibit labels; html/pdf/docx.

**Sections**
1. Executive summary — ESG stance and materiality call
2. Regulatory landscape — CSRD/ISSB/SEC applicability matrix (table)
3. Environmental — emissions, targets, transition plan exhibits
4. Social — labor, supply chain, community metrics
5. Governance — board independence, pay ratios, shareholder rights vs peers
6. ESG in valuation — assumptions adjusted, ESG multiples
7. Trajectory — commitments vs delivered progress year-over-year
8. Appendix — data sources, framework mapping

**Why trending:** ESG equity research is a standard 2026 institutional offering
(dedicated E/S/G sections feeding valuation) [3]; 2026 brings a wave of ESG
reporting regulation and compliance guidance — CSRD/ISSB/SEC updates [11][15],
framework/metrics guides [13].

## 9. `ipo-note` — IPO / pre-IPO valuation note

**Description:** IPO or pre-IPO research note: deal terms, pipeline context,
public-peer comps with IPO discounts, revenue multiples and down-round data for
late-stage privates, fair-value framework, listing timeline, risks. TOC off,
numbered off, exhibit labels; html/pdf/docx.

**Sections**
1. Deal summary — issuer, expected range, float, timeline
2. Company & growth profile — unit economics, cohort data if available
3. Market context — 2026 IPO window, pipeline, sentiment
4. Valuation — public comps, IPO-discount frameworks, scenario values
5. Private-market marks — last round, down-round prevalence, multiples
6. Catalysts & lockup calendar
7. Risks — governance, dual-class, dilution, path-to-profitability
8. Appendix — comp tables, assumptions

**Why trending:** 2026 pre-IPO analysis is an active genre — down rounds,
multiples, and exit frameworks for late-stage startups [26][30]; pre-IPO
unlisted-company coverage is a retail-investor research category in 2026 [28].

## 10. `chartbook` — monthly strategy chartbook

**Description:** Exhibit-led monthly chartbook: 12-20 full-width exhibits with
2-4 lines of read-through each, minimal prose, no long-form narrative. No TOC
(or one-page exhibit index), exhibit labels mandatory; html/pdf.

**Sections**
1. Cover & exhibit index
2. Macro dash — growth, inflation, rates exhibits
3. Markets dash — equities, credit spreads, FX, commodities
4. Positioning & flows
5. Breadth & technicals
6. One-page summary table of calls

**Why trending:** The monthly chartbook is a standing institutional format
(e.g. Jadwa Monthly Chartbooks [56]); 2026 year-ahead outputs are heavily
chart-led [31][32].

## 11. `valuation-dcf` — DCF model-centric deep dive

**Description:** Valuation workhorse note built around a defended DCF:
historical baseline exhibits, projection drivers each argued with evidence,
WACC build, sensitivity tornado/heatmap, cross-check vs comps. TOC + numbered
sections, exhibit labels; html/pdf/docx.

**Sections**
1. Valuation summary — intrinsic value range vs market, as-of
2. Historical baseline — 5-10yr growth/margin/working-capital trends
3. Forecast drivers — revenue, margins, capex, NWC; each assumption sourced
4. Discount rate — WACC build, risk premium justification
5. DCF output — FCF projection table, terminal value
6. Sensitivity — tornado chart, two-way heatmap
7. Cross-checks — comps and precedent triangulation
8. Risks to the valuation
9. Appendix — full model tables

**Why trending:** The DCF-centric report is one of the seven canonical 2026
equity report types — an "extended argument for a specific valuation," heavily
used in PE memoranda and deep-value work [3].

## 12. `technical-workpaper` — technical analysis workpaper

**Description:** Chart-driven technical workpaper: annotated price charts with
trendlines/levels, indicator panels (RSI, MACD, moving averages), support/
resistance tables, multi-timeframe scenario maps, invalidation levels per
scenario. No TOC, numbered off, exhibit labels; hero-width charts; html/pdf.

**Sections**
1. Setup summary — instrument, timeframe, bias, key levels, as-of
2. Weekly/daily structure — annotated trend chart (hero)
3. Levels table — support/resistance with confluence notes
4. Indicator panel — momentum, trend, volume exhibits
5. Scenarios — bull/base/bear paths with trigger and invalidation
6. Risk management — stop placement, position sizing notes

**Why trending:** Daily/multi-asset technical analysis remains a high-volume
2026 retail-and-desk format (daily FX technical forecasts [36]; TradingView's
chart-first research ecosystem [37]; technical strategies primers [39]).

---

## Runners-up (not in the top 12)

- `private-markets-q` — quarterly private markets/NAV note (NAV-financing
  market reports are an active 2026 genre [60]; private-markets momentum
  commentary [61]). Overlaps enough with `ipo-note` + `equity-note` to defer.
- `geopolitics-risk-brief` — risk-matrix format; feeds `macro-outlook`
  scenarios rather than standing alone.

## Source fit with the existing engine

- All 12 slots into the current Quarto scaffold + `list_templates()` shape:
  `{name, description, toc, number_sections, exhibit_labels, papersize,
  formats}`.
- `flagship-rules.md` conventions (Exhibit crossrefs, width tiers, engine
  builders, as-of on every number) apply unchanged; `chartbook` and
  `technical-workpaper` are the two that stress the width-tier rules hardest
  (hero-width density).

## Sources

## Sources

[1] https://www.hebbia.com/resources/equity-research-report — What Makes a Good Equity Research Report?
[2] https://corporatefinanceinstitute.com/resources/valuation/equity-research-report — Equity Research Report: Definition, Types, and Key Components
[3] https://pdf.ai/resources/equity-research-report-example — 7 Essential Equity Research Report Example Types for 2026
[6] https://www.linkedin.com/pulse/infrastructure-world-diverging-megatrends-rakse — Infrastructure in a World of Diverging Megatrends
[8] https://www.ey.com/en_gl/megatrends — Megatrends 2026 and beyond | EY - Global
[11] https://www.footprint-intelligence.com/blog/sustainability-regulation-updates-2026 — Global Sustainability Regulations 2026: Key ESG, CSRD ...
[13] https://www.iso20400.org/esg-reporting — ESG Reporting Guide 2026: Frameworks, Metrics & Strategy
[15] https://www.aranca.com/knowledge-library/articles/business-research/esg-reporting-requirements-2026 — ESG Reporting Requirements 2026 | CSRD, SEC and IFRS ...
[16] https://www.coinbase.com/institutional/research-insights/research/insights-reports/2026-institutional-investor-survey-e-and-y — 2026 Institutional Investor Digital Assets Survey - Coinbase
[17] https://research.grayscale.com/reports/2026-digital-asset-outlook-dawn-of-the-institutional-era — 2026 Digital Asset Outlook: Dawn of the Institutional Era
[18] https://quasa.io/media/crypto-institutional-era-trends-defining-digital-asset-investing-in-2026 — Crypto Institutional Era: 2026 Digital Asset Investing Trends
[19] https://trendsunplugged.io/wp-content/uploads/2026/01/Grayscale-2026-Digital-Asset-Outlook.pdf — 2026 Digital Asset Outlook: Dawn of the Institutional Era
[20] https://blog.amberdata.io/institutional-crypto-flows-2026-market-analysis — Institutional Crypto Flows & 2026 Market Analysis
[21] https://dorseywright.nasdaq.com/research/bigwire/2026/04/01/04-01-2026/q1-2026-factor-review-smart-beta-quilts — Q1 2026 Factor Review: Smart Beta Quilts | Nasdaq Dorsey Wright
[22] https://www.ishares.com/us/strategies/smart-beta-investing — Introducing Factors and Smart Beta | iShares - BlackRock
[24] https://www.ishares.com/us/investor-education/investment-strategies/what-is-smart-beta — Smart Beta Investing 101 - A Beginner's Guide | iShares
[26] https://eqvista.com/pre-ipo-late-stage-startups — Pre-IPO Startups in 2026: Down Rounds, Multiples & Exit
[28] https://www.ritscapital.com/blogs/wealth-management/pre-ipo-companies-in-india-2026 — Pre-IPO Stars of 2026: Top 5 Unlisted Indian Companies Investors...
[30] https://beyondotc.com/blog/pre-ipo-discount-to-expected-ipo-price-fair-value-frameworks — Pre-IPO Discount to Expected IPO Price: Fair Value Frameworks...
[31] https://www.goldmansachs.com/insights/outlooks/2026-outlooks — 2026 Outlooks | Goldman Sachs
[32] https://am.jpmorgan.com/content/dam/jpm-am-aem/global/en/2026+Year-Ahead+Investment+Outlook.pdf — 2026 Year-Ahead Investment Outlook - am.jpmorgan.com
[34] https://www.deloitte.com/us/en/insights/topics/economy/global-economic-outlook-2026.html — Global economic outlook 2026 | Deloitte Insights
[35] https://www.tdsecurities.com/ca/en/global-strategy-outlook-2026 — Global Strategy Outlook 2026: Carry On My Wayward Growth
[36] https://roboforex.com/beginners/analytics/forex-forecast/forex-technical-analysis/technical-forecast-daily-2026-09-04 — Daily technical analysis of EURUSD, USDJPY... - RoboForex
[37] https://www.tradingview.com — TradingView — Track All Markets
[39] https://www.investopedia.com/articles/active-trading/102914/technical-analysis-strategies-beginners.asp — investopedia.com/articles/active-trading/102914/technical-analysis...
[41] https://weconvene.com/mifid-ii-2026-corporate-access-update — MiFID II in 2026: What the Updated Regulatory Landscape Means for Corporate Access and Investor Relations - WeConvene
[50] https://seekingalpha.com/news/4620638-wingstop-anticipates-minus-4-percent-to-minus-6-percent-domestic-same-store-sales-in-2026 — Wingstop anticipates (-4%) to (-6%) domestic same-store sales ...
[51] https://seekingalpha.com/news/4558414-sweetgreen-outlines-2026-guidance-with-same-store-sales-decline-of-4-percent-to-2-percent — Sweetgreen outlines 2026 guidance with same-store sales ...
[52] https://qz.com/starbucks-earnings-same-store-sales-guidance-raised-073026 — Starbucks Q3 2026 earnings beat as same-store sales jump 7.9%
[54] https://www.cnbc.com/2026/07/29/starbucks-sbux-q3-2026-earnings.html — Starbucks (SBUX) Q3 2026 earnings - CNBC
[56] https://www.jadwa.com/en/monthly-chartbooks — Monthly Chartbooks | Jadwa
[60] https://www.rede-partners.com/news-insights-database/publication-rede-nav-2026?trk=article-ssr-frontend-pulse_little-text-block — Rede Partners | Rede Insights: NAV Financing Market Report 2026
[61] https://www.linkedin.com/posts/the-carlyle-group_a-light-may-be-emerging-at-the-end-of-the-activity-7424837392777359360-aFQc — Private Markets Show Renewed Momentum Amid Uncertainty | LinkedIn
