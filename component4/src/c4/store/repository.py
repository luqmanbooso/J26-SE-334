"""Append-only versioned test repository."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from c4.healing.models import HealingDecision, HealingStatus


class TestRepository:
    """Persist generated scripts and auditable healing history."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def add_version(
        self,
        test_id: str,
        script: str,
        reason: str,
        parent_version: int | None,
        decision: HealingDecision | None,
    ) -> int:
        target = self.root / test_id
        target.mkdir(parents=True, exist_ok=True)
        history = self.history(test_id)
        version = len(history) + 1
        (target / f"v{version}.py").write_text(script, encoding="utf-8")
        entry = {
            "version": version,
            "parent": parent_version,
            "reason": reason,
            "sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
            "status": decision.status.value if decision else "generated",
            "old_locator": decision.original_locator if decision else None,
            "new_locator": decision.healed_locator if decision else None,
            "confidence": decision.confidence if decision else None,
        }
        history.append(entry)
        (target / "versions.json").write_text(
            json.dumps(history, indent=2, sort_keys=True), encoding="utf-8"
        )
        return version

    def latest(self, test_id: str) -> tuple[int, str]:
        history = self.history(test_id)
        if not history:
            raise FileNotFoundError(f"No versions for test: {test_id}")
        version = int(history[-1]["version"])
        return version, (self.root / test_id / f"v{version}.py").read_text(encoding="utf-8")

    def history(self, test_id: str) -> list[dict[str, object]]:
        path = self.root / test_id / "versions.json"
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, list) else []
