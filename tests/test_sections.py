"""Task 1.3 — section operations (contract §2, docs/milestone-a-contracts.md).

Ops address sections by stable id (s- + slugified heading); mutating ops take
expected_revision; stale mismatch returns ok:false + changed_sections; append
is idempotent under a caller key; unrelated bytes are preserved exactly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from reportforge import engine
from reportforge import manifest as manifest_mod


@pytest.fixture
def isolated_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    reports = tmp_path / "reports"
    monkeypatch.setattr(engine, "REPORTS_DIR", reports)
    monkeypatch.setattr(engine, "_ensure_reportforge_kernel", lambda: "reportforge")
    monkeypatch.setattr(engine, "_default_reference_docx", lambda: None)
    return reports


@pytest.fixture
def sectioned_report(isolated_reports: Path) -> Path:
    """Scaffolded 'standard' report with a fresh manifest (revision 1, draft)."""
    result = engine.scaffold_report(
        "sections-fixture",
        template="standard",
        formats=["html"],
    )
    assert result["ok"] is True
    root = Path(result["path"])
    # Task 1.2 will make scaffold write the manifest itself; until then the
    # contract-defined import path (§1.6 import_dir) creates it from the QMD.
    if not (root / "report.json").exists():
        manifest_mod.import_dir(root)
    return root


def _section_ids(root: Path) -> list[str]:
    return [s["id"] for s in manifest_mod.load(root).sections]


# --- get_section ---------------------------------------------------------------

def test_get_section_returns_markdown_level_and_byte_range(sectioned_report: Path) -> None:
    res = engine.get_section("sections-fixture", "s-executive-summary")
    assert res["ok"] is True
    assert res["section_id"] == "s-executive-summary"
    assert res["title"] == "Executive summary"
    assert res["level"] == 1
    assert res["markdown"].startswith("# Executive summary")
    start, end = res["byte_range"]
    text = (sectioned_report / "index.qmd").read_text()
    assert text[start:end] == res["markdown"]


def test_get_section_read_only_no_bump(sectioned_report: Path) -> None:
    before = (sectioned_report / "index.qmd").read_bytes()
    res = engine.get_section("sections-fixture", "s-analysis")
    assert res["ok"] is True
    m = manifest_mod.load(sectioned_report)
    assert m.revision == 1
    assert (sectioned_report / "index.qmd").read_bytes() == before


def test_get_section_unknown_id_is_clean_error(sectioned_report: Path) -> None:
    res = engine.get_section("sections-fixture", "s-does-not-exist")
    assert res["ok"] is False
    assert "error" in res


def test_section_scope_deeper_headings_belong_shallower_do_not(
    sectioned_report: Path,
) -> None:
    """# Analysis spans ## Data and method + ## Findings; # Recommendations ends it."""
    res = engine.get_section("sections-fixture", "s-analysis")
    assert res["ok"] is True
    assert "## Data and method" in res["markdown"]
    assert "## Findings" in res["markdown"]
    assert "# Recommendations" not in res["markdown"]


# --- replace_section -----------------------------------------------------------

def test_replace_section_changes_one_section_rest_byte_identical(
    sectioned_report: Path,
) -> None:
    qmd = sectioned_report / "index.qmd"
    original = qmd.read_bytes()
    res = engine.get_section("sections-fixture", "s-recommendations")
    start, end = res["byte_range"]
    new_md = "# Recommendations\n\nBuy high, sell low, but later.\n"
    rep = engine.replace_section(
        "sections-fixture", "s-recommendations", new_md, expected_revision=1
    )
    assert rep["ok"] is True
    assert rep["revision"] == 2

    now = qmd.read_bytes()
    assert new_md.encode() in now
    # Everything outside the replaced range is byte-identical.
    assert now.startswith(original[:start])
    assert now.endswith(original[end:])


def test_replace_section_rebuilds_manifest_index(sectioned_report: Path) -> None:
    engine.replace_section(
        "sections-fixture",
        "s-recommendations",
        "# Next steps\n\nDo these.\n",
        expected_revision=1,
    )
    ids = _section_ids(sectioned_report)
    assert "s-recommendations" not in ids
    assert "s-next-steps" in ids


def test_replace_section_stale_revision_returns_context(
    sectioned_report: Path,
) -> None:
    # Advance the manifest to revision 2 with one real edit.
    engine.replace_section(
        "sections-fixture", "s-background", "# Background\n\nNewer context.\n",
        expected_revision=1,
    )
    res = engine.replace_section(
        "sections-fixture", "s-background", "# Background\n\nClobbered?\n",
        expected_revision=1,
    )
    assert res["ok"] is False
    assert res["stale_revision"] is True
    assert res["current_revision"] == 2
    assert res["changed_sections"]
    evt = res["changed_sections"][0]
    assert evt["id"] == "s-background"
    assert evt["event"] == "replaced"
    assert evt["revision"] == 2
    assert "hint" in res
    # Rejected op changed nothing.
    assert manifest_mod.load(sectioned_report).revision == 2


def test_replace_section_missing_expected_revision_arg_is_required(
    sectioned_report: Path,
) -> None:
    res = engine.replace_section("sections-fixture", "s-background", "# X\n")
    assert res["ok"] is False
    assert "expected_revision" in res["error"]


# --- move_section --------------------------------------------------------------

def test_move_section_before_another_moves_block_as_unit(
    sectioned_report: Path,
) -> None:
    res = engine.move_section(
        "sections-fixture", "s-recommendations", before_section_id="s-executive-summary",
        expected_revision=1,
    )
    assert res["ok"] is True
    assert res["revision"] == 2
    text = (sectioned_report / "index.qmd").read_text()
    rec = text.index("# Recommendations")
    exec_sum = text.index("# Executive summary")
    bg = text.index("# Background")
    assert rec < exec_sum < bg


def test_move_section_to_end(sectioned_report: Path) -> None:
    res = engine.move_section(
        "sections-fixture", "s-executive-summary", to_end=True, expected_revision=1
    )
    assert res["ok"] is True
    text = (sectioned_report / "index.qmd").read_text()
    assert text.rindex("# Executive summary") > text.index("# Analysis")


def test_move_section_stale_revision_noop(sectioned_report: Path) -> None:
    before = (sectioned_report / "index.qmd").read_bytes()
    res = engine.move_section(
        "sections-fixture", "s-exec-summary", to_end=True, expected_revision=99
    )
    assert res["ok"] is False
    assert res["stale_revision"] is True
    assert (sectioned_report / "index.qmd").read_bytes() == before


# --- delete_section ------------------------------------------------------------

def test_delete_section_removes_block_and_bumps(sectioned_report: Path) -> None:
    res = engine.delete_section("sections-fixture", "s-appendix", expected_revision=1)
    assert res["ok"] is True
    assert res["revision"] == 2
    assert "s-appendix" not in _section_ids(sectioned_report)
    assert "# Appendix {.appendix}" not in (sectioned_report / "index.qmd").read_text()


def test_delete_section_stale_revision_reports_changed_sections(
    sectioned_report: Path,
) -> None:
    engine.delete_section("sections-fixture", "s-appendix", expected_revision=1)
    res = engine.delete_section("sections-fixture", "s-background", expected_revision=1)
    assert res["ok"] is False
    assert res["current_revision"] == 2
    assert any(e["id"] == "s-appendix" and e["event"] == "deleted" for e in res["changed_sections"])


# --- append_section idempotency ------------------------------------------------

def test_append_with_idempotency_key_replay_is_noop(sectioned_report: Path) -> None:
    md = "# Odd lots\n\nLeftover observations.\n"
    first = engine.append_section(
        "sections-fixture", md, idempotency_key="agent1-42"
    )
    assert first["ok"] is True
    assert first["idempotent_replay"] is False
    rev = first["revision"]
    section_id = first["section_id"]
    assert rev == 2 and section_id

    body_after_first = (sectioned_report / "index.qmd").read_bytes()

    replay = engine.append_section(
        "sections-fixture", md, idempotency_key="agent1-42"
    )
    assert replay["ok"] is True
    assert replay["idempotent_replay"] is True
    assert replay["revision"] == rev
    assert replay["section_id"] == section_id
    assert (sectioned_report / "index.qmd").read_bytes() == body_after_first
    assert manifest_mod.load(sectioned_report).revision == rev


def test_append_without_key_never_noop(sectioned_report: Path) -> None:
    r1 = engine.append_section("sections-fixture", "# Notes A\n\nA.\n")
    assert r1["ok"] is True
    r2 = engine.append_section("sections-fixture", "# Notes A\n\nA.\n")
    assert r2["ok"] is True
    assert r2["revision"] > r1["revision"]


# --- manifest consistency ------------------------------------------------------

def test_mutating_ops_record_revision_log(sectioned_report: Path) -> None:
    engine.replace_section(
        "sections-fixture", "s-background", "# Background\n\nv2.\n", expected_revision=1
    )
    m = manifest_mod.load(sectioned_report)
    assert m.revision == 2
    log = getattr(m, "revision_log", [])
    assert log, "revision_log must record mutating ops (contract §2.3)"
    last = log[-1]
    assert last["op"] == "replace"
    assert last["section_id"] == "s-background"
    assert last["revision"] == 2


# --- MCP surface ---------------------------------------------------------------

def test_mcp_section_tools_registered() -> None:
    import asyncio

    from reportforge.mcp_server import mcp

    tools = {t.name for t in asyncio.run(mcp.list_tools())}
    for name in (
        "reportforge_get_section",
        "reportforge_replace_section",
        "reportforge_move_section",
        "reportforge_delete_section",
    ):
        assert name in tools, f"missing MCP tool {name}"


def test_mcp_replace_section_tool_takes_expected_revision() -> None:
    import asyncio

    from reportforge.mcp_server import mcp

    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    props = tools["reportforge_replace_section"].parameters["properties"]
    assert "expected_revision" in props
    append_props = tools["reportforge_append_section"].parameters["properties"]
    assert "idempotency_key" in append_props


# --- critic-1 RF-02 review regressions ---------------------------------------

def test_stale_window_scoped_to_caller_revision(sectioned_report: Path) -> None:
    """changed_sections covers caller-rev → current, not the whole log."""
    for i in range(6):  # rev 2..7, all on s-background
        r = engine.replace_section(
            "sections-fixture", "s-background",
            f"# Background\n\nEdit {i}.\n", expected_revision=1 + i,
        )
        assert r["ok"] is True
    res = engine.replace_section(
        "sections-fixture", "s-background", "# Background\n\nStale.\n",
        expected_revision=6,
    )
    assert res["ok"] is False and res["stale_revision"] is True
    assert res["current_revision"] == 7
    revs = [e["revision"] for e in res["changed_sections"]]
    assert revs == [7], f"window must be caller-blind-spot only, got {revs}"
    assert res["events_truncated"] is False


def test_append_first_heading_ignores_fenced_code(sectioned_report: Path) -> None:
    md = "```python\n# not a heading\n```\n\n# Real Section\n\nBody.\n"
    res = engine.append_section("sections-fixture", md)
    assert res["ok"] is True
    assert res["section_id"] == "s-real-section"
    m = manifest_mod.load(sectioned_report)
    assert m.revision_log[-1]["section_id"] == "s-real-section"


def test_append_first_heading_strips_quarto_attrs(sectioned_report: Path) -> None:
    res = engine.append_section("sections-fixture", "# Annex {.appendix}\n\nBody.\n")
    assert res["ok"] is True
    assert res["section_id"] == "s-annex"


def test_move_noop_does_not_bump(sectioned_report: Path) -> None:
    # s-scope already sits directly before s-background: the move is
    # byte-identical, so it must not bump (§1.3 — content-changing ops only).
    before = (sectioned_report / "index.qmd").read_bytes()
    res = engine.move_section(
        "sections-fixture", "s-scope",
        before_section_id="s-background", expected_revision=1,
    )
    assert res["ok"] is True
    assert res.get("moved") is False
    assert res["revision"] == 1
    assert (sectioned_report / "index.qmd").read_bytes() == before
    assert manifest_mod.load(sectioned_report).revision == 1


def test_replace_without_heading_warns(sectioned_report: Path) -> None:
    res = engine.replace_section(
        "sections-fixture", "s-background", "Just prose, no heading.\n",
        expected_revision=1,
    )
    assert res["ok"] is True
    assert "warning" in res
    assert "s-background" not in _section_ids(sectioned_report)


def test_section_op_non_utf8_qmd_is_clean_error(sectioned_report: Path) -> None:
    (sectioned_report / "index.qmd").write_bytes(b"# Bad \xff\xfe\n\nbody\n")
    res = engine.get_section("sections-fixture", "s-anything")
    assert res["ok"] is False
    assert "error" in res  # dict, never an exception across the boundary


def test_multibyte_section_byte_range_roundtrips(sectioned_report: Path) -> None:
    md = "# Ünïcodé Nötés\n\nCafé naïve — €42.\n"
    res = engine.append_section("sections-fixture", md)
    assert res["ok"] is True
    got = engine.get_section("sections-fixture", res["section_id"])
    assert got["ok"] is True
    assert "Café" in got["markdown"]
    text = (sectioned_report / "index.qmd").read_text(encoding="utf-8")
    start, end = got["byte_range"]
    assert text.encode("utf-8")[start:end].decode("utf-8") == got["markdown"]


def test_mcp_move_delete_require_expected_revision() -> None:
    import asyncio

    from reportforge.mcp_server import mcp

    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    for name in ("reportforge_move_section", "reportforge_delete_section"):
        required = tools[name].parameters.get("required", [])
        assert "expected_revision" in required, f"{name} must require expected_revision"
