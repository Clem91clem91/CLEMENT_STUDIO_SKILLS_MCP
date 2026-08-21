from __future__ import annotations

import json
from pathlib import Path

import pytest

from clement_skills_mcp.catalog import CatalogError, SkillsCatalog


def _skill(
    skill_id: str,
    name: str,
    *,
    status: str,
    category: str,
    cost: int,
    keywords: list[str] | None = None,
    dependencies: list[str] | None = None,
    conflicts: list[str] | None = None,
    unresolved_dependencies: list[str] | None = None,
    unresolved_conflicts: list[str] | None = None,
) -> dict:
    return {
        "schema_version": "1.0.0",
        "id": skill_id,
        "name": name,
        "version": "1.0.0",
        "status": status,
        "category": category,
        "description": f"{name} deterministic capability for tests",
        "sha256": "A" * 64,
        "content_path": f"skills/{category}/{name}/SKILL.md",
        "source": {
            "canonical_path": f"source/{name}/SKILL.md",
            "library": "fixture",
            "replica_count": 1,
            "replicas": [f"source/{name}/SKILL.md"],
            "manifest_sha256": None,
        },
        "keywords": keywords or [],
        "dependencies": dependencies or [],
        "conflicts": conflicts or [],
        "unresolved_dependencies": unresolved_dependencies or [],
        "unresolved_conflicts": unresolved_conflicts or [],
        "estimated_context_cost": cost,
    }


def _build_catalog(tmp_path: Path) -> tuple[SkillsCatalog, Path]:
    hub = tmp_path / "CLEMENT_STUDIO_SKILLS_HUB"
    registry_dir = hub / "registry"
    registry_dir.mkdir(parents=True)

    skills = [
        _skill(
            "clement.coding.alpha.aaaaaaaaaaaa",
            "alpha",
            status="ACTIVE",
            category="coding",
            cost=100,
            keywords=["automation", "python"],
            dependencies=["beta"],
        ),
        _skill(
            "clement.research.beta.bbbbbbbbbbbb",
            "beta",
            status="ACTIVE",
            category="research",
            cost=50,
            keywords=["evidence", "research"],
        ),
        _skill(
            "clement.security.gamma.cccccccccccc",
            "gamma",
            status="CANDIDATE",
            category="security",
            cost=25,
            keywords=["verification", "security"],
            conflicts=["alpha"],
        ),
    ]

    payload = {
        "registry_version": "1.0.0",
        "generator_version": "0.1.0",
        "state": "MATERIALIZED",
        "source_snapshot_sha256": "B" * 64,
        "content_fingerprint": "C" * 64,
        "stats": {"total_entries": 3},
        "skills": skills,
    }
    (registry_dir / "skills_registry.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    for skill in skills:
        content = hub / skill["content_path"]
        content.parent.mkdir(parents=True, exist_ok=True)
        content.write_text(f"# {skill['name']}\n", encoding="utf-8")

    return SkillsCatalog(hub_root=hub), hub


def _mutate_registry(hub: Path, mutate) -> None:
    path = hub / "registry" / "skills_registry.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_status_reports_read_only(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    status = catalog.status()
    assert status["ok"] is True
    assert status["mode"] == "READ_ONLY"
    assert status["writes_supported"] is False
    assert status["stats"]["total_entries"] == 3


def test_list_is_deterministically_sorted(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    result = catalog.list_skills()
    assert [item["name"] for item in result["skills"]] == ["alpha", "beta", "gamma"]


def test_list_filters_status(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    result = catalog.list_skills(status="CANDIDATE")
    assert result["total"] == 1
    assert result["skills"][0]["name"] == "gamma"


def test_list_filters_category(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    result = catalog.list_skills(category="research")
    assert [item["name"] for item in result["skills"]] == ["beta"]


def test_list_paginates(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    result = catalog.list_skills(limit=1, offset=1)
    assert result["total"] == 3
    assert result["skills"][0]["name"] == "beta"


def test_list_rejects_invalid_limit(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    with pytest.raises(CatalogError, match="LIMIT_OUT_OF_RANGE"):
        catalog.list_skills(limit=0)


def test_list_rejects_negative_offset(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    with pytest.raises(CatalogError, match="OFFSET_MUST_BE_NON_NEGATIVE"):
        catalog.list_skills(offset=-1)


def test_get_by_id(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    skill = catalog.get_skill("clement.coding.alpha.aaaaaaaaaaaa")
    assert skill["name"] == "alpha"


def test_get_by_normalized_name(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    assert catalog.get_skill("ALPHA")["category"] == "coding"


def test_get_missing_raises(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    with pytest.raises(CatalogError, match="SKILL_NOT_FOUND"):
        catalog.get_skill("does-not-exist")


def test_get_can_include_skill_content(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    skill = catalog.get_skill("alpha", include_content=True)
    assert skill["content"] == "# alpha\n"


def test_content_path_cannot_escape_hub(tmp_path: Path) -> None:
    catalog, hub = _build_catalog(tmp_path)

    def mutate(payload: dict) -> None:
        payload["skills"][0]["content_path"] = "../outside/SKILL.md"

    _mutate_registry(hub, mutate)
    with pytest.raises(CatalogError, match="PATH_OUTSIDE_SKILLS_HUB"):
        catalog.get_skill("alpha", include_content=True)


def test_search_exact_name_is_top_ranked(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    result = catalog.search("alpha")
    assert result["matches"][0]["skill"]["name"] == "alpha"
    assert "exact-name-or-id" in result["matches"][0]["reasons"]


def test_search_matches_keyword(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    result = catalog.search("automation")
    assert result["matches"][0]["skill"]["name"] == "alpha"


def test_search_filters_category(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    result = catalog.search("security", category="security")
    assert [item["skill"]["name"] for item in result["matches"]] == ["gamma"]


def test_search_filters_statuses(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    result = catalog.search("deterministic", statuses=["CANDIDATE"])
    assert [item["skill"]["name"] for item in result["matches"]] == ["gamma"]


def test_empty_search_returns_deterministic_listing(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    result = catalog.search("")
    assert [item["skill"]["name"] for item in result["matches"]] == ["alpha", "beta", "gamma"]


def test_match_reports_deterministic_strategy(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    result = catalog.match("python automation")
    assert result["deterministic"] is True
    assert result["selected"][0]["skill"]["name"] == "alpha"


def test_dependencies_resolve_by_name(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    result = catalog.dependencies("alpha")
    assert [item["name"] for item in result["resolved_dependencies"]] == ["beta"]
    assert result["unresolved_dependencies"] == []


def test_dependencies_report_unresolved(tmp_path: Path) -> None:
    catalog, hub = _build_catalog(tmp_path)

    def mutate(payload: dict) -> None:
        payload["skills"][0]["dependencies"].append("missing")

    _mutate_registry(hub, mutate)
    result = catalog.dependencies("alpha")
    assert result["unresolved_dependencies"] == ["missing"]


def test_conflicts_resolve_by_name(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    result = catalog.conflicts("gamma")
    assert [item["name"] for item in result["resolved_conflicts"]] == ["alpha"]


def test_validate_accepts_valid_fixture(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    result = catalog.validate()
    assert result["valid"] is True
    assert result["checked"] == 3
    assert result["invalid"] == 0


def test_validate_detects_missing_required_field(tmp_path: Path) -> None:
    catalog, hub = _build_catalog(tmp_path)

    def mutate(payload: dict) -> None:
        del payload["skills"][0]["sha256"]

    _mutate_registry(hub, mutate)
    result = catalog.validate("alpha")
    assert result["valid"] is False
    assert "MISSING_FIELD:sha256" in result["results"][0]["issues"]


def test_validate_optional_content_check_detects_missing_file(tmp_path: Path) -> None:
    catalog, hub = _build_catalog(tmp_path)
    (hub / "skills" / "coding" / "alpha" / "SKILL.md").unlink()
    result = catalog.validate("alpha", check_content=True)
    assert "CONTENT_NOT_FOUND" in result["results"][0]["issues"]


def test_bundle_plan_orders_dependencies_first(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    result = catalog.bundle_plan(["alpha"])
    assert [item["name"] for item in result["execution_order"]] == ["beta", "alpha"]
    assert result["verdict"] == "PASS"


def test_bundle_plan_marks_candidate_partial(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    result = catalog.bundle_plan(["gamma"])
    assert result["verdict"] == "PARTIAL"
    assert result["non_active"][0]["status"] == "CANDIDATE"


def test_bundle_plan_fails_on_selected_conflict(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    result = catalog.bundle_plan(["alpha", "gamma"])
    assert result["verdict"] == "FAIL"
    assert result["conflicts"]


def test_bundle_plan_fails_on_unresolved_dependency(tmp_path: Path) -> None:
    catalog, hub = _build_catalog(tmp_path)

    def mutate(payload: dict) -> None:
        payload["skills"][0]["dependencies"] = ["missing"]

    _mutate_registry(hub, mutate)
    result = catalog.bundle_plan(["alpha"])
    assert result["verdict"] == "FAIL"
    assert result["unresolved_dependencies"] == ["missing"]


def test_bundle_plan_fails_context_budget(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    result = catalog.bundle_plan(["alpha"], max_context_cost=149)
    assert result["total_context_cost"] == 150
    assert result["verdict"] == "FAIL"


def test_bundle_plan_rejects_empty_request(tmp_path: Path) -> None:
    catalog, _ = _build_catalog(tmp_path)
    with pytest.raises(CatalogError, match="REQUESTED_SKILLS_EMPTY"):
        catalog.bundle_plan([])
