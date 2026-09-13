#!/usr/bin/env python3
"""One-time Phase 3 split: engine.py -> reportforge/engine/ package.

Mechanics (robustness refactor plan, Phase 3):
- Function/class bodies move VERBATIM (line ranges from ast, decorators
  included). No ast.unparse: comments and formatting survive.
- Cross-module references are rewritten to `_E.<name>` (deferred package
  attribute access), where `from reportforge import engine as _E` sits in
  each submodule header. Rewrites are applied at exact AST Name-node
  positions only — comments and docstrings are never touched.
- The seven test-stubbed globals (REPORTS_DIR, _ensure_reportforge_kernel,
  _default_reference_docx, _quarto_version, _chromium_binary,
  _toolchain_stamp, _venv_python) are ALWAYS routed through `_E.` —
  including inside their home module — so monkeypatching the facade keeps
  working everywhere.
- __init__.py is generated with an explicit re-export of every top-level
  name, so `from reportforge.engine import X` (mcp_server, cli) and
  `engine.X` attribute access (tests) are unchanged.

Run from repo root BEFORE any manual staging edits:
    .venv/bin/python scripts/split_engine.py
"""

from __future__ import annotations

import ast
import builtins
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "reportforge"
IMPL = SRC / "engine" / "_impl.py"

# name -> home module (everything not listed stays in _impl.py)
MOVED: dict[str, list[str]] = {
    "scaffold": [
        "scaffold_report", "_profile_matrix_error", "_profile_for_template",
        "_write_scaffold_manifest", "template_version", "list_templates",
        "_set_frontmatter_flag", "_frontmatter_flag", "_normalize_kpis",
        "_metric_yaml", "_normalize_key_points", "_normalize_scenarios",
        "_str_list_yaml", "_scenario_yaml", "_drop_yaml_block", "_yaml_scalar",
    ],
    "readiness": [
        "_num_value", "_frontmatter_dict", "_issue", "_body_text",
        "_readiness_structure", "_readiness_evidence",
        "_strip_code_spans_and_comments", "_cover_number",
        "_cover_values_match", "_cover_numeric_candidates",
        "_readiness_evidence_coverage", "_label_tokens", "_same_key",
        "_is_table_row", "_governor_kind", "_header_cell_for",
        "_pipe_tables", "_extract_quantities", "_section_for_line",
        "_readiness_numerical", "_scenario_pairs",
        "_stated_weighted_return", "_figure_layout_kind",
        "_readiness_layout_policies", "_readiness_presentation",
        "_readiness_editorial", "check_readiness", "record_review",
        "_missing_work_summary",
    ],
    "sections": [
        "write_report_body", "_section_op_errors", "append_section",
        "_append_locked", "_first_heading_id", "_project_root_or_error",
        "_section_spans", "_find_span", "_stale_response",
        "_check_expected", "_write_qmd_atomic", "_commit_qmd_change",
        "get_section", "replace_section", "move_section", "delete_section",
        "_set_frontmatter_description",
    ],
    "registry": [
        "_bibtex_escape", "_bibtex_escape_url", "_source_to_bibtex",
        "_ensure_bibliography", "register_source", "_check_registry_links",
        "_exhibit_anchors", "_register_exhibit_locked", "register_exhibit",
        "_register_fact_locked", "register_fact", "update_fact",
        "_parse_asof",
    ],
    "preview": [
        "render_preview", "_page_sort_key", "_numbered_pages",
        "_build_contact_sheet", "_describe_or_skip", "_file_descriptor",
    ],
    "cover": ["derive_cover", "_cover_field_fact_id", "_yaml_cover_scalar"],
    "publish": ["publish_report", "_translate_sandbox_path"],
    "charts": [
        "tokens_for_keys", "tokens_for", "_apply_quantflow_plotly_template",
        "_slugify_exhibit_id", "_anchor_chart_output", "save_chart",
        "save_asset",
    ],
    "status": [
        "open_report", "project_status", "_status_artifacts",
        "_mime_for_name", "reportforge_capabilities", "_mcp_tool_names",
        "read_project_file", "_render_state_revision",
        "_render_state_registry_version", "_manifest_view",
    ],
    "release": [
        "freeze_release", "_release_summary", "_registry_content_hash",
        "_release_inputs", "_read_release_record", "_write_release_record",
        "rollforward_report", "export_release", "_export_release_locked",
        "_bundle_artifact_id",
    ],
    "exec_env": [
        "_exec_enabled", "_project_optional", "_resolve_project_root",
        "_snapshot_project", "_diff_snapshot", "run_code", "run_file",
        "_tail",
    ],
}
HOME = {name: mod for mod, names in MOVED.items() for name in names}

# always facade-routed (tests monkeypatch these on the package)
STUBBED = {
    "REPORTS_DIR", "_ensure_reportforge_kernel", "_default_reference_docx",
    "_quarto_version", "_chromium_binary", "_toolchain_stamp",
    "_venv_python",
}


def block_span(node: ast.AST, lines: list[str]) -> tuple[int, int]:
    start = min(
        [getattr(node, "lineno", 10**9)]
        + [d.lineno for d in getattr(node, "decorator_list", [])])
    end = node.end_lineno
    return start, end


def free_engine_names(fn_node: ast.AST, engine_names: set[str]) -> set[str]:
    """Engine-level names the function LOADs but does not bind locally."""
    bound: set[str] = set()
    for node in ast.walk(fn_node):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for a in node.args.args + node.args.kwonlyargs + node.args.posonlyargs:
                    bound.add(a.arg)
                if node.args.vararg:
                    bound.add(node.args.vararg.arg)
                if node.args.kwarg:
                    bound.add(node.args.kwarg.arg)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
        elif isinstance(node, ast.comprehension):
            for t in ast.walk(node.target):
                if isinstance(t, ast.Name):
                    bound.add(t.id)
    loads = {
        node.id for node in ast.walk(fn_node)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    return {n for n in loads - bound if n in engine_names}


def collect_positions(fn_node: ast.AST, names: set[str]) -> list[tuple[int, int, int, str]]:
    """(lineno, col, end_col, name) for Load-context Name nodes in `names`."""
    out = []
    for node in ast.walk(fn_node):
        if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                and node.id in names):
            out.append((node.lineno, node.col_offset, node.end_col_offset, node.id))
    return sorted(out, reverse=True)


def apply_prefix(lines: list[str], start_line: int,
                 positions: list[tuple[int, int, int, str]]) -> list[str]:
    lines = list(lines)
    for lineno, col, end_col, name in positions:
        idx = lineno - start_line
        row = lines[idx]
        assert row[col:end_col] == name, (name, row[col:end_col], lineno)
        lines[idx] = row[:col] + "_E." + row[col:]
    return lines


def main() -> int:
    source_path = SRC / "engine.py"
    original = source_path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    tree = ast.parse(original)

    engine_names: set[str] = set()   # everything bound at module level
    engine_top_names: set[str] = set()  # defs/classes/constants only
    top_blocks: dict[str, tuple[ast.AST, int, int]] = {}
    import_lines: list[tuple[int, int]] = []  # (start, end) per import stmt
    header_end = None
    for node in tree.body:
        start, end = block_span(node, lines)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_lines.append((start, end))
            header_end = end
            for alias in node.names:
                engine_names.add((alias.asname or alias.name).split(".")[0])
            continue
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    engine_names.add(t.id)
                    engine_top_names.add(t.id)
                    top_blocks[t.id] = (node, start, end)
            continue
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            engine_names.add(node.name)
            engine_top_names.add(node.name)
            top_blocks[node.name] = (node, start, end)

    # sanity: partition covers reality
    missing = [n for n in HOME if n not in top_blocks]
    assert not missing, f"partition names not found in engine.py: {missing}"

    builtin_set = set(dir(builtins))
    imported_names = {n for n in engine_names}  # superset incl. import bindings

    def emit(fn_name: str, node: ast.AST, start: int, end: int,
             home: str | None) -> list[str]:
        body = lines[start - 1:end]
        # import bindings (json, functools, Path, ...) are never prefixed:
        # needed_imports() re-emits the original import statement instead.
        import_bindings = engine_names - engine_top_names
        if home is None:
            # stays in _impl: route stubbed + moved names through _E
            targets = ((set(HOME) | STUBBED) & engine_top_names) | (STUBBED - import_bindings)
        else:
            # extracted: every engine-level name EXCEPT this module's own
            # (decorators and intra-module calls resolve locally at import
            # time)
            own = set(MOVED[home])
            targets = ((engine_top_names - own - import_bindings) | STUBBED) - import_bindings
        positions = collect_positions(node, targets)
        out = apply_prefix(body, start, positions)
        return out

    def needed_imports(nodes: list[ast.AST]) -> list[str]:
        """Original import statements whose bindings the moved code loads."""
        bound: dict[str, list[str]] = {}
        for s, e in import_lines:
            stmt = ast.parse("".join(lines[s - 1:e])).body[0]
            names: list[str] = []
            if isinstance(stmt, ast.Import):
                for a in stmt.names:
                    names.append(a.asname or a.name.split(".")[0])
            else:
                for a in stmt.names:
                    names.append(a.asname or a.name)
            for n in names:
                bound.setdefault(n, []).append(s)
        needed = set()
        for node in nodes:
            for node_in in ast.walk(node):
                if isinstance(node_in, ast.Name) and isinstance(node_in.ctx, ast.Load):
                    if node_in.id in bound and node_in.id not in builtin_set:
                        needed.add(node_in.id)
        out = []
        for s, e in import_lines:
            stmt = ast.parse("".join(lines[s - 1:e])).body[0]
            names = ([a.asname or a.name.split(".")[0] for a in stmt.names]
                     if isinstance(stmt, ast.Import)
                     else [a.asname or a.name for a in stmt.names])
            if any(n in needed for n in names):
                out.append("".join(lines[s - 1:e]).rstrip("\n") + "\n")
        out.append("\n")
        return out

    pkg = SRC / "engine"
    pkg.mkdir(exist_ok=True)

    # ---- _impl.py ----
    impl_parts = [
        '"""Core engine: toolchain wrappers, scaffold, render, gates, release,\n'
        'execution, status. Split out per Phase 3 of the robustness refactor\n'
        'plan; the package __init__ re-exports the full surface.\n\n'
        'Cross-module and test-stubbed references go through `_E` (the\n'
        'package namespace) with deferred attribute access so monkeypatching\n'
        '`reportforge.engine.<name>` keeps working.\n"""\n\n',
        "from __future__ import annotations\n\n",
        "from reportforge import engine as _E\n\n",
    ]
    impl_parts += needed_imports(
        [top_blocks[n][0] for n in top_blocks if n not in HOME])
    impl_parts.append("\n\n")
    impl_order = [n for n in top_blocks if n not in HOME]
    impl_order.sort(key=lambda n: top_blocks[n][1])
    for n in impl_order:
        node, s, e = top_blocks[n]
        impl_parts += emit(n, node, s, e, None)
        impl_parts.append("\n\n")
    IMPL.write_text("".join(impl_parts), encoding="utf-8", newline="")

    # ---- extracted modules ----
    for home, names in MOVED.items():
        mod = pkg / f"{home}.py"
        nodes = [top_blocks[n][0] for n in names]
        parts = [
            f'"""Engine {home} cluster (Phase 3 split; see plan §4).\n\n'
            'All engine-level references go through `_E` (deferred package\n'
            'attribute access) so monkeypatching `reportforge.engine.<name>`\n'
            'keeps working.\n"""\n\n',
            "from __future__ import annotations\n\n",
            "from reportforge import engine as _E\n\n",
        ]
        parts += needed_imports(nodes)
        parts.append("\n\n")
        nodes_sorted = sorted(names, key=lambda n: top_blocks[n][1])
        for n in nodes_sorted:
            node, s, e = top_blocks[n]
            parts += emit(n, node, s, e, home)
            parts.append("\n\n")
        mod.write_text("".join(parts), encoding="utf-8", newline="")

    # ---- __init__.py facade ----
    facade = [
        '"""Engine facade (Phase 3): re-exports the full engine surface.\n\n'
        '`from reportforge.engine import X` (mcp_server, cli) and\n'
        '`engine.X` attribute access (tests, including monkeypatching the\n'
        'stub-able internals) behave exactly as when engine was one module.\n"""\n\n',
        "from __future__ import annotations\n\n",
        "from reportforge.engine._impl import (  # noqa: F401\n",
    ]
    for n in sorted(impl_order):
        facade.append(f"    {n},\n")
    facade.append(")\n")
    for home, names in MOVED.items():
        facade.append(f"from reportforge.engine.{home} import (  # noqa: F401\n")
        for n in sorted(names):
            facade.append(f"    {n},\n")
        facade.append(")\n")
    # The old single module exposed its import bindings (engine.shutil,
    # engine.sys, ...) as attributes; tests reach through them. Re-export
    # each binding from the module where needed_imports() actually placed
    # it (scan the generated files rather than tracking homes by hand).
    import_bindings = sorted(engine_names - engine_top_names)
    binding_homes: dict[str, str] = {}
    module_files = {"_impl": IMPL.read_text(encoding="utf-8")}
    for home in MOVED:
        module_files[home] = (pkg / f"{home}.py").read_text(encoding="utf-8")
    for mod_name, text in module_files.items():
        for stmt in ast.parse(text).body:
            if isinstance(stmt, ast.Import):
                for a in stmt.names:
                    binding_homes[a.asname or a.name.split(".")[0]] = mod_name
            elif isinstance(stmt, ast.ImportFrom):
                for a in stmt.names:
                    binding_homes[a.asname or a.name] = mod_name
    homeless = [b for b in import_bindings if b not in binding_homes]
    assert not homeless, f"import bindings with no generated home: {homeless}"
    grouped: dict[str, list[str]] = {}
    for binding in import_bindings:
        grouped.setdefault(binding_homes[binding], []).append(binding)
    for mod_name in sorted(grouped):
        facade.append(f"from reportforge.engine.{mod_name} import (  # noqa: F401\n")
        for n in sorted(grouped[mod_name]):
            facade.append(f"    {n},\n")
        facade.append(")\n")
    (pkg / "__init__.py").write_text("".join(facade), encoding="utf-8", newline="")

    source_path.unlink()
    print(f"split complete: _impl={len(impl_order)} names, "
          + ", ".join(f"{h}={len(v)}" for h, v in MOVED.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
