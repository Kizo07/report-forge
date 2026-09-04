"""WS-8 live smoke: drive reportforge MCP over stdio exactly as deer-flow does.

Verifies the NEW flexibility tools at the real protocol boundary (pydantic
schema validation included): bespoke scaffold, run_code, save_asset,
append_section, project_status, read_project_file, render html+pdf+pdf-web,
publish_report.

Run: .venv/bin/python scripts/smoke_mcp_flexibility.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import shutil
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

REPO = Path(__file__).resolve().parents[1]
SLUG = "smoke-mcp-flex"
DEST = Path("/tmp/smoke-mcp-flex-publish")

EXPECTED_TOOLS = {
    "reportforge_list_templates",
    "reportforge_scaffold_report",
    "reportforge_render_report",
    "reportforge_save_chart",
    "reportforge_write_report_body",
    "reportforge_publish_report",
    "reportforge_run_code",
    "reportforge_run_file",
    "reportforge_save_asset",
    "reportforge_project_status",
    "reportforge_read_project_file",
    "reportforge_append_section",
}


def payload(result) -> dict:
    """Extract the structured content from an MCP tool result."""
    content = result.content
    if content and content[0].type == "text":
        return json.loads(content[0].text)
    if getattr(result, "structured_content", None):
        return result.structured_content
    raise RuntimeError(f"unexpected result shape: {result!r}")


async def main() -> None:
    # fresh slate
    proj = REPO / "reports" / SLUG
    if proj.exists():
        shutil.rmtree(proj)
    if DEST.exists():
        shutil.rmtree(DEST)

    transport = StdioTransport(
        command=str(REPO / ".venv" / "bin" / "python"),
        args=["-m", "reportforge.mcp_server"],
    )
    async with Client(transport) as client:
        # 1. tool census — all 13 tools registered at the boundary
        tools = await client.list_tools()
        names = {t.name for t in tools}
        missing = EXPECTED_TOOLS - names
        assert not missing, f"missing tools: {missing}"
        print(f"[1] tool census ok: {len(names)} tools, all {len(EXPECTED_TOOLS)} expected present")

        # 2. bespoke scaffold — formats passed as a STRING to prove schema coercion
        r = payload(await client.call_tool(
            "reportforge_scaffold_report",
            {
                "slug": SLUG,
                "template": "bespoke",
                "formats": "html,pdf,pdf-web",  # CSV string at the boundary
                "frontmatter_yaml": 'title: "MCP Flexibility Smoke"\nauthor: "Hermes"\ndate: today',
                "body": "# Intro\n\nSmoke content.\n",
            },
        ))
        assert r["ok"], r
        assert r["formats"] == ["html", "pdf", "pdf-web"], r["formats"]
        print(f"[2] bespoke scaffold ok: {r['formats']}")

        # 3. run_code — real host execution, quant stack, file diff
        r = payload(await client.call_tool(
            "reportforge_run_code",
            {
                "project": SLUG,
                "code": (
                    "import numpy as np, pandas as pd, statsmodels.api as sm\n"
                    "rng = np.random.default_rng(3)\n"
                    "x = rng.normal(size=200); y = 0.4 * x + rng.normal(size=200)\n"
                    "beta = sm.OLS(y, sm.add_constant(x)).fit().params[1]\n"
                    "print('beta:', round(float(beta), 4))\n"
                    "pd.DataFrame({'x': x, 'y': y}).to_csv('assets/smoke-data.csv', index=False)\n"
                ),
            },
        ))
        assert r["ok"], r
        assert "beta:" in r["stdout_tail"], r["stdout_tail"]
        assert "assets/smoke-data.csv" in r["created"], r["created"]
        print(f"[3] run_code ok: {r['stdout_tail'].strip()} | created={r['created']}")

        # 4. save_asset — base64 binary
        png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"smoke" * 10).decode()
        r = payload(await client.call_tool(
            "reportforge_save_asset",
            {"project": SLUG, "dest_relpath": "assets/smoke.png", "content_b64": png},
        ))
        assert r["ok"], r
        assert r["bytes"] == 8 + 50, r  # 8-byte PNG magic + b"smoke"*10
        print(f"[4] save_asset ok: {r['relpath']} ({r['bytes']} bytes)")

        # 5. append_section — embed the generated figure + data note
        r = payload(await client.call_tool(
            "reportforge_append_section",
            {
                "project": SLUG,
                "markdown": "## Evidence\n\nSmoke regression beta estimated over 200 draws.\n",
            },
        ))
        assert r["ok"], r
        print(f"[5] append_section ok: {r['action']}")

        # 6. project_status — inspection surface
        r = payload(await client.call_tool("reportforge_project_status", {"project": SLUG}))
        assert r["ok"], r
        rels = {f["relpath"] for f in r["files"]}
        assert {"index.qmd", "assets/smoke-data.csv", "assets/smoke.png"} <= rels, rels
        print(f"[6] project_status ok: {len(r['files'])} files, formats={r['configured_formats']}")

        # 7. render html + typst pdf + pdf-web — real quarto + chromium
        r = payload(await client.call_tool(
            "reportforge_render_report", {"source": SLUG, "formats": ["html", "pdf", "pdf-web"]}
        ))
        assert r["ok"], r
        names = sorted(Path(p).name for p in r["outputs"])
        assert names == ["index-web.pdf", "index.html", "index.pdf"], names
        print(f"[7] render ok: {names}")

        # 8. read render log via the inspection tool
        r = payload(await client.call_tool(
            "reportforge_read_project_file",
            {"project": SLUG, "relpath": "output/.render-log-html.txt"},
        ))
        assert r["ok"] and "Output created" in r["content"], r
        print("[8] read_project_file ok: render log readable")

        # 9. publish_report — bridge with explicit dest (no DEERFLOW env in this smoke)
        r = payload(await client.call_tool(
            "reportforge_publish_report", {"project": SLUG, "dest_dir": str(DEST)}
        ))
        assert r["ok"], r
        entries = list(DEST.rglob("*"))
        assert (DEST / SLUG / "index.pdf").exists(), "no pdf published"
        assert (DEST / SLUG / "index-web.pdf").exists(), "no pdf-web published"
        print(f"[9] publish_report ok: {len(entries)} entries at {DEST}/{SLUG}/")

    print("\nWS-8 MCP SMOKE: ALL 9 STEPS PASSED")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except AssertionError as exc:
        print(f"\nSMOKE FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
