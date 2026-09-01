from __future__ import annotations

import asyncio

from reportforge.mcp_server import mcp


def test_mcp_scaffold_schema_exposes_studio_visual_options() -> None:
    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}

    scaffold = tools["reportforge_scaffold_report"]
    properties = scaffold.parameters["properties"]
    assert {
        "organization",
        "eyebrow",
        "title_layout",
        "accent",
        "metrics",
    } <= set(properties)
    assert properties["title_layout"]["default"] == "hero"
    assert properties["accent"]["default"] == "#4f46e5"
