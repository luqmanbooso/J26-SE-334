"""Version-independent baseline hierarchy storage."""

from __future__ import annotations

import hashlib
import ast
import json
import shutil
from pathlib import Path


class BaselineStore:
    """Store captured step hierarchies keyed by test id and step index."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def save_from_run(self, test_id: str, run_dir: Path) -> None:
        """Copy captured baseline files and write deterministic metadata."""
        target = self.root / test_id
        target.mkdir(parents=True, exist_ok=True)
        for source in sorted((Path(run_dir) / "baseline").glob("step_*.xml")):
            if source.stem.removeprefix("step_").isdigit():
                shutil.copyfile(source, target / source.name)
        script = Path(run_dir) / "synthesized_test.py"
        package = _read_package(script)
        steps = len(list(target.glob("step_*.xml")))
        index = {
            "script_sha256": hashlib.sha256(script.read_bytes()).hexdigest()
            if script.exists()
            else None,
            "script_text_sha256": script_digest(script.read_text(encoding="utf-8"))
            if script.exists()
            else None,
            "app_package": package,
            "step_count": steps,
        }
        (target / "index.json").write_text(
            json.dumps(index, indent=2, sort_keys=True), encoding="utf-8"
        )

    def load(self, test_id: str, step_index: int, script: str | None = None) -> str | None:
        """Load one baseline hierarchy by test id and step index.

        When ``script`` is given, the baseline is returned only if it was captured
        from that same script, so step indexes cannot drift between versions.
        Baselines saved without a script hash (before this check existed) are
        ignored: they were captured from failing runs and show the changed screen.
        """
        path = self.root / test_id / f"step_{step_index}.xml"
        if not path.is_file():
            return None
        if script is not None:
            try:
                recorded = json.loads((self.root / test_id / "index.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
            if recorded.get("script_text_sha256") != script_digest(script):
                return None
        return path.read_text(encoding="utf-8")


def script_digest(script: str) -> str:
    """Hash script text independent of platform line endings."""
    return hashlib.sha256(script.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def _read_package(script: Path) -> str | None:
    if not script.exists():
        return None
    try:
        tree = ast.parse(script.read_text(encoding="utf-8"))
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            for key, value in zip(node.value.keys, node.value.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "appPackage"
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    return value.value
    return None
