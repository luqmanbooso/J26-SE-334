"""Dataset loading for offline healing evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_hierarchies(directory: str | Path) -> list[tuple[str, str]]:
    """Load XML hierarchy files in deterministic filename order."""
    root = Path(directory)
    return [(path.name, path.read_text(encoding="utf-8")) for path in sorted(root.glob("*.xml"))]


def load_release_pairs(manifest_json: str | Path) -> list[dict[str, Any]]:
    """Load and validate hand-labelled release-pair scenarios."""
    payload = json.loads(Path(manifest_json).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("release manifest must be a JSON list")
    required = {"name", "old_xml_path", "new_xml_path", "script_locator", "expected_new"}
    result = []
    for item in payload:
        if not isinstance(item, dict) or not required.issubset(item):
            raise ValueError("each release pair must contain the required fields")
        result.append(item)
    return result

