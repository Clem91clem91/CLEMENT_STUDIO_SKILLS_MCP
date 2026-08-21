from __future__ import annotations

import asyncio
import json
from pathlib import Path

from mcp import Client

from clement_skills_mcp.catalog import SkillsCatalog
from clement_skills_mcp.server import build_server


EXPECTED_TOOLS = {
    "skills_status",
    "skills_list",
    "skills_search",
    "skills_get",
    "skills_match",
    "skills_dependencies",
    "skills_conflicts",
    "skills_validate",
    "skills_bundle_plan",
}


def _empty_catalog(tmp_path: Path) -> SkillsCatalog:
    hub = tmp_path / "CLEMENT_STUDIO_SKILLS_HUB"
    registry = hub / "registry" / "skills_registry.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps(
            {
                "registry_version": "1.0.0",
                "generator_version": "0.1.0",
                "state": "BOOTSTRAP",
                "source_snapshot_sha256": "A" * 64,
                "content_fingerprint": None,
                "stats": {"total_entries": 0},
                "skills": [],
            }
        ),
        encoding="utf-8",
    )
    return SkillsCatalog(hub_root=hub)


async def _list_tools(catalog: SkillsCatalog):
    async with Client(build_server(catalog)) as client:
        return await client.list_tools()


async def _call_status(catalog: SkillsCatalog):
    async with Client(build_server(catalog)) as client:
        return await client.call_tool("skills_status", {})


def test_mcp_exposes_exact_read_only_tool_contract(tmp_path: Path) -> None:
    tools = asyncio.run(_list_tools(_empty_catalog(tmp_path)))
    assert {tool.name for tool in tools.tools} == EXPECTED_TOOLS
    for tool in tools.tools:
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.open_world_hint is False


def test_mcp_status_call_returns_structured_read_only_payload(tmp_path: Path) -> None:
    result = asyncio.run(_call_status(_empty_catalog(tmp_path)))
    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["ok"] is True
    assert result.structured_content["mode"] == "READ_ONLY"
    assert result.structured_content["writes_supported"] is False
