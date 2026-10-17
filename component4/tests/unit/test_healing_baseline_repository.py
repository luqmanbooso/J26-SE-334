from __future__ import annotations

import json

from c4.healing.baseline import BaselineStore
from c4.store.repository import TestRepository as VersionedRepository


def test_baseline_store_round_trip_is_keyed_by_test_and_step(tmp_path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "baseline").mkdir(parents=True)
    (run_dir / "baseline" / "step_0.xml").write_text(
        '<hierarchy resource-id="never-used"><node /></hierarchy>',
        encoding="utf-8",
    )
    (run_dir / "synthesized_test.py").write_text(
        'CAPABILITIES = {"appPackage": "com.example"}\n', encoding="utf-8"
    )
    store = BaselineStore(tmp_path / "baselines")
    store.save_from_run("journey", run_dir)

    assert store.load("journey", 0).startswith("<hierarchy")
    assert store.load("never-used", 0) is None
    index = json.loads(
        (tmp_path / "baselines" / "journey" / "index.json").read_text()
    )
    assert index["app_package"] == "com.example"


def test_repository_versions_are_append_only_with_parent_links(tmp_path) -> None:
    repository = VersionedRepository(tmp_path / "repo")
    first = repository.add_version("journey", "one", "synthesized", None, None)
    second = repository.add_version("journey", "two", "healed", first, None)

    assert repository.latest("journey") == (2, "two")
    assert second == 2
    history = repository.history("journey")
    assert [entry["version"] for entry in history] == [1, 2]
    assert history[1]["parent"] == 1
    assert (tmp_path / "repo" / "journey" / "v1.py").read_text() == "one"
