"""Task 1.1: manifest module (RF-01) — contract docs/milestone-a-contracts.md §1."""

import json
import os

import pytest

from reportforge import manifest as M

QMD = """---
title: Test Report
reportforge-template: earnings-recap
---

# Test Report

## Executive summary

Body one.

## Risks

Body two.
"""


@pytest.fixture
def proj(tmp_path):
    root = tmp_path / "demo-1m"
    root.mkdir()
    (root / "index.qmd").write_text(QMD, encoding="utf-8")
    return str(root)


def test_create_fresh_manifest(proj):
    m = M.create(proj, title="Test Report", brief="brief")
    assert m.revision == 1 and m.state == "draft"
    assert m.report_id == "demo-1m"
    assert os.path.exists(os.path.join(proj, "report.json"))
    assert [s["id"] for s in m.sections] == ["s-test-report", "s-executive-summary", "s-risks"]


def test_illegal_draft_to_exported(proj):
    m = M.create(proj, title="T")
    res = M.transition(m, "exported", actor="agent")
    assert res["ok"] is False
    assert m.state == "draft" and m.revision == 1


def test_legal_path_needs_review_record(proj):
    m = M.create(proj, title="T")
    assert M.transition(m, "review", actor="agent")["ok"] is True
    gated = M.transition(m, "approved", actor="human:fire")
    assert gated["ok"] is False  # no approved review record yet
    M.add_review(m, revision=m.revision, reviewer="human:fire", decision="approved")
    assert M.transition(m, "approved", actor="human:fire")["ok"] is True


def test_bump_reopens_to_draft_and_logs(proj):
    m = M.create(proj, title="T")
    M.transition(m, "review", actor="agent")
    M.add_review(m, revision=m.revision, reviewer="human:fire", decision="approved")
    M.transition(m, "approved", actor="human:fire")
    res = M.bump(m, "fix typo", actor="agent", op="replace_section", section_id="s-risks")
    assert res["revision"] == 2 and res["state"] == "draft"
    assert m.state == "draft"
    assert m.revision_log[-1]["summary"] == "fix typo"


def test_revision_log_capped(proj):
    m = M.create(proj, title="T")
    for i in range(70):
        M.bump(m, f"edit {i}", actor="agent")
    assert len(m.revision_log) == M.REVISION_LOG_CAP
    assert m.revision == 71


def test_save_is_atomic_and_reloadable(proj):
    m = M.create(proj, title="T")
    M.save(m, proj)
    raw = json.load(open(os.path.join(proj, "report.json"), encoding="utf-8"))
    assert raw["report_id"] == "demo-1m" and raw["revision"] == 1
    assert not [p for p in os.listdir(proj) if p.startswith(".report.json.")]


def test_manual_edit_rebuilds_index_and_bumps(proj):
    m = M.create(proj, title="T")
    assert m.revision == 1
    text = open(os.path.join(proj, "index.qmd"), encoding="utf-8").read()
    text += "\n## Outlook\n\nNew hand section.\n"
    open(os.path.join(proj, "index.qmd"), "w", encoding="utf-8").write(text)
    m2 = M.load(proj)
    assert m2.revision == 2
    assert "s-outlook" in [s["id"] for s in m2.sections]
    assert "s-risks" in [s["id"] for s in m2.sections]  # ids preserved


def test_clean_load_does_not_bump(proj):
    M.create(proj, title="T")
    m = M.load(proj)
    assert m.revision == 1


def test_import_dir(proj):
    m = M.import_dir(proj)
    assert m.revision == 1 and m.state == "draft"
    assert m.profile["report_type"] == "earnings-recap"
    assert len(m.sections) == 3
    # import never rewrites the qmd body
    assert open(os.path.join(proj, "index.qmd"), encoding="utf-8").read() == QMD


def test_newer_schema_refuses_loudly(proj, tmp_path):
    M.create(proj, title="T")
    path = os.path.join(proj, "report.json")
    raw = json.load(open(path, encoding="utf-8"))
    raw["schema_version"] = 999
    json.dump(raw, open(path, "w", encoding="utf-8"))
    with pytest.raises(M.ManifestError, match="newer schema"):
        M.load(proj)


def test_missing_manifest_errors(proj, tmp_path):
    with pytest.raises(M.ManifestError, match="no manifest"):
        M.load(str(tmp_path))


def test_events_since(proj):
    m = M.create(proj, title="T")
    M.bump(m, "e1", actor="a", op="replace_section", section_id="s-risks")
    M.bump(m, "e2", actor="a", op="move_section", section_id="s-risks")
    got = M.events_since(m, 1)
    assert got["events_truncated"] is False
    assert [e["revision"] for e in got["events"]] == [2, 3]


FENCED_QMD = """---
title: Fenced
---

# Real Heading

```python
# this comment is not a heading
## neither is this
```

Some prose.

~~~markdown
# also not a heading
~~~

## Second Real
"""


def test_fenced_code_comments_are_not_sections(proj):
    open(os.path.join(proj, "index.qmd"), "w", encoding="utf-8").write(FENCED_QMD)
    sections = M.scan_sections(FENCED_QMD)
    ids = [s["id"] for s in sections]
    assert ids == ["s-real-heading", "s-second-real"]
    # line_start still counts the fenced lines (advisory, 1-based, exact)
    assert sections[1]["line_start"] == FENCED_QMD.splitlines().index("## Second Real") + 1


def test_duplicate_headings_get_suffixed_ids():
    qmd = "# A\n\n## Results\n\n## Results\n\n## Results\n"
    ids = [s["id"] for s in M.scan_sections(qmd)]
    assert ids == ["s-a", "s-results", "s-results-2", "s-results-3"]


def test_create_refuses_to_clobber(proj):
    M.create(proj, title="T")
    m = M.load(proj)
    for _ in range(3):
        M.bump(m, "work", actor="a")
    M.save(m, proj)
    with pytest.raises(M.ManifestError, match="already exists"):
        M.create(proj, title="T2")
    assert M.load(proj).revision == 4  # history intact
    M.create(proj, title="T2", overwrite=True)
    assert M.load(proj).revision == 1  # explicit reset only


def test_illegal_transitions_fail(proj):
    m = M.create(proj, title="T")
    assert M.transition(m, "approved", actor="a")["ok"] is False  # draft -> approved
    assert M.transition(m, "bogus-state", actor="a")["ok"] is False  # unknown state
    M.transition(m, "review", actor="a")
    M.add_review(m, m.revision, "r", "approved", "ship it")
    assert M.transition(m, "approved", actor="a")["ok"] is True
    assert M.transition(m, "draft", actor="a")["ok"] is False  # approved -> draft
    assert M.transition(m, "exported", actor="a")["ok"] is True
    assert M.transition(m, "approved", actor="a")["ok"] is False  # exported -> approved


def test_double_load_does_not_bump(proj):
    M.create(proj, title="T")
    assert M.load(proj).revision == 1
    assert M.load(proj).revision == 1


def test_approval_blocked_when_registry_changed_since_review(proj):
    # R2: review records bind registry_version; registering a source after
    # the review but before approval must fail loudly, not ship stale bytes.
    m = M.create(proj, title="T")
    M.transition(m, "review", actor="a")
    M.add_review(m, m.revision, "r", "approved", "ship it")
    assert M.transition(m, "approved", actor="a")["ok"] is True
    M.transition(m, "review", actor="a")
    M.add_review(m, m.revision, "r2", "approved", "ship it again")
    m.registry_version += 1  # a registration landed after the review
    res = M.transition(m, "approved", actor="a")
    assert res["ok"] is False
    assert "registry" in res["error"]
