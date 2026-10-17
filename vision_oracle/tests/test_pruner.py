"""
Unit tests for HierarchyPruner.
Verifies XML and JSON parsing, wrapper collapse, coordinate normalization, and token reduction telemetry.
"""

import pytest
from local_vision_oracle.pruner import HierarchyPruner, PrunedNode


SAMPLE_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.example.app" bounds="[0,0][1080,2400]" checkable="false" checked="false" clickable="false" enabled="true" focusable="false" focused="false" scrollable="false" long-clickable="false" password="false" selected="false">
    <node index="0" text="" resource-id="" class="android.widget.LinearLayout" package="com.example.app" bounds="[0,0][1080,2400]" checkable="false" checked="false" clickable="false" enabled="true" focusable="false" focused="false" scrollable="false" long-clickable="false" password="false" selected="false">
      <!-- Empty zero-area spacer -->
      <node index="0" text="" class="android.view.View" bounds="[0,0][0,0]" clickable="false" />
      <!-- Off-screen element -->
      <node index="1" text="Hidden" class="android.widget.TextView" bounds="[0,2500][1080,2600]" clickable="false" />
      <!-- Valid Header TextView -->
      <node index="2" text="Shopping Cart" resource-id="com.example.app:id/title" class="android.widget.TextView" bounds="[48,120][540,240]" checkable="false" checked="false" clickable="false" enabled="true" focusable="false" focused="false" scrollable="false" long-clickable="false" password="false" selected="false" />
      <!-- Valid Clickable Checkout Button -->
      <node index="3" text="Checkout" resource-id="com.example.app:id/btn_checkout" class="android.widget.Button" bounds="[60,2100][1020,2280]" checkable="false" checked="false" clickable="true" enabled="true" focusable="true" focused="false" scrollable="false" long-clickable="false" password="false" selected="false" />
      <!-- Icon button with empty text but non-empty content-desc -->
      <node index="4" text="" content-desc="Back Navigation" resource-id="com.example.app:id/btn_back" class="android.widget.ImageButton" bounds="[20,40][120,140]" checkable="false" checked="false" clickable="true" enabled="true" focusable="true" focused="false" scrollable="false" long-clickable="false" password="false" selected="false" />
    </node>
  </node>
</hierarchy>
"""

SAMPLE_RICO_JSON = {
    "root": {
        "class": "android.widget.FrameLayout",
        "bounds": [0, 0, 1080, 2400],
        "clickable": False,
        "children": [
            {
                "class": "android.widget.LinearLayout",
                "bounds": [0, 0, 1080, 2400],
                "clickable": False,
                "children": [
                    {
                        "class": "android.widget.TextView",
                        "resource-id": "com.rico:id/welcome",
                        "text": "Welcome to Rico Store",
                        "bounds": [100, 200, 980, 350],
                        "clickable": False
                    },
                    {
                        "class": "android.widget.Button",
                        "resource-id": "com.rico:id/btn_buy",
                        "text": "Buy Now",
                        "bounds": [100, 1800, 980, 1950],
                        "clickable": True
                    }
                ]
            }
        ]
    }
}


def test_prune_xml_extracts_interactive_and_text_nodes():
    pruner = HierarchyPruner(screen_width=1080, screen_height=2400)
    nodes = pruner.prune_xml(SAMPLE_XML)

    # Should retain 3 nodes: Title TextView, Checkout Button, Back ImageButton
    assert len(nodes) == 3

    # Check Title TextView
    title_node = next(n for n in nodes if "title" in n.element_id)
    assert title_node.text == "Shopping Cart"
    assert title_node.clickable is False
    # Check normalized bounds [ymin, xmin, ymax, xmax]
    # y1=120/2400 = 50, x1=48/1080 = 44, y2=240/2400 = 100, x2=540/1080 = 500
    assert title_node.bounds == [50, 44, 100, 500]

    # Check Button
    btn_node = next(n for n in nodes if "btn_checkout" in n.element_id)
    assert btn_node.text == "Checkout"
    assert btn_node.clickable is True

    # Check ImageButton (retained via content-desc + clickable)
    back_node = next(n for n in nodes if "btn_back" in n.element_id)
    assert back_node.content_desc == "Back Navigation"
    assert back_node.clickable is True


def test_prune_filters_zero_area_and_offscreen():
    pruner = HierarchyPruner(screen_width=1080, screen_height=2400)
    nodes = pruner.prune_xml(SAMPLE_XML)

    # Zero-area and off-screen nodes must not be present
    for n in nodes:
        assert n.text != "Hidden"
        # Area must be > 0
        ymin, xmin, ymax, xmax = n.bounds
        assert ymax > ymin
        assert xmax > xmin


def test_prune_rico_json():
    pruner = HierarchyPruner(screen_width=1080, screen_height=2400)
    nodes = pruner.prune_rico_json(SAMPLE_RICO_JSON)

    assert len(nodes) == 2
    texts = [n.text for n in nodes]
    assert "Welcome to Rico Store" in texts
    assert "Buy Now" in texts

    buy_btn = next(n for n in nodes if n.text == "Buy Now")
    assert buy_btn.clickable is True
    # Verify bounds normalized
    assert 0 <= buy_btn.bounds[0] <= 1000
    assert 0 <= buy_btn.bounds[1] <= 1000


def test_prune_limits_max_nodes():
    pruner = HierarchyPruner(screen_width=1080, screen_height=2400, max_nodes=1)
    nodes = pruner.prune_xml(SAMPLE_XML)
    assert len(nodes) == 1


def test_reduction_telemetry():
    pruner = HierarchyPruner(screen_width=1080, screen_height=2400)
    pruner.prune_xml(SAMPLE_XML)
    stats = pruner.get_reduction_stats()

    assert stats["raw_nodes"] > stats["pruned_nodes"]
    assert stats["reduction_pct"] > 40.0


def test_handles_empty_or_malformed_xml():
    pruner = HierarchyPruner()
    assert pruner.prune_xml("") == []
    assert pruner.prune_xml("not valid xml <<<>>>") == []
    assert pruner.prune_rico_json("") == []
    assert pruner.prune_rico_json("{bad json") == []


def test_pruned_node_to_prompt_string():
    node = PrunedNode(
        element_id="com.app:id/submit",
        class_name="android.widget.Button",
        text="Submit Order",
        content_desc="",
        bounds=[800, 100, 900, 900],
        clickable=True,
        scrollable=False
    )
    prompt_str = node.to_prompt_string()
    assert '<Button' in prompt_str
    assert 'id="submit"' in prompt_str
    assert 'text="Submit Order"' in prompt_str
    assert 'bounds=[800, 100, 900, 900]' in prompt_str
    assert 'clickable' in prompt_str


def test_detect_layout_collisions():
    pruner = HierarchyPruner()
    # Node A: Card view at bottom of screen
    node_card = PrunedNode(
        element_id="com.app:id/reservation_card",
        class_name="android.widget.CardView",
        text="Reservation Details",
        content_desc="",
        bounds=[700, 50, 920, 950],
        clickable=True,
        scrollable=False,
    )
    # Node B: Fixed Bottom Navigation Bar occluding card
    node_nav = PrunedNode(
        element_id="com.app:id/bottom_navigation",
        class_name="android.widget.BottomNavigationView",
        text="",
        content_desc="Navigation Bar",
        bounds=[850, 0, 1000, 1000],
        clickable=True,
        scrollable=False,
    )
    # Node C: Non-overlapping header button
    node_header = PrunedNode(
        element_id="com.app:id/back_btn",
        class_name="android.widget.ImageButton",
        text="",
        content_desc="Back",
        bounds=[50, 50, 150, 150],
        clickable=True,
        scrollable=False,
    )

    collisions = pruner.detect_layout_collisions([node_card, node_nav, node_header])
    assert len(collisions) == 1
    col = collisions[0]
    assert col["element_a_id"] == "com.app:id/reservation_card"
    assert col["element_b_id"] == "com.app:id/bottom_navigation"
    assert col["collision_bbox"] == [850, 50, 920, 950]
    assert col["overlap_ratio"] > 0.20

