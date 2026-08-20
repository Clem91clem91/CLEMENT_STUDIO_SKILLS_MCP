from __future__ import annotations

import argparse
import asyncio
import hashlib
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

PROOF_FILES = (
    "pyproject.toml",
    "README.md",
    "src/clement_skills_mcp/__init__.py",
    "src/clement_skills_mcp/catalog.py",
    "src/clement_skills_mcp/server.py",
    "tests/test_catalog.py",
    "tests/test_mcp_contract.py",
    ".github/workflows/ci.yml",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


async def certify_mcp(catalog: SkillsCatalog) -> None:
    async with Client(build_server(catalog)) as client:
        response = await client.list_tools()
        names = {tool.name for tool in response.tools}

        print("MCP_TOOLS=" + ",".join(sorted(names)))
        print("MCP_MISSING=" + ",".join(sorted(EXPECTED_TOOLS - names)))
        print("MCP_UNEXPECTED=" + ",".join(sorted(names - EXPECTED_TOOLS)))

        if names != EXPECTED_TOOLS:
            raise RuntimeError("MCP_TOOL_CONTRACT_MISMATCH")

        for tool in response.tools:
            if tool.annotations is None:
                raise RuntimeError(f"MCP_ANNOTATIONS_MISSING={tool.name}")
            if tool.annotations.read_only_hint is not True:
                raise RuntimeError(f"MCP_NOT_READ_ONLY={tool.name}")
            if tool.annotations.open_world_hint is not False:
                raise RuntimeError(f"MCP_OPEN_WORLD_UNEXPECTED={tool.name}")

        status_result = await client.call_tool("skills_status", {})
        if status_result.is_error:
            raise RuntimeError("MCP_SKILLS_STATUS_FAILED")
        if status_result.structured_content is None:
            raise RuntimeError("MCP_SKILLS_STATUS_UNSTRUCTURED")
        if status_result.structured_content.get("mode") != "READ_ONLY":
            raise RuntimeError("MCP_SKILLS_STATUS_NOT_READ_ONLY")
        if status_result.structured_content.get("writes_supported") is not False:
            raise RuntimeError("MCP_SKILLS_STATUS_WRITES_SUPPORTED")

        search_result = await client.call_tool(
            "skills_search",
            {"query": "agent orchestration", "limit": 5},
        )
        if search_result.is_error:
            raise RuntimeError("MCP_SKILLS_SEARCH_FAILED")

        print("MCP_LIST_TOOLS=PASS")
        print("MCP_SKILLS_STATUS=PASS")
        print("MCP_SKILLS_SEARCH=PASS")
        print("MCP_READ_ONLY_ANNOTATIONS=PASS")
        print("MCP_CONTRACT=PASS")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    default_hub = repo_root.parent / "CLEMENT_STUDIO_SKILLS_HUB"

    parser = argparse.ArgumentParser(
        description="Certify CLEMENT STUDIO Skills MCP against a real Skills Hub without writing to it."
    )
    parser.add_argument(
        "--hub-root",
        type=Path,
        default=default_hub,
        help="Skills Hub root (defaults to the sibling CLEMENT_STUDIO_SKILLS_HUB directory).",
    )
    args = parser.parse_args()

    hub_root = args.hub_root.expanduser().resolve()
    print(f"REPO_ROOT={repo_root}")
    print(f"HUB_ROOT={hub_root}")

    if not hub_root.is_dir():
        raise SystemExit(f"SKILLS_HUB_NOT_FOUND={hub_root}")

    catalog = SkillsCatalog(hub_root=hub_root)

    print("============================================================")
    print("PHASE=REAL_HUB_STATUS")
    print("============================================================")
    status = catalog.status()
    print("SKILLS_STATUS_BEGIN")
    print(json.dumps(status, indent=2, ensure_ascii=False))
    print("SKILLS_STATUS_END")
    if not status.get("ok"):
        raise SystemExit("REAL_HUB_STATUS_FAILED")

    total_entries = int(status.get("stats", {}).get("total_entries", 0) or 0)
    print(f"REGISTRY_STATE={status.get('state')}")
    print(f"TOTAL_ENTRIES={total_entries}")
    print("REAL_HUB_STATUS=PASS")

    print("============================================================")
    print("PHASE=REAL_SKILLS_SEARCH")
    print("============================================================")
    search = catalog.search(query="agent orchestration", limit=5)
    print("SKILLS_SEARCH_BEGIN")
    print(json.dumps(search, indent=2, ensure_ascii=False))
    print("SKILLS_SEARCH_END")
    search_total = int(search.get("total", 0) or 0)
    print(f"SEARCH_TOTAL={search_total}")
    if search_total == 0:
        print("SEARCH_RESULT=EMPTY_REGISTRY_OR_NO_MATCH")
    else:
        print("SEARCH_RESULT=MATCHES_FOUND")
    print("REAL_SKILLS_SEARCH=PASS")

    print("============================================================")
    print("PHASE=MCP_V2_CONTRACT")
    print("============================================================")
    asyncio.run(certify_mcp(catalog))

    print("============================================================")
    print("PHASE=SHA256_PROOFS")
    print("============================================================")
    for relative in PROOF_FILES:
        path = repo_root / relative
        if not path.is_file():
            raise SystemExit(f"PROOF_FILE_MISSING={relative}")
        print(f"SHA256={sha256(path)} FILE={relative}")

    print("============================================================")
    print("RESULT=PASS")
    print("P0_02_REAL_HUB=PASS")
    print("P0_02_REAL_SEARCH=PASS")
    print("P0_02_MCP_V2_CONTRACT=PASS")
    print("P0_02_READ_ONLY=PASS")
    print("============================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
