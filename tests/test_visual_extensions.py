"""Contract: vendored visual Quarto extensions + studio-white chart theme.

Impl E vendors the iconify and highlight-text Quarto extensions
(quarto-add equivalent: upstream `_extensions/<name>/` payloads copied
byte-identical into `_shared/_extensions/`) and registers them in the
pilot families' configs (portfolio-light via _shared/portfolio.yml,
studio via studio/studio.yml) per each extension's docs. The
studio-white Plotly palette mirrors the studio brand tokens
(navy/steel on white) instead of the portfolio gold it was copied from.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from reportforge import templates as templates_mod
from reportforge.engine._impl import QUANTFLOW_PLOTLY_THEMES

ASSETS = templates_mod.ASSETS_DIR
EXT_DIR = ASSETS / "_shared" / "_extensions"

# Registered filter names, per each extension's docs:
# - highlight-text docs (index.qmd/reference.qmd): `filters: [- highlight-text]`
# - iconify docs (reference.qmd "Offline icons"): `filters: [- iconify]`
#   (shortcode works unregistered; the filter enables preload and is a
#   no-op without `extensions.iconify.preload` metadata).
EXPECTED_FILTERS = ["iconify", "highlight-text"]

PILOT_YMLS = (
    "_shared/portfolio.yml",  # portfolio-light (also serves ledger/* + portfolio-dark)
    "studio/studio.yml",  # studio
)

# Extension dir -> documented _extension.yml contributions that must exist.
EXPECTED_CONTRIBUTES = {
    "iconify": {"shortcodes": ["iconify.lua"], "filters": ["iconify-filter.lua"]},
    "highlight-text": {"filters": ["highlight-text.lua"]},
}


def _load_yml(rel: str) -> dict:
    text = (ASSETS / rel).read_text(encoding="utf-8")
    return yaml.safe_load(text)


def test_vendored_extensions_present_with_manifest():
    """Both extensions exist with a readable _extension.yml manifest."""
    assert EXT_DIR.is_dir(), f"missing vendored extensions dir: {EXT_DIR}"
    for name in EXPECTED_FILTERS:
        ext = EXT_DIR / name
        assert ext.is_dir(), f"missing vendored extension: {name}"
        manifest = ext / "_extension.yml"
        assert manifest.is_file(), f"missing _extension.yml for {name}"
        data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        assert data.get("title"), f"{name}: manifest has no title"
        assert data.get("contributes"), f"{name}: manifest contributes nothing"


def test_vendored_contributions_match_docs():
    """Each manifest's documented shortcodes/filters exist as files, and
    the registered filter name matches the extension directory (Quarto
    convention used in both extensions' docs)."""
    for name, expected in EXPECTED_CONTRIBUTES.items():
        ext = EXT_DIR / name
        manifest = yaml.safe_load((ext / "_extension.yml").read_text(encoding="utf-8"))
        contributes = manifest["contributes"]
        for kind, files in expected.items():
            assert kind in contributes, f"{name}: manifest lacks {kind}"
            for fname in files:
                assert fname in contributes[kind], f"{name}: {kind} lacks {fname}"
                assert (ext / fname).is_file(), f"{name}: missing {kind} file {fname}"


def test_pilot_families_register_both_filters():
    """portfolio-light + studio configs register exactly the documented
    filter names."""
    for rel in PILOT_YMLS:
        config = _load_yml(rel)
        assert config.get("filters") == EXPECTED_FILTERS, (
            f"{rel}: filters={config.get('filters')!r}, "
            f"expected {EXPECTED_FILTERS!r}"
        )


def test_scaffolded_pilot_carries_vendored_extensions(tmp_path, monkeypatch):
    """A scaffolded pilot project must contain the _extensions payload its
    _quarto.yml declares, or Quarto cannot render it standalone."""
    from reportforge import engine

    monkeypatch.setattr(engine, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "reportforge")
    monkeypatch.setattr(engine, "_default_reference_docx", lambda: None)
    result = engine.scaffold_report("visual-pilot", template="studio", formats=["html"])
    assert result["ok"], result
    root = tmp_path / "reports" / "visual-pilot"
    for name in EXPECTED_FILTERS:
        assert (root / "_extensions" / name / "_extension.yml").is_file(), name
    standard = engine.scaffold_report("visual-std", template="standard", formats=["html"])
    assert standard["ok"], standard
    assert not (tmp_path / "reports" / "visual-std" / "_extensions").exists()


def test_non_pilot_families_unregistered():
    """No other template config registers the visual extensions (pilot
    scope is portfolio-light + studio only)."""
    for rel in ("_shared/quarto.yml", "_shared/bespoke.yml", "modern/modern.yml"):
        text = (ASSETS / rel).read_text(encoding="utf-8")
        for name in EXPECTED_FILTERS:
            assert name not in text, f"{rel}: out-of-pilot registration of {name}"


def test_studio_white_matches_studio_brand():
    """studio-white chart colours equal the studio brand tokens, read
    from the brand file (not hardcoded on both sides)."""
    brand = yaml.safe_load((ASSETS / "studio" / "brand.yml").read_text(encoding="utf-8"))
    pal = QUANTFLOW_PLOTLY_THEMES["studio-white"]
    assert pal["paper_bg"] == brand["color"]["background"]
    assert pal["plot_bg"] == brand["color"]["palette"]["mist"]
    assert pal["font"] == brand["color"]["foreground"]
    assert pal["primary"] == brand["color"]["primary"] == brand["color"]["palette"]["navy"]
    assert pal["secondary"] == brand["color"]["secondary"] == brand["color"]["palette"]["steel"]
    assert pal["positive"] == brand["color"]["success"]
    assert pal["negative"] == brand["color"]["danger"]
    assert pal["muted"] == brand["color"]["tertiary"] == brand["color"]["palette"]["slate"]
    # Ramp follows the house pattern (light/primary/dark primary,
    # secondary/dark secondary) anchored on the brand navy/steel.
    assert pal["ramp"][1] == pal["primary"]
    assert pal["ramp"][3] == pal["secondary"]
    # No warm-paper portfolio leftovers from the copy-paste origin.
    blob = " ".join([pal["paper_bg"], pal["plot_bg"], pal["font"], pal["grid"],
                     pal["primary"], pal["secondary"], pal["positive"],
                     pal["negative"], pal["muted"], *pal["ramp"]])
    for leftover in ("#8f621f", "#14756c", "#f8f7f3", "#362e21", "#d3c8b0",
                     "#c62828", "#6d6250", "#0f4c44"):
        assert leftover not in blob, f"portfolio leftover {leftover} in studio-white"
