"""Parsing saved UIAutomator dumps into targets — the device-free substrate."""
import xml.etree.ElementTree as ET

import pytest

from bridge.hierarchy import (
    UiElement,
    load_corpus,
    parse_bounds,
    parse_hierarchy,
    tappable_targets,
)

DUMP = """<hierarchy rotation="0">
  <node bounds="[0,0][1080,2340]" clickable="false" resource-id="root"/>
  <node bounds="[100,200][300,320]" clickable="true" text="Submit" resource-id="a/btn_submit"/>
  <node bounds="[0,0][1080,2340]" clickable="true" content-desc="whole screen"/>
  <node bounds="[10,10][14,14]" clickable="true" text="speck"/>
  <node bounds="[400,200][500,300]" clickable="false" text="Label"/>
  <node bounds="garbage" clickable="true" text="broken"/>
</hierarchy>"""


def test_bounds_parse_to_a_rectangle():
    assert parse_bounds("[12,34][56,78]") == (12, 34, 56, 78)


@pytest.mark.parametrize("bad", ["", None, "12,34,56,78", "[1,2][3]"])
def test_malformed_bounds_are_rejected(bad):
    with pytest.raises(ValueError):
        parse_bounds(bad)


def test_elements_are_centred_on_their_bounds():
    submit = next(e for e in parse_hierarchy(DUMP) if e.text == "Submit")
    assert (submit.x, submit.y) == (200.0, 260.0)
    assert (submit.width, submit.height) == (200.0, 120.0)


def test_a_node_with_unusable_bounds_is_skipped_not_fatal():
    assert all(e.text != "broken" for e in parse_hierarchy(DUMP))


def test_labels_fall_back_from_text_to_description_to_id():
    by_id = {e.element_id for e in parse_hierarchy(DUMP)}
    assert "Submit" in by_id
    assert "whole screen" in by_id
    assert "root" in by_id


def test_only_clickable_elements_of_a_plausible_size_are_targets():
    labels = {t.element_id for t in tappable_targets(parse_hierarchy(DUMP))}
    assert labels == {"Submit"}  # label not clickable, screen too big, speck too small


def test_a_target_is_shaped_the_way_the_simulator_expects():
    target = tappable_targets(parse_hierarchy(DUMP))[0].as_target()
    assert set(target) == {"id", "x", "y", "width", "height"}


@pytest.mark.parametrize("source", ["path", "string", "element"])
def test_hierarchy_accepts_a_path_a_string_or_a_parsed_tree(tmp_path, source):
    path = tmp_path / "dump.xml"
    path.write_text(DUMP, encoding="utf-8")
    given = {"path": str(path), "string": DUMP, "element": ET.fromstring(DUMP)}[source]
    assert len(parse_hierarchy(given)) == 5


def test_area_is_width_times_height():
    assert UiElement("x", 0, 0, 20.0, 5.0, "", "", True).area == 100.0


def test_a_corpus_is_keyed_by_screen_name(tmp_path):
    (tmp_path / "dialer.xml").write_text(DUMP, encoding="utf-8")
    (tmp_path / "settings.xml").write_text(DUMP, encoding="utf-8")
    corpus = load_corpus(tmp_path)
    assert set(corpus) == {"dialer", "settings"}
    assert all(len(v) == 1 for v in corpus.values())


def test_the_real_saved_dump_yields_usable_targets():
    """The dump committed with the component parses and gives real element sizes."""
    targets = tappable_targets(parse_hierarchy("biometry/window_dump.xml"))
    assert len(targets) > 10
    sides = [min(t.width, t.height) for t in targets]
    assert min(sides) >= 20 and max(sides) <= 900
