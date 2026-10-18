"""Create deterministic Sentry telemetry journeys for Android Settings paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def make_payload(labels: list[str], index: int) -> dict[str, Any]:
    """Build one deterministic Sentry event for a Settings label path."""
    digest = hashlib.sha256(
        json.dumps(labels, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    breadcrumbs = [
        {
            "timestamp": f"2026-01-01T00:00:{step:02d}Z",
            "category": "ui.click",
            "data": {"text": label},
        }
        for step, label in enumerate(labels, start=1)
    ]
    return {
        "event_id": f"synthetic-settings-{index:04d}-{digest}",
        "timestamp": "2026-01-01T00:01:00Z",
        "release": "synthetic",
        "exception": {
            "values": [
                {
                    "type": "SyntheticSettingsFailure",
                    "value": "synthetic evaluation failure",
                }
            ]
        },
        "breadcrumbs": breadcrumbs,
    }


def main(argv: list[str] | None = None) -> int:
    """Generate one Sentry JSON file per label path."""
    parser = argparse.ArgumentParser(prog="python -m evaluation.make_settings_journeys")
    parser.add_argument("--labels", required=True)
    parser.add_argument("--out", required=True)
    try:
        args = parser.parse_args(argv)
        payload = json.loads(Path(args.labels).read_text(encoding="utf-8-sig"))
        if not isinstance(payload, list) or not all(
            isinstance(path, list) and all(isinstance(label, str) for label in path)
            for path in payload
        ):
            raise ValueError("labels must be a JSON list of string lists")
        output = Path(args.out)
        output.mkdir(parents=True, exist_ok=True)
        for index, labels in enumerate(payload, start=1):
            path = output / f"settings_{index:04d}.json"
            path.write_text(
                json.dumps(make_payload(labels, index), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
