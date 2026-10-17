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
            "app_package": package,
            "step_count": steps,
        }
        (target / "index.json").write_text(
            json.dumps(index, indent=2, sort_keys=True), encoding="utf-8"
        )

    def load(self, test_id: str, step_index: int) -> str | None:
        """Load one baseline hierarchy by test id and step index."""
        path = self.root / test_id / f"step_{step_index}.xml"
        return path.read_text(encoding="utf-8") if path.is_file() else None


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
