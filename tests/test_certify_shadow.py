from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_certify_shadow_script_passes_against_bootstrap_hub(tmp_path: Path) -> None:
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

    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "certify_shadow.py"

    completed = subprocess.run(
        [sys.executable, str(script), "--hub-root", str(hub)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "REGISTRY_STATE=BOOTSTRAP" in completed.stdout
    assert "TOTAL_ENTRIES=0" in completed.stdout
    assert "SEARCH_TOTAL=0" in completed.stdout
    assert "MCP_MISSING=" in completed.stdout
    assert "MCP_UNEXPECTED=" in completed.stdout
    assert "MCP_CONTRACT=PASS" in completed.stdout
    assert "RESULT=PASS" in completed.stdout
