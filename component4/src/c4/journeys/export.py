"""Deterministic journey seed file export."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from c4.schemas import (
    FailureJourney,
    JourneyDocument,
    document_to_journey,
    journey_to_document,
)


def load_hint_rules(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load and validate the editable perturbation hint table."""
    rules_path = Path(path) if path else Path(__file__).parents[3] / "configs" / "perturbation_hints.json"
    try:
        payload = json.loads(rules_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Unable to load perturbation hint rules: {rules_path}") from error
    if not isinstance(payload, list):
        raise ValueError("perturbation hint rules must be a JSON list")
    for rule in payload:
        if (
            not isinstance(rule, dict)
            or not isinstance(rule.get("match"), dict)
            or not isinstance(rule.get("stressor"), str)
            or not isinstance(rule.get("note"), str)
        ):
            raise ValueError("each perturbation hint rule needs match, stressor, and note")
        if not any(key in rule["match"] for key in ("exception_type_contains", "message_contains")):
            raise ValueError("hint rule match must contain an exception_type_contains or message_contains list")
        for values in rule["match"].values():
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                raise ValueError("hint rule match values must be string lists")
    return payload


def write_journeys(
    journeys: list[FailureJourney],
    out_dir: str | Path,
    hint_rules: list[dict[str, Any]] | None = None,
) -> Path:
    """Write one document per journey and a deterministic index."""
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    documents = [journey_to_document(journey, hint_rules) for journey in journeys]
    entries = []
    for document in sorted(documents, key=lambda item: item.journey_id):
        filename = f"{_safe_id(document.journey_id)}.json"
        (target / filename).write_text(
            json.dumps(document.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        entries.append({"journey_id": document.journey_id, "file": filename})
    (target / "journeys_index.json").write_text(
        json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return target


def load_journeys(path_or_dir: str | Path) -> list[FailureJourney]:
    """Load one journey document or all indexed documents in a directory."""
    path = Path(path_or_dir)
    paths = [path] if path.is_file() else sorted(
        item for item in path.glob("*.json") if item.name != "journeys_index.json"
    )
    documents = [
        JourneyDocument.model_validate(json.loads(item.read_text(encoding="utf-8")))
        for item in paths
    ]
    return [document_to_journey(doc) for doc in sorted(documents, key=lambda item: item.journey_id)]


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return safe or "journey"
