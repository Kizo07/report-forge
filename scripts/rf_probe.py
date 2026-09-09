#!/usr/bin/env python3
"""Milestone C live probe (checked in; /tmp probes don't survive sessions).

Reconstructs the B-8 9-case evidence probe (clean zero + 7 breaks firing
their exact codes + bespoke info) and adds 8 Milestone C end-to-end cases
with a REAL quarto render (html, then docx — no latex needed).

Run: REPORTFORGE_REPORTS_DIR is forced to a fresh tmp dir inside; the repo
tree is untouched.
  .venv/bin/python scripts/rf_probe.py
Exit nonzero on the first failure; prints PASS lines 1..17 on success.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

WORK = tempfile.mkdtemp(prefix="rf_probe_")
os.environ["REPORTFORGE_REPORTS_DIR"] = os.path.join(WORK, "reports")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from reportforge import engine  # noqa: E402

N = 0


def check(name, cond, extra=""):
    global N
    assert cond, f"PROBE FAIL [{name}]: {extra}"
    N += 1
    print(f"PASS {N:02d} {name}", flush=True)

def ecodes(slug, category="evidence"):
    res = engine.check_readiness(slug)
    assert res["ok"], res
    return [(i["code"], i["severity"])
            for i in res["categories"][category]["issues"]]


def new(slug, template="standard", formats=("html",)):
    res = engine.scaffold_report(slug, template=template,
                                 formats=list(formats))
    assert res["ok"], res
    return res


SRC = {"key": "src-probe-reg", "kind": "report",
       "title": "Probe Regime", "date": "2026-09-01"}

# --- B-8 reconstruction: clean zero ---------------------------------------
new("b-clean")
assert engine.register_source("b-clean", **SRC)["ok"] is True
root = engine.REPORTS_DIR / "b-clean"
(root / "index.qmd").write_text(
    "---\ntitle: B\nreportforge-template: standard\n"
    "date: 2026-09-08\nabstract: Probe body.\n---\n\n# B\n\n"
    "Basis [@src-probe-reg].\n")
check("b-clean-zero", ecodes("b-clean") == [], ecodes("b-clean"))

# --- B-8 breaks (each fires its exact code) ---------------------------------
new("b-cite")
engine.append_section("b-cite", "# Notes\n\nGhost [@src-nope].\n")
check("b-unregistered-cite",
      ("EVID-UNREGISTERED-CITE", "error") in ecodes("b-cite"))

new("b-exh")
engine.append_section("b-exh", "# Notes\n\nSee @fig-ghost.\n")
check("b-exhibit-unregistered",
      ("EVID-EXHIBIT-UNREGISTERED", "error") in ecodes("b-exh"))

new("b-file")
root = engine.REPORTS_DIR / "b-file"
(root / "figures").mkdir(exist_ok=True)
(root / "figures" / "m.png").write_bytes(b"png")
engine.append_section("b-file", "# Notes\n\n![M](figures/m.png){#fig-m}\n")
assert engine.register_exhibit(
    "b-file", exhibit_id="fig-m", title="M",
    file="figures/m.png")["ok"] is True
(root / "figures" / "m.png").unlink()  # vanish after registration
check("b-exhibit-file-missing",
      ("EVID-EXHIBIT-FILE-MISSING", "error") in ecodes("b-file"))

new("b-anchor")
engine.append_section("b-anchor", "# Notes\n\n![A](figures/a.png){#fig-a}\n")
assert engine.register_exhibit(
    "b-anchor", exhibit_id="fig-a", title="A", file=None)["ok"] is True
root = engine.REPORTS_DIR / "b-anchor"
qmd = root / "index.qmd"
qmd.write_text(qmd.read_text().replace("{#fig-a}", ""))
check("b-exhibit-anchor-missing",
      ("EVID-EXHIBIT-ANCHOR-MISSING", "warning") in ecodes("b-anchor"))

new("b-cover", template="bespoke", formats=("html",))
root = engine.REPORTS_DIR / "b-cover"
qmd = root / "index.qmd"
qmd.write_text("---\ntitle: C\nreportforge-template: bespoke\ntarget: 999\n---\n\n# C\n")
check("b-cover-unlinked",
      ("EVID-COVER-UNLINKED", "error") in ecodes("b-cover"))

engine.register_fact("b-cover", "fact-illust", 999.0, kind="illustrative")
check("b-cover-illustrative",
      ("EVID-COVER-ILLUSTRATIVE", "warning") in ecodes("b-cover"))

new("b-req")
check("b-missing-required",
      ("EVID-MISSING-REQUIRED", "error") in ecodes("b-req"))

new("b-info", template="bespoke")
check("b-bespoke-info",
      ("EVID-NO-REQUIRED-LIST", "info") in ecodes("b-info"))

# --- C-10: separate real renders share one release --------------------------
new("c-rel", formats=("html", "docx"))
assert engine.register_source("c-rel", **SRC)["ok"] is True
engine.append_section("c-rel", "# Notes\n\nBasis [@src-probe-reg].\n")
r1 = engine.render_report("c-rel", formats=["html"])
assert r1["ok"], r1
rel1 = json.loads((engine.REPORTS_DIR / "c-rel" / "output"
                   / "release.json").read_text())
r2 = engine.render_report("c-rel", formats=["docx"])
assert r2["ok"], r2
rel2 = json.loads((engine.REPORTS_DIR / "c-rel" / "output"
                   / "release.json").read_text())
check("c-shared-release",
      rel1["release_id"] == rel2["release_id"]
      and set(rel2["artifacts"]) == {"html", "docx"},
      f"{rel1.get('release_id')} vs {rel2.get('release_id')}")

# --- C-11: qmd edit between renders refuses to mix ---------------------------
qmd = engine.REPORTS_DIR / "c-rel" / "index.qmd"
qmd.write_text(qmd.read_text() + "\n<!-- probe edit -->\n")
mix = engine.render_report("c-rel", formats=["docx"])
check("c-stale-mix-fails",
      mix["ok"] is False and ("snapshot" in mix["error"]
                              or "re-render" in mix["error"]), mix)
ok = engine.render_report("c-rel", formats=["html", "docx"])
assert ok["ok"], ok

# --- C-12: freeze verifies ----------------------------------------------------
fr = engine.freeze_release("c-rel")
check("c-freeze-verified",
      fr["ok"] is True and fr["verified"] is True, fr)

# --- C-13: rollforward carries + stale checklist -------------------------------
assert engine.register_fact(
    "c-rel", "fact-oldrev", 5.0, as_of="2026-01-01")["ok"] is True
rf = engine.rollforward_report("c-rel", "c-rel-q4", brief="Q4 refresh",
                               params={"period": "Q4-2026",
                                       "as_of": "2026-11-30"})
check("c-rollforward", rf["ok"] is True
      and rf["carried"]["sources"] == 1
      and rf["stale"] == ["fact-oldrev"]
      and rf["supersedes"]["report"] == "c-rel", rf)

# --- C-14: derive_cover binds ---------------------------------------------------
new("c-cov", template="bespoke")
root = engine.REPORTS_DIR / "c-cov"
(root / "index.qmd").write_text(
    "---\ntitle: C\nreportforge-template: bespoke\ntarget: 1\n---\n\n# C\n")
engine.register_fact("c-cov", "fact-target", 42.0)
dc = engine.derive_cover("c-cov")
check("c-derive", dc["ok"] is True
      and "EVID-COVER-UNLINKED" not in [c for c, _ in ecodes("c-cov")], dc)

# --- C-15: derived weights split stays checked ----------------------------------
root = engine.REPORTS_DIR / "c-cov"
(root / "index.qmd").write_text(
    "---\ntitle: C\nreportforge-template: bespoke\ncover_derived: true\n"
    "scenarios:\n  - {label: bear, value: 30}\n"
    "  - {label: base, value: 40}\n"
    "  - {label: bull, value: 30}\n---\n\n# C\n")
for fid, val in (("fact-scenarios-0-value", 30.0),
                 ("fact-scenarios-1-value", 40.0),
                 ("fact-scenarios-2-value", 30.0)):
    engine.register_fact("c-cov", fid, val)
assert engine.derive_cover("c-cov")["ok"] is True
engine.update_fact("c-cov", "fact-scenarios-1-value", value=41.0)
check("c-weights-exempt",
      ("EVID-COVER-UNLINKED", "error") in ecodes("c-cov"))

# --- C-16: layout policy fires live ----------------------------------------------
new("c-lay", template="bespoke")
root = engine.REPORTS_DIR / "c-lay"
(root / "index.qmd").write_text(
    "---\ntitle: L\nreportforge-template: bespoke\n---\n\n# L\n\n"
    "![Wide](figures/w.png){#fig-w width=95%}\n")
assert engine.register_exhibit(
    "c-lay", exhibit_id="fig-w", title="W", file=None)["ok"] is True
pres = [i["code"] for i in
        engine.check_readiness("c-lay")["categories"]["presentation"]["issues"]]
check("c-layout-policy", "PRES-ALT-MISSING" in pres, pres)

# --- C-17: export embeds the sealed release ---------------------------------------
mpath = engine.REPORTS_DIR / "c-rel" / "report.json"
m = json.loads(mpath.read_text())
m["state"] = "approved"
mpath.write_text(json.dumps(m))
dest = os.path.join(WORK, "bundles")
ex = engine.export_release("c-rel", dest=dest)
assert ex["ok"], ex
bundle_release = Path(dest) / "c-rel" / f"r{ex['revision']}" / "release.json"
check("c-export-embeds", bundle_release.is_file(), ex)

print(f"\nALL {N} PROBE CHECKS PASSED")
