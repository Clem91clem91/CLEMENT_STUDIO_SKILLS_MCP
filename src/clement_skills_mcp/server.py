from __future__ import annotations

from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from .catalog import SkillsCatalog


_READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)


def build_server(catalog: SkillsCatalog | None = None) -> MCPServer:
    """Build the CLEMENT Skills MCP server with nine READ-ONLY tools."""

    catalog = catalog or SkillsCatalog()
    mcp = MCPServer("CLEMENT Skills MCP")

    @mcp.tool(
        name="skills_status",
        title="Skills status",
        description="READ-ONLY health and registry status for CLEMENT Skills Hub.",
        annotations=_READ_ONLY,
    )
    def skills_status() -> dict[str, Any]:
        return catalog.status()

    @mcp.tool(
        name="skills_list",
        title="List skills",
        description="READ-ONLY deterministic listing of normalized Skills Hub entries.",
        annotations=_READ_ONLY,
    )
    def skills_list(
        status: str | None = None,
        category: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        return catalog.list_skills(status=status, category=category, limit=limit, offset=offset)

    @mcp.tool(
        name="skills_search",
        title="Search skills",
        description="READ-ONLY deterministic metadata search without embeddings or vector databases.",
        annotations=_READ_ONLY,
    )
    def skills_search(
        query: str,
        category: str | None = None,
        statuses: list[str] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        return catalog.search(query=query, category=category, statuses=statuses, limit=limit)

    @mcp.tool(
        name="skills_get",
        title="Get skill",
        description="READ-ONLY retrieval of one normalized skill and optionally its SKILL.md content.",
        annotations=_READ_ONLY,
    )
    def skills_get(reference: str, include_content: bool = False) -> dict[str, Any]:
        return catalog.get_skill(reference=reference, include_content=include_content)

    @mcp.tool(
        name="skills_match",
        title="Match skills",
        description="READ-ONLY deterministic intent-to-skill ranking using names, keywords, categories and descriptions.",
        annotations=_READ_ONLY,
    )
    def skills_match(
        intent: str,
        category: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        return catalog.match(intent=intent, category=category, limit=limit)

    @mcp.tool(
        name="skills_dependencies",
        title="Skill dependencies",
        description="READ-ONLY dependency resolution for one skill.",
        annotations=_READ_ONLY,
    )
    def skills_dependencies(reference: str) -> dict[str, Any]:
        return catalog.dependencies(reference)

    @mcp.tool(
        name="skills_conflicts",
        title="Skill conflicts",
        description="READ-ONLY conflict resolution for one skill.",
        annotations=_READ_ONLY,
    )
    def skills_conflicts(reference: str) -> dict[str, Any]:
        return catalog.conflicts(reference)

    @mcp.tool(
        name="skills_validate",
        title="Validate skills",
        description="READ-ONLY validation of normalized skill metadata and optional content paths.",
        annotations=_READ_ONLY,
    )
    def skills_validate(
        reference: str | None = None,
        check_content: bool = False,
    ) -> dict[str, Any]:
        return catalog.validate(reference=reference, check_content=check_content)

    @mcp.tool(
        name="skills_bundle_plan",
        title="Plan skill bundle",
        description="READ-ONLY dependency-aware bundle plan with conflict and context-cost gates.",
        annotations=_READ_ONLY,
    )
    def skills_bundle_plan(
        requested: list[str],
        max_context_cost: int = 12000,
    ) -> dict[str, Any]:
        return catalog.bundle_plan(requested=requested, max_context_cost=max_context_cost)

    return mcp


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
