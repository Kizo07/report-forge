"""Engine readiness cluster (Phase 3 split; see plan §4).

All engine-level references go through `_E` (deferred package
attribute access) so monkeypatching `reportforge.engine.<name>`
keeps working.
"""

from __future__ import annotations

from reportforge import engine as _E

import re
from pathlib import Path
import yaml
from reportforge import manifest as manifest_mod



def _missing_work_summary(root: Path, view: dict | None, artifacts: list[dict]) -> dict:
    """Compact readiness projection (§4.2): unrendered formats + error counts."""
    if view is None:
        return {"manifest": False, "unrendered_formats": [], "error_counts": {}}
    rendered = {a["id"] for a in artifacts}
    unrendered = [f for f in view.get("formats", [])
                  if f in ("html", "pdf", "docx") and f not in rendered]
    return {"manifest": True, "unrendered_formats": unrendered, "error_counts": {}}


def _num_value(token: str) -> float | None:
    t = token.replace("$", "").replace(",", "").strip()
    t = re.sub(r"\s*(USD|usd|percent|pct|%|bps?)$", "", t, flags=re.IGNORECASE).strip()
    t = t.replace("−", "-")
    try:
        v = float(t)
    except ValueError:
        return None
    if re.search(r"bps?$", token.strip(), re.IGNORECASE):
        v = v / 100.0
    return v


def _frontmatter_dict(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    close = text.find("\n---", 3)
    if close == -1:
        return {}
    try:
        return yaml.safe_load(text[3:close]) or {}
    except yaml.YAMLError:
        return {}


def _issue(category: str, severity: str, code: str, message: str,
           section_id: str | None = None, detail: str = "") -> dict:
    return {"category": category, "severity": severity, "code": code,
            "message": message, "section_id": section_id, "detail": detail}


def _body_text(text: str) -> str:
    """QMD without the leading YAML frontmatter block (body facts only)."""
    if text.startswith("---"):
        close = text.find("\n---", 3)
        if close != -1:
            fence_end = text.find("\n", close + 1)
            if fence_end != -1:
                return text[fence_end + 1:]
    return text


def _readiness_structure(text: str, spans: list[dict], template: str) -> list[dict]:
    issues = []
    required = _E.REQUIRED_SECTIONS.get(template or "")
    if required is None:
        # Contract §4.1 honest branch: content-neutral / caller-owned bodies
        # have no required-heading list — say so instead of silently passing.
        issues.append(_issue("structure", "info", "STRUCT-NO-REQUIRED-LIST",
                             f"no required-section list defined for template {template!r}"))
    else:
        titles = " ".join(s["title"].lower() for s in spans)
        for keyword in required:
            if keyword.lower() not in titles:
                issues.append(_issue("structure", "error", "STRUCT-MISSING-SECTION",
                                     f"mandatory section missing for template {template!r}: {keyword}"))
    if not spans:
        issues.append(_issue("structure", "error", "STRUCT-NO-SECTIONS",
                             "no sections found in index.qmd"))
    return issues


def _readiness_evidence(text: str, spans: list[dict]) -> list[dict]:
    issues = []
    total = 0
    for i, line in enumerate(text.splitlines(), start=1):
        for marker in _E.ILLUSTRATIVE_MARKERS:
            if marker in line:
                total += 1
                if len([x for x in issues if x["code"] == "EVID-ILLUSTRATIVE"]) < 10:
                    issues.append(_issue("evidence", "warning", "EVID-ILLUSTRATIVE",
                                         f"illustrative content marker {marker!r} (line {i}) — never silently passed"))
                break
    if total > 10:
        # The 10-issue cap is display-only; the count itself stays visible so
        # a marker-heavy draft can never look cleaner than it is.
        issues.append(_issue("evidence", "info", "EVID-ILLUSTRATIVE-OVERFLOW",
                             f"{total} illustrative markers found; showing first 10"))
    return issues


def _strip_code_spans_and_comments(text: str) -> str:
    """Remove `code spans` and <!-- comments --> before evidence scanning.

    Finding 1: backticked syntax docs (`use [@src-key]`) and commented-out
    cites are documentation, not claims — same error-FP class as fenced
    blocks. Documented heuristic: a cite you want checked must be real prose.
    """
    return "\n".join(
        _E._CODE_SPAN_RE.sub("", ln) for ln in _E._HTML_COMMENT_RE.sub("", text).splitlines())


def _cover_number(value) -> float | None:
    """Normalize a cover/fact value for linkage; None means unchecked.

    Ranges ("300-310", "300 to 320") and non-numerics ("Q3'26") are
    documented unchecked in the contract. Unit-blind and silent by design:
    a "300 bps" fact and a "$300" target compare as 300 with no issue —
    readiness is heuristic (charter §3.6), and unit judgment stays
    editorial. Only the ILLUSTRATIVE link names its fact id.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    t = value.strip().replace(",", "").replace("$", "").strip()
    t = re.sub(r"\s*(USD|usd|percent|pct|%|bps?)$", "", t, flags=re.IGNORECASE).strip()
    if not t or re.search(r"\d\s*[-–~]\s*\d|\bto\b", t):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _cover_values_match(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))


def _cover_numeric_candidates(front: dict, skip_weights: bool = True,
                            ) -> list[tuple[str, float]]:
    """Structured cover numerics: target, scenario values, metric values.

    Verdict prose is excluded by design (policed by UNREGISTERED-CITE and
    the numerics pass instead) — see the contract's deferred-items list.
    """
    cands: list[tuple[str, float]] = []
    t = _cover_number(front.get("target"))
    if t is not None:
        cands.append(("target", t))
    scenarios = front.get("scenarios")
    scen_vals: list[tuple[int, float]] = []
    if isinstance(scenarios, list):
        for i, item in enumerate(scenarios):
            if isinstance(item, dict):
                v = _cover_number(item.get("value"))
                if v is not None:
                    scen_vals.append((i, v))
    # Finding 5: scenario probability weights (bear/base/bull shares summing
    # to ~100) are not thesis facts — demanding a fact record for each
    # degrades every scenario-bearing genre to noise. Two or more numeric
    # values summing to 99..101 are treated as weights and skipped.
    # R2-F9: a DERIVED cover is exempt — its weights are registry-grounded,
    # so the skip must not hide later drift.
    scen_total = sum(v for _, v in scen_vals)
    weights = (len(scen_vals) >= 2 and 99.0 <= scen_total <= 101.0)
    if not weights or not skip_weights:
        for i, v in scen_vals:
            cands.append((f"scenarios[{i}].value", v))
    metrics = front.get("metrics")
    if isinstance(metrics, list):
        for i, item in enumerate(metrics):
            if isinstance(item, dict):
                v = _cover_number(item.get("value"))
                if v is not None:
                    cands.append((f"metrics[{i}].value", v))
    return cands


def _readiness_evidence_coverage(root: Path, body: str, front: dict,
                                 registries: dict, template: str) -> list[dict]:
    """Registry↔body evidence linkage: cites, exhibits, cover, required kinds."""
    issues: list[dict] = []
    sources = registries.get("sources", {}) or {}
    exhibits = registries.get("exhibits", {}) or {}
    facts = registries.get("facts", {}) or {}
    # Fenced code blocks are never prose: an [@key] inside a python chunk
    # is documentation, and an error-severity FP would block release.
    # Code spans and HTML comments get the same treatment (finding 1).
    scanned = _strip_code_spans_and_comments("\n".join(
        line for _, line in manifest_mod._iter_prose_lines(body.splitlines())))
    cited = set(_E._SRC_CITE_RE.findall(scanned))
    for key in sorted(cited):
        if key not in sources:
            issues.append(_issue(
                "evidence", "error", "EVID-UNREGISTERED-CITE",
                f"cited source {key!r} has no registry record — register it first"))
    # Exhibits: @fig- cross-refs AND {#fig-} embed definitions — an
    # embedded-but-never-cross-referenced figure is the common style.
    shorts = set(_E._FIGREF_RE.findall(scanned)) | set(_E._FIGANCHOR_RE.findall(scanned))
    for short in sorted(shorts):
        if f"fig-{short}" not in exhibits:
            issues.append(_issue(
                "evidence", "error", "EVID-EXHIBIT-UNREGISTERED",
                f"figure @fig-{short} has no exhibit record — register it first"))
    anchors = set(_E._FIGANCHOR_RE.findall(scanned))
    for eid in sorted(exhibits):
        rec = exhibits[eid]
        f = rec.get("file")
        if f is not None:
            # Boundary pinned (critic-2 F3): only set-but-absent fires.
            # file: null (anchor-grounded) never reaches this branch.
            if not (root / f).is_file():
                issues.append(_issue(
                    "evidence", "error", "EVID-EXHIBIT-FILE-MISSING",
                    f"exhibit {eid!r} points at missing file {f!r}"))
        else:
            short = eid[4:] if eid.startswith("fig-") else eid
            if short not in anchors:
                issues.append(_issue(
                    "evidence", "warning", "EVID-EXHIBIT-ANCHOR-MISSING",
                    f"exhibit {eid!r} is anchor-grounded but {{#fig-{short}}} "
                    "no longer exists in index.qmd"))
    for field, number in _cover_numeric_candidates(
            front, skip_weights=not bool(front.get("cover_derived"))):
        # Finding 3: two-pass match — a legitimate non-illustrative fact
        # wins over an illustrative shadow with the same value, so the
        # message never misstates the report's actual grounding.
        match_id: str | None = None
        match_kind = ""
        ordered = sorted(facts,
                         key=lambda fid: (facts[fid].get("kind")
                                          == "illustrative", fid))
        for fid in ordered:
            fv = _cover_number(facts[fid].get("value"))
            if fv is not None and _cover_values_match(number, fv):
                match_id, match_kind = fid, facts[fid].get("kind", "")
                break
        if match_id is None:
            issues.append(_issue(
                "evidence", "error", "EVID-COVER-UNLINKED",
                f"cover {field} = {number:g} has no matching fact record — "
                "run derive_cover to bind it"))
        elif match_kind == "illustrative":
            issues.append(_issue(
                "evidence", "warning", "EVID-COVER-ILLUSTRATIVE",
                f"cover {field} links to illustrative fact {match_id!r} — "
                "thesis built on illustrative data"))
    required = _E.REQUIRED_EVIDENCE.get(template or "")
    if required is None:
        issues.append(_issue(
            "evidence", "info", "EVID-NO-REQUIRED-LIST",
            f"no required-evidence list defined for template {template!r}"))
    else:
        for req in required:
            kinds = req["kind"] if isinstance(req.get("kind"), list) else [req.get("kind")]
            satisfied = any(
                s.get("kind") in kinds and skey in cited
                for skey, s in sources.items())
            if not satisfied:
                issues.append(_issue(
                    "evidence", "error", "EVID-MISSING-REQUIRED",
                    f"no cited {req.get('label', req.get('kind'))} in registry "
                    f"for template {template!r}"))
    return issues


def _label_tokens(window: str, line: str = "") -> dict:
    """Discriminating tokens near a number: tickers + window/metric words.

    Tickers come from the number's own line only — a ±120-char window
    spans adjacent table rows and would glue peer tickers onto every
    quantity in the block. Metric/window words use the wider window.
    """
    tickers = {t for t in _E._TICKER_RE.findall(line or window)
               if t not in _E._TICKER_STOP}
    low = window.lower()
    words = {w for w in _E._WINDOW_WORDS + _E._METRIC_WORDS if w in low}
    return {"tickers": tickers, "words": words}


def _same_key(a: dict, b: dict) -> bool:
    """Conservative overlap (§2): same quantity only on shared discriminators.

    Same ticker on both sides, or — when neither side names a ticker —
    shared window/metric words. Anything else: no comparison is made.
    """
    if a["tickers"] and b["tickers"]:
        return bool(a["tickers"] & b["tickers"])
    if a["tickers"] or b["tickers"]:
        return False
    return bool(a["words"] & b["words"])


def _is_table_row(line: str) -> bool:
    return line.lstrip().startswith("|")


def _governor_kind(before: str, after: str, header_word: str = "") -> str | None:
    """The word governing a number: nearest price/metric language before it.

    Whole-window presence tests misfire on mixed sentences ("closed at $S.
    Price target $T" — both words sit in both windows). The rightmost match
    in the ~40 chars before the number is what the number belongs to; a
    trailing target phrase ("$X price target") and the table column header
    are the only fallbacks. Returns spot/target/other/None.
    """
    cands: list[tuple[int, str]] = []
    for m in _E._TARGET_PHRASE_RE.finditer(before):
        cands.append((m.end(), "target"))
    for m in _E._SPOT_WORDS_RE.finditer(before):
        cands.append((m.end(), "spot"))
    for m in _E._TARGET_WORD_RE.finditer(before):
        cands.append((m.end(), "target"))
    if cands:
        return sorted(cands)[-1][1]
    if _E._TARGET_PHRASE_RE.search(after) or _E._TARGET_WORD_RE.search(after):
        return "target"
    low = before.lower()
    if any(w in low for w in _E._METRIC_WORDS):
        return "other"
    hw = header_word.lower()
    if _E._TARGET_PHRASE_RE.search(hw) or _E._TARGET_WORD_RE.search(hw):
        return "target"
    if _E._SPOT_WORDS_RE.search(hw):
        return "spot"
    if any(w in hw for w in _E._METRIC_WORDS):
        return "other"
    return None


def _header_cell_for(lines: list[str], line_no: int, pos: int, line_start: int) -> str:
    """Column-header cell above a table-row number (empty when not a table)."""
    idx = line_no - 1
    if idx < 0 or idx >= len(lines) or not _is_table_row(lines[idx]):
        return ""
    start = 0
    while idx > 0 and _is_table_row(lines[idx - 1]):
        idx -= 1
    header = [c.strip() for c in lines[idx].strip().strip("|").split("|")]
    col = lines[line_no - 1][:pos - line_start].count("|")
    return header[col] if col < len(header) else ""


def _pipe_tables(body: str) -> list[list[list[str]]]:
    """Consecutive pipe-row blocks parsed into rows of cells."""
    tables = []
    current: list[list[str]] = []
    for line in body.splitlines():
        if _is_table_row(line):
            current.append([c.strip() for c in line.strip().strip("|").split("|")])
        elif current:
            if len(current) >= 2:
                tables.append(current)
            current = []
    if len(current) >= 2:
        tables.append(current)
    return tables


def _extract_quantities(body: str) -> list[dict]:
    """Every comparable number with its §2 key.

    Money is a price mention only beside spot/target language — a target is
    never a spot (§3 NUM-DERIVED-PCT / NUM-SPOT-DISAGREE scoping). Money
    beside other metric words (revenue, margin, …) gets kind "other" so
    NUM-PROSE-TABLE can still key it. Bare numbers count only within 3
    tokens of a price word (spec §1).
    """
    quantities = []
    claimed = []  # (start, end) spans already claimed by money/pct matches
    lines = body.splitlines()
    line_starts = [0]
    for ln in lines:
        line_starts.append(line_starts[-1] + len(ln.encode("utf-8")) + 1)

    def line_of(pos: int) -> int:
        import bisect
        return min(bisect.bisect_right(line_starts, pos), len(lines))

    for m in _E._MONEY_RE.finditer(body):
        window = body[max(0, m.start() - 120):m.end() + 60]
        line_no = line_of(m.start())
        before = body[max(0, m.start() - 40):m.start()]
        after = body[m.end():m.end() + 30]
        header = _header_cell_for(lines, line_no, m.start(),
                                  line_starts[line_no - 1])
        kind = _governor_kind(before, after, header)
        if kind is None:
            continue  # money without quantity language is not comparable
        v = _num_value(m.group(0))
        if v is None:
            continue
        near = body[max(0, m.start() - 300):m.start()]
        dates = _E._ASOF_RE.findall(near)
        quantities.append({"value": v, "kind": kind,
                           "labels": _label_tokens(window, lines[line_no - 1]),
                           "asof": dates[-1] if dates else None,
                           "line": line_no, "pos": m.start(),
                           "table": _is_table_row(lines[line_no - 1])})
        claimed.append((m.start(), m.end()))
    for m in _E._PCT_RE.finditer(body):
        if any(s <= m.start() < e for s, e in claimed):
            continue
        window = body[max(0, m.start() - 120):m.end() + 60]
        low = window.lower()
        if "vol" in low or "volatility" in low or "std" in low.split():
            kind = "vol_pct"
        elif re.search(r"weight|probability|allocation|scenario", low):
            kind = "weight_pct"
        else:
            kind = "return_pct"
        v = _num_value(m.group(0))
        if v is None or v == 0:
            continue
        before = body[max(0, m.start() - 40):m.start()]
        sign = ("neg" if _E._SIGN_NEG_RE.search(before)
                else "pos" if _E._SIGN_POS_RE.search(before) else None)
        line_no = line_of(m.start())
        quantities.append({"value": v, "kind": kind,
                           "labels": _label_tokens(window, lines[line_no - 1]),
                           "asof": None, "line": line_no,
                           "pos": m.start(), "sign": sign,
                           "table": _is_table_row(lines[line_no - 1]),
                           "hedged": _E._HEDGE_RE.search(window) is not None})
        claimed.append((m.start(), m.end()))
    for m in _E._BARE_NUM_RE.finditer(body):
        if any(s <= m.start() < e for s, e in claimed):
            continue
        ctx = body[max(0, m.start() - 40):m.end() + 40]
        if _E._PRICEISH_RE.search(ctx) is None:
            continue
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        window = body[max(0, m.start() - 120):m.end() + 60]
        line_no = line_of(m.start())
        before = body[max(0, m.start() - 40):m.start()]
        after = body[m.end():m.end() + 30]
        header = _header_cell_for(lines, line_no, m.start(),
                                  line_starts[line_no - 1])
        kind = _governor_kind(before, after, header)
        # Bare numbers count only as price mentions (spec §1); a bare
        # metric-word number ("revenue 152") is too ambiguous to key.
        if kind not in ("spot", "target"):
            continue
        near = body[max(0, m.start() - 300):m.start()]
        dates = _E._ASOF_RE.findall(near)
        quantities.append({"value": v, "kind": kind,
                           "labels": _label_tokens(window, lines[line_no - 1]),
                           "asof": dates[-1] if dates else None,
                           "line": line_no, "pos": m.start(),
                           "table": _is_table_row(lines[line_no - 1])})
    return quantities


def _section_for_line(spans: list[dict], full_line: int) -> str | None:
    current = None
    for s in spans:
        if s.get("line_start", 0) <= full_line:
            current = s.get("id")
        else:
            break
    return current


def _readiness_numerical(body: str, front: dict, spans: list[dict] | None = None,
                         body_offset: int = 0) -> list[dict]:
    """All ten numerics-v1 checks over body quantities + frontmatter.

    Posture per spec: exact-label conflicts and arithmetic contradictions
    are error; fuzzy matches are warning; passes stay silent (the category
    `pass: true` verdict is the signal, so quiet fixtures stay quiet).
    One quantity with N disagreeing mentions yields ONE issue.
    """
    issues = []
    quants = _extract_quantities(body)
    spans = spans or []

    def sec(line: int) -> str | None:
        return _section_for_line(spans, body_offset + line) if spans else None

    def detail_line(line: int) -> str:
        return f"index.qmd:{body_offset + line}"

    # -- NUM-DERIVED-PCT: cover target +Y% vs a body spot $S ------------------
    verdict = str(front.get("verdict", ""))
    target_raw = front.get("target", "")
    pct_m = _E._PCT_RE.search(verdict)
    tgt_m = _E._MONEY_RE.search(str(target_raw) + " " + verdict)
    if tgt_m is None and isinstance(target_raw, (int, float)):
        target = float(target_raw)
    elif tgt_m is None and re.fullmatch(r"[\d,]+(?:\.\d+)?", str(target_raw).strip()):
        # Frontmatter `target: 300` is an exact-value field even without a
        # dollar sign — zero tolerance still applies (spec §3 TARGET-AGREE).
        target = float(str(target_raw).strip().replace(",", ""))
    else:
        target = _num_value(tgt_m.group(0)) if tgt_m else None
    spots = [q for q in quants if q["kind"] == "spot"]
    if pct_m and target and spots:
        claimed = _num_value(pct_m.group(0))
        spot = spots[0]  # document-order first true spot — never a target
        if claimed is not None and spot["value"]:
            derived = (target / spot["value"] - 1) * 100
            if abs(claimed - derived) > 0.5:
                issues.append(_issue(
                    "numerical", "error", "NUM-DERIVED-PCT",
                    f"cover claims {claimed:g}% to ${target:g} but spot "
                    f"${spot['value']:g} implies {derived:+.1f}%",
                    section_id=sec(spot["line"]),
                    detail=f"frontmatter:verdict/target vs {detail_line(spot['line'])}"))
    # -- NUM-SPOT-DISAGREE: clusters keyed by ticker+as-of --------------------
    groups: dict = {}
    order: list = []
    for s in spots:
        key = (s["asof"], frozenset(s["labels"]["tickers"]))
        placed = False
        for i, (ka, _) in enumerate(order):
            same_asof = ka[0] == key[0]
            tick_ok = (ka[1] == key[1] or (not ka[1] and not key[1]))
            if same_asof and tick_ok:
                groups[i].append(s)
                placed = True
                break
        if not placed:
            order.append((key, None))
            groups[len(order) - 1] = [s]
    for members in groups.values():
        if len(members) < 2:
            continue
        vals = [m["value"] for m in members]
        spread = max(vals) - min(vals)
        locs = ", ".join(detail_line(m["line"]) for m in members[:6])
        if spread > 1.0:
            issues.append(_issue(
                "numerical", "error", "NUM-SPOT-DISAGREE",
                f"spot mentions disagree by ${spread:.2f} "
                f"(as-of {members[0]['asof'] or 'unstated'})",
                section_id=sec(members[0]["line"]), detail=locs))
        elif spread > 0.05:
            issues.append(_issue(
                "numerical", "warning", "NUM-SPOT-DISAGREE",
                f"spot mentions differ by ${spread:.2f} — rounding gray zone",
                section_id=sec(members[0]["line"]), detail=locs))
    # -- price-fact as-of dates (tables, captions, price windows) -------------
    price_dates: list[tuple[str, int]] = []  # (date, body line)
    for m in _E._ASOF_RE.finditer(body):
        line_no = body.count("\n", 0, m.start()) + 1
        line = body.splitlines()[line_no - 1]
        is_price_fact = (
            _is_table_row(line)
            or "fig" in line.lower() or "caption" in line.lower()
            or any(q["kind"] in ("spot", "target")
                   and m.start() <= q["pos"] < m.start() + 400
                   for q in quants)
        )
        if is_price_fact:
            price_dates.append((m.group(1), line_no))
    fm_date = front.get("date")
    fm_date = str(fm_date) if fm_date is not None else None
    for d, line_no in sorted(set(price_dates)):
        if fm_date and d > fm_date:
            issues.append(_issue(
                "numerical", "error", "NUM-ASOF-FUTURE",
                f"as-of {d} is later than frontmatter date {fm_date}",
                section_id=sec(line_no), detail=detail_line(line_no)))
    if price_dates:
        from collections import Counter
        mode = Counter(d for d, _ in price_dates).most_common(1)[0][0]
        outliers = sorted({d for d, _ in price_dates if d != mode})
        if outliers:
            issues.append(_issue(
                "numerical", "warning", "NUM-ASOF-MIXED",
                f"as-of mode {mode}; outliers: {', '.join(outliers)}"))
    # -- NUM-SIGN-CONFLICT: prose sign vs same-key table row ------------------
    prose_pcts = [q for q in quants
                  if q["kind"] == "return_pct" and not q["table"] and q.get("sign")]
    if prose_pcts:
        for line in body.splitlines():
            if not _is_table_row(line):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 2:
                continue
            row_labels = _label_tokens(" ".join(cells))
            for cell in cells[1:]:
                cm = _E._PCT_RE.search(cell) or _E._MONEY_RE.search(cell)
                if not cm:
                    continue
                v = _num_value(cm.group(0))
                if v is None:
                    continue
                cell_neg = cell.strip().startswith(("-", "−")) or \
                    _E._SIGN_NEG_RE.search(cell) is not None
                cell_pos = cell.strip().startswith("+") or \
                    _E._SIGN_POS_RE.search(cell) is not None
                for p in prose_pcts:
                    if round(abs(p["value"]), 4) != round(abs(v), 4):
                        continue
                    if not _same_key(p["labels"], row_labels):
                        continue
                    conflict = ((p["sign"] == "neg" and cell_pos and not cell_neg)
                                or (p["sign"] == "pos" and cell_neg and not cell_pos))
                    if conflict:
                        issues.append(_issue(
                            "numerical", "error", "NUM-SIGN-CONFLICT",
                            f"prose states {'-' if p['sign'] == 'neg' else '+'}{abs(v):g} "
                            f"but table shows {cell.strip()[:24]}",
                            detail=f"{detail_line(p['line'])} vs table row: {line.strip()[:120]}"))
                        break
    # -- NUM-PROSE-TABLE: prose repeats a table quantity, mismatch ------------
    # Best-match pairing per table quantity: the closest same-key prose
    # mention decides. An exact repeat elsewhere must not let a distant
    # prose number fire against this cell (or vice versa).
    _COMPARABLE = ("spot", "target", "other", "return_pct")
    table_quants = [q for q in quants if q["table"] and q["kind"] in _COMPARABLE]
    prose_quants = [q for q in quants if not q["table"] and q["kind"] in _COMPARABLE]
    for t in table_quants:
        best = None  # (delta, prose_quant, threshold)
        for p in prose_quants:
            if t["kind"] != p["kind"] or not _same_key(t["labels"], p["labels"]):
                continue
            delta = abs(t["value"] - p["value"])
            if t["kind"] == "return_pct":
                threshold = 2.0 if p.get("hedged", False) else 0.05
            else:
                threshold = 0.5  # precise quote vs rounded cell: pass
            if best is None or delta < best[0]:
                best = (delta, p, threshold)
        if best is None:
            continue
        delta, p, threshold = best
        if delta <= threshold:
            continue
        if t["kind"] == "return_pct":
            issues.append(_issue(
                "numerical", "warning", "NUM-PROSE-TABLE",
                f"prose {p['value']:g} vs table {t['value']:g} "
                f"(Δ {delta:g}pp{', hedged' if p.get('hedged', False) else ''})",
                section_id=sec(p["line"]),
                detail=f"{detail_line(p['line'])} vs {detail_line(t['line'])}"))
        else:
            issues.append(_issue(
                "numerical", "warning", "NUM-PROSE-TABLE",
                f"prose ${p['value']:g} vs table ${t['value']:g}",
                section_id=sec(p["line"]),
                detail=f"{detail_line(p['line'])} vs {detail_line(t['line'])}"))
    # -- NUM-SCENARIO-WEIGHTS: weights sum to 100 ± 0.5 ------------------------
    weights = []
    scenarios = front.get("scenarios")
    if isinstance(scenarios, list):
        for s in scenarios:
            if isinstance(s, dict) and isinstance(s.get("value"), (int, float)):
                weights.append(float(s["value"]))
    if len(weights) >= 2 and abs(sum(weights) - 100) > 0.5:
        issues.append(_issue("numerical", "error", "NUM-SCENARIO-WEIGHTS",
                             f"scenario weights sum to {sum(weights):g}, not 100"))
    # -- NUM-SCENARIO-RECOMPUTE: weights × returns vs stated figure -----------
    pairs, tail_open = _scenario_pairs(front, body)
    stated, stated_hedged = _stated_weighted_return(front, body)
    if pairs and stated is not None:
        lo = sum(w * (r if r is not None else -20.0) for w, r, _ in pairs) / 100.0
        hi = sum(w * (r if r is not None else 20.0) for w, r, _ in pairs) / 100.0
        tol = 4.0 if stated_hedged else 2.0
        if tail_open:
            # Bounded, not exact: warn only when the stated figure sits
            # outside the whole feasible band by more than tolerance.
            if stated < lo - tol or stated > hi + tol:
                issues.append(_issue(
                    "numerical", "warning", "NUM-SCENARIO-RECOMPUTE",
                    f"weights × returns recompute to {lo:.1f}–{hi:.1f}% "
                    f"but stated {stated:g}% (tail scenario unparseable — bounded)",
                    detail="frontmatter:scenarios vs body/scenario prose"))
        elif abs(sum(w * r for w, r, _ in pairs) / 100.0 - stated) > tol:
            recomputed = sum(w * r for w, r, _ in pairs) / 100.0
            issues.append(_issue(
                "numerical", "error", "NUM-SCENARIO-RECOMPUTE",
                f"weights × returns recompute to {recomputed:.1f}% "
                f"but stated {stated:g}% (Δ > {tol:g}pp)",
                detail="frontmatter:scenarios vs stated weighted figure"))
    # -- NUM-TARGET-AGREE: cover target vs scenario-table base target ---------
    if target is not None:
        cover_target = target
        for table in _pipe_tables(body):
            for row in table[1:]:
                if not row or not re.search(r"\bbase\b", row[0], re.IGNORECASE):
                    continue
                for cell in row[1:]:
                    cm = _E._MONEY_RE.search(cell)
                    if not cm:
                        continue
                    base_target = _num_value(cm.group(0))
                    if (cover_target is not None and base_target is not None
                            and abs(cover_target - base_target) > 0):
                        issues.append(_issue(
                            "numerical", "error", "NUM-TARGET-AGREE",
                            f"cover target ${cover_target:g} vs scenario-table "
                            f"base ${base_target:g}",
                            detail=f"frontmatter:target vs {cell.strip()[:60]}"))
                        break
                else:
                    continue
                break
    # -- NUM-TABLE-TOTAL: total/sum/net rows recompute -------------------------
    for table in _pipe_tables(body):
        if len(table) < 3:
            continue
        header, rows = table[0], table[1:]
        total_idx = next((i for i, r in enumerate(rows)
                          if r and re.match(r"(?i)^(total|sum|net|combined)\b",
                                            r[0])), None)
        if total_idx is None:
            continue
        data_rows = [r for i, r in enumerate(rows) if i != total_idx]
        for col in range(1, max(len(r) for r in rows)):
            tcell = rows[total_idx][col] if col < len(rows[total_idx]) else ""
            tm = _E._MONEY_RE.search(tcell) or _E._PCT_RE.search(tcell)
            if not tm:
                continue
            tval = _num_value(tm.group(0))
            parts = []
            for r in data_rows:
                if col >= len(r):
                    break
                cm = _E._MONEY_RE.search(r[col]) or _E._PCT_RE.search(r[col])
                if not cm:
                    break
                v = _num_value(cm.group(0))
                if v is None:
                    break
                parts.append(v)
            else:
                if tval is None or not parts:
                    continue
                is_pct = "%" in tm.group(0) or "percent" in tm.group(0).lower()
                if is_pct:
                    bad = abs(sum(parts) - tval) > 0.5
                else:
                    bad = abs(sum(parts) - tval) > max(0.5, abs(tval) * 0.01)
                if bad:
                    issues.append(_issue(
                        "numerical", "error", "NUM-TABLE-TOTAL",
                        f"{header[col] if col < len(header) else 'column'} total "
                        f"{tval:g} vs recomputed {sum(parts):g}",
                        detail=f"row: {rows[total_idx][0][:60]}"))
    return issues


def _scenario_pairs(front: dict, body: str) -> tuple[list, bool]:
    """(weight, return-or-None, label) per scenario + tail-open flag."""
    pairs: list = []
    scenarios = front.get("scenarios")
    if isinstance(scenarios, list):
        for s in scenarios:
            if not isinstance(s, dict):
                continue
            w = s.get("value")
            if isinstance(w, bool) or not isinstance(w, (int, float)):
                for k in ("weight", "probability"):
                    if isinstance(s.get(k), (int, float)):
                        w = s[k]
                        break
            if isinstance(w, bool) or not isinstance(w, (int, float)):
                continue
            r = None
            for k in ("return", "pct", "percent", "upside", "expected"):
                v = s.get(k)
                if isinstance(v, bool):
                    continue
                if isinstance(v, (int, float)):
                    r = float(v)
                    break
                if isinstance(v, str):
                    m = _E._PCT_RE.search(v)
                    if m:
                        r = _num_value(m.group(0))
                        break
            pairs.append((float(w), r, str(s.get("label", "?"))))
    for table in _pipe_tables(body):
        header = [c.lower() for c in table[0]]
        has_label = any("scenario" in h or "case" in h for h in header)
        wi = next((i for i, h in enumerate(header)
                   if "weight" in h or "prob" in h), None)
        ri = next((i for i, h in enumerate(header)
                   if "return" in h or "upside" in h or "pct" in h or "%" in h),
                  None)
        if not (has_label and wi is not None and ri is not None):
            continue
        for row in table[1:]:
            if max(wi, ri) >= len(row):
                continue
            wm = _E._PCT_RE.search(row[wi]) or _E._BARE_NUM_RE.search(row[wi])
            rm = _E._PCT_RE.search(row[ri])
            if not wm:
                continue
            w = _num_value(wm.group(0)) if "%" in wm.group(0) else None
            try:
                w = float(wm.group(1).replace(",", "")) if w is None else w
            except (ValueError, AttributeError):
                continue
            r = _num_value(rm.group(0)) if rm else None
            pairs.append((w, r, row[0][:40]))
    tail_open = any(r is None for _, r, _ in pairs)
    return pairs, tail_open


def _stated_weighted_return(front: dict, body: str) -> tuple[float | None, bool]:
    """The report's own stated blended/expected return, if any."""
    for k in ("expected_return", "weighted_return", "blended_return", "expected"):
        v = front.get(k)
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            return float(v), False
        if isinstance(v, str):
            m = _E._PCT_RE.search(v)
            if m:
                return _num_value(m.group(0)), _E._HEDGE_RE.search(v) is not None
    m = re.search(
        r"(?:weighted|expected|blended)[^.\n]{0,60}?([+-]?[\d,]+(?:\.\d+)?\s?(?:percent|pct|%))",
        body, re.IGNORECASE)
    if m:
        return _num_value(m.group(1)), _E._HEDGE_RE.search(m.group(0)) is not None
    return None, False


def _figure_layout_kind(attrs: str) -> str:
    """Classify a figure from its {#fig-} attribute text.

    R2-F6: the hook the RED policy tests hang on — width/column/ncol
    come from the anchor, never from an exhibit record field.
    """
    if _E._COLUMN_PAGE_RE.search(attrs) or _E._NCOL_RE.search(attrs):
        return "wide"
    m = _E._WIDTH_PCT_RE.search(attrs)
    if m:
        pct = float(m.group(1))
        if pct >= 90:
            return "wide"
        if pct >= 70:
            return "complex"
    return "compact"


def _readiness_layout_policies(prose: str, exhibits: dict) -> list[dict]:
    """Caption/alt/appendix rules for the four documented exhibit shapes."""
    issues = []
    seen: set[str] = set()
    for cap, short, attrs in _E._FIGEMBED_RE.findall(prose):
        if short in seen:
            continue
        seen.add(short)
        eid = f"fig-{short}"
        rec = exhibits.get(eid)
        if rec is None:
            # EXHIBIT-UNREGISTERED already errors; policy warnings stay out.
            continue
        kind = _figure_layout_kind(attrs)
        if kind in ("complex", "wide") and not cap.strip():
            issues.append(_issue(
                "presentation", "warning", "PRES-CAP-MISSING",
                f"figure @fig-{short} is {kind} but carries no embed caption — "
                "complex figures need one"))
        if kind == "wide" and not (rec.get("alt") or "").strip():
            issues.append(_issue(
                "presentation", "warning", "PRES-ALT-MISSING",
                f"figure @fig-{short} is wide but has no alt text — "
                "register the exhibit with alt"))
    for _, line in manifest_mod._iter_prose_lines(prose.splitlines()):
        m = re.match(r"^#{1,6}\s+.*(\{[^}]*\.appendix[^}]*\})\s*$", line)
        if m and not re.search(r"(?:^|[\s.{])-(?=[\s.}])|unnumbered",
                               m.group(1)):
            issues.append(_issue(
                "presentation", "warning", "PRES-APPENDIX-NUMBERED",
                "appendix section is numbered — add .unnumbered "
                f"({line.strip()[:60]})"))
    return issues


def _readiness_presentation(root: Path, text: str,
                              exhibits: dict | None = None) -> list[dict]:
    issues = []
    charts_dir = root / "charts"
    if charts_dir.is_dir():
        charts = sorted(p.name for p in charts_dir.glob("*.png"))
        for name in charts:
            stem = Path(name).stem
            if stem not in text and name not in text:
                issues.append(_issue("presentation", "warning", "PRES-UNREFERENCED-CHART",
                                     f"charts/{name} is never referenced in index.qmd"))
    # Finding 2: refs/anchors scan fence-stripped prose (a @fig- inside a
    # code chunk is documentation, not a dangling cross-ref). The charts/
    # check above intentionally keeps raw text: a filename mentioned
    # anywhere still counts as referenced.
    prose = "\n".join(
        line for _, line in manifest_mod._iter_prose_lines(text.splitlines()))
    anchors = set(_E._FIGANCHOR_RE.findall(prose))
    for ref in sorted(set(_E._FIGREF_RE.findall(prose))):
        if ref not in anchors:
            issues.append(_issue("presentation", "error", "PRES-DANGLING-REF",
                                 f"@fig-{ref} has no matching figure anchor"))
    issues.extend(_readiness_layout_policies(prose, exhibits or {}))
    try:
        violation = _E._engine_charts_violation(root)
    except Exception:
        violation = None
    if violation:
        issues.append(_issue("presentation", "error", "PRES-ENGINE-CHARTS",
                             violation))
    lint_out = _E._run_figure_lint(root)
    if lint_out is not None:
        issues.append(_issue("presentation", "warning", "PRES-FIGURE-LINT",
                             f"figure_lint reports: {lint_out[:300]}"))
    return issues


def _readiness_editorial(manifest) -> list[dict]:
    if any(r.get("revision") == manifest.revision and r.get("decision") == "approved"
           for r in manifest.reviews):
        return [_issue("editorial", "info", "EDIT-REVIEWED",
                       f"revision {manifest.revision} has an approved review record")]
    return [_issue("editorial", "warning", "EDIT-NEEDS-REVIEW",
                   f"revision {manifest.revision} has no approved review record — judgment is human-only")]


def check_readiness(project: str) -> dict:
    """Unified readiness: structure, evidence, numerical, presentation, editorial.

    Automated checks only; factual accuracy and source quality are explicitly
    out of scope (review §3.6) — see the scope_note in every response.
    """
    root, err = _E._project_root_or_error(project)
    if err:
        return err
    assert root is not None
    manifest, err = _E._load_or_import(root)
    if err:
        return err
    assert manifest is not None
    text = (root / "index.qmd").read_text(encoding="utf-8")
    spans = _E._section_spans(text)
    front = _frontmatter_dict(text)
    body = _body_text(text)
    body_offset = len(text.splitlines()) - len(body.splitlines())
    template = manifest.to_dict().get("profile", {}).get("report_type", "")
    categories = {
        "structure": _readiness_structure(text, spans, template),
        "evidence": (_readiness_evidence(text, spans)
                     + _readiness_evidence_coverage(
                         root, body, front, manifest.to_dict(), template)),
        "numerical": _readiness_numerical(body, front, spans, body_offset),
        "presentation": _readiness_presentation(
            root, text, manifest.to_dict().get("exhibits", {})),
        "editorial": _readiness_editorial(manifest),
    }
    cats = {name: {"pass": not any(i["severity"] == "error" for i in iss),
                   "issues": iss} for name, iss in categories.items()}
    ready = all(c["pass"] for c in cats.values())
    return {
        "ok": True,
        "report_id": manifest.report_id,
        "revision": manifest.revision,
        "state": manifest.state,
        "categories": cats,
        "ready_for_review": ready,
        "scope_note": ("automated structure/evidence/presentation checks only — "
                       "not factual accuracy, source quality, or financial claims (review §3.6)"),
    }


def record_review(project: str, revision: int, reviewer: str, decision: str,
                  comments: str = "", section_id: str | None = None,
                  actor: str = "tool:record_review") -> dict:
    """Append a review record to the manifest (§4.3)."""
    root, err = _E._project_root_or_error(project)
    if err:
        return err
    assert root is not None
    manifest, err = _E._load_or_import(root)
    if err:
        return err
    assert manifest is not None
    res = manifest_mod.add_review(manifest, revision, reviewer, decision,
                                  comments, section_id)
    if not res.get("ok"):
        return res
    manifest_mod.save(manifest, str(root))
    return {"ok": True, "report_id": manifest.report_id,
            "revision": revision, "decision": decision}


