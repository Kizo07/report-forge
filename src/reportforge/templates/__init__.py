"""Template assets for reportforge.scaffold (loader package).

Phase 2 of the robustness refactor plan: every template asset is a real
file under `_assets/` (reviewable, previewable, snapshot-testable); this
loader re-exposes them under the same attribute names the pre-refactor
`templates.py` module had, so consumers are unchanged.

All scaffold-visible values are byte-identical to the pre-extraction
constants — parity is enforced by tests/test_scaffold_parity.py and the
RF_PARITY render gate.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "_assets"

# attribute name → asset path (relative to ASSETS_DIR)
SPEC: dict[str, str] = {
    "QUARTO_YML": "_shared/quarto.yml",
    "BRAND_YML": "_shared/brand.yml",
    "STYLES_SCSS": "_shared/styles.scss",
    "INDEX_QMD": "_shared/index.qmd",
    "BESPOKE_YML": "_shared/bespoke.yml",
    "PORTFOLIO_YML": "_shared/portfolio.yml",
    "MEMO_QMD": "memo/memo.qmd",
    "WHITEPAPER_QMD": "whitepaper/whitepaper.qmd",
    "WHITEPAPER_STYLES_EXTRA": "whitepaper/styles-extra.scss",
    "WHITEPAPER_TYPT_TEMPLATE": "whitepaper/typst-template.typ",
    "WHITEPAPER_TYPT_SHOW": "whitepaper/typst-show.typ",
    "MODERN_YML": "modern/modern.yml",
    "MODERN_QMD": "modern/modern.qmd",
    "MODERN_STYLES_EXTRA": "modern/styles-extra.scss",
    "MODERN_TYPT_TEMPLATE": "modern/typst-template.typ",
    "MODERN_TYPT_SHOW": "modern/typst-show.typ",
    "STUDIO_YML": "studio/studio.yml",
    "STUDIO_BRAND_YML": "studio/brand.yml",
    "STUDIO_HTML_HEADER": "studio/header.html",
    "STUDIO_QMD": "studio/studio.qmd",
    "STUDIO_STYLES_EXTRA": "studio/styles-extra.scss",
    "STUDIO_TYPT_TEMPLATE": "studio/typst-template.typ",
    "STUDIO_TYPT_SHOW": "studio/typst-show.typ",
    "PORTFOLIO_LIGHT_BRAND_YML": "portfolio-light/brand.yml",
    "PORTFOLIO_LIGHT_STYLES_EXTRA": "portfolio-light/styles-extra.scss",
    "PORTFOLIO_LIGHT_TYPT_TEMPLATE": "portfolio-light/typst-template.typ",
    "PORTFOLIO_LIGHT_TYPT_SHOW": "portfolio-light/typst-show.typ",
    "PORTFOLIO_DARK_BRAND_YML": "portfolio-dark/brand.yml",
    "PORTFOLIO_DARK_STYLES_EXTRA": "portfolio-dark/styles-extra.scss",
    "PORTFOLIO_DARK_TYPT_TEMPLATE": "portfolio-dark/typst-template.typ",
    "PORTFOLIO_DARK_TYPT_SHOW": "portfolio-dark/typst-show.typ",
    "LEDGER_LIGHT_BRAND_YML": "ledger-light/brand.yml",
    "LEDGER_LIGHT_STYLES_EXTRA": "ledger-light/styles-extra.scss",
    "LEDGER_LIGHT_TYPT_TEMPLATE": "ledger-light/typst-template.typ",
    "LEDGER_LIGHT_TYPT_SHOW": "ledger-light/typst-show.typ",
    "LEDGER_DARK_BRAND_YML": "ledger-dark/brand.yml",
    "LEDGER_DARK_STYLES_EXTRA": "ledger-dark/styles-extra.scss",
    "LEDGER_DARK_TYPT_TEMPLATE": "ledger-dark/typst-template.typ",
    "LEDGER_DARK_TYPT_SHOW": "ledger-dark/typst-show.typ",
}

DOMAIN_SLUGS = {
    "EARNINGS_RECAP_QMD": "earnings-recap",
    "SECTOR_OUTLOOK_QMD": "sector-outlook",
    "THEMATIC_DEEPDIVE_QMD": "thematic-deepdive",
    "MACRO_OUTLOOK_QMD": "macro-outlook",
    "QUANT_FACTOR_BRIEF_QMD": "quant-factor-brief",
    "TECHNICAL_BRIEF_QMD": "technical-brief",
    "ESG_SUSTAINABILITY_QMD": "esg-sustainability",
    "CRYPTO_DIGITAL_QMD": "crypto-digital",
    "DESK_SYNTHESIS_QMD": "desk-synthesis",
}

for _name, _rel in SPEC.items():
    globals()[_name] = (ASSETS_DIR / _rel).read_text(encoding="utf-8")

# Typed research bodies (earnings recap, outlooks, briefs, ...): one .qmd
# per domain, exposed both as named constants and as the mapping the
# standard pipeline consumes.
for _attr, _slug in DOMAIN_SLUGS.items():
    globals()[_attr] = (ASSETS_DIR / "domains" / (_slug + ".qmd")).read_text(encoding="utf-8")

DOMAIN_BODY_TEMPLATES = {
    slug: globals()[attr] for attr, slug in DOMAIN_SLUGS.items()
}


def content_hash() -> str:
    """sha256 (12-hex) over the asset tree: sorted relpath + bytes.

    Computed live so working-tree edits stamp honestly; old manifests
    keep theirs forever (C-2 R1-F4)."""
    h = hashlib.sha256()
    for p in sorted(ASSETS_DIR.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ASSETS_DIR).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(p.read_bytes())
        h.update(b"\x00")
    return h.hexdigest()[:12]


# --- scaffold-output parity hashing (robustness plan Phase 2.5) -------------

# report.json embeds wall-clock timestamps; scaffolded text files embed the
# scaffold date (frontmatter `date: "…"` and studio header `<time>…</time>`).
# The parity gate must catch CONTENT drift, not creation time.
VOLATILE_MANIFEST_KEYS = ("created", "updated", "revision_log")

def _normalize_scaffold_text(text: str) -> str:
    import re

    text = re.sub(
        r'^date: "?\d{4}-\d{2}-\d{2}"?$', "date: <SCAFFOLD-DATE>",
        text, flags=re.MULTILINE)
    text = re.sub(
        r"<time>[^<]*</time>", "<time><SCAFFOLD-DATE></time>", text)
    return text


def canonical_file_hash(path: Path) -> str:
    """Hash one scaffolded file with wall-clock noise normalized away."""
    if path.name == "report.json":
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in VOLATILE_MANIFEST_KEYS:
            data.pop(key, None)
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()
    if path.suffix in (".qmd", ".html", ".yml", ".scss", ".typ"):
        normalized = _normalize_scaffold_text(path.read_text(encoding="utf-8"))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scaffold_tree_hash(root: Path) -> dict[str, str]:
    """{relpath: canonical hash} for every file scaffolded under root."""
    hashes: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            hashes[p.relative_to(root).as_posix()] = canonical_file_hash(p)
    return hashes
