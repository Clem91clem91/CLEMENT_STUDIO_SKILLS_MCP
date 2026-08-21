from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable


SKILL_STATUSES = {
    "ACTIVE",
    "CANDIDATE",
    "NEEDS_REVIEW",
    "DEPRECATED",
    "ARCHIVED",
    "CONFLICT",
    "INCOMPLETE",
}

SKILL_CATEGORIES = {
    "coding",
    "documents",
    "research",
    "3d",
    "blender",
    "unreal",
    "comfyui",
    "filesystem",
    "github",
    "orchestration",
    "security",
    "other",
}

REQUIRED_FIELDS = {
    "schema_version",
    "id",
    "name",
    "version",
    "status",
    "category",
    "description",
    "sha256",
    "content_path",
    "source",
    "keywords",
    "dependencies",
    "conflicts",
    "unresolved_dependencies",
    "unresolved_conflicts",
    "estimated_context_cost",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class CatalogError(RuntimeError):
    """Raised when the Skills Hub registry cannot satisfy a read request."""


def _norm(value: str) -> str:
    return "-".join(_TOKEN_RE.findall(str(value).lower()))


def _tokens(value: str) -> set[str]:
    return set(_TOKEN_RE.findall(str(value).lower()))


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


class SkillsCatalog:
    """Deterministic, filesystem READ-ONLY view of CLEMENT STUDIO Skills Hub."""

    def __init__(
        self,
        hub_root: str | Path | None = None,
        registry_path: str | Path | None = None,
    ) -> None:
        default_hub = Path(__file__).resolve().parents[3] / "CLEMENT_STUDIO_SKILLS_HUB"
        configured_hub = hub_root or os.environ.get("CLEMENT_SKILLS_HUB_ROOT") or default_hub
        self.hub_root = Path(configured_hub).expanduser().resolve()

        configured_registry = registry_path or os.environ.get("CLEMENT_SKILLS_REGISTRY_PATH")
        self.registry_path = (
            Path(configured_registry).expanduser().resolve()
            if configured_registry
            else (self.hub_root / "registry" / "skills_registry.json").resolve()
        )

    def _assert_within_hub(self, path: Path) -> Path:
        resolved = path.expanduser().resolve()
        try:
            resolved.relative_to(self.hub_root)
        except ValueError as exc:
            raise CatalogError(f"PATH_OUTSIDE_SKILLS_HUB={resolved}") from exc
        return resolved

    def _load_registry(self) -> dict[str, Any]:
        registry = self._assert_within_hub(self.registry_path)
        if not registry.is_file():
            raise CatalogError(f"SKILLS_REGISTRY_NOT_FOUND={registry}")
        try:
            payload = json.loads(registry.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CatalogError(f"SKILLS_REGISTRY_INVALID_JSON={registry}") from exc

        if not isinstance(payload, dict):
            raise CatalogError("SKILLS_REGISTRY_ROOT_NOT_OBJECT")
        if not isinstance(payload.get("skills"), list):
            raise CatalogError("SKILLS_REGISTRY_SKILLS_NOT_ARRAY")
        return payload

    def _skills(self) -> list[dict[str, Any]]:
        skills = [item for item in self._load_registry()["skills"] if isinstance(item, dict)]
        return sorted(skills, key=lambda item: (_norm(item.get("name", "")), str(item.get("id", ""))))

    def _resolve_ref(self, reference: str) -> dict[str, Any] | None:
        wanted = _norm(reference)
        for skill in self._skills():
            if str(skill.get("id", "")) == reference:
                return skill
            if _norm(str(skill.get("name", ""))) == wanted:
                return skill
        return None

    def _read_content(self, skill: dict[str, Any]) -> str:
        relative = str(skill.get("content_path", "")).strip()
        if not relative:
            raise CatalogError(f"SKILL_CONTENT_PATH_MISSING={skill.get('id', skill.get('name', 'unknown'))}")
        target = self._assert_within_hub(self.hub_root / relative)
        if not target.is_file():
            raise CatalogError(f"SKILL_CONTENT_NOT_FOUND={target}")
        return target.read_text(encoding="utf-8")

    def status(self) -> dict[str, Any]:
        try:
            registry = self._load_registry()
            return {
                "ok": True,
                "mode": "READ_ONLY",
                "hub_root": str(self.hub_root),
                "registry_path": str(self.registry_path),
                "registry_version": registry.get("registry_version"),
                "generator_version": registry.get("generator_version"),
                "state": registry.get("state"),
                "content_fingerprint": registry.get("content_fingerprint"),
                "source_snapshot_sha256": registry.get("source_snapshot_sha256"),
                "stats": registry.get("stats", {}),
                "writes_supported": False,
            }
        except CatalogError as exc:
            return {
                "ok": False,
                "mode": "READ_ONLY",
                "hub_root": str(self.hub_root),
                "registry_path": str(self.registry_path),
                "error": str(exc),
                "writes_supported": False,
            }

    def list_skills(
        self,
        status: str | None = None,
        category: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        if limit < 1 or limit > 500:
            raise CatalogError("LIMIT_OUT_OF_RANGE=1..500")
        if offset < 0:
            raise CatalogError("OFFSET_MUST_BE_NON_NEGATIVE")

        skills = self._skills()
        if status:
            skills = [skill for skill in skills if skill.get("status") == status]
        if category:
            skills = [skill for skill in skills if skill.get("category") == category]

        page = skills[offset : offset + limit]
        return {
            "total": len(skills),
            "offset": offset,
            "limit": limit,
            "skills": page,
        }

    def get_skill(self, reference: str, include_content: bool = False) -> dict[str, Any]:
        skill = self._resolve_ref(reference)
        if skill is None:
            raise CatalogError(f"SKILL_NOT_FOUND={reference}")
        result = dict(skill)
        if include_content:
            result["content"] = self._read_content(skill)
        return result

    def search(
        self,
        query: str,
        category: str | None = None,
        statuses: Iterable[str] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        if limit < 1 or limit > 100:
            raise CatalogError("LIMIT_OUT_OF_RANGE=1..100")

        query_tokens = _tokens(query)
        query_norm = _norm(query)
        allowed_statuses = set(statuses or [])
        matches: list[dict[str, Any]] = []

        for skill in self._skills():
            if category and skill.get("category") != category:
                continue
            if allowed_statuses and skill.get("status") not in allowed_statuses:
                continue

            name = str(skill.get("name", ""))
            skill_id = str(skill.get("id", ""))
            description = str(skill.get("description", ""))
            keyword_values = [str(item) for item in _as_list(skill.get("keywords"))]

            name_tokens = _tokens(name)
            id_tokens = _tokens(skill_id)
            keyword_tokens = set().union(*(_tokens(item) for item in keyword_values)) if keyword_values else set()
            description_tokens = _tokens(description)
            category_tokens = _tokens(str(skill.get("category", "")))
            all_tokens = name_tokens | id_tokens | keyword_tokens | description_tokens | category_tokens

            score = 0
            reasons: list[str] = []

            if query_norm and query_norm in {_norm(name), _norm(skill_id)}:
                score += 100
                reasons.append("exact-name-or-id")

            name_overlap = len(query_tokens & name_tokens)
            keyword_overlap = len(query_tokens & keyword_tokens)
            description_overlap = len(query_tokens & description_tokens)
            category_overlap = len(query_tokens & category_tokens)

            if name_overlap:
                score += 20 * name_overlap
                reasons.append(f"name-tokens:{name_overlap}")
            if keyword_overlap:
                score += 10 * keyword_overlap
                reasons.append(f"keyword-tokens:{keyword_overlap}")
            if category_overlap:
                score += 5 * category_overlap
                reasons.append(f"category-tokens:{category_overlap}")
            if description_overlap:
                score += 2 * description_overlap
                reasons.append(f"description-tokens:{description_overlap}")
            if query_tokens and query_tokens.issubset(all_tokens):
                score += 25
                reasons.append("all-query-tokens-covered")

            if not query_tokens:
                score = 1
                reasons = ["empty-query"]

            if score > 0:
                matches.append(
                    {
                        "score": score,
                        "reasons": reasons,
                        "skill": skill,
                    }
                )

        matches.sort(
            key=lambda item: (
                -int(item["score"]),
                _norm(str(item["skill"].get("name", ""))),
                str(item["skill"].get("id", "")),
            )
        )
        return {"query": query, "total": len(matches), "matches": matches[:limit]}

    def match(
        self,
        intent: str,
        category: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        result = self.search(intent, category=category, limit=limit)
        return {
            "intent": intent,
            "selected": result["matches"],
            "deterministic": True,
            "strategy": "exact+token-weighted-metadata",
        }

    def dependencies(self, reference: str) -> dict[str, Any]:
        skill = self.get_skill(reference)
        resolved: list[dict[str, Any]] = []
        unresolved = list(_as_list(skill.get("unresolved_dependencies")))

        for dependency in _as_list(skill.get("dependencies")):
            found = self._resolve_ref(str(dependency))
            if found is None:
                unresolved.append(str(dependency))
            else:
                resolved.append(found)

        return {
            "skill": skill,
            "resolved_dependencies": resolved,
            "unresolved_dependencies": sorted(set(unresolved)),
        }

    def conflicts(self, reference: str) -> dict[str, Any]:
        skill = self.get_skill(reference)
        resolved: list[dict[str, Any]] = []
        unresolved = list(_as_list(skill.get("unresolved_conflicts")))

        for conflict in _as_list(skill.get("conflicts")):
            found = self._resolve_ref(str(conflict))
            if found is None:
                unresolved.append(str(conflict))
            else:
                resolved.append(found)

        return {
            "skill": skill,
            "resolved_conflicts": resolved,
            "unresolved_conflicts": sorted(set(unresolved)),
        }

    def _validation_issues(self, skill: dict[str, Any], check_content: bool) -> list[str]:
        issues: list[str] = []
        missing = sorted(REQUIRED_FIELDS - set(skill))
        issues.extend(f"MISSING_FIELD:{name}" for name in missing)

        if skill.get("status") not in SKILL_STATUSES:
            issues.append(f"INVALID_STATUS:{skill.get('status')}")
        if skill.get("category") not in SKILL_CATEGORIES:
            issues.append(f"INVALID_CATEGORY:{skill.get('category')}")

        for field in (
            "keywords",
            "dependencies",
            "conflicts",
            "unresolved_dependencies",
            "unresolved_conflicts",
        ):
            if field in skill and not isinstance(skill.get(field), list):
                issues.append(f"FIELD_NOT_ARRAY:{field}")

        cost = skill.get("estimated_context_cost")
        if not isinstance(cost, int) or isinstance(cost, bool) or cost < 0:
            issues.append("INVALID_ESTIMATED_CONTEXT_COST")

        content_path = str(skill.get("content_path", ""))
        if content_path:
            try:
                target = self._assert_within_hub(self.hub_root / content_path)
                if check_content and not target.is_file():
                    issues.append("CONTENT_NOT_FOUND")
            except CatalogError:
                issues.append("CONTENT_PATH_OUTSIDE_HUB")
        elif "content_path" in skill:
            issues.append("CONTENT_PATH_EMPTY")

        return sorted(set(issues))

    def validate(self, reference: str | None = None, check_content: bool = False) -> dict[str, Any]:
        skills = [self.get_skill(reference)] if reference else self._skills()
        results: list[dict[str, Any]] = []

        for skill in skills:
            issues = self._validation_issues(skill, check_content=check_content)
            results.append(
                {
                    "id": skill.get("id"),
                    "name": skill.get("name"),
                    "valid": not issues,
                    "issues": issues,
                }
            )

        invalid = sum(1 for item in results if not item["valid"])
        return {
            "valid": invalid == 0,
            "checked": len(results),
            "invalid": invalid,
            "results": results,
        }

    def bundle_plan(
        self,
        requested: list[str],
        max_context_cost: int = 12000,
    ) -> dict[str, Any]:
        if not requested:
            raise CatalogError("REQUESTED_SKILLS_EMPTY")
        if max_context_cost < 0:
            raise CatalogError("MAX_CONTEXT_COST_MUST_BE_NON_NEGATIVE")

        ordered: list[dict[str, Any]] = []
        permanent: set[str] = set()
        temporary: set[str] = set()
        unresolved: set[str] = set()
        cycles: list[list[str]] = []

        def key(skill: dict[str, Any]) -> str:
            return str(skill.get("id") or skill.get("name"))

        def visit(reference: str, trail: list[str]) -> None:
            skill = self._resolve_ref(reference)
            if skill is None:
                unresolved.add(reference)
                return
            skill_key = key(skill)
            if skill_key in permanent:
                return
            if skill_key in temporary:
                cycles.append(trail + [skill_key])
                return

            temporary.add(skill_key)
            for dependency in _as_list(skill.get("dependencies")):
                visit(str(dependency), trail + [skill_key])
            unresolved.update(str(item) for item in _as_list(skill.get("unresolved_dependencies")))
            temporary.remove(skill_key)
            permanent.add(skill_key)
            ordered.append(skill)

        for reference in requested:
            visit(reference, [])

        selected_ids = {key(skill) for skill in ordered}
        conflicts: list[dict[str, str]] = []
        for skill in ordered:
            source = key(skill)
            for conflict_ref in _as_list(skill.get("conflicts")):
                conflict_skill = self._resolve_ref(str(conflict_ref))
                if conflict_skill is not None and key(conflict_skill) in selected_ids:
                    pair = tuple(sorted((source, key(conflict_skill))))
                    if not any(tuple(sorted((item["a"], item["b"]))) == pair for item in conflicts):
                        conflicts.append({"a": pair[0], "b": pair[1]})

        total_cost = sum(int(skill.get("estimated_context_cost", 0) or 0) for skill in ordered)
        non_active = [
            {"id": skill.get("id"), "status": skill.get("status")}
            for skill in ordered
            if skill.get("status") != "ACTIVE"
        ]

        if unresolved or cycles or conflicts or total_cost > max_context_cost:
            verdict = "FAIL"
        elif non_active:
            verdict = "PARTIAL"
        else:
            verdict = "PASS"

        return {
            "requested": requested,
            "execution_order": [
                {
                    "id": skill.get("id"),
                    "name": skill.get("name"),
                    "status": skill.get("status"),
                    "estimated_context_cost": skill.get("estimated_context_cost", 0),
                }
                for skill in ordered
            ],
            "total_context_cost": total_cost,
            "max_context_cost": max_context_cost,
            "unresolved_dependencies": sorted(unresolved),
            "cycles": cycles,
            "conflicts": sorted(conflicts, key=lambda item: (item["a"], item["b"])),
            "non_active": non_active,
            "verdict": verdict,
            "mode": "READ_ONLY",
        }
